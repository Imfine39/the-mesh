"""Mesh to pytest Unit Test Generator

Generates executable unit tests from TRIR specification with:
- Constraint-based edge case tests
- Auto-generated validation functions
- Fixtures for entity creation

Note: This generator does NOT require import_modules parameter because unit tests
validate data constraints (min/max, format, enum values) without calling actual
implementation functions. Tests use generated validator functions inline.
"""

from typing import Any
from dataclasses import dataclass

from the_mesh.generators.constraint_inference import (
    infer_constraints,
    build_constraint_cache,
    FieldConstraints,
    PRESETS,
)
from the_mesh.generators.edge_case_gen import (
    generate_edge_cases_for_field,
    EdgeCase,
)


@dataclass
class TestCase:
    """Represents a single unit test case"""
    id: str
    description: str
    category: str  # 'boundary', 'error_case', 'precondition', 'format', 'enum', 'null'
    target: str    # entity.field or function name
    entity: str
    field: str
    value: Any
    should_be_valid: bool


class PytestUnitGenerator:
    """Generates executable pytest unit tests from TRIR specification"""

    def __init__(self, spec: dict[str, Any]):
        self.spec = spec
        self.entities = spec.get("state", {})
        self.derived = spec.get("derived", {})
        self.functions = spec.get("functions", {})
        self.invariants = spec.get("invariants", [])

        # Build constraint cache
        self._constraint_cache = build_constraint_cache(spec)

    def generate_all(self) -> str:
        """Generate all unit tests"""
        test_cases = []

        # 1. Boundary value tests from constraints
        test_cases.extend(self._generate_boundary_tests())

        # 2. Error case tests from functions
        test_cases.extend(self._generate_error_case_tests())

        # 3. Precondition tests
        test_cases.extend(self._generate_precondition_tests())

        return self._render_tests(test_cases)

    def _generate_boundary_tests(self) -> list[TestCase]:
        """Generate boundary value tests from field constraints"""
        cases = []

        for entity_name, entity_def in self.entities.items():
            fields = entity_def.get("fields", {})

            for field_name, field_def in fields.items():
                constraints = self._constraint_cache.get(entity_name, {}).get(field_name)
                if not constraints:
                    constraints = infer_constraints(field_name, field_def)

                # Generate edge cases for this field
                edge_cases = generate_edge_cases_for_field(field_name, field_def, constraints)

                for ec in edge_cases:
                    cases.append(TestCase(
                        id=f"ut_{entity_name}_{field_name}_{ec.label}",
                        description=f"{entity_name}.{field_name}: {ec.description}",
                        category=ec.category,
                        target=f"{entity_name}.{field_name}",
                        entity=entity_name,
                        field=field_name,
                        value=ec.value,
                        should_be_valid=ec.should_be_valid,
                    ))

        return cases

    def _generate_error_case_tests(self) -> list[TestCase]:
        """Generate tests for function error cases"""
        cases = []

        for func_name, func_def in self.functions.items():
            for i, error_def in enumerate(func_def.get("error", [])):
                error_code = error_def.get("code", f"ERR_{i+1:03d}")
                reason = error_def.get("reason", "")

                cases.append(TestCase(
                    id=f"ut_{func_name}_{error_code.lower().replace('-', '_')}",
                    description=f"{func_name}: {reason or error_code}",
                    category="error_case",
                    target=func_name,
                    entity="",
                    field="",
                    value={"error_code": error_code},
                    should_be_valid=False,
                ))

        return cases

    def _generate_precondition_tests(self) -> list[TestCase]:
        """Generate tests for function preconditions"""
        cases = []

        for func_name, func_def in self.functions.items():
            for i, pre in enumerate(func_def.get("pre", []), 1):
                cases.append(TestCase(
                    id=f"ut_{func_name}_pre{i}_pass",
                    description=f"{func_name}: precondition {i} satisfied",
                    category="precondition",
                    target=func_name,
                    entity="",
                    field="",
                    value={"precondition": i, "pass": True},
                    should_be_valid=True,
                ))

                cases.append(TestCase(
                    id=f"ut_{func_name}_pre{i}_fail",
                    description=f"{func_name}: precondition {i} violated",
                    category="precondition",
                    target=func_name,
                    entity="",
                    field="",
                    value={"precondition": i, "pass": False},
                    should_be_valid=False,
                ))

        return cases

    def _render_tests(self, test_cases: list[TestCase]) -> str:
        """Render test cases to executable pytest code"""
        lines = [
            '"""',
            'Auto-generated Unit Tests from TRIR specification',
            '',
            'These tests validate field constraints and are fully executable.',
            '@generated',
            '"""',
            '',
            'import pytest',
            'import re',
            'from typing import Any',
            '',
        ]

        # Generate presets reference
        lines.append('# ========== Presets Reference ==========')
        lines.append('PRESETS = {')
        for name, constraints in PRESETS.items():
            lines.append(f'    "{name}": {repr(constraints)},')
        lines.append('}')
        lines.append('')

        # Generate validation functions for each entity
        lines.append('# ========== Validation Functions ==========')
        lines.append('')
        for entity_name, entity_def in self.entities.items():
            lines.append(self._generate_validation_function(entity_name, entity_def))
            lines.append('')

        # Generate fixtures
        lines.append('# ========== Fixtures ==========')
        lines.append('')
        for entity_name, entity_def in self.entities.items():
            lines.append(self._generate_fixture(entity_name, entity_def))
            lines.append('')

        # Group test cases by entity.field
        by_target: dict[str, list[TestCase]] = {}
        for tc in test_cases:
            if tc.target not in by_target:
                by_target[tc.target] = []
            by_target[tc.target].append(tc)

        # Generate test classes
        lines.append('# ========== Tests ==========')
        lines.append('')

        for target, target_cases in by_target.items():
            # Determine class name
            if '.' in target:
                entity, field = target.split('.', 1)
                class_name = f"Test{self._to_pascal(entity)}{self._to_pascal(field)}"
                is_field_test = True
            else:
                class_name = f"Test{self._to_pascal(target)}"
                is_field_test = False

            # Get constraint info for docstring
            if is_field_test:
                constraints = self._constraint_cache.get(entity, {}).get(field)
                if constraints and constraints.preset_applied:
                    doc = f'Boundary tests for {target} (preset: {constraints.preset_applied})'
                else:
                    doc = f'Boundary tests for {target}'
            else:
                doc = f'Tests for {target}'

            lines.append(f'class {class_name}:')
            lines.append(f'    """{doc}"""')
            lines.append('')

            for tc in target_cases:
                lines.extend(self._render_test_method(tc, is_field_test))
                lines.append('')

        return '\n'.join(lines)

    def _generate_validation_function(self, entity_name: str, entity_def: dict) -> str:
        """Generate validation function for an entity"""
        fields = entity_def.get("fields", {})
        func_name = f"validate_{self._to_snake(entity_name)}"

        lines = [
            f'def {func_name}(data: dict[str, Any]) -> tuple[bool, list[str]]:',
            f'    """Validate {entity_name} entity against constraints"""',
            '    errors = []',
            '',
        ]

        for field_name, field_def in fields.items():
            constraints = self._constraint_cache.get(entity_name, {}).get(field_name)
            if not constraints:
                constraints = infer_constraints(field_name, field_def)

            required = field_def.get("required", True)
            field_type = field_def.get("type")

            lines.append(f'    # {field_name}')

            # Null check
            if required:
                lines.append(f'    if "{field_name}" not in data or data["{field_name}"] is None:')
                lines.append(f'        errors.append("{field_name}: required field is missing or null")')
                lines.append(f'    else:')
                indent = '        '
            else:
                lines.append(f'    if "{field_name}" in data and data["{field_name}"] is not None:')
                indent = '        '

            # Min constraint
            if constraints.min is not None:
                lines.append(f'{indent}if isinstance(data["{field_name}"], (int, float)) and data["{field_name}"] < {constraints.min}:')
                lines.append(f'{indent}    errors.append("{field_name}: must be >= {constraints.min}")')

            # Max constraint
            if constraints.max is not None:
                lines.append(f'{indent}if isinstance(data["{field_name}"], (int, float)) and data["{field_name}"] > {constraints.max}:')
                lines.append(f'{indent}    errors.append("{field_name}: must be <= {constraints.max}")')

            # MinLength constraint
            if constraints.min_length is not None:
                lines.append(f'{indent}if isinstance(data["{field_name}"], str) and len(data["{field_name}"]) < {constraints.min_length}:')
                lines.append(f'{indent}    errors.append("{field_name}: length must be >= {constraints.min_length}")')

            # MaxLength constraint
            if constraints.max_length is not None:
                lines.append(f'{indent}if isinstance(data["{field_name}"], str) and len(data["{field_name}"]) > {constraints.max_length}:')
                lines.append(f'{indent}    errors.append("{field_name}: length must be <= {constraints.max_length}")')

            # Pattern constraint
            if constraints.pattern is not None:
                pattern_escaped = constraints.pattern.replace('\\', '\\\\').replace('"', '\\"')
                lines.append(f'{indent}if isinstance(data["{field_name}"], str) and not re.match(r"{pattern_escaped}", data["{field_name}"]):')
                lines.append(f'{indent}    errors.append("{field_name}: must match pattern {pattern_escaped}")')

            # Enum check
            if isinstance(field_type, dict) and "enum" in field_type:
                enum_values = field_type["enum"]
                lines.append(f'{indent}if data["{field_name}"] not in {repr(enum_values)}:')
                lines.append(f'{indent}    errors.append("{field_name}: must be one of {enum_values}")')

            # Empty string check for required strings
            if required and (field_type == "string" or field_type == "text"):
                if constraints.min_length is None or constraints.min_length == 0:
                    lines.append(f'{indent}if isinstance(data["{field_name}"], str) and data["{field_name}"] == "":')
                    lines.append(f'{indent}    errors.append("{field_name}: cannot be empty string")')

            lines.append('')

        lines.append('    return len(errors) == 0, errors')
        return '\n'.join(lines)

    def _generate_fixture(self, entity_name: str, entity_def: dict) -> str:
        """Generate pytest fixture for entity creation"""
        fields = entity_def.get("fields", {})
        fixture_name = f"create_{self._to_snake(entity_name)}"

        lines = [
            '@pytest.fixture',
            f'def {fixture_name}():',
            f'    """Create a {entity_name} instance for testing"""',
            '    def _create(**kwargs):',
            '        return {',
        ]

        for field_name, field_def in fields.items():
            default = self._get_default_value(field_name, field_def)
            lines.append(f'            "{field_name}": kwargs.get("{field_name}", {default}),')

        lines.append('        }')
        lines.append('    return _create')

        return '\n'.join(lines)

    def _render_test_method(self, tc: TestCase, is_field_test: bool) -> list[str]:
        """Render a single test method"""
        lines = []
        method_name = f"test_{tc.id}"

        if is_field_test:
            entity = tc.entity
            field = tc.field
            fixture_name = f"create_{self._to_snake(entity)}"
            validate_func = f"validate_{self._to_snake(entity)}"

            lines.append(f'    def {method_name}(self, {fixture_name}):')
            lines.append(f'        """{tc.description}"""')

            # Create entity with test value
            if tc.value is None:
                lines.append(f'        data = {fixture_name}({field}=None)')
            elif isinstance(tc.value, str):
                if tc.value.startswith('<'):
                    # Placeholder for very long strings
                    lines.append(f'        # {tc.value}')
                    lines.append(f'        pytest.skip("Test value too long to include")')
                    return lines
                else:
                    lines.append(f'        data = {fixture_name}({field}={repr(tc.value)})')
            else:
                lines.append(f'        data = {fixture_name}({field}={repr(tc.value)})')

            lines.append(f'        is_valid, errors = {validate_func}(data)')

            if tc.should_be_valid:
                lines.append(f'        assert is_valid is True, f"Expected valid but got errors: {{errors}}"')
            else:
                lines.append(f'        assert is_valid is False, f"Expected invalid for {tc.category}"')
                lines.append(f'        assert any("{field}" in e for e in errors), f"Expected error for {field}, got: {{errors}}"')

        else:
            # Function test (error case or precondition)
            lines.append(f'    def {method_name}(self):')
            lines.append(f'        """{tc.description}"""')
            lines.append(f'        # TODO: Implement with actual function call')
            lines.append(f'        # This test requires the function implementation')
            lines.append(f'        pytest.skip("Requires function implementation")')

        return lines

    def _get_default_value(self, field_name: str, field_def: dict) -> str:
        """Get a valid default value for a field"""
        field_type = field_def.get("type")
        constraints = self._constraint_cache.get("", {}).get(field_name)
        if not constraints:
            constraints = infer_constraints(field_name, field_def)

        if isinstance(field_type, str):
            if field_type == "int":
                # Use min if available, otherwise 0
                if constraints and constraints.min is not None and constraints.min > 0:
                    return str(int(constraints.min))
                return "0"
            elif field_type == "float":
                if constraints and constraints.min is not None and constraints.min > 0:
                    return str(float(constraints.min))
                return "0.0"
            elif field_type == "string":
                # Generate a valid string based on constraints
                if constraints and constraints.pattern:
                    return '"VALID-001"'
                if constraints and constraints.format == "email":
                    return '"test@example.com"'
                return '"test"'
            elif field_type == "text":
                return '"test content"'
            elif field_type == "bool":
                return "True"
            elif field_type == "datetime":
                return '"2024-01-01T00:00:00Z"'
            elif field_type == "date":
                return '"2024-01-01"'

        elif isinstance(field_type, dict):
            if "enum" in field_type:
                enum_values = field_type["enum"]
                if enum_values:
                    return repr(enum_values[0])
            if "ref" in field_type:
                return '"REF-001"'

        return "None"

    def _to_snake(self, name: str) -> str:
        """Convert to snake_case"""
        return name.replace(".", "_").lower()

    def _to_pascal(self, name: str) -> str:
        """Convert to PascalCase"""
        return "".join(p.capitalize() for p in name.replace(".", "_").split("_"))
