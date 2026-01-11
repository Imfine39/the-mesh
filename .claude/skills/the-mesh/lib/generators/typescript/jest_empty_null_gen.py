"""Mesh to Jest Empty/Null Boundary Test Generator

Generates tests for empty and null value handling.

Test patterns generated:
1. Optional field absent - omit optional fields entirely
2. Optional field null - explicitly set optional fields to null
3. Empty string - empty string for string fields
4. Empty list - empty array for list fields
5. Zero values - zero for numeric fields (when allowed)
"""

from typing import Any
from dataclasses import dataclass


@dataclass
class EmptyNullTestCase:
    """Represents an empty/null test case"""
    id: str
    description: str
    target: str  # command or entity name
    target_type: str  # 'command' or 'entity'
    field: str
    pattern: str  # 'absent', 'null', 'empty_string', 'empty_list', 'zero'
    field_type: str
    is_required: bool


class JestEmptyNullGenerator:
    """Generates Jest empty/null boundary tests from TRIR specification"""

    def __init__(self, spec: dict[str, Any]):
        self.spec = spec
        self.entities = spec.get("entities", {})
        self.commands = spec.get("commands", {})
        self.test_strategies = spec.get("testStrategies", {})

    def generate_all(self) -> str:
        """Generate all empty/null tests"""
        test_cases = []

        # Generate tests for command inputs
        for cmd_name, cmd_def in self.commands.items():
            test_cases.extend(self._generate_tests_for_command(cmd_name, cmd_def))

        # Generate tests for entity fields
        for entity_name, entity_def in self.entities.items():
            test_cases.extend(self._generate_tests_for_entity(entity_name, entity_def))

        if not test_cases:
            return self._render_empty_tests()

        return self._render_tests(test_cases)

    def _generate_tests_for_command(self, cmd_name: str, cmd_def: dict) -> list[EmptyNullTestCase]:
        """Generate empty/null test cases for command inputs"""
        cases = []
        input_fields = cmd_def.get("input", {})

        for field_name, field_def in input_fields.items():
            field_type = field_def.get("type", "string")
            is_required = field_def.get("required", False)

            # Pattern 1 & 2: Absent and Null for optional fields
            if not is_required:
                cases.append(EmptyNullTestCase(
                    id=f"empty_{cmd_name}_{field_name}_absent",
                    description=f"{cmd_name}: should handle missing optional field '{field_name}'",
                    target=cmd_name,
                    target_type="command",
                    field=field_name,
                    pattern="absent",
                    field_type=field_type,
                    is_required=False,
                ))
                cases.append(EmptyNullTestCase(
                    id=f"empty_{cmd_name}_{field_name}_null",
                    description=f"{cmd_name}: should handle null value for optional field '{field_name}'",
                    target=cmd_name,
                    target_type="command",
                    field=field_name,
                    pattern="null",
                    field_type=field_type,
                    is_required=False,
                ))

            # Pattern 3: Empty string for string fields
            if field_type == "string":
                cases.append(EmptyNullTestCase(
                    id=f"empty_{cmd_name}_{field_name}_empty_string",
                    description=f"{cmd_name}: should {'reject' if is_required else 'handle'} empty string for '{field_name}'",
                    target=cmd_name,
                    target_type="command",
                    field=field_name,
                    pattern="empty_string",
                    field_type=field_type,
                    is_required=is_required,
                ))

            # Pattern 4: Empty list for list fields
            if field_type == "list" or field_def.get("items"):
                cases.append(EmptyNullTestCase(
                    id=f"empty_{cmd_name}_{field_name}_empty_list",
                    description=f"{cmd_name}: should handle empty list for '{field_name}'",
                    target=cmd_name,
                    target_type="command",
                    field=field_name,
                    pattern="empty_list",
                    field_type="list",
                    is_required=is_required,
                ))

            # Pattern 5: Zero for numeric fields
            if field_type in ["int", "float", "number"] or field_def.get("preset") in ["money", "count"]:
                min_val = field_def.get("min")
                cases.append(EmptyNullTestCase(
                    id=f"empty_{cmd_name}_{field_name}_zero",
                    description=f"{cmd_name}: should {'reject' if min_val and min_val > 0 else 'accept'} zero for '{field_name}'",
                    target=cmd_name,
                    target_type="command",
                    field=field_name,
                    pattern="zero",
                    field_type=field_type,
                    is_required=is_required,
                ))

        return cases

    def _generate_tests_for_entity(self, entity_name: str, entity_def: dict) -> list[EmptyNullTestCase]:
        """Generate empty/null test cases for entity fields"""
        cases = []
        fields = entity_def.get("fields", {})

        for field_name, field_def in fields.items():
            # Skip id fields
            if field_name == "id" or field_def.get("preset") == "id":
                continue

            field_type = field_def.get("type", "string")
            is_required = field_def.get("required", False)

            # Only test optional fields for entities
            if not is_required:
                cases.append(EmptyNullTestCase(
                    id=f"empty_{entity_name}_{field_name}_null",
                    description=f"{entity_name}: optional field '{field_name}' should accept null",
                    target=entity_name,
                    target_type="entity",
                    field=field_name,
                    pattern="null",
                    field_type=field_type,
                    is_required=False,
                ))

        return cases

    def _render_empty_tests(self) -> str:
        """Render placeholder when no tests generated"""
        return '''/**
 * Auto-generated Empty/Null Boundary Tests from TRIR specification
 *
 * No testable fields found.
 *
 * @generated
 */

describe('Empty/Null Tests (disabled)', () => {
  test.skip('placeholder', () => {
    // No testable fields found
  });
});
'''

    def _render_tests(self, test_cases: list[EmptyNullTestCase]) -> str:
        """Render test cases to executable Jest code"""
        lines = [
            '/**',
            ' * Auto-generated Empty/Null Boundary Tests from TRIR specification',
            ' *',
            ' * These tests verify handling of empty and null values:',
            ' * - Optional fields can be omitted or null',
            ' * - Empty strings are handled correctly',
            ' * - Empty lists are handled correctly',
            ' * - Zero values are validated against constraints',
            ' *',
            ' * @generated',
            ' */',
            '',
            '// ========== Test Infrastructure ==========',
            '',
            'interface InputData {',
            '  [key: string]: unknown;',
            '}',
            '',
            'class InputBuilder {',
            '  private base: InputData;',
            '',
            '  constructor(baseInput: InputData) {',
            '    this.base = { ...baseInput };',
            '  }',
            '',
            '  without(field: string): InputData {',
            '    const result = { ...this.base };',
            '    delete result[field];',
            '    return result;',
            '  }',
            '',
            '  withNull(field: string): InputData {',
            '    return { ...this.base, [field]: null };',
            '  }',
            '',
            '  withEmptyString(field: string): InputData {',
            '    return { ...this.base, [field]: "" };',
            '  }',
            '',
            '  withEmptyList(field: string): InputData {',
            '    return { ...this.base, [field]: [] };',
            '  }',
            '',
            '  withZero(field: string): InputData {',
            '    return { ...this.base, [field]: 0 };',
            '  }',
            '}',
            '',
            'function createInputBuilder(baseInput: InputData): InputBuilder {',
            '  return new InputBuilder(baseInput);',
            '}',
            '',
        ]

        # Group by target
        by_target: dict[str, list[EmptyNullTestCase]] = {}
        for tc in test_cases:
            key = f"{tc.target_type}_{tc.target}"
            if key not in by_target:
                by_target[key] = []
            by_target[key].append(tc)

        lines.append('// ========== Tests ==========')
        lines.append('')

        for target_key, cases in by_target.items():
            target_type, target_name = target_key.split("_", 1)

            lines.append(f"describe('Empty/Null: {target_name} ({target_type})', () => {{")
            lines.append('')
            lines.append(f'  function getValidBaseInput(): InputData {{')
            lines.append(f'    // TODO: Generate from spec')
            lines.append(f'    return {{}};')
            lines.append(f'  }}')
            lines.append('')

            for tc in cases:
                lines.extend(self._render_test_method(tc))
                lines.append('')

            lines.append('});')
            lines.append('')

        return '\n'.join(lines)

    def _render_test_method(self, tc: EmptyNullTestCase) -> list[str]:
        """Render a single test method"""
        lines = []

        if tc.pattern == "absent":
            lines.append(f"  test('{tc.description}', () => {{")
            lines.append(f'    // Arrange: Create input without optional field')
            lines.append(f'    const builder = createInputBuilder(getValidBaseInput());')
            lines.append(f'    const testInput = builder.without("{tc.field}");')
            lines.append(f'    ')
            lines.append(f'    // Act & Assert: Should succeed (optional field)')
            lines.append(f'    // TODO: Call {tc.target} with testInput')
            lines.append(f'    throw new Error("Requires {tc.target} implementation");')
            lines.append('  });')

        elif tc.pattern == "null":
            lines.append(f"  test('{tc.description}', () => {{")
            lines.append(f'    // Arrange: Create input with null value')
            lines.append(f'    const builder = createInputBuilder(getValidBaseInput());')
            lines.append(f'    const testInput = builder.withNull("{tc.field}");')
            lines.append(f'    ')
            lines.append(f'    // Act & Assert: Should succeed (optional field accepts null)')
            lines.append(f'    // TODO: Call {tc.target} with testInput')
            lines.append(f'    throw new Error("Requires {tc.target} implementation");')
            lines.append('  });')

        elif tc.pattern == "empty_string":
            if tc.is_required:
                lines.append(f"  test('{tc.description}', () => {{")
                lines.append(f'    // Arrange: Create input with empty string')
                lines.append(f'    const builder = createInputBuilder(getValidBaseInput());')
                lines.append(f'    const testInput = builder.withEmptyString("{tc.field}");')
                lines.append(f'    ')
                lines.append(f'    // Act & Assert: Should REJECT empty string for required field')
                lines.append(f'    // TODO: Verify validation error')
                lines.append(f'    throw new Error("Requires {tc.target} implementation");')
                lines.append('  });')
            else:
                lines.append(f"  test('{tc.description}', () => {{")
                lines.append(f'    // Arrange: Create input with empty string')
                lines.append(f'    const builder = createInputBuilder(getValidBaseInput());')
                lines.append(f'    const testInput = builder.withEmptyString("{tc.field}");')
                lines.append(f'    ')
                lines.append(f'    // Act & Assert: Should handle empty string')
                lines.append(f'    // TODO: Call {tc.target} with testInput')
                lines.append(f'    throw new Error("Requires {tc.target} implementation");')
                lines.append('  });')

        elif tc.pattern == "empty_list":
            lines.append(f"  test('{tc.description}', () => {{")
            lines.append(f'    // Arrange: Create input with empty list')
            lines.append(f'    const builder = createInputBuilder(getValidBaseInput());')
            lines.append(f'    const testInput = builder.withEmptyList("{tc.field}");')
            lines.append(f'    ')
            lines.append(f'    // Act & Assert: Should handle empty list gracefully')
            lines.append(f'    // TODO: Call {tc.target} with testInput')
            lines.append(f'    throw new Error("Requires {tc.target} implementation");')
            lines.append('  });')

        elif tc.pattern == "zero":
            lines.append(f"  test('{tc.description}', () => {{")
            lines.append(f'    // Arrange: Create input with zero value')
            lines.append(f'    const builder = createInputBuilder(getValidBaseInput());')
            lines.append(f'    const testInput = builder.withZero("{tc.field}");')
            lines.append(f'    ')
            lines.append(f'    // Act & Assert: Verify zero value handling')
            lines.append(f'    // Check if min constraint exists and zero violates it')
            lines.append(f'    // TODO: Call {tc.target} with testInput')
            lines.append(f'    throw new Error("Requires {tc.target} implementation");')
            lines.append('  });')

        return lines

    def _to_snake(self, name: str) -> str:
        """Convert to snake_case"""
        import re
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

    def _to_pascal(self, name: str) -> str:
        """Convert to PascalCase"""
        return "".join(word.capitalize() for word in self._to_snake(name).split("_"))
