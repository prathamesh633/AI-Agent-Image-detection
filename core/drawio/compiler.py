# core/drawio/compiler.py
import json
import os
import xml.etree.ElementTree as ET
from typing import Dict, Optional, Tuple
from core.diagram_ir.schema import DiagramIR, Node, Group, Edge


def load_icon_registry(registry_path: Optional[str] = None) -> Dict[str, dict]:
    """Loads icon registry JSON mapping icon keys and aliases to draw.io shapes."""
    if registry_path is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        registry_path = os.path.join(base_dir, "assets", "icons", "registry.json")

    if os.path.exists(registry_path):
        with open(registry_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def resolve_node_style(node: Node, registry: Dict[str, dict]) -> str:
    """Resolves icon stencil style from registry or falls back to a generic box."""
    target_type = node.type.lower()
    base_style = None

    # Exact registry key match
    if target_type in registry:
        base_style = registry[target_type].get("drawio_shape", "")
    else:
        # Alias search
        for key, data in registry.items():
            aliases = [a.lower() for a in data.get("aliases", [])]
            if target_type in aliases:
                base_style = data.get("drawio_shape", "")
                break

    if base_style:
        # Append label positioning so node labels render cleanly beneath icon stencils
        if "verticalLabelPosition" not in base_style:
            base_style += "verticalLabelPosition=bottom;verticalAlign=top;"
        return base_style

    # Generic fallback shape (box)
    stroke = node.style.stroke if node.style else "#000000"
    fill = node.style.fill if node.style else "#ffffff"
    line_style = ""
    if node.style and node.style.line_style == "dashed":
        line_style = "dashed=1;"
    elif node.style and node.style.line_style == "dotted":
        line_style = "dashed=1;dashPattern=1 3;"

    return f"rounded=1;whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};{line_style}"


def resolve_group_style(group: Group, registry: Dict[str, dict]) -> str:
    """Resolves container style for groups using registry or default swimlane."""
    target_type = group.type.lower()

    if target_type in registry:
        return registry[target_type].get("drawio_shape", "")

    for key, data in registry.items():
        aliases = [a.lower() for a in data.get("aliases", [])]
        if target_type in aliases:
            return data.get("drawio_shape", "")

    stroke = group.style.stroke if group.style else "#999999"
    fill = group.style.fill if group.style else "#f8f9fa"
    line_style = ""
    if group.style and group.style.line_style == "dashed":
        line_style = "dashed=1;"
    return f"swimlane;whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};startSize=28;collapsible=0;container=1;fontSize=11;fontStyle=1;{line_style}"


def create_canvas(width: float, height: float) -> Tuple[ET.Element, ET.Element]:
    """Creates the root XML tree structure for a draw.io diagram."""
    mxfile = ET.Element("mxfile", host="Electron", agent="5.0", version="21.6.8", type="device")
    diagram = ET.SubElement(mxfile, "diagram", id="diagram_1", name="Page-1")
    graph_model = ET.SubElement(
        diagram,
        "mxGraphModel",
        dx="1000",
        dy="1000",
        grid="1",
        gridSize="10",
        guides="1",
        tooltips="1",
        connect="1",
        arrows="1",
        fold="1",
        page="1",
        pageScale="1",
        pageWidth=str(int(width)),
        pageHeight=str(int(height)),
        math="0",
        shadow="0",
    )
    root = ET.SubElement(graph_model, "root")
    # Base cells required by mxGraph
    ET.SubElement(root, "mxCell", id="0")
    ET.SubElement(root, "mxCell", id="1", parent="0")
    return mxfile, root


def add_group(
    root: ET.Element,
    group: Group,
    registry: Dict[str, dict],
    parent_coords: Tuple[float, float] = (0.0, 0.0),
) -> ET.Element:
    """Adds a Group container mxCell to root."""
    parent_id = group.parent if group.parent else "1"
    style = resolve_group_style(group, registry)
    cell = ET.SubElement(
        root,
        "mxCell",
        id=group.id,
        value=group.label,
        style=style,
        vertex="1",
        parent=parent_id,
    )
    rel_x = group.x - parent_coords[0]
    rel_y = group.y - parent_coords[1]
    ET.SubElement(
        cell,
        "mxGeometry",
        x=str(rel_x),
        y=str(rel_y),
        width=str(group.width),
        height=str(group.height),
        **{"as": "geometry"},
    )
    return cell


def add_node(
    root: ET.Element,
    node: Node,
    registry: Dict[str, dict],
    parent_coords: Tuple[float, float] = (0.0, 0.0),
) -> ET.Element:
    """Adds a Node mxCell to root."""
    parent_id = node.parent if node.parent else "1"
    style = resolve_node_style(node, registry)
    cell = ET.SubElement(
        root,
        "mxCell",
        id=node.id,
        value=node.label,
        style=style,
        vertex="1",
        parent=parent_id,
    )
    rel_x = node.x - parent_coords[0]
    rel_y = node.y - parent_coords[1]
    ET.SubElement(
        cell,
        "mxGeometry",
        x=str(rel_x),
        y=str(rel_y),
        width=str(node.width),
        height=str(node.height),
        **{"as": "geometry"},
    )
    return cell


def add_edge(root: ET.Element, edge: Edge) -> ET.Element:
    """Adds an Edge mxCell to root."""
    # Arrow direction styling
    if edge.direction == "forward":
        arrows = "startArrow=none;endArrow=classic;"
    elif edge.direction == "backward":
        arrows = "startArrow=classic;endArrow=none;"
    elif edge.direction == "bidirectional":
        arrows = "startArrow=classic;endArrow=classic;"
    else:  # none
        arrows = "startArrow=none;endArrow=none;"

    line_style = "dashed=1;" if edge.style == "dashed" else "dashed=0;"
    style = f"edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;{arrows}{line_style}"

    cell = ET.SubElement(
        root,
        "mxCell",
        id=edge.id,
        value=edge.label or "",
        style=style,
        edge="1",
        parent="1",
        source=edge.source,
        target=edge.target,
    )
    geometry = ET.SubElement(cell, "mxGeometry", relative="1", **{"as": "geometry"})

    if edge.waypoints:
        pts = ET.SubElement(geometry, "Array", **{"as": "points"})
        for wp in edge.waypoints:
            if len(wp) >= 2:
                ET.SubElement(pts, "mxPoint", x=str(wp[0]), y=str(wp[1]))
    return cell


def generate_xml(ir: DiagramIR, icon_registry_path: Optional[str] = None) -> str:
    """Generates complete draw.io XML representation from DiagramIR."""
    registry = load_icon_registry(icon_registry_path)
    mxfile, root = create_canvas(ir.canvas.width, ir.canvas.height)

    # Compute absolute top-left coordinates for all groups to support relative child positioning
    abs_coords: Dict[str, Tuple[float, float]] = {}
    group_dict = {g.id: g for g in ir.groups}

    def get_abs_coords(group_id: str) -> Tuple[float, float]:
        if group_id in abs_coords:
            return abs_coords[group_id]
        grp = group_dict[group_id]
        if grp.parent and grp.parent in group_dict:
            parent_x, parent_y = get_abs_coords(grp.parent)
            abs_coords[group_id] = (grp.x + parent_x, grp.y + parent_y)
        else:
            abs_coords[group_id] = (grp.x, grp.y)
        return abs_coords[group_id]

    for grp in ir.groups:
        get_abs_coords(grp.id)

    # Add groups
    for grp in ir.groups:
        parent_coord = (0.0, 0.0)
        if grp.parent and grp.parent in abs_coords:
            parent_coord = abs_coords[grp.parent]
        add_group(root, grp, registry, parent_coords=parent_coord)

    # Add nodes
    for nd in ir.nodes:
        parent_coord = (0.0, 0.0)
        if nd.parent and nd.parent in abs_coords:
            parent_coord = abs_coords[nd.parent]
        add_node(root, nd, registry, parent_coords=parent_coord)

    # Add edges
    for ed in ir.edges:
        add_edge(root, ed)

    # Serialize to string
    ET.indent(mxfile, space="  ")
    xml_str = ET.tostring(mxfile, encoding="utf-8", method="xml").decode("utf-8")
    return f'<?xml version="1.0" encoding="UTF-8"?>\n{xml_str}'
