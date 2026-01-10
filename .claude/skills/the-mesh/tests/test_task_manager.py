"""Tests for TaskManager"""

import json
import tempfile
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.task import TaskManager


def test_activate_task_no_folder():
    """Test activating a task when folder doesn't exist"""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = TaskManager(Path(tmpdir))
        result = manager.activate_task("nonexistent_function")

        assert result["success"] is False
        assert "not found" in result["error"].lower()


def test_activate_task_success():
    """Test successfully activating a task"""
    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)

        # Create task folder
        task_dir = base_dir / "tasks" / "my_function"
        task_dir.mkdir(parents=True)

        manager = TaskManager(base_dir)
        result = manager.activate_task("my_function", "python")

        assert result["success"] is True
        assert result["function"] == "my_function"
        assert "activated_at" in result

        # Verify state file was created
        state_file = base_dir / ".mesh" / "state.json"
        assert state_file.exists()

        with open(state_file) as f:
            state = json.load(f)

        assert "my_function" in state["active_tasks"]
        assert state["active_tasks"]["my_function"]["language"] == "python"


def test_activate_task_already_active():
    """Test activating an already active task"""
    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)
        task_dir = base_dir / "tasks" / "my_function"
        task_dir.mkdir(parents=True)

        manager = TaskManager(base_dir)

        # Activate first time
        result1 = manager.activate_task("my_function")
        assert result1["success"] is True

        # Activate second time
        result2 = manager.activate_task("my_function")
        assert result2["success"] is True
        assert "already active" in result2.get("message", "").lower()


def test_deactivate_task():
    """Test deactivating a task"""
    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)
        task_dir = base_dir / "tasks" / "my_function"
        task_dir.mkdir(parents=True)

        manager = TaskManager(base_dir)

        # Activate first
        manager.activate_task("my_function")

        # Deactivate
        result = manager.deactivate_task("my_function")
        assert result["success"] is True

        # Verify it's no longer active
        status = manager.get_task_status("my_function")
        assert status["status"] == "pending"


def test_deactivate_inactive_task():
    """Test deactivating a task that's not active"""
    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)
        task_dir = base_dir / "tasks" / "my_function"
        task_dir.mkdir(parents=True)

        manager = TaskManager(base_dir)
        result = manager.deactivate_task("my_function")

        assert result["success"] is False
        assert "not active" in result["error"].lower()


def test_complete_task_success():
    """Test completing a task successfully"""
    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)
        task_dir = base_dir / "tasks" / "my_function"
        task_dir.mkdir(parents=True)

        manager = TaskManager(base_dir)

        # Activate first
        manager.activate_task("my_function")

        # Complete with passing tests
        result = manager.complete_task("my_function", {"passed": ["test1", "test2"], "failed": []})

        assert result["success"] is True
        assert "completed_at" in result

        # Verify it's now completed
        status = manager.get_task_status("my_function")
        assert status["status"] == "completed"


def test_complete_task_with_failures():
    """Test completing a task with failing tests"""
    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)
        task_dir = base_dir / "tasks" / "my_function"
        task_dir.mkdir(parents=True)

        manager = TaskManager(base_dir)

        # Activate first
        manager.activate_task("my_function")

        # Try to complete with failing tests
        result = manager.complete_task("my_function", {"passed": ["test1"], "failed": ["test2"]})

        assert result["success"] is False
        assert "test" in result["error"].lower()
        assert "test2" in result["failed_tests"]

        # Verify it's still active
        status = manager.get_task_status("my_function")
        assert status["status"] == "active"


def test_complete_inactive_task():
    """Test completing a task that's not active"""
    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)
        task_dir = base_dir / "tasks" / "my_function"
        task_dir.mkdir(parents=True)

        manager = TaskManager(base_dir)
        result = manager.complete_task("my_function")

        assert result["success"] is False
        assert "not active" in result["error"].lower()


def test_get_task_status_all():
    """Test getting status of all tasks"""
    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)

        # Create multiple task folders
        for name in ["func_a", "func_b", "func_c"]:
            (base_dir / "tasks" / name).mkdir(parents=True)

        manager = TaskManager(base_dir)

        # Activate one, complete one
        manager.activate_task("func_a")
        manager.activate_task("func_b")
        manager.complete_task("func_b")

        status = manager.get_task_status()

        assert status["active_count"] == 1
        assert status["completed_count"] == 1
        assert status["pending_count"] == 1

        tasks = {t["function"]: t["status"] for t in status["tasks"]}
        assert tasks["func_a"] == "active"
        assert tasks["func_b"] == "completed"
        assert tasks["func_c"] == "pending"


