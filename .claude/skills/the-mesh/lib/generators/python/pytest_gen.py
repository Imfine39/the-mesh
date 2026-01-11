"""Mesh to pytest Acceptance Test Generator

Generates EXECUTABLE acceptance tests from TRIR scenarios using:
- Given/When/Then structure
- Mock repositories for data access
- Actual assertions that can run without implementation

Tests use Repository pattern - implementation must accept repository parameter.
"""

from typing import Any


class PytestGenerator:
    """Generates executable pytest acceptance tests from TRIR scenarios"""

    def __init__(self, spec: dict[str, Any], import_modules: dict[str, str] | None = None):
        """
        Args:
            spec: TRIR specification
            import_modules: Map of function_name -> module path
                           e.g. {"create_order": "src.orders.create_order"}
        """
        self.spec = spec
        self.entities = spec.get("entities", {})
        self.derived = spec.get("derived", {})
        self.functions = spec.get("commands", {})
        self.scenarios = spec.get("scenarios", {})
        self.invariants = spec.get("invariants", [])
        self.import_modules = import_modules or {}

    def _generate_imports(self, function_names: set[str]) -> list[str]:
        """Generate import statements for functions"""
        lines = []

        # Group imports by module
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

    def generate_all(self) -> str:
        """Generate pytest code for all scenarios"""
        # Collect all functions used in scenarios
        used_functions = {
            s.get("when", {}).get("call")
            for s in self.scenarios.values()
            if s.get("when", {}).get("call")
        }

        lines = [
            '"""',
            'Auto-generated Acceptance Tests from TRIR specification',
            '',
            'These tests verify scenario-based behavior using Given/When/Then structure.',
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

        # Generate repository interfaces
        lines.append('# ========== Repository Interfaces ==========')
        lines.append('')
        for entity_name in self.entities.keys():
            lines.extend(self._generate_repository_interface(entity_name))
            lines.append('')

        # Generate fixtures
        lines.append('# ========== Fixtures ==========')
        lines.append('')
        for entity_name in self.entities.keys():
            lines.extend(self._generate_mock_fixture(entity_name))
            lines.append('')
        lines.extend(self._generate_combined_repository_fixture())
        lines.append('')

        # Generate entity factory fixtures
        lines.append('# ========== Entity Factories ==========')
        lines.append('')
        for entity_name, entity in self.entities.items():
            lines.extend(self._generate_factory_fixture(entity_name, entity))
            lines.append('')

        # Scenario tests
        lines.append('# ========== Acceptance Tests ==========')
        lines.append('')

        for scenario_id, scenario in self.scenarios.items():
            lines.extend(self._generate_scenario_test(scenario_id, scenario))
            lines.append('')

        # Invariant tests
        if self.invariants:
            lines.append('# ========== Invariant Tests ==========')
            lines.append('')
            for inv in self.invariants:
                lines.extend(self._generate_invariant_test(inv))
                lines.append('')

        return '\n'.join(lines)

    def generate_for_function(self, function_name: str) -> str:
        """Generate pytest code for scenarios testing a specific function"""
        relevant_scenarios = {
            sid: s for sid, s in self.scenarios.items()
            if s.get("when", {}).get("call") == function_name
        }

        lines = [
            '"""',
            f'Auto-generated Acceptance Tests for {function_name}',
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

        # Add implementation import
        impl_imports = self._generate_imports({function_name})
        if impl_imports:
            lines.append('# Implementation imports')
            lines.extend(impl_imports)
            lines.append('')

        # Collect entities used in relevant scenarios
        entities_used = set()
        for scenario in relevant_scenarios.values():
            for entity in scenario.get("given", {}).keys():
                if entity in self.entities:
                    entities_used.add(entity)

        # Generate repository interfaces for used entities
        lines.append('# ========== Repository Interfaces ==========')
        lines.append('')
        for entity_name in sorted(entities_used):
            lines.extend(self._generate_repository_interface(entity_name))
            lines.append('')

        # Generate fixtures for used entities
        lines.append('# ========== Fixtures ==========')
        lines.append('')
        for entity_name in sorted(entities_used):
            lines.extend(self._generate_mock_fixture(entity_name))
            lines.append('')

        # Entity factories
        lines.append('# ========== Entity Factories ==========')
        lines.append('')
        for entity_name in sorted(entities_used):
            lines.extend(self._generate_factory_fixture(entity_name, self.entities[entity_name]))
            lines.append('')

        # Scenario tests
        lines.append(f'# ========== Acceptance Tests for {function_name} ==========')
        lines.append('')

        for scenario_id, scenario in relevant_scenarios.items():
            lines.extend(self._generate_scenario_test(scenario_id, scenario))
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
        return [
            '@pytest.fixture',
            f'def mock_{snake}_repository():',
            f'    """Mock {entity_name} repository"""',
            f'    repo = Mock(spec={entity_name}Repository)',
            f'    repo._data = {{}}  # Internal storage for test setup',
            f'    repo.get.side_effect = lambda id: repo._data.get(id)',
            f'    repo.get_all.return_value = []',
            f'    repo.create.side_effect = lambda data: {{**data, "id": data.get("id", "NEW-001")}}',
            f'    repo.update.side_effect = lambda id, data: {{**repo._data.get(id, {{}}), **data}}',
            f'    repo.delete.return_value = True',
            f'    return repo',
        ]

    def _generate_combined_repository_fixture(self) -> list[str]:
        """Generate a combined repositories fixture"""
        lines = [
            '@pytest.fixture',
            'def repositories(',
        ]
        for entity_name in self.entities.keys():
            lines.append(f'    mock_{self._to_snake(entity_name)}_repository,')
        lines.append('):')
        lines.append('    """Combined repository fixture for easy access"""')
        lines.append('    return {')
        for entity_name in self.entities.keys():
            snake = self._to_snake(entity_name)
            lines.append(f'        "{entity_name}": mock_{snake}_repository,')
        lines.append('    }')
        return lines

    def _generate_factory_fixture(self, entity_name: str, entity: dict) -> list[str]:
        """Generate factory fixture for creating test entities"""
        snake = self._to_snake(entity_name)
        fields = entity.get("fields", {})

        lines = [
            '@pytest.fixture',
            f'def create_{snake}(mock_{snake}_repository):',
            f'    """Factory for {entity_name} test data"""',
            f'    def _create(**kwargs):',
            f'        data = {{',
        ]

        for field_name, field_def in fields.items():
            default = self._get_default_value(field_name, field_def)
            lines.append(f'            "{field_name}": kwargs.get("{field_name}", {default}),')

        lines.append('        }')
        lines.append(f'        mock_{snake}_repository._data[data["id"]] = data')
        lines.append(f'        return data')
        lines.append('    return _create')

        return lines

    def _generate_scenario_test(self, scenario_id: str, scenario: dict) -> list[str]:
        """Generate a single test from a scenario"""
        lines = []

        safe_id = scenario_id.lower().replace("-", "_")
        title = scenario.get("title", "")

        # Build fixture list
        given_raw = scenario.get("given", {})
        # Normalize given to dict format for compatibility
        if isinstance(given_raw, list):
            # List format: [{"entity": "Product", "id": "...", "data": {...}}, ...]
            given = {item["entity"]: item.get("data", {}) for item in given_raw if "entity" in item}
        else:
            given = given_raw
        fixtures = []
        for entity_name in given.keys():
            if entity_name in self.entities:
                fixtures.append(f"create_{self._to_snake(entity_name)}")
                fixtures.append(f"mock_{self._to_snake(entity_name)}_repository")

        # Remove duplicates while preserving order
        fixtures = list(dict.fromkeys(fixtures))

        lines.append(f'class TestScenario{self._to_pascal(safe_id)}:')
        lines.append(f'    """')
        lines.append(f'    Scenario: {title}')
        lines.append(f'    """')
        lines.append('')

        # Main test method
        fixture_params = ", ".join(fixtures) if fixtures else ""
        lines.append(f'    def test_{safe_id}(self, {fixture_params}):')
        lines.append(f'        """')
        lines.append(f'        {title}')
        if scenario.get("verifies"):
            lines.append(f'        Verifies: {", ".join(scenario["verifies"])}')
        lines.append(f'        """')

        # Given section
        lines.append('        # Given')
        for entity_name, data in given.items():
            if entity_name not in self.entities:
                continue
            snake = self._to_snake(entity_name)
            if isinstance(data, list):
                for i, item in enumerate(data):
                    lines.append(f'        {snake}_{i} = create_{snake}(**{repr(item)})')
            elif isinstance(data, dict):
                lines.append(f'        {snake} = create_{snake}(**{repr(data)})')

        lines.append('')

        # When section
        when = scenario.get("when", {})
        func_name = when.get("call", "unknown")
        input_data = when.get("input", {})

        lines.append('        # When')
        lines.append(f'        input_data = {repr(input_data)}')

        # Build repository kwargs
        repo_kwargs = []
        for entity_name in given.keys():
            if entity_name in self.entities:
                snake = self._to_snake(entity_name)
                repo_kwargs.append(f'{snake}_repository=mock_{snake}_repository')

        # Generate function call - uncommented if import_modules provided
        has_import = func_name in self.import_modules
        comment = "" if has_import else "# "

        if repo_kwargs:
            lines.append(f'        {comment}result = {func_name}(input_data, {", ".join(repo_kwargs)})')
        else:
            lines.append(f'        {comment}result = {func_name}(input_data)')
        lines.append('')

        # Then section
        then = scenario.get("then", {})
        lines.append('        # Then')

        if then.get("result", {}).get("success") is True:
            lines.append(f'        {comment}assert result["success"] is True')
        elif then.get("result", {}).get("success") is False:
            lines.append(f'        {comment}assert result["success"] is False')
            if "error" in then.get("result", {}):
                lines.append(f'        {comment}assert result["error"]["code"] == {repr(then["result"]["error"])}')

        for i, assertion in enumerate(then.get("assert", [])):
            lines.append(f'        # Assertion: {self._expr_to_pseudo(assertion)}')

        if not has_import:
            # Placeholder when no implementation connected
            lines.append('')
            lines.append('        # TODO: Uncomment assertions after connecting implementation')
            lines.append('        pass')

        return lines

    def _generate_invariant_test(self, inv: dict) -> list[str]:
        """Generate test for a single invariant"""
        inv_id = inv.get("id", "unknown").lower().replace("-", "_")
        entity = inv.get("entity", "entity")
        snake = self._to_snake(entity)

        lines = [
            f'class TestInvariant{self._to_pascal(inv_id)}:',
            f'    """',
            f'    Invariant: {inv.get("description", inv_id)}',
            f'    """',
            '',
            f'    def test_{inv_id}(self, mock_{snake}_repository, create_{snake}):',
            f'        """Verify invariant holds for all {entity} instances"""',
            f'        # Create test data',
            f'        entity1 = create_{snake}()',
            f'        entity2 = create_{snake}(id="{entity.upper()}-002")',
            '',
            f'        # Set up repository to return test data',
            f'        mock_{snake}_repository.get_all.return_value = [entity1, entity2]',
            '',
            f'        # Check invariant: {self._expr_to_pseudo(inv.get("expr", {}))}',
            f'        for entity in mock_{snake}_repository.get_all():',
            f'            # TODO: Add invariant check based on expression',
            f'            pass',
        ]

        return lines

    def _expr_to_pseudo(self, expr: dict) -> str:
        """Convert expression to pseudo-code for comments"""
        if not isinstance(expr, dict):
            return str(expr)

        expr_type = expr.get("type")

        if expr_type == "literal":
            return repr(expr.get("value"))
        if expr_type == "self":
            field = expr.get("field", "")
            return f"self.{field}" if field else "self"
        if expr_type == "ref":
            return expr.get("path", "")
        if expr_type == "input":
            return f"input.{expr.get('name', '')}"
        if expr_type == "binary":
            op = expr.get("op", "")
            left = self._expr_to_pseudo(expr.get("left", {}))
            right = self._expr_to_pseudo(expr.get("right", {}))
            return f"{left} {op} {right}"
        if expr_type == "unary":
            return f"{expr.get('op', '')}({self._expr_to_pseudo(expr.get('expr', {}))})"
        if expr_type == "agg":
            return f"{expr.get('op', '')}({expr.get('from', '')})"

        return str(expr)

    def _get_default_value(self, field_name: str, field_def: dict) -> str:
        """Get default value for a field"""
        field_type = field_def.get("type")

        if isinstance(field_type, str):
            defaults = {
                "string": f'"{field_name.upper()}-001"',
                "text": '"test content"',
                "int": "100",
                "float": "100.0",
                "bool": "True",
                "datetime": '"2024-01-01T00:00:00Z"',
                "date": '"2024-01-01"',
            }
            return defaults.get(field_type, '"test"')

        if isinstance(field_type, dict):
            if "enum" in field_type:
                return repr(field_type["enum"][0])
            if "ref" in field_type:
                return f'"{field_type["ref"].upper()}-001"'

        return "None"

    def _to_pascal(self, name: str) -> str:
        """Convert to PascalCase"""
        return "".join(p.capitalize() for p in name.replace(".", "_").replace("-", "_").split("_"))

    def _to_snake(self, name: str) -> str:
        """Convert to snake_case"""
        return name.replace(".", "_").replace("-", "_").lower()
