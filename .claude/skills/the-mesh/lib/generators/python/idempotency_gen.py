"""Mesh to pytest Idempotency Test Generator

Generates idempotency tests for commands specified in testStrategies.

Idempotency means: executing the same operation multiple times
produces the same result as executing it once.

Test patterns generated:
1. Double execution - same input twice should not create duplicates
2. Retry safety - if first call fails midway, retry should succeed
3. Concurrent retry - two identical calls at same time should be safe
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
    pattern: str  # 'double_exec', 'retry_safety', 'concurrent_retry'
    idempotency_key_fields: list[str]  # Fields that identify a unique operation


class IdempotencyTestGenerator:
    """Generates pytest idempotency tests from TRIR specification"""

    def __init__(self, spec: dict[str, Any]):
        self.spec = spec
        self.entities = spec.get("entities", spec.get("entities", {}))
        self.commands = spec.get("commands", spec.get("commands", {}))
        self.test_strategies = spec.get("testStrategies", {})

    def generate_all(self) -> str:
        """Generate all idempotency tests"""
        # Get targets from testStrategies
        idempotency_config = self.test_strategies.get("templates", {}).get("idempotency", {})

        if not idempotency_config.get("enabled", False):
            return self._render_empty_tests()

        targets = idempotency_config.get("targets", [])
        if not targets:
            # Default: test all commands that create entities
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
            # Heuristic: commands with 'create', 'add', 'register' in name
            # or commands that have post actions with 'create'
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

        # Identify idempotency key fields (usually required input fields)
        input_fields = cmd_def.get("input", {})
        key_fields = [
            name for name, field in input_fields.items()
            if field.get("required", False) or field.get("type") == "id" or "Id" in name
        ]

        # Pattern 1: Double execution
        cases.append(IdempotencyTestCase(
            id=f"idempotency_{cmd_name}_double_exec",
            description=f"{cmd_name}: executing twice with same input should not create duplicates",
            command=cmd_name,
            entity=entity,
            pattern="double_exec",
            idempotency_key_fields=key_fields,
        ))

        # Pattern 2: Retry safety (for commands that might fail midway)
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
        return '''"""
Auto-generated Idempotency Tests from TRIR specification

Idempotency testing is DISABLED in testStrategies.
To enable, set testStrategies.templates.idempotency.enabled = true

