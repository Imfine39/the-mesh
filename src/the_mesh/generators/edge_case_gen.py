"""Edge Case Generator Module

Generates edge case test values from field constraints.
"""

from dataclasses import dataclass
from typing import Any

from the_mesh.generators.constraint_inference import FieldConstraints


@dataclass
class EdgeCase:
    """Represents a single edge case for testing"""
    label: str
    value: Any
    should_be_valid: bool
    description: str
    category: str  # "boundary", "format", "null", "enum"


# Sample values for format validation
FORMAT_VALID_SAMPLES: dict[str, str] = {
    "email": "test@example.com",
    "url": "https://example.com",
    "uuid": "550e8400-e29b-41d4-a716-446655440000",
    "phone": "+1-555-123-4567",
    "date": "2024-01-15",
    "datetime": "2024-01-15T10:30:00Z",
}

FORMAT_INVALID_SAMPLES: dict[str, str] = {
    "email": "not-an-email",
    "url": "not-a-url",
    "uuid": "not-a-uuid",
    "phone": "12345",
    "date": "not-a-date",
    "datetime": "not-a-datetime",
}


def generate_edge_cases(
    constraints: FieldConstraints,
    required: bool,
    field_type: str | None = None,
    enum_values: list[str] | None = None
) -> list[EdgeCase]:
    """
    Generate edge cases from field constraints.

    Args:
        constraints: Resolved field constraints
        required: Whether the field is required
        field_type: Base field type (int, float, string, etc.)
        enum_values: List of valid enum values (if enum type)

    Returns:
        List of EdgeCase instances
    """
    cases: list[EdgeCase] = []

    # Numeric boundary tests
    if constraints.min is not None:
        min_val = constraints.min
        cases.append(EdgeCase(
            label="at_min",
            value=min_val,
            should_be_valid=True,
            description=f"At minimum ({min_val})",
            category="boundary"
        ))
        # For integers, below_min is min - 1
        # For floats, we use a small delta
        if field_type == "int" or isinstance(min_val, int):
            below_val = int(min_val) - 1
        else:
            below_val = min_val - 0.01
        cases.append(EdgeCase(
            label="below_min",
            value=below_val,
            should_be_valid=False,
            description=f"Below minimum ({below_val})",
            category="boundary"
        ))

    if constraints.max is not None:
        max_val = constraints.max
        cases.append(EdgeCase(
            label="at_max",
            value=max_val,
            should_be_valid=True,
            description=f"At maximum ({max_val})",
            category="boundary"
        ))
        if field_type == "int" or isinstance(max_val, int):
            above_val = int(max_val) + 1
        else:
            above_val = max_val + 0.01
        cases.append(EdgeCase(
            label="above_max",
            value=above_val,
            should_be_valid=False,
            description=f"Above maximum ({above_val})",
            category="boundary"
        ))

    # String length tests
    if constraints.min_length is not None:
        length = constraints.min_length
        cases.append(EdgeCase(
            label="at_min_length",
            value="a" * length,
            should_be_valid=True,
            description=f"At min length ({length})",
            category="boundary"
        ))
        if length > 0:
            cases.append(EdgeCase(
                label="below_min_length",
                value="a" * (length - 1),
                should_be_valid=False,
                description=f"Below min length ({length - 1})",
                category="boundary"
            ))

    if constraints.max_length is not None:
        length = constraints.max_length
        # Only generate if not too long
        if length <= 1000:
            cases.append(EdgeCase(
                label="at_max_length",
                value="a" * length,
                should_be_valid=True,
                description=f"At max length ({length})",
                category="boundary"
            ))
            cases.append(EdgeCase(
                label="above_max_length",
                value="a" * (length + 1),
                should_be_valid=False,
                description=f"Above max length ({length + 1})",
                category="boundary"
            ))
        else:
            # For very long maxLength, just note it
            cases.append(EdgeCase(
                label="at_max_length",
                value=f"<string of length {length}>",
                should_be_valid=True,
                description=f"At max length ({length})",
                category="boundary"
            ))

    # Pattern tests
    if constraints.pattern is not None:
        pattern = constraints.pattern
        # Generate a value that matches common patterns
        valid_value = _generate_valid_for_pattern(pattern)
        invalid_value = _generate_invalid_for_pattern(pattern)

        cases.append(EdgeCase(
            label="valid_pattern",
            value=valid_value,
            should_be_valid=True,
            description=f"Matches pattern {pattern}",
            category="format"
        ))
        cases.append(EdgeCase(
            label="invalid_pattern",
            value=invalid_value,
            should_be_valid=False,
            description=f"Violates pattern {pattern}",
            category="format"
        ))

    # Format tests
    if constraints.format is not None:
        fmt = constraints.format
        valid_sample = FORMAT_VALID_SAMPLES.get(fmt, "valid")
        invalid_sample = FORMAT_INVALID_SAMPLES.get(fmt, "invalid")

        cases.append(EdgeCase(
            label="valid_format",
            value=valid_sample,
            should_be_valid=True,
            description=f"Valid {fmt} format",
            category="format"
        ))
        cases.append(EdgeCase(
            label="invalid_format",
            value=invalid_sample,
            should_be_valid=False,
            description=f"Invalid {fmt} format",
            category="format"
        ))

    # Enum tests
    if enum_values:
        for val in enum_values:
            cases.append(EdgeCase(
                label=f"enum_{val.lower().replace('-', '_')}",
                value=val,
                should_be_valid=True,
                description=f"Valid enum value: {val}",
                category="enum"
            ))
        cases.append(EdgeCase(
            label="invalid_enum",
            value="__INVALID_ENUM_VALUE__",
            should_be_valid=False,
            description="Invalid enum value",
            category="enum"
        ))

    # Null/required tests
    if required:
        cases.append(EdgeCase(
            label="null_required",
            value=None,
            should_be_valid=False,
            description="Null for required field",
            category="null"
        ))
    else:
        cases.append(EdgeCase(
            label="null_optional",
            value=None,
            should_be_valid=True,
            description="Null for optional field",
            category="null"
        ))

    # Empty string test for strings
    if field_type == "string":
        if constraints.min_length is not None and constraints.min_length > 0:
            cases.append(EdgeCase(
                label="empty_string",
                value="",
                should_be_valid=False,
                description="Empty string (minLength > 0)",
                category="boundary"
            ))
        elif required:
            # Required string with no minLength - empty might be invalid depending on implementation
            cases.append(EdgeCase(
                label="empty_string",
                value="",
                should_be_valid=False,
                description="Empty string for required field",
                category="boundary"
            ))

    return cases


