#!/usr/bin/env python3
"""
Claude Code Hook: Post Activate Task

This hook runs after activate_task tool call to display task information.
Shows TASK.md content and worktree information to help the user get started.

Usage in .claude/settings.json:
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "mcp__the_mesh__activate_task",
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"$CLAUDE_PROJECT_DIR\"/hooks/post_activate.py"
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


def main():
    # Read hook input from stdin
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    tool_result = input_data.get("tool_result", {})

    # Only process activate_task results
    if "activate_task" not in tool_name:
        sys.exit(0)

    # Parse tool result if it's a string
    if isinstance(tool_result, str):
        try:
            tool_result = json.loads(tool_result)
        except json.JSONDecodeError:
            sys.exit(0)

    # Check if activation was successful
    if not tool_result.get("success"):
        sys.exit(0)

    function_name = tool_result.get("function", "")
    task_dir = tool_result.get("task_dir", "")
    worktree_path = tool_result.get("worktree_path")
    branch = tool_result.get("branch")
    impl_path = tool_result.get("impl_path")

    # Build information message
    info_lines = [
        "",
        "=" * 60,
        f"Task Activated: {function_name}",
        "=" * 60,
        "",
    ]

    # Add worktree info if available
    if worktree_path:
        info_lines.extend([
            f"Worktree: {worktree_path}",
            f"Branch: {branch}",
            "",
        ])

    if impl_path:
        info_lines.append(f"Implementation file: {impl_path}")
        info_lines.append("")

    # Try to read and display TASK.md
    if task_dir:
        task_md_path = Path(task_dir) / "TASK.md"
        if task_md_path.exists():
            info_lines.extend([
                "-" * 60,
                "TASK.md:",
                "-" * 60,
            ])
            try:
                content = task_md_path.read_text()
                # Limit to first 50 lines to avoid overwhelming output
                lines = content.split('\n')[:50]
                info_lines.extend(lines)
                if len(content.split('\n')) > 50:
                    info_lines.append("... (truncated)")
            except Exception:
                info_lines.append("(Could not read TASK.md)")

    info_lines.extend([
        "",
        "-" * 60,
        "Next steps:",
        f"  1. Implement the function in {impl_path or 'src/'}",
        "  2. Run tests with: pytest (or npx jest)",
        "  3. Complete with: complete_task(function_name='{}')",
        "-" * 60,
        "",
    ])

    # Output to stderr (stdout is for hook-specific JSON output)
    for line in info_lines:
        print(line, file=sys.stderr)

    # Return empty output (no hook-specific modifications)
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse"
        }
    }
    print(json.dumps(output))
    sys.exit(0)


if __name__ == "__main__":
    main()
