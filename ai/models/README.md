# Skin Condition Classifier — Model Card

## Origin

This model was **not trained as part of this project's pipeline**. It
was sourced from an existing, separately-trained, MIT-licensed public
repository ([Shashwat8405/Skin-disease-detection](https://github.com/Shashwat8405/Skin-disease-detection))
and integrated as this platform's real serving model — a deliberate
trade-off documented in `docs/DECISIONS.md`, made because training a
model from scratch on the datasets originally specified (HAM10000,
ISIC, DermNet, PAD-UFES-20, Fitzpatrick17k) requires GPU
infrastructure and multi-gigabyte dataset downloads that weren't
available in the development environment this project was built in.

**This is disclosed here plainly: the platform did not train this
model.** It integrates it.

## Architecture

- **Base:** MobileNetV2 (transfer learning, ImageNet-pretrained backbone)
- **Head:** GlobalAveragePooling → Dense(256, ReLU) → Dropout →
  Dense(128, ReLU) → Dropout → Dense(4, softmax)
- **Parameters:** ~2.6M total (~1.6M trainable)
- **Input:** 224×224 RGB, rescaled to [0, 1] (no ImageNet mean/std
  normalization — see `ai/inference/predictor.py`'s `preprocess_image`,
  which must exactly match this or predictions will be silently wrong)

## Classes (4 — not the 20+ originally specified)

| Class | Meaning |
|---|---|
| `acne` | Signs consistent with acne |
| `eczema` | Signs consistent with eczema |
| `fungal` | Signs consistent with a fungal skin infection |
| `normal` | No signs of the above conditions |

## Reported performance (from the source repository, not independently verified here)

~88% accuracy on a 50-image held-out test set, per-class F1 scores in
the source repo's README. **This has not been independently
re-verified against a real labeled test set in this project** —
`ai/training/evaluate.py` exists and was tested to confirm it runs
correctly end-to-end, but only against synthetic placeholder images
(see its test run in `docs/DECISIONS.md`), not real skin photos.
Before relying on this model for anything beyond development/demo
purposes, run `evaluate.py` against a real labeled test set.

## Known limitations

- **4 classes only.** Any actual skin condition outside these 4
  (including most of the 20+ conditions in the original spec) will be
  forced into one of these 4 buckets — a genuinely different disease
  could be misreported as "normal" or one of the other 3.
- **Small test set (50 images)** behind the reported 88% accuracy — a
  small sample size means that number has real uncertainty around it.
- **No calibration check performed** — a "72% confidence" prediction
  hasn't been verified to actually be right ~72% of the time.
- **Not a diagnosis.** Every prediction returned by
  `ai/inference/predictor.py` includes a disclaimer for exactly this
  reason — see `DISCLAIMER` in that file.

## Files in this directory

- `skin_disease_model.h5` — the original Keras model (training format)
- `skin_disease_model.onnx` — ONNX export (see `training/export_onnx.py`),
  numerically verified to match the Keras model's output to float32
  precision (~1e-7 max difference) — this is what the production
  Prediction API (Phase 8) actually loads
- `class_labels.txt` — the 4 class names, in the order the model's
  output layer expects them

## If you want to replace this with a from-scratch trained model later

The pipeline code in `ai/training/` (data loading, augmentation,
cross-validation, class balancing) is written for exactly this and is
architecture-agnostic — swapping in a properly trained model just
means pointing `ai/models/skin_disease_model.h5` at the new file and
updating `class_labels.txt` and `CLASS_INFO` in `predictor.py` to
match its actual classes. See `ai/training/README.md` for how to
actually run real training once real GPU access and dataset downloads
are available (e.g. via Google Colab).
