# agents/vision_agent/cv_detector.py
import logging
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ShapeBox(BaseModel):
    id: str
    is_container: bool
    bbox: List[float]  # [x, y, w, h]
    parent: Optional[str] = None
    matched_text: Optional[str] = None


class TextCluster(BaseModel):
    text: str
    bbox: List[float]  # [x, y, w, h]
    confidence: float = 1.0


def cluster_text_items(ocr_items: List[Any], max_vertical_dist: float = 35.0, max_horizontal_dist: float = 120.0) -> List[TextCluster]:
    """Clusters vertically adjacent text boxes into unified multi-line labels."""
    if not ocr_items:
        return []

    # Sort text items top to bottom
    sorted_items = sorted(ocr_items, key=lambda item: item.bbox[1])
    clusters: List[List[Any]] = []

    for item in sorted_items:
        ix, iy, iw, ih = item.bbox
        item_center_x = ix + iw / 2.0

        merged = False
        for cluster in clusters:
            last_item = cluster[-1]
            lx, ly, lw, lh = last_item.bbox
            last_center_x = lx + lw / 2.0

            # If vertically close and horizontally aligned
            if (iy - (ly + lh)) <= max_vertical_dist and abs(item_center_x - last_center_x) <= max_horizontal_dist:
                cluster.append(item)
                merged = True
                break

        if not merged:
            clusters.append([item])

    result: List[TextCluster] = []
    for clus in clusters:
        full_text = "\n".join([i.text for i in clus])
        min_x = min(i.bbox[0] for i in clus)
        min_y = min(i.bbox[1] for i in clus)
        max_x = max(i.bbox[0] + i.bbox[2] for i in clus)
        max_y = max(i.bbox[1] + i.bbox[3] for i in clus)
        conf = sum(getattr(i, "confidence", 0.9) for i in clus) / float(len(clus))

        result.append(
            TextCluster(
                text=full_text,
                bbox=[float(min_x), float(min_y), float(max_x - min_x), float(max_y - min_y)],
                confidence=round(conf, 2),
            )
        )

    return result


def detect_visual_shapes(image_path: str) -> List[ShapeBox]:
    """Uses OpenCV contour analysis to detect rectangular shape boundaries in a diagram image."""
    shape_boxes: List[ShapeBox] = []
    try:
        import cv2
        import numpy as np

        image = cv2.imread(image_path)
        if image is None:
            logger.warning(f"OpenCV could not load image at {image_path}")
            return shape_boxes

        h_img, w_img = image.shape[:2]
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Morphological Closing to bridge dashed lines into solid container boxes
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
        closed = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, kernel)

        blur = cv2.GaussianBlur(closed, (5, 5), 0)
        edges = cv2.Canny(blur, 30, 120)

        contours, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

        raw_boxes = []
        for i, cnt in enumerate(contours):
            x, y, w, h = cv2.boundingRect(cnt)
            # Filter noise / tiny boxes and full image box
            if w < 25 or h < 25 or (w > w_img * 0.98 and h > h_img * 0.98):
                continue
            raw_boxes.append([float(x), float(y), float(w), float(h)])

        # Deduplicate overlapping bounding boxes
        unique_boxes = []
        for b in raw_boxes:
            x1, y1, w1, h1 = b
            duplicate = False
            for u in unique_boxes:
                x2, y2, w2, h2 = u
                if abs(x1 - x2) < 20 and abs(y1 - y2) < 20 and abs(w1 - w2) < 20 and abs(h1 - h2) < 20:
                    duplicate = True
                    break
            if not duplicate:
                unique_boxes.append(b)

        # Classify container vs node by area threshold (area > 2% of canvas)
        for idx, box in enumerate(unique_boxes):
            w, h = box[2], box[3]
            area = w * h
            is_container = area > (w_img * h_img * 0.02)

            box_id = f"shape_{'container' if is_container else 'node'}_{idx+1}"
            shape_boxes.append(
                ShapeBox(
                    id=box_id,
                    is_container=is_container,
                    bbox=box,
                )
            )

    except Exception as e:
        logger.error(f"OpenCV shape detection error: {e}")

    return shape_boxes


def calculate_containment(parent_bbox: List[float], child_bbox: List[float]) -> bool:
    """Returns True if child_bbox center is inside parent_bbox."""
    px, py, pw, ph = parent_bbox
    cx, cy, cw, ch = child_bbox

    child_center_x = cx + cw / 2.0
    child_center_y = cy + ch / 2.0

    return (
        px <= child_center_x <= (px + pw)
        and py <= child_center_y <= (py + ph)
        and (pw * ph) > (cw * ch)
    )
