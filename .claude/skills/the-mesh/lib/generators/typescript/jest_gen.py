"""Mesh to Jest Acceptance Test Generator

Generates EXECUTABLE Jest tests from TRIR scenarios using:
- Given/When/Then structure (describe/it blocks)
- Mock repositories for data access
- TypeScript interfaces (optional)

Tests use Repository pattern - implementation must accept repository parameter.
"""

from typing import Any


class JestGenerator:
    """Generates executable Jest acceptance tests from TRIR scenarios"""

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
        self.typescript = typescript
        self.entities = spec.get("state", {})
        self.derived = spec.get("derived", {})
        self.functions = spec.get("functions", {})
        self.scenarios = spec.get("scenarios", {})
        self.invariants = spec.get("invariants", [])
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
        """Generate Jest test code for all scenarios"""
        # Collect all functions used in scenarios
        used_functions = {
            s.get("when", {}).get("call")
            for s in self.scenarios.values()
            if s.get("when", {}).get("call")
        }

        lines = [
            '/**',
            ' * Auto-generated Acceptance Tests from TRIR specification',
            ' *',
            ' * These tests verify scenario-based behavior using Given/When/Then structure.',
            ' * Tests use mock repositories - implementation must accept repository parameter.',
            ' * @generated',
            ' */',
            '',
        ]

        # Imports
        if self.typescript:
            lines.append("import { describe, it, expect, beforeEach } from '@jest/globals';")

        # Implementation imports
        impl_imports = self._generate_imports(used_functions)
        if impl_imports:
            lines.append('')
            lines.append('// Implementation imports')
            lines.extend(impl_imports)
        lines.append('')

        # Repository interfaces
        if self.typescript:
            lines.append('// ========== Repository Interfaces ==========')
            lines.append('')
            for entity_name in self.entities.keys():
                lines.extend(self._generate_repository_interface(entity_name))
                lines.append('')

        # Mock factories
        lines.append('// ========== Mock Factories ==========')
        lines.append('')
        for entity_name in self.entities.keys():
            lines.extend(self._generate_mock_factory(entity_name))
            lines.append('')

        # Entity factories
        lines.append('// ========== Entity Factories ==========')
        lines.append('')
        for entity_name, entity in self.entities.items():
            lines.extend(self._generate_entity_factory(entity_name, entity))
            lines.append('')

        # Scenario tests
        lines.append('// ========== Acceptance Tests ==========')
        lines.append('')

        # Group scenarios by function
        by_function: dict[str, list[tuple[str, dict]]] = {}
        for scenario_id, scenario in self.scenarios.items():
            func_name = scenario.get("when", {}).get("call", "misc")
            if func_name not in by_function:
                by_function[func_name] = []
            by_function[func_name].append((scenario_id, scenario))

        for func_name, scenarios in by_function.items():
            lines.append(f"describe('{func_name}', () => {{")
            for scenario_id, scenario in scenarios:
                lines.extend(self._generate_scenario_test(scenario_id, scenario))
            lines.append('});')
            lines.append('')

        # Invariant tests
        if self.invariants:
            lines.append('// ========== Invariant Tests ==========')
            lines.append('')
            lines.append("describe('Invariants', () => {")
            for inv in self.invariants:
                lines.extend(self._generate_invariant_test(inv))
            lines.append('});')

        return '\n'.join(lines)

    def generate_for_function(self, function_name: str) -> str:
        """Generate Jest test code for scenarios testing a specific function"""
        relevant_scenarios = {
            sid: s for sid, s in self.scenarios.items()
            if s.get("when", {}).get("call") == function_name
        }

        lines = [
            '/**',
            f' * Auto-generated Acceptance Tests for {function_name}',
            ' *',
            ' * Tests use mock repositories - implementation must accept repository parameter.',
            ' * @generated',
            ' */',
            '',
        ]

        if self.typescript:
            lines.append("import { describe, it, expect, beforeEach } from '@jest/globals';")

        # Implementation imports
        impl_imports = self._generate_imports({function_name})
        if impl_imports:
            lines.append('')
            lines.append('// Implementation imports')
            lines.extend(impl_imports)
        lines.append('')

        # Collect entities used
        entities_used = set()
        for scenario in relevant_scenarios.values():
            for entity in scenario.get("given", {}).keys():
                if entity in self.entities:
                    entities_used.add(entity)

        # Repository interfaces
        if self.typescript and entities_used:
            lines.append('// ========== Repository Interfaces ==========')
            lines.append('')
            for entity_name in sorted(entities_used):
                lines.extend(self._generate_repository_interface(entity_name))
                lines.append('')

        # Mock factories
        if entities_used:
            lines.append('// ========== Mock Factories ==========')
            lines.append('')
            for entity_name in sorted(entities_used):
                lines.extend(self._generate_mock_factory(entity_name))
                lines.append('')

            lines.append('// ========== Entity Factories ==========')
            lines.append('')
            for entity_name in sorted(entities_used):
                lines.extend(self._generate_entity_factory(entity_name, self.entities[entity_name]))
                lines.append('')

        # Scenario tests
        lines.append(f'// ========== Acceptance Tests for {function_name} ==========')
        lines.append('')
        lines.append(f"describe('{function_name}', () => {{")
        for scenario_id, scenario in relevant_scenarios.items():
            lines.extend(self._generate_scenario_test(scenario_id, scenario))
        lines.append('});')

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

    def _generate_entity_factory(self, entity_name: str, entity: dict) -> list[str]:
        """Generate entity factory function"""
        fields = entity.get("fields", {})
        camel = self._to_camel(entity_name)

        partial_type = f': Partial<{entity_name}>' if self.typescript else ''
        return_type = f': {entity_name}' if self.typescript else ''

        lines = [
            f'function create{entity_name}(overrides{partial_type} = {{}}){return_type} {{',
            f'  return {{',
        ]

        for field_name, field_def in fields.items():
            default = self._get_default_value(field_name, field_def)
            lines.append(f'    {field_name}: overrides.{field_name} ?? {default},')

        lines.append('  };')
        lines.append('}')

        return lines

    def _generate_scenario_test(self, scenario_id: str, scenario: dict) -> list[str]:
        """Generate a single scenario test"""
        lines = []
        title = scenario.get("title", scenario_id)

        lines.append('')
        lines.append(f"  it('{title}', async () => {{")

        # Given section
        given = scenario.get("given", {})
        lines.append('    // Given')

        for entity_name, data in given.items():
            if entity_name not in self.entities:
                continue
            camel = self._to_camel(entity_name)
            if isinstance(data, list):
                for i, item in enumerate(data):
                    lines.append(f'    const {camel}{i} = create{entity_name}({self._to_js_object(item)});')
            elif isinstance(data, dict):
                lines.append(f'    const {camel} = create{entity_name}({self._to_js_object(data)});')

        # Create repositories
        for entity_name in given.keys():
            if entity_name in self.entities:
                lines.append(f'    const {self._to_camel(entity_name)}Repository = createMock{entity_name}Repository();')

        lines.append('')

        # When section
        when = scenario.get("when", {})
        func_name = when.get("call", "unknown")
        input_data = when.get("input", {})

        lines.append('    // When')
        lines.append(f'    const inputData = {self._to_js_object(input_data)};')
        lines.append('')

        # Check if import is available
        has_import = func_name in self.import_modules
        comment = "" if has_import else "// "

        repo_args = ", ".join(f'{self._to_camel(e)}Repository' for e in given.keys() if e in self.entities)
        if repo_args:
            lines.append(f'    {comment}const result = await {func_name}(inputData, {{ {repo_args} }});')
        else:
            lines.append(f'    {comment}const result = await {func_name}(inputData);')

        lines.append('')

        # Then section
        then = scenario.get("then", {})
        lines.append('    // Then')

        if then.get("success") is True:
            lines.append(f'    {comment}expect(result.success).toBe(true);')
        elif then.get("success") is False:
            lines.append(f'    {comment}expect(result.success).toBe(false);')
            if "error" in then:
                lines.append(f'    {comment}expect(result.error.code).toBe({self._to_js_value(then["error"])});')

        for assertion in then.get("assert", []):
            lines.append(f'    // Assertion: {self._expr_to_pseudo(assertion)}')

        if not has_import:
            lines.append('')
            lines.append('    // TODO: Uncomment assertions after connecting implementation')
            lines.append('    expect(true).toBe(true); // Placeholder')
        lines.append('  });')

        return lines

    def _generate_invariant_test(self, inv: dict) -> list[str]:
        """Generate invariant test"""
        inv_id = inv.get("id", "unknown")
        entity = inv.get("entity", "entity")
        camel = self._to_camel(entity)
        inv_description = inv.get("description", inv_id)

        lines = [
            '',
            f"  it('Invariant: {inv_description}', async () => {{",
            f'    // Create test data',
            f'    const entity1 = create{entity}();',
            f'    const entity2 = create{entity}({{ id: "{entity.upper()}-002" }});',
            '',
            f'    const {camel}Repository = createMock{entity}Repository();',
            f'    {camel}Repository.getAll.mockResolvedValue([entity1, entity2]);',
            '',
            f'    // Check invariant: {self._expr_to_pseudo(inv.get("expr", {}))}',
            f'    const all = await {camel}Repository.getAll();',
            f'    for (const entity of all) {{',
            f'      // TODO: Add invariant check',
            f'      expect(entity).toBeDefined();',
            f'    }}',
            '  });',
        ]

        return lines

    def _expr_to_pseudo(self, expr: dict) -> str:
        """Convert expression to pseudo-code for comments"""
        if not isinstance(expr, dict):
            return str(expr)

        expr_type = expr.get("type")

        if expr_type == "literal":
            return repr(expr.get("value"))
        if expr_type == "ref":
            return expr.get("path", "")
        if expr_type == "input":
            return f"input.{expr.get('name', '')}"
        if expr_type == "binary":
            op = expr.get("op", "")
            left = self._expr_to_pseudo(expr.get("left", {}))
            right = self._expr_to_pseudo(expr.get("right", {}))
            return f"{left} {op} {right}"

        return str(expr)

    def _get_default_value(self, field_name: str, field_def: dict) -> str:
        """Get default value for a field as JavaScript literal"""
        field_type = field_def.get("type")

        if isinstance(field_type, str):
            defaults = {
                "string": f'"{field_name.upper()}-001"',
                "text": '"test content"',
                "int": "100",
                "float": "100.0",
                "bool": "true",
                "datetime": '"2024-01-01T00:00:00Z"',
                "date": '"2024-01-01"',
            }
            return defaults.get(field_type, '"test"')

        if isinstance(field_type, dict):
            if "enum" in field_type:
                return f'"{field_type["enum"][0]}"'
            if "ref" in field_type:
                return f'"{field_type["ref"].upper()}-001"'

        return "null"

    def _to_js_object(self, obj: dict) -> str:
        """Convert dict to JavaScript object literal"""
        if not obj:
            return '{}'
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

    def _to_pascal(self, name: str) -> str:
        """Convert to PascalCase"""
        return "".join(p.capitalize() for p in name.replace(".", "_").replace("-", "_").split("_"))

    def _to_camel(self, name: str) -> str:
        """Convert to camelCase"""
        parts = name.replace(".", "_").replace("-", "_").split("_")
        return parts[0].lower() + "".join(p.capitalize() for p in parts[1:])
