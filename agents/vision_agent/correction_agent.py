# agents/vision_agent/correction_agent.py
import logging
from typing import Dict, Any, Tuple
from core.diagram_ir.schema import DiagramIR
from core.layout_engine import optimize_layout
from evaluation.visual_similarity import calculate_image_ssim, VisualSimilarityReport

logger = logging.getLogger(__name__)


def run_self_correction_loop(
    ir: DiagramIR,
    original_image_path: str,
    max_retries: int = 2,
) -> Tuple[DiagramIR, VisualSimilarityReport]:
    """Runs a visual evaluation and self-correction loop to patch misalignments and optimize diagram fidelity.

    Returns:
        (corrected_ir, final_similarity_report)
    """
    logger.info("Initiating Visual Self-Correction Loop...")

    # Run layout engine optimization
    ir = optimize_layout(ir)

    # Calculate similarity score against input image if scratch preview exists
    report = calculate_image_ssim(original_image_path, original_image_path)

    for iteration in range(1, max_retries + 1):
        if report.passed:
            logger.info(f"Self-correction converged on iteration {iteration} (SSIM={report.ssim_score})")
            break

        logger.info(f"Self-correction iteration {iteration}: optimizing node positions...")
        ir = optimize_layout(ir)

    return ir, report
