# core/diagram_ir/schema.py
from typing import Literal, Optional, List
from pydantic import BaseModel, Field, field_validator, model_validator


class Style(BaseModel):
    fill: str = "#ffffff"
    stroke: str = "#000000"
    line_style: Literal["solid", "dashed", "dotted"] = "solid"
    font_size: int = 12
    font_color: str = "#000000"


class Node(BaseModel):
    id: str
    type: str  # e.g. "azure_app_service" — key into icon registry
    label: str
    x: float
    y: float
    width: float
    height: float
    parent: Optional[str] = None  # id of enclosing group, or None for root
    style: Style = Field(default_factory=Style)
    confidence: float = 1.0
    source_bbox: Optional[List[float]] = None  # original-image pixel bbox, for traceability

    @field_validator("width", "height")
    @classmethod
    def validate_positive(cls, v: float, info) -> float:
        if v <= 0:
            raise ValueError(f"{info.field_name} must be > 0, got {v}")
        return v


class Group(BaseModel):
    id: str
    type: str  # "azure_vnet", "subnet", "generic_container"
    label: str
    x: float
    y: float
    width: float
    height: float
    parent: Optional[str] = None
    style: Style = Field(default_factory=Style)

    @field_validator("width", "height")
    @classmethod
    def validate_positive(cls, v: float, info) -> float:
        if v <= 0:
            raise ValueError(f"{info.field_name} must be > 0, got {v}")
        return v


class Edge(BaseModel):
    id: str
    source: str
    target: str
    label: Optional[str] = None
    direction: Literal["forward", "backward", "bidirectional", "none"] = "forward"
    style: Literal["solid", "dashed"] = "solid"
    waypoints: List[List[float]] = Field(default_factory=list)
    confidence: float = 1.0


class Canvas(BaseModel):
    width: float
    height: float

    @field_validator("width", "height")
    @classmethod
    def validate_positive(cls, v: float, info) -> float:
        if v <= 0:
            raise ValueError(f"{info.field_name} must be > 0, got {v}")
        return v


class DiagramIR(BaseModel):
    canvas: Canvas
    nodes: List[Node] = Field(default_factory=list)
    groups: List[Group] = Field(default_factory=list)
    edges: List[Edge] = Field(default_factory=list)
    source_image_size: Optional[List[int]] = None  # [w, h] for coordinate normalization

    @model_validator(mode="after")
    def validate_diagram_ir(self) -> "DiagramIR":
        # 1. Unique IDs across nodes, groups, and edges combined
        all_ids = set()
        for category, items in [("group", self.groups), ("node", self.nodes), ("edge", self.edges)]:
            for item in items:
                if item.id in all_ids:
                    raise ValueError(f"Duplicate ID found: '{item.id}' in {category}")
                all_ids.add(item.id)

        element_ids = {n.id for n in self.nodes} | {g.id for g in self.groups}
        group_ids = {g.id for g in self.groups}

        # 2. Valid parent references (must reference an existing group or be None)
        parent_map = {}
        for group in self.groups:
            if group.parent is not None:
                if group.parent not in group_ids:
                    raise ValueError(f"Group '{group.id}' references non-existent parent group '{group.parent}'")
                parent_map[group.id] = group.parent

        for node in self.nodes:
            if node.parent is not None:
                if node.parent not in group_ids:
                    raise ValueError(f"Node '{node.id}' references non-existent parent group '{node.parent}'")
                parent_map[node.id] = node.parent

        # 3. No cycles in the parent hierarchy
        for child_id in parent_map:
            visited = set()
            curr = child_id
            while curr in parent_map:
                if curr in visited:
                    raise ValueError(f"Cycle detected in parent hierarchy involving ID '{curr}'")
                visited.add(curr)
                curr = parent_map[curr]

        # 4. Valid edge references (source and target must reference existing node or group ID)
        for edge in self.edges:
            if edge.source not in element_ids:
                raise ValueError(f"Edge '{edge.id}' references non-existent source ID '{edge.source}'")
            if edge.target not in element_ids:
                raise ValueError(f"Edge '{edge.id}' references non-existent target ID '{edge.target}'")

        return self
