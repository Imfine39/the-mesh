"""Mesh Post-Condition Test Generator

Generates EXECUTABLE tests to verify function post-conditions using Repository pattern:
- Entity creation (create actions) - verifies repository.create() called correctly
- Entity updates (update actions) - verifies repository.update() called correctly
- Entity deletion (delete actions) - verifies repository.delete() called correctly

Tests use mock repositories to verify the implementation performs the specified side effects.
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
    inputs: dict[str, Any]  # Function inputs
    expected_fields: dict[str, Any]  # Fields expected in repository call
    existing_entity: dict[str, Any] | None  # For update/delete tests


class PostConditionGenerator:
    """Generates executable post-condition tests from TRIR specification"""

    def __init__(self, spec: dict[str, Any], import_modules: dict[str, str] | None = None):
        """
        Args:
            spec: TRIR specification
            import_modules: Map of function_name -> module path
        """
        self.spec = spec
        self.functions = spec.get("functions", {})
        self.entities = spec.get("state", {})  # Note: "state" not "entities"
        self.import_modules = import_modules or {}

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

                if "create" in action:
                    tests.append(self._generate_create_test(
                        func_name, func_def, action, i
                    ))
                elif "update" in action:
                    tests.append(self._generate_update_test(
                        func_name, func_def, action, i
                    ))
                elif "delete" in action:
                    tests.append(self._generate_delete_test(
                        func_name, func_def, action, i
                    ))

        return tests

    def _generate_create_test(
        self, func_name: str, func_def: dict, action: dict, index: int
    ) -> PostConditionTest:
        """Generate test for create action"""
        entity_name = action["create"]
        with_values = action.get("with", {})

        # Extract expected fields from the "with" clause
        expected_fields = {}
        for field_name, value_expr in with_values.items():
            expected_fields[field_name] = self._expr_to_input_ref(value_expr)

        return PostConditionTest(
            id=f"pc_{func_name}_creates_{self._to_snake(entity_name)}",
            description=f"{func_name}: should create {entity_name} with specified fields",
            function=func_name,
            action_type="create",
            target_entity=entity_name,
            inputs=self._get_sample_inputs(func_def),
            expected_fields=expected_fields,
            existing_entity=None,
        )

    def _generate_update_test(
        self, func_name: str, func_def: dict, action: dict, index: int
    ) -> PostConditionTest:
        """Generate test for update action"""
        entity_name = action["update"]
        set_values = action.get("set", {})

        expected_fields = {}
        for field_name, value_expr in set_values.items():
            expected_fields[field_name] = self._expr_to_input_ref(value_expr)

        return PostConditionTest(
            id=f"pc_{func_name}_updates_{self._to_snake(entity_name)}",
            description=f"{func_name}: should update {entity_name} with specified fields",
            function=func_name,
            action_type="update",
            target_entity=entity_name,
            inputs=self._get_sample_inputs(func_def),
            expected_fields=expected_fields,
            existing_entity=self._get_entity_sample(entity_name),
        )

    def _generate_delete_test(
        self, func_name: str, func_def: dict, action: dict, index: int
    ) -> PostConditionTest:
        """Generate test for delete action"""
        entity_name = action["delete"]

        return PostConditionTest(
            id=f"pc_{func_name}_deletes_{self._to_snake(entity_name)}",
            description=f"{func_name}: should delete {entity_name}",
            function=func_name,
            action_type="delete",
            target_entity=entity_name,
            inputs=self._get_sample_inputs(func_def),
            expected_fields={},
            existing_entity=self._get_entity_sample(entity_name),
        )

    def _expr_to_input_ref(self, expr: dict) -> str | Any:
        """Convert expression to input reference or literal"""
        if not isinstance(expr, dict):
            return expr

        expr_type = expr.get("type")

        if expr_type == "literal":
            return expr.get("value")
        elif expr_type == "input":
            return f"$input.{expr.get('name')}"
        else:
            return f"$expr"

    def _get_sample_inputs(self, func_def: dict) -> dict:
        """Get sample inputs for a function"""
        inputs = {}
        input_schema = func_def.get("input", {})
        for field_name, field_def in input_schema.items():
            inputs[field_name] = self._get_default_value(field_name, field_def.get("type"))
        return inputs

    def _get_entity_sample(self, entity_name: str) -> dict:
        """Get sample data for an entity"""
        entity = self.entities.get(entity_name, {})
        sample = {"id": f"{entity_name.upper()}-001"}
        for field_name, field_def in entity.get("fields", {}).items():
            if field_name != "id":
                sample[field_name] = self._get_default_value(field_name, field_def.get("type"))
        return sample

    def _get_default_value(self, field_name: str, field_type: Any) -> Any:
        """Get default value for a field type"""
        if isinstance(field_type, str):
            if field_type == "string":
                return f"{field_name.upper()}-001"
            defaults = {
                "text": "test content",
                "int": 100,
                "float": 100.0,
                "bool": True,
                "datetime": "2024-01-01T00:00:00Z",
                "date": "2024-01-01",
            }
            return defaults.get(field_type, "test")
        if isinstance(field_type, dict):
            if "enum" in field_type:
                return field_type["enum"][0]
            if "ref" in field_type:
                return "REF-001"
        return None

    def _generate_imports(self, function_names: set[str]) -> list[str]:
        """Generate import statements for functions"""
        lines = []
        module_funcs: dict[str, list[str]] = {}
        for func_name in sorted(function_names):
            module = self.import_modules.get(func_name)
            if module:
                if module not in module_funcs:
                    module_funcs[module] = []
                module_funcs[module].append(func_name)

        for module, funcs in sorted(module_funcs.items()):
            funcs_str = ", ".join(sorted(funcs))
            lines.append(f'from {module} import {funcs_str}')

        return lines

    def _render_pytest(self, tests: list[PostConditionTest]) -> str:
        """Render tests as executable pytest code"""
        # Collect functions used
        used_functions = {t.function for t in tests}

        lines = [
            '"""',
            'Auto-generated Post-Condition Tests from TRIR specification',
            '',
            'These tests verify that function implementations actually perform',
            'the side effects (create/update/delete) specified in the spec.',
            '',
            'Tests use mock repositories - implementation must accept repository parameter.',
            '@generated',
            '"""',
            '',
            'import pytest',
            'from unittest.mock import Mock, MagicMock',
            'from typing import Any, Protocol',
            '',
        ]

        # Add implementation imports
        impl_imports = self._generate_imports(used_functions)
        if impl_imports:
            lines.append('# Implementation imports')
            lines.extend(impl_imports)
            lines.append('')

        # Collect all entities used
        entities_used = set()
        for test in tests:
            entities_used.add(test.target_entity)

        # Generate Repository Protocol for each entity
        lines.append('# ========== Repository Interfaces ==========')
        lines.append('')
        for entity_name in sorted(entities_used):
            lines.extend(self._generate_repository_interface(entity_name))
            lines.append('')

        # Generate fixtures
        lines.append('# ========== Fixtures ==========')
        lines.append('')
        for entity_name in sorted(entities_used):
            lines.extend(self._generate_mock_fixture(entity_name))
            lines.append('')

        # Group by function
        by_function: dict[str, list[PostConditionTest]] = {}
        for test in tests:
            if test.function not in by_function:
                by_function[test.function] = []
            by_function[test.function].append(test)

        # Generate test classes
        lines.append('# ========== Post-Condition Tests ==========')
        lines.append('')

        for func_name, func_tests in by_function.items():
            lines.append(f"class TestPostCondition{self._to_pascal(func_name)}:")
            lines.append(f'    """Post-condition tests for {func_name}"""')
            lines.append('')

            for test in func_tests:
                lines.extend(self._render_test_method(test))
                lines.append('')

            lines.append('')

        return '\n'.join(lines)

    def _generate_repository_interface(self, entity_name: str) -> list[str]:
        """Generate Repository Protocol for an entity"""
        return [
            f'class {entity_name}Repository(Protocol):',
            f'    """Repository interface for {entity_name}"""',
            f'    def create(self, data: dict[str, Any]) -> dict[str, Any]: ...',
            f'    def get(self, id: str) -> dict[str, Any] | None: ...',
            f'    def get_all(self) -> list[dict[str, Any]]: ...',
            f'    def update(self, id: str, data: dict[str, Any]) -> dict[str, Any]: ...',
            f'    def delete(self, id: str) -> bool: ...',
        ]

    def _generate_mock_fixture(self, entity_name: str) -> list[str]:
        """Generate mock fixture for an entity repository"""
        snake = self._to_snake(entity_name)
        sample = self._get_entity_sample(entity_name)
        sample_repr = self._to_py_repr(sample)

        return [
            '@pytest.fixture',
            f'def mock_{snake}_repository():',
            f'    """Mock {entity_name} repository"""',
            f'    repo = Mock(spec={entity_name}Repository)',
            f'    repo.create.return_value = {sample_repr}',
            f'    repo.get.return_value = {sample_repr}',
            f'    repo.get_all.return_value = []',
            f'    repo.update.return_value = {sample_repr}',
            f'    repo.delete.return_value = True',
            f'    return repo',
        ]

    def _render_test_method(self, test: PostConditionTest) -> list[str]:
        """Render a single test method"""
        lines = []
        entity_snake = self._to_snake(test.target_entity)
        fixture_name = f"mock_{entity_snake}_repository"

        lines.append(f"    def test_{test.id}(self, {fixture_name}):")
        lines.append(f'        """')
        lines.append(f'        {test.description}')
        lines.append(f'        """')

        # Arrange
        lines.append('        # Arrange')
        lines.append(f'        input_data = {self._to_py_repr(test.inputs)}')

        if test.existing_entity:
            lines.append(f'        existing = {self._to_py_repr(test.existing_entity)}')
            lines.append(f'        {fixture_name}.get.return_value = existing')

        lines.append('')

        # Act - uncomment if import available
        has_import = test.function in self.import_modules
        comment = "" if has_import else "# "

        lines.append('        # Act')
        lines.append(f'        {comment}result = {test.function}(input_data, repository={fixture_name})')
        lines.append('')

        # Assert
        lines.append('        # Assert')

        if test.action_type == "create":
            lines.append(f'        {fixture_name}.create.assert_called_once()')
            lines.append(f'        call_args = {fixture_name}.create.call_args[0][0]')
            lines.append('')

            for field, expected in test.expected_fields.items():
                if isinstance(expected, str) and expected.startswith("$input."):
                    input_field = expected[7:]
                    lines.append(f'        assert "{field}" in call_args, "Field \'{field}\' was not saved"')
                    lines.append(f'        assert call_args["{field}"] == input_data["{input_field}"]')
                else:
                    lines.append(f'        assert "{field}" in call_args, "Field \'{field}\' was not saved"')
                    lines.append(f'        assert call_args["{field}"] == {repr(expected)}')

        elif test.action_type == "update":
            lines.append(f'        {fixture_name}.update.assert_called_once()')
            lines.append(f'        call_args = {fixture_name}.update.call_args')
            lines.append(f'        update_id = call_args[0][0]')
            lines.append(f'        update_data = call_args[0][1]')
            lines.append('')

            for field, expected in test.expected_fields.items():
                if isinstance(expected, str) and expected.startswith("$input."):
                    input_field = expected[7:]
                    lines.append(f'        assert "{field}" in update_data, "Field \'{field}\' was not updated"')
                    lines.append(f'        assert update_data["{field}"] == input_data["{input_field}"]')
                else:
                    lines.append(f'        assert "{field}" in update_data')
                    lines.append(f'        assert update_data["{field}"] == {repr(expected)}')

        elif test.action_type == "delete":
            lines.append(f'        {fixture_name}.delete.assert_called_once()')
            lines.append(f'        deleted_id = {fixture_name}.delete.call_args[0][0]')
            lines.append(f'        assert deleted_id == existing["id"]')

        return lines

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
            items = ", ".join(f'"{k}": {self._to_py_repr(v)}' for k, v in obj.items())
            return "{" + items + "}"
        if isinstance(obj, list):
            items = ", ".join(self._to_py_repr(v) for v in obj)
            return "[" + items + "]"
        return repr(obj)
