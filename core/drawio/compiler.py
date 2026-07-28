# core/drawio/compiler.py
import xml.etree.ElementTree as ET
from typing import Dict, Optional, Tuple
from core.diagram_ir.schema import DiagramIR, Node, Group, Edge
from core.icon_resolver import load_registry


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
        # Append complete label positioning so node labels render cleanly centered beneath icon stencils
        if "verticalLabelPosition" not in base_style:
            base_style += "verticalLabelPosition=bottom;verticalAlign=top;align=center;labelPosition=center;"
        elif "align=" not in base_style:
            base_style += "align=center;labelPosition=center;"
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
    node_w, node_h = node.width, node.height
    target_type = node.type.lower()
    if target_type in registry:
        default_size = registry[target_type].get("default_size")
        if default_size and len(default_size) == 2:
            # Stencils should use registry standard aspect size rather than distorted text boxes
            node_w, node_h = float(default_size[0]), float(default_size[1])

    # Compute relative coordinates to parent container
    if node.parent:
        rel_x = node.x - parent_coords[0] if node.x >= parent_coords[0] else node.x
        rel_y = node.y - parent_coords[1] if node.y >= parent_coords[1] else node.y
        rel_x = max(15.0, rel_x)
        rel_y = max(35.0, rel_y)
    else:
        rel_x = node.x
        rel_y = node.y

    ET.SubElement(
        cell,
        "mxGeometry",
        x=str(rel_x),
        y=str(rel_y),
        width=str(node_w),
        height=str(node_h),
        **{"as": "geometry"},
    )
    return cell


def add_edge(
    root: ET.Element,
    edge: Edge,
    element_coords: Optional[Dict[str, Tuple[float, float, float, float]]] = None,
) -> ET.Element:
    """Adds an Edge mxCell to root with exit/entry port anchors for clean connection routing."""
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

    # Calculate optimal connection exit/entry port anchors if bounding box coordinates are available
    ports = ""
    if element_coords and edge.source in element_coords and edge.target in element_coords:
        sx, sy, sw, sh = element_coords[edge.source]
        tx, ty, tw, th = element_coords[edge.target]

        sc_x, sc_y = sx + sw / 2.0, sy + sh / 2.0
        tc_x, tc_y = tx + tw / 2.0, ty + th / 2.0

        dx = tc_x - sc_x
        dy = tc_y - sc_y

        if abs(dx) >= abs(dy):
            if dx > 0:
                ports = "exitX=1;exitY=0.5;exitDx=0;exitDy=0;entryX=0;entryY=0.5;entryDx=0;entryDy=0;"
            else:
                ports = "exitX=0;exitY=0.5;exitDx=0;exitDy=0;entryX=1;entryY=0.5;entryDx=0;entryDy=0;"
        else:
            if dy > 0:
                ports = "exitX=0.5;exitY=1;exitDx=0;exitDy=0;entryX=0.5;entryY=0;entryDx=0;entryDy=0;"
            else:
                ports = "exitX=0.5;exitY=0;exitDx=0;exitDy=0;entryX=0.5;entryY=1;entryDx=0;entryDy=0;"

    style = f"edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;{ports}{arrows}{line_style}"

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
    registry = load_registry(icon_registry_path)
    mxfile, root = create_canvas(ir.canvas.width, ir.canvas.height)

    # Compute absolute top-left coordinates for all groups to support relative child positioning
    abs_coords: Dict[str, Tuple[float, float]] = {}
    group_dict = {g.id: g for g in ir.groups}

    def get_abs_coords(group_id: str) -> Tuple[float, float]:
        if group_id in abs_coords:
            return abs_coords[group_id]
        grp = group_dict[group_id]
        abs_coords[group_id] = (grp.x, grp.y)
        return abs_coords[group_id]

    for grp in ir.groups:
        get_abs_coords(grp.id)

    # Collect absolute bounding boxes (x, y, width, height) for all nodes and groups for edge port calculations
    element_coords: Dict[str, Tuple[float, float, float, float]] = {}

    for grp in ir.groups:
        element_coords[grp.id] = (grp.x, grp.y, grp.width, grp.height)

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
        element_coords[nd.id] = (nd.x, nd.y, nd.width, nd.height)

    # Add edges
    for ed in ir.edges:
        add_edge(root, ed, element_coords=element_coords)

    # Serialize to string
    ET.indent(mxfile, space="  ")
    xml_str = ET.tostring(mxfile, encoding="utf-8", method="xml").decode("utf-8")
    return f'<?xml version="1.0" encoding="UTF-8"?>\n{xml_str}'
