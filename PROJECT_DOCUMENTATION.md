# Project Documentation: Diagram-to-Editable Draw.io Reconstruction Agent

## Executive Overview
The **Diagram-to-Editable Draw.io Reconstruction Agent** is an end-to-end Python engine that converts static architecture diagram images (PNG, JPG) into 100% native, fully editable `.drawio` files. 

It solves common rendering distortions—such as broken image icon placeholders, cramped label overlaps, missing container hierarchies, and un-editable graphics—by combining strict Intermediate Representation (IR) schemas, native Draw.io stencil registries, automated OCR + OpenCV shape detection, and hard XML validation gates.

---

## 📁 Repository File Structure

```text
new_AI_Agent/
├── convert.py                         # Master CLI entry point for diagram conversion
├── pytest.ini                         # Pytest configuration
├── README.md                          # Quickstart guide
├── PROJECT_DOCUMENTATION.md           # Comprehensive technical architecture & walkthrough
│
├── core/                              # Core Compiler & Intermediate Representation Engine
│   ├── diagram_ir/
│   │   ├── __init__.py
│   │   ├── schema.py                  # Pydantic models for DiagramIR, Canvas, Node, Group, Edge
│   │   └── assembly.py                # Bounding box containment & relative coordinate math
│   ├── drawio/
│   │   ├── __init__.py
│   │   ├── compiler.py                # XML Compiler converting IR tree to mxGraphModel XML
│   │   └── xml_validator.py           # Hard validation gates (well-formed, unique IDs, geometry)
│   ├── icon_resolver.py               # Fuzzy string matcher linking labels to stencil registry
│   └── layout_engine.py               # Collision resolution, container bounds, grid snapping
│
├── agents/                            # Vision & Extraction Sub-Agents
│   └── vision_agent/
│       ├── __init__.py
│       ├── ocr.py                     # EasyOCR text detection & bounding box extraction
│       ├── cv_detector.py             # OpenCV contour shape analysis & box detection
│       └── detector.py                # Master detection orchestrator
│
├── assets/
│   └── icons/
│       └── registry.json              # Master registry mapping AWS & Azure stencils to Draw.io URIs
│
└── tests/                             # Test Suite (16/16 Passed)
    ├── test_compiler.py               # Unit tests for XML compiler & failure modes
    ├── test_ocr_cv.py                 # Unit tests for EasyOCR & OpenCV shape detection
    └── test_vision_pipeline.py        # Unit tests for containment math & fuzzy icon resolver
```

---

## 🛠️ Key Technologies & Frameworks Used

1. **Python 3.10**: Core runtime.
2. **Pydantic v2**: Type-safe validation for intermediate diagram representations (`DiagramIR`).
3. **EasyOCR & PyTorch**: Lightweight, zero-cost, local optical character recognition (OCR) for extracting text labels and pixel bounding boxes.
4. **OpenCV (`cv2`)**: Computer vision contour detection (`cv2.findContours`, `cv2.boundingRect`) for identifying visual boxes and container boundaries.
5. **Python `xml.etree.ElementTree` & `xml.dom.minidom`**: Precise construction and pretty-printing of Draw.io's `mxGraphModel` XML schema.
6. **Pytest**: Automated unit testing suite ensuring schema compliance, duplicate ID prevention, and orphaned edge rejection.

---

## 🚀 How Diagram Conversion Works (Step-by-Step Pipeline)

```text
[ Input Image (.png/.jpg) ]
           │
           ▼
 [ Step 1: Vision Agent (OCR + OpenCV) ]
  - EasyOCR extracts text labels & pixel coordinates [x, y, w, h].
  - OpenCV extracts visual shape contours & container bounds.
           │
           ▼
 [ Step 2: Intermediate Representation (IR) Assembly ]
  - Calculates parent-child containment (is node inside Subnet? inside VNet?).
  - Converts absolute canvas coordinates to parent-relative coordinates.
  - Matches label strings against registry.json using fuzzy matching.
           │
           ▼
 [ Step 3: Draw.io XML Compiler ]
  - Generates mxCell elements with exact Draw.io stencil style strings.
  - Generates mxGeometry bounds and edge connector waypoints.
           │
           ▼
 [ Step 4: XML Hard Validation Gate ]
  - Validates XML well-formedness.
  - Verifies ID uniqueness, edge endpoint existence, and positive geometry.
           │
           ▼
[ Editable .drawio Output ]
```

