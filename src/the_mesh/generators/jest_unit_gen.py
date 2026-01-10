"""TRIR to Unit Test Generator

Generates granular unit tests from:
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


class JestUnitGenerator:
    """Generates unit tests from TRIR specification"""

    def __init__(self, spec: dict[str, Any], typescript: bool = False):
        self.spec = spec
        self.typescript = typescript
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

            # Analyze formula to generate test cases
            formula_cases = self._analyze_formula(name, formula, entity)
            cases.extend(formula_cases)

        return cases

    def _analyze_formula(self, name: str, formula: dict, entity: str) -> list[TestCase]:
        """Analyze formula structure to generate test cases"""
        cases = []
        formula_type = formula.get("type")

        # Binary operations: test with various operand combinations
        if formula_type == "binary":
            op = formula.get("op", "")
            cases.extend(self._generate_binary_op_cases(name, op, formula, entity))

        # Aggregations: test empty, single, multiple
        elif formula_type == "agg":
            cases.extend(self._generate_agg_cases(name, formula, entity))

        # Conditionals: test each branch
        elif formula_type == "if":
            cases.extend(self._generate_conditional_cases(name, formula, entity))

        # Default: at least one basic case
        if not cases:
            cases.append(TestCase(
                id=f"UT-{name}-001",
                description=f"Basic test for {name}",
                category="derived",
                target=name,
                inputs={entity: self._get_sample_entity(entity)},
                expected="/* TODO: specify expected value */"
            ))

        return cases

    def _generate_binary_op_cases(self, name: str, op: str, formula: dict, entity: str) -> list[TestCase]:
        """Generate test cases for binary operations"""
        cases = []

        # Arithmetic operations
        if op in ("add", "sub", "mul", "div"):
            # Case 1: Zero values
            cases.append(TestCase(
                id=f"UT-{name}-zero",
                description=f"{name}: operands with zero",
                category="derived",
                target=name,
                inputs=self._make_zero_inputs(formula, entity),
                expected=0 if op in ("add", "sub", "mul") else "/* division by zero check */"
            ))

            # Case 2: Positive values
            cases.append(TestCase(
                id=f"UT-{name}-positive",
                description=f"{name}: positive operands",
                category="derived",
                target=name,
                inputs=self._make_positive_inputs(formula, entity),
                expected="/* calculate expected */"
            ))

            # Case 3: Result is zero (for sub)
            if op == "sub":
                cases.append(TestCase(
                    id=f"UT-{name}-equal",
                    description=f"{name}: equal operands (result=0)",
                    category="derived",
                    target=name,
                    inputs=self._make_equal_inputs(formula, entity),
                    expected=0
                ))

        # Comparison operations
        elif op in ("eq", "ne", "lt", "le", "gt", "ge"):
            cases.append(TestCase(
                id=f"UT-{name}-true",
                description=f"{name}: condition is true",
                category="derived",
                target=name,
                inputs=self._make_comparison_true_inputs(op, formula, entity),
                expected=True
            ))
            cases.append(TestCase(
                id=f"UT-{name}-false",
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

        # Empty collection
        cases.append(TestCase(
            id=f"UT-{name}-empty",
            description=f"{name}: empty {from_entity}",
            category="derived",
            target=name,
            inputs={entity: self._get_sample_entity(entity), f"{from_entity}_list": []},
            expected=0 if agg_op in ("sum", "count") else None
        ))

        # Single item
        cases.append(TestCase(
            id=f"UT-{name}-single",
            description=f"{name}: single {from_entity}",
            category="derived",
            target=name,
            inputs={
                entity: self._get_sample_entity(entity),
                f"{from_entity}_list": [{"amount": 1000}]
            },
            expected=1000 if agg_op == "sum" else 1 if agg_op == "count" else "/* expected */"
        ))

        # Multiple items
        cases.append(TestCase(
            id=f"UT-{name}-multiple",
            description=f"{name}: multiple {from_entity}",
            category="derived",
            target=name,
            inputs={
                entity: self._get_sample_entity(entity),
                f"{from_entity}_list": [{"amount": 1000}, {"amount": 2000}, {"amount": 3000}]
            },
            expected=6000 if agg_op == "sum" else 3 if agg_op == "count" else "/* expected */"
        ))

        return cases

    def _generate_conditional_cases(self, name: str, formula: dict, entity: str) -> list[TestCase]:
        """Generate test cases for conditional expressions"""
        cases = []

        # Then branch
        cases.append(TestCase(
            id=f"UT-{name}-then",
            description=f"{name}: condition true → then branch",
            category="derived",
            target=name,
            inputs={entity: self._get_sample_entity(entity), "_condition": True},
            expected="/* then value */"
        ))

        # Else branch
        cases.append(TestCase(
            id=f"UT-{name}-else",
            description=f"{name}: condition false → else branch",
            category="derived",
            target=name,
            inputs={entity: self._get_sample_entity(entity), "_condition": False},
            expected="/* else value */"
        ))

        return cases

    def _generate_error_case_tests(self) -> list[TestCase]:
        """Generate tests for function error cases"""
        cases = []

        for func_name, func_def in self.functions.items():
            # Note: schema uses "error" not "error_cases"
            for i, error_def in enumerate(func_def.get("error", [])):
                error_code = error_def.get("code", f"ERR-{i+1:03d}")
                when_expr = error_def.get("when", {})
                reason = error_def.get("reason", "")

                # Error should occur
                cases.append(TestCase(
                    id=f"UT-{func_name}-{error_code}",
                    description=f"{func_name}: {reason or error_code}",
                    category="error_case",
                    target=func_name,
                    inputs=self._make_error_trigger_inputs(when_expr, func_def),
                    expected={"success": False, "error": error_code},
                    is_error_case=True
                ))

                # Boundary: just under the error threshold
                boundary_inputs = self._make_error_boundary_inputs(when_expr, func_def)
                if boundary_inputs:
                    cases.append(TestCase(
                        id=f"UT-{func_name}-{error_code}-boundary",
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
                # Note: schema uses "expr" not "check"
                check_expr = pre.get("expr", {})

                # Precondition satisfied
                cases.append(TestCase(
                    id=f"UT-{func_name}-pre{i+1}-pass",
                    description=f"{func_name}: precondition {i+1} satisfied",
                    category="precondition",
                    target=func_name,
                    inputs=self._make_precondition_pass_inputs(check_expr, func_def),
                    expected={"precondition_passed": True}
                ))

                # Precondition violated
                cases.append(TestCase(
                    id=f"UT-{func_name}-pre{i+1}-fail",
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
                        id=f"UT-{entity_name}-{field_name}-{bv['label']}",
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
                    {"label": "negative", "value": -1, "should_be_valid": "/* depends on domain */", "description": "negative value"},
                    {"label": "large", "value": 2147483647, "should_be_valid": True, "description": "max int32"},
                ]
            elif field_type == "float":
                values = [
                    {"label": "zero", "value": 0.0, "should_be_valid": True, "description": "zero"},
                    {"label": "small", "value": 0.01, "should_be_valid": True, "description": "small positive"},
                    {"label": "negative", "value": -0.01, "should_be_valid": "/* depends */", "description": "small negative"},
                ]
            elif field_type == "string":
                values = [
                    {"label": "empty", "value": "", "should_be_valid": not required, "description": "empty string"},
                    {"label": "single", "value": "a", "should_be_valid": True, "description": "single char"},
                    {"label": "long", "value": "a" * 1000, "should_be_valid": "/* depends on max length */", "description": "very long string"},
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

        # Null check for required fields
        if required:
            values.append({
                "label": "null",
                "value": None,
                "should_be_valid": False,
                "description": "null for required field"
            })

        return values

    def _render_tests(self, test_cases: list[TestCase]) -> str:
        """Render test cases to code"""
        if self.typescript:
            return self._render_typescript(test_cases)
        else:
            return self._render_javascript(test_cases)

    def _render_typescript(self, test_cases: list[TestCase]) -> str:
        """Render as TypeScript/Jest"""
        lines = [
            "/**",
            " * Auto-generated Unit Tests from TRIR specification",
            " * @generated",
            " */",
            "",
            "import { describe, test, expect } from '@jest/globals';",
            "",
            "// TODO: Import your implementation",
            "// import { outstandingAmount, allocatePayment, ... } from './implementation';",
            "",
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
            lines.append(f"// ========== {category_titles.get(category, category)} ==========")
            lines.append("")

            # Group by target
            by_target: dict[str, list[TestCase]] = {}
            for tc in cases:
                if tc.target not in by_target:
                    by_target[tc.target] = []
                by_target[tc.target].append(tc)

            for target, target_cases in by_target.items():
                lines.append(f"describe('{target}', () => {{")

                for tc in target_cases:
                    lines.append(f"  test('{tc.id}: {self._escape(tc.description)}', () => {{")
                    lines.append(f"    // Inputs: {self._to_js_obj(tc.inputs)}")
                    lines.append(f"    // Expected: {self._to_js_obj(tc.expected)}")
                    lines.append("")

                    if tc.category == "derived":
                        lines.append(f"    // const result = {self._to_camel(target)}(...);")
                        lines.append(f"    // expect(result).toBe({self._to_js_obj(tc.expected)});")
                    elif tc.category == "error_case":
                        lines.append(f"    // const result = await {self._to_camel(target)}({self._to_js_obj(tc.inputs)});")
                        if tc.is_error_case:
                            lines.append(f"    // expect(result.success).toBe(false);")
                            lines.append(f"    // expect(result.error.code).toBe('{tc.expected.get('error', '')}');")
                        else:
                            lines.append(f"    // expect(result.success).toBe(true);")
                    elif tc.category == "precondition":
                        lines.append(f"    // Setup precondition test for {target}")
                        lines.append(f"    // expect(checkPrecondition(...)).toBe({not tc.is_error_case});")
                    elif tc.category == "boundary":
                        lines.append(f"    // const isValid = validate{self._to_pascal(target.split('.')[0])}({self._to_js_obj(tc.inputs)});")
                        lines.append(f"    // expect(isValid).toBe({self._to_js_obj(tc.expected.get('valid', True))});")

                    lines.append("  });")
                    lines.append("")

                lines.append("});")
                lines.append("")

        return "\n".join(lines)

    def _render_javascript(self, test_cases: list[TestCase]) -> str:
        """Render as JavaScript/Jest (no types)"""
        # Same as TypeScript but without type imports
        ts_code = self._render_typescript(test_cases)
        return ts_code.replace(
            "import { describe, test, expect } from '@jest/globals';",
            "// Jest globals are available automatically"
        )

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
        # Set numeric fields to 0
        for k, v in sample.items():
            if isinstance(v, (int, float)):
                sample[k] = 0
        return {entity: sample}

    def _make_positive_inputs(self, formula: dict, entity: str) -> dict:
        sample = self._get_sample_entity(entity)
        return {entity: sample}

    def _make_equal_inputs(self, formula: dict, entity: str) -> dict:
        sample = self._get_sample_entity(entity)
        return {entity: sample, "_note": "set operands to equal values"}

    def _make_comparison_true_inputs(self, op: str, formula: dict, entity: str) -> dict:
        return {entity: self._get_sample_entity(entity), "_condition_should_be": True}

    def _make_comparison_false_inputs(self, op: str, formula: dict, entity: str) -> dict:
        return {entity: self._get_sample_entity(entity), "_condition_should_be": False}

    def _make_error_trigger_inputs(self, when_expr: dict, func_def: dict) -> dict:
        """Generate inputs that trigger the error condition (make when_expr TRUE)"""
        if not when_expr:
            return {"_trigger_error": True, "_comment": "no when expression"}

        inputs = self._get_function_default_inputs(func_def)
        analyzed = self._analyze_expr_for_trigger(when_expr, func_def, trigger=True)
        inputs.update(analyzed)
        return inputs

    def _make_error_boundary_inputs(self, when_expr: dict, func_def: dict) -> dict | None:
        """Generate inputs at the boundary (just valid, error NOT triggered)"""
        if not when_expr:
            return None

        inputs = self._get_function_default_inputs(func_def)
        analyzed = self._analyze_expr_for_trigger(when_expr, func_def, trigger=False)
        inputs.update(analyzed)
        inputs["_boundary"] = True
        return inputs

    def _make_precondition_pass_inputs(self, check_expr: dict, func_def: dict) -> dict:
        """Generate inputs that satisfy the precondition (make check_expr TRUE)"""
        inputs = self._get_function_default_inputs(func_def)
        analyzed = self._analyze_expr_for_trigger(check_expr, func_def, trigger=True)
        inputs.update(analyzed)
        return inputs

    def _make_precondition_fail_inputs(self, check_expr: dict, func_def: dict) -> dict:
        """Generate inputs that violate the precondition (make check_expr FALSE)"""
        inputs = self._get_function_default_inputs(func_def)
        analyzed = self._analyze_expr_for_trigger(check_expr, func_def, trigger=False)
        inputs.update(analyzed)
        return inputs

    def _get_function_default_inputs(self, func_def: dict) -> dict:
        """Get default input values for a function from its input schema"""
        inputs = {}
        input_schema = func_def.get("input", {})
        for field_name, field_def in input_schema.items():
            inputs[field_name] = self._get_default_value(field_def.get("type"))
        return inputs

    def _analyze_expr_for_trigger(self, expr: dict, func_def: dict, trigger: bool) -> dict:
        """
        Analyze expression to generate inputs that trigger or avoid a condition.

        Args:
            expr: TRIR expression (binary, unary, ref, input, literal, etc.)
            func_def: Function definition for context
            trigger: If True, generate inputs that make expr TRUE; if False, make expr FALSE

        Returns:
            Dict of input values that achieve the desired condition
        """
        if not isinstance(expr, dict):
            return {}

        expr_type = expr.get("type")
        result = {}

        if expr_type == "binary":
            op = expr.get("op")
            left = expr.get("left", {})
            right = expr.get("right", {})

            # Extract input names and ref paths
            left_input = self._extract_input_name(left)
            right_input = self._extract_input_name(right)
            left_ref = self._extract_ref_path(left)
            right_ref = self._extract_ref_path(right)

            # Handle comparison operators
            if op in ("gt", "ge", "lt", "le", "eq", "ne"):
                result = self._generate_comparison_values(
                    op, left_input, right_input, left_ref, right_ref, trigger
                )

            # Handle logical operators (recursively analyze)
            elif op == "and":
                if trigger:
                    result.update(self._analyze_expr_for_trigger(left, func_def, True))
                    result.update(self._analyze_expr_for_trigger(right, func_def, True))
                else:
                    result.update(self._analyze_expr_for_trigger(left, func_def, False))

            elif op == "or":
                if trigger:
                    result.update(self._analyze_expr_for_trigger(left, func_def, True))
                else:
                    result.update(self._analyze_expr_for_trigger(left, func_def, False))
                    result.update(self._analyze_expr_for_trigger(right, func_def, False))

            elif op in ("in", "not_in"):
                right_literal = self._extract_literal(right)

                if left_input:
                    if (op == "in" and trigger) or (op == "not_in" and not trigger):
                        if isinstance(right_literal, list) and right_literal:
                            result[left_input] = right_literal[0]
                        else:
                            result[left_input] = "/* set to value IN list */"
                    else:
                        result[left_input] = "_INVALID_VALUE_"

                elif left_ref:
                    setup_key = f"_setup_{left_ref.replace('.', '_')}"
                    if (op == "in" and trigger) or (op == "not_in" and not trigger):
                        if isinstance(right_literal, list) and right_literal:
                            result[setup_key] = right_literal[0]
                        else:
                            result[setup_key] = "/* set to value IN list */"
                    else:
                        result[setup_key] = "_INVALID_STATE_"

        elif expr_type == "unary":
            op = expr.get("op")
            operand = expr.get("operand", {})
            if op == "not":
                result = self._analyze_expr_for_trigger(operand, func_def, not trigger)

        elif expr_type == "input":
            name = expr.get("name")
            if name:
                result[name] = trigger

        elif expr_type == "principal":
            op = expr.get("op")
            if op == "has_role":
                role = expr.get("role")
                if trigger:
                    result["_principal_role"] = role
                else:
                    result["_principal_role"] = f"_NOT_{role}_"
            elif op == "has_permission":
                perm = expr.get("permission")
                if trigger:
                    result["_principal_permission"] = perm
                else:
                    result["_principal_permission"] = f"_NOT_{perm}_"

        elif expr_type == "ref":
            path = expr.get("path")
            if path:
                setup_key = f"_setup_{path.replace('.', '_')}"
                result[setup_key] = trigger

        return result

    def _extract_input_name(self, expr: dict) -> str | None:
        """Extract input name from expression if it's an input reference"""
        if not isinstance(expr, dict):
            return None
        if expr.get("type") == "input":
            return expr.get("name")
        return None

    def _extract_ref_path(self, expr: dict) -> str | None:
        """Extract ref path from expression if it's a reference"""
        if not isinstance(expr, dict):
            return None
        if expr.get("type") == "ref":
            return expr.get("path")
        return None

    def _extract_literal(self, expr: dict) -> Any:
        """Extract literal value from expression if it's a literal"""
        if not isinstance(expr, dict):
            return None
        if expr.get("type") == "literal":
            return expr.get("value")
        return None

    def _generate_comparison_values(
        self, op: str, left_input: str | None, right_input: str | None,
        left_ref: str | None, right_ref: str | None, trigger: bool
    ) -> dict:
        """Generate input values for comparison operators."""
        result = {}
        base_value = 50000
        delta = 10000

        if trigger:
            value_map = {
                "gt": (base_value + delta, base_value),
                "ge": (base_value, base_value),
                "lt": (base_value - delta, base_value),
                "le": (base_value, base_value),
                "eq": (base_value, base_value),
                "ne": (base_value + delta, base_value),
            }
        else:
            value_map = {
                "gt": (base_value, base_value),
                "ge": (base_value - delta, base_value),
                "lt": (base_value, base_value),
                "le": (base_value + delta, base_value),
                "eq": (base_value + delta, base_value),
                "ne": (base_value, base_value),
            }

        left_val, right_val = value_map.get(op, (base_value, base_value))

        if left_input:
            result[left_input] = left_val
        if right_input:
            result[right_input] = right_val
        if left_ref:
            result[f"_setup_{left_ref.replace('.', '_')}"] = left_val
        if right_ref:
            result[f"_setup_{right_ref.replace('.', '_')}"] = right_val

        return result

    def _to_js_obj(self, obj: Any) -> str:
        """Convert to JS object literal string"""
        if obj is None:
            return "null"
        if isinstance(obj, bool):
            return "true" if obj else "false"
        if isinstance(obj, str):
            return f"'{obj}'"
        if isinstance(obj, (int, float)):
            return str(obj)
        if isinstance(obj, dict):
            items = ", ".join(f"{k}: {self._to_js_obj(v)}" for k, v in obj.items())
            return "{ " + items + " }"
        if isinstance(obj, list):
            items = ", ".join(self._to_js_obj(v) for v in obj)
            return "[" + items + "]"
        return str(obj)

    def _to_camel(self, name: str) -> str:
        parts = name.replace(".", "_").split("_")
        return parts[0] + "".join(p.capitalize() for p in parts[1:])

    def _to_pascal(self, name: str) -> str:
        return "".join(p.capitalize() for p in name.split("_"))

    def _escape(self, s: str) -> str:
        return s.replace("'", "\\'").replace("\n", " ")
