# agents/vision_agent/scaffold.py
import logging
import os
from typing import List, Dict, Any, Tuple
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ScaffoldBox(BaseModel):
    box_id: str
    is_container: bool
    bbox: List[float]  # [x, y, w, h] in pixel coordinates
    ocr_text: str = ""


class ScaffoldResult(BaseModel):
    annotated_image_path: str
    image_size: List[int]  # [width, height]
    boxes: List[ScaffoldBox] = Field(default_factory=list)


def create_diagram_scaffold(
    image_path: str,
    output_dir: str = "scratch",
) -> ScaffoldResult:
    """Detects physical shape boundaries with OpenCV/OCR and overlays numbered bounding box badges on an annotated image to eliminate LLM coordinate hallucination."""

    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image not found: {image_path}")

    try:
        import cv2
        from agents.vision_agent.cv_detector import detect_visual_shapes
        from agents.vision_agent.ocr import extract_text_regions
        from agents.vision_agent.cv_detector import calculate_containment

        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"Could not load image: {image_path}")

        h_img, w_img = image.shape[:2]

        shapes = detect_visual_shapes(image_path)
        ocr_res = extract_text_regions(image_path)

        scaffold_boxes: List[ScaffoldBox] = []
        annotated = image.copy()

        for idx, shape in enumerate(shapes):
            box_id = f"Box_{idx+1}"
            bx, by, bw, bh = [int(v) for v in shape.bbox]

            # Find matching OCR text inside or nearby this shape box
            matched_texts = []
            for item in ocr_res.items:
                if calculate_containment(shape.bbox, item.bbox):
                    matched_texts.append(item.text)

            text_summary = " | ".join(matched_texts[:3])

            scaffold_boxes.append(
                ScaffoldBox(
                    box_id=box_id,
                    is_container=shape.is_container,
                    bbox=shape.bbox,
                    ocr_text=text_summary,
                )
            )

            # Draw colored bounding box and badge tag on annotated image
            color = (255, 120, 0) if shape.is_container else (0, 180, 255)  # Orange for containers, Cyan for nodes
            thickness = 3 if shape.is_container else 2
            cv2.rectangle(annotated, (bx, by), (bx + bw, by + bh), color, thickness)

            # Draw numbered badge label tag
            badge_label = f"#{idx+1}: {'CONTAINER' if shape.is_container else 'NODE'}"
            cv2.putText(
                annotated,
                badge_label,
                (bx + 4, max(18, by - 6)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                2,
                cv2.LINE_AA,
            )

        os.makedirs(output_dir, exist_ok=True)
        base_name = os.path.basename(image_path)
        annotated_path = os.path.join(output_dir, f"scaffold_{base_name}")
        cv2.imwrite(annotated_path, annotated)

        return ScaffoldResult(
            annotated_image_path=annotated_path,
            image_size=[w_img, h_img],
            boxes=scaffold_boxes,
        )

    except Exception as err:
        logger.warning(f"Scaffolding pipeline fallback ({err}). Using raw image.")
        return ScaffoldResult(
            annotated_image_path=image_path,
            image_size=[1200, 900],
            boxes=[],
        )
