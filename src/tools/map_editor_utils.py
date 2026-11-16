"""Pure helpers for map_editor.py: unique IDs and map-data validation."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping

ELEMENT_COLLECTIONS = ("collisions", "triggers", "props")


def next_unique_id(map_data: Mapping, prefix: str) -> str:
    """Return the next unused <prefix>_<integer> ID across all map elements.

    The numeric suffix starts above the highest existing suffix for this
    prefix, rather than using collection length. IDs are checked globally
    across collisions, triggers and props to avoid ambiguous editor labels.
    """
    if not prefix or not isinstance(prefix, str):
        raise ValueError("ID prefix must be a non-empty string")

    used_ids: set[str] = set()
    pattern = re.compile(rf"^{re.escape(prefix)}_(\d+)$")
    highest_suffix = 0

    for collection_name in ELEMENT_COLLECTIONS:
        collection = map_data.get(collection_name, [])
        if not isinstance(collection, list):
            continue
        for item in collection:
            if not isinstance(item, Mapping):
                continue
            element_id = item.get("id")
            if not isinstance(element_id, str) or not element_id:
                continue
            used_ids.add(element_id)
            match = pattern.fullmatch(element_id)
            if match:
                highest_suffix = max(highest_suffix, int(match.group(1)))

    candidate_number = highest_suffix + 1
    candidate = f"{prefix}_{candidate_number}"
    while candidate in used_ids:
        candidate_number += 1
        candidate = f"{prefix}_{candidate_number}"
    return candidate


def validate_map_data(map_data: Mapping) -> tuple[list[str], list[str]]:
    """Validate map data before saving; return (blocking_errors, warnings).

    Out-of-bounds rectangles are warnings, not errors: boundary collision
    boxes may intentionally extend 1-2 pixels beyond the visible canvas.
    """
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(map_data, Mapping):
        return ["Map data root must be an object."], warnings

    dimensions = map_data.get("dimensions", {})
    if not isinstance(dimensions, Mapping):
        errors.append("Map dimensions must be an object.")
        map_width = map_height = None
    else:
        try:
            map_width = float(dimensions["width"])
            map_height = float(dimensions["height"])
            if (
                not math.isfinite(map_width)
                or not math.isfinite(map_height)
                or map_width <= 0
                or map_height <= 0
            ):
                raise ValueError
        except (KeyError, TypeError, ValueError, OverflowError):
            errors.append("Map width and height must be finite positive numbers.")
            map_width = map_height = None

    seen_ids: dict[str, str] = {}

    for collection_name in ELEMENT_COLLECTIONS:
        collection = map_data.get(collection_name, [])
        if not isinstance(collection, list):
            errors.append(f"'{collection_name}' must be a list.")
            continue

        for index, item in enumerate(collection):
            label = f"{collection_name}[{index}]"
            if not isinstance(item, Mapping):
                errors.append(f"{label} must be an object.")
                continue

            element_id = item.get("id")
            if not isinstance(element_id, str) or not element_id.strip():
                errors.append(f"{label} is missing a non-empty ID.")
                element_id = label
            elif element_id in seen_ids:
                errors.append(
                    f"Duplicate ID '{element_id}' in {collection_name}; "
                    f"already used by {seen_ids[element_id]}."
                )
            else:
                seen_ids[element_id] = label

            width = item.get("w", item.get("width")) if collection_name == "collisions" else item.get("width", item.get("w"))
            height = item.get("h", item.get("height")) if collection_name == "collisions" else item.get("height", item.get("h"))
            raw_rect = (item.get("x"), item.get("y"), width, height)

            try:
                if any(isinstance(value, bool) for value in raw_rect):
                    raise ValueError
                x, y, rect_width, rect_height = (float(value) for value in raw_rect)
                if not all(math.isfinite(value) for value in (x, y, rect_width, rect_height)):
                    raise ValueError
                if rect_width <= 0 or rect_height <= 0:
                    errors.append(f"{label} ('{element_id}') must have positive width and height.")
                    continue
            except (TypeError, ValueError, OverflowError):
                errors.append(
                    f"{label} ('{element_id}') has invalid x/y/width/height values."
                )
                continue

            if map_width is not None and map_height is not None:
                if (
                    x < 0
                    or y < 0
                    or x + rect_width > map_width
                    or y + rect_height > map_height
                ):
                    warnings.append(
                        f"{label} ('{element_id}') extends outside the "
                        f"{int(map_width)}x{int(map_height)} map bounds."
                    )

            if collection_name == "triggers":
                trigger_type = item.get("trigger_type", "dialogue")
                if trigger_type == "dialogue" and not item.get("dialogue_id"):
                    errors.append(f"Dialogue trigger '{element_id}' is missing dialogue_id.")
                elif trigger_type == "transition" and not item.get("target_map_id"):
                    errors.append(f"Transition trigger '{element_id}' is missing target_map_id.")

            if collection_name == "props" and item.get("light"):
                light = item["light"]
                if not isinstance(light, Mapping):
                    errors.append(f"Light prop '{element_id}' has invalid light settings.")
                else:
                    radius = light.get("radius", 0)
                    try:
                        valid_radius = math.isfinite(float(radius)) and float(radius) > 0
                    except (TypeError, ValueError, OverflowError):
                        valid_radius = False
                    if not valid_radius:
                        errors.append(f"Light prop '{element_id}' must have a positive light radius.")

    return errors, warnings
