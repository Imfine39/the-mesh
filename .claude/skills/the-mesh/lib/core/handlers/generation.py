"""Generation handlers for The Mesh."""

import json
from pathlib import Path
from typing import Any

from core.validator import MeshValidator
from graph.graph import DependencyGraph
from core.storage import SpecStorage
from generators.pytest_gen import PytestGenerator
from generators.pytest_unit_gen import PytestUnitGenerator
from generators.postcondition_gen import PostConditionGenerator
from generators.state_transition_gen import StateTransitionGenerator
from generators.jest_gen import JestGenerator
from generators.jest_unit_gen import JestUnitGenerator
from generators.jest_postcondition_gen import JestPostConditionGenerator
from generators.jest_state_transition_gen import JestStateTransitionGenerator
from generators.task_package_gen import TaskPackageGenerator


def compute_spec_changes(previous_spec: dict | None, current_spec: dict) -> list[dict]:
    """Compute JSON Patch-like changes between two specs.

    Returns a list of changes in simplified format:
    [{"op": "add/replace/remove", "path": "/section/key", "value": ...}]
    """
    if previous_spec is None:
        # New spec - everything is added
        changes = []
        for section, data in current_spec.items():
            if section == "meta":
                continue
            if isinstance(data, dict):
                for key in data:
                    changes.append({"op": "add", "path": f"/{section}/{key}"})
            elif isinstance(data, list):
                changes.append({"op": "add", "path": f"/{section}"})
        return changes

    changes = []
    sections = ["state", "functions", "scenarios", "derived", "invariants", "views", "routes"]

    for section in sections:
        prev_data = previous_spec.get(section, {})
        curr_data = current_spec.get(section, {})

        # Handle dict sections
        if isinstance(prev_data, dict) and isinstance(curr_data, dict):
            # Added keys
            for key in curr_data:
                if key not in prev_data:
                    changes.append({"op": "add", "path": f"/{section}/{key}"})
                elif curr_data[key] != prev_data[key]:
                    changes.append({"op": "replace", "path": f"/{section}/{key}"})

            # Removed keys
            for key in prev_data:
                if key not in curr_data:
                    changes.append({"op": "remove", "path": f"/{section}/{key}"})

        # Handle list sections (invariants)
        elif isinstance(prev_data, list) and isinstance(curr_data, list):
            if prev_data != curr_data:
                changes.append({"op": "replace", "path": f"/{section}"})

        # Section added/removed
        elif prev_data and not curr_data:
            changes.append({"op": "remove", "path": f"/{section}"})
        elif curr_data and not prev_data:
            changes.append({"op": "add", "path": f"/{section}"})

    return changes


def _load_spec_from_args(storage: SpecStorage, args: dict) -> dict | None:
    """Helper to load spec from various sources in args"""
    spec = args.get("spec")
    spec_path = args.get("spec_path")
    spec_id = args.get("spec_id")

    if spec is not None:
        return spec
    if spec_path:
        path = Path(spec_path)
        if path.exists():
            with open(path) as f:
                return json.load(f)
        return None
    if spec_id:
        return storage.read_spec(spec_id)
    return None


def get_function_context(validator: MeshValidator, storage: SpecStorage, args: dict) -> dict:
    """Get minimal context needed to implement a function"""
    function_name = args["function_name"]

    # Load spec from various sources
    spec = _load_spec_from_args(storage, args)
    if spec is None:
        if args.get("spec_id"):
            return {"error": f"Spec not found: {args['spec_id']}"}
        return {"error": "One of spec, spec_path, or spec_id is required"}

    # Check if function exists
    functions = spec.get("functions", {})
    if function_name not in functions:
        return {
            "error": f"Function not found: {function_name}",
            "available_functions": list(functions.keys())
        }

    # Build dependency graph and get slice
    graph = DependencyGraph()
    graph.build_from_spec(spec)
    slice_info = graph.get_slice(function_name)

    if "error" in slice_info:
        return slice_info

    # Extract full definitions for each referenced item
    result = {
        "function": function_name,
        "function_def": functions[function_name],
        "entities": {},
        "derived": {},
        "scenarios": {},
        "invariants": []
    }

    # Get entity definitions
    state = spec.get("state", {})
    for entity_name in slice_info.get("entities", []):
        if entity_name in state:
            result["entities"][entity_name] = state[entity_name]

    # Get derived definitions
    derived = spec.get("derived", {})
    for derived_name in slice_info.get("derived", []):
        if derived_name in derived:
            result["derived"][derived_name] = derived[derived_name]

    # Get scenario definitions
    scenarios = spec.get("scenarios", {})
    for scenario_id in slice_info.get("scenarios", []):
        if scenario_id in scenarios:
            result["scenarios"][scenario_id] = scenarios[scenario_id]

    # Get invariant definitions
    invariants = spec.get("invariants", [])
    invariant_ids = set(slice_info.get("invariants", []))
    for inv in invariants:
        if inv.get("id") in invariant_ids:
            result["invariants"].append(inv)

    # Add summary counts
    result["summary"] = {
        "entity_count": len(result["entities"]),
        "derived_count": len(result["derived"]),
        "scenario_count": len(result["scenarios"]),
        "invariant_count": len(result["invariants"])
    }

    return result


