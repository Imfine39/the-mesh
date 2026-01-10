#!/usr/bin/env python3
"""Task management operations

Usage:
    python mesh_task.py status                    # Get current task status
    python mesh_task.py activate <spec_id> <fn>   # Activate task for function
    python mesh_task.py deactivate                # Deactivate current task
    python mesh_task.py complete                  # Complete current task
    python mesh_task.py check-edit <file>         # Check if edit is allowed
    python mesh_task.py test-command              # Get test command for task
"""
import sys
import argparse

# Add lib directory to path
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from core.task.manager import TaskManager
from core.storage.spec_storage import SpecStorage


def main():
    parser = argparse.ArgumentParser(description="Task management operations")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # status
    subparsers.add_parser("status", help="Get current task status")

    # activate
    activate_parser = subparsers.add_parser("activate", help="Activate task")
    activate_parser.add_argument("spec_id")
    activate_parser.add_argument("function_name")

    # deactivate
    subparsers.add_parser("deactivate", help="Deactivate current task")

    # complete
    subparsers.add_parser("complete", help="Complete current task")

    # check-edit
    check_parser = subparsers.add_parser("check-edit", help="Check if edit is allowed")
    check_parser.add_argument("file_path")

    # test-command
    subparsers.add_parser("test-command", help="Get test command for task")

    args = parser.parse_args()

    task_manager = TaskManager()
    storage = SpecStorage()

    if args.command == "status":
        status = task_manager.get_status()
        if not status.get("active"):
            print("No active task")
        else:
            print(f"Active Task:")
            print(f"  Spec: {status.get('spec_id')}")
            print(f"  Function: {status.get('function_name')}")
            print(f"  Branch: {status.get('branch')}")
            if status.get("allowed_files"):
                print(f"  Allowed files:")
                for f in status["allowed_files"][:10]:
                    print(f"    - {f}")

    elif args.command == "activate":
        spec = storage.read_spec(args.spec_id)
        if spec is None:
            print(f"Error: Spec '{args.spec_id}' not found", file=sys.stderr)
            sys.exit(1)

        result = task_manager.activate(args.spec_id, args.function_name, spec)
        if result.get("success"):
            print(f"Task activated:")
            print(f"  Branch: {result.get('branch')}")
            print(f"  Run: {result.get('test_command')}")
        else:
            print(f"Error: {result.get('error')}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "deactivate":
        result = task_manager.deactivate()
        if result.get("success"):
            print("Task deactivated")
        else:
            print(f"Error: {result.get('error')}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "complete":
        result = task_manager.complete()
        if result.get("success"):
            print(f"Task completed")
            if result.get("pr_url"):
                print(f"  PR: {result['pr_url']}")
        else:
            print(f"Error: {result.get('error')}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "check-edit":
        result = task_manager.check_edit_permission(args.file_path)
        if result.get("allowed"):
            print(f"Edit allowed: {args.file_path}")
        else:
            print(f"Edit NOT allowed: {args.file_path}")
            print(f"  Reason: {result.get('reason')}")
            sys.exit(1)

    elif args.command == "test-command":
        status = task_manager.get_status()
        if not status.get("active"):
            print("No active task", file=sys.stderr)
            sys.exit(1)
        print(status.get("test_command", "pytest"))


if __name__ == "__main__":
    main()
