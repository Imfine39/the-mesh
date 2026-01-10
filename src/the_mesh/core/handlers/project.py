"""Project configuration handlers for The Mesh."""

from pathlib import Path
from typing import Any

from the_mesh.core.validator import MeshValidator
from the_mesh.config.project import ProjectConfig
from the_mesh.core.storage import SpecStorage


def init_project(validator: MeshValidator, storage: SpecStorage, args: dict) -> dict:
    """Initialize project configuration"""
    output_dir = args.get("output_dir", ".")
    language = args.get("language", "python")
    src_path = args.get("src_path")
    test_framework = args.get("test_framework")

    git_config = {}
    if "base_branch" in args:
        git_config["base_branch"] = args["base_branch"]
    if "auto_worktree" in args:
        git_config["auto_worktree"] = args["auto_worktree"]
    if "auto_pr" in args:
        git_config["auto_pr"] = args["auto_pr"]

    config_manager = ProjectConfig(Path(output_dir))

    # Check if already initialized
    if config_manager.exists():
        existing = config_manager.load()
        return {
            "success": False,
            "error": "Project already initialized",
            "existing_config": existing,
            "hint": "Use get_project_config to view current config"
        }

    config = config_manager.init(
        language=language,
        src_path=src_path,
        test_framework=test_framework,
        git_config=git_config if git_config else None
    )

    return {
        "success": True,
        "config": config,
        "config_file": str(config_manager.config_file)
    }


def get_project_config(validator: MeshValidator, storage: SpecStorage, args: dict) -> dict:
    """Get current project configuration"""
    output_dir = args.get("output_dir", ".")

    config_manager = ProjectConfig(Path(output_dir))

    if not config_manager.exists():
        return {
            "initialized": False,
            "config": config_manager.load(),  # Returns defaults
            "hint": "Run init_project to create config file"
        }

    return {
        "initialized": True,
        "config": config_manager.load(),
        "config_file": str(config_manager.config_file)
    }


# Handler registry
HANDLERS = {
    "init_project": init_project,
    "get_project_config": get_project_config,
}
