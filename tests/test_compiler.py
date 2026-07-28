# tests/test_compiler.py
import pytest
from pydantic import ValidationError
from core.diagram_ir.schema import (
    DiagramIR,
    Canvas,
    Node,
    Group,
    Edge,
    Style,
)
from core.drawio.compiler import generate_xml
from core.drawio.xml_validator import validate_drawio_xml, XMLValidationError


def test_flat_nodes():
    """Section 16.4 Case 1: Flat nodes without groups."""
    ir = DiagramIR(
        canvas=Canvas(width=800, height=600),
        nodes=[
            Node(
                id="node_1",
                type="azure_app_service",
                label="App Service 1",
                x=100,
                y=100,
                width=60,
                height=60,
            ),
            Node(
                id="node_2",
                type="azure_postgresql",
                label="Database",
                x=300,
                y=100,
                width=60,
                height=60,
            ),
        ],
        edges=[
            Edge(id="edge_1", source="node_1", target="node_2", label="SQL Connection")
        ],
    )
    xml_output = generate_xml(ir)
    assert validate_drawio_xml(xml_output) is True
    assert "App Service 1" in xml_output
    assert "Database" in xml_output
    assert "SQL Connection" in xml_output


def test_one_nested_group():
    """Section 16.4 Case 2: One group containing child nodes."""
    ir = DiagramIR(
        canvas=Canvas(width=1000, height=800),
        groups=[
            Group(
                id="vnet_1",
                type="azure_vnet",
                label="Main VNet",
                x=50,
                y=50,
                width=400,
                height=300,
            )
        ],
        nodes=[
            Node(
                id="app_1",
                type="azure_app_service",
                label="Web App",
                x=100,
                y=100,
                width=60,
                height=60,
                parent="vnet_1",
            )
        ],
        edges=[],
    )
    xml_output = generate_xml(ir)
    assert validate_drawio_xml(xml_output) is True
    assert 'parent="vnet_1"' in xml_output
    # Relative coordinate assertion: app_1 x=100 relative to canvas, vnet_1 x=50, so rel_x = 50
    assert 'x="50.0"' in xml_output or 'x="50"' in xml_output


def test_two_level_nesting():
    """Section 16.4 Case 3: Two-level nested groups (Region -> VNet -> Subnet -> Node)."""
    ir = DiagramIR(
        canvas=Canvas(width=1200, height=1000),
        groups=[
            Group(
                id="region_1",
                type="azure_region",
                label="East US Region",
                x=20,
                y=20,
                width=600,
                height=500,
            ),
            Group(
                id="vnet_1",
                type="azure_vnet",
                label="Virtual Network",
                x=50,
                y=50,
                width=500,
                height=400,
                parent="region_1",
            ),
        ],
        nodes=[
            Node(
                id="kv_1",
                type="azure_key_vault",
                label="Key Vault",
                x=100,
                y=100,
                width=60,
                height=60,
                parent="vnet_1",
            )
        ],
    )
    xml_output = generate_xml(ir)
    assert validate_drawio_xml(xml_output) is True
    assert 'parent="region_1"' in xml_output
    assert 'parent="vnet_1"' in xml_output


def test_edges_with_waypoints():
    """Section 16.4 Case 4: Edges with routing waypoints."""
    ir = DiagramIR(
        canvas=Canvas(width=800, height=600),
        nodes=[
            Node(id="n1", type="azure_storage", label="S1", x=100, y=100, width=60, height=60),
            Node(id="n2", type="azure_storage", label="S2", x=500, y=300, width=60, height=60),
        ],
        edges=[
            Edge(
                id="e1",
                source="n1",
                target="n2",
                waypoints=[[200.0, 100.0], [200.0, 300.0]],
            )
        ],
    )
    xml_output = generate_xml(ir)
    assert validate_drawio_xml(xml_output) is True
    assert '<Array as="points">' in xml_output
    assert '<mxPoint x="200.0" y="100.0"' in xml_output or '<mxPoint x="200" y="100"' in xml_output


def test_dashed_edge_with_label():
    """Section 16.4 Case 5: Dashed edge with a descriptive label."""
    ir = DiagramIR(
        canvas=Canvas(width=800, height=600),
        nodes=[
            Node(id="n1", type="azure_front_door", label="FD", x=100, y=100, width=60, height=60),
            Node(id="n2", type="azure_apim", label="APIM", x=400, y=100, width=60, height=60),
        ],
        edges=[
            Edge(
                id="e1",
                source="n1",
                target="n2",
                label="Async HTTPS Call",
                style="dashed",
                direction="bidirectional",
            )
        ],
    )
    xml_output = generate_xml(ir)
    assert validate_drawio_xml(xml_output) is True
    assert "dashed=1" in xml_output
    assert "Async HTTPS Call" in xml_output
    assert "startArrow=classic;endArrow=classic" in xml_output