def _generate_valid_for_pattern(pattern: str) -> str:
    """Generate a value that matches the pattern (best effort)"""
    # Common pattern mappings
    pattern_samples = {
        r"^[A-Z0-9_-]+$": "ABC-123",
        r"^[a-z]+$": "abc",
        r"^[A-Z]+$": "ABC",
        r"^[0-9]+$": "12345",
        r"^\d+$": "12345",
        r"^[a-zA-Z0-9]+$": "Abc123",
    }

    for p, sample in pattern_samples.items():
        if pattern == p:
            return sample

    # Default: return a simple alphanumeric string
    return "VALID-001"


def _generate_invalid_for_pattern(pattern: str) -> str:
    """Generate a value that violates the pattern"""
    # Return something that's unlikely to match most patterns
    return "!@#$%^&*()"


def generate_edge_cases_for_field(
    field_name: str,
    field_def: dict[str, Any],
    constraints: FieldConstraints
) -> list[EdgeCase]:
    """
    Generate edge cases for a specific field.

    Args:
        field_name: Name of the field
        field_def: Field definition from spec
        constraints: Resolved constraints for the field

    Returns:
        List of EdgeCase instances
    """
    required = field_def.get("required", True)
    field_type = field_def.get("type")

    # Handle enum types
    enum_values = None
    if isinstance(field_type, dict) and "enum" in field_type:
        enum_values = field_type["enum"]
        base_type = "string"
    elif isinstance(field_type, str):
        base_type = field_type
    else:
        base_type = None

    return generate_edge_cases(
        constraints=constraints,
        required=required,
        field_type=base_type,
        enum_values=enum_values
    )
