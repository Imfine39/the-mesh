"""Core validation components."""

from core.errors import StructuredError, ValidationError, ValidationResult
from core.cache import ValidationCache, ValidationContext
from core.utils import generate_fix_patches, suggest_completions, validate_changes
from core.validator import MeshValidator

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
