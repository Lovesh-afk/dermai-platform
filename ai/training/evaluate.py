"""
Evaluates the model against a labeled test set laid out as:

    test_data/
        acne/       *.jpg
        eczema/     *.jpg
        fungal/     *.jpg
        normal/     *.jpg

Reports accuracy, a full classification report (precision/recall/F1
per class), and a confusion matrix — the same metrics the original
model's README reports (88% accuracy on its own held-out set), so
this script is what you'd run to verify that number, or re-check it
after any retraining/fine-tuning.

Run: python training/evaluate.py --test-dir path/to/test_data
"""
import argparse
from pathlib import Path

import numpy as np
from PIL import Image
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from inference.predictor import _load_model, preprocess_image  # noqa: E402


def evaluate(test_dir: Path):
    model, classes = _load_model()

    y_true, y_pred = [], []
    for class_name in classes:
        class_dir = test_dir / class_name
        if not class_dir.exists():
            print(f"  (skipping '{class_name}' — no folder found at {class_dir})")
            continue
        image_paths = list(class_dir.glob("*.jpg")) + list(class_dir.glob("*.jpeg")) + list(class_dir.glob("*.png"))
        for path in image_paths:
            img = Image.open(path)
            tensor = preprocess_image(img)
            preds = model.predict(tensor, verbose=0)[0]
            predicted_class = classes[int(np.argmax(preds))]
            y_true.append(class_name)
            y_pred.append(predicted_class)

    if not y_true:
        print("No labeled test images found — nothing to evaluate. Check --test-dir.")
        return

    print(f"\nEvaluated on {len(y_true)} images across {len(set(y_true))} classes\n")
    print(f"Accuracy: {accuracy_score(y_true, y_pred):.4f}\n")
    print("Classification report:")
    print(classification_report(y_true, y_pred, labels=classes, zero_division=0))
    print("Confusion matrix (rows = actual, columns = predicted):")
    print(f"  {classes}")
    print(confusion_matrix(y_true, y_pred, labels=classes))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--test-dir", type=str, required=True, help="Folder with one subfolder per class")
    args = parser.parse_args()
    evaluate(Path(args.test_dir))
