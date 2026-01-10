#!/usr/bin/env python3
"""TRIR Spec CRUD operations

Usage:
    python mesh_spec.py list                          # List all specs
    python mesh_spec.py read <spec_id>                # Read full spec
    python mesh_spec.py read <spec_id> --section state.Order
    python mesh_spec.py write <spec_id> < spec.json   # Write spec from stdin
    python mesh_spec.py write <spec_id> --file spec.json
    python mesh_spec.py delete <spec_id>              # Delete spec
    python mesh_spec.py update <spec_id> --section state.Order < order.json
    python mesh_spec.py backups <spec_id>             # List backups
    python mesh_spec.py restore <spec_id> <backup>    # Restore backup
"""
import sys
import json
import argparse

from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent / "src"))

from the_mesh.core.storage.spec_storage import SpecStorage


def main():
    parser = argparse.ArgumentParser(description="TRIR Spec CRUD operations")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # list
    subparsers.add_parser("list", help="List all specs")

    # read
    read_parser = subparsers.add_parser("read", help="Read spec")
    read_parser.add_argument("spec_id")
    read_parser.add_argument("--section", "-s", help="Specific section (e.g., state.Order)")

    # write
    write_parser = subparsers.add_parser("write", help="Write spec")
    write_parser.add_argument("spec_id")
    write_parser.add_argument("--file", "-f", help="Read from file instead of stdin")

    # delete
    delete_parser = subparsers.add_parser("delete", help="Delete spec")
    delete_parser.add_argument("spec_id")

    # update
    update_parser = subparsers.add_parser("update", help="Update spec section")
    update_parser.add_argument("spec_id")
    update_parser.add_argument("--section", "-s", required=True, help="Section path")
    update_parser.add_argument("--file", "-f", help="Read from file instead of stdin")

    # backups
    backup_parser = subparsers.add_parser("backups", help="List backups")
    backup_parser.add_argument("spec_id")

    # restore
    restore_parser = subparsers.add_parser("restore", help="Restore backup")
    restore_parser.add_argument("spec_id")
    restore_parser.add_argument("backup", help="Backup filename")

    args = parser.parse_args()
    storage = SpecStorage()

    if args.command == "list":
        specs = storage.list_specs()
        if not specs:
            print("No specs found")
        else:
            for s in specs:
                print(f"  {s['id']}")
                if s.get("meta"):
                    meta = s["meta"]
                    if meta.get("title"):
                        print(f"    Title: {meta['title']}")

    elif args.command == "read":
        spec = storage.read_spec(args.spec_id)
        if spec is None:
            print(f"Error: Spec '{args.spec_id}' not found", file=sys.stderr)
            sys.exit(1)

        if args.section:
            # Navigate to section
            parts = args.section.split(".")
            data = spec
            for part in parts:
                if isinstance(data, dict) and part in data:
                    data = data[part]
                else:
                    print(f"Error: Section '{args.section}' not found", file=sys.stderr)
                    sys.exit(1)
            print(json.dumps(data, indent=2))
        else:
            print(json.dumps(spec, indent=2))

    elif args.command == "write":
        if args.file:
            with open(args.file) as f:
                spec = json.load(f)
        else:
            spec = json.load(sys.stdin)

        storage.write_spec(args.spec_id, spec)
        print(f"Spec '{args.spec_id}' written")

    elif args.command == "delete":
        success = storage.delete_spec(args.spec_id)
        if success:
            print(f"Spec '{args.spec_id}' deleted")
        else:
            print(f"Error: Spec '{args.spec_id}' not found", file=sys.stderr)
            sys.exit(1)

    elif args.command == "update":
        spec = storage.read_spec(args.spec_id)
        if spec is None:
            print(f"Error: Spec '{args.spec_id}' not found", file=sys.stderr)
            sys.exit(1)

        if args.file:
            with open(args.file) as f:
                section_data = json.load(f)
        else:
            section_data = json.load(sys.stdin)

        # Navigate and update section
        parts = args.section.split(".")
        target = spec
        for part in parts[:-1]:
            if part not in target:
                target[part] = {}
            target = target[part]
        target[parts[-1]] = section_data

        storage.write_spec(args.spec_id, spec)
        print(f"Section '{args.section}' updated in '{args.spec_id}'")

    elif args.command == "backups":
        backups = storage.list_backups(args.spec_id)
        if not backups:
            print("No backups found")
        else:
            for b in backups:
                print(f"  {b}")

    elif args.command == "restore":
        success = storage.restore_backup(args.spec_id, args.backup)
        if success:
            print(f"Backup '{args.backup}' restored to '{args.spec_id}'")
        else:
            print(f"Error: Failed to restore backup", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
