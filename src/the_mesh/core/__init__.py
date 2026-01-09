"""Core validation components."""

from the_mesh.core.validator import (
    MeshValidator,
    ValidationResult,
    ValidationError,
    StructuredError,
    generate_fix_patches,
)

__all__ = [
    "MeshValidator",
    "ValidationResult",
    "ValidationError",
    "StructuredError",
    "generate_fix_patches",
]
