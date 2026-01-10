"""The Mesh - Specification validation framework for AI-driven development."""

__version__ = "0.2.0"

from core.validator import MeshValidator
from core.errors import ValidationResult, StructuredError
from graph.graph import DependencyGraph
from config.project import ProjectConfig

__all__ = [
    "MeshValidator",
    "ValidationResult",
    "StructuredError",
    "DependencyGraph",
    "ProjectConfig",
]
