# agents/vision_agent/preprocess.py
import logging
import os
from typing import Tuple
from PIL import Image

logger = logging.getLogger(__name__)


def preprocess_diagram_image(
    image_path: str,
    target_min_dim: int = 1200,
    boost_contrast: bool = True,
    output_dir: str = "scratch",
) -> Tuple[str, Tuple[int, int]]:
    """Preprocesses diagram image for vision analysis: upscales low-res images and enhances contrast for thin line/box detection.

    Returns:
        (preprocessed_image_path, (width, height))
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image not found: {image_path}")

    try:
        with Image.open(image_path) as img:
            orig_w, orig_h = img.size
    except Exception as e:
        logger.error(f"Failed to open image {image_path}: {e}")
        return image_path, (1200, 900)

    # Check if OpenCV is available for image processing
    try:
        import cv2
        import numpy as np

        image = cv2.imread(image_path)
        if image is None:
            return image_path, (orig_w, orig_h)

        h, w = image.shape[:2]
        scale = 1.0

        # Upscale low-res images so thin text/arrows become crisp
        if min(w, h) < target_min_dim:
            scale = float(target_min_dim) / float(min(w, h))
            new_w, new_h = int(w * scale), int(h * scale)
            image = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
            logger.info(f"Upscaled diagram image from {w}x{h} to {new_w}x{new_h} (scale={scale:.2f})")
            h, w = new_h, new_w

        if boost_contrast:
            # Convert to LAB color space and apply CLAHE to L channel to enhance faint container lines
            lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            cl = clahe.apply(l)
            limg = cv2.merge((cl, a, b))
            image = cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)

        os.makedirs(output_dir, exist_ok=True)
        base_name = os.path.basename(image_path)
        processed_path = os.path.join(output_dir, f"prep_{base_name}")
        cv2.imwrite(processed_path, image)
        return processed_path, (w, h)

    except Exception as err:
        logger.warning(f"OpenCV preprocessing fallback ({err}). Using original image.")
        return image_path, (orig_w, orig_h)