def generate_tests(validator: MeshValidator, storage: SpecStorage, args: dict) -> dict:
    """Generate test code from specification scenarios"""
    # Load spec from various sources
    spec = _load_spec_from_args(storage, args)
    if spec is None:
        if args.get("spec_id"):
            return {"error": f"Spec not found: {args['spec_id']}"}
        return {"error": "One of spec, spec_path, or spec_id is required"}

    framework = args.get("framework", "pytest")
    function_name = args.get("function_name")

    # Select generator
    is_unit_test = framework.endswith("-ut")

    if framework == "pytest":
        generator = PytestGenerator(spec)
        file_ext = "py"
        file_name = "test_generated.py"
        test_type = "acceptance"
    elif framework == "pytest-ut":
        generator = PytestUnitGenerator(spec)
        file_ext = "py"
        file_name = "test_unit_generated.py"
        test_type = "unit"
    elif framework == "jest":
        generator = JestGenerator(spec, typescript=False)
        file_ext = "js"
        file_name = "generated.test.js"
        test_type = "acceptance"
    elif framework == "jest-ts":
        generator = JestGenerator(spec, typescript=True)
        file_ext = "ts"
        file_name = "generated.test.ts"
        test_type = "acceptance"
    elif framework == "jest-ut":
        generator = JestUnitGenerator(spec, typescript=False)
        file_ext = "js"
        file_name = "generated.unit.test.js"
        test_type = "unit"
    elif framework == "jest-ts-ut":
        generator = JestUnitGenerator(spec, typescript=True)
        file_ext = "ts"
        file_name = "generated.unit.test.ts"
        test_type = "unit"
    # PostCondition tests - verify create/update/delete side effects
    elif framework == "pytest-postcondition":
        generator = PostConditionGenerator(spec)
        file_ext = "py"
        file_name = "test_postcondition_generated.py"
        test_type = "postcondition"
    elif framework == "jest-postcondition":
        generator = JestPostConditionGenerator(spec, typescript=False)
        file_ext = "js"
        file_name = "generated.postcondition.test.js"
        test_type = "postcondition"
    elif framework == "jest-ts-postcondition":
        generator = JestPostConditionGenerator(spec, typescript=True)
        file_ext = "ts"
        file_name = "generated.postcondition.test.ts"
        test_type = "postcondition"
    # State transition tests - verify state machine behavior
    elif framework == "pytest-state":
        generator = StateTransitionGenerator(spec)
        file_ext = "py"
        file_name = "test_state_transition_generated.py"
        test_type = "state_transition"
    elif framework == "jest-state":
        generator = JestStateTransitionGenerator(spec, typescript=False)
        file_ext = "js"
        file_name = "generated.state.test.js"
        test_type = "state_transition"
    elif framework == "jest-ts-state":
        generator = JestStateTransitionGenerator(spec, typescript=True)
        file_ext = "ts"
        file_name = "generated.state.test.ts"
        test_type = "state_transition"
    else:
        return {
            "error": f"Unknown framework: {framework}",
            "supported_frameworks": [
                "pytest", "pytest-ut", "pytest-postcondition", "pytest-state",
                "jest", "jest-ts", "jest-ut", "jest-ts-ut",
                "jest-postcondition", "jest-ts-postcondition",
                "jest-state", "jest-ts-state"
            ]
        }

    # Generate tests
    # State transition generators use generate_for_state_machine, not generate_for_function
    is_state_framework = test_type == "state_transition"

    if function_name:
        if is_state_framework:
            # For state frameworks, function_name is treated as state_machine name
            state_machines = spec.get("stateMachines", {})
            if function_name not in state_machines:
                return {
                    "error": f"State machine not found: {function_name}",
                    "available_state_machines": list(state_machines.keys()),
                    "hint": "For state transition tests, use state_machine name instead of function name"
                }
            code = generator.generate_for_state_machine(function_name)
            file_name = f"test_state_{function_name}.{file_ext}" if framework.startswith("pytest") else f"{function_name}.state.test.{file_ext}"
        else:
            # Check if function exists
            functions = spec.get("functions", {})
            if function_name not in functions:
                return {
                    "error": f"Function not found: {function_name}",
                    "available_functions": list(functions.keys())
                }
            code = generator.generate_for_function(function_name)
            file_name = f"test_{function_name}.{file_ext}" if framework == "pytest" else f"{function_name}.test.{file_ext}"
    else:
        code = generator.generate_all()

    # Count generated tests
    scenarios = spec.get("scenarios", {})
    invariants = spec.get("invariants", [])

    if function_name:
        # Count only relevant scenarios
        relevant_count = sum(
            1 for s in scenarios.values()
            if s.get("when", {}).get("call") == function_name
        )
        test_count = relevant_count
    else:
        test_count = len(scenarios) + len(invariants)

    return {
        "success": True,
        "framework": framework,
        "test_type": test_type,
        "code": code,
        "suggested_filename": file_name,
        "stats": {
            "scenario_tests": len(scenarios) if not function_name else relevant_count,
            "invariant_tests": len(invariants) if not function_name else 0,
            "total_tests": test_count
        }
    }


