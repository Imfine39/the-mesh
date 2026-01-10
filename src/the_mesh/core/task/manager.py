"""Task management for implementation workflow."""

import json
from datetime import datetime
from pathlib import Path

from the_mesh.config.project import ProjectConfig
from the_mesh.hooks.git_worktree import (
    get_branch_name,
    create_worktree,
    remove_worktree,
    commit_and_push,
    create_pull_request,
)


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
