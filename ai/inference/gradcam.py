"""
Grad-CAM: produces a heatmap showing which pixels the model actually
weighted most heavily to reach its prediction, overlaid on the
original image. This is what makes an AI skin-condition prediction
somewhat trustworthy to show a patient or doctor — "the model focused
on this exact patch of skin" is verifiable in a way a bare confidence
number isn't.

Targets the last convolutional layer of the MobileNetV2 backbone
("Conv_1") — the standard Grad-CAM target, since it's the last point
in the network where spatial location information still survives
(everything after it is pooled/flattened).
"""
from pathlib import Path

import numpy as np
from PIL import Image

GRADCAM_TARGET_LAYER = "Conv_1"


def generate_gradcam_overlay(model, preprocessed_tensor: np.ndarray, original_image: Image.Image, predicted_class_idx: int, alpha: float = 0.4) -> Image.Image:
    """Returns the original image with a red/yellow heatmap overlaid
    on the regions that drove the prediction toward predicted_class_idx."""
    import tensorflow as tf

    grad_model = tf.keras.models.Model(
        inputs=model.inputs,
        outputs=[model.get_layer(GRADCAM_TARGET_LAYER).output, model.output],
    )

    with tf.GradientTape() as tape:
        conv_output, predictions = grad_model(preprocessed_tensor)
        class_channel = predictions[:, predicted_class_idx]

    grads = tape.gradient(class_channel, conv_output)
    # Average the gradient over width/height -> importance weight per filter
    pooled_grads = tf.reduce_mean(grads, axis=(0, 1, 2))

    conv_output = conv_output[0]
    heatmap = conv_output @ pooled_grads[..., tf.newaxis]
    heatmap = tf.squeeze(heatmap)
    heatmap = tf.maximum(heatmap, 0) / (tf.math.reduce_max(heatmap) + 1e-8)  # ReLU + normalize to 0-1
    heatmap = heatmap.numpy()

    return _overlay_heatmap(heatmap, original_image, alpha)


def _overlay_heatmap(heatmap: np.ndarray, original_image: Image.Image, alpha: float) -> Image.Image:
    heatmap_img = Image.fromarray(np.uint8(255 * heatmap)).resize(original_image.size)
    heatmap_arr = np.array(heatmap_img)

    # Simple red-yellow colormap without a matplotlib dependency —
    # low activation -> transparent/black, high activation -> red/yellow
    colored = np.zeros((*heatmap_arr.shape, 3), dtype=np.uint8)
    colored[..., 0] = 255  # full red channel
    colored[..., 1] = heatmap_arr  # green ramps up with activation -> yellow at high activation

    base = np.array(original_image.convert("RGB"))
    blended = (base * (1 - alpha) + colored * alpha).astype(np.uint8)
    return Image.fromarray(blended)
