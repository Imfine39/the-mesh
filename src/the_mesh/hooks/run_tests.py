#!/usr/bin/env python3
"""
Claude Code Hook: Run Tests Before Complete

This hook runs before complete_task tool call to verify all tests pass.
If tests fail, the task completion is blocked.

Usage in .claude/settings.json:
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "mcp__the_mesh__complete_task",
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"$CLAUDE_PROJECT_DIR\"/hooks/run_tests.py"
          }
        ]
      }
    ]
  }
}
"""

import json
import os
import subprocess
import sys
from pathlib import Path

# Add parent directory to path for imports

from the_mesh.core.task import TaskManager


def run_pytest(task_dir: Path) -> dict:
    """Run pytest and return results"""
    try:
        result = subprocess.run(
            ["pytest", "-v", "--tb=short", "-q"],
            cwd=task_dir,
            capture_output=True,
            text=True,
            timeout=120
        )

        # Parse output for pass/fail counts
        output = result.stdout + result.stderr
        passed = []
        failed = []

        for line in output.split('\n'):
            if '::' in line:
                if 'PASSED' in line:
                    test_name = line.split('::')[1].split()[0]
                    passed.append(test_name)
                elif 'FAILED' in line:
                    test_name = line.split('::')[1].split()[0]
                    failed.append(test_name)

        return {
            "success": result.returncode == 0,
            "passed": passed,
            "failed": failed,
            "output": output[-2000:] if len(output) > 2000 else output,
            "returncode": result.returncode
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "Tests timed out after 120 seconds",
            "passed": [],
            "failed": []
        }
    except FileNotFoundError:
        return {
            "success": False,
            "error": "pytest not found. Install with: pip install pytest",
            "passed": [],
            "failed": []
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "passed": [],
            "failed": []
        }


def run_jest(task_dir: Path) -> dict:
    """Run jest and return results"""
    try:
        result = subprocess.run(
            ["npx", "jest", "--verbose", "--passWithNoTests"],
            cwd=task_dir,
            capture_output=True,
            text=True,
            timeout=120
        )

        output = result.stdout + result.stderr
        passed = []
        failed = []

        # Parse Jest output
        for line in output.split('\n'):
            if '✓' in line or 'PASS' in line:
                # Extract test name
                if '✓' in line:
                    test_name = line.split('✓')[1].strip().split(' (')[0]
                    passed.append(test_name)
            elif '✕' in line or 'FAIL' in line:
                if '✕' in line:
                    test_name = line.split('✕')[1].strip().split(' (')[0]
                    failed.append(test_name)

        return {
            "success": result.returncode == 0,
            "passed": passed,
            "failed": failed,
            "output": output[-2000:] if len(output) > 2000 else output,
            "returncode": result.returncode
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "Tests timed out after 120 seconds",
            "passed": [],
            "failed": []
        }
    except FileNotFoundError:
        return {
            "success": False,
            "error": "npx/jest not found. Install with: npm install jest",
            "passed": [],
            "failed": []
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "passed": [],
            "failed": []
        }


def main():
    # Read hook input from stdin
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})

    # Only process complete_task calls
    if "complete_task" not in tool_name:
        sys.exit(0)

    function_name = tool_input.get("function_name", "")
    if not function_name:
        sys.exit(0)

    # Check if test_results already provided (skip auto-testing)
    if tool_input.get("test_results"):
        sys.exit(0)

    # Get project directory
    project_dir_path = os.environ.get("CLAUDE_PROJECT_DIR", input_data.get("cwd", "."))
    manager = TaskManager(Path(project_dir_path))

    # Check if task exists and is active
    state = manager.load_state()
    if function_name not in state.get("active_tasks", {}):
        sys.exit(0)

    task_info = state["active_tasks"][function_name]
    task_dir = manager.get_task_dir(function_name)

    # Determine test framework
    language = task_info.get("language", "python")

    print(f"Running tests for {function_name}...", file=sys.stderr)

    # Run tests
    if language in ("typescript", "javascript"):
        test_result = run_jest(task_dir)
    else:
        test_result = run_pytest(task_dir)

    # Output test results
    if test_result["success"]:
        passed_count = len(test_result.get("passed", []))
        print(f"All tests passed ({passed_count} tests)", file=sys.stderr)

        # Allow completion with test results
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason": f"Tests passed: {passed_count} tests",
                "testResults": {
                    "passed": test_result.get("passed", []),
                    "failed": []
                }
            }
        }
        print(json.dumps(output))
        sys.exit(0)
    else:
        failed = test_result.get("failed", [])
        error = test_result.get("error", "")

        message = "[BLOCKED] Tests must pass before completing task.\n"
        if failed:
            message += f"Failed tests ({len(failed)}):\n"
            for t in failed[:10]:
                message += f"  - {t}\n"
            if len(failed) > 10:
                message += f"  ... and {len(failed) - 10} more\n"
        if error:
            message += f"\nError: {error}\n"

        message += "\nFix the failing tests, then try complete_task again."

        # Show test output snippet
        output_snippet = test_result.get("output", "")
        if output_snippet:
            print("\nTest output:", file=sys.stderr)
            print(output_snippet[-1000:], file=sys.stderr)

        output = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": message
            }
        }
        print(json.dumps(output))
        sys.exit(0)


if __name__ == "__main__":
    main()
