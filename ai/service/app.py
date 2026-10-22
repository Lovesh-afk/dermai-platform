"""
Inference microservice: the only process that loads the TensorFlow
model. The main backend never imports TensorFlow — it sends an image
here over HTTP and gets JSON back.

Why a separate service:
  - Keeps the ~600MB TensorFlow dependency out of the backend image.
  - The model can be scaled, restarted, or swapped independently of
    the rest of the app (e.g. move this one container onto a GPU box).
  - A clear contract: image in -> prediction + heatmap out.

Why the Keras model and not the ONNX export: Grad-CAM needs gradients,
and ONNX Runtime only runs forward passes. The ONNX file stays in the
repo as a verified artifact for any future prediction-only deployment.
"""
import base64
import io
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError

from inference.gradcam import generate_gradcam_overlay
from inference.predictor import _load_model, predict, preprocess_image

MAX_IMAGE_BYTES = 10 * 1024 * 1024  # mirrors the backend's upload limit
HEATMAP_MAX_SIDE = 512  # keeps the heatmap PNG small regardless of upload size


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load the model once at startup, so the first real request isn't
    # stuck waiting several seconds for TensorFlow to initialise.
    _load_model()
    yield


app = FastAPI(title="DermAI Inference Service", version="1.0.0", lifespan=lifespan)


@app.get("/health")
def health():
    model, classes = _load_model()
    return {"status": "ok", "classes": classes}


@app.post("/predict")
async def predict_endpoint(file: UploadFile = File(...)):
    content = await file.read()
    if len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image too large")

    try:
        image = Image.open(io.BytesIO(content))
        image.load()  # force a full decode now, so corrupt files fail here
    except (UnidentifiedImageError, OSError):
        raise HTTPException(status_code=400, detail="File is not a readable image")

    image = image.convert("RGB")
    image.thumbnail((HEATMAP_MAX_SIDE, HEATMAP_MAX_SIDE))  # in-place, keeps aspect ratio

    result = predict(image)

    # Explain the top prediction with Grad-CAM
    model, classes = _load_model()
    class_idx = classes.index(result["predicted_class"])
    overlay = generate_gradcam_overlay(model, preprocess_image(image), image, class_idx)

    buffer = io.BytesIO()
    overlay.save(buffer, format="PNG")
    result["gradcam_png_base64"] = base64.b64encode(buffer.getvalue()).decode("ascii")
    result["model_name"] = "mobilenetv2-skin-4class"
    return result
