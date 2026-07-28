# tests/test_vision_pipeline.py
import os
import pytest
from core.icon_resolver import resolve_icon_type
from core.diagram_ir.assembly import assemble_diagram_ir, contains_bbox
from core.drawio.compiler import generate_xml
from core.drawio.xml_validator import validate_drawio_xml
from agents.vision_agent.detector import detect_diagram


def test_icon_resolver_fuzzy_matching():
    """Test fuzzy matching icon queries against Azure registry aliases."""
    key, score = resolve_icon_type("App Service")
    assert key == "azure_app_service"
    assert score >= 0.80

    key, score = resolve_icon_type("postgresql database")
    assert key == "azure_postgresql"
    assert score >= 0.80

    key, score = resolve_icon_type("azure front door")
    assert key == "azure_front_door"
    assert score >= 0.80

    key, score = resolve_icon_type("completely_unknown_shape_xyz")
    assert key == "generic_box"


def test_bbox_containment_logic():
    """Test bounding box geometric containment calculation."""
    parent_bbox = [100.0, 100.0, 400.0, 300.0]
    child_inside = [150.0, 150.0, 80.0, 60.0]
    child_outside = [600.0, 600.0, 80.0, 60.0]

    assert contains_bbox(parent_bbox, child_inside) is True
    assert contains_bbox(parent_bbox, child_outside) is False


def test_assembly_and_nesting():
    """Test IR assembly with automatic nesting resolution."""
    raw_data = {
        "groups": [
            {
                "id": "vnet_1",
                "type": "azure_vnet",
                "label": "VNet",
                "bbox": [50.0, 50.0, 500.0, 400.0],
            }
        ],
        "nodes": [
            {
                "id": "app_1",
                "type": "web app",
                "label": "App",
                "bbox": [100.0, 100.0, 80.0, 60.0],
            }
        ],
        "edges": [
            {
                "id": "edge_1",
                "source": "app_1",
                "target": "vnet_1",
                "label": "Connected",
            }
        ],
    }

    ir = assemble_diagram_ir(raw_data, canvas_width=1000.0, canvas_height=800.0)

    assert len(ir.groups) == 1
    assert len(ir.nodes) == 1
    assert len(ir.edges) == 1
    assert ir.nodes[0].parent == "vnet_1"
    assert ir.nodes[0].type == "azure_app_service"


def test_end_to_end_mock_pipeline(tmp_path):
    """Test full Vision -> Assembly -> Compiler -> Validator pipeline."""
    mock_detection = detect_diagram("dummy_image.png", use_mock=True)
    ir = assemble_diagram_ir(mock_detection)

    xml_str = generate_xml(ir)
    assert validate_drawio_xml(xml_str) is True

    output_file = tmp_path / "output.drawio"
    output_file.write_text(xml_str, encoding="utf-8")
    assert output_file.exists()
