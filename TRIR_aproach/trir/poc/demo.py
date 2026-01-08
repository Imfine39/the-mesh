#!/usr/bin/env python3
"""TRIR PoC Demo Script"""

import sys
import json
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

# Use absolute imports when run as script
if __name__ == "__main__":
    from validator import TRIRValidator, ValidationResult
    from graph import DependencyGraph, ImpactAnalysis

    # Inline engine to avoid import issues
    class TRIREngine:
        def __init__(self, schema_dir=None):
            self.spec = {"meta": {}, "state": {}, "derived": {}, "functions": {}, "scenarios": {}, "invariants": []}
            self.validator = TRIRValidator(schema_dir)
            self.graph = DependencyGraph()

        def load(self, path):
            from dataclasses import dataclass
            @dataclass
            class Result:
                success: bool
                data: dict = None
                error: str = None
            try:
                with open(path) as f:
                    self.spec = json.load(f)
                self.graph.build_from_spec(self.spec)
                return Result(success=True, data={"loaded": str(path)})
            except Exception as e:
                return Result(success=False, error=str(e))

        def validate(self):
            return self.validator.validate(self.spec)

        def analyze_impact(self, target_type, target_name, change_type="modify"):
            return self.graph.analyze_impact(target_type, target_name, change_type)

        def get_slice(self, function_name):
            return self.graph.get_slice(function_name)

        def export_mermaid(self):
            return self.graph.to_mermaid()

    sys.path.insert(0, str(Path(__file__).parent / "generators"))
    from pytest_gen import PytestGenerator
    from yaml_gen import YAMLGenerator
else:
    from .engine import TRIREngine
    from .generators import PytestGenerator, YAMLGenerator


def main():
    print("=" * 60)
    print("TRIR (Typed Relational IR) PoC Demo")
    print("=" * 60)

    # Load example spec
    example_path = Path(__file__).parent / "examples" / "accounting.trir.json"
    engine = TRIREngine()

    print("\n[1] Loading specification...")
    result = engine.load(example_path)
    if result.success:
        print(f"    ✅ Loaded: {result.data}")
    else:
        print(f"    ❌ Error: {result.error}")
        return

    # Validate
    print("\n[2] Validating specification...")
    validation = engine.validate()
    if validation.valid:
        print("    ✅ Specification is valid")
    else:
        print("    ❌ Validation errors:")
        for err in validation.errors:
            print(f"       - {err.path}: {err.message}")

    if validation.warnings:
        print("    ⚠️  Warnings:")
        for warn in validation.warnings:
            print(f"       - {warn.path}: {warn.message}")

    # Analyze impact
    print("\n[3] Analyzing impact of changing invoice.amount...")
    impact = engine.analyze_impact("entity", "invoice", "modify")
    print(f"    Affected functions: {impact.affected_functions}")
    print(f"    Affected derived: {impact.affected_derived}")
    print(f"    Affected scenarios: {impact.affected_scenarios}")
    print(f"    Affected invariants: {impact.affected_invariants}")

    # Get slice for implementation
    print("\n[4] Getting slice for allocate_payment implementation...")
    slice_info = engine.get_slice("allocate_payment")
    print(f"    Entities needed: {slice_info.get('entities', [])}")
    print(f"    Derived needed: {slice_info.get('derived', [])}")
    print(f"    Scenarios to pass: {slice_info.get('scenarios', [])}")
    print(f"    Invariants to satisfy: {slice_info.get('invariants', [])}")

    # Generate pytest
    print("\n[5] Generating pytest code for allocate_payment...")
    pytest_gen = PytestGenerator(engine.spec)
    pytest_code = pytest_gen.generate_for_function("allocate_payment")
    print("    Generated test code (first 50 lines):")
    for i, line in enumerate(pytest_code.split("\n")[:50]):
        print(f"    {line}")
    print("    ...")

    # Generate YAML (Human View)
    print("\n[6] Generating Human View (YAML)...")
    try:
        yaml_gen = YAMLGenerator(engine.spec)
        yaml_view = yaml_gen.generate_section("functions")
        print("    Generated YAML (functions section):")
        for line in yaml_view.split("\n")[:30]:
            print(f"    {line}")
        print("    ...")
    except ImportError as e:
        print(f"    ⚠️  {e}")

    # Export Mermaid diagram
    print("\n[7] Exporting dependency graph (Mermaid)...")
    mermaid = engine.export_mermaid()
    print("    Generated Mermaid diagram (first 20 lines):")
    for line in mermaid.split("\n")[:20]:
        print(f"    {line}")
    print("    ...")

    print("\n" + "=" * 60)
    print("Demo complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