---

## 💡 How We Increased Accuracy & Visual Quality

### 1. Native Draw.io Stencil Integration (Fixed Broken Image Placeholders)
- **Problem**: Custom Base64 image URIs or external URL fetches caused "broken image" placeholders in Draw.io.
- **Solution**: Standardized `assets/icons/registry.json` to use official native Draw.io built-in library URIs:
  - **Azure**: `image=img/lib/azure2/security/Key_Vaults.svg`, `image=img/lib/azure2/containers/Container_Registries.svg`, etc.
  - **AWS**: `shape=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4.alb`, `resIcon=mxgraph.aws4.ec2`, etc.

### 2. Clean Swimlane Container System (Fixed Giant Chevron Overlays)
- **Problem**: Default Azure subnet shapes drew massive decorative chevrons covering contained child nodes.
- **Solution**: Replaced group shapes with transparent swimlanes (`swimlane;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor=#0078D4;startSize=28;container=1;`).

### 3. Dynamic Horizontal & Vertical Spacing (Fixed Overlapping Text Labels)
- **Problem**: Cramped 50px spacing caused long component labels (e.g. `Document Intelligence Endpoint`) to collide.
- **Solution**: Expanded container bounding box widths (e.g. 860px) and enforced standard 100px center-to-center spacing between adjacent nodes.

### 4. Relative Coordinate Normalization
- **Problem**: Draw.io requires child nodes inside a group to use coordinates relative to the parent box, while vision models output absolute canvas coordinates.
- **Solution**: Implemented coordinate conversion in `core/diagram_ir/assembly.py` (`rel_x = child_x - parent_x`).

---

## 📊 Verification & Test Suite

Run all automated unit tests to verify system health:
```bash
pytest -v
```

### Passing Tests (16/16):
- `test_flat_nodes`: Standard flat diagram export.
- `test_one_nested_group`: Single-level parent-child container nesting.
- `test_two_level_nesting`: Two-level container hierarchy (VNet -> Subnet -> Node).
- `test_edges_with_waypoints`: Connector routing waypoints.
- `test_dashed_edge_with_label`: Dashed relationship connectors with labels.
- `test_real_icon_vs_generic_fallback`: Stencil lookup and fallback verification.
- `test_failure_duplicate_ids`: Rejection gate for non-unique cell IDs.
- `test_failure_orphaned_edges`: Rejection gate for broken edge connections.
- `test_failure_negative_geometry`: Rejection gate for negative coordinate geometry.
- `test_ocr_extraction_on_sample`: EasyOCR text extraction.
- `test_cv_shape_detection`: OpenCV contour analysis.
- `test_containment_logic`: Geometry containment math.
- `test_icon_resolver_fuzzy_matching`: Fuzzy icon alias resolution.
- `test_bbox_containment_logic`: Bounding box nesting logic.
- `test_assembly_and_nesting`: IR tree construction.
- `test_end_to_end_mock_pipeline`: Complete pipeline execution test.

---

## 🎮 How to Run CLI Conversions

To convert any architecture image into an editable `.drawio` file:

```bash
# Convert Azure diagram
python3 convert.py "rk_v5 1.jpg" -o rk_v5_editable.drawio

# Convert AWS diagram
python3 convert.py demo-infrastructure.png -o demo-infrastructure.drawio
```

Open the resulting `.drawio` file in [https://app.diagrams.net](https://app.diagrams.net) or Draw.io Desktop to edit, move, or modify any component.
