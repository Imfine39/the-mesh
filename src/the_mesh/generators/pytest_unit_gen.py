"""Mesh to pytest Unit Test Generator

Generates granular unit tests for Python/pytest from:
- derived formulas (calculation logic)
- function error_cases (error handling)
- function preconditions (validation logic)
- field types (boundary values)
"""

from typing import Any
from dataclasses import dataclass


@dataclass
class TestCase:
    """Represents a single unit test case"""
    id: str
    description: str
    category: str  # 'derived', 'error_case', 'precondition', 'boundary'
    target: str    # function or derived name
    inputs: dict[str, Any]
    expected: Any
    is_error_case: bool = False


class PytestUnitGenerator:
    """Generates pytest unit tests from TRIR specification"""

    def __init__(self, spec: dict[str, Any]):
        self.spec = spec
        self.entities = spec.get("state", {})
        self.derived = spec.get("derived", {})
        self.functions = spec.get("functions", {})
        self.invariants = spec.get("invariants", [])

    def generate_all(self) -> str:
        """Generate all unit tests"""
        test_cases = []

        # 1. Derived formula tests
        test_cases.extend(self._generate_derived_tests())

        # 2. Error case tests
        test_cases.extend(self._generate_error_case_tests())

        # 3. Precondition tests
        test_cases.extend(self._generate_precondition_tests())

        # 4. Boundary value tests
        test_cases.extend(self._generate_boundary_tests())

        return self._render_tests(test_cases)

    def _generate_derived_tests(self) -> list[TestCase]:
        """Generate tests for derived/calculated fields"""
        cases = []

        for name, derived in self.derived.items():
            formula = derived.get("formula", {})
            entity = derived.get("entity", "")

            formula_cases = self._analyze_formula(name, formula, entity)
            cases.extend(formula_cases)

        return cases

    def _analyze_formula(self, name: str, formula: dict, entity: str) -> list[TestCase]:
        """Analyze formula structure to generate test cases"""
        cases = []
        formula_type = formula.get("type")

        if formula_type == "binary":
            op = formula.get("op", "")
            cases.extend(self._generate_binary_op_cases(name, op, formula, entity))

        elif formula_type == "agg":
            cases.extend(self._generate_agg_cases(name, formula, entity))

        elif formula_type == "if":
            cases.extend(self._generate_conditional_cases(name, formula, entity))

        if not cases:
            cases.append(TestCase(
                id=f"ut_{name}_001",
                description=f"Basic test for {name}",
                category="derived",
                target=name,
                inputs={entity: self._get_sample_entity(entity)},
                expected="# TODO: specify expected value"
            ))

        return cases

    def _generate_binary_op_cases(self, name: str, op: str, formula: dict, entity: str) -> list[TestCase]:
        """Generate test cases for binary operations"""
        cases = []

        if op in ("add", "sub", "mul", "div"):
            cases.append(TestCase(
                id=f"ut_{name}_zero",
                description=f"{name}: operands with zero",
                category="derived",
                target=name,
                inputs=self._make_zero_inputs(formula, entity),
                expected=0 if op in ("add", "sub", "mul") else "# division by zero check"
            ))

            cases.append(TestCase(
                id=f"ut_{name}_positive",
                description=f"{name}: positive operands",
                category="derived",
                target=name,
                inputs=self._make_positive_inputs(formula, entity),
                expected="# calculate expected"
            ))

            if op == "sub":
                cases.append(TestCase(
                    id=f"ut_{name}_equal",
                    description=f"{name}: equal operands (result=0)",
                    category="derived",
                    target=name,
                    inputs=self._make_equal_inputs(formula, entity),
                    expected=0
                ))

        elif op in ("eq", "ne", "lt", "le", "gt", "ge"):
            cases.append(TestCase(
                id=f"ut_{name}_true",
                description=f"{name}: condition is true",
                category="derived",
                target=name,
                inputs=self._make_comparison_true_inputs(op, formula, entity),
                expected=True
            ))
            cases.append(TestCase(
                id=f"ut_{name}_false",
                description=f"{name}: condition is false",
                category="derived",
                target=name,
                inputs=self._make_comparison_false_inputs(op, formula, entity),
                expected=False
            ))

        return cases

    def _generate_agg_cases(self, name: str, formula: dict, entity: str) -> list[TestCase]:
        """Generate test cases for aggregation operations"""
        cases = []
        agg_op = formula.get("op", "")
        from_entity = formula.get("from", "items")

        cases.append(TestCase(
            id=f"ut_{name}_empty",
            description=f"{name}: empty {from_entity}",
            category="derived",
            target=name,
            inputs={entity: self._get_sample_entity(entity), f"{from_entity}_list": []},
            expected=0 if agg_op in ("sum", "count") else None
        ))

        cases.append(TestCase(
            id=f"ut_{name}_single",
            description=f"{name}: single {from_entity}",
            category="derived",
            target=name,
            inputs={
                entity: self._get_sample_entity(entity),
                f"{from_entity}_list": [{"amount": 1000}]
            },
            expected=1000 if agg_op == "sum" else 1 if agg_op == "count" else "# expected"
        ))

        cases.append(TestCase(
            id=f"ut_{name}_multiple",
            description=f"{name}: multiple {from_entity}",
            category="derived",
            target=name,
            inputs={
                entity: self._get_sample_entity(entity),
                f"{from_entity}_list": [{"amount": 1000}, {"amount": 2000}, {"amount": 3000}]
            },
            expected=6000 if agg_op == "sum" else 3 if agg_op == "count" else "# expected"
        ))

        return cases

    def _generate_conditional_cases(self, name: str, formula: dict, entity: str) -> list[TestCase]:
        """Generate test cases for conditional expressions"""
        cases = []

        cases.append(TestCase(
            id=f"ut_{name}_then",
            description=f"{name}: condition true -> then branch",
            category="derived",
            target=name,
            inputs={entity: self._get_sample_entity(entity), "_condition": True},
            expected="# then value"
        ))

        cases.append(TestCase(
            id=f"ut_{name}_else",
            description=f"{name}: condition false -> else branch",
            category="derived",
            target=name,
            inputs={entity: self._get_sample_entity(entity), "_condition": False},
            expected="# else value"
        ))

        return cases

    def _generate_error_case_tests(self) -> list[TestCase]:
        """Generate tests for function error cases"""
        cases = []

        for func_name, func_def in self.functions.items():
            for i, error_case in enumerate(func_def.get("error_cases", [])):
                error_code = error_case.get("code", f"ERR_{i+1:03d}")
                when_expr = error_case.get("when", {})

                cases.append(TestCase(
                    id=f"ut_{func_name}_{error_code.lower().replace('-', '_')}",
                    description=f"{func_name}: {error_case.get('message', error_code)}",
                    category="error_case",
                    target=func_name,
                    inputs=self._make_error_trigger_inputs(when_expr, func_def),
                    expected={"success": False, "error": error_code},
                    is_error_case=True
                ))

                boundary_inputs = self._make_error_boundary_inputs(when_expr, func_def)
                if boundary_inputs:
                    cases.append(TestCase(
                        id=f"ut_{func_name}_{error_code.lower().replace('-', '_')}_boundary",
                        description=f"{func_name}: boundary - just valid",
                        category="error_case",
                        target=func_name,
                        inputs=boundary_inputs,
                        expected={"success": True},
                        is_error_case=False
                    ))

        return cases

    def _generate_precondition_tests(self) -> list[TestCase]:
        """Generate tests for function preconditions"""
        cases = []

        for func_name, func_def in self.functions.items():
            for i, pre in enumerate(func_def.get("pre", [])):
                check_expr = pre.get("check", {})

                cases.append(TestCase(
                    id=f"ut_{func_name}_pre{i+1}_pass",
                    description=f"{func_name}: precondition {i+1} satisfied",
                    category="precondition",
                    target=func_name,
                    inputs=self._make_precondition_pass_inputs(check_expr, func_def),
                    expected={"precondition_passed": True}
                ))

                cases.append(TestCase(
                    id=f"ut_{func_name}_pre{i+1}_fail",
                    description=f"{func_name}: precondition {i+1} violated",
                    category="precondition",
                    target=func_name,
                    inputs=self._make_precondition_fail_inputs(check_expr, func_def),
                    expected={"precondition_passed": False},
                    is_error_case=True
                ))

        return cases

    def _generate_boundary_tests(self) -> list[TestCase]:
        """Generate boundary value tests from field types"""
        cases = []

        for entity_name, entity_def in self.entities.items():
            fields = entity_def.get("fields", {})

            for field_name, field_def in fields.items():
                field_type = field_def.get("type")
                required = field_def.get("required", False)

                boundary_values = self._get_boundary_values(field_type, required)

                for bv in boundary_values:
                    cases.append(TestCase(
                        id=f"ut_{entity_name}_{field_name}_{bv['label']}",
                        description=f"{entity_name}.{field_name}: {bv['description']}",
                        category="boundary",
                        target=f"{entity_name}.{field_name}",
                        inputs={field_name: bv["value"]},
                        expected={"valid": bv["should_be_valid"]}
                    ))

        return cases

    def _get_boundary_values(self, field_type: Any, required: bool) -> list[dict]:
        """Get boundary test values for a field type"""
        values = []

        if isinstance(field_type, str):
            if field_type == "int":
                values = [
                    {"label": "zero", "value": 0, "should_be_valid": True, "description": "zero value"},
                    {"label": "positive", "value": 1, "should_be_valid": True, "description": "minimum positive"},
                    {"label": "negative", "value": -1, "should_be_valid": "# depends on domain", "description": "negative value"},
                    {"label": "large", "value": 2147483647, "should_be_valid": True, "description": "max int32"},
                ]
            elif field_type == "float":
                values = [
                    {"label": "zero", "value": 0.0, "should_be_valid": True, "description": "zero"},
                    {"label": "small", "value": 0.01, "should_be_valid": True, "description": "small positive"},
                    {"label": "negative", "value": -0.01, "should_be_valid": "# depends", "description": "small negative"},
                ]
            elif field_type == "string":
                values = [
                    {"label": "empty", "value": "", "should_be_valid": not required, "description": "empty string"},
                    {"label": "single", "value": "a", "should_be_valid": True, "description": "single char"},
                    {"label": "long", "value": "a" * 1000, "should_be_valid": "# depends on max length", "description": "very long string"},
                ]

        elif isinstance(field_type, dict):
            if "enum" in field_type:
                for enum_val in field_type["enum"]:
                    values.append({
                        "label": enum_val.lower(),
                        "value": enum_val,
                        "should_be_valid": True,
                        "description": f"enum value: {enum_val}"
                    })
                values.append({
                    "label": "invalid_enum",
                    "value": "INVALID_VALUE",
                    "should_be_valid": False,
                    "description": "invalid enum value"
                })

        if required:
            values.append({
                "label": "null",
                "value": None,
                "should_be_valid": False,
                "description": "null for required field"
            })

        return values

    def _render_tests(self, test_cases: list[TestCase]) -> str:
        """Render test cases to pytest code"""
        lines = [
            '"""',
            'Auto-generated Unit Tests from TRIR specification',
            '',
            '@generated',
            '"""',
            '',
            'import pytest',
            'from typing import Any',
            '',
            '# TODO: Import your implementation',
            '# from your_module import calculate_outstanding, validate_invoice, ...',
            '',
        ]

        # Group by category
        by_category: dict[str, list[TestCase]] = {}
        for tc in test_cases:
            if tc.category not in by_category:
                by_category[tc.category] = []
            by_category[tc.category].append(tc)

        category_titles = {
            "derived": "Derived/Calculated Field Tests",
            "error_case": "Error Case Tests",
            "precondition": "Precondition Tests",
            "boundary": "Boundary Value Tests"
        }

        for category, cases in by_category.items():
            lines.append(f"# {'=' * 10} {category_titles.get(category, category)} {'=' * 10}")
            lines.append("")

            # Group by target
            by_target: dict[str, list[TestCase]] = {}
            for tc in cases:
                if tc.target not in by_target:
                    by_target[tc.target] = []
                by_target[tc.target].append(tc)

            for target, target_cases in by_target.items():
                lines.append(f"class Test{self._to_pascal(target)}:")
                lines.append(f'    """Tests for {target}"""')
                lines.append("")

                for tc in target_cases:
                    lines.append(f"    def test_{tc.id}(self):")
                    lines.append(f'        """')
                    lines.append(f'        {tc.description}')
                    lines.append(f'        """')

                    # Add input comment
                    lines.append(f"        # Inputs: {self._to_py_repr(tc.inputs)}")
                    lines.append(f"        # Expected: {self._to_py_repr(tc.expected)}")
                    lines.append("")

                    if tc.category == "derived":
                        lines.append(f"        # result = {self._to_snake(target)}(...)")
                        lines.append(f"        # assert result == {self._to_py_repr(tc.expected)}")
                        lines.append("        pytest.skip('TODO: implement')")
                    elif tc.category == "error_case":
                        lines.append(f"        # result = {self._to_snake(target)}({self._to_py_repr(tc.inputs)})")
                        if tc.is_error_case:
                            lines.append(f"        # assert result.success is False")
                            lines.append(f"        # assert result.error.code == '{tc.expected.get('error', '')}'")
                        else:
                            lines.append(f"        # assert result.success is True")
                        lines.append("        pytest.skip('TODO: implement')")
                    elif tc.category == "precondition":
                        lines.append(f"        # Setup precondition test for {target}")
                        lines.append(f"        # assert check_precondition(...) is {not tc.is_error_case}")
                        lines.append("        pytest.skip('TODO: implement')")
                    elif tc.category == "boundary":
                        entity = target.split('.')[0]
                        lines.append(f"        # is_valid = validate_{self._to_snake(entity)}({self._to_py_repr(tc.inputs)})")
                        lines.append(f"        # assert is_valid is {self._to_py_repr(tc.expected.get('valid', True))}")
                        lines.append("        pytest.skip('TODO: implement')")

                    lines.append("")

                lines.append("")

        return "\n".join(lines)

    # Helper methods
    def _get_sample_entity(self, entity_name: str) -> dict:
        """Get sample entity with default values"""
        entity = self.entities.get(entity_name, {})
        sample = {}
        for field_name, field_def in entity.get("fields", {}).items():
            sample[field_name] = self._get_default_value(field_def.get("type"))
        return sample

    def _get_default_value(self, field_type: Any) -> Any:
        """Get default value for field type"""
        if isinstance(field_type, str):
            return {"string": "TEST", "int": 1000, "float": 1.0, "bool": True, "datetime": "2024-01-01"}.get(field_type, None)
        if isinstance(field_type, dict):
            if "enum" in field_type:
                return field_type["enum"][0]
            if "ref" in field_type:
                return "REF-001"
        return None

    def _make_zero_inputs(self, formula: dict, entity: str) -> dict:
        sample = self._get_sample_entity(entity)
        for k, v in sample.items():
            if isinstance(v, (int, float)):
                sample[k] = 0
        return {entity: sample}

    def _make_positive_inputs(self, formula: dict, entity: str) -> dict:
        return {entity: self._get_sample_entity(entity)}

    def _make_equal_inputs(self, formula: dict, entity: str) -> dict:
        sample = self._get_sample_entity(entity)
        return {entity: sample, "_note": "set operands to equal values"}

    def _make_comparison_true_inputs(self, op: str, formula: dict, entity: str) -> dict:
        return {entity: self._get_sample_entity(entity), "_condition_should_be": True}

    def _make_comparison_false_inputs(self, op: str, formula: dict, entity: str) -> dict:
        return {entity: self._get_sample_entity(entity), "_condition_should_be": False}

    def _make_error_trigger_inputs(self, when_expr: dict, func_def: dict) -> dict:
        return {"_trigger_error": True, "_expr": str(when_expr)[:50]}

    def _make_error_boundary_inputs(self, when_expr: dict, func_def: dict) -> dict | None:
        return {"_boundary": True, "_expr": str(when_expr)[:50]}

    def _make_precondition_pass_inputs(self, check_expr: dict, func_def: dict) -> dict:
        return {"_precondition_should_pass": True}

    def _make_precondition_fail_inputs(self, check_expr: dict, func_def: dict) -> dict:
        return {"_precondition_should_fail": True}

    def _to_py_repr(self, obj: Any) -> str:
        """Convert to Python repr string"""
        if obj is None:
            return "None"
        if isinstance(obj, bool):
            return "True" if obj else "False"
        if isinstance(obj, str):
            if obj.startswith("#"):
                return obj  # Comment
            return repr(obj)
        if isinstance(obj, (int, float)):
            return str(obj)
        if isinstance(obj, dict):
            items = ", ".join(f"{repr(k)}: {self._to_py_repr(v)}" for k, v in obj.items())
            return "{" + items + "}"
        if isinstance(obj, list):
            items = ", ".join(self._to_py_repr(v) for v in obj)
            return "[" + items + "]"
        return repr(obj)

    def _to_snake(self, name: str) -> str:
        """Convert to snake_case"""
        return name.replace(".", "_").lower()

    def _to_pascal(self, name: str) -> str:
        """Convert to PascalCase"""
        return "".join(p.capitalize() for p in name.replace(".", "_").split("_"))
