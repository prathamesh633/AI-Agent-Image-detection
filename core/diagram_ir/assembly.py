# core/diagram_ir/assembly.py
from typing import Dict, List, Optional, Any
from core.diagram_ir.schema import DiagramIR, Canvas, Node, Group, Edge, Style
from core.icon_resolver import resolve_icon_type


def contains_bbox(
    parent_bbox: List[float],
    child_bbox: List[float],
    margin: float = 5.0,
) -> bool:
    """Checks if child_bbox [x, y, w, h] is geometrically contained inside parent_bbox [x, y, w, h]."""
    px, py, pw, ph = parent_bbox
    cx, cy, cw, ch = child_bbox

    return (
        (px - margin) <= cx
        and (py - margin) <= cy
        and (px + pw + margin) >= (cx + cw)
        and (py + ph + margin) >= (cy + ch)
    )


def normalize_coordinates(
    bbox: List[float],
    source_size: Optional[List[int]],
    target_canvas: Canvas,
) -> List[float]:
    """Scales bounding box coordinates [x, y, w, h] to target canvas dimensions."""
    x, y, w, h = bbox

    # If coordinates are normalized in [0.0, 1.0] range
    if max(x, y, w, h) <= 1.0:
        return [
            x * target_canvas.width,
            y * target_canvas.height,
            w * target_canvas.width,
            h * target_canvas.height,
        ]

    # If pixel coordinates with source_size provided
    if source_size and source_size[0] > 0 and source_size[1] > 0:
        scale_x = target_canvas.width / float(source_size[0])
        scale_y = target_canvas.height / float(source_size[1])
        return [x * scale_x, y * scale_y, w * scale_x, h * scale_y]

    # Already in canvas coordinates
    return [float(x), float(y), float(w), float(h)]



def assemble_diagram_ir(
    detection_data: Dict[str, Any],
    canvas_width: float = 1200.0,
    canvas_height: float = 900.0,
) -> DiagramIR:
    """Assembles raw vision detection dictionary into a strictly validated DiagramIR.

    Expected detection_data format:
    {
      "source_image_size": [w, h],  # optional
      "groups": [
         {"id": "g1", "label": "VNet", "type": "azure_vnet", "bbox": [x,y,w,h], "parent": None},
         ...
      ],
      "nodes": [
         {"id": "n1", "label": "App Service", "type": "app service", "bbox": [x,y,w,h], "parent": None},
         ...
      ],
      "edges": [
         {"id": "e1", "source": "n1", "target": "n2", "label": "HTTP", "style": "solid", "direction": "forward", "waypoints": [...]},
         ...
      ]
    }
    """
    canvas = Canvas(width=canvas_width, height=canvas_height)
    source_image_size = detection_data.get("source_image_size")

    # 1. Process Groups
    groups: List[Group] = []
    group_bboxes: Dict[str, List[float]] = {}

    raw_groups = detection_data.get("groups", [])
    for idx, raw_grp in enumerate(raw_groups):
        grp_id = raw_grp.get("id") or f"group_{idx+1}"
        label = raw_grp.get("label") or f"Group {idx+1}"
        raw_type = raw_grp.get("type", "generic_container")
        bbox = normalize_coordinates(raw_grp.get("bbox", [50, 50, 300, 200]), source_image_size, canvas)

        group_bboxes[grp_id] = bbox
        groups.append(
            Group(
                id=grp_id,
                type=raw_type,
                label=label,
                x=bbox[0],
                y=bbox[1],
                width=bbox[2],
                height=bbox[3],
                parent=raw_grp.get("parent"),  # Will be cross-checked by containment
            )
        )

    # 2. Determine Parent Containment for Groups (Group inside Group)
    for grp in groups:
        grp_bbox = group_bboxes[grp.id]
        best_parent = None
        smallest_area = float("inf")

        for other_grp in groups:
            if other_grp.id == grp.id:
                continue
            other_bbox = group_bboxes[other_grp.id]
            if contains_bbox(other_bbox, grp_bbox):
                area = other_bbox[2] * other_bbox[3]
                if area < smallest_area:
                    smallest_area = area
                    best_parent = other_grp.id

        if best_parent:
            grp.parent = best_parent

    # 3. Process Nodes
    nodes: List[Node] = []
    raw_nodes = detection_data.get("nodes", [])

    for idx, raw_nd in enumerate(raw_nodes):
        node_id = raw_nd.get("id") or f"node_{idx+1}"
        label = raw_nd.get("label") or f"Component {idx+1}"
        raw_type = raw_nd.get("type", "generic_box")

        resolved_type, confidence = resolve_icon_type(raw_type)
        bbox = normalize_coordinates(raw_nd.get("bbox", [100, 100, 60, 60]), source_image_size, canvas)

        # Cross-check containment to assign enclosing parent group
        best_parent = raw_nd.get("parent")
        smallest_area = float("inf")

        for grp in groups:
            grp_bbox = group_bboxes[grp.id]
            if contains_bbox(grp_bbox, bbox):
                area = grp_bbox[2] * grp_bbox[3]
                if area < smallest_area:
                    smallest_area = area
                    best_parent = grp.id

        nodes.append(
            Node(
                id=node_id,
                type=resolved_type,
                label=label,
                x=bbox[0],
                y=bbox[1],
                width=bbox[2],
                height=bbox[3],
                parent=best_parent,
                confidence=confidence,
            )
        )

    # 4. Process Edges
    edges: List[Edge] = []
    valid_ids = {n.id for n in nodes} | {g.id for g in groups}

    raw_edges = detection_data.get("edges", [])
    for idx, raw_ed in enumerate(raw_edges):
        edge_id = raw_ed.get("id") or f"edge_{idx+1}"
        source = raw_ed.get("source")
        target = raw_ed.get("target")

        # Skip invalid or orphaned edges
        if source not in valid_ids or target not in valid_ids:
            continue

        direction = raw_ed.get("direction", "forward")
        if direction not in ["forward", "backward", "bidirectional", "none"]:
            direction = "forward"

        style = raw_ed.get("style", "solid")
        if style not in ["solid", "dashed"]:
            style = "solid"

        edges.append(
            Edge(
                id=edge_id,
                source=source,
                target=target,
                label=raw_ed.get("label"),
                direction=direction,
                style=style,
                waypoints=raw_ed.get("waypoints", []),
            )
        )

    diagram_ir = DiagramIR(
        canvas=canvas,
        nodes=nodes,
        groups=groups,
        edges=edges,
        source_image_size=source_image_size,
    )

    try:
        from core.layout_engine import optimize_layout
        diagram_ir = optimize_layout(diagram_ir)
    except Exception as err:
        pass

    return diagram_ir
