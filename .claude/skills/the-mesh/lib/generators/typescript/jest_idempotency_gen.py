"""Mesh to Jest Idempotency Test Generator

Generates idempotency tests for commands specified in testStrategies.

Idempotency means: executing the same operation multiple times
produces the same result as executing it once.

Test patterns generated:
1. Double execution - same input twice should not create duplicates
2. Retry safety - if first call fails midway, retry should succeed
"""

from typing import Any
from dataclasses import dataclass


@dataclass
class IdempotencyTestCase:
    """Represents an idempotency test case"""
    id: str
    description: str
    command: str
    entity: str
    pattern: str  # 'double_exec', 'retry_safety'
    idempotency_key_fields: list[str]


class JestIdempotencyGenerator:
    """Generates Jest idempotency tests from TRIR specification"""

    def __init__(self, spec: dict[str, Any]):
        self.spec = spec
        self.entities = spec.get("entities", {})
        self.commands = spec.get("commands", {})
        self.test_strategies = spec.get("testStrategies", {})

    def generate_all(self) -> str:
        """Generate all idempotency tests"""
        idempotency_config = self.test_strategies.get("templates", {}).get("idempotency", {})

        if not idempotency_config.get("enabled", False):
            return self._render_empty_tests()

        targets = idempotency_config.get("targets", [])
        if not targets:
            targets = self._infer_create_commands()

        test_cases = []
        for cmd_name in targets:
            cmd_def = self.commands.get(cmd_name)
            if cmd_def:
                test_cases.extend(self._generate_tests_for_command(cmd_name, cmd_def))

        return self._render_tests(test_cases)

    def _infer_create_commands(self) -> list[str]:
        """Infer which commands are create operations"""
        create_commands = []
        for cmd_name, cmd_def in self.commands.items():
            if any(kw in cmd_name.lower() for kw in ['create', 'add', 'register', 'confirm']):
                create_commands.append(cmd_name)
            elif 'post' in cmd_def:
                for post in cmd_def.get('post', []):
                    action = post.get('action', {})
                    if 'create' in action:
                        create_commands.append(cmd_name)
                        break
        return create_commands

    def _generate_tests_for_command(self, cmd_name: str, cmd_def: dict) -> list[IdempotencyTestCase]:
        """Generate idempotency test cases for a command"""
        cases = []
        entity = cmd_def.get("entity", "")

        input_fields = cmd_def.get("input", {})
        key_fields = [
            name for name, field in input_fields.items()
            if field.get("required", False) or field.get("type") == "id" or "Id" in name
        ]

        cases.append(IdempotencyTestCase(
            id=f"idempotency_{cmd_name}_double_exec",
            description=f"{cmd_name}: executing twice with same input should not create duplicates",
            command=cmd_name,
            entity=entity,
            pattern="double_exec",
            idempotency_key_fields=key_fields,
        ))

        cases.append(IdempotencyTestCase(
            id=f"idempotency_{cmd_name}_retry_safety",
            description=f"{cmd_name}: retry after partial failure should succeed or return idempotent result",
            command=cmd_name,
            entity=entity,
            pattern="retry_safety",
            idempotency_key_fields=key_fields,
        ))

        return cases

    def _render_empty_tests(self) -> str:
        """Render placeholder when idempotency tests are disabled"""
        return '''/**
 * Auto-generated Idempotency Tests from TRIR specification
 *
 * Idempotency testing is DISABLED in testStrategies.
 * To enable, set testStrategies.templates.idempotency.enabled = true
 *
 * @generated
 */

describe('Idempotency Tests (disabled)', () => {
  test.skip('placeholder', () => {
    // Idempotency tests disabled in testStrategies
  });
});
'''

    def _render_tests(self, test_cases: list[IdempotencyTestCase]) -> str:
        """Render test cases to executable Jest code"""
        lines = [
            '/**',
            ' * Auto-generated Idempotency Tests from TRIR specification',
            ' *',
            ' * These tests verify that commands are idempotent:',
            ' * - Executing the same operation twice produces the same result',
            ' * - Retrying a failed operation is safe',
            ' *',
            ' * @generated',
            ' */',
            '',
            '// ========== Test Infrastructure ==========',
            '',
            'interface IdempotencyResult {',
            '  success: boolean;',
            '  errorCode?: string;',
            '  data?: unknown;',
            '  isDuplicate?: boolean;',
            '}',
            '',
            'class IdempotencyChecker {',
            '  constructor(private countFunc: (keyFields: Record<string, unknown>) => number) {}',
            '',
            '  checkNoDuplicates(keyFields: Record<string, unknown>, expectedCount: number = 1): boolean {',
            '    const actualCount = this.countFunc(keyFields);',
            '    return actualCount === expectedCount;',
            '  }',
            '',
            '  isIdempotentResult(result1: IdempotencyResult, result2: IdempotencyResult): boolean {',
            '    // Both succeed with same data',
            '    if (result1.success && result2.success) {',
            '      return JSON.stringify(result1.data) === JSON.stringify(result2.data) || result2.isDuplicate === true;',
            '    }',
            '    // First succeeds, second indicates duplicate',
            '    if (result1.success && !result2.success) {',
            '      return ["DUPLICATE", "ALREADY_EXISTS", "CONFLICT"].includes(result2.errorCode || "");',
            '    }',
            '    // Both fail with same error',
            '    if (!result1.success && !result2.success) {',
            '      return result1.errorCode === result2.errorCode;',
            '    }',
            '    return false;',
            '  }',
            '}',
            '',
            '// ========== Fixtures ==========',
            '',
            'function createIdempotencyChecker(): IdempotencyChecker {',
            '  // TODO: Replace with actual entity count function',
            '  const callCount = { value: 0 };',
            '  ',
            '  const mockCount = (keyFields: Record<string, unknown>): number => {',
            '    // In real implementation, query database',
            '    return callCount.value;',
            '  };',
            '  ',
            '  return new IdempotencyChecker(mockCount);',
            '}',
            '',
        ]

        # Group by command
        by_command: dict[str, list[IdempotencyTestCase]] = {}
        for tc in test_cases:
            if tc.command not in by_command:
                by_command[tc.command] = []
            by_command[tc.command].append(tc)

        lines.append('// ========== Tests ==========')
        lines.append('')

        for cmd_name, cases in by_command.items():
            class_name = self._to_pascal(cmd_name)

            lines.append(f"describe('Idempotency: {cmd_name}', () => {{")
            lines.append('  let checker: IdempotencyChecker;')
            lines.append('')
            lines.append('  beforeEach(() => {')
            lines.append('    checker = createIdempotencyChecker();')
            lines.append('  });')
            lines.append('')

            for tc in cases:
                lines.extend(self._render_test_method(tc))
                lines.append('')

            # Add helper functions
            lines.extend(self._render_helper_functions(cmd_name))
            lines.append('});')
            lines.append('')

        return '\n'.join(lines)

    def _render_test_method(self, tc: IdempotencyTestCase) -> list[str]:
        """Render a single test method"""
        lines = []
        cmd_name = tc.command
        entity = tc.entity

        if tc.pattern == "double_exec":
            lines.append(f"  test('{tc.description}', async () => {{")
            lines.append(f'    // Arrange: Create valid input for {cmd_name}')
            lines.append(f'    const inputData = createValidInput();')
            lines.append(f'    const keyFields = {{')
            for field in tc.idempotency_key_fields:
                lines.append(f"      {field}: inputData.{field},")
            lines.append(f'    }};')
            lines.append('')
            lines.append(f'    // Act: Execute {cmd_name} twice with same input')
            lines.append(f'    const result1 = await execute{self._to_pascal(cmd_name)}(inputData);')
            lines.append(f'    const result2 = await execute{self._to_pascal(cmd_name)}(inputData);')
            lines.append('')
            lines.append(f'    // Assert: Results should be idempotent')
            lines.append(f'    expect(checker.isIdempotentResult(result1, result2)).toBe(true);')
            lines.append('')
            lines.append(f'    // Assert: No duplicates created')
            lines.append(f'    if (result1.success) {{')
            lines.append(f'      expect(checker.checkNoDuplicates(keyFields)).toBe(true);')
            lines.append(f'    }}')
            lines.append('  });')

        elif tc.pattern == "retry_safety":
            lines.append(f"  test('{tc.description}', async () => {{")
            lines.append(f'    // Arrange')
            lines.append(f'    const inputData = createValidInput();')
            lines.append('')
            lines.append(f'    // Act: Simulate failure on first attempt, success on retry')
            lines.append(f'    const result1 = await executeWithFailure{self._to_pascal(cmd_name)}(inputData);')
            lines.append('')
            lines.append(f'    // Retry')
            lines.append(f'    const result2 = await execute{self._to_pascal(cmd_name)}(inputData);')
            lines.append('')
            lines.append(f'    // Assert: Retry should succeed or return idempotent error')
            lines.append(f'    expect(')
            lines.append(f'      result2.success || ["DUPLICATE", "ALREADY_EXISTS"].includes(result2.errorCode || "")')
            lines.append(f'    ).toBe(true);')
            lines.append('  });')

        return lines

    def _render_helper_functions(self, cmd_name: str) -> list[str]:
        """Render helper functions for a command"""
        pascal = self._to_pascal(cmd_name)
        return [
            f'  function createValidInput(): Record<string, unknown> {{',
            f'    // TODO: Generate from spec',
            f'    return {{}};',
            f'  }}',
            '',
            f'  async function execute{pascal}(inputData: Record<string, unknown>): Promise<IdempotencyResult> {{',
            f'    // TODO: Call actual implementation',
            f'    throw new Error("Requires {cmd_name} implementation");',
            f'  }}',
            '',
            f'  async function executeWithFailure{pascal}(inputData: Record<string, unknown>): Promise<IdempotencyResult> {{',
            f'    // TODO: Simulate partial failure',
            f'    return {{ success: false, errorCode: "PARTIAL_FAILURE" }};',
            f'  }}',
        ]

    def _to_snake(self, name: str) -> str:
        """Convert to snake_case"""
        import re
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

    def _to_pascal(self, name: str) -> str:
        """Convert to PascalCase"""
        return "".join(word.capitalize() for word in self._to_snake(name).split("_"))
