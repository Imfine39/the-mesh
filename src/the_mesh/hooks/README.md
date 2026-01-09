# The Mesh Hooks for Claude Code

This directory contains hook scripts for integrating The Mesh with Claude Code.

## Available Hooks

### 1. `check_permission.py` (PreToolUse)
Enforces file edit permissions based on active tasks:
- Only impl files of active tasks can be edited
- Task folder files (TASK.md, context.json) are read-only
- Auto-generated tests are read-only

### 2. `post_activate.py` (PostToolUse)
Runs after `activate_task`:
- Displays TASK.md content
- Shows worktree/branch information
- Provides next steps guidance

### 3. `run_tests.py` (PreToolUse)
Runs before `complete_task`:
- Automatically runs pytest or jest
- Blocks completion if tests fail
- Passes test results to complete_task

### 4. `git_worktree.py` (Library)
Helper functions for git worktree management:
- `create_worktree()` - Create new worktree with branch
- `remove_worktree()` - Remove worktree
- `commit_and_push()` - Commit changes and push
- `create_pull_request()` - Create PR using gh CLI

## Configuration

Add to `.claude/settings.json`:

```json
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
      },
      {
        "matcher": "mcp__the_mesh__complete_task",
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"$CLAUDE_PROJECT_DIR\"/hooks/run_tests.py"
          }
        ]
      }
    ],
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
```

## Workflow

1. **Initialize project**: `init_project(language="python")`
2. **Generate task package**: `generate_task_package(function_name="my_function")`
3. **Activate task**: `activate_task(function_name="my_function")`
   - Creates worktree (if `auto_worktree` enabled)
   - Displays TASK.md (via hook)
4. **Implement**: Edit `src/my_function.py`
5. **Test**: Run tests manually or via hook
6. **Complete**: `complete_task(function_name="my_function")`
   - Hook runs tests automatically
   - Commits, pushes, creates PR (if configured)

## Requirements

- Python 3.10+
- pytest (for Python projects)
- jest (for TypeScript/JavaScript projects)
- gh CLI (for PR creation)
