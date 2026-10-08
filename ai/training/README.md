# Training a real model from scratch

The model currently in `ai/models/` was integrated from an existing
project, not trained here (see `ai/models/README.md`). This document
is for when you're ready to do the real thing — a proper model
trained on the datasets from the original spec (HAM10000, ISIC,
DermNet, PAD-UFES-20, Fitzpatrick17k), covering the full 20+
condition set.

## Why not in this dev environment

Real training needs two things this sandboxed development environment
doesn't have:
- **A GPU.** CPU training on a real dataset (tens of thousands of
  images) would take days-to-weeks instead of hours.
- **Access to the dataset hosts.** HAM10000/ISIC/DermNet are hosted on
  Kaggle, the ISIC Archive, and Harvard Dataverse — none reachable
  from this sandbox's restricted network.

## Where to actually run it: Google Colab (recommended, free GPU)

1. Go to [colab.research.google.com](https://colab.research.google.com), new notebook
2. **Runtime → Change runtime type → T4 GPU** (free tier)
3. Download the datasets directly into the Colab environment (Colab
   *can* reach Kaggle/the ISIC Archive):
   ```python
   # Kaggle datasets (HAM10000, PAD-UFES-20 mirrors, etc.)
   !pip install kaggle
   # upload your kaggle.json API token, then:
   !kaggle datasets download -d kmader/skin-cancer-mnist-ham10000
   !unzip skin-cancer-mnist-ham10000.zip -d ham10000/

   # ISIC Archive has its own API/CLI: https://api.isic-archive.com/
   ```
4. Clone this repo into Colab (or upload `ai/` as a zip) and install:
   ```python
   !pip install -r ai/requirements.txt
   !pip install torch torchvision albumentations timm  # full training stack — not needed for inference-only, see below
   ```
5. Adapt `ai/training/train.py` (a template, not written yet — see
   "What's not built yet" below) to point at your downloaded dataset
   folders and run it.
6. Once trained, export to ONNX (`ai/training/export_onnx.py` — note
   this currently assumes a Keras model; a PyTorch model needs
   `torch.onnx.export` instead, a straightforward swap) and download
   the resulting `.onnx`/`.h5` file back to your machine.
7. Replace `ai/models/skin_disease_model.h5` (or `.onnx`) with your
   new file, update `ai/models/class_labels.txt` to match your real
   class list, and update `CLASS_INFO` in `ai/inference/predictor.py`
   accordingly.
8. Run `ai/tests/` against the new model to confirm the inference
   pipeline still works, and `ai/training/evaluate.py` against a real
   held-out test set to get real accuracy numbers.

## What's not built yet

This project currently has the **inference side** fully built and
tested (`ai/inference/predictor.py`, `ai/inference/gradcam.py`,
`ai/training/export_onnx.py`, `ai/training/evaluate.py`) — everything
needed to *serve* a trained model.

The **training loop itself** (data loading from the real dataset
formats, augmentation, the actual `model.fit(...)`/training loop,
cross-validation, class balancing for the real 20+-class,
imbalanced dataset) is not written yet, since building it against
datasets this environment can't download or verify would mean
shipping untested code — the same standard applied to every other
part of this project. That's the next piece of work once you have
real dataset access (Colab or a local GPU machine).
