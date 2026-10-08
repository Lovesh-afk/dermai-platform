"""
Loads the trained skin-condition classifier and runs inference.

This model was NOT trained as part of this codebase — it's an
existing, separately-trained MobileNetV2 model being integrated as
the platform's real serving model (see docs/DECISIONS.md for the
full reasoning). The preprocessing here deliberately matches the
original training pipeline exactly (simple 0-1 rescaling, no
ImageNet mean/std normalization) — using different preprocessing
than what the model was trained on would silently produce wrong
predictions even though the code would run without error.
"""
import json
from pathlib import Path

import numpy as np
from PIL import Image

MODEL_DIR = Path(__file__).resolve().parent.parent / "models"
MODEL_PATH = MODEL_DIR / "skin_disease_model.h5"
CLASS_LABELS_PATH = MODEL_DIR / "class_labels.txt"
IMG_SIZE = 224

# Per-class info shown alongside a prediction — mirrors the source
# model's intended usage. "confidence" alone isn't actionable for a
# patient; a plain-language label and next-step guidance is.
CLASS_INFO = {
    "normal": {
        "label": "No condition detected",
        "guidance": "No signs of the conditions this model screens for. This is not a substitute for a dermatologist visit if something feels wrong.",
    },
    "acne": {
        "label": "Signs consistent with acne",
        "guidance": "Consider gentle, non-comedogenic skincare. See a dermatologist if it's persistent, painful, or scarring.",
    },
    "eczema": {
        "label": "Signs consistent with eczema",
        "guidance": "Avoid known irritants and fragranced products. A dermatologist can confirm and prescribe appropriate treatment.",
    },
    "fungal": {
        "label": "Signs consistent with a fungal infection",
        "guidance": "Keep the area clean and dry. See a doctor for confirmation and antifungal treatment — self-treating the wrong condition can make things worse.",
    },
}

DISCLAIMER = (
    "This is an AI-generated preliminary screening, not a medical diagnosis. "
    "It can be wrong, including confidently wrong. Always consult a licensed "
    "dermatologist for an actual diagnosis and before starting any treatment."
)

_model = None
_classes = None


def _load_model():
    """Lazy singleton load — the model is ~24MB and loading it is not
    free; every caller in a running server process should share one
    loaded instance rather than reloading per-request."""
    global _model, _classes
    if _model is None:
        import tensorflow as tf  # imported lazily so importing this module doesn't require TF unless actually predicting

        if not MODEL_PATH.exists():
            raise FileNotFoundError(
                f"Model file not found at {MODEL_PATH}. See ai/models/README.md for how to obtain it."
            )
        _model = tf.keras.models.load_model(str(MODEL_PATH))
        with open(CLASS_LABELS_PATH) as f:
            _classes = [line.strip() for line in f.readlines() if line.strip()]
    return _model, _classes


def preprocess_image(image: Image.Image) -> np.ndarray:
    """Must exactly match the preprocessing used when this model was
    trained (simple /255 rescale, RGB, 224x224) — see module docstring."""
    img = image.convert("RGB").resize((IMG_SIZE, IMG_SIZE))
    arr = np.array(img, dtype=np.float32) / 255.0
    return np.expand_dims(arr, axis=0)


def predict(image: Image.Image) -> dict:
    """Returns the full prediction payload: top class, confidence,
    every class's probability, plain-language guidance, and the
    disclaimer — everything the Prediction API (Phase 8) needs to
    hand back to the frontend without reimplementing any of this."""
    model, classes = _load_model()
    tensor = preprocess_image(image)
    raw_preds = model.predict(tensor, verbose=0)[0]

    idx = int(np.argmax(raw_preds))
    predicted_class = classes[idx]
    confidence = float(raw_preds[idx])

    all_probabilities = {classes[i]: float(raw_preds[i]) for i in range(len(classes))}
    info = CLASS_INFO.get(predicted_class, {
        "label": predicted_class.replace("_", " ").title(),
        "guidance": "Consult a dermatologist for an accurate assessment.",
    })

    return {
        "predicted_class": predicted_class,
        "label": info["label"],
        "confidence": confidence,
        "guidance": info["guidance"],
        "all_probabilities": all_probabilities,
        "disclaimer": DISCLAIMER,
    }