def generate_task_package(validator: MeshValidator, storage: SpecStorage, args: dict) -> dict:
    """Generate a complete implementation task package"""
    # Load spec from various sources
    spec = _load_spec_from_args(storage, args)
    if spec is None:
        if args.get("spec_id"):
            return {"error": f"Spec not found: {args['spec_id']}"}
        return {"error": "One of spec, spec_path, or spec_id is required"}

    function_name = args.get("function_name")
    if not function_name:
        return {"error": "function_name is required"}

    language = args.get("language", "python")
    output_dir = args.get("output_dir", ".")

    # Create generator
    generator = TaskPackageGenerator(spec, base_dir=output_dir)

    # Generate for all or single function
    if function_name == "all":
        results = generator.generate_all_task_packages(language)
        return {
            "success": True,
            "generated_count": len(results),
            "tasks": [
                {
                    "function": r.task_dir.split("/")[-1],
                    "task_dir": r.task_dir,
                    "files_count": len(r.files_created),
                    "related_functions": r.related_functions
                }
                for r in results
            ],
            "tests_dir": str(generator.tests_dir)
        }
    else:
        result = generator.generate_task_package(function_name, language)

        if not result.success:
            return {"error": result.error}

        return {
            "success": True,
            "function": function_name,
            "task_dir": result.task_dir,
            "tests_dir": result.tests_dir,
            "files_created": result.files_created,
            "related_functions": result.related_functions,
            "run_tests_command": f"cd {result.task_dir} && pytest" if language == "python" else f"cd {result.task_dir} && npx jest"
        }


def _expr_uses_entities(expr: dict, entities: set) -> bool:
    """Check if expression references any of the given entities"""
    if not isinstance(expr, dict):
        return False

    if expr.get("type") == "ref":
        path = expr.get("path", "")
        if "." in path:
            entity = path.split(".")[0]
            if entity in entities:
                return True

    # Recurse
    for key in ["left", "right", "expr", "cond", "then", "else"]:
        if key in expr and _expr_uses_entities(expr[key], entities):
            return True

    return False


def _expr_uses_derived(expr: dict, derived_names: set) -> bool:
    """Check if expression references any of the given derived values"""
    if not isinstance(expr, dict):
        return False

    if expr.get("type") == "call":
        if expr.get("name") in derived_names:
            return True

    # Recurse
    for key in ["left", "right", "expr", "cond", "then", "else"]:
        if key in expr and _expr_uses_derived(expr[key], derived_names):
            return True

    return False


