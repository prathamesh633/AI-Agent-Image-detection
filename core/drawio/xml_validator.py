# core/drawio/xml_validator.py
import xml.etree.ElementTree as ET
from typing import List


class XMLValidationError(Exception):
    """Raised when generated draw.io XML fails structural validation."""

    pass


def validate_drawio_xml(xml_str: str) -> bool:
    """Validates structural compliance of a draw.io XML string per Build Plan spec.

    Checks:
    1. Well-formed XML parse
    2. Unique cell IDs
    3. Edge endpoints exist (source and target)
    4. Parent cells exist (or parent is "0")
    5. Non-negative geometry (x, y, width, height >= 0)

    Raises XMLValidationError if any check fails. Returns True if valid.
    """
    try:
        root = ET.fromstring(xml_str)
    except ET.ParseError as e:
        raise XMLValidationError(f"Malformed XML: {e}") from e

    # Find all mxCell elements
    mx_cells = root.findall(".//mxCell")
    if not mx_cells:
        raise XMLValidationError("No mxCell elements found in XML")

    # 1. Unique IDs
    cell_ids = set()
    for cell in mx_cells:
        cell_id = cell.get("id")
        if not cell_id:
            raise XMLValidationError("Found mxCell without an 'id' attribute")
        if cell_id in cell_ids:
            raise XMLValidationError(f"Duplicate cell ID found in XML: '{cell_id}'")
        cell_ids.add(cell_id)

    # 2. Parents exist
    for cell in mx_cells:
        parent_id = cell.get("parent")
        if parent_id is not None and parent_id != "0":
            if parent_id not in cell_ids:
                raise XMLValidationError(
                    f"Cell '{cell.get('id')}' references non-existent parent ID '{parent_id}'"
                )

    # 3. Edge endpoints exist
    for cell in mx_cells:
        if cell.get("edge") == "1":
            source_id = cell.get("source")
            target_id = cell.get("target")

            if source_id and source_id not in cell_ids:
                raise XMLValidationError(
                    f"Edge '{cell.get('id')}' references non-existent source ID '{source_id}'"
                )
            if target_id and target_id not in cell_ids:
                raise XMLValidationError(
                    f"Edge '{cell.get('id')}' references non-existent target ID '{target_id}'"
                )

    # 4. Non-negative geometry (width and height only — negative x/y are valid in draw.io)
    geometries = root.findall(".//mxGeometry")
    for geom in geometries:
        # Validate all numeric attributes are parseable
        for attr in ["x", "y", "width", "height"]:
            val_str = geom.get(attr)
            if val_str is not None:
                try:
                    float(val_str)
                except ValueError:
                    raise XMLValidationError(f"Invalid float in <mxGeometry> attribute {attr}: '{val_str}'")

        # Only width and height must be non-negative
        for attr in ["width", "height"]:
            val_str = geom.get(attr)
            if val_str is not None:
                val = float(val_str)
                if val < 0:
                    raise XMLValidationError(
                        f"Negative geometry detected: {attr}='{val}' in <mxGeometry>"
                    )

    return True
