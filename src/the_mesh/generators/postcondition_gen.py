"""Mesh Post-Condition Test Generator

Generates tests to verify function post-conditions:
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
    setup: dict[str, Any]  # Entities/data to set up before test
    inputs: dict[str, Any]  # Function inputs
    assertions: list[dict[str, Any]]  # What to verify after function call


class PostConditionGenerator:
    """Generates post-condition tests from TRIR specification"""

    def __init__(self, spec: dict[str, Any]):
        self.spec = spec
        self.functions = spec.get("functions", {})
        self.entities = spec.get("entities", {})

    def generate_all(self) -> str:
        """Generate all post-condition tests"""
        tests = self._generate_tests()
        return self._render_pytest(tests)

    def generate_for_function(self, func_name: str) -> str:
        """Generate post-condition tests for a specific function"""
        tests = self._generate_tests(func_filter=func_name)
        return self._render_pytest(tests)

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

        # Main creation test
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
            id=f"post_{func_name}_creates_{entity_name}_{index+1}",
            description=f"{func_name}: should create {entity_name} - {reason}",
            function=func_name,
            action_type="create",
            target_entity=entity_name,
            setup=self._get_function_setup(func_def),
            inputs=self._get_function_inputs(func_def),
            assertions=assertions,
        ))

        # Entity existence test
        tests.append(PostConditionTest(
            id=f"post_{func_name}_{entity_name}_exists_{index+1}",
            description=f"{func_name}: {entity_name} should exist after call",
            function=func_name,
            action_type="create",
            target_entity=entity_name,
            setup=self._get_function_setup(func_def),
            inputs=self._get_function_inputs(func_def),
            assertions=[{
                "type": "entity_exists",
                "entity": entity_name,
            }],
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
        target_expr = action.get("target", {})

        # Field update tests
        assertions = []
        for field_name, value_expr in set_values.items():
            expected = self._expr_to_expected(value_expr)
            assertions.append({
                "type": "field_equals",
                "entity": entity_name,
                "field": field_name,
                "expected": expected,
            })

        # Setup includes the entity to be updated
        setup = self._get_function_setup(func_def)
        setup[f"_existing_{entity_name}"] = self._get_entity_sample(entity_name)

        tests.append(PostConditionTest(
            id=f"post_{func_name}_updates_{entity_name}_{index+1}",
            description=f"{func_name}: should update {entity_name} - {reason}",
            function=func_name,
            action_type="update",
            target_entity=entity_name,
            setup=setup,
            inputs=self._get_function_inputs(func_def),
            assertions=assertions,
        ))

        # Unchanged field test - verify fields NOT in set are preserved
        entity_def = self.entities.get(entity_name, {})
        unchanged_fields = [
            f for f in entity_def.get("fields", {}).keys()
            if f not in set_values and f not in ("id", "created_at", "updated_at")
        ]

        if unchanged_fields:
            tests.append(PostConditionTest(
                id=f"post_{func_name}_{entity_name}_unchanged_{index+1}",
                description=f"{func_name}: unchanged fields should be preserved",
                function=func_name,
                action_type="update",
                target_entity=entity_name,
                setup=setup,
                inputs=self._get_function_inputs(func_def),
                assertions=[{
                    "type": "fields_unchanged",
                    "entity": entity_name,
                    "fields": unchanged_fields[:3],  # Limit for readability
                }],
            ))

        return tests

    def _generate_delete_tests(
        self, func_name: str, func_def: dict,
        action: dict, reason: str, index: int
    ) -> list[PostConditionTest]:
        """Generate tests for delete actions"""
        tests = []
        entity_name = action["delete"]
        target_expr = action.get("target", {})

        # Setup includes the entity to be deleted
        setup = self._get_function_setup(func_def)
        setup[f"_existing_{entity_name}"] = self._get_entity_sample(entity_name)

        tests.append(PostConditionTest(
            id=f"post_{func_name}_deletes_{entity_name}_{index+1}",
            description=f"{func_name}: should delete {entity_name} - {reason}",
            function=func_name,
            action_type="delete",
            target_entity=entity_name,
            setup=setup,
            inputs=self._get_function_inputs(func_def),
            assertions=[{
                "type": "entity_not_exists",
                "entity": entity_name,
            }],
        ))

        return tests

    def _expr_to_expected(self, expr: dict) -> Any:
        """Convert expression to expected value for assertion"""
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
            if op == "today":
                return "$date.today"
            elif op == "now":
                return "$datetime.now"
            return f"$date.{op}"
        else:
            return f"$expr({expr_type})"

    def _get_function_setup(self, func_def: dict) -> dict:
        """Get setup requirements for a function"""
        setup = {}
        # Look at input refs to determine what entities need to exist
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
            defaults = {
                "string": "TEST_VALUE",
                "int": 10000,
                "float": 100.0,
                "bool": True,
                "datetime": "2024-01-01T00:00:00Z",
            }
            return defaults.get(field_type, None)
        if isinstance(field_type, dict):
            if "enum" in field_type:
                return field_type["enum"][0]
            if "ref" in field_type:
                return "REF_TEST_001"
        return None

    def _render_pytest(self, tests: list[PostConditionTest]) -> str:
        """Render tests as pytest code"""
        lines = [
            '"""',
            'Auto-generated Post-Condition Tests from TRIR specification',
            '',
            'These tests verify that function implementations actually perform',
            'the side effects (create/update/delete) specified in the spec.',
            '',
            '@generated',
            '"""',
            '',
            'import pytest',
            'from datetime import datetime, date',
            'from typing import Any',
            '',
            '# TODO: Import your implementation and database fixtures',
            '# from your_module import execute_clearing, reverse_clearing, ...',
            '# from your_fixtures import db, create_test_entity, ...',
            '',
        ]

        # Group by function
        by_function: dict[str, list[PostConditionTest]] = {}
        for test in tests:
            if test.function not in by_function:
                by_function[test.function] = []
            by_function[test.function].append(test)

        for func_name, func_tests in by_function.items():
            lines.append(f"class TestPostCondition_{self._to_pascal(func_name)}:")
            lines.append(f'    """Post-condition tests for {func_name}"""')
            lines.append("")

            for test in func_tests:
                lines.append(f"    def test_{test.id}(self):")
                lines.append(f'        """')
                lines.append(f'        {test.description}')
                lines.append(f'        """')

                # Setup section
                lines.append("        # Setup")
                if test.setup:
                    for setup_key, setup_val in test.setup.items():
                        lines.append(f"        # {setup_key} = {self._to_py_repr(setup_val)}")
                else:
                    lines.append("        # No setup required")

                lines.append("")

                # Execute section
                lines.append("        # Execute")
                lines.append(f"        # result = {self._to_snake(test.function)}({self._to_py_repr(test.inputs)})")
                lines.append("")

                # Assert section
                lines.append("        # Assert")
                for assertion in test.assertions:
                    a_type = assertion.get("type")
                    entity = assertion.get("entity", "")

                    if a_type == "entity_exists":
                        lines.append(f"        # created = db.get_{self._to_snake(entity)}(result.{self._to_snake(entity)}_id)")
                        lines.append(f"        # assert created is not None")

                    elif a_type == "entity_not_exists":
                        lines.append(f"        # deleted = db.get_{self._to_snake(entity)}(original_{self._to_snake(entity)}_id)")
                        lines.append(f"        # assert deleted is None")

                    elif a_type == "field_equals":
                        field = assertion.get("field", "")
                        expected = assertion.get("expected", "")
                        lines.append(f"        # assert entity.{field} == {self._format_expected(expected)}")

                    elif a_type == "fields_unchanged":
                        fields = assertion.get("fields", [])
                        for field in fields:
                            lines.append(f"        # assert updated.{field} == original.{field}")

                lines.append("")
                lines.append("        pytest.skip('TODO: Implement with actual database/repository')")
                lines.append("")

            lines.append("")

        return "\n".join(lines)

    def _format_expected(self, expected: Any) -> str:
        """Format expected value for assertion"""
        if isinstance(expected, str):
            if expected.startswith("$input."):
                field = expected[7:]
                return f"input_data['{field}']"
            elif expected.startswith("$ref."):
                path = expected[5:]
                return f"# {path}"
            elif expected.startswith("$date."):
                op = expected[6:]
                if op == "today":
                    return "date.today()"
                return f"# {op}"
            elif expected.startswith("$datetime."):
                op = expected[10:]
                if op == "now":
                    return "datetime.now()  # approximate"
                return f"# {op}"
            elif expected.startswith("$expr"):
                return f"# {expected}"
            else:
                return repr(expected)
        return repr(expected)

    def _to_pascal(self, name: str) -> str:
        """Convert to PascalCase"""
        return "".join(p.capitalize() for p in name.replace(".", "_").split("_"))

    def _to_snake(self, name: str) -> str:
        """Convert to snake_case"""
        return name.replace(".", "_").lower()

    def _to_py_repr(self, obj: Any) -> str:
        """Convert to Python repr"""
        if obj is None:
            return "None"
        if isinstance(obj, bool):
            return "True" if obj else "False"
        if isinstance(obj, str):
            return repr(obj)
        if isinstance(obj, dict):
            items = ", ".join(f"'{k}': {self._to_py_repr(v)}" for k, v in obj.items())
            return "{" + items + "}"
        if isinstance(obj, list):
            items = ", ".join(self._to_py_repr(v) for v in obj)
            return "[" + items + "]"
        return repr(obj)
