"""JSON Schema definitions for Mesh specifications."""

import json
from pathlib import Path

_SCHEMA_DIR = Path(__file__).parent


def get_mesh_schema() -> dict:
    """Load the main Mesh specification schema."""
    with open(_SCHEMA_DIR / "mesh.schema.json") as f:
        return json.load(f)


def get_expression_schema() -> dict:
    """Load the expression schema."""
    with open(_SCHEMA_DIR / "expression.schema.json") as f:
        return json.load(f)


__all__ = ["get_mesh_schema", "get_expression_schema"]