def test_real_icon_vs_generic_fallback():
    """Section 16.4 Case 6: Real registered icon vs generic fallback box."""
    ir = DiagramIR(
        canvas=Canvas(width=800, height=600),
        nodes=[
            Node(
                id="known_icon",
                type="azure_key_vault",
                label="KV",
                x=100,
                y=100,
                width=60,
                height=60,
            ),
            Node(
                id="unknown_icon",
                type="custom_unregistered_widget",
                label="Custom Component",
                x=300,
                y=100,
                width=80,
                height=60,
            ),
        ],
    )
    xml_output = generate_xml(ir)
    assert validate_drawio_xml(xml_output) is True
    assert "image=img/lib/azure2/security/Key_Vaults.svg" in xml_output
    assert "rounded=1;whiteSpace=wrap;html=1" in xml_output


# --- Failure Mode Tests (Section 12) ---


def test_failure_duplicate_ids():
    """Section 12 Failure Mode: Duplicate IDs across nodes/groups/edges."""
    # Test IR Schema Validation
    with pytest.raises(ValidationError) as exc_info:
        DiagramIR(
            canvas=Canvas(width=800, height=600),
            nodes=[
                Node(id="duplicate_id", type="azure_app_service", label="A", x=10, y=10, width=50, height=50),
                Node(id="duplicate_id", type="azure_storage", label="B", x=100, y=10, width=50, height=50),
            ],
        )
    assert "Duplicate ID found: 'duplicate_id'" in str(exc_info.value)

    # Test XML Validator directly on bad XML string
    bad_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <mxfile>
      <diagram id="d1">
        <mxGraphModel>
          <root>
            <mxCell id="0" />
            <mxCell id="1" parent="0" />
            <mxCell id="cell_1" value="A" parent="1" />
            <mxCell id="cell_1" value="B" parent="1" />
          </root>
        </mxGraphModel>
      </diagram>
    </mxfile>"""
    with pytest.raises(XMLValidationError) as exc_info:
        validate_drawio_xml(bad_xml)
    assert "Duplicate cell ID found in XML: 'cell_1'" in str(exc_info.value)


def test_failure_orphaned_edges():
    """Section 12 Failure Mode: Orphaned edge referencing non-existent node."""
    # Test IR Schema Validation
    with pytest.raises(ValidationError) as exc_info:
        DiagramIR(
            canvas=Canvas(width=800, height=600),
            nodes=[Node(id="n1", type="azure_app_service", label="A", x=10, y=10, width=50, height=50)],
            edges=[Edge(id="e1", source="n1", target="non_existent_node")],
        )
    assert "references non-existent target ID 'non_existent_node'" in str(exc_info.value)

    # Test XML Validator directly on bad XML string
    bad_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <mxfile>
      <diagram id="d1">
        <mxGraphModel>
          <root>
            <mxCell id="0" />
            <mxCell id="1" parent="0" />
            <mxCell id="n1" value="A" vertex="1" parent="1" />
            <mxCell id="e1" edge="1" parent="1" source="n1" target="n_missing" />
          </root>
        </mxGraphModel>
      </diagram>
    </mxfile>"""
    with pytest.raises(XMLValidationError) as exc_info:
        validate_drawio_xml(bad_xml)
    assert "references non-existent target ID 'n_missing'" in str(exc_info.value)


def test_failure_negative_geometry():
    """Section 12 Failure Mode: Negative geometry or dimensions."""
    # Test IR Schema Validation on negative dimensions
    with pytest.raises(ValidationError) as exc_info:
        DiagramIR(
            canvas=Canvas(width=800, height=600),
            nodes=[Node(id="n1", type="azure_app_service", label="A", x=10, y=10, width=-50, height=50)],
        )
    assert "width must be > 0" in str(exc_info.value)

    # Test XML Validator accepts negative x/y (valid in draw.io for off-canvas positioning)
    valid_neg_xy_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <mxfile>
      <diagram id="d1">
        <mxGraphModel>
          <root>
            <mxCell id="0" />
            <mxCell id="1" parent="0" />
            <mxCell id="n1" value="A" vertex="1" parent="1">
              <mxGeometry x="-10" y="-20" width="50" height="50" as="geometry" />
            </mxCell>
          </root>
        </mxGraphModel>
      </diagram>
    </mxfile>"""
    assert validate_drawio_xml(valid_neg_xy_xml) is True

    # Test XML Validator rejects negative width
    bad_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <mxfile>
      <diagram id="d1">
        <mxGraphModel>
          <root>
            <mxCell id="0" />
            <mxCell id="1" parent="0" />
            <mxCell id="n1" value="A" vertex="1" parent="1">
              <mxGeometry x="10" y="10" width="-50" height="50" as="geometry" />
            </mxCell>
          </root>
        </mxGraphModel>
      </diagram>
    </mxfile>"""
    with pytest.raises(XMLValidationError) as exc_info:
        validate_drawio_xml(bad_xml)
    assert "Negative geometry detected: width='-50.0'" in str(exc_info.value)
