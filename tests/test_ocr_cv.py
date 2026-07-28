# tests/test_ocr_cv.py
import pytest
import os
from agents.vision_agent.ocr import extract_text_regions, OCRResult
from agents.vision_agent.cv_detector import detect_visual_shapes, calculate_containment


def test_ocr_extraction_on_sample():
    """Test OCR text extraction module on test images."""
    image_path = "rk_v5 1.jpg"
    if not os.path.exists(image_path):
        pytest.skip("Test image not present")

    res = extract_text_regions(image_path)
    assert isinstance(res, OCRResult)
    assert res.image_size[0] > 0
    assert res.image_size[1] > 0


def test_cv_shape_detection():
    """Test OpenCV shape and box detection."""
    image_path = "demo-infrastructure.png"
    if not os.path.exists(image_path):
        pytest.skip("Test image not present")

    shapes = detect_visual_shapes(image_path)
    assert isinstance(shapes, list)


def test_containment_logic():
    """Test geometry containment calculation."""
    parent_box = [100.0, 100.0, 400.0, 300.0]
    child_box = [150.0, 150.0, 60.0, 60.0]
    outside_box = [600.0, 600.0, 50.0, 50.0]

    assert calculate_containment(parent_box, child_box) is True
    assert calculate_containment(parent_box, outside_box) is False
