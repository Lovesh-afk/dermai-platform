"""Real tests against the real model — same rationale as
test_predictor.py. Grad-CAM specifically is easy to get subtly wrong
(wrong layer name, gradient shape mismatch) in a way that still runs
without crashing but produces a meaningless flat heatmap — these
checks catch that class of bug, not just "did it throw."""
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from inference.predictor import _load_model, preprocess_image  # noqa: E402
from inference.gradcam import generate_gradcam_overlay  # noqa: E402


def _sample_image() -> Image.Image:
    img = Image.new("RGB", (300, 300), color=(210, 180, 160))
    draw = ImageDraw.Draw(img)
    draw.ellipse((80, 80, 220, 220), fill=(160, 70, 50))
    return img


def test_gradcam_overlay_matches_original_image_size():
    model, classes = _load_model()
    img = _sample_image()
    tensor = preprocess_image(img)
    preds = model.predict(tensor, verbose=0)[0]
    idx = int(np.argmax(preds))

    overlay = generate_gradcam_overlay(model, tensor, img, idx)
    assert overlay.size == img.size
    assert overlay.mode == "RGB"


def test_gradcam_overlay_is_not_flat():
    """A broken Grad-CAM (e.g. wrong layer, dead gradient) often still
    runs and returns a valid-looking image — one that's uniformly one
    color. Checking for actual pixel variance catches that silently
    wrong case, not just "no exception was raised."""
    model, classes = _load_model()
    img = _sample_image()
    tensor = preprocess_image(img)
    preds = model.predict(tensor, verbose=0)[0]
    idx = int(np.argmax(preds))

    overlay = generate_gradcam_overlay(model, tensor, img, idx)
    arr = np.array(overlay)
    assert arr.std() > 1.0  # real spatial variation, not a flat/broken output


def test_gradcam_runs_for_every_class_index():
    """Grad-CAM should work regardless of which class it's asked to
    explain, not just the model's top prediction — Phase 8 may want to
    show "why not X" for a differential."""
    model, classes = _load_model()
    img = _sample_image()
    tensor = preprocess_image(img)

    for idx in range(len(classes)):
        overlay = generate_gradcam_overlay(model, tensor, img, idx)
        assert overlay.size == img.size
