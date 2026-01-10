#!/usr/bin/env python3
"""Validate a TRIR spec

Usage:
    python mesh_validate.py <spec_id>           # Validate stored spec
    python mesh_validate.py --stdin             # Validate from stdin
    python mesh_validate.py --file <path>       # Validate from file

Exit codes:
    0: Valid (may have warnings)
    1: Invalid (has errors)
"""
import sys
import json
import argparse

# Add lib directory to path
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from core.validator import MeshValidator
from core.storage.spec_storage import SpecStorage


def main():
    parser = argparse.ArgumentParser(description="Validate a TRIR spec")
    parser.add_argument("spec_id", nargs="?", help="Spec ID to validate")
    parser.add_argument("--stdin", action="store_true", help="Read spec from stdin")
    parser.add_argument("--file", "-f", help="Read spec from file")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    storage = SpecStorage()
    validator = MeshValidator()

    # Load spec
    if args.stdin:
        spec = json.load(sys.stdin)
    elif args.file:
        with open(args.file) as f:
            spec = json.load(f)
    elif args.spec_id:
        spec = storage.read_spec(args.spec_id)
        if spec is None:
            print(f"Error: Spec '{args.spec_id}' not found", file=sys.stderr)
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)

    # Validate
    result = validator.validate(spec)

    # Output
    if args.json:
        output = {
            "valid": result.valid,
            "errors": [{"code": e.code, "path": e.path, "message": e.message} for e in result.errors],
            "warnings": [{"code": w.code, "path": w.path, "message": w.message} for w in result.warnings],
        }
        print(json.dumps(output, indent=2))
    else:
        print(f"Valid: {result.valid}")
        print(f"Errors: {len(result.errors)}")
        print(f"Warnings: {len(result.warnings)}")

        for e in result.errors:
            print(f"  ERROR {e.code}: {e.path}")
            print(f"        {e.message}")

        for w in result.warnings:
            print(f"  WARN  {w.code}: {w.path}")
            print(f"        {w.message}")

    sys.exit(0 if result.valid else 1)


if __name__ == "__main__":
    main()
