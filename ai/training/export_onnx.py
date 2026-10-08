"""
Exports the trained Keras model to ONNX — the format the production
Prediction API (Phase 8) actually loads via onnxruntime, not the raw
.h5 file. ONNX Runtime is lighter to deploy (no full TensorFlow
dependency needed in the API container) and is the standard format
called for in the original project spec.

Run manually whenever models/skin_disease_model.h5 changes:
    python training/export_onnx.py
"""
from pathlib import Path

import tensorflow as tf
import tf2onnx

MODEL_DIR = Path(__file__).resolve().parent.parent / "models"
KERAS_MODEL_PATH = MODEL_DIR / "skin_disease_model.h5"
ONNX_OUTPUT_PATH = MODEL_DIR / "skin_disease_model.onnx"


def export():
    if not KERAS_MODEL_PATH.exists():
        raise FileNotFoundError(f"No Keras model found at {KERAS_MODEL_PATH} — nothing to export.")

    model = tf.keras.models.load_model(str(KERAS_MODEL_PATH))
    input_signature = (tf.TensorSpec((None, 224, 224, 3), tf.float32, name="input"),)

    tf2onnx.convert.from_keras(
        model, input_signature=input_signature, opset=13, output_path=str(ONNX_OUTPUT_PATH)
    )
    print(f"Exported ONNX model to {ONNX_OUTPUT_PATH}")


if __name__ == "__main__":
    export()
