# core/layout_engine.py
import logging
from typing import List, Dict, Any, Optional, Tuple
from core.diagram_ir.schema import DiagramIR, Node, Group, Edge

logger = logging.getLogger(__name__)


def bboxes_intersect(x1: float, y1: float, w1: float, h1: float,
                      x2: float, y2: float, w2: float, h2: float, margin: float = 10.0) -> bool:
    """Returns True if bbox1 and bbox2 overlap within margin."""
    return not (
        x1 + w1 + margin <= x2
        or x2 + w2 + margin <= x1
        or y1 + h1 + margin <= y2
        or y2 + h2 + margin <= y1
    )


def snap_to_grid(val: float, grid_size: float = 10.0) -> float:
    """Snaps value to nearest grid multiple."""
    return round(val / grid_size) * grid_size


def resolve_sibling_collisions(nodes: List[Node], grid_size: float = 10.0):
    """Pushes significantly overlapping sibling nodes apart horizontally or vertically."""
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            n1 = nodes[i]
            n2 = nodes[j]
            if n1.parent == n2.parent:
                # Only resolve if there is actual physical overlap (margin = -5.0)
                if bboxes_intersect(n1.x, n1.y, n1.width, n1.height, n2.x, n2.y, n2.width, n2.height, margin=-5.0):
                    dx = (n1.x + n1.width / 2.0) - (n2.x + n2.width / 2.0)
                    dy = (n1.y + n1.height / 2.0) - (n2.y + n2.height / 2.0)

                    if abs(dy) >= abs(dx):
                        if n2.y >= n1.y:
                            n2.y = snap_to_grid(n1.y + n1.height + 15.0, grid_size)
                        else:
                            n1.y = snap_to_grid(n2.y + n2.height + 15.0, grid_size)
                    else:
                        if n2.x >= n1.x:
                            n2.x = snap_to_grid(n1.x + n1.width + 15.0, grid_size)
                        else:
                            n1.x = snap_to_grid(n2.x + n2.width + 15.0, grid_size)


def adjust_container_bounds(groups: List[Group], nodes: List[Node], grid_size: float = 10.0):
    """Adjusts container bounding box width & height to enclose all contained child nodes with padding without shifting original (x, y) positions."""
    for group in reversed(groups):
        child_nodes = [n for n in nodes if n.parent == group.id]
        child_groups = [g for g in groups if g.parent == group.id]

        all_child_rects = [(n.x, n.y, n.width, n.height) for n in child_nodes] + [(g.x, g.y, g.width, g.height) for g in child_groups]

        if all_child_rects:
            max_x = max(r[0] + r[2] for r in all_child_rects) + 30.0
            max_y = max(r[1] + r[3] for r in all_child_rects) + 30.0

            # Preserve original group.x and group.y top-left origin detected from vision
            width = max(max_x - group.x, group.width, 180.0)
            height = max(max_y - group.y, group.height, 140.0)

            group.width = snap_to_grid(width, grid_size)
            group.height = snap_to_grid(height, grid_size)


def route_obstacle_avoiding_edges(diagram_ir: DiagramIR):
    """Calculates detour waypoints for edge connectors when an intermediate node blocks the direct path."""
    node_map = {n.id: n for n in diagram_ir.nodes}

    for edge in diagram_ir.edges:
        if edge.waypoints:  # Preserve explicitly provided waypoints
            continue

        if edge.source in node_map and edge.target in node_map:
            src = node_map[edge.source]
            tgt = node_map[edge.target]

            sc_x, sc_y = src.x + src.width / 2.0, src.y + src.height / 2.0
            tc_x, tc_y = tgt.x + tgt.width / 2.0, tgt.y + tgt.height / 2.0

            # Check if any other node intersects the bounding box line segment between src and tgt
            for obstacle_id, obs in node_map.items():
                if obstacle_id == edge.source or obstacle_id == edge.target:
                    continue

                if obs.parent != src.parent:
                    continue

                # Check if obstacle lies on the direct path between src and tgt
                min_x, max_x = min(sc_x, tc_x), max(sc_x, tc_x)
                min_y, max_y = min(sc_y, tc_y), max(sc_y, tc_y)

                if (min_x <= obs.x + obs.width / 2.0 <= max_x) and (min_y <= obs.y + obs.height / 2.0 <= max_y):
                    # Route detour waypoint around obstacle top or bottom
                    detour_y = min(src.y, tgt.y, obs.y) - 30.0
                    edge.waypoints = [
                        [sc_x, detour_y],
                        [tc_x, detour_y],
                    ]
                    logger.info(f"Routed detour waypoints for edge '{edge.id}' around obstacle '{obs.id}'")
                    break


def optimize_layout(diagram_ir: DiagramIR) -> DiagramIR:
    """Main layout optimization pipeline: collision resolution, container padding, obstacle-avoiding edge routing, grid snapping."""
    logger.info("Running Layout Engine optimization pass...")

    resolve_sibling_collisions(diagram_ir.nodes)
    adjust_container_bounds(diagram_ir.groups, diagram_ir.nodes)
    route_obstacle_avoiding_edges(diagram_ir)

    for g in diagram_ir.groups:
        g.x = snap_to_grid(g.x)
        g.y = snap_to_grid(g.y)
        g.width = snap_to_grid(g.width)
        g.height = snap_to_grid(g.height)

    for n in diagram_ir.nodes:
        n.x = snap_to_grid(n.x)
        n.y = snap_to_grid(n.y)
        n.width = snap_to_grid(n.width)
        n.height = snap_to_grid(n.height)

    return diagram_ir
