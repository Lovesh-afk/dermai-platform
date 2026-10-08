"""
Real tests against the real model file — not mocked. These load the
actual 23MB skin_disease_model.h5, run actual TensorFlow inference,
and check real invariants (probabilities sum to 1, confidence is in
range, all 4 classes are represented, etc). Slower than a typical unit
test (model loading alone takes a few seconds) but the whole point of
this module is "does the real model actually produce sane output" —
mocking that away would test nothing meaningful.
"""
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from inference.predictor import predict, preprocess_image, CLASS_INFO, DISCLAIMER  # noqa: E402


def _sample_image() -> Image.Image:
    img = Image.new("RGB", (300, 300), color=(210, 180, 160))
    draw = ImageDraw.Draw(img)
    draw.ellipse((80, 80, 220, 220), fill=(160, 70, 50))
    return img


def test_preprocess_image_shape_and_range():
    img = _sample_image()
    tensor = preprocess_image(img)
    assert tensor.shape == (1, 224, 224, 3)
    assert tensor.dtype == np.float32
    assert tensor.min() >= 0.0 and tensor.max() <= 1.0


def test_preprocess_handles_non_rgb_input():
    """A grayscale or RGBA upload shouldn't crash preprocessing — real
    patient uploads won't always be clean RGB JPEGs."""
    grayscale = Image.new("L", (300, 300), color=128)
    tensor = preprocess_image(grayscale)
    assert tensor.shape == (1, 224, 224, 3)

    rgba = Image.new("RGBA", (300, 300), color=(200, 150, 130, 255))
    tensor = preprocess_image(rgba)
    assert tensor.shape == (1, 224, 224, 3)


def test_predict_returns_complete_payload():
    result = predict(_sample_image())

    assert result["predicted_class"] in CLASS_INFO
    assert 0.0 <= result["confidence"] <= 1.0
    assert result["label"]
    assert result["guidance"]
    assert result["disclaimer"] == DISCLAIMER


def test_predict_probabilities_sum_to_approximately_one():
    result = predict(_sample_image())
    total = sum(result["all_probabilities"].values())
    assert abs(total - 1.0) < 1e-4


def test_predict_all_four_classes_present():
    result = predict(_sample_image())
    assert set(result["all_probabilities"].keys()) == {"acne", "eczema", "fungal", "normal"}


def test_predict_top_class_matches_max_probability():
    """The predicted_class must actually be the argmax of
    all_probabilities — these are computed from the same underlying
    prediction but returned as two separate fields, so it's worth
    confirming they never drift apart."""
    result = predict(_sample_image())
    top_from_probs = max(result["all_probabilities"], key=result["all_probabilities"].get)
    assert result["predicted_class"] == top_from_probs


def test_predict_is_deterministic_for_the_same_image():
    """No dropout/randomness should be active at inference time —
    the same image must produce the same prediction every time."""
    img = _sample_image()
    result1 = predict(img)
    result2 = predict(img)
    assert result1["all_probabilities"] == result2["all_probabilities"]
