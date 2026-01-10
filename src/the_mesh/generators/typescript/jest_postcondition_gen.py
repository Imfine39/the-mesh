"""Mesh Post-Condition Test Generator for Jest

Generates EXECUTABLE Jest tests to verify function post-conditions using Repository pattern:
- Entity creation (create actions) - verifies repository.create() called correctly
- Entity updates (update actions) - verifies repository.update() called correctly
- Entity deletion (delete actions) - verifies repository.delete() called correctly

Tests use mock repositories - implementation must accept repository parameter.
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
    inputs: dict[str, Any]
    expected_fields: dict[str, Any]
    existing_entity: dict[str, Any] | None


class JestPostConditionGenerator:
    """Generates executable Jest post-condition tests from TRIR specification"""

    def __init__(self, spec: dict[str, Any], typescript: bool = True,
                 import_modules: dict[str, str] | None = None):
        """
        Args:
            spec: TRIR specification
            typescript: Whether to generate TypeScript (True) or JavaScript (False)
            import_modules: Map of function_name -> module path
                           e.g. {"createOrder": "./src/orders/createOrder"}
        """
        self.spec = spec
        self.functions = spec.get("functions", {})
        self.entities = spec.get("state", {})  # Note: "state" not "entities"
        self.typescript = typescript
        self.import_modules = import_modules or {}

    def _generate_imports(self, function_names: set[str]) -> list[str]:
        """Generate import statements for functions (grouped by module)"""
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
            lines.append(f"import {{ {funcs_str} }} from '{module}';")
        return lines

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

        expected_fields = {}
        for field_name, value_expr in with_values.items():
            expected_fields[field_name] = self._expr_to_input_ref(value_expr)

        return PostConditionTest(
            id=f"pc-{func_name}-creates-{self._to_kebab(entity_name)}",
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
            id=f"pc-{func_name}-updates-{self._to_kebab(entity_name)}",
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
            id=f"pc-{func_name}-deletes-{self._to_kebab(entity_name)}",
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
            return "$expr"

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

    def _render_jest(self, tests: list[PostConditionTest]) -> str:
        """Render tests as executable Jest code"""
        # Collect functions used
        used_functions = {t.function for t in tests}

        lines = [
            '/**',
            ' * Auto-generated Post-Condition Tests from TRIR specification',
            ' *',
            ' * These tests verify that function implementations actually perform',
            ' * the side effects (create/update/delete) specified in the spec.',
            ' *',
            ' * Tests use mock repositories - implementation must accept repository parameter.',
            ' * @generated',
            ' */',
            '',
        ]

        # Jest imports
        if self.typescript:
            lines.append("import { describe, it, expect } from '@jest/globals';")

        # Implementation imports
        impl_imports = self._generate_imports(used_functions)
        if impl_imports:
            lines.append('')
            lines.append('// Implementation imports')
            lines.extend(impl_imports)
        lines.append('')

        # Collect all entities used
        entities_used = set()
        for test in tests:
            entities_used.add(test.target_entity)

        # Generate TypeScript interfaces if needed
        if self.typescript:
            lines.append('// ========== Repository Interfaces ==========')
            lines.append('')
            for entity_name in sorted(entities_used):
                lines.extend(self._generate_repository_interface(entity_name))
                lines.append('')

        # Generate mock factory
        lines.append('// ========== Mock Factories ==========')
        lines.append('')
        for entity_name in sorted(entities_used):
            lines.extend(self._generate_mock_factory(entity_name))
            lines.append('')

        # Group tests by function
        by_function: dict[str, list[PostConditionTest]] = {}
        for test in tests:
            if test.function not in by_function:
                by_function[test.function] = []
            by_function[test.function].append(test)

        # Generate test suites
        lines.append('// ========== Post-Condition Tests ==========')
        lines.append('')

        for func_name, func_tests in by_function.items():
            lines.append(f"describe('PostCondition: {func_name}', () => {{")

            for test in func_tests:
                lines.extend(self._render_test(test))

            lines.append('});')
            lines.append('')

        return '\n'.join(lines)

    def _generate_repository_interface(self, entity_name: str) -> list[str]:
        """Generate TypeScript interface for repository"""
        return [
            f'interface {entity_name}Repository {{',
            f'  create(data: Partial<{entity_name}>): Promise<{entity_name}>;',
            f'  get(id: string): Promise<{entity_name} | null>;',
            f'  getAll(): Promise<{entity_name}[]>;',
            f'  update(id: string, data: Partial<{entity_name}>): Promise<{entity_name}>;',
            f'  delete(id: string): Promise<boolean>;',
            '}',
            '',
            f'interface {entity_name} {{',
            f'  id: string;',
            f'  [key: string]: unknown;',
            '}',
        ]

    def _generate_mock_factory(self, entity_name: str) -> list[str]:
        """Generate mock repository factory"""
        type_hint = f': {entity_name}Repository' if self.typescript else ''
        data_type = f': Record<string, {entity_name}>' if self.typescript else ''

        return [
            f'function createMock{entity_name}Repository(){type_hint} {{',
            f'  const mockData{data_type} = {{}};',
            f'  return {{',
            f'    create: jest.fn().mockImplementation((data) => Promise.resolve({{ id: "NEW-001", ...data }})),',
            f'    get: jest.fn().mockImplementation((id) => Promise.resolve(mockData[id] || null)),',
            f'    getAll: jest.fn().mockResolvedValue([]),',
            f'    update: jest.fn().mockImplementation((id, data) => Promise.resolve({{ ...mockData[id], ...data }})),',
            f'    delete: jest.fn().mockResolvedValue(true),',
            f'    _setData: (id{": string" if self.typescript else ""}, data{f": {entity_name}" if self.typescript else ""}) => {{ mockData[id] = data; }},',
            f'  }};',
            '}',
        ]

    def _render_test(self, test: PostConditionTest) -> list[str]:
        """Render a single test"""
        lines = []
        entity_name = test.target_entity

        lines.append('')
        lines.append(f"  it('{test.description}', async () => {{")

        # Arrange
        lines.append('    // Arrange')
        lines.append(f'    const repository = createMock{entity_name}Repository();')
        lines.append(f'    const inputData = {self._to_js_object(test.inputs)};')

        if test.existing_entity:
            lines.append(f'    const existing = {self._to_js_object(test.existing_entity)};')
            lines.append(f'    repository._setData(existing.id, existing);')
            lines.append(f'    repository.get.mockResolvedValue(existing);')

        lines.append('')

        # Act
        has_import = test.function in self.import_modules
        comment = "" if has_import else "// "

        lines.append('    // Act')
        lines.append(f'    {comment}const result = await {test.function}(inputData, {{ repository }});')
        lines.append('')

        # Assert
        lines.append('    // Assert')

        if test.action_type == "create":
            lines.append('    expect(repository.create).toHaveBeenCalledTimes(1);')
            lines.append('    const callArgs = repository.create.mock.calls[0][0];')
            lines.append('')

            for field, expected in test.expected_fields.items():
                if isinstance(expected, str) and expected.startswith("$input."):
                    input_field = expected[7:]
                    lines.append(f'    expect(callArgs).toHaveProperty("{field}");')
                    lines.append(f'    expect(callArgs.{field}).toBe(inputData.{input_field});')
                else:
                    lines.append(f'    expect(callArgs).toHaveProperty("{field}");')
                    lines.append(f'    expect(callArgs.{field}).toBe({self._to_js_value(expected)});')

        elif test.action_type == "update":
            lines.append('    expect(repository.update).toHaveBeenCalledTimes(1);')
            lines.append('    const [updateId, updateData] = repository.update.mock.calls[0];')
            lines.append('')

            for field, expected in test.expected_fields.items():
                if isinstance(expected, str) and expected.startswith("$input."):
                    input_field = expected[7:]
                    lines.append(f'    expect(updateData).toHaveProperty("{field}");')
                    lines.append(f'    expect(updateData.{field}).toBe(inputData.{input_field});')
                else:
                    lines.append(f'    expect(updateData).toHaveProperty("{field}");')
                    lines.append(f'    expect(updateData.{field}).toBe({self._to_js_value(expected)});')

        elif test.action_type == "delete":
            lines.append('    expect(repository.delete).toHaveBeenCalledTimes(1);')
            lines.append('    expect(repository.delete).toHaveBeenCalledWith(existing.id);')

        lines.append('  });')

        return lines

    def _to_js_object(self, obj: dict) -> str:
        """Convert dict to JavaScript object literal"""
        items = []
        for k, v in obj.items():
            items.append(f'{k}: {self._to_js_value(v)}')
        return '{ ' + ', '.join(items) + ' }'

    def _to_js_value(self, val: Any) -> str:
        """Convert Python value to JavaScript value"""
        if val is None:
            return 'null'
        if isinstance(val, bool):
            return 'true' if val else 'false'
        if isinstance(val, str):
            return f'"{val}"'
        if isinstance(val, (int, float)):
            return str(val)
        if isinstance(val, dict):
            return self._to_js_object(val)
        if isinstance(val, list):
            return '[' + ', '.join(self._to_js_value(v) for v in val) + ']'
        return str(val)

    def _to_kebab(self, name: str) -> str:
        """Convert to kebab-case"""
        return name.replace(".", "-").replace("_", "-").lower()

    def _to_camel(self, name: str) -> str:
        """Convert to camelCase"""
        parts = name.replace(".", "_").replace("-", "_").split("_")
        return parts[0].lower() + "".join(p.capitalize() for p in parts[1:])
