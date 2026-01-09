"""The Mesh - Specification validation framework for AI-driven development."""

__version__ = "0.2.0"

from the_mesh.core.validator import MeshValidator, ValidationResult, StructuredError
from the_mesh.graph.graph import DependencyGraph
from the_mesh.config.project import ProjectConfig

__all__ = [
    "MeshValidator",
    "ValidationResult",
    "StructuredError",
    "DependencyGraph",
    "ProjectConfig",
]
