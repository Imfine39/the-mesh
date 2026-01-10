#!/usr/bin/env python3
"""Generate tests or types from TRIR spec

Usage:
    python mesh_generate.py <spec_id> --type tests --framework pytest-ut
    python mesh_generate.py <spec_id> --type tests --framework pytest-at --function create_order
    python mesh_generate.py <spec_id> --type typescript
    python mesh_generate.py <spec_id> --type openapi
    python mesh_generate.py <spec_id> --type zod
    python mesh_generate.py <spec_id> --type task-package --function create_order

Test frameworks:
    pytest-ut       Unit tests (Python)
    pytest-at       Acceptance tests (Python)
    pytest-pc       PostCondition tests (Python)
    pytest-st       State transition tests (Python)
    jest-ut         Unit tests (TypeScript)
    jest-at         Acceptance tests (TypeScript)
    jest-pc         PostCondition tests (TypeScript)
    jest-st         State transition tests (TypeScript)
"""
import sys
import json
import argparse

from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent / "src"))

from the_mesh.core.validator import MeshValidator
from the_mesh.core.storage.spec_storage import SpecStorage


def main():
    parser = argparse.ArgumentParser(description="Generate tests or types from spec")
    parser.add_argument("spec_id", help="Spec ID to generate from")
    parser.add_argument("--type", "-t", required=True,
                        choices=["tests", "typescript", "openapi", "zod", "task-package"],
                        help="Type of generation")
    parser.add_argument("--framework", "-fw", default="pytest-ut",
                        help="Test framework (for --type tests)")
    parser.add_argument("--function", "-fn", default=None,
                        help="Specific function to generate for")
    parser.add_argument("--output", "-o", default=None,
                        help="Output file path")
    args = parser.parse_args()

    storage = SpecStorage()
    validator = MeshValidator()

    spec = storage.read_spec(args.spec_id)
    if spec is None:
        print(f"Error: Spec '{args.spec_id}' not found", file=sys.stderr)
        sys.exit(1)

    # Validate first
    result = validator.validate(spec)
    if not result.valid:
        print("Error: Spec has validation errors", file=sys.stderr)
        for e in result.errors[:5]:
            print(f"  {e.code}: {e.message}", file=sys.stderr)
        sys.exit(1)

    output = ""

    if args.type == "tests":
        output = generate_tests(spec, args.framework, args.function)
    elif args.type == "typescript":
        from the_mesh.generators.typescript_gen import TypeScriptGenerator
        gen = TypeScriptGenerator(spec)
        output = gen.generate_all()
    elif args.type == "openapi":
        from the_mesh.generators.openapi_gen import OpenAPIGenerator
        gen = OpenAPIGenerator(spec)
        schema = gen.generate()
        output = json.dumps(schema, indent=2)
    elif args.type == "zod":
        from the_mesh.generators.zod_gen import ZodGenerator
        gen = ZodGenerator(spec)
        output = gen.generate_all()
    elif args.type == "task-package":
        output = generate_task_package(spec, args.function or "all")

    # Output
    if args.output:
        with open(args.output, "w") as f:
            f.write(output)
        print(f"Written to {args.output}")
    else:
        print(output)


def generate_tests(spec: dict, framework: str, function_name: str | None) -> str:
    """Generate tests based on framework"""

    # Parse framework
    parts = framework.split("-")
    lang = parts[0]  # pytest or jest
    test_type = parts[1] if len(parts) > 1 else "ut"  # ut, at, pc, st

    if lang == "pytest":
        if test_type == "ut":
            from the_mesh.generators.python.pytest_unit_gen import PytestUnitGenerator
            gen = PytestUnitGenerator(spec)
            return gen.generate_all()
        elif test_type == "at":
            from the_mesh.generators.python.pytest_gen import PytestGenerator
            gen = PytestGenerator(spec)
            if function_name:
                return gen.generate_for_function(function_name)
            return gen.generate_all()
        elif test_type == "pc":
            from the_mesh.generators.python.postcondition_gen import PostConditionGenerator
            gen = PostConditionGenerator(spec)
            if function_name:
                return gen.generate_for_function(function_name)
            return gen.generate_all()
        elif test_type == "st":
            from the_mesh.generators.python.state_transition_gen import StateTransitionGenerator
            gen = StateTransitionGenerator(spec)
            return gen.generate_all()
    elif lang == "jest":
        if test_type == "ut":
            from the_mesh.generators.typescript.jest_unit_gen import JestUnitGenerator
            gen = JestUnitGenerator(spec)
            return gen.generate_all()
        elif test_type == "at":
            from the_mesh.generators.typescript.jest_gen import JestGenerator
            gen = JestGenerator(spec)
            if function_name:
                return gen.generate_for_function(function_name)
            return gen.generate_all()
        elif test_type == "pc":
            from the_mesh.generators.typescript.jest_postcondition_gen import JestPostConditionGenerator
            gen = JestPostConditionGenerator(spec)
            if function_name:
                return gen.generate_for_function(function_name)
            return gen.generate_all()
        elif test_type == "st":
            from the_mesh.generators.typescript.jest_state_transition_gen import JestStateTransitionGenerator
            gen = JestStateTransitionGenerator(spec)
            return gen.generate_all()

    return f"// Unknown framework: {framework}"


def generate_task_package(spec: dict, function_name: str) -> str:
    """Generate task implementation package"""
    from the_mesh.generators.task_package_gen import TaskPackageGenerator

    gen = TaskPackageGenerator(spec)
    if function_name == "all":
        return gen.generate_all()
    return gen.generate_for_function(function_name)


if __name__ == "__main__":
    main()
