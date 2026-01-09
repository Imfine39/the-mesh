"""The Mesh MCP Server - Model Context Protocol interface for specification validation"""

import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from the_mesh.core.validator import (
    MeshValidator,
    ValidationResult,
    ValidationError,
    StructuredError,
    generate_fix_patches,
)
from the_mesh.graph.graph import DependencyGraph
from the_mesh.config.project import ProjectConfig
from the_mesh.hooks.git_worktree import (
    get_branch_name,
    create_worktree,
    remove_worktree,
    list_worktrees,
    commit_and_push,
    create_pull_request,
)
from the_mesh.generators.pytest_gen import PytestGenerator
from the_mesh.generators.pytest_unit_gen import PytestUnitGenerator
from the_mesh.generators.jest_gen import JestGenerator
from the_mesh.generators.unit_test_gen import UnitTestGenerator
from the_mesh.generators.task_package_gen import TaskPackageGenerator

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.server.models import InitializationOptions
    from mcp.types import Tool, TextContent, ServerCapabilities
    HAS_MCP = True
except ImportError:
    HAS_MCP = False


class SpecStorage:
    """Manages spec file storage, backups, and templates"""

    VALID_SECTIONS = [
        "meta", "state", "requirements", "derived", "functions", "scenarios",
        "invariants", "stateMachines", "events", "subscriptions", "roles",
        "sagas", "schedules", "gateways", "deadlines", "externalServices",
        "constraints", "relations", "dataPolicies", "auditPolicies"
    ]

    MINIMAL_TEMPLATE = {
        "meta": {
            "id": "new-spec",
            "title": "New Specification",
            "version": "0.1.0",
            "domain": "general"
        },
        "state": {}
    }

    def __init__(self, base_dir: Path | None = None, max_backups: int = 10):
        self.base_dir = base_dir or Path.home() / ".mesh" / "specs"
        self.backup_dir = self.base_dir / ".backups"
        self.template_dir = self.base_dir / ".templates"
        self.max_backups = max_backups

    def ensure_dirs(self) -> None:
        """Create storage directories if they don't exist"""
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.template_dir.mkdir(parents=True, exist_ok=True)

    def sanitize_id(self, spec_id: str) -> str:
        """Sanitize spec ID for filesystem use"""
        sanitized = re.sub(r'[^\w\-_.]', '_', spec_id)
        sanitized = sanitized.strip('._')
        return sanitized or "unnamed"

    def spec_path(self, spec_id: str) -> Path:
        """Get path for a spec file"""
        sanitized = self.sanitize_id(spec_id)
        if not sanitized.endswith('.mesh.json'):
            sanitized = f"{sanitized}.mesh.json"
        return self.base_dir / sanitized

    def create_backup(self, spec_id: str) -> Path | None:
        """Create timestamped backup, prune old backups"""
        spec_file = self.spec_path(spec_id)
        if not spec_file.exists():
            return None

        sanitized_id = self.sanitize_id(spec_id)
        backup_subdir = self.backup_dir / sanitized_id
        backup_subdir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{timestamp}_{sanitized_id}.mesh.json"
        backup_path = backup_subdir / backup_name

        shutil.copy2(spec_file, backup_path)
        self._prune_backups(sanitized_id)

        return backup_path

    def _prune_backups(self, spec_id: str) -> None:
        """Remove old backups exceeding max_backups"""
        backup_subdir = self.backup_dir / spec_id
        if not backup_subdir.exists():
            return

        backups = sorted(backup_subdir.glob("*.mesh.json"), reverse=True)
        for old_backup in backups[self.max_backups:]:
            old_backup.unlink()

    def list_specs(self, include_meta: bool = True) -> list[dict]:
        """List all spec files"""
        self.ensure_dirs()
        specs = []

        for spec_file in self.base_dir.glob("*.mesh.json"):
            entry = {
                "filename": spec_file.name,
                "spec_id": spec_file.stem.replace('.trir', ''),
                "modified": datetime.fromtimestamp(spec_file.stat().st_mtime).isoformat(),
                "size": spec_file.stat().st_size
            }

            if include_meta:
                try:
                    with open(spec_file) as f:
                        spec = json.load(f)
                        entry["meta"] = spec.get("meta", {})
                except (json.JSONDecodeError, IOError):
                    entry["meta"] = None
                    entry["error"] = "Failed to read meta"

            specs.append(entry)

        return sorted(specs, key=lambda x: x["modified"], reverse=True)

    def read_spec(self, spec_id: str) -> dict | None:
        """Read a spec file"""
        spec_file = self.spec_path(spec_id)
        if not spec_file.exists():
            return None

        with open(spec_file) as f:
            return json.load(f)

    def write_spec(self, spec: dict, spec_id: str | None = None) -> Path:
        """Write a spec to file"""
        self.ensure_dirs()

        if spec_id is None:
            spec_id = spec.get("meta", {}).get("id", "unnamed")

        spec_file = self.spec_path(spec_id)

        with open(spec_file, 'w') as f:
            json.dump(spec, f, indent=2, ensure_ascii=False)

        return spec_file

    def delete_spec(self, spec_id: str, keep_backup: bool = True) -> bool:
        """Delete a spec file"""
        spec_file = self.spec_path(spec_id)
        if not spec_file.exists():
            return False

        if keep_backup:
            self.create_backup(spec_id)

        spec_file.unlink()
        return True

    def list_backups(self, spec_id: str, limit: int = 10) -> list[dict]:
        """List backup versions of a spec"""
        sanitized_id = self.sanitize_id(spec_id)
        backup_subdir = self.backup_dir / sanitized_id

        if not backup_subdir.exists():
            return []

        backups = []
        for backup_file in sorted(backup_subdir.glob("*.mesh.json"), reverse=True)[:limit]:
            timestamp_str = backup_file.name.split('_')[0] + '_' + backup_file.name.split('_')[1]
            try:
                timestamp = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
            except ValueError:
                timestamp = datetime.fromtimestamp(backup_file.stat().st_mtime)

            backups.append({
                "filename": backup_file.name,
                "timestamp": timestamp.isoformat(),
                "path": str(backup_file),
                "size": backup_file.stat().st_size
            })

        return backups

    def restore_backup(self, spec_id: str, backup_timestamp: str) -> dict | None:
        """Restore a spec from a backup version"""
        sanitized_id = self.sanitize_id(spec_id)
        backup_subdir = self.backup_dir / sanitized_id

        if not backup_subdir.exists():
            return None

        for backup_file in backup_subdir.glob("*.mesh.json"):
            if backup_timestamp in backup_file.name:
                with open(backup_file) as f:
                    return json.load(f)

        return None

    def get_template(self, template_name: str) -> dict | None:
        """Get a built-in template"""
        templates = {
            "minimal": self.MINIMAL_TEMPLATE,
        }
        return templates.get(template_name)


