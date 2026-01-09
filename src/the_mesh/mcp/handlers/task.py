"""Task management handlers for The Mesh MCP Server."""

from pathlib import Path
from typing import Any

from the_mesh.core.validator import MeshValidator
from the_mesh.mcp.storage import SpecStorage
from the_mesh.mcp.task_manager import TaskManager


def activate_task(validator: MeshValidator, storage: SpecStorage, args: dict) -> dict:
    """Activate a task for implementation"""
    function_name = args.get("function_name")
    if not function_name:
        return {"error": "function_name is required"}

    language = args.get("language", "python")
    output_dir = args.get("output_dir", ".")

    manager = TaskManager(Path(output_dir))
    return manager.activate_task(function_name, language)


def deactivate_task(validator: MeshValidator, storage: SpecStorage, args: dict) -> dict:
    """Deactivate a task without completing it"""
    function_name = args.get("function_name")
    if not function_name:
        return {"error": "function_name is required"}

    cleanup_worktree = args.get("cleanup_worktree", False)
    output_dir = args.get("output_dir", ".")

    manager = TaskManager(Path(output_dir))
    return manager.deactivate_task(function_name, cleanup_worktree=cleanup_worktree)


def complete_task(validator: MeshValidator, storage: SpecStorage, args: dict) -> dict:
    """Mark a task as completed"""
    function_name = args.get("function_name")
    if not function_name:
        return {"error": "function_name is required"}

    test_results = args.get("test_results")
    commit_message = args.get("commit_message")
    pr_title = args.get("pr_title")
    pr_body = args.get("pr_body")
    output_dir = args.get("output_dir", ".")

    manager = TaskManager(Path(output_dir))
    return manager.complete_task(
        function_name, test_results,
        commit_message=commit_message,
        pr_title=pr_title,
        pr_body=pr_body
    )


def get_task_status(validator: MeshValidator, storage: SpecStorage, args: dict) -> dict:
    """Get status of tasks"""
    function_name = args.get("function_name")
    output_dir = args.get("output_dir", ".")

    manager = TaskManager(Path(output_dir))
    return manager.get_task_status(function_name)


def check_edit_permission(validator: MeshValidator, storage: SpecStorage, args: dict) -> dict:
    """Check if a file can be edited"""
    file_path = args.get("file_path")
    if not file_path:
        return {"error": "file_path is required"}

    output_dir = args.get("output_dir", ".")

    manager = TaskManager(Path(output_dir))
    return manager.check_edit_permission(file_path)


def get_test_command(validator: MeshValidator, storage: SpecStorage, args: dict) -> dict:
    """Get the command to run tests for a task"""
    function_name = args.get("function_name")
    if not function_name:
        return {"error": "function_name is required"}

    output_dir = args.get("output_dir", ".")

    manager = TaskManager(Path(output_dir))
    return manager.get_test_command(function_name)


# Handler registry
HANDLERS = {
    "activate_task": activate_task,
    "deactivate_task": deactivate_task,
    "complete_task": complete_task,
    "get_task_status": get_task_status,
    "check_edit_permission": check_edit_permission,
    "get_test_command": get_test_command,
}