def test_check_edit_permission_active_task():
    """Test edit permission for active task's impl file in src/"""
    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)
        task_dir = base_dir / "tasks" / "my_function"
        task_dir.mkdir(parents=True)
        src_dir = base_dir / "src"
        src_dir.mkdir(parents=True)

        manager = TaskManager(base_dir)
        manager.activate_task("my_function")

        # New design: impl file is in src/
        impl_file = src_dir / "my_function.py"
        result = manager.check_edit_permission(str(impl_file))

        assert result["allowed"] is True
        assert result["task"] == "my_function"


def test_check_edit_permission_inactive_task():
    """Test edit permission for inactive task's impl file in src/"""
    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)
        task_dir = base_dir / "tasks" / "my_function"
        task_dir.mkdir(parents=True)
        src_dir = base_dir / "src"
        src_dir.mkdir(parents=True)

        manager = TaskManager(base_dir)
        # Don't activate the task

        # New design: impl file is in src/
        impl_file = src_dir / "my_function.py"
        result = manager.check_edit_permission(str(impl_file))

        assert result["allowed"] is False
        assert "not active" in result["reason"].lower()
        assert "hint" in result


def test_check_edit_permission_task_folder_file():
    """Test edit permission for files in task folder (read-only)"""
    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)
        task_dir = base_dir / "tasks" / "my_function"
        task_dir.mkdir(parents=True)

        manager = TaskManager(base_dir)
        manager.activate_task("my_function")

        # Try to edit TASK.md (read-only)
        task_md = task_dir / "TASK.md"
        result = manager.check_edit_permission(str(task_md))

        assert result["allowed"] is False
        assert "read-only" in result["reason"].lower()


def test_check_edit_permission_test_file():
    """Test edit permission for test file"""
    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)
        tests_dir = base_dir / ".mesh" / "tests" / "at"
        tests_dir.mkdir(parents=True)

        manager = TaskManager(base_dir)

        test_file = tests_dir / "test_func_at.py"
        result = manager.check_edit_permission(str(test_file))

        assert result["allowed"] is False
        assert "auto-generated" in result["reason"].lower()


def test_check_edit_permission_other_file():
    """Test edit permission for files outside task system"""
    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)

        manager = TaskManager(base_dir)

        other_file = base_dir / "some_other_file.py"
        result = manager.check_edit_permission(str(other_file))

        assert result["allowed"] is True
        assert "not managed" in result["reason"].lower()


def test_get_test_command_python():
    """Test getting test command for Python task"""
    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)
        task_dir = base_dir / "tasks" / "my_function"
        task_dir.mkdir(parents=True)

        manager = TaskManager(base_dir)
        manager.activate_task("my_function", "python")

        result = manager.get_test_command("my_function")

        assert result["command"] == "pytest"
        assert "pytest.ini" in result["config_file"]


def test_get_test_command_typescript():
    """Test getting test command for TypeScript task"""
    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)
        task_dir = base_dir / "tasks" / "my_function"
        task_dir.mkdir(parents=True)

        manager = TaskManager(base_dir)
        manager.activate_task("my_function", "typescript")

        result = manager.get_test_command("my_function")

        assert result["command"] == "npx jest"
        assert "jest.config.json" in result["config_file"]


def test_reactivate_completed_task():
    """Test reactivating a completed task"""
    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)
        task_dir = base_dir / "tasks" / "my_function"
        task_dir.mkdir(parents=True)

        manager = TaskManager(base_dir)

        # Activate and complete
        manager.activate_task("my_function")
        manager.complete_task("my_function")

        # Reactivate
        result = manager.activate_task("my_function")

        assert result["success"] is True

        # Verify it's now active again (not completed)
        status = manager.get_task_status("my_function")
        assert status["status"] == "active"


# Run tests if executed directly
if __name__ == "__main__":
    import traceback

    tests = [
        test_activate_task_no_folder,
        test_activate_task_success,
        test_activate_task_already_active,
        test_deactivate_task,
        test_deactivate_inactive_task,
        test_complete_task_success,
        test_complete_task_with_failures,
        test_complete_inactive_task,
        test_get_task_status_all,
        test_check_edit_permission_active_task,
        test_check_edit_permission_inactive_task,
        test_check_edit_permission_task_folder_file,
        test_check_edit_permission_test_file,
        test_check_edit_permission_other_file,
        test_get_test_command_python,
        test_get_test_command_typescript,
        test_reactivate_completed_task,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            print(f"PASSED: {test.__name__}")
            passed += 1
        except Exception as e:
            print(f"FAILED: {test.__name__}")
            traceback.print_exc()
            failed += 1

    print(f"\nResults: {passed} passed, {failed} failed")
