"""HTTP-level tests for the inference service, against the real model."""
import base64
import io
import sys
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from service.app import app  # noqa: E402


def _image_bytes(fmt="JPEG", size=(300, 300)) -> bytes:
    img = Image.new("RGB", size, color=(210, 180, 160))
    ImageDraw.Draw(img).ellipse((80, 80, 220, 220), fill=(160, 70, 50))
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


def test_health_reports_classes():
    with TestClient(app) as client:
        resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["classes"] == ["acne", "eczema", "fungal", "normal"]


def test_predict_returns_prediction_and_heatmap():
    with TestClient(app) as client:
        resp = client.post("/predict", files={"file": ("rash.jpg", _image_bytes(), "image/jpeg")})
    assert resp.status_code == 200
    body = resp.json()
    assert body["predicted_class"] in {"acne", "eczema", "fungal", "normal"}
    assert 0.0 <= body["confidence"] <= 1.0
    assert body["disclaimer"]
    # heatmap must decode to a real PNG image
    heatmap = Image.open(io.BytesIO(base64.b64decode(body["gradcam_png_base64"])))
    assert heatmap.format == "PNG"


def test_large_upload_heatmap_is_downscaled():
    with TestClient(app) as client:
        resp = client.post("/predict", files={"file": ("big.png", _image_bytes("PNG", (2000, 1500)), "image/png")})
    heatmap = Image.open(io.BytesIO(base64.b64decode(resp.json()["gradcam_png_base64"])))
    assert max(heatmap.size) <= 512


def test_non_image_file_is_rejected():
    with TestClient(app) as client:
        resp = client.post("/predict", files={"file": ("notes.txt", b"definitely not an image", "image/jpeg")})
    assert resp.status_code == 400