def sync_after_change(validator: MeshValidator, storage: SpecStorage, args: dict) -> dict:
    """Sync task packages after spec changes - regenerate only affected items"""
    # Load spec
    spec = _load_spec_from_args(storage, args)
    if spec is None:
        if args.get("spec_id"):
            return {"error": f"Spec not found: {args['spec_id']}"}
        return {"error": "One of spec, spec_path, or spec_id is required"}

    changes = args.get("changes", [])
    if not changes:
        return {"error": "changes is required (JSON Patch format)"}

    language = args.get("language", "python")
    output_dir = args.get("output_dir", ".")

    # Parse changes to find affected elements directly
    affected_entities = set()
    affected_functions_direct = set()
    affected_scenarios = set()
    affected_derived = set()
    affected_invariants = set()

    for change in changes:
        path = change.get("path", "")
        parts = path.strip("/").split("/")

        if len(parts) >= 2:
            section = parts[0]
            name = parts[1]

            if section == "state":
                affected_entities.add(name)
            elif section == "functions":
                affected_functions_direct.add(name)
            elif section == "scenarios":
                affected_scenarios.add(name)
            elif section == "derived":
                affected_derived.add(name)
            elif section == "invariants":
                # invariants is an array, need to handle differently
                pass

    # Collect all affected functions
    affected_functions = set(affected_functions_direct)

    # Functions that use affected entities
    for func_name, func_def in spec.get("functions", {}).items():
        # Check preconditions
        for pre in func_def.get("pre", []):
            if _expr_uses_entities(pre.get("check", {}), affected_entities):
                affected_functions.add(func_name)
        # Check post-actions
        for post in func_def.get("post", []):
            action = post.get("action", {})
            for action_type in ["create", "update", "delete"]:
                if action.get(action_type) in affected_entities:
                    affected_functions.add(func_name)
        # Check input types that reference entities
        for input_name, input_def in func_def.get("input", {}).items():
            input_type = input_def.get("type", {})
            if isinstance(input_type, dict) and input_type.get("ref") in affected_entities:
                affected_functions.add(func_name)

    # Functions whose scenarios are affected
    for scenario_id, scenario in spec.get("scenarios", {}).items():
        if scenario_id in affected_scenarios:
            func_name = scenario.get("when", {}).get("call")
            if func_name:
                affected_functions.add(func_name)
        # Also check if scenario uses affected entities in given
        for entity_name in scenario.get("given", {}).keys():
            if entity_name in affected_entities:
                func_name = scenario.get("when", {}).get("call")
                if func_name:
                    affected_functions.add(func_name)

    # Functions that use affected derived values
    for func_name, func_def in spec.get("functions", {}).items():
        for pre in func_def.get("pre", []):
            if _expr_uses_derived(pre.get("check", {}), affected_derived):
                affected_functions.add(func_name)

    if not affected_functions:
        return {
            "success": True,
            "message": "No functions affected by changes",
            "updated_functions": [],
            "updated_tests": [],
            "updated_task_packages": []
        }

    # Create generator and regenerate affected packages
    generator = TaskPackageGenerator(spec, base_dir=output_dir)

    updated_tests = []
    updated_task_packages = []

    for func_name in affected_functions:
        result = generator.generate_task_package(func_name, language, write_files=True)
        if result.success:
            updated_task_packages.append(func_name)
            # Extract test file names from files_created
            for f in result.files_created:
                if "/tests/" in f:
                    updated_tests.append(f.split("/")[-1])

    # Remove duplicates from test list
    updated_tests = list(set(updated_tests))

    return {
        "success": True,
        "changes_analyzed": len(changes),
        "impact_summary": {
            "affected_entities": list(affected_entities),
            "affected_functions": list(affected_functions),
            "affected_scenarios": list(affected_scenarios),
            "affected_derived": list(affected_derived)
        },
        "updated_functions": list(affected_functions),
        "updated_tests": updated_tests,
        "updated_task_packages": updated_task_packages,
        "unchanged_functions": [
            f for f in spec.get("functions", {}).keys()
            if f not in affected_functions
        ]
    }


# Handler registry
HANDLERS = {
    "get_function_context": get_function_context,
    "generate_tests": generate_tests,
    "generate_task_package": generate_task_package,
    "sync_after_change": sync_after_change,
}
