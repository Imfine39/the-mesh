"""Mesh to Jest Unit Test Generator

Generates executable unit tests from TRIR specification with:
- Constraint-based edge case tests
- Auto-generated validation functions
- Factory functions for entity creation

Note: This generator does NOT require import_modules parameter because unit tests
validate data constraints (min/max, format, enum values) without calling actual
implementation functions. Tests use generated validator functions inline.
"""

from typing import Any
from dataclasses import dataclass

from generators.constraint_inference import (
    infer_constraints,
    build_constraint_cache,
    FieldConstraints,
    PRESETS,
)
from generators.edge_case_gen import (
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


class JestUnitGenerator:
    """Generates executable Jest unit tests from TRIR specification"""

    def __init__(self, spec: dict[str, Any], typescript: bool = True):
        self.spec = spec
        self.typescript = typescript
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
        """Render test cases to executable Jest code"""
        lines = [
            '/**',
            ' * Auto-generated Unit Tests from TRIR specification',
            ' *',
            ' * These tests validate field constraints and are fully executable.',
            ' * @generated',
            ' */',
            '',
        ]

        if self.typescript:
            lines.extend([
                "import { describe, test, expect, beforeEach } from '@jest/globals';",
                '',
            ])
        else:
            lines.extend([
                '// Jest globals are available automatically',
                '',
            ])

        # Generate presets reference
        lines.append('// ========== Presets Reference ==========')
        lines.append('const PRESETS = {')
        for name, constraints in PRESETS.items():
            lines.append(f'  {name}: {self._to_js_obj(constraints)},')
        lines.append('};')
        lines.append('')

        # Generate type definitions for TypeScript
        if self.typescript:
            lines.append('// ========== Type Definitions ==========')
            for entity_name, entity_def in self.entities.items():
                lines.append(self._generate_type_definition(entity_name, entity_def))
                lines.append('')

        # Generate validation functions for each entity
        lines.append('// ========== Validation Functions ==========')
        lines.append('')
        for entity_name, entity_def in self.entities.items():
            lines.append(self._generate_validation_function(entity_name, entity_def))
            lines.append('')

        # Generate factory functions
        lines.append('// ========== Factory Functions ==========')
        lines.append('')
        for entity_name, entity_def in self.entities.items():
            lines.append(self._generate_factory_function(entity_name, entity_def))
            lines.append('')

        # Group test cases by entity.field
        by_target: dict[str, list[TestCase]] = {}
        for tc in test_cases:
            if tc.target not in by_target:
                by_target[tc.target] = []
            by_target[tc.target].append(tc)

        # Generate test suites
        lines.append('// ========== Tests ==========')
        lines.append('')

        for target, target_cases in by_target.items():
            # Determine describe block name
            if '.' in target:
                entity, field = target.split('.', 1)
                describe_name = f"{self._to_pascal(entity)}.{field}"
                is_field_test = True
            else:
                describe_name = self._to_pascal(target)
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

            lines.append(f"describe('{describe_name}', () => {{")
            lines.append(f'  // {doc}')
            lines.append('')

            for tc in target_cases:
                lines.extend(self._render_test_case(tc, is_field_test))
                lines.append('')

            lines.append('});')
            lines.append('')

        return '\n'.join(lines)

    def _generate_type_definition(self, entity_name: str, entity_def: dict) -> str:
        """Generate TypeScript interface for an entity"""
        fields = entity_def.get("fields", {})
        interface_name = self._to_pascal(entity_name)

        lines = [f'interface {interface_name} {{']

        for field_name, field_def in fields.items():
            ts_type = self._get_ts_type(field_def)
            required = field_def.get("required", True)
            optional = '?' if not required else ''
            lines.append(f'  {field_name}{optional}: {ts_type};')

        lines.append('}')
        return '\n'.join(lines)

    def _get_ts_type(self, field_def: dict) -> str:
        """Get TypeScript type for a field"""
        field_type = field_def.get("type")

        if isinstance(field_type, str):
            type_map = {
                "int": "number",
                "float": "number",
                "string": "string",
                "text": "string",
                "bool": "boolean",
                "datetime": "string",
                "date": "string",
            }
            return type_map.get(field_type, "unknown")

        if isinstance(field_type, dict):
            if "enum" in field_type:
                enum_values = field_type["enum"]
                return " | ".join(f"'{v}'" for v in enum_values)
            if "ref" in field_type:
                return "string"

        return "unknown"

    def _generate_validation_function(self, entity_name: str, entity_def: dict) -> str:
        """Generate validation function for an entity"""
        fields = entity_def.get("fields", {})
        func_name = f"validate{self._to_pascal(entity_name)}"
        type_name = self._to_pascal(entity_name) if self.typescript else ""
        param_type = f": Partial<{type_name}>" if self.typescript else ""
        return_type = ": [boolean, string[]]" if self.typescript else ""

        lines = [
            f'function {func_name}(data{param_type}){return_type} {{',
            f'  const errors: string[] = [];',
            '',
        ]

        for field_name, field_def in fields.items():
            constraints = self._constraint_cache.get(entity_name, {}).get(field_name)
            if not constraints:
                constraints = infer_constraints(field_name, field_def)

            required = field_def.get("required", True)
            field_type = field_def.get("type")

            lines.append(f'  // {field_name}')

            # Null check
            if required:
                lines.append(f"  if (data.{field_name} === undefined || data.{field_name} === null) {{")
                lines.append(f"    errors.push('{field_name}: required field is missing or null');")
                lines.append('  } else {')
                indent = '    '
            else:
                lines.append(f"  if (data.{field_name} !== undefined && data.{field_name} !== null) {{")
                indent = '    '

            # Min constraint
            if constraints.min is not None:
                lines.append(f"{indent}if (typeof data.{field_name} === 'number' && data.{field_name} < {constraints.min}) {{")
                lines.append(f"{indent}  errors.push('{field_name}: must be >= {constraints.min}');")
                lines.append(f'{indent}}}')

            # Max constraint
            if constraints.max is not None:
                lines.append(f"{indent}if (typeof data.{field_name} === 'number' && data.{field_name} > {constraints.max}) {{")
                lines.append(f"{indent}  errors.push('{field_name}: must be <= {constraints.max}');")
                lines.append(f'{indent}}}')

            # MinLength constraint
            if constraints.min_length is not None:
                lines.append(f"{indent}if (typeof data.{field_name} === 'string' && data.{field_name}.length < {constraints.min_length}) {{")
                lines.append(f"{indent}  errors.push('{field_name}: length must be >= {constraints.min_length}');")
                lines.append(f'{indent}}}')

            # MaxLength constraint
            if constraints.max_length is not None:
                lines.append(f"{indent}if (typeof data.{field_name} === 'string' && data.{field_name}.length > {constraints.max_length}) {{")
                lines.append(f"{indent}  errors.push('{field_name}: length must be <= {constraints.max_length}');")
                lines.append(f'{indent}}}')

            # Pattern constraint
            if constraints.pattern is not None:
                pattern_escaped = constraints.pattern.replace('\\', '\\\\').replace("'", "\\'")
                lines.append(f"{indent}if (typeof data.{field_name} === 'string' && !/{pattern_escaped}/.test(data.{field_name})) {{")
                lines.append(f"{indent}  errors.push('{field_name}: must match pattern {pattern_escaped}');")
                lines.append(f'{indent}}}')

            # Enum check
            if isinstance(field_type, dict) and "enum" in field_type:
                enum_values = field_type["enum"]
                enum_array = '[' + ', '.join(f"'{v}'" for v in enum_values) + ']'
                lines.append(f"{indent}if (!{enum_array}.includes(data.{field_name} as string)) {{")
                lines.append(f"{indent}  errors.push('{field_name}: must be one of {enum_values}');")
                lines.append(f'{indent}}}')

            # Empty string check for required strings
            if required and (field_type == "string" or field_type == "text"):
                if constraints.min_length is None or constraints.min_length == 0:
                    lines.append(f"{indent}if (typeof data.{field_name} === 'string' && data.{field_name} === '') {{")
                    lines.append(f"{indent}  errors.push('{field_name}: cannot be empty string');")
                    lines.append(f'{indent}}}')

            lines.append('  }')
            lines.append('')

        lines.append('  return [errors.length === 0, errors];')
        lines.append('}')
        return '\n'.join(lines)

    def _generate_factory_function(self, entity_name: str, entity_def: dict) -> str:
        """Generate factory function for entity creation"""
        fields = entity_def.get("fields", {})
        func_name = f"create{self._to_pascal(entity_name)}"
        type_name = self._to_pascal(entity_name) if self.typescript else ""
        param_type = f": Partial<{type_name}>" if self.typescript else ""
        return_type = f": {type_name}" if self.typescript else ""

        lines = [
            f'function {func_name}(overrides{param_type} = {{}}){return_type} {{',
            '  return {',
        ]

        for field_name, field_def in fields.items():
            default = self._get_default_value(field_name, field_def)
            lines.append(f'    {field_name}: overrides.{field_name} ?? {default},')

        lines.append('  };')
        lines.append('}')

        return '\n'.join(lines)

    def _render_test_case(self, tc: TestCase, is_field_test: bool) -> list[str]:
        """Render a single test case"""
        lines = []
        test_name = f"{tc.id}: {tc.description}"

        if is_field_test:
            entity = tc.entity
            field = tc.field
            factory_name = f"create{self._to_pascal(entity)}"
            validate_func = f"validate{self._to_pascal(entity)}"

            lines.append(f"  test('{self._escape(test_name)}', () => {{")

            # Create entity with test value
            if tc.value is None:
                lines.append(f'    const data = {factory_name}({{ {field}: null }});')
            elif isinstance(tc.value, str):
                if tc.value.startswith('<'):
                    # Placeholder for very long strings
                    lines.append(f'    // {tc.value}')
                    lines.append(f'    test.skip(/* Test value too long to include */);')
                    lines.append('  });')
                    return lines
                else:
                    lines.append(f"    const data = {factory_name}({{ {field}: {repr(tc.value)} }});")
            else:
                lines.append(f'    const data = {factory_name}({{ {field}: {self._to_js_literal(tc.value)} }});')

            lines.append(f'    const [isValid, errors] = {validate_func}(data);')

            if tc.should_be_valid:
                lines.append(f'    expect(isValid).toBe(true);')
                lines.append(f'    if (!isValid) console.log("Unexpected errors:", errors);')
            else:
                lines.append(f'    expect(isValid).toBe(false);')
                lines.append(f"    expect(errors.some(e => e.includes('{field}'))).toBe(true);")

            lines.append('  });')

        else:
            # Function test (error case or precondition)
            lines.append(f"  test('{self._escape(test_name)}', () => {{")
            lines.append('    // TODO: Implement with actual function call')
            lines.append('    // This test requires the function implementation')
            lines.append("    test.skip('Requires function implementation');")
            lines.append('  });')

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
                    return "'VALID-001'"
                if constraints and constraints.format == "email":
                    return "'test@example.com'"
                return "'test'"
            elif field_type == "text":
                return "'test content'"
            elif field_type == "bool":
                return "true"
            elif field_type == "datetime":
                return "'2024-01-01T00:00:00Z'"
            elif field_type == "date":
                return "'2024-01-01'"

        elif isinstance(field_type, dict):
            if "enum" in field_type:
                enum_values = field_type["enum"]
                if enum_values:
                    return f"'{enum_values[0]}'"
            if "ref" in field_type:
                return "'REF-001'"

        return "null"

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
            if not obj:
                return "{}"
            items = ", ".join(f"{k}: {self._to_js_obj(v)}" for k, v in obj.items())
            return "{ " + items + " }"
        if isinstance(obj, list):
            if not obj:
                return "[]"
            items = ", ".join(self._to_js_obj(v) for v in obj)
            return "[" + items + "]"
        return str(obj)

    def _to_js_literal(self, value: Any) -> str:
        """Convert Python value to JS literal"""
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, str):
            return f"'{value}'"
        if isinstance(value, (int, float)):
            return str(value)
        return str(value)

    def _to_snake(self, name: str) -> str:
        """Convert to snake_case"""
        return name.replace(".", "_").lower()

    def _to_pascal(self, name: str) -> str:
        """Convert to PascalCase"""
        return "".join(p.capitalize() for p in name.replace(".", "_").split("_"))

    def _to_camel(self, name: str) -> str:
        """Convert to camelCase"""
        parts = name.replace(".", "_").split("_")
        return parts[0].lower() + "".join(p.capitalize() for p in parts[1:])

    def _escape(self, s: str) -> str:
        """Escape string for JS"""
        return s.replace("'", "\\'").replace("\n", " ")
