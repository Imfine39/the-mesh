"""Mesh to pytest Concurrency Test Generator

Generates concurrency tests for entities specified in testStrategies.

Concurrency means: multiple operations accessing the same resource
simultaneously should behave correctly (no race conditions, data corruption).

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
    operations: list[str]  # Operations to run concurrently


class ConcurrencyTestGenerator:
    """Generates pytest concurrency tests from TRIR specification"""

    def __init__(self, spec: dict[str, Any]):
        self.spec = spec
        self.entities = spec.get("entities", spec.get("entities", {}))
        self.commands = spec.get("commands", spec.get("commands", {}))
        self.test_strategies = spec.get("testStrategies", {})

    def generate_all(self) -> str:
        """Generate all concurrency tests"""
        # Get targets from testStrategies
        concurrency_config = self.test_strategies.get("templates", {}).get("concurrency", {})

        if not concurrency_config.get("enabled", False):
            return self._render_empty_tests()

        targets = concurrency_config.get("targets", [])
        parallel_count = concurrency_config.get("parallelRequests", 2)

        if not targets:
            # Default: test entities with money or inventory fields
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
            # Entities with money, count, or stock fields are likely concurrent
            for field_name, field_def in fields.items():
                preset = field_def.get("preset", "")
                if preset in ["money", "count"] or "stock" in field_name.lower():
                    concurrent_entities.append(entity_name)
                    break
        return concurrent_entities

    def _get_commands_for_entity(self, entity_name: str) -> list[str]:
        """Get commands that operate on an entity

        Searches for commands that:
        1. Have input fields with ref to this entity
        2. Have post actions that create/update/delete this entity
        """
        commands = []
        for cmd_name, cmd_def in self.commands.items():
            found = False
            # Check input refs
            for field_def in cmd_def.get("input", {}).values():
                if isinstance(field_def, dict) and field_def.get("ref") == entity_name:
                    commands.append(cmd_name)
                    found = True
                    break
            if found:
                continue
            # Check post action targets
            for post in cmd_def.get("post", []):
                action = post.get("action", {})
                for action_type in ("create", "update", "delete"):
                    if action_type in action:
                        target = action[action_type]
                        if isinstance(target, dict):
                            target = target.get("target")
                        if target == entity_name:
                            commands.append(cmd_name)
                            found = True
                            break
                if found:
                    break
        return list(set(commands))

    def _generate_tests_for_entity(
        self, entity_name: str, entity_def: dict, parallel_count: int
    ) -> list[ConcurrencyTestCase]:
        """Generate concurrency test cases for an entity"""
        cases = []
        related_commands = self._get_commands_for_entity(entity_name)

        # Pattern 1: Parallel same operation
        for cmd_name in related_commands:
            cases.append(ConcurrencyTestCase(
                id=f"concurrent_{entity_name}_{cmd_name}_parallel_same",
                description=f"{cmd_name}: {parallel_count} parallel executions should not corrupt data",
                entity=entity_name,
                pattern="parallel_same",
                parallel_count=parallel_count,
                operations=[cmd_name],
            ))

        # Pattern 2: Parallel conflicting (for entities with count/stock)
        fields = entity_def.get("fields", {})
        has_count_field = any(
            f.get("preset") == "count" or "stock" in fname.lower()
            for fname, f in fields.items()
        )
        if has_count_field and len(related_commands) >= 2:
            cases.append(ConcurrencyTestCase(
                id=f"concurrent_{entity_name}_parallel_conflict",
                description=f"{entity_name}: conflicting operations should not cause oversell/negative count",
                entity=entity_name,
                pattern="parallel_conflict",
                parallel_count=parallel_count,
                operations=related_commands[:2],  # First two commands
            ))

        # Pattern 3: Read-write race
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
        return '''"""
Auto-generated Concurrency Tests from TRIR specification

Concurrency testing is DISABLED in testStrategies.
To enable, set testStrategies.templates.concurrency.enabled = true

