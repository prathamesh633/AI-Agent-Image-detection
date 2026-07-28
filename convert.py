#!/usr/bin/env python3
"""convert.py - Diagram Image to Editable .drawio CLI Tool."""

import argparse
import sys
import os
from agents.vision_agent.detector import detect_diagram
from core.diagram_ir.assembly import assemble_diagram_ir
from core.drawio.compiler import generate_xml
from core.drawio.xml_validator import validate_drawio_xml, XMLValidationError


def parse_args():
    parser = argparse.ArgumentParser(
        description="Convert static architecture diagram images (PNG/JPG) to editable .drawio files."
    )
    parser.add_argument("image_path", help="Path to input diagram image (PNG/JPG/PDF)")
    parser.add_argument(
        "-o",
        "--output",
        help="Path for generated .drawio file (default: same name with .drawio extension)",
    )
    parser.add_argument("--api-key", help="API key for Vision LLM provider (optional)")
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Force offline mock vision detection for testing",
    )
    parser.add_argument(
        "--width",
        type=float,
        default=1200.0,
        help="Canvas width (default: 1200)",
    )
    parser.add_argument(
        "--height",
        type=float,
        default=900.0,
        help="Canvas height (default: 900)",
    )
    return parser.parse_args()


MAX_IMAGE_SIZE_MB = 20.0
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".pdf"}


def validate_input_image(image_path: str):
    """Validates input file existence, extension, and size."""
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Input file '{image_path}' does not exist.")

    ext = os.path.splitext(image_path)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file format '{ext}'. Supported formats: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    file_size_mb = os.path.getsize(image_path) / (1024 * 1024)
    if file_size_mb > MAX_IMAGE_SIZE_MB:
        raise ValueError(
            f"Input file size ({file_size_mb:.1f} MB) exceeds maximum limit of {MAX_IMAGE_SIZE_MB} MB."
        )


def main():
    args = parse_args()
    image_path = os.path.abspath(args.image_path)

    if not args.mock:
        try:
            validate_input_image(image_path)
        except (FileNotFoundError, ValueError) as err:
            print(f"Error: {err}", file=sys.stderr)
            sys.exit(1)

    if args.api_key:
        print("[WARNING] Passing API keys via CLI args can expose secrets in process tables. Use GEMINI_API_KEY or OPENAI_API_KEY env variables instead.", file=sys.stderr)

    output_path = args.output
    if not output_path:
        base, _ = os.path.splitext(image_path)
        output_path = f"{base}.drawio"

    print("=" * 60)
    print(" Diagram-to-draw.io Reconstruction Agent CLI ")
    print("=" * 60)
    print(f" Input Image  : {image_path}")
    print(f" Output Target: {output_path}")

    # 1. Vision Detection
    print("\n[1/4] Running vision detection pipeline...")
    detection_data = detect_diagram(image_path, api_key=args.api_key, use_mock=args.mock)
    num_nodes = len(detection_data.get("nodes", []))
    num_groups = len(detection_data.get("groups", []))
    num_edges = len(detection_data.get("edges", []))
    print(f"      Detected: {num_nodes} components, {num_groups} containers, {num_edges} connections")

    # 2. IR Assembly
    print("[2/4] Assembling Intermediate Representation (IR)...")
    ir = assemble_diagram_ir(
        detection_data,
        canvas_width=args.width,
        canvas_height=args.height,
    )
    print(f"      Assembled DiagramIR (Canvas: {ir.canvas.width}x{ir.canvas.height})")

    # 3. XML Compilation
    print("[3/4] Compiling draw.io XML...")
    xml_output = generate_xml(ir)

    # 4. XML Structural Validation Gate
    print("[4/4] Validating XML structure...")
    try:
        validate_drawio_xml(xml_output)
        print("      Validation: PASSED (100% compliant mxGraphModel XML)")
    except XMLValidationError as e:
        print(f"      Validation FAILED: {e}", file=sys.stderr)
        sys.exit(2)

    # Save Output
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(xml_output)

    print("\n" + "=" * 60)
    print(f" SUCCESS: Editable .drawio saved to:\n {os.path.abspath(output_path)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
