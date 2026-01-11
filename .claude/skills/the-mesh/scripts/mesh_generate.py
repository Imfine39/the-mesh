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
    pytest-idem     Idempotency tests (Python)
    pytest-conc     Concurrency tests (Python)
    pytest-authz    Authorization tests (Python)
    pytest-empty    Empty/Null boundary tests (Python)
    pytest-ref      Reference integrity tests (Python)
    pytest-time     Temporal tests (Python)
    jest-ut         Unit tests (TypeScript)
    jest-at         Acceptance tests (TypeScript)
    jest-pc         PostCondition tests (TypeScript)
    jest-st         State transition tests (TypeScript)
    jest-idem       Idempotency tests (TypeScript)
    jest-conc       Concurrency tests (TypeScript)
    jest-authz      Authorization tests (TypeScript)
    jest-empty      Empty/Null boundary tests (TypeScript)
    jest-ref        Reference integrity tests (TypeScript)
    jest-time       Temporal tests (TypeScript)
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
                        help="Output file path (default: output/<type>/)")
    args = parser.parse_args()

    # Set default output directory based on type
    script_dir = Path(__file__).parent.parent
    default_output_dir = script_dir / "output"

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
        from generators.typescript_gen import TypeScriptGenerator
        gen = TypeScriptGenerator(spec)
        output = gen.generate_all()
    elif args.type == "openapi":
        from generators.openapi_gen import OpenAPIGenerator
        gen = OpenAPIGenerator(spec)
        schema = gen.generate()
        output = json.dumps(schema, indent=2)
    elif args.type == "zod":
        from generators.zod_gen import ZodGenerator
        gen = ZodGenerator(spec)
        output = gen.generate_all()
    elif args.type == "task-package":
        output = generate_task_package(spec, args.function or "all")

    # Determine output path
    output_path = args.output
    if not output_path:
        # Set default output based on type
        if args.type == "tests":
            output_subdir = default_output_dir / "generated_tests"
            output_subdir.mkdir(parents=True, exist_ok=True)
            ext = ".py" if args.framework.startswith("pytest") else ".test.ts"
            output_path = output_subdir / f"test_{args.framework.replace('-', '_')}{ext}"
        elif args.type == "typescript":
            output_subdir = default_output_dir / "generated_types"
            output_subdir.mkdir(parents=True, exist_ok=True)
            output_path = output_subdir / "types.ts"
        elif args.type == "openapi":
            output_subdir = default_output_dir / "generated_api"
            output_subdir.mkdir(parents=True, exist_ok=True)
            output_path = output_subdir / "openapi.json"
        elif args.type == "zod":
            output_subdir = default_output_dir / "generated_types"
            output_subdir.mkdir(parents=True, exist_ok=True)
            output_path = output_subdir / "schemas.ts"

    # Output
    if output_path:
        with open(output_path, "w") as f:
            f.write(output)
        print(f"Written to {output_path}")
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
            from generators.python.pytest_unit_gen import PytestUnitGenerator
            gen = PytestUnitGenerator(spec)
            return gen.generate_all()
        elif test_type == "at":
            from generators.python.pytest_gen import PytestGenerator
            gen = PytestGenerator(spec)
            if function_name:
                return gen.generate_for_function(function_name)
            return gen.generate_all()
        elif test_type == "pc":
            from generators.python.postcondition_gen import PostConditionGenerator
            gen = PostConditionGenerator(spec)
            if function_name:
                return gen.generate_for_function(function_name)
            return gen.generate_all()
        elif test_type == "st":
            from generators.python.state_transition_gen import StateTransitionGenerator
            gen = StateTransitionGenerator(spec)
            return gen.generate_all()
        elif test_type == "idem":
            from generators.python.idempotency_gen import IdempotencyTestGenerator
            gen = IdempotencyTestGenerator(spec)
            return gen.generate_all()
        elif test_type == "conc":
            from generators.python.concurrency_gen import ConcurrencyTestGenerator
            gen = ConcurrencyTestGenerator(spec)
            return gen.generate_all()
        elif test_type == "authz":
            from generators.python.authorization_gen import AuthorizationTestGenerator
            gen = AuthorizationTestGenerator(spec)
            return gen.generate_all()
        elif test_type == "empty":
            from generators.python.empty_null_gen import EmptyNullTestGenerator
            gen = EmptyNullTestGenerator(spec)
            return gen.generate_all()
        elif test_type == "ref":
            from generators.python.reference_integrity_gen import ReferenceIntegrityTestGenerator
            gen = ReferenceIntegrityTestGenerator(spec)
            return gen.generate_all()
        elif test_type == "time":
            from generators.python.temporal_gen import TemporalTestGenerator
            gen = TemporalTestGenerator(spec)
            return gen.generate_all()
    elif lang == "jest":
        if test_type == "ut":
            from generators.typescript.jest_unit_gen import JestUnitGenerator
            gen = JestUnitGenerator(spec)
            return gen.generate_all()
        elif test_type == "at":
            from generators.typescript.jest_gen import JestGenerator
            gen = JestGenerator(spec)
            if function_name:
                return gen.generate_for_function(function_name)
            return gen.generate_all()
        elif test_type == "pc":
            from generators.typescript.jest_postcondition_gen import JestPostConditionGenerator
            gen = JestPostConditionGenerator(spec)
            if function_name:
                return gen.generate_for_function(function_name)
            return gen.generate_all()
        elif test_type == "st":
            from generators.typescript.jest_state_transition_gen import JestStateTransitionGenerator
            gen = JestStateTransitionGenerator(spec)
            return gen.generate_all()
        elif test_type == "idem":
            from generators.typescript.jest_idempotency_gen import JestIdempotencyGenerator
            gen = JestIdempotencyGenerator(spec)
            return gen.generate_all()
        elif test_type == "conc":
            from generators.typescript.jest_concurrency_gen import JestConcurrencyGenerator
            gen = JestConcurrencyGenerator(spec)
            return gen.generate_all()
        elif test_type == "authz":
            from generators.typescript.jest_authorization_gen import JestAuthorizationGenerator
            gen = JestAuthorizationGenerator(spec)
            return gen.generate_all()
        elif test_type == "empty":
            from generators.typescript.jest_empty_null_gen import JestEmptyNullGenerator
            gen = JestEmptyNullGenerator(spec)
            return gen.generate_all()
        elif test_type == "ref":
            from generators.typescript.jest_reference_integrity_gen import JestReferenceIntegrityGenerator
            gen = JestReferenceIntegrityGenerator(spec)
            return gen.generate_all()
        elif test_type == "time":
            from generators.typescript.jest_temporal_gen import JestTemporalGenerator
            gen = JestTemporalGenerator(spec)
            return gen.generate_all()

    return f"// Unknown framework: {framework}"


def generate_task_package(spec: dict, function_name: str) -> str:
    """Generate task implementation package"""
    from generators.task_package_gen import TaskPackageGenerator

    gen = TaskPackageGenerator(spec)
    if function_name == "all":
        return gen.generate_all()
    return gen.generate_for_function(function_name)


if __name__ == "__main__":
    main()
