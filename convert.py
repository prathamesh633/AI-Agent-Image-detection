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


def main():
    args = parse_args()
    image_path = os.path.abspath(args.image_path)

    if not args.mock and not os.path.exists(image_path):
        print(f"Error: Input file '{image_path}' does not exist.", file=sys.stderr)
        sys.exit(1)

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