@generated
"""

import pytest


class TestConcurrency:
    """Concurrency tests (disabled)"""

    @pytest.mark.skip(reason="Concurrency tests disabled in testStrategies")
    def test_placeholder(self):
        pass
'''

    def _render_tests(self, test_cases: list[ConcurrencyTestCase]) -> str:
        """Render test cases to executable pytest code"""
        lines = [
            '"""',
            'Auto-generated Concurrency Tests from TRIR specification',
            '',
            'These tests verify that concurrent operations are safe:',
            '- Multiple parallel operations do not corrupt data',
            '- Conflicting operations are properly serialized',
            '- Reads see consistent state during writes',
            '',
            '@generated',
            '"""',
            '',
            'import pytest',
            'import asyncio',
            'from typing import Any, Callable, Awaitable',
            'from dataclasses import dataclass',
            'import threading',
            'import time',
            '',
            '',
            '# ========== Test Infrastructure ==========',
            '',
            '@dataclass',
            'class ConcurrencyResult:',
            '    """Result of a concurrent operation"""',
            '    success: bool',
            '    error: str | None = None',
            '    value: Any = None',
            '    thread_id: int = 0',
            '',
            '',
            'class ConcurrencyRunner:',
            '    """Helper for running operations concurrently"""',
            '',
            '    def __init__(self, operation: Callable[..., Any]):',
            '        self.operation = operation',
            '        self.results: list[ConcurrencyResult] = []',
            '        self.lock = threading.Lock()',
            '',
            '    def run_parallel(self, count: int, *args, **kwargs) -> list[ConcurrencyResult]:',
            '        """Run operation in parallel N times"""',
            '        threads = []',
            '        self.results = []',
            '',
            '        def worker(thread_id: int):',
            '            try:',
            '                result = self.operation(*args, **kwargs)',
            '                with self.lock:',
            '                    self.results.append(ConcurrencyResult(',
            '                        success=True,',
            '                        value=result,',
            '                        thread_id=thread_id',
            '                    ))',
            '            except Exception as e:',
            '                with self.lock:',
            '                    self.results.append(ConcurrencyResult(',
            '                        success=False,',
            '                        error=str(e),',
            '                        thread_id=thread_id',
            '                    ))',
            '',
            '        for i in range(count):',
            '            t = threading.Thread(target=worker, args=(i,))',
            '            threads.append(t)',
            '',
            '        # Start all threads as close together as possible',
            '        for t in threads:',
            '            t.start()',
            '',
            '        for t in threads:',
            '            t.join()',
            '',
            '        return self.results',
            '',
            '',
            'class AsyncConcurrencyRunner:',
            '    """Helper for running async operations concurrently"""',
            '',
            '    def __init__(self, operation: Callable[..., Awaitable[Any]]):',
            '        self.operation = operation',
            '',
            '    async def run_parallel(self, count: int, *args, **kwargs) -> list[ConcurrencyResult]:',
            '        """Run async operation in parallel N times"""',
            '        async def worker(task_id: int) -> ConcurrencyResult:',
            '            try:',
            '                result = await self.operation(*args, **kwargs)',
            '                return ConcurrencyResult(success=True, value=result, thread_id=task_id)',
            '            except Exception as e:',
            '                return ConcurrencyResult(success=False, error=str(e), thread_id=task_id)',
            '',
            '        tasks = [worker(i) for i in range(count)]',
            '        return await asyncio.gather(*tasks)',
            '',
            '',
            '# ========== Fixtures ==========',
            '',
            '@pytest.fixture',
            'def concurrency_runner():',
            '    """Create a concurrency runner factory"""',
            '    def factory(operation):',
            '        return ConcurrencyRunner(operation)',
            '    return factory',
            '',
            '',
        ]

        # Group by entity
        by_entity: dict[str, list[ConcurrencyTestCase]] = {}
        for tc in test_cases:
            if tc.entity not in by_entity:
                by_entity[tc.entity] = []
            by_entity[tc.entity].append(tc)

        lines.append('# ========== Tests ==========')
        lines.append('')

        for entity_name, cases in by_entity.items():
            class_name = f"TestConcurrency{entity_name}"

            lines.append(f'class {class_name}:')
            lines.append(f'    """Concurrency tests for {entity_name}"""')
            lines.append('')

            for tc in cases:
                lines.extend(self._render_test_method(tc))
                lines.append('')

        return '\n'.join(lines)

    def _render_test_method(self, tc: ConcurrencyTestCase) -> list[str]:
        """Render a single test method"""
        lines = []
        method_name = f"test_{tc.id}"

        if tc.pattern == "parallel_same":
            lines.append(f'    def {method_name}(self, concurrency_runner):')
            lines.append(f'        """{tc.description}"""')
            lines.append(f'        # Arrange: Setup initial state')
            lines.append(f'        initial_state = self._setup_initial_state()')
            lines.append(f'        ')
            lines.append(f'        # Act: Run {tc.parallel_count} parallel operations')
            lines.append(f'        runner = concurrency_runner(self._execute_{self._to_snake(tc.operations[0])})')
            lines.append(f'        results = runner.run_parallel({tc.parallel_count}, initial_state)')
            lines.append(f'        ')
            lines.append(f'        # Assert: All should succeed or fail predictably')
            lines.append(f'        success_count = sum(1 for r in results if r.success)')
            lines.append(f'        assert success_count >= 1, "At least one operation should succeed"')
            lines.append(f'        ')
            lines.append(f'        # Assert: Final state should be consistent')
            lines.append(f'        final_state = self._get_final_state()')
            lines.append(f'        assert self._is_consistent_state(final_state), \\')
            lines.append(f'            f"Final state is inconsistent: {{final_state}}"')
            lines.append('')
            lines.append(f'    def _setup_initial_state(self) -> dict:')
            lines.append(f'        """Setup initial state for concurrency test"""')
            lines.append(f'        # TODO: Create {tc.entity} with known state')
            lines.append(f'        pytest.skip("Requires test setup implementation")')
            lines.append('')
            lines.append(f'    def _execute_{self._to_snake(tc.operations[0])}(self, state: dict) -> Any:')
            lines.append(f'        """Execute operation"""')
            lines.append(f'        # TODO: Call actual implementation')
            lines.append(f'        pytest.skip("Requires implementation")')
            lines.append('')
            lines.append(f'    def _get_final_state(self) -> dict:')
            lines.append(f'        """Get final state after operations"""')
            lines.append(f'        # TODO: Read current state')
            lines.append(f'        return {{}}')
            lines.append('')
            lines.append(f'    def _is_consistent_state(self, state: dict) -> bool:')
            lines.append(f'        """Check if state is consistent"""')
            lines.append(f'        # TODO: Validate invariants')
            lines.append(f'        return True')

        elif tc.pattern == "parallel_conflict":
            lines.append(f'    def {method_name}(self, concurrency_runner):')
            lines.append(f'        """{tc.description}"""')
            lines.append(f'        # Arrange: Setup state near boundary')
            lines.append(f'        self._setup_boundary_state()')
            lines.append(f'        ')
            lines.append(f'        # Act: Run conflicting operations in parallel')
            lines.append(f'        # This simulates race condition scenarios')
            lines.append(f'        results = []')
            lines.append(f'        ')
            lines.append(f'        # TODO: Run {tc.operations} concurrently')
            lines.append(f'        pytest.skip("Requires conflict test implementation")')
            lines.append(f'        ')
            lines.append(f'        # Assert: No oversell, no negative values')
            lines.append(f'        final_state = self._get_final_state()')
            lines.append(f'        assert self._no_invariant_violations(final_state)')
            lines.append('')
            lines.append(f'    def _setup_boundary_state(self) -> None:')
            lines.append(f'        """Setup state near boundary (e.g., low stock)"""')
            lines.append(f'        pass')
            lines.append('')
            lines.append(f'    def _no_invariant_violations(self, state: dict) -> bool:')
            lines.append(f'        """Check no invariants are violated"""')
            lines.append(f'        # TODO: Check stock >= 0, balance >= 0, etc.')
            lines.append(f'        return True')

        elif tc.pattern == "read_write_race":
            lines.append(f'    def {method_name}(self, concurrency_runner):')
            lines.append(f'        """{tc.description}"""')
            lines.append(f'        # Arrange')
            lines.append(f'        initial_state = self._setup_initial_state()')
            lines.append(f'        read_results = []')
            lines.append(f'        ')
            lines.append(f'        # Act: Read and write concurrently')
            lines.append(f'        def read_operation():')
            lines.append(f'            return self._read_{self._to_snake(tc.entity)}()')
            lines.append(f'        ')
            lines.append(f'        def write_operation():')
            lines.append(f'            return self._write_{self._to_snake(tc.entity)}()')
            lines.append(f'        ')
            lines.append(f'        # TODO: Run read and write in parallel')
            lines.append(f'        pytest.skip("Requires read-write race test implementation")')
            lines.append(f'        ')
            lines.append(f'        # Assert: Reads should see consistent snapshots')
            lines.append(f'        for result in read_results:')
            lines.append(f'            assert self._is_valid_snapshot(result), \\')
            lines.append(f'                f"Read returned inconsistent snapshot: {{result}}"')
            lines.append('')
            lines.append(f'    def _read_{self._to_snake(tc.entity)}(self) -> dict:')
            lines.append(f'        """Read current state"""')
            lines.append(f'        return {{}}')
            lines.append('')
            lines.append(f'    def _write_{self._to_snake(tc.entity)}(self) -> None:')
            lines.append(f'        """Modify state"""')
            lines.append(f'        pass')
            lines.append('')
            lines.append(f'    def _is_valid_snapshot(self, state: dict) -> bool:')
            lines.append(f'        """Check if snapshot is valid (no partial writes visible)"""')
            lines.append(f'        return True')

        return lines

    def _to_snake(self, name: str) -> str:
        """Convert to snake_case"""
        import re
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
