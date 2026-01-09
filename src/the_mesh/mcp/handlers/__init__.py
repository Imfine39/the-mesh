"""Handler registry for The Mesh MCP Server.

All tool handlers are organized by category and registered in a unified registry.
"""

from the_mesh.mcp.handlers import validation
from the_mesh.mcp.handlers import spec_crud
from the_mesh.mcp.handlers import generation
from the_mesh.mcp.handlers import task
from the_mesh.mcp.handlers import project
from the_mesh.mcp.handlers import frontend


# Unified handler registry - combines all handler modules
HANDLERS = {
    **validation.HANDLERS,
    **spec_crud.HANDLERS,
    **generation.HANDLERS,
    **task.HANDLERS,
    **project.HANDLERS,
    **frontend.HANDLERS,
}


def get_handler(name: str):
    """Get a handler function by name.

    Args:
        name: The tool name to look up

    Returns:
        The handler function, or None if not found
    """
    return HANDLERS.get(name)


def list_handlers() -> list[str]:
    """List all registered handler names."""
    return list(HANDLERS.keys())