class TaskManager:
    """Manages active task state for implementation workflow"""

    def __init__(self, base_dir: Path | None = None):
        self.base_dir = base_dir or Path.cwd()
        self.mesh_dir = self.base_dir / ".mesh"
        self.state_file = self.mesh_dir / "state.json"
        self.tasks_dir = self.base_dir / "tasks"
        self.config = ProjectConfig(self.base_dir)

    def ensure_dirs(self) -> None:
        """Create directories if they don't exist"""
        self.mesh_dir.mkdir(parents=True, exist_ok=True)
        self.tasks_dir.mkdir(parents=True, exist_ok=True)

    def load_state(self) -> dict:
        """Load task state from file"""
        if not self.state_file.exists():
            return {"active_tasks": {}, "completed_tasks": {}}

        with open(self.state_file) as f:
            return json.load(f)

    def save_state(self, state: dict) -> None:
        """Save task state to file"""
        self.ensure_dirs()
        with open(self.state_file, 'w') as f:
            json.dump(state, f, indent=2, ensure_ascii=False)

    def get_task_dir(self, function_name: str) -> Path:
        """Get path to task directory"""
        return self.tasks_dir / function_name

    def task_exists(self, function_name: str) -> bool:
        """Check if task folder exists"""
        return self.get_task_dir(function_name).exists()

    def activate_task(self, function_name: str, language: str = "python") -> dict:
        """Activate a task for implementation

        If auto_worktree is enabled in config, creates a git worktree with a unique branch.
        """
        if not self.task_exists(function_name):
            return {
                "success": False,
                "error": f"Task folder not found: tasks/{function_name}",
                "hint": "Run generate_task_package first"
            }

        state = self.load_state()
        config = self.config.load()

        # Check if already active
        if function_name in state["active_tasks"]:
            existing = state["active_tasks"][function_name]
            return {
                "success": True,
                "message": f"Task already active: {function_name}",
                "activated_at": existing["activated_at"],
                "worktree_path": existing.get("worktree_path"),
                "branch": existing.get("branch")
            }

        # Prepare task info
        task_info = {
            "activated_at": datetime.now().isoformat(),
            "language": language
        }

        # Create worktree if enabled and in a git repo
        worktree_result = None
        if config.get("git", {}).get("auto_worktree", False):
            # Check if we're in a git repository
            import subprocess
            git_check = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                cwd=self.base_dir,
                capture_output=True,
                text=True
            )

            if git_check.returncode == 0:
                branch_prefix = config.get("git", {}).get("branch_prefix", "task")
                branch_name = get_branch_name(function_name, prefix=branch_prefix)

                worktree_result = create_worktree(self.base_dir, branch_name)

                if worktree_result["success"]:
                    task_info["branch"] = worktree_result["branch"]
                    task_info["worktree_path"] = worktree_result["worktree_path"]
                else:
                    return {
                        "success": False,
                        "error": f"Failed to create worktree: {worktree_result.get('error')}",
                        "hint": "Check git status and ensure you're in a git repository"
                    }
            # If not a git repo, skip worktree creation silently

        # Add to active tasks
        state["active_tasks"][function_name] = task_info

        # Remove from completed if re-activating
        if function_name in state["completed_tasks"]:
            del state["completed_tasks"][function_name]

        self.save_state(state)

        # Build result
        result = {
            "success": True,
            "function": function_name,
            "activated_at": task_info["activated_at"],
            "task_dir": str(self.get_task_dir(function_name)),
            "impl_path": str(self.config.get_impl_path(function_name)),
        }

        if worktree_result and worktree_result["success"]:
            result["worktree_path"] = worktree_result["worktree_path"]
            result["branch"] = worktree_result["branch"]
            result["message"] = f"Worktree created at {worktree_result['worktree_path']}"

        return result

    def deactivate_task(self, function_name: str, cleanup_worktree: bool = False) -> dict:
        """Deactivate a task (without completing)

        Args:
            function_name: Name of the function/task to deactivate
            cleanup_worktree: If True, remove the worktree (default: False to preserve work)
        """
        state = self.load_state()

        if function_name not in state["active_tasks"]:
            return {
                "success": False,
                "error": f"Task not active: {function_name}"
            }

        task_info = state["active_tasks"][function_name]
        worktree_path = task_info.get("worktree_path")
        branch = task_info.get("branch")

        # Optionally cleanup worktree
        worktree_removed = False
        if cleanup_worktree and worktree_path:
            result = remove_worktree(self.base_dir, worktree_path)
            worktree_removed = result.get("success", False)

        del state["active_tasks"][function_name]
        self.save_state(state)

        result = {
            "success": True,
            "function": function_name,
            "message": "Task deactivated (not completed)"
        }

        if worktree_path:
            result["worktree_path"] = worktree_path
            result["branch"] = branch
            result["worktree_removed"] = worktree_removed
            if not cleanup_worktree:
                result["hint"] = "Worktree preserved. Use cleanup_worktree=True to remove it."

        return result

    def complete_task(self, function_name: str, test_results: dict | None = None,
                      commit_message: str | None = None, pr_title: str | None = None,
                      pr_body: str | None = None) -> dict:
        """Mark a task as completed

        If task has worktree:
        1. Commit changes (if any)
        2. Push to remote
        3. Create PR (if auto_pr enabled)
        4. Optionally cleanup worktree
        """
        state = self.load_state()
        config = self.config.load()

        if function_name not in state["active_tasks"]:
            return {
                "success": False,
                "error": f"Task not active: {function_name}",
                "hint": "Activate the task first with activate_task"
            }

        # If test results provided, check them
        if test_results:
            failed_tests = test_results.get("failed", [])
            if failed_tests:
                return {
                    "success": False,
                    "error": "Cannot complete task: tests failed",
                    "failed_tests": failed_tests,
                    "hint": "Fix the failing tests before completing"
                }

        task_info = state["active_tasks"][function_name]
        worktree_path = task_info.get("worktree_path")
        branch = task_info.get("branch")

        result = {
            "success": True,
            "function": function_name,
            "activated_at": task_info["activated_at"],
        }

        # If worktree exists, handle git operations
        if worktree_path:
            from pathlib import Path
            worktree_dir = Path(worktree_path)

            # 1. Commit and push
            commit_msg = commit_message or f"Implement {function_name}"
            commit_result = commit_and_push(worktree_dir, function_name, commit_msg)

            if commit_result["success"]:
                result["commit_hash"] = commit_result.get("commit_hash")
                result["pushed"] = commit_result.get("pushed", False)
                if commit_result.get("message"):
                    result["commit_message"] = commit_result["message"]
            else:
                # Commit failed - but we continue to mark as complete
                result["commit_error"] = commit_result.get("error")

            # 2. Create PR (if enabled and push was successful)
            pr_url = None
            if config.get("git", {}).get("auto_pr", False) and commit_result.get("pushed"):
                base_branch = config.get("git", {}).get("base_branch", "main")
                title = pr_title or f"Implement {function_name}"
                body = pr_body or self._generate_pr_body(function_name, test_results)

                pr_result = create_pull_request(
                    worktree_dir, function_name,
                    title=title, body=body, base_branch=base_branch
                )

                if pr_result["success"]:
                    pr_url = pr_result["pr_url"]
                    result["pr_url"] = pr_url
                else:
                    result["pr_error"] = pr_result.get("error")

            # 3. Cleanup worktree (if enabled)
            if config.get("git", {}).get("cleanup_worktree", False):
                cleanup_result = remove_worktree(self.base_dir, worktree_path)
                result["worktree_removed"] = cleanup_result.get("success", False)
            else:
                result["worktree_path"] = worktree_path
                result["branch"] = branch

        # Move from active to completed
        task_info = state["active_tasks"].pop(function_name)
        task_info["completed_at"] = datetime.now().isoformat()
        state["completed_tasks"][function_name] = task_info

        self.save_state(state)

        result["completed_at"] = task_info["completed_at"]
        return result

    def _generate_pr_body(self, function_name: str, test_results: dict | None = None) -> str:
        """Generate PR body from TASK.md"""
        task_dir = self.get_task_dir(function_name)
        task_md = task_dir / "TASK.md"

        summary = f"Implements `{function_name}` function."

        # Try to extract summary from TASK.md
        if task_md.exists():
            try:
                content = task_md.read_text()
                # Extract first section after ## Summary or just first paragraph
                lines = content.split('\n')
                for i, line in enumerate(lines):
                    if line.startswith('## Summary') or line.startswith('## 概要'):
                        # Get next non-empty lines
                        summary_lines = []
                        for j in range(i + 1, min(i + 5, len(lines))):
                            if lines[j].startswith('##'):
                                break
                            if lines[j].strip():
                                summary_lines.append(lines[j].strip())
                        if summary_lines:
                            summary = '\n'.join(summary_lines)
                        break
            except Exception:
                pass

        # Build test results section
        test_section = ""
        if test_results:
            passed = test_results.get("passed", [])
            failed = test_results.get("failed", [])
            test_section = f"""
## Test Results
- Passed: {len(passed)}
- Failed: {len(failed)}
"""

        return f"""## Summary
{summary}

## Changes
- Implements `{function_name}` function
{test_section}
---
Generated by The Mesh
"""

    def get_task_status(self, function_name: str | None = None) -> dict:
        """Get status of tasks"""
        state = self.load_state()

        if function_name:
            # Status of specific task
            if function_name in state["active_tasks"]:
                return {
                    "function": function_name,
                    "status": "active",
                    **state["active_tasks"][function_name]
                }
            elif function_name in state["completed_tasks"]:
                return {
                    "function": function_name,
                    "status": "completed",
                    **state["completed_tasks"][function_name]
                }
            elif self.task_exists(function_name):
                return {
                    "function": function_name,
                    "status": "pending"
                }
            else:
                return {
                    "function": function_name,
                    "status": "not_found",
                    "error": f"Task folder not found: tasks/{function_name}"
                }

        # Status of all tasks
        all_tasks = []

        # Get all task folders
        if self.tasks_dir.exists():
            for task_folder in self.tasks_dir.iterdir():
                if task_folder.is_dir():
                    task_name = task_folder.name
                    if task_name in state["active_tasks"]:
                        all_tasks.append({
                            "function": task_name,
                            "status": "active",
                            **state["active_tasks"][task_name]
                        })
                    elif task_name in state["completed_tasks"]:
                        all_tasks.append({
                            "function": task_name,
                            "status": "completed",
                            **state["completed_tasks"][task_name]
                        })
                    else:
                        all_tasks.append({
                            "function": task_name,
                            "status": "pending"
                        })

        return {
            "active_count": len(state["active_tasks"]),
            "completed_count": len(state["completed_tasks"]),
            "pending_count": len([t for t in all_tasks if t["status"] == "pending"]),
            "tasks": all_tasks
        }

    def check_edit_permission(self, file_path: str) -> dict:
        """Check if a file can be edited based on active tasks

        Rules:
        - src/{function}.py or src/functions/{function}.ts: allowed if task is active
        - tasks/{function}/TASK.md, context.json, etc: read-only
        - .mesh/tests/*: read-only (auto-generated)
        - Other files: allowed
        """
        file_path = Path(file_path).resolve()
        state = self.load_state()
        config = self.config.load()

        # Check if file is in src/ directory (implementation files)
        src_path = (self.base_dir / config.get("src_path", "src")).resolve()
        try:
            relative = file_path.relative_to(src_path)
            # Extract function name from filename
            filename = relative.name
            stem = relative.stem  # filename without extension

            # Check against active tasks (handle both naming conventions)
            for task_name in state["active_tasks"]:
                # Check if this impl file belongs to an active task
                expected_impl = self.config.get_impl_path(task_name).resolve()
                if file_path == expected_impl:
                    return {
                        "allowed": True,
                        "file": str(file_path),
                        "task": task_name,
                        "reason": "Implementation file belongs to active task"
                    }

            # File is in src/ but not associated with an active task
            # Try to find which task this file belongs to
            for task_folder in self.tasks_dir.iterdir() if self.tasks_dir.exists() else []:
                if task_folder.is_dir():
                    expected_impl = self.config.get_impl_path(task_folder.name).resolve()
                    if file_path == expected_impl:
                        return {
                            "allowed": False,
                            "file": str(file_path),
                            "task": task_folder.name,
                            "reason": f"Task '{task_folder.name}' is not active",
                            "hint": f"Run activate_task(function_name='{task_folder.name}') first"
                        }

            # Not a known task impl file - allow
            return {
                "allowed": True,
                "file": str(file_path),
                "reason": "File is not managed by task system"
            }

        except ValueError:
            pass

        # Check if file is in tasks/ directory
        tasks_dir = self.tasks_dir.resolve()
        try:
            relative = file_path.relative_to(tasks_dir)
            parts = relative.parts

            if len(parts) >= 1:
                task_name = parts[0]
                # Task folder files (TASK.md, context.json, pytest.ini) are read-only
                return {
                    "allowed": False,
                    "file": str(file_path),
                    "task": task_name,
                    "reason": "Task folder files are auto-generated and read-only",
                    "hint": "Edit the implementation file in src/ instead"
                }

        except ValueError:
            pass

        # Check if file is in .mesh/tests/
        tests_dir = (self.mesh_dir / "tests").resolve()
        try:
            relative = file_path.relative_to(tests_dir)
            return {
                "allowed": False,
                "file": str(file_path),
                "reason": "Test files are auto-generated and should not be manually edited",
                "hint": "Use sync_after_change to regenerate tests after spec changes"
            }
        except ValueError:
            pass

        # Other files - allow by default
        return {
            "allowed": True,
            "file": str(file_path),
            "reason": "File is not managed by task system"
        }

    def get_test_command(self, function_name: str) -> dict:
        """Get the command to run tests for a task"""
        if not self.task_exists(function_name):
            return {
                "error": f"Task not found: {function_name}"
            }

        state = self.load_state()
        task_info = state["active_tasks"].get(function_name, {})
        language = task_info.get("language", "python")

        task_dir = self.get_task_dir(function_name)

        if language == "python":
            return {
                "command": "pytest",
                "working_dir": str(task_dir),
                "config_file": str(task_dir / "pytest.ini")
            }
        else:
            return {
                "command": "npx jest",
                "working_dir": str(task_dir),
                "config_file": str(task_dir / "jest.config.json")
            }


