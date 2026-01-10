#!/usr/bin/env python3
"""
Claude Code Hook: File Edit Permission Checker

This hook runs before Edit/Write tool calls to enforce task-based editing restrictions.
Only impl files of active tasks can be edited.

Usage in .claude/settings.json:
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"$CLAUDE_PROJECT_DIR\"/hooks/check_permission.py"
          }
        ]
      }
    ]
  }
}
"""

import json
import os
import sys
from pathlib import Path

# Add parent directory to path for imports

from the_mesh.core.task import TaskManager


def main():
    # Read hook input from stdin
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        # If no JSON input, allow the operation (might be a test)
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    # Only check Edit and Write operations
    if tool_name not in ["Edit", "Write"]:
        sys.exit(0)

    if not file_path:
        sys.exit(0)

    # Get project directory from environment or use current working directory
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", input_data.get("cwd", "."))

    # Initialize TaskManager
    manager = TaskManager(Path(project_dir))

    # Check permission
    result = manager.check_edit_permission(file_path)

    if result.get("allowed", True):
        # Allow the edit
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason": result.get("reason", "Edit allowed")
            }
        }
        print(json.dumps(output))
        sys.exit(0)
    else:
        # Deny the edit with explanation
        reason = result.get("reason", "Edit not allowed")
        hint = result.get("hint", "")
        task = result.get("task", "")

        message = f"[BLOCKED] {reason}"
        if task:
            message += f" (task: {task})"
        if hint:
            message += f"\n{hint}"

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
