"""Core validation components."""

from the_mesh.core.errors import StructuredError, ValidationError, ValidationResult
from the_mesh.core.cache import ValidationCache, ValidationContext
from the_mesh.core.utils import generate_fix_patches, suggest_completions, validate_changes
from the_mesh.core.validator import MeshValidator

__all__ = [
    "MeshValidator",
    "ValidationResult",
    "ValidationError",
    "StructuredError",
    "ValidationCache",
    "ValidationContext",
    "generate_fix_patches",
    "suggest_completions",
    "validate_changes",
]
