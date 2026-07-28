# agents/vision_agent/ocr.py
import logging
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class OCRItem(BaseModel):
    text: str
    confidence: float
    bbox: List[float]  # [x, y, width, height] in pixel coordinates


class OCRResult(BaseModel):
    image_size: List[int]  # [width, height]
    items: List[OCRItem] = Field(default_factory=list)


_reader_instance = None


def get_ocr_reader():
    """Lazy loader for EasyOCR reader instance."""
    global _reader_instance
    if _reader_instance is None:
        try:
            import easyocr
            logger.info("Initializing EasyOCR reader...")
            _reader_instance = easyocr.Reader(['en'], gpu=False)
        except Exception as e:
            logger.warning(f"EasyOCR initialization failed: {e}. OCR will use fallback.")
            _reader_instance = None
    return _reader_instance


def extract_text_regions(image_path: str) -> OCRResult:
    """Scans an image using OCR and returns detected text strings and pixel bounding boxes."""
    try:
        from PIL import Image
        with Image.open(image_path) as img:
            width, height = img.size
    except Exception as e:
        logger.error(f"Failed to read image dimensions for {image_path}: {e}")
        width, height = 1200, 900

    items: List[OCRItem] = []
    reader = get_ocr_reader()

    if reader:
        try:
            # EasyOCR returns list of (bbox, text, prob)
            results = reader.readtext(image_path)
            for top_left, top_right, bottom_right, bottom_left, text, prob in [
                (r[0][0], r[0][1], r[0][2], r[0][3], r[1], r[2]) for r in results
            ]:
                if not text or len(text.strip()) == 0 or prob < 0.2:
                    continue

                min_x = float(min(top_left[0], bottom_left[0]))
                min_y = float(min(top_left[1], top_right[1]))
                max_x = float(max(top_right[0], bottom_right[0]))
                max_y = float(max(bottom_left[1], bottom_right[1]))

                w = max(1.0, max_x - min_x)
                h = max(1.0, max_y - min_y)

                items.append(
                    OCRItem(
                        text=text.strip(),
                        confidence=float(prob),
                        bbox=[min_x, min_y, w, h],
                    )
                )
        except Exception as e:
            logger.error(f"EasyOCR extraction error: {e}")

    return OCRResult(image_size=[width, height], items=items)
