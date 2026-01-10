#!/usr/bin/env python3
"""
Git Worktree Management for The Mesh

Provides functions for creating and managing git worktrees for task isolation.
"""

import json
import os
import subprocess
import secrets
from pathlib import Path

# Add parent directory to path
import sys

from config.project import ProjectConfig


def generate_short_id(length: int = 6) -> str:
    """Generate a short random ID"""
    return secrets.token_hex(length // 2)


def get_worktree_base_dir(project_dir: Path) -> Path:
    """Get the base directory for worktrees"""
    return project_dir.parent / f"{project_dir.name}-worktrees"


def get_branch_name(function_name: str, prefix: str = "task") -> str:
    """Generate a unique branch name for a task"""
    short_id = generate_short_id()
    return f"{prefix}/{function_name}_{short_id}"


def create_worktree(project_dir: Path, branch_name: str) -> dict:
    """Create a git worktree for a task

    Args:
        project_dir: Base project directory
        branch_name: Branch name to create (e.g., task/create_invoice_abc123)

    Returns:
        dict with success, worktree_path, branch, or error
    """
    worktree_base = get_worktree_base_dir(project_dir)
    worktree_base.mkdir(parents=True, exist_ok=True)

    # Use sanitized branch name for directory
    dir_name = branch_name.replace("/", "-")
    worktree_path = worktree_base / dir_name

    if worktree_path.exists():
        return {
            "success": False,
            "error": f"Worktree already exists: {worktree_path}"
        }

    try:
        # Create worktree with new branch
        result = subprocess.run(
            ["git", "worktree", "add", str(worktree_path), "-b", branch_name],
            cwd=project_dir,
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            return {
                "success": False,
                "error": f"Failed to create worktree: {result.stderr}"
            }

        return {
            "success": True,
            "worktree_path": str(worktree_path),
            "branch": branch_name
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def remove_worktree(project_dir: Path, worktree_path: str) -> dict:
    """Remove a git worktree

    Args:
        project_dir: Base project directory
        worktree_path: Path to the worktree to remove

    Returns:
        dict with success or error
    """
    try:
        # Remove worktree
        result = subprocess.run(
            ["git", "worktree", "remove", worktree_path, "--force"],
            cwd=project_dir,
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            return {
                "success": False,
                "error": f"Failed to remove worktree: {result.stderr}"
            }

        return {"success": True}

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def list_worktrees(project_dir: Path) -> list[dict]:
    """List all git worktrees

    Args:
        project_dir: Base project directory

    Returns:
        List of worktree info dicts
    """
    try:
        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            cwd=project_dir,
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            return []

        worktrees = []
        current = {}

        for line in result.stdout.strip().split("\n"):
            if not line:
                if current:
                    worktrees.append(current)
                    current = {}
            elif line.startswith("worktree "):
                current["path"] = line[9:]
            elif line.startswith("HEAD "):
                current["head"] = line[5:]
            elif line.startswith("branch "):
                current["branch"] = line[7:]
            elif line == "bare":
                current["bare"] = True
            elif line == "detached":
                current["detached"] = True

        if current:
            worktrees.append(current)

        return worktrees

    except Exception as e:
        return []


def commit_and_push(worktree_path: Path, function_name: str, message: str | None = None) -> dict:
    """Commit changes and push to remote

    Args:
        worktree_path: Path to the worktree
        function_name: Name of the function being implemented
        message: Optional commit message

    Returns:
        dict with success, commit_hash, or error
    """
    if message is None:
        message = f"Implement {function_name}"

    try:
        # Stage all changes
        subprocess.run(["git", "add", "-A"], cwd=worktree_path, check=True)

        # Check if there are changes to commit
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=worktree_path,
            capture_output=True,
            text=True
        )

        if not status.stdout.strip():
            return {
                "success": True,
                "message": "No changes to commit"
            }

        # Commit
        commit_result = subprocess.run(
            ["git", "commit", "-m", message],
            cwd=worktree_path,
            capture_output=True,
            text=True
        )

        if commit_result.returncode != 0:
            return {
                "success": False,
                "error": f"Failed to commit: {commit_result.stderr}"
            }

        # Get commit hash
        hash_result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=worktree_path,
            capture_output=True,
            text=True
        )
        commit_hash = hash_result.stdout.strip()

        # Push
        push_result = subprocess.run(
            ["git", "push", "-u", "origin", "HEAD"],
            cwd=worktree_path,
            capture_output=True,
            text=True
        )

        if push_result.returncode != 0:
            return {
                "success": True,
                "commit_hash": commit_hash,
                "pushed": False,
                "push_error": push_result.stderr
            }

        return {
            "success": True,
            "commit_hash": commit_hash,
            "pushed": True
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def create_pull_request(worktree_path: Path, function_name: str,
                        title: str | None = None, body: str | None = None,
                        base_branch: str = "main") -> dict:
    """Create a pull request using gh CLI

    Args:
        worktree_path: Path to the worktree
        function_name: Name of the function being implemented
        title: Optional PR title
        body: Optional PR body
        base_branch: Base branch for the PR

    Returns:
        dict with success, pr_url, or error
    """
    if title is None:
        title = f"Implement {function_name}"

    if body is None:
        body = f"""## Summary
Implements `{function_name}` function.

---
Generated by The Mesh
"""

    try:
        result = subprocess.run(
            ["gh", "pr", "create",
             "--title", title,
             "--body", body,
             "--base", base_branch],
            cwd=worktree_path,
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            return {
                "success": False,
                "error": f"Failed to create PR: {result.stderr}"
            }

        # Extract PR URL from output
        pr_url = result.stdout.strip()

        return {
            "success": True,
            "pr_url": pr_url
        }

    except FileNotFoundError:
        return {
            "success": False,
            "error": "gh CLI not found. Install with: brew install gh"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


if __name__ == "__main__":
    # Test
    import tempfile

    print("Git Worktree Management Test")
    print(f"Short ID: {generate_short_id()}")
    print(f"Branch name: {get_branch_name('create_invoice')}")
