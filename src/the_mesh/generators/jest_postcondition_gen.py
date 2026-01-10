"""Mesh Post-Condition Test Generator for Jest

Generates Jest tests to verify function post-conditions:
- Entity creation (create actions)
- Entity updates (update actions)
- Entity deletion (delete actions)
- Field value verification

These tests detect implementation drift by ensuring the implementation
actually performs the side effects specified in the TRIR spec.
"""

from typing import Any
from dataclasses import dataclass


@dataclass
class PostConditionTest:
    """Represents a single post-condition test case"""
    id: str
    description: str
    function: str
    action_type: str  # 'create', 'update', 'delete'
    target_entity: str
    setup: dict[str, Any]
    inputs: dict[str, Any]
    assertions: list[dict[str, Any]]


class JestPostConditionGenerator:
    """Generates Jest post-condition tests from TRIR specification"""

    def __init__(self, spec: dict[str, Any], typescript: bool = True):
        self.spec = spec
        self.functions = spec.get("functions", {})
        self.entities = spec.get("entities", {})
        self.typescript = typescript

    def generate_all(self) -> str:
        """Generate all post-condition tests"""
        tests = self._generate_tests()
        return self._render_jest(tests)

    def generate_for_function(self, func_name: str) -> str:
        """Generate post-condition tests for a specific function"""
        tests = self._generate_tests(func_filter=func_name)
        return self._render_jest(tests)

    def _generate_tests(self, func_filter: str | None = None) -> list[PostConditionTest]:
        """Generate test cases from spec"""
        tests = []

        for func_name, func_def in self.functions.items():
            if func_filter and func_name != func_filter:
                continue

            posts = func_def.get("post", [])
            for i, post in enumerate(posts):
                action = post.get("action", {})
                reason = post.get("reason", "")

                if "create" in action:
                    tests.extend(self._generate_create_tests(
                        func_name, func_def, action, reason, i
                    ))
                elif "update" in action:
                    tests.extend(self._generate_update_tests(
                        func_name, func_def, action, reason, i
                    ))
                elif "delete" in action:
                    tests.extend(self._generate_delete_tests(
                        func_name, func_def, action, reason, i
                    ))

        return tests

    def _generate_create_tests(
        self, func_name: str, func_def: dict,
        action: dict, reason: str, index: int
    ) -> list[PostConditionTest]:
        """Generate tests for create actions"""
        tests = []
        entity_name = action["create"]
        with_values = action.get("with", {})

        assertions = []
        for field_name, value_expr in with_values.items():
            expected = self._expr_to_expected(value_expr)
            assertions.append({
                "type": "field_equals",
                "entity": entity_name,
                "field": field_name,
                "expected": expected,
            })

        tests.append(PostConditionTest(
            id=f"post-{func_name}-creates-{entity_name}-{index+1}",
            description=f"{func_name}: should create {entity_name} - {reason}",
            function=func_name,
            action_type="create",
            target_entity=entity_name,
            setup=self._get_function_setup(func_def),
            inputs=self._get_function_inputs(func_def),
            assertions=assertions,
        ))

        tests.append(PostConditionTest(
            id=f"post-{func_name}-{entity_name}-exists-{index+1}",
            description=f"{func_name}: {entity_name} should exist after call",
            function=func_name,
            action_type="create",
            target_entity=entity_name,
            setup=self._get_function_setup(func_def),
            inputs=self._get_function_inputs(func_def),
            assertions=[{"type": "entity_exists", "entity": entity_name}],
        ))

        return tests

    def _generate_update_tests(
        self, func_name: str, func_def: dict,
        action: dict, reason: str, index: int
    ) -> list[PostConditionTest]:
        """Generate tests for update actions"""
        tests = []
        entity_name = action["update"]
        set_values = action.get("set", {})

        assertions = []
        for field_name, value_expr in set_values.items():
            expected = self._expr_to_expected(value_expr)
            assertions.append({
                "type": "field_equals",
                "entity": entity_name,
                "field": field_name,
                "expected": expected,
            })

        setup = self._get_function_setup(func_def)
        setup[f"_existing_{entity_name}"] = self._get_entity_sample(entity_name)

        tests.append(PostConditionTest(
            id=f"post-{func_name}-updates-{entity_name}-{index+1}",
            description=f"{func_name}: should update {entity_name} - {reason}",
            function=func_name,
            action_type="update",
            target_entity=entity_name,
            setup=setup,
            inputs=self._get_function_inputs(func_def),
            assertions=assertions,
        ))

        return tests

    def _generate_delete_tests(
        self, func_name: str, func_def: dict,
        action: dict, reason: str, index: int
    ) -> list[PostConditionTest]:
        """Generate tests for delete actions"""
        tests = []
        entity_name = action["delete"]

        setup = self._get_function_setup(func_def)
        setup[f"_existing_{entity_name}"] = self._get_entity_sample(entity_name)

        tests.append(PostConditionTest(
            id=f"post-{func_name}-deletes-{entity_name}-{index+1}",
            description=f"{func_name}: should delete {entity_name} - {reason}",
            function=func_name,
            action_type="delete",
            target_entity=entity_name,
            setup=setup,
            inputs=self._get_function_inputs(func_def),
            assertions=[{"type": "entity_not_exists", "entity": entity_name}],
        ))

        return tests

    def _expr_to_expected(self, expr: dict) -> Any:
        """Convert expression to expected value"""
        if not isinstance(expr, dict):
            return expr

        expr_type = expr.get("type")
        if expr_type == "literal":
            return expr.get("value")
        elif expr_type == "input":
            return f"$input.{expr.get('name')}"
        elif expr_type == "ref":
            return f"$ref.{expr.get('path')}"
        elif expr_type == "date":
            op = expr.get("op")
            return f"$date.{op}"
        return f"$expr({expr_type})"

    def _get_function_setup(self, func_def: dict) -> dict:
        """Get setup requirements for a function"""
        setup = {}
        input_schema = func_def.get("input", {})
        for field_name, field_def in input_schema.items():
            field_type = field_def.get("type", {})
            if isinstance(field_type, dict) and "ref" in field_type:
                ref_entity = field_type["ref"].split(".")[0]
                setup[f"_ref_{ref_entity}"] = self._get_entity_sample(ref_entity)
        return setup

    def _get_function_inputs(self, func_def: dict) -> dict:
        """Get sample inputs for a function"""
        inputs = {}
        input_schema = func_def.get("input", {})
        for field_name, field_def in input_schema.items():
            inputs[field_name] = self._get_default_value(field_def.get("type"))
        return inputs

    def _get_entity_sample(self, entity_name: str) -> dict:
        """Get sample data for an entity"""
        entity = self.entities.get(entity_name, {})
        sample = {"id": f"{entity_name.upper()}_TEST_001"}
        for field_name, field_def in entity.get("fields", {}).items():
            sample[field_name] = self._get_default_value(field_def.get("type"))
        return sample

    def _get_default_value(self, field_type: Any) -> Any:
        """Get default value for a field type"""
        if isinstance(field_type, str):
            return {
                "string": "TEST_VALUE",
                "int": 10000,
                "float": 100.0,
                "bool": True,
                "datetime": "2024-01-01T00:00:00Z",
            }.get(field_type)
        if isinstance(field_type, dict):
            if "enum" in field_type:
                return field_type["enum"][0]
            if "ref" in field_type:
                return "REF_TEST_001"
        return None

    def _render_jest(self, tests: list[PostConditionTest]) -> str:
        """Render tests as Jest code"""
        lines = [
            "/**",
            " * Auto-generated Post-Condition Tests from TRIR specification",
            " *",
            " * These tests verify that function implementations actually perform",
            " * the side effects (create/update/delete) specified in the spec.",
            " *",
            " * @generated",
            " */",
            "",
        ]

        if self.typescript:
            lines.append("import { describe, test, expect, beforeEach } from '@jest/globals';")
        else:
            lines.append("// Jest globals are available automatically")

        lines.extend([
            "",
            "// TODO: Import your implementation and database fixtures",
            "// import { executeClearing, reverseClearing, ... } from './implementation';",
            "// import { db, createTestEntity, ... } from './fixtures';",
            "",
        ])

        by_function: dict[str, list[PostConditionTest]] = {}
        for test in tests:
            if test.function not in by_function:
                by_function[test.function] = []
            by_function[test.function].append(test)

        for func_name, func_tests in by_function.items():
            lines.append(f"describe('PostCondition: {func_name}', () => {{")

            for test in func_tests:
                lines.append(f"  test('{test.id}: {self._escape(test.description)}', async () => {{")

                lines.append("    // Setup")
                if test.setup:
                    for key, val in test.setup.items():
                        lines.append(f"    // {key} = {self._to_js(val)};")

                lines.append("")
                lines.append("    // Execute")
                lines.append(f"    // const result = await {self._to_camel(test.function)}({self._to_js(test.inputs)});")
                lines.append("")

                lines.append("    // Assert")
                for assertion in test.assertions:
                    a_type = assertion.get("type")
                    entity = assertion.get("entity", "")

                    if a_type == "entity_exists":
                        lines.append(f"    // const created = await db.get{self._to_pascal(entity)}(result.{self._to_camel(entity)}Id);")
                        lines.append("    // expect(created).not.toBeNull();")
                    elif a_type == "entity_not_exists":
                        lines.append(f"    // const deleted = await db.get{self._to_pascal(entity)}(original{self._to_pascal(entity)}Id);")
                        lines.append("    // expect(deleted).toBeNull();")
                    elif a_type == "field_equals":
                        field = assertion.get("field", "")
                        expected = assertion.get("expected", "")
                        lines.append(f"    // expect(entity.{self._to_camel(field)}).toBe({self._format_expected(expected)});")

                lines.append("  });")
                lines.append("")

            lines.append("});")
            lines.append("")

        return "\n".join(lines)

    def _format_expected(self, expected: Any) -> str:
        """Format expected value for assertion"""
        if isinstance(expected, str):
            if expected.startswith("$input."):
                return f"inputData.{self._to_camel(expected[7:])}"
            elif expected.startswith("$date."):
                op = expected[6:]
                if op == "today":
                    return "new Date().toISOString().split('T')[0]"
                elif op == "now":
                    return "expect.any(Date)"
            return repr(expected)
        return self._to_js(expected)

    def _to_js(self, obj: Any) -> str:
        """Convert to JS object literal"""
        if obj is None:
            return "null"
        if isinstance(obj, bool):
            return "true" if obj else "false"
        if isinstance(obj, str):
            return f"'{obj}'"
        if isinstance(obj, (int, float)):
            return str(obj)
        if isinstance(obj, dict):
            items = ", ".join(f"{self._to_camel(k)}: {self._to_js(v)}" for k, v in obj.items())
            return "{ " + items + " }"
        if isinstance(obj, list):
            return "[" + ", ".join(self._to_js(v) for v in obj) + "]"
        return str(obj)

    def _to_camel(self, name: str) -> str:
        parts = name.replace(".", "_").split("_")
        return parts[0] + "".join(p.capitalize() for p in parts[1:])

    def _to_pascal(self, name: str) -> str:
        return "".join(p.capitalize() for p in name.replace(".", "_").split("_"))

    def _escape(self, s: str) -> str:
        return s.replace("'", "\\'").replace("\n", " ")