class MeshServer:
    """MCP Server providing The Mesh specification validation tools for Claude Code"""

    def __init__(self, schema_dir: Path | None = None, storage_dir: Path | None = None):
        self.validator = MeshValidator(schema_dir)
        self.storage = SpecStorage(storage_dir)
        self.schema_dir = schema_dir or Path(__file__).parent.parent
        self._spec_cache: dict[str, dict] = {}  # Cache for loaded specs

    def get_tools(self) -> list[dict]:
        """Return list of available MCP tools"""
        return [
            {
                "name": "validate_spec",
                "description": "Validate a complete Mesh specification against schema and semantic rules",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "spec": {
                            "type": "object",
                            "description": "The Mesh specification to validate"
                        },
                        "spec_path": {
                            "type": "string",
                            "description": "Path to Mesh spec file (alternative to spec)"
                        }
                    }
                }
            },
            {
                "name": "validate_expression",
                "description": "Validate a single expression against Mesh expression schema",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "expression": {
                            "type": "object",
                            "description": "The expression to validate"
                        },
                        "context": {
                            "type": "object",
                            "description": "Context for validation (entities, derived, etc.)"
                        }
                    },
                    "required": ["expression"]
                }
            },
            {
                "name": "validate_partial",
                "description": "Validate only changed parts of a spec (incremental validation)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "base_spec": {
                            "type": "object",
                            "description": "The base specification"
                        },
                        "changes": {
                            "type": "array",
                            "items": {"type": "object"},
                            "description": "JSON Patch format changes to validate"
                        }
                    },
                    "required": ["base_spec", "changes"]
                }
            },
            {
                "name": "get_fix_suggestion",
                "description": "Get auto-fix suggestions for validation errors (JSON Patch format)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "errors": {
                            "type": "array",
                            "items": {"type": "object"},
                            "description": "List of validation errors"
                        }
                    },
                    "required": ["errors"]
                }
            },
            {
                "name": "suggest_completion",
                "description": "Suggest completions for missing required fields",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "partial_spec": {
                            "type": "object",
                            "description": "Partial specification needing completion"
                        }
                    },
                    "required": ["partial_spec"]
                }
            },
            {
                "name": "analyze_impact",
                "description": "Analyze impact of a change on the specification",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "spec": {
                            "type": "object",
                            "description": "The current specification"
                        },
                        "change": {
                            "type": "object",
                            "description": "The proposed change"
                        }
                    },
                    "required": ["spec", "change"]
                }
            },
            {
                "name": "check_reference",
                "description": "Check if a reference path is valid in the spec",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "spec": {
                            "type": "object",
                            "description": "The specification"
                        },
                        "reference": {
                            "type": "string",
                            "description": "Reference path to check (e.g., 'invoice.customer.name')"
                        }
                    },
                    "required": ["spec", "reference"]
                }
            },
            {
                "name": "get_entity_schema",
                "description": "Get schema information for an entity",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "spec": {
                            "type": "object",
                            "description": "The specification"
                        },
                        "entity_name": {
                            "type": "string",
                            "description": "Name of the entity"
                        }
                    },
                    "required": ["spec", "entity_name"]
                }
            },
            {
                "name": "list_valid_values",
                "description": "List valid values for a field (enum values, reference targets, etc.)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "spec": {
                            "type": "object",
                            "description": "The specification"
                        },
                        "field_path": {
                            "type": "string",
                            "description": "Path to the field (e.g., 'Invoice.status')"
                        }
                    },
                    "required": ["spec", "field_path"]
                }
            },
            {
                "name": "get_dependencies",
                "description": "Get dependencies for a given element in the spec",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "spec": {
                            "type": "object",
                            "description": "The specification"
                        },
                        "element_path": {
                            "type": "string",
                            "description": "Path to the element (e.g., 'derived.total_amount')"
                        }
                    },
                    "required": ["spec", "element_path"]
                }
            },
            # === Spec File Management Tools ===
            {
                "name": "spec_list",
                "description": "List all spec files in storage (~/.mesh/specs/)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "include_meta": {
                            "type": "boolean",
                            "description": "Include meta info (id, title, version) for each spec",
                            "default": True
                        }
                    }
                }
            },
            {
                "name": "spec_read",
                "description": "Read a spec file from storage",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "spec_id": {
                            "type": "string",
                            "description": "Spec ID or filename"
                        },
                        "sections": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional: only return specific sections"
                        }
                    },
                    "required": ["spec_id"]
                }
            },
            {
                "name": "spec_write",
                "description": "Write/create a spec file (validates before saving, creates backup)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "spec": {
                            "type": "object",
                            "description": "The complete spec to write"
                        },
                        "spec_id": {
                            "type": "string",
                            "description": "Override spec ID (otherwise uses meta.id)"
                        },
                        "validate": {
                            "type": "boolean",
                            "description": "Validate before saving (default: true)",
                            "default": True
                        },
                        "force": {
                            "type": "boolean",
                            "description": "Save even if validation fails (default: false)",
                            "default": False
                        }
                    },
                    "required": ["spec"]
                }
            },
            {
                "name": "spec_delete",
                "description": "Delete a spec file (moves to backup first)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "spec_id": {
                            "type": "string",
                            "description": "Spec ID or filename to delete"
                        },
                        "keep_backup": {
                            "type": "boolean",
                            "description": "Keep a backup copy (default: true)",
                            "default": True
                        }
                    },
                    "required": ["spec_id"]
                }
            },
            {
                "name": "spec_get_section",
                "description": "Get a specific section from a spec",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "spec_id": {"type": "string", "description": "Spec ID"},
                        "section": {
                            "type": "string",
                            "description": "Section name (e.g., 'state', 'functions', 'derived')"
                        },
                        "key": {
                            "type": "string",
                            "description": "Specific key within section (e.g., 'Invoice' in 'state')"
                        }
                    },
                    "required": ["spec_id", "section"]
                }
            },
            {
                "name": "spec_update_section",
                "description": "Update a specific section or item within a spec (creates backup)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "spec_id": {"type": "string", "description": "Spec ID"},
                        "section": {"type": "string", "description": "Section to update"},
                        "key": {
                            "type": "string",
                            "description": "Specific key to update (for object sections)"
                        },
                        "data": {
                            "type": "object",
                            "description": "New data for the section/key"
                        },
                        "merge": {
                            "type": "boolean",
                            "description": "Merge with existing data (default: false = replace)",
                            "default": False
                        },
                        "validate": {
                            "type": "boolean",
                            "description": "Validate after update (default: true)",
                            "default": True
                        }
                    },
                    "required": ["spec_id", "section", "data"]
                }
            },
            {
                "name": "spec_delete_section",
                "description": "Delete a section or item from a spec",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "spec_id": {"type": "string", "description": "Spec ID"},
                        "section": {"type": "string", "description": "Section to delete"},
                        "key": {
                            "type": "string",
                            "description": "Specific key to delete (e.g., delete one entity)"
                        }
                    },
                    "required": ["spec_id", "section"]
                }
            },
            {
                "name": "spec_create_from_template",
                "description": "Create a new spec from a template",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "template": {
                            "type": "string",
                            "enum": ["minimal"],
                            "description": "Template to use"
                        },
                        "meta": {
                            "type": "object",
                            "description": "Override meta fields (id, title, version, domain)",
                            "properties": {
                                "id": {"type": "string"},
                                "title": {"type": "string"},
                                "version": {"type": "string"},
                                "domain": {"type": "string"}
                            },
                            "required": ["id", "title", "version"]
                        }
                    },
                    "required": ["template", "meta"]
                }
            },
            {
                "name": "spec_list_backups",
                "description": "List backup versions of a spec",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "spec_id": {"type": "string", "description": "Spec ID"},
                        "limit": {
                            "type": "integer",
                            "description": "Max backups to return (default: 10)",
                            "default": 10
                        }
                    },
                    "required": ["spec_id"]
                }
            },
            {
                "name": "spec_restore_backup",
                "description": "Restore a spec from a backup version",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "spec_id": {"type": "string", "description": "Spec ID"},
                        "backup_timestamp": {
                            "type": "string",
                            "description": "Timestamp of backup to restore (from spec_list_backups)"
                        },
                        "backup_current": {
                            "type": "boolean",
                            "description": "Backup current before restoring (default: true)",
                            "default": True
                        }
                    },
                    "required": ["spec_id", "backup_timestamp"]
                }
            },
            # === Context Extraction Tools ===
            {
                "name": "get_function_context",
                "description": "Get minimal context needed to implement a function (entities, derived, scenarios, invariants with full definitions)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "spec": {
                            "type": "object",
                            "description": "The specification"
                        },
                        "spec_path": {
                            "type": "string",
                            "description": "Path to spec file (alternative to spec)"
                        },
                        "spec_id": {
                            "type": "string",
                            "description": "Spec ID in storage (alternative to spec/spec_path)"
                        },
                        "function_name": {
                            "type": "string",
                            "description": "Name of the function to get context for"
                        }
                    },
                    "required": ["function_name"]
                }
            },
            # === Test Generation Tools ===
            {
                "name": "generate_tests",
                "description": "Generate test code from TRIR specification scenarios. Supports pytest (Python) and Jest (JavaScript/TypeScript).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "spec": {
                            "type": "object",
                            "description": "The specification"
                        },
                        "spec_path": {
                            "type": "string",
                            "description": "Path to spec file (alternative to spec)"
                        },
                        "spec_id": {
                            "type": "string",
                            "description": "Spec ID in storage (alternative to spec/spec_path)"
                        },
                        "framework": {
                            "type": "string",
                            "enum": ["pytest", "pytest-ut", "jest", "jest-ts", "jest-ut", "jest-ts-ut"],
                            "description": "Test framework: 'pytest'/'jest'/'jest-ts' for AT, add '-ut' suffix for Unit Tests",
                            "default": "pytest"
                        },
                        "function_name": {
                            "type": "string",
                            "description": "Generate tests only for this function (optional, default: all)"
                        }
                    }
                }
            },
            {
                "name": "generate_task_package",
                "description": "Generate a complete implementation task package with tests, context, skeleton, and test runner config. Tests are stored in .mesh/tests/ (no duplication), task files in tasks/{function}/",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "spec": {
                            "type": "object",
                            "description": "The specification"
                        },
                        "spec_path": {
                            "type": "string",
                            "description": "Path to spec file (alternative to spec)"
                        },
                        "spec_id": {
                            "type": "string",
                            "description": "Spec ID in storage (alternative to spec/spec_path)"
                        },
                        "function_name": {
                            "type": "string",
                            "description": "Function to generate task package for. Use 'all' to generate for all functions."
                        },
                        "language": {
                            "type": "string",
                            "enum": ["python", "typescript", "javascript"],
                            "description": "Target language for implementation",
                            "default": "python"
                        },
                        "output_dir": {
                            "type": "string",
                            "description": "Base directory for output (default: current directory)",
                            "default": "."
                        }
                    },
                    "required": ["function_name"]
                }
            },
            {
                "name": "sync_after_change",
                "description": "Sync task packages after spec changes. Analyzes impact and regenerates only affected tests, task packages (TASK.md, context.json, impl skeleton, pytest.ini).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "spec": {
                            "type": "object",
                            "description": "The NEW specification (after changes)"
                        },
                        "spec_path": {
                            "type": "string",
                            "description": "Path to NEW spec file (alternative to spec)"
                        },
                        "spec_id": {
                            "type": "string",
                            "description": "Spec ID in storage (alternative to spec/spec_path)"
                        },
                        "changes": {
                            "type": "array",
                            "items": {"type": "object"},
                            "description": "JSON Patch format changes that were made"
                        },
                        "language": {
                            "type": "string",
                            "enum": ["python", "typescript", "javascript"],
                            "description": "Target language for implementation",
                            "default": "python"
                        },
                        "output_dir": {
                            "type": "string",
                            "description": "Base directory for output (default: current directory)",
                            "default": "."
                        }
                    },
                    "required": ["changes"]
                }
            },
            # === Task Management Tools ===
            {
                "name": "activate_task",
                "description": "Activate a task for implementation. Only active tasks can have their impl files edited.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "function_name": {
                            "type": "string",
                            "description": "Name of the function/task to activate"
                        },
                        "language": {
                            "type": "string",
                            "enum": ["python", "typescript", "javascript"],
                            "description": "Target language for implementation",
                            "default": "python"
                        },
                        "output_dir": {
                            "type": "string",
                            "description": "Base directory containing tasks/ folder",
                            "default": "."
                        }
                    },
                    "required": ["function_name"]
                }
            },
            {
                "name": "deactivate_task",
                "description": "Deactivate a task without completing it. Use this to pause work on a task.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "function_name": {
                            "type": "string",
                            "description": "Name of the function/task to deactivate"
                        },
                        "cleanup_worktree": {
                            "type": "boolean",
                            "description": "If True, remove the worktree (default: False to preserve work)",
                            "default": False
                        },
                        "output_dir": {
                            "type": "string",
                            "description": "Base directory containing tasks/ folder",
                            "default": "."
                        }
                    },
                    "required": ["function_name"]
                }
            },
            {
                "name": "complete_task",
                "description": "Mark a task as completed. If task has worktree, commits changes, pushes, and creates PR (if enabled).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "function_name": {
                            "type": "string",
                            "description": "Name of the function/task to complete"
                        },
                        "test_results": {
                            "type": "object",
                            "description": "Test results from running task tests. Include 'passed' and 'failed' arrays.",
                            "properties": {
                                "passed": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "List of passed test names"
                                },
                                "failed": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "List of failed test names"
                                }
                            }
                        },
                        "commit_message": {
                            "type": "string",
                            "description": "Custom commit message (default: 'Implement {function_name}')"
                        },
                        "pr_title": {
                            "type": "string",
                            "description": "Custom PR title (default: 'Implement {function_name}')"
                        },
                        "pr_body": {
                            "type": "string",
                            "description": "Custom PR body (default: generated from TASK.md)"
                        },
                        "output_dir": {
                            "type": "string",
                            "description": "Base directory containing tasks/ folder",
                            "default": "."
                        }
                    },
                    "required": ["function_name"]
                }
            },
            {
                "name": "get_task_status",
                "description": "Get status of tasks (active, completed, pending). Returns all tasks if no function_name specified.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "function_name": {
                            "type": "string",
                            "description": "Optional: specific task to check status"
                        },
                        "output_dir": {
                            "type": "string",
                            "description": "Base directory containing tasks/ folder",
                            "default": "."
                        }
                    }
                }
            },
            {
                "name": "check_edit_permission",
                "description": "Check if a file can be edited based on active task status. Only impl files of active tasks are editable.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Path to the file to check"
                        },
                        "output_dir": {
                            "type": "string",
                            "description": "Base directory containing tasks/ folder",
                            "default": "."
                        }
                    },
                    "required": ["file_path"]
                }
            },
            {
                "name": "get_test_command",
                "description": "Get the command to run tests for a task",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "function_name": {
                            "type": "string",
                            "description": "Name of the function/task"
                        },
                        "output_dir": {
                            "type": "string",
                            "description": "Base directory containing tasks/ folder",
                            "default": "."
                        }
                    },
                    "required": ["function_name"]
                }
            },
            # === Project Configuration Tools ===
            {
                "name": "init_project",
                "description": "Initialize project configuration. Creates .mesh/config.json with language, paths, and git settings.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "language": {
                            "type": "string",
                            "enum": ["python", "typescript", "javascript"],
                            "description": "Project language",
                            "default": "python"
                        },
                        "src_path": {
                            "type": "string",
                            "description": "Path for implementation files (default: 'src' for Python, 'src/functions' for TypeScript)"
                        },
                        "test_framework": {
                            "type": "string",
                            "enum": ["pytest", "jest", "vitest"],
                            "description": "Test framework (default: based on language)"
                        },
                        "base_branch": {
                            "type": "string",
                            "description": "Base branch for PRs (default: 'main')"
                        },
                        "auto_worktree": {
                            "type": "boolean",
                            "description": "Auto-create worktree on task activation (default: true)"
                        },
                        "auto_pr": {
                            "type": "boolean",
                            "description": "Auto-create PR on task completion (default: true)"
                        },
                        "output_dir": {
                            "type": "string",
                            "description": "Base directory for the project",
                            "default": "."
                        }
                    }
                }
            },
            {
                "name": "get_project_config",
                "description": "Get current project configuration",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "output_dir": {
                            "type": "string",
                            "description": "Base directory for the project",
                            "default": "."
                        }
                    }
                }
            }
        ]

    def call_tool(self, name: str, arguments: dict) -> dict:
        """Execute a tool and return results"""
        handlers = {
            "validate_spec": self._validate_spec,
            "validate_expression": self._validate_expression,
            "validate_partial": self._validate_partial,
            "get_fix_suggestion": self._get_fix_suggestion,
            "suggest_completion": self._suggest_completion,
            "analyze_impact": self._analyze_impact,
            "check_reference": self._check_reference,
            "get_entity_schema": self._get_entity_schema,
            "list_valid_values": self._list_valid_values,
            "get_dependencies": self._get_dependencies,
            # Spec file management
            "spec_list": self._spec_list,
            "spec_read": self._spec_read,
            "spec_write": self._spec_write,
            "spec_delete": self._spec_delete,
            "spec_get_section": self._spec_get_section,
            "spec_update_section": self._spec_update_section,
            "spec_delete_section": self._spec_delete_section,
            "spec_create_from_template": self._spec_create_from_template,
            "spec_list_backups": self._spec_list_backups,
            "spec_restore_backup": self._spec_restore_backup,
            # Context extraction
            "get_function_context": self._get_function_context,
            # Test generation
            "generate_tests": self._generate_tests,
            "generate_task_package": self._generate_task_package,
            "sync_after_change": self._sync_after_change,
            # Task management
            "activate_task": self._activate_task,
            "deactivate_task": self._deactivate_task,
            "complete_task": self._complete_task,
            "get_task_status": self._get_task_status,
            "check_edit_permission": self._check_edit_permission,
            "get_test_command": self._get_test_command,
            # Project configuration
            "init_project": self._init_project,
            "get_project_config": self._get_project_config,
        }

        if name not in handlers:
            return {"error": f"Unknown tool: {name}"}

        try:
            return handlers[name](arguments)
        except Exception as e:
            return {"error": str(e), "error_type": type(e).__name__}

    def _load_spec(self, spec: dict | None, spec_path: str | None) -> dict:
        """Load spec from dict or file path"""
        if spec:
            return spec
        if spec_path:
            path = Path(spec_path)
            if path.exists():
                with open(path) as f:
                    return json.load(f)
            raise FileNotFoundError(f"Spec file not found: {spec_path}")
        raise ValueError("Either 'spec' or 'spec_path' must be provided")

    def _validate_spec(self, args: dict) -> dict:
        """Validate a complete Mesh specification"""
        spec = self._load_spec(args.get("spec"), args.get("spec_path"))
        result = self.validator.validate(spec)

        return {
            "valid": result.valid,
            "errors": [e.to_structured().to_dict() for e in result.errors],
            "warnings": [e.to_structured().to_dict() for e in result.warnings],
            "error_count": len(result.errors),
            "warning_count": len(result.warnings),
            "fix_patches": result.get_fix_patches(),
        }

    def _validate_expression(self, args: dict) -> dict:
        """Validate a single expression"""
        expression = args["expression"]
        context = args.get("context", {})

        # Create a minimal spec for validation
        minimal_spec = {
            "meta": {"name": "expression_validation", "version": "1.0"},
            "state": {
                "entities": context.get("entities", {}),
                "derived": {
                    "_temp_expr": {
                        "formula": expression,
                        "returns": "any"
                    }
                }
            }
        }

        result = self.validator.validate(minimal_spec)

        # Filter errors to only those related to the expression
        expr_errors = [
            e for e in result.errors
            if "_temp_expr" in e.path or "expression" in e.path.lower()
        ]

        return {
            "valid": len(expr_errors) == 0,
            "errors": [e.to_structured().to_dict() for e in expr_errors],
        }

    def _validate_partial(self, args: dict) -> dict:
        """Validate only changed parts of a spec (incremental validation)"""
        base_spec = args["base_spec"]
        changes = args["changes"]

        # Apply changes to create new spec
        import copy
        new_spec = copy.deepcopy(base_spec)

        for change in changes:
            op = change.get("op")
            path = change.get("path", "").strip("/").split("/")
            value = change.get("value")

            # Navigate to the target location
            current = new_spec
            for i, key in enumerate(path[:-1]):
                if isinstance(current, dict):
                    current = current.get(key, {})
                elif isinstance(current, list) and key.isdigit():
                    current = current[int(key)]

            # Apply the operation
            if path:
                final_key = path[-1]
                if op == "add" or op == "replace":
                    if isinstance(current, dict):
                        current[final_key] = value
                    elif isinstance(current, list) and final_key.isdigit():
                        if op == "add":
                            current.insert(int(final_key), value)
                        else:
                            current[int(final_key)] = value
                elif op == "remove":
                    if isinstance(current, dict) and final_key in current:
                        del current[final_key]
                    elif isinstance(current, list) and final_key.isdigit():
                        del current[int(final_key)]

        # Validate the modified spec
        result = self.validator.validate(new_spec)

        # Optionally filter to only errors in changed paths
        changed_paths = set()
        for change in changes:
            changed_paths.add(change.get("path", "").strip("/").replace("/", "."))

        return {
            "valid": result.valid,
            "errors": [e.to_structured().to_dict() for e in result.errors],
            "warnings": [e.to_structured().to_dict() for e in result.warnings],
            "changes_applied": len(changes),
        }

    def _get_fix_suggestion(self, args: dict) -> dict:
        """Get auto-fix suggestions for validation errors"""
        errors = args["errors"]

        # Convert dict errors back to ValidationError objects
        validation_errors = []
        for e in errors:
            validation_errors.append(ValidationError(
                path=e.get("path", ""),
                message=e.get("message", ""),
                severity=e.get("severity", "error"),
                code=e.get("code", ""),
                category=e.get("category", "schema"),
                expected=e.get("expected"),
                actual=e.get("actual"),
                valid_options=e.get("valid_options", []),
                auto_fixable=e.get("auto_fixable", False),
                fix_patch=e.get("fix_patch"),
            ))

        patches = generate_fix_patches(validation_errors)

        return {
            "patches": patches,
            "fixable_count": len(patches),
            "total_errors": len(errors),
        }

    def _suggest_completion(self, args: dict) -> dict:
        """Suggest completions for missing required fields"""
        partial_spec = args["partial_spec"]
        suggestions = []

        # Check for missing meta fields
        if "meta" not in partial_spec:
            suggestions.append({
                "path": "/meta",
                "suggestion": {"name": "untitled", "version": "1.0"},
                "reason": "meta is required"
            })

        # Check for missing state
        if "state" not in partial_spec:
            suggestions.append({
                "path": "/state",
                "suggestion": {"entities": {}},
                "reason": "state is required"
            })

        state = partial_spec.get("state", {})

        # Check SagaSteps for missing forward
        for saga_name, saga in state.get("sagas", {}).items():
            for i, step in enumerate(saga.get("steps", [])):
                if "forward" not in step and "action" not in step:
                    suggestions.append({
                        "path": f"/state/sagas/{saga_name}/steps/{i}/forward",
                        "suggestion": f"execute_{step.get('name', 'step')}",
                        "reason": "SagaStep requires 'forward' field"
                    })

        # Check UpdateActions for missing target
        for func_name, func in state.get("functions", {}).items():
            for i, post in enumerate(func.get("post", [])):
                action = post.get("action", {})
                if "update" in action and "target" not in action:
                    suggestions.append({
                        "path": f"/state/functions/{func_name}/post/{i}/action/target",
                        "suggestion": {"type": "input", "name": "id"},
                        "reason": "UpdateAction requires 'target' field"
                    })

        # Check DerivedFormula for missing returns
        for derived_name, derived in state.get("derived", {}).items():
            if "returns" not in derived:
                suggestions.append({
                    "path": f"/state/derived/{derived_name}/returns",
                    "suggestion": "number",
                    "reason": "DerivedFormula requires 'returns' field"
                })

        return {
            "suggestions": suggestions,
            "count": len(suggestions),
        }

    def _analyze_impact(self, args: dict) -> dict:
        """Analyze impact of a change on the specification"""
        spec = args["spec"]
        change = args["change"]

        # Build dependency graph
        graph = DependencyGraph()
        graph.build_from_spec(spec)

        # Determine what's being changed
        change_path = change.get("path", "").strip("/")
        change_type = change.get("type", "modify")  # add, modify, remove

        # Parse change_path to get target_type and target_name
        # Format: "state/entities/Invoice" or "state.entities.Invoice"
        parts = change_path.replace("/", ".").split(".")
        target_type = "unknown"
        target_name = change_path

        if len(parts) >= 3 and parts[0] == "state":
            category = parts[1]  # entities, derived, functions, etc.
            target_name = parts[2] if len(parts) > 2 else ""
            type_map = {
                "entities": "entity",
                "derived": "derived",
                "functions": "function",
                "scenarios": "scenario",
                "invariants": "invariant",
                "stateMachines": "stateMachine",
                "events": "event",
                "subscriptions": "subscription",
                "sagas": "saga",
                "roles": "role",
                "gateways": "gateway",
                "deadlines": "deadline",
            }
            target_type = type_map.get(category, "unknown")

        # Find affected elements
        impact = graph.analyze_impact(target_type, target_name, change_type)

        # Calculate total affected
        total_affected = (
            len(impact.affected_entities) +
            len(impact.affected_derived) +
            len(impact.affected_functions) +
            len(impact.affected_scenarios) +
            len(impact.affected_invariants) +
            len(impact.affected_state_machines) +
            len(impact.affected_events) +
            len(impact.affected_subscriptions) +
            len(impact.affected_sagas) +
            len(impact.affected_roles) +
            len(impact.affected_gateways) +
            len(impact.affected_deadlines)
        )

        # Determine if breaking change
        is_breaking = (
            change_type == "remove" and
            (len(impact.affected_functions) > 0 or
             len(impact.affected_scenarios) > 0 or
             len(impact.breaking_changes) > 0)
        )

        return {
            "change_path": change_path,
            "change_type": change_type,
            "affected_entities": list(impact.affected_entities),
            "affected_derived": list(impact.affected_derived),
            "affected_functions": list(impact.affected_functions),
            "affected_scenarios": list(impact.affected_scenarios),
            "affected_invariants": list(impact.affected_invariants),
            "affected_state_machines": list(impact.affected_state_machines),
            "affected_events": list(impact.affected_events),
            "affected_sagas": list(impact.affected_sagas),
            "affected_roles": list(impact.affected_roles),
            "total_affected": total_affected,
            "breaking_change": is_breaking,
            "breaking_changes": impact.breaking_changes,
        }

    def _check_reference(self, args: dict) -> dict:
        """Check if a reference path is valid in the spec"""
        spec = args["spec"]
        reference = args["reference"]

        state = spec.get("state", {})
        entities = state.get("entities", {})
        derived = state.get("derived", {})

        parts = reference.split(".")
        if not parts:
            return {"valid": False, "error": "Empty reference"}

        # First part should be an entity name or 'self'
        first = parts[0]
        if first == "self":
            return {
                "valid": True,
                "note": "'self' reference - context dependent",
                "remaining_path": ".".join(parts[1:])
            }

        if first not in entities:
            # Check if it's a derived formula
            if first in derived:
                return {"valid": True, "type": "derived", "name": first}
            return {
                "valid": False,
                "error": f"Unknown entity: {first}",
                "valid_entities": list(entities.keys())
            }

        # Navigate through the reference path
        current_entity = entities[first]
        path_so_far = first

        for i, part in enumerate(parts[1:], 1):
            fields = current_entity.get("fields", {})
            if part not in fields:
                return {
                    "valid": False,
                    "error": f"Unknown field '{part}' in {path_so_far}",
                    "valid_fields": list(fields.keys())
                }

            field = fields[part]
            field_type = field.get("type", {})
            path_so_far += f".{part}"

            # Check if it's a reference to another entity
            if isinstance(field_type, dict) and "ref" in field_type:
                ref_target = field_type["ref"]
                if ref_target in entities:
                    current_entity = entities[ref_target]
                else:
                    return {
                        "valid": False,
                        "error": f"Invalid reference target: {ref_target}",
                        "at_path": path_so_far
                    }
            elif i < len(parts) - 1:
                # Trying to traverse through a non-reference field
                return {
                    "valid": False,
                    "error": f"Cannot traverse through non-reference field: {part}",
                    "at_path": path_so_far,
                    "field_type": field_type
                }

        return {
            "valid": True,
            "resolved_path": path_so_far,
            "final_entity": current_entity.get("_kind", "entity")
        }

    def _get_entity_schema(self, args: dict) -> dict:
        """Get schema information for an entity"""
        spec = args["spec"]
        entity_name = args["entity_name"]

        entities = spec.get("state", {}).get("entities", {})

        if entity_name not in entities:
            return {
                "found": False,
                "error": f"Entity not found: {entity_name}",
                "available_entities": list(entities.keys())
            }

        entity = entities[entity_name]
        fields = entity.get("fields", {})

        # Build field info
        field_info = {}
        for field_name, field in fields.items():
            field_type = field.get("type")
            info = {
                "type": field_type,
                "required": field.get("required", False),
            }
            if "default" in field:
                info["default"] = field["default"]
            if isinstance(field_type, dict):
                if "enum" in field_type:
                    info["enum_values"] = field_type["enum"]
                if "ref" in field_type:
                    info["references"] = field_type["ref"]
            field_info[field_name] = info

        return {
            "found": True,
            "entity_name": entity_name,
            "fields": field_info,
            "field_count": len(fields),
            "indexes": entity.get("indexes", []),
        }

    def _list_valid_values(self, args: dict) -> dict:
        """List valid values for a field"""
        spec = args["spec"]
        field_path = args["field_path"]

        parts = field_path.split(".")
        if len(parts) != 2:
            return {"error": "field_path should be 'EntityName.fieldName'"}

        entity_name, field_name = parts
        entities = spec.get("state", {}).get("entities", {})

        if entity_name not in entities:
            return {
                "found": False,
                "error": f"Entity not found: {entity_name}",
                "available_entities": list(entities.keys())
            }

        entity = entities[entity_name]
        fields = entity.get("fields", {})

        if field_name not in fields:
            return {
                "found": False,
                "error": f"Field not found: {field_name}",
                "available_fields": list(fields.keys())
            }

        field = fields[field_name]
        field_type = field.get("type")

        result = {
            "found": True,
            "field_path": field_path,
            "field_type": field_type,
        }

        if isinstance(field_type, dict):
            if "enum" in field_type:
                result["valid_values"] = field_type["enum"]
                result["value_type"] = "enum"
            elif "ref" in field_type:
                ref_target = field_type["ref"]
                result["references"] = ref_target
                result["value_type"] = "reference"
                # List existing IDs if available
                if ref_target in entities:
                    result["note"] = f"Reference to {ref_target} entity"
        elif field_type in ("string", "int", "float", "bool", "datetime"):
            result["value_type"] = field_type

        return result

    def _get_dependencies(self, args: dict) -> dict:
        """Get dependencies for a given element in the spec"""
        spec = args["spec"]
        element_path = args["element_path"]

        # Build dependency graph
        graph = DependencyGraph()
        graph.build_from_spec(spec)

        # Get dependencies
        node_id = element_path.replace("/", ".")

        deps = graph.get_dependencies(node_id)
        dependents = graph.get_dependents(node_id)

        return {
            "element": element_path,
            "dependencies": list(deps),
            "dependents": list(dependents),
            "dependency_count": len(deps),
            "dependent_count": len(dependents),
        }

    # === Spec File Management Handlers ===

    def _spec_list(self, args: dict) -> dict:
        """List all spec files in storage"""
        include_meta = args.get("include_meta", True)
        specs = self.storage.list_specs(include_meta)
        return {
            "specs": specs,
            "count": len(specs),
            "storage_path": str(self.storage.base_dir),
        }

    def _spec_read(self, args: dict) -> dict:
        """Read a spec file from storage"""
        spec_id = args["spec_id"]
        sections = args.get("sections")

        spec = self.storage.read_spec(spec_id)
        if spec is None:
            return {
                "found": False,
                "error": f"Spec not found: {spec_id}",
                "available_specs": [s["spec_id"] for s in self.storage.list_specs(False)]
            }

        if sections:
            filtered = {"meta": spec.get("meta", {})}
            for section in sections:
                if section in spec:
                    filtered[section] = spec[section]
            spec = filtered

        return {
            "found": True,
            "spec": spec,
            "path": str(self.storage.spec_path(spec_id)),
        }

    def _spec_write(self, args: dict) -> dict:
        """Write/create a spec file"""
        spec = args["spec"]
        spec_id = args.get("spec_id") or spec.get("meta", {}).get("id")
        validate = args.get("validate", True)
        force = args.get("force", False)

        if not spec_id:
            return {"success": False, "error": "No spec_id provided and meta.id missing"}

        # Validate if requested
        validation_result = None
        if validate:
            result = self.validator.validate(spec)
            validation_result = {
                "valid": result.valid,
                "error_count": len(result.errors),
                "warning_count": len(result.warnings),
            }
            if not result.valid and not force:
                return {
                    "success": False,
                    "error": "Validation failed",
                    "validation": validation_result,
                    "errors": [e.to_structured().to_dict() for e in result.errors[:10]]
                }

        # Create backup if file exists
        backup_created = False
        if self.storage.spec_path(spec_id).exists():
            self.storage.create_backup(spec_id)
            backup_created = True

        # Write spec
        path = self.storage.write_spec(spec, spec_id)

        return {
            "success": True,
            "path": str(path),
            "spec_id": spec_id,
            "validation": validation_result,
            "backup_created": backup_created,
        }

    def _spec_delete(self, args: dict) -> dict:
        """Delete a spec file"""
        spec_id = args["spec_id"]
        keep_backup = args.get("keep_backup", True)

        if not self.storage.spec_path(spec_id).exists():
            return {
                "success": False,
                "error": f"Spec not found: {spec_id}",
            }

        deleted = self.storage.delete_spec(spec_id, keep_backup)
        return {
            "success": deleted,
            "deleted": spec_id,
            "backup_kept": keep_backup,
        }

    def _spec_get_section(self, args: dict) -> dict:
        """Get a specific section from a spec"""
        spec_id = args["spec_id"]
        section = args["section"]
        key = args.get("key")

        spec = self.storage.read_spec(spec_id)
        if spec is None:
            return {"found": False, "error": f"Spec not found: {spec_id}"}

        if section not in spec:
            return {
                "found": False,
                "error": f"Section not found: {section}",
                "available_sections": list(spec.keys()),
                "valid_sections": SpecStorage.VALID_SECTIONS,
            }

        data = spec[section]
        if key:
            if isinstance(data, dict) and key in data:
                data = data[key]
            else:
                return {
                    "found": False,
                    "error": f"Key not found: {key}",
                    "available_keys": list(data.keys()) if isinstance(data, dict) else [],
                }

        return {
            "found": True,
            "section": section,
            "key": key,
            "data": data,
        }

    def _spec_update_section(self, args: dict) -> dict:
        """Update a specific section or item within a spec"""
        spec_id = args["spec_id"]
        section = args["section"]
        key = args.get("key")
        data = args["data"]
        merge = args.get("merge", False)
        validate = args.get("validate", True)

        spec = self.storage.read_spec(spec_id)
        if spec is None:
            return {"success": False, "error": f"Spec not found: {spec_id}"}

        # Update section
        if section not in spec:
            spec[section] = {} if key else data

        if key:
            if not isinstance(spec[section], dict):
                return {"success": False, "error": f"Section {section} is not a dict, cannot use key"}
            if merge and key in spec[section] and isinstance(spec[section][key], dict):
                spec[section][key] = {**spec[section][key], **data}
            else:
                spec[section][key] = data
        else:
            if merge and isinstance(spec[section], dict) and isinstance(data, dict):
                spec[section] = {**spec[section], **data}
            else:
                spec[section] = data

        # Validate and save
        return self._spec_write({
            "spec": spec,
            "spec_id": spec_id,
            "validate": validate,
            "force": False
        })

    def _spec_delete_section(self, args: dict) -> dict:
        """Delete a section or item from a spec"""
        spec_id = args["spec_id"]
        section = args["section"]
        key = args.get("key")

        spec = self.storage.read_spec(spec_id)
        if spec is None:
            return {"success": False, "error": f"Spec not found: {spec_id}"}

        if section not in spec:
            return {"success": False, "error": f"Section not found: {section}"}

        deleted_key = None
        if key:
            if isinstance(spec[section], dict) and key in spec[section]:
                del spec[section][key]
                deleted_key = key
            else:
                return {"success": False, "error": f"Key not found: {key}"}
        else:
            if section in ["meta", "state"]:
                return {"success": False, "error": f"Cannot delete required section: {section}"}
            del spec[section]

        # Save without validation (deletion might make spec invalid temporarily)
        self.storage.create_backup(spec_id)
        self.storage.write_spec(spec, spec_id)

        return {
            "success": True,
            "deleted_section": section if not key else None,
            "deleted_key": deleted_key,
        }

    def _spec_create_from_template(self, args: dict) -> dict:
        """Create a new spec from a template"""
        template_name = args["template"]
        meta = args["meta"]

        template = self.storage.get_template(template_name)
        if template is None:
            return {
                "success": False,
                "error": f"Unknown template: {template_name}",
                "available_templates": ["minimal"],
            }

        # Deep copy and update meta
        import copy
        spec = copy.deepcopy(template)
        spec["meta"] = {**spec.get("meta", {}), **meta}

        spec_id = meta.get("id")
        if self.storage.spec_path(spec_id).exists():
            return {
                "success": False,
                "error": f"Spec already exists: {spec_id}",
            }

        path = self.storage.write_spec(spec, spec_id)
        return {
            "success": True,
            "spec": spec,
            "path": str(path),
            "template_used": template_name,
        }

    def _spec_list_backups(self, args: dict) -> dict:
        """List backup versions of a spec"""
        spec_id = args["spec_id"]
        limit = args.get("limit", 10)

        backups = self.storage.list_backups(spec_id, limit)
        return {
            "spec_id": spec_id,
            "backups": backups,
            "count": len(backups),
        }

    def _spec_restore_backup(self, args: dict) -> dict:
        """Restore a spec from a backup version"""
        spec_id = args["spec_id"]
        backup_timestamp = args["backup_timestamp"]
        backup_current = args.get("backup_current", True)

        # Find and load backup
        backup_spec = self.storage.restore_backup(spec_id, backup_timestamp)
        if backup_spec is None:
            backups = self.storage.list_backups(spec_id)
            return {
                "success": False,
                "error": f"Backup not found for timestamp: {backup_timestamp}",
                "available_backups": [b["timestamp"] for b in backups],
            }

        # Backup current version if requested
        current_backed_up = False
        if backup_current and self.storage.spec_path(spec_id).exists():
            self.storage.create_backup(spec_id)
            current_backed_up = True

        # Write restored spec
        path = self.storage.write_spec(backup_spec, spec_id)

        return {
            "success": True,
            "restored_from": backup_timestamp,
            "current_backed_up": current_backed_up,
            "path": str(path),
        }

    # === Context Extraction Handlers ===

    def _get_function_context(self, args: dict) -> dict:
        """Get minimal context needed to implement a function"""
        function_name = args["function_name"]

        # Load spec from various sources
        spec = args.get("spec")
        spec_path = args.get("spec_path")
        spec_id = args.get("spec_id")

        if spec is None:
            if spec_path:
                spec = self._load_spec(None, spec_path)
            elif spec_id:
                spec = self.storage.read_spec(spec_id)
                if spec is None:
                    return {"error": f"Spec not found: {spec_id}"}
            else:
                return {"error": "One of spec, spec_path, or spec_id is required"}

        # Check if function exists
        functions = spec.get("functions", {})
        if function_name not in functions:
            return {
                "error": f"Function not found: {function_name}",
                "available_functions": list(functions.keys())
            }

        # Build dependency graph and get slice
        graph = DependencyGraph()
        graph.build_from_spec(spec)
        slice_info = graph.get_slice(function_name)

        if "error" in slice_info:
            return slice_info

        # Extract full definitions for each referenced item
        result = {
            "function": function_name,
            "function_def": functions[function_name],
            "entities": {},
            "derived": {},
            "scenarios": {},
            "invariants": []
        }

        # Get entity definitions
        state = spec.get("state", {})
        for entity_name in slice_info.get("entities", []):
            if entity_name in state:
                result["entities"][entity_name] = state[entity_name]

        # Get derived definitions
        derived = spec.get("derived", {})
        for derived_name in slice_info.get("derived", []):
            if derived_name in derived:
                result["derived"][derived_name] = derived[derived_name]

        # Get scenario definitions
        scenarios = spec.get("scenarios", {})
        for scenario_id in slice_info.get("scenarios", []):
            if scenario_id in scenarios:
                result["scenarios"][scenario_id] = scenarios[scenario_id]

        # Get invariant definitions
        invariants = spec.get("invariants", [])
        invariant_ids = set(slice_info.get("invariants", []))
        for inv in invariants:
            if inv.get("id") in invariant_ids:
                result["invariants"].append(inv)

        # Add summary counts
        result["summary"] = {
            "entity_count": len(result["entities"]),
            "derived_count": len(result["derived"]),
            "scenario_count": len(result["scenarios"]),
            "invariant_count": len(result["invariants"])
        }

        return result

    # === Test Generation Handlers ===

    def _generate_tests(self, args: dict) -> dict:
        """Generate test code from TRIR specification scenarios"""
        # Load spec from various sources
        spec = args.get("spec")
        spec_path = args.get("spec_path")
        spec_id = args.get("spec_id")

        if spec is None:
            if spec_path:
                spec = self._load_spec(None, spec_path)
            elif spec_id:
                spec = self.storage.read_spec(spec_id)
                if spec is None:
                    return {"error": f"Spec not found: {spec_id}"}
            else:
                return {"error": "One of spec, spec_path, or spec_id is required"}

        framework = args.get("framework", "pytest")
        function_name = args.get("function_name")

        # Select generator
        is_unit_test = framework.endswith("-ut")

        if framework == "pytest":
            generator = PytestGenerator(spec)
            file_ext = "py"
            file_name = "test_generated.py"
            test_type = "acceptance"
        elif framework == "pytest-ut":
            generator = PytestUnitGenerator(spec)
            file_ext = "py"
            file_name = "test_unit_generated.py"
            test_type = "unit"
        elif framework == "jest":
            generator = JestGenerator(spec, typescript=False)
            file_ext = "js"
            file_name = "generated.test.js"
            test_type = "acceptance"
        elif framework == "jest-ts":
            generator = JestGenerator(spec, typescript=True)
            file_ext = "ts"
            file_name = "generated.test.ts"
            test_type = "acceptance"
        elif framework == "jest-ut":
            generator = UnitTestGenerator(spec, typescript=False)
            file_ext = "js"
            file_name = "generated.unit.test.js"
            test_type = "unit"
        elif framework == "jest-ts-ut":
            generator = UnitTestGenerator(spec, typescript=True)
            file_ext = "ts"
            file_name = "generated.unit.test.ts"
            test_type = "unit"
        else:
            return {
                "error": f"Unknown framework: {framework}",
                "supported_frameworks": ["pytest", "pytest-ut", "jest", "jest-ts", "jest-ut", "jest-ts-ut"]
            }

        # Generate tests
        if function_name:
            # Check if function exists
            functions = spec.get("functions", {})
            if function_name not in functions:
                return {
                    "error": f"Function not found: {function_name}",
                    "available_functions": list(functions.keys())
                }
            code = generator.generate_for_function(function_name)
            file_name = f"test_{function_name}.{file_ext}" if framework == "pytest" else f"{function_name}.test.{file_ext}"
        else:
            code = generator.generate_all()

        # Count generated tests
        scenarios = spec.get("scenarios", {})
        invariants = spec.get("invariants", [])

        if function_name:
            # Count only relevant scenarios
            relevant_count = sum(
                1 for s in scenarios.values()
                if s.get("when", {}).get("call") == function_name
            )
            test_count = relevant_count
        else:
            test_count = len(scenarios) + len(invariants)

        return {
            "success": True,
            "framework": framework,
            "test_type": test_type,
            "code": code,
            "suggested_filename": file_name,
            "stats": {
                "scenario_tests": len(scenarios) if not function_name else relevant_count,
                "invariant_tests": len(invariants) if not function_name else 0,
                "total_tests": test_count
            }
        }

    def _generate_task_package(self, args: dict) -> dict:
        """Generate a complete implementation task package"""
        # Load spec from various sources
        spec = args.get("spec")
        spec_path = args.get("spec_path")
        spec_id = args.get("spec_id")

        if spec is None:
            if spec_path:
                spec = self._load_spec(None, spec_path)
            elif spec_id:
                spec = self.storage.read_spec(spec_id)
                if spec is None:
                    return {"error": f"Spec not found: {spec_id}"}
            else:
                return {"error": "One of spec, spec_path, or spec_id is required"}

        function_name = args.get("function_name")
        if not function_name:
            return {"error": "function_name is required"}

        language = args.get("language", "python")
        output_dir = args.get("output_dir", ".")

        # Create generator
        generator = TaskPackageGenerator(spec, base_dir=output_dir)

        # Generate for all or single function
        if function_name == "all":
            results = generator.generate_all_task_packages(language)
            return {
                "success": True,
                "generated_count": len(results),
                "tasks": [
                    {
                        "function": r.task_dir.split("/")[-1],
                        "task_dir": r.task_dir,
                        "files_count": len(r.files_created),
                        "related_functions": r.related_functions
                    }
                    for r in results
                ],
                "tests_dir": str(generator.tests_dir)
            }
        else:
            result = generator.generate_task_package(function_name, language)

            if not result.success:
                return {"error": result.error}

            return {
                "success": True,
                "function": function_name,
                "task_dir": result.task_dir,
                "tests_dir": result.tests_dir,
                "files_created": result.files_created,
                "related_functions": result.related_functions,
                "run_tests_command": f"cd {result.task_dir} && pytest" if language == "python" else f"cd {result.task_dir} && npx jest"
            }

    def _sync_after_change(self, args: dict) -> dict:
        """Sync task packages after spec changes - regenerate only affected items"""
        # Load spec
        spec = args.get("spec")
        spec_path = args.get("spec_path")
        spec_id = args.get("spec_id")

        if spec is None:
            if spec_path:
                spec = self._load_spec(None, spec_path)
            elif spec_id:
                spec = self.storage.read_spec(spec_id)
                if spec is None:
                    return {"error": f"Spec not found: {spec_id}"}
            else:
                return {"error": "One of spec, spec_path, or spec_id is required"}

        changes = args.get("changes", [])
        if not changes:
            return {"error": "changes is required (JSON Patch format)"}

        language = args.get("language", "python")
        output_dir = args.get("output_dir", ".")

        # Parse changes to find affected elements directly
        affected_entities = set()
        affected_functions_direct = set()
        affected_scenarios = set()
        affected_derived = set()
        affected_invariants = set()

        for change in changes:
            path = change.get("path", "")
            parts = path.strip("/").split("/")

            if len(parts) >= 2:
                section = parts[0]
                name = parts[1]

                if section == "state":
                    affected_entities.add(name)
                elif section == "functions":
                    affected_functions_direct.add(name)
                elif section == "scenarios":
                    affected_scenarios.add(name)
                elif section == "derived":
                    affected_derived.add(name)
                elif section == "invariants":
                    # invariants is an array, need to handle differently
                    pass

        # Collect all affected functions
        affected_functions = set(affected_functions_direct)

        # Functions that use affected entities
        for func_name, func_def in spec.get("functions", {}).items():
            # Check preconditions
            for pre in func_def.get("pre", []):
                if self._expr_uses_entities(pre.get("check", {}), affected_entities):
                    affected_functions.add(func_name)
            # Check post-actions
            for post in func_def.get("post", []):
                action = post.get("action", {})
                for action_type in ["create", "update", "delete"]:
                    if action.get(action_type) in affected_entities:
                        affected_functions.add(func_name)
            # Check input types that reference entities
            for input_name, input_def in func_def.get("input", {}).items():
                input_type = input_def.get("type", {})
                if isinstance(input_type, dict) and input_type.get("ref") in affected_entities:
                    affected_functions.add(func_name)

        # Functions whose scenarios are affected
        for scenario_id, scenario in spec.get("scenarios", {}).items():
            if scenario_id in affected_scenarios:
                func_name = scenario.get("when", {}).get("call")
                if func_name:
                    affected_functions.add(func_name)
            # Also check if scenario uses affected entities in given
            for entity_name in scenario.get("given", {}).keys():
                if entity_name in affected_entities:
                    func_name = scenario.get("when", {}).get("call")
                    if func_name:
                        affected_functions.add(func_name)

        # Functions that use affected derived values
        for func_name, func_def in spec.get("functions", {}).items():
            for pre in func_def.get("pre", []):
                if self._expr_uses_derived(pre.get("check", {}), affected_derived):
                    affected_functions.add(func_name)

        if not affected_functions:
            return {
                "success": True,
                "message": "No functions affected by changes",
                "updated_functions": [],
                "updated_tests": [],
                "updated_task_packages": []
            }

        # Create generator and regenerate affected packages
        generator = TaskPackageGenerator(spec, base_dir=output_dir)

        updated_tests = []
        updated_task_packages = []

        for func_name in affected_functions:
            result = generator.generate_task_package(func_name, language, write_files=True)
            if result.success:
                updated_task_packages.append(func_name)
                # Extract test file names from files_created
                for f in result.files_created:
                    if "/tests/" in f:
                        updated_tests.append(f.split("/")[-1])

        # Remove duplicates from test list
        updated_tests = list(set(updated_tests))

        return {
            "success": True,
            "changes_analyzed": len(changes),
            "impact_summary": {
                "affected_entities": list(affected_entities),
                "affected_functions": list(affected_functions),
                "affected_scenarios": list(affected_scenarios),
                "affected_derived": list(affected_derived)
            },
            "updated_functions": list(affected_functions),
            "updated_tests": updated_tests,
            "updated_task_packages": updated_task_packages,
            "unchanged_functions": [
                f for f in spec.get("functions", {}).keys()
                if f not in affected_functions
            ]
        }

    # === Task Management Handlers ===

    def _activate_task(self, args: dict) -> dict:
        """Activate a task for implementation"""
        function_name = args.get("function_name")
        if not function_name:
            return {"error": "function_name is required"}

        language = args.get("language", "python")
        output_dir = args.get("output_dir", ".")

        manager = TaskManager(Path(output_dir))
        return manager.activate_task(function_name, language)

    def _deactivate_task(self, args: dict) -> dict:
        """Deactivate a task without completing it"""
        function_name = args.get("function_name")
        if not function_name:
            return {"error": "function_name is required"}

        cleanup_worktree = args.get("cleanup_worktree", False)
        output_dir = args.get("output_dir", ".")

        manager = TaskManager(Path(output_dir))
        return manager.deactivate_task(function_name, cleanup_worktree=cleanup_worktree)

    def _complete_task(self, args: dict) -> dict:
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

    def _get_task_status(self, args: dict) -> dict:
        """Get status of tasks"""
        function_name = args.get("function_name")
        output_dir = args.get("output_dir", ".")

        manager = TaskManager(Path(output_dir))
        return manager.get_task_status(function_name)

    def _check_edit_permission(self, args: dict) -> dict:
        """Check if a file can be edited"""
        file_path = args.get("file_path")
        if not file_path:
            return {"error": "file_path is required"}

        output_dir = args.get("output_dir", ".")

        manager = TaskManager(Path(output_dir))
        return manager.check_edit_permission(file_path)

    def _get_test_command(self, args: dict) -> dict:
        """Get the command to run tests for a task"""
        function_name = args.get("function_name")
        if not function_name:
            return {"error": "function_name is required"}

        output_dir = args.get("output_dir", ".")

        manager = TaskManager(Path(output_dir))
        return manager.get_test_command(function_name)

    # === Project Configuration Handlers ===

    def _init_project(self, args: dict) -> dict:
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

    def _get_project_config(self, args: dict) -> dict:
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

    # === Helper Methods ===

    def _expr_uses_entities(self, expr: dict, entities: set) -> bool:
        """Check if expression references any of the given entities"""
        if not isinstance(expr, dict):
            return False

        if expr.get("type") == "ref":
            path = expr.get("path", "")
            if "." in path:
                entity = path.split(".")[0]
                if entity in entities:
                    return True

        # Recurse
        for key in ["left", "right", "expr", "cond", "then", "else"]:
            if key in expr and self._expr_uses_entities(expr[key], entities):
                return True

        return False

    def _expr_uses_derived(self, expr: dict, derived_names: set) -> bool:
        """Check if expression references any of the given derived values"""
        if not isinstance(expr, dict):
            return False

        if expr.get("type") == "call":
            if expr.get("name") in derived_names:
                return True

        # Recurse
        for key in ["left", "right", "expr", "cond", "then", "else"]:
            if key in expr and self._expr_uses_derived(expr[key], derived_names):
                return True

        return False


# MCP Server setup (when run as main)
def create_mcp_server():
    """Create and configure MCP server"""
    if not HAS_MCP:
        raise ImportError("mcp package is required: pip install mcp")

    server = Server("the_mesh")
    mesh = MeshServer()

    @server.list_tools()
    async def list_tools():
        return [
            Tool(
                name=tool["name"],
                description=tool["description"],
                inputSchema=tool["inputSchema"]
            )
            for tool in mesh.get_tools()
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict):
        result = mesh.call_tool(name, arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    return server


async def main():
    """Run the MCP server"""
    server = create_mcp_server()
    options = InitializationOptions(
        server_name="the_mesh",
        server_version="0.1.0",
        capabilities=ServerCapabilities(tools={})
    )
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, options)


def main_sync():
    """Synchronous entry point for CLI"""
    import asyncio
    asyncio.run(main())


if __name__ == "__main__":
    main_sync()