@generated
"""

import pytest


class TestIdempotency:
    """Idempotency tests (disabled)"""

    @pytest.mark.skip(reason="Idempotency tests disabled in testStrategies")
    def test_placeholder(self):
        pass
'''

    def _render_tests(self, test_cases: list[IdempotencyTestCase]) -> str:
        """Render test cases to executable pytest code"""
        lines = [
            '"""',
            'Auto-generated Idempotency Tests from TRIR specification',
            '',
            'These tests verify that commands are idempotent:',
            '- Executing the same operation twice produces the same result',
            '- Retrying a failed operation is safe',
            '',
            '@generated',
            '"""',
            '',
            'import pytest',
            'import asyncio',
            'from typing import Any, Callable',
            'from dataclasses import dataclass',
            '',
            '',
            '# ========== Test Infrastructure ==========',
            '',
            '@dataclass',
            'class IdempotencyResult:',
            '    """Result of an idempotent operation"""',
            '    success: bool',
            '    error_code: str | None = None',
            '    data: Any = None',
            '    is_duplicate: bool = False',
            '',
            '',
            'class IdempotencyChecker:',
            '    """Helper for checking idempotency properties"""',
            '',
            '    def __init__(self, count_func: Callable[[dict], int]):',
            '        """',
            '        Args:',
            '            count_func: Function that counts entities matching criteria',
            '        """',
            '        self.count_func = count_func',
            '',
            '    def check_no_duplicates(self, key_fields: dict, expected_count: int = 1) -> bool:',
            '        """Check that executing multiple times did not create duplicates"""',
            '        actual_count = self.count_func(key_fields)',
            '        return actual_count == expected_count',
            '',
            '    def is_idempotent_result(self, result1: IdempotencyResult, result2: IdempotencyResult) -> bool:',
            '        """Check if two results indicate idempotent behavior"""',
            '        # Both succeed with same data',
            '        if result1.success and result2.success:',
            '            return result1.data == result2.data or result2.is_duplicate',
            '        # First succeeds, second indicates duplicate',
            '        if result1.success and not result2.success:',
            '            return result2.error_code in ["DUPLICATE", "ALREADY_EXISTS", "CONFLICT"]',
            '        # Both fail with same error',
            '        if not result1.success and not result2.success:',
            '            return result1.error_code == result2.error_code',
            '        return False',
            '',
            '',
            '# ========== Fixtures ==========',
            '',
            '@pytest.fixture',
            'def idempotency_checker():',
            '    """Create an idempotency checker with mock count function"""',
            '    # TODO: Replace with actual entity count function',
            '    call_count = {"value": 0}',
            '    ',
            '    def mock_count(key_fields: dict) -> int:',
            '        # In real implementation, query database',
            '        return call_count["value"]',
            '    ',
            '    return IdempotencyChecker(mock_count)',
            '',
            '',
        ]

        # Group by command
        by_command: dict[str, list[IdempotencyTestCase]] = {}
        for tc in test_cases:
            if tc.command not in by_command:
                by_command[tc.command] = []
            by_command[tc.command].append(tc)

        lines.append('# ========== Tests ==========')
        lines.append('')

        for cmd_name, cases in by_command.items():
            class_name = f"TestIdempotency{self._to_pascal(cmd_name)}"

            lines.append(f'class {class_name}:')
            lines.append(f'    """Idempotency tests for {cmd_name}"""')
            lines.append('')

            for tc in cases:
                lines.extend(self._render_test_method(tc))
                lines.append('')

        return '\n'.join(lines)

    def _render_test_method(self, tc: IdempotencyTestCase) -> list[str]:
        """Render a single test method"""
        lines = []
        method_name = f"test_{tc.id}"
        cmd_name = tc.command
        entity = tc.entity

        if tc.pattern == "double_exec":
            lines.append(f'    def {method_name}(self, idempotency_checker):')
            lines.append(f'        """{tc.description}"""')
            lines.append(f'        # Arrange: Create valid input for {cmd_name}')
            lines.append(f'        input_data = self._create_valid_input()')
            lines.append(f'        key_fields = {{')
            for field in tc.idempotency_key_fields:
                lines.append(f'            "{field}": input_data.get("{field}"),')
            lines.append(f'        }}')
            lines.append('')
            lines.append(f'        # Act: Execute {cmd_name} twice with same input')
            lines.append(f'        result1 = self._execute_{self._to_snake(cmd_name)}(input_data)')
            lines.append(f'        result2 = self._execute_{self._to_snake(cmd_name)}(input_data)')
            lines.append('')
            lines.append(f'        # Assert: Results should be idempotent')
            lines.append(f'        assert idempotency_checker.is_idempotent_result(result1, result2), \\')
            lines.append(f'            f"Expected idempotent result: first={{result1}}, second={{result2}}"')
            lines.append('')
            lines.append(f'        # Assert: No duplicates created')
            lines.append(f'        if result1.success:')
            lines.append(f'            assert idempotency_checker.check_no_duplicates(key_fields), \\')
            lines.append(f'                "Duplicate {entity} was created"')
            lines.append('')
            lines.append(f'    def _create_valid_input(self) -> dict:')
            lines.append(f'        """Create valid input for {cmd_name}"""')
            lines.append(f'        # TODO: Generate from spec')
            lines.append(f'        return {{}}')
            lines.append('')
            lines.append(f'    def _execute_{self._to_snake(cmd_name)}(self, input_data: dict) -> IdempotencyResult:')
            lines.append(f'        """Execute {cmd_name} and return result"""')
            lines.append(f'        # TODO: Call actual implementation')
            lines.append(f'        pytest.skip("Requires {cmd_name} implementation")')

        elif tc.pattern == "retry_safety":
            lines.append(f'    def {method_name}(self, idempotency_checker):')
            lines.append(f'        """{tc.description}"""')
            lines.append(f'        # Arrange')
            lines.append(f'        input_data = self._create_valid_input()')
            lines.append('')
            lines.append(f'        # Act: Simulate failure on first attempt, success on retry')
            lines.append(f'        # First call - inject failure')
            lines.append(f'        with self._simulate_partial_failure():')
            lines.append(f'            result1 = self._execute_{self._to_snake(cmd_name)}(input_data)')
            lines.append('')
            lines.append(f'        # Retry')
            lines.append(f'        result2 = self._execute_{self._to_snake(cmd_name)}(input_data)')
            lines.append('')
            lines.append(f'        # Assert: Retry should succeed or return idempotent error')
            lines.append(f'        assert result2.success or result2.error_code in ["DUPLICATE", "ALREADY_EXISTS"], \\')
            lines.append(f'            f"Retry failed unexpectedly: {{result2}}"')
            lines.append('')
            lines.append(f'    @staticmethod')
            lines.append(f'    def _simulate_partial_failure():')
            lines.append(f'        """Context manager to simulate partial failure"""')
            lines.append(f'        import contextlib')
            lines.append(f'        @contextlib.contextmanager')
            lines.append(f'        def _manager():')
            lines.append(f'            # TODO: Inject failure mechanism')
            lines.append(f'            yield')
            lines.append(f'        return _manager()')

        return lines

    def _to_snake(self, name: str) -> str:
        """Convert to snake_case"""
        import re
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

    def _to_pascal(self, name: str) -> str:
        """Convert to PascalCase"""
        return "".join(word.capitalize() for word in self._to_snake(name).split("_"))
