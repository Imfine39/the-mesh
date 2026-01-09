"""Validation cache and context for The Mesh validator."""

from dataclasses import dataclass, field as dataclass_field


@dataclass
class ValidationCache:
    """Cache for validation results to avoid re-validation"""
    # Expression hash -> validation errors (for identical expressions)
    expression_results: dict = dataclass_field(default_factory=dict)
    # Reference path -> resolved entity/field (for path resolution)
    reference_cache: dict = dataclass_field(default_factory=dict)
    # Entity name -> field info (for entity lookups)
    entity_fields_cache: dict = dataclass_field(default_factory=dict)
    # Stats for debugging
    hits: int = 0
    misses: int = 0

    def clear(self):
        """Clear all caches"""
        self.expression_results.clear()
        self.reference_cache.clear()
        self.entity_fields_cache.clear()
        self.hits = 0
        self.misses = 0


@dataclass
class ValidationContext:
    """Configuration for validation behavior"""
    max_depth: int = 50  # Maximum expression nesting depth
    current_depth: int = 0
    cache: ValidationCache | None = None  # Optional cache for performance

    def with_depth(self, depth: int) -> "ValidationContext":
        """Create a new context with specified depth"""
        return ValidationContext(max_depth=self.max_depth, current_depth=depth, cache=self.cache)

    def get_or_create_cache(self) -> ValidationCache:
        """Get existing cache or create new one"""
        if self.cache is None:
            self.cache = ValidationCache()
        return self.cache


# Default validation context
DEFAULT_VALIDATION_CONTEXT = ValidationContext()
