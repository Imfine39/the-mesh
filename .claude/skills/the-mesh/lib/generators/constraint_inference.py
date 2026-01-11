"""Field Constraint Inference Module

Infers field constraints from:
1. Explicit constraints (min, max, etc.)
2. Preset specification
3. Automatic inference from field name patterns
4. Type-based defaults
"""

import re
from dataclasses import dataclass, field
from typing import Any


# Preset definitions
PRESETS: dict[str, dict[str, Any]] = {
    "money": {"min": 0, "precision": 2},
    "email": {"format": "email", "maxLength": 254},
    "id": {"pattern": r"^[A-Z0-9_-]+$", "minLength": 1},
    "percentage": {"min": 0, "max": 100},
    "age": {"min": 0, "max": 150},
    "count": {"min": 0},
    "signed_number": {},  # No constraints (allows negative)
    "text": {"maxLength": 65535},
    "none": {},  # Disable auto-inference
}

# Auto-inference rules: (field_name_pattern, preset_name)
INFERENCE_RULES: list[tuple[str, str]] = [
    (r".*amount.*|.*price.*|.*cost.*|.*total.*|.*fee.*|.*balance.*", "money"),
    (r".*email.*", "email"),
    (r".*_id$|^id$", "id"),
    (r".*rate.*|.*percent.*|.*ratio.*", "percentage"),
    (r".*age.*", "age"),
    (r".*count.*|.*quantity.*|.*qty.*|.*num_.*", "count"),
]

# Type-based defaults
TYPE_DEFAULTS: dict[str, dict[str, Any]] = {
    "int": {"min": -2147483648, "max": 2147483647},
    "float": {"precision": 2},
    "string": {"maxLength": 255},
    "text": {"maxLength": 65535},
}


@dataclass
class FieldConstraints:
    """Resolved constraints for a field"""
    min: int | float | None = None
    max: int | float | None = None
    min_length: int | None = None
    max_length: int | None = None
    pattern: str | None = None
    precision: int | None = None
    format: str | None = None
    preset_applied: str | None = None
    inferred_from: str | None = None  # 'preset', 'field_name', 'type', 'explicit'

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary (excluding None values)"""
        result = {}
        if self.min is not None:
            result["min"] = self.min
        if self.max is not None:
            result["max"] = self.max
        if self.min_length is not None:
            result["minLength"] = self.min_length
        if self.max_length is not None:
            result["maxLength"] = self.max_length
        if self.pattern is not None:
            result["pattern"] = self.pattern
        if self.precision is not None:
            result["precision"] = self.precision
        if self.format is not None:
            result["format"] = self.format
        return result


def infer_preset_from_field_name(field_name: str) -> str | None:
    """Infer preset from field name using pattern matching"""
    for pattern, preset_name in INFERENCE_RULES:
        if re.match(pattern, field_name, re.IGNORECASE):
            return preset_name
    return None


def infer_constraints(field_name: str, field_def: dict[str, Any]) -> FieldConstraints:
    """
    Infer field constraints with the following priority:
    1. Explicit constraints (min, max, etc.) - highest priority
    2. Preset specification
    3. Auto-inference from field name
    4. Type-based defaults - lowest priority

    Args:
        field_name: Name of the field
        field_def: Field definition from spec

    Returns:
        FieldConstraints with resolved values
    """
    constraints = FieldConstraints()
    field_type = field_def.get("type")

    # Normalize field_type for simple types
    if isinstance(field_type, str):
        base_type = field_type
    elif isinstance(field_type, dict):
        # Complex types like {"enum": [...]} or {"ref": "..."}
        base_type = None
    else:
        base_type = None

    # Step 1: Determine which preset to apply
    preset_name = field_def.get("preset")

    if preset_name:
        # Explicit preset specified
        if preset_name != "none":
            preset_constraints = PRESETS.get(preset_name, {})
            constraints.preset_applied = preset_name
            constraints.inferred_from = "preset"
        else:
            # preset: "none" disables auto-inference
            preset_constraints = {}
            constraints.inferred_from = "explicit"
    else:
        # Try auto-inference from field name
        inferred_preset = infer_preset_from_field_name(field_name)
        if inferred_preset:
            preset_constraints = PRESETS.get(inferred_preset, {})
            constraints.preset_applied = inferred_preset
            constraints.inferred_from = "field_name"
        else:
            preset_constraints = {}

    # Step 2: Apply type-based defaults (lowest priority)
    if base_type and base_type in TYPE_DEFAULTS:
        type_defaults = TYPE_DEFAULTS[base_type]
        if constraints.min is None and "min" in type_defaults:
            constraints.min = type_defaults["min"]
        if constraints.max is None and "max" in type_defaults:
            constraints.max = type_defaults["max"]
        if constraints.max_length is None and "maxLength" in type_defaults:
            constraints.max_length = type_defaults["maxLength"]
        if constraints.precision is None and "precision" in type_defaults:
            constraints.precision = type_defaults["precision"]
        if not constraints.inferred_from:
            constraints.inferred_from = "type"

    # Step 3: Apply preset constraints (medium priority)
    if preset_constraints:
        if "min" in preset_constraints:
            constraints.min = preset_constraints["min"]
        if "max" in preset_constraints:
            constraints.max = preset_constraints["max"]
        if "minLength" in preset_constraints:
            constraints.min_length = preset_constraints["minLength"]
        if "maxLength" in preset_constraints:
            constraints.max_length = preset_constraints["maxLength"]
        if "pattern" in preset_constraints:
            constraints.pattern = preset_constraints["pattern"]
        if "precision" in preset_constraints:
            constraints.precision = preset_constraints["precision"]
        if "format" in preset_constraints:
            constraints.format = preset_constraints["format"]

    # Step 4: Apply explicit constraints (highest priority)
    explicit_keys = ["min", "max", "minLength", "maxLength", "pattern", "precision", "format"]
    has_explicit = False

    if "min" in field_def:
        constraints.min = field_def["min"]
        has_explicit = True
    if "max" in field_def:
        constraints.max = field_def["max"]
        has_explicit = True
    if "minLength" in field_def:
        constraints.min_length = field_def["minLength"]
        has_explicit = True
    if "maxLength" in field_def:
        constraints.max_length = field_def["maxLength"]
        has_explicit = True
    if "pattern" in field_def:
        constraints.pattern = field_def["pattern"]
        has_explicit = True
    if "precision" in field_def:
        constraints.precision = field_def["precision"]
        has_explicit = True
    if "format" in field_def:
        constraints.format = field_def["format"]
        has_explicit = True

    if has_explicit:
        constraints.inferred_from = "explicit"

    return constraints


def get_preset_names() -> list[str]:
    """Get list of available preset names"""
    return list(PRESETS.keys())


def get_preset_definition(preset_name: str) -> dict[str, Any] | None:
    """Get preset definition by name"""
    return PRESETS.get(preset_name)


def build_constraint_cache(spec: dict[str, Any]) -> dict[str, dict[str, FieldConstraints]]:
    """
    Build constraint cache for all fields in spec.

    Args:
        spec: TRIR specification

    Returns:
        Nested dict: entity_name -> field_name -> FieldConstraints
    """
    cache: dict[str, dict[str, FieldConstraints]] = {}

    entities = spec.get("entities", {})
    for entity_name, entity_def in entities.items():
        cache[entity_name] = {}
        fields = entity_def.get("fields", {})
        for field_name, field_def in fields.items():
            cache[entity_name][field_name] = infer_constraints(field_name, field_def)

    return cache
