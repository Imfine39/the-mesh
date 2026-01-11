"""Mesh to Jest Concurrency Test Generator

Generates concurrency tests for entities specified in testStrategies.

Test patterns generated:
1. Parallel same operation - multiple identical operations at once
2. Parallel conflicting - operations that conflict (e.g., both decrement stock)
3. Read-write race - read during write should see consistent state
"""

from typing import Any
from dataclasses import dataclass


@dataclass
class ConcurrencyTestCase:
    """Represents a concurrency test case"""
    id: str
    description: str
    entity: str
    pattern: str  # 'parallel_same', 'parallel_conflict', 'read_write_race'
    parallel_count: int
    operations: list[str]


class JestConcurrencyGenerator:
    """Generates Jest concurrency tests from TRIR specification"""

    def __init__(self, spec: dict[str, Any]):
        self.spec = spec
        self.entities = spec.get("entities", {})
        self.commands = spec.get("commands", {})
        self.test_strategies = spec.get("testStrategies", {})

    def generate_all(self) -> str:
        """Generate all concurrency tests"""
        concurrency_config = self.test_strategies.get("templates", {}).get("concurrency", {})

        if not concurrency_config.get("enabled", False):
            return self._render_empty_tests()

        targets = concurrency_config.get("targets", [])
        parallel_count = concurrency_config.get("parallelRequests", 2)

        if not targets:
            targets = self._infer_concurrent_entities()

        test_cases = []
        for entity_name in targets:
            entity_def = self.entities.get(entity_name)
            if entity_def:
                test_cases.extend(
                    self._generate_tests_for_entity(entity_name, entity_def, parallel_count)
                )

        return self._render_tests(test_cases)

    def _infer_concurrent_entities(self) -> list[str]:
        """Infer which entities likely need concurrency testing"""
        concurrent_entities = []
        for entity_name, entity_def in self.entities.items():
            fields = entity_def.get("fields", {})
            for field_name, field_def in fields.items():
                preset = field_def.get("preset", "")
                if preset in ["money", "count"] or "stock" in field_name.lower():
                    concurrent_entities.append(entity_name)
                    break
        return concurrent_entities

    def _get_commands_for_entity(self, entity_name: str) -> list[str]:
        """Get commands that operate on an entity"""
        commands = []
        for cmd_name, cmd_def in self.commands.items():
            if cmd_def.get("entity") == entity_name:
                commands.append(cmd_name)
        return commands

    def _generate_tests_for_entity(
        self, entity_name: str, entity_def: dict, parallel_count: int
    ) -> list[ConcurrencyTestCase]:
        """Generate concurrency test cases for an entity"""
        cases = []
        related_commands = self._get_commands_for_entity(entity_name)

        for cmd_name in related_commands:
            cases.append(ConcurrencyTestCase(
                id=f"concurrent_{entity_name}_{cmd_name}_parallel_same",
                description=f"{cmd_name}: {parallel_count} parallel executions should not corrupt data",
                entity=entity_name,
                pattern="parallel_same",
                parallel_count=parallel_count,
                operations=[cmd_name],
            ))

        fields = entity_def.get("fields", {})
        has_count_field = any(
            f.get("preset") == "count" or "stock" in fname.lower()
            for fname, f in fields.items()
        )
        if has_count_field and len(related_commands) >= 2:
            cases.append(ConcurrencyTestCase(
                id=f"concurrent_{entity_name}_parallel_conflict",
                description=f"{entity_name}: conflicting operations should not cause oversell",
                entity=entity_name,
                pattern="parallel_conflict",
                parallel_count=parallel_count,
                operations=related_commands[:2],
            ))

        cases.append(ConcurrencyTestCase(
            id=f"concurrent_{entity_name}_read_write_race",
            description=f"{entity_name}: read during write should see consistent state",
            entity=entity_name,
            pattern="read_write_race",
            parallel_count=parallel_count,
            operations=related_commands[:1] if related_commands else [],
        ))

        return cases

    def _render_empty_tests(self) -> str:
        """Render placeholder when concurrency tests are disabled"""
        return '''/**
 * Auto-generated Concurrency Tests from TRIR specification
 *
 * Concurrency testing is DISABLED in testStrategies.
 * To enable, set testStrategies.templates.concurrency.enabled = true
 *
 * @generated
 */

describe('Concurrency Tests (disabled)', () => {
  test.skip('placeholder', () => {
    // Concurrency tests disabled in testStrategies
  });
});
'''

    def _render_tests(self, test_cases: list[ConcurrencyTestCase]) -> str:
        """Render test cases to executable Jest code"""
        lines = [
            '/**',
            ' * Auto-generated Concurrency Tests from TRIR specification',
            ' *',
            ' * These tests verify that concurrent operations are safe:',
            ' * - Multiple parallel operations do not corrupt data',
            ' * - Conflicting operations are properly serialized',
            ' * - Reads see consistent state during writes',
            ' *',
            ' * @generated',
            ' */',
            '',
            '// ========== Test Infrastructure ==========',
            '',
            'interface ConcurrencyResult {',
            '  success: boolean;',
            '  error?: string;',
            '  value?: unknown;',
            '  taskId: number;',
            '}',
            '',
            'async function runParallel<T>(',
            '  count: number,',
            '  operation: (taskId: number) => Promise<T>',
            '): Promise<ConcurrencyResult[]> {',
            '  const tasks = Array.from({ length: count }, (_, i) =>',
            '    operation(i)',
            '      .then(value => ({ success: true, value, taskId: i } as ConcurrencyResult))',
            '      .catch(error => ({ success: false, error: String(error), taskId: i } as ConcurrencyResult))',
            '  );',
            '  return Promise.all(tasks);',
            '}',
            '',
        ]

        by_entity: dict[str, list[ConcurrencyTestCase]] = {}
        for tc in test_cases:
            if tc.entity not in by_entity:
                by_entity[tc.entity] = []
            by_entity[tc.entity].append(tc)

        lines.append('// ========== Tests ==========')
        lines.append('')

        for entity_name, cases in by_entity.items():
            lines.append(f"describe('Concurrency: {entity_name}', () => {{")
            lines.append('')

            for tc in cases:
                lines.extend(self._render_test_method(tc))
                lines.append('')

            lines.extend(self._render_helper_functions(entity_name, cases))
            lines.append('});')
            lines.append('')

        return '\n'.join(lines)

    def _render_test_method(self, tc: ConcurrencyTestCase) -> list[str]:
        """Render a single test method"""
        lines = []

        if tc.pattern == "parallel_same":
            cmd_name = tc.operations[0] if tc.operations else "operation"
            lines.append(f"  test('{tc.description}', async () => {{")
            lines.append(f'    // Arrange: Setup initial state')
            lines.append(f'    const initialState = await setupInitialState();')
            lines.append(f'    ')
            lines.append(f'    // Act: Run {tc.parallel_count} parallel operations')
            lines.append(f'    const results = await runParallel({tc.parallel_count}, async (taskId) => {{')
            lines.append(f'      return execute{self._to_pascal(cmd_name)}(initialState);')
            lines.append(f'    }});')
            lines.append(f'    ')
            lines.append(f'    // Assert: All should succeed or fail predictably')
            lines.append(f'    const successCount = results.filter(r => r.success).length;')
            lines.append(f'    expect(successCount).toBeGreaterThanOrEqual(1);')
            lines.append(f'    ')
            lines.append(f'    // Assert: Final state should be consistent')
            lines.append(f'    const finalState = await getFinalState();')
            lines.append(f'    expect(isConsistentState(finalState)).toBe(true);')
            lines.append('  });')

        elif tc.pattern == "parallel_conflict":
            lines.append(f"  test('{tc.description}', async () => {{")
            lines.append(f'    // Arrange: Setup state near boundary')
            lines.append(f'    await setupBoundaryState();')
            lines.append(f'    ')
            lines.append(f'    // Act: Run conflicting operations in parallel')
            lines.append(f'    // TODO: Run {tc.operations} concurrently')
            lines.append(f'    throw new Error("Requires conflict test implementation");')
            lines.append(f'    ')
            lines.append(f'    // Assert: No oversell, no negative values')
            lines.append(f'    const finalState = await getFinalState();')
            lines.append(f'    expect(noInvariantViolations(finalState)).toBe(true);')
            lines.append('  });')

        elif tc.pattern == "read_write_race":
            lines.append(f"  test('{tc.description}', async () => {{")
            lines.append(f'    // Arrange')
            lines.append(f'    await setupInitialState();')
            lines.append(f'    ')
            lines.append(f'    // Act: Read and write concurrently')
            lines.append(f'    // TODO: Run read and write in parallel')
            lines.append(f'    throw new Error("Requires read-write race test implementation");')
            lines.append(f'    ')
            lines.append(f'    // Assert: Reads should see consistent snapshots')
            lines.append('  });')

        return lines

    def _render_helper_functions(self, entity_name: str, cases: list[ConcurrencyTestCase]) -> list[str]:
        """Render helper functions for an entity"""
        lines = [
            f'  async function setupInitialState(): Promise<Record<string, unknown>> {{',
            f'    // TODO: Create {entity_name} with known state',
            f'    throw new Error("Requires test setup implementation");',
            f'  }}',
            '',
            f'  async function setupBoundaryState(): Promise<void> {{',
            f'    // TODO: Setup state near boundary (e.g., low stock)',
            f'  }}',
            '',
            f'  async function getFinalState(): Promise<Record<string, unknown>> {{',
            f'    // TODO: Read current state',
            f'    return {{}};',
            f'  }}',
            '',
            f'  function isConsistentState(state: Record<string, unknown>): boolean {{',
            f'    // TODO: Validate invariants',
            f'    return true;',
            f'  }}',
            '',
            f'  function noInvariantViolations(state: Record<string, unknown>): boolean {{',
            f'    // TODO: Check stock >= 0, balance >= 0, etc.',
            f'    return true;',
            f'  }}',
        ]

        # Add execute functions for each operation
        operations = set()
        for tc in cases:
            operations.update(tc.operations)

        for op in operations:
            lines.extend([
                '',
                f'  async function execute{self._to_pascal(op)}(state: Record<string, unknown>): Promise<unknown> {{',
                f'    // TODO: Call actual implementation',
                f'    throw new Error("Requires implementation");',
                f'  }}',
            ])

        return lines

    def _to_snake(self, name: str) -> str:
        """Convert to snake_case"""
        import re
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

    def _to_pascal(self, name: str) -> str:
        """Convert to PascalCase"""
        return "".join(word.capitalize() for word in self._to_snake(name).split("_"))
