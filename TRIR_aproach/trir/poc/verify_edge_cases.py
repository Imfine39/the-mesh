#!/usr/bin/env python3
"""TRIR Edge Case Verification Script"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "generators"))

from validator import TRIRValidator
from graph import DependencyGraph
from pytest_gen import PytestGenerator
from yaml_gen import YAMLGenerator


def print_header(title: str):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_result(name: str, success: bool, details: str = ""):
    status = "✅" if success else "❌"
    print(f"  {status} {name}")
    if details:
        for line in details.split("\n"):
            print(f"      {line}")


def verify_spec(spec_path: Path, name: str) -> dict:
    """Verify a single spec file"""
    results = {
        "name": name,
        "load": False,
        "validate": False,
        "graph": False,
        "pytest_gen": False,
        "yaml_gen": False,
        "errors": [],
        "warnings": []
    }

    try:
        with open(spec_path) as f:
            spec = json.load(f)
        results["load"] = True
    except Exception as e:
        results["errors"].append(f"Load failed: {e}")
        return results

    # Validate
    try:
        validator = TRIRValidator()
        validation = validator.validate(spec)
        results["validate"] = validation.valid
        results["validation_errors"] = [f"{e.path}: {e.message}" for e in validation.errors]
        results["warnings"] = [f"{w.path}: {w.message}" for w in validation.warnings]
    except Exception as e:
        results["errors"].append(f"Validation failed: {e}")

    # Build graph
    try:
        graph = DependencyGraph()
        graph.build_from_spec(spec)
        results["graph"] = True
        results["node_count"] = len(graph.nodes)
        results["edge_count"] = len(graph.edges)
    except Exception as e:
        results["errors"].append(f"Graph build failed: {e}")

    # Generate pytest
    try:
        pytest_gen = PytestGenerator(spec)
        pytest_code = pytest_gen.generate_all()
        results["pytest_gen"] = True
        results["pytest_lines"] = len(pytest_code.split("\n"))
    except Exception as e:
        results["errors"].append(f"Pytest generation failed: {e}")

    # Generate YAML
    try:
        yaml_gen = YAMLGenerator(spec)
        yaml_code = yaml_gen.generate()
        results["yaml_gen"] = True
        results["yaml_lines"] = len(yaml_code.split("\n"))
    except ImportError:
        results["yaml_gen"] = None  # PyYAML not installed
    except Exception as e:
        results["errors"].append(f"YAML generation failed: {e}")

    return results


def verify_invalid_specs(invalid_specs_path: Path) -> list:
    """Verify that invalid specs are correctly rejected"""
    results = []

    with open(invalid_specs_path) as f:
        data = json.load(f)

    validator = TRIRValidator()

    for test_case in data["test_cases"]:
        name = test_case["name"]
        expected_error = test_case["expected_error"]
        spec = test_case["spec"]

        validation = validator.validate(spec)
        all_messages = [e.message for e in validation.errors] + [w.message for w in validation.warnings]

        if expected_error is None:
            # Should be valid
            success = validation.valid
            detail = "" if success else f"Unexpected errors: {all_messages}"
        else:
            # Should have error containing expected_error
            found = any(expected_error in msg for msg in all_messages)
            success = found
            if not found:
                detail = f"Expected '{expected_error}' but got: {all_messages}"
            else:
                detail = f"Correctly detected: {expected_error}"

        results.append({
            "name": name,
            "success": success,
            "detail": detail,
            "expected": expected_error
        })

    return results


def verify_complex_expressions(spec_path: Path) -> list:
    """Verify complex expression handling"""
    results = []

    with open(spec_path) as f:
        spec = json.load(f)

    # Test each derived formula
    for name, derived in spec.get("derived", {}).items():
        formula = derived.get("formula", {})

        # Check formula complexity
        def count_depth(expr, depth=0):
            if not isinstance(expr, dict):
                return depth
            max_child_depth = depth
            for v in expr.values():
                if isinstance(v, dict):
                    max_child_depth = max(max_child_depth, count_depth(v, depth + 1))
                elif isinstance(v, list):
                    for item in v:
                        if isinstance(item, dict):
                            max_child_depth = max(max_child_depth, count_depth(item, depth + 1))
            return max_child_depth

        depth = count_depth(formula)

        # Check for specific constructs (Tagged Union format)
        has_case = '"type": "case"' in str(formula) or "'type': 'case'" in str(formula)
        has_date = '"type": "date"' in str(formula) or "'type': 'date'" in str(formula)
        # Check for nested function calls
        has_nested_call = formula.get("type") == "call" and '"type": "call"' in str(formula.get("args", []))

        results.append({
            "name": name,
            "depth": depth,
            "has_case": has_case,
            "has_date": has_date,
            "has_nested_call": has_nested_call
        })

    return results


def main():
    examples_dir = Path(__file__).parent / "examples"

    # 1. Verify main specs
    print_header("1. Valid Spec Verification")

    specs_to_verify = [
        ("accounting.trir.json", "会計システム（基本）"),
        ("edge_cases.trir.json", "エッジケース（複雑な式）"),
        ("reservation.trir.json", "予約システム（日付演算）"),
    ]

    all_results = []
    for filename, name in specs_to_verify:
        spec_path = examples_dir / filename
        if spec_path.exists():
            result = verify_spec(spec_path, name)
            all_results.append(result)

            print(f"\n  [{name}]")
            print_result("Load", result["load"])
            print_result("Validate", result["validate"],
                        "\n".join(result.get("validation_errors", [])) if not result["validate"] else "")
            print_result("Graph Build", result["graph"],
                        f"Nodes: {result.get('node_count', 0)}, Edges: {result.get('edge_count', 0)}" if result["graph"] else "")
            print_result("Pytest Gen", result["pytest_gen"],
                        f"Lines: {result.get('pytest_lines', 0)}" if result["pytest_gen"] else "")
            if result["yaml_gen"] is None:
                print("  ⚠️  YAML Gen: PyYAML not installed")
            else:
                print_result("YAML Gen", result["yaml_gen"],
                            f"Lines: {result.get('yaml_lines', 0)}" if result["yaml_gen"] else "")

            if result.get("warnings"):
                print("  ⚠️  Warnings:")
                for w in result["warnings"]:
                    print(f"      - {w}")

    # 2. Invalid specs detection
    print_header("2. Invalid Spec Detection")

    invalid_path = examples_dir / "invalid_specs.json"
    if invalid_path.exists():
        invalid_results = verify_invalid_specs(invalid_path)

        for r in invalid_results:
            if r["expected"] is None:
                desc = "(should be valid)"
            else:
                desc = f"(should detect: {r['expected'][:30]}...)"
            print_result(f"{r['name']} {desc}", r["success"], r["detail"] if not r["success"] else "")

    # 3. Complex expression analysis
    print_header("3. Complex Expression Analysis")

    edge_cases_path = examples_dir / "edge_cases.trir.json"
    if edge_cases_path.exists():
        expr_results = verify_complex_expressions(edge_cases_path)

        print("\n  Derived Formula Complexity:")
        print("  " + "-" * 60)
        print(f"  {'Name':<30} {'Depth':<6} {'CASE':<6} {'Date':<6} {'Nested'}")
        print("  " + "-" * 60)
        for r in expr_results:
            print(f"  {r['name']:<30} {r['depth']:<6} {'✓' if r['has_case'] else '':<6} {'✓' if r['has_date'] else '':<6} {'✓' if r['has_nested_call'] else ''}")

    # 4. Summary
    print_header("4. Summary")

    total_specs = len(all_results)
    valid_specs = sum(1 for r in all_results if r["validate"])
    graph_success = sum(1 for r in all_results if r["graph"])
    pytest_success = sum(1 for r in all_results if r["pytest_gen"])

    print(f"""
  Specs tested: {total_specs}
  Validation passed: {valid_specs}/{total_specs}
  Graph build success: {graph_success}/{total_specs}
  Pytest generation success: {pytest_success}/{total_specs}
    """)

    if invalid_path.exists():
        invalid_success = sum(1 for r in invalid_results if r["success"])
        print(f"  Invalid spec detection: {invalid_success}/{len(invalid_results)}")

    # Check for overall success
    all_passed = (valid_specs == total_specs and
                  graph_success == total_specs and
                  pytest_success == total_specs)

    if invalid_path.exists():
        all_passed = all_passed and (invalid_success == len(invalid_results))

    if all_passed:
        print("\n  🎉 All tests passed!")
    else:
        print("\n  ⚠️  Some tests failed - see details above")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
