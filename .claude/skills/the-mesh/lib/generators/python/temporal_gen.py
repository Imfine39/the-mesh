"""Mesh to pytest Temporal Test Generator

Generates tests for time-based logic from deadlines, schedules, and temporal expressions.

Test patterns generated:
1. Deadline expiration - action after deadline should fail/trigger
2. Deadline before expiration - action before deadline should succeed
3. Schedule trigger - scheduled job runs at correct time
4. Time-based state transition - state changes based on time
5. Temporal field validation - datetime fields validate correctly
"""

from typing import Any
from dataclasses import dataclass


@dataclass
class TemporalTestCase:
    """Represents a temporal test case"""
    id: str
    description: str
    target: str  # entity or deadline name
    pattern: str  # 'deadline_expired', 'deadline_valid', 'schedule_trigger', 'time_transition', 'datetime_field'
    deadline_duration: str | None  # e.g., "24h", "7d"
    action: str | None
    field: str | None


class TemporalTestGenerator:
    """Generates pytest temporal tests from TRIR specification"""

    def __init__(self, spec: dict[str, Any]):
        self.spec = spec
        self.entities = spec.get("entities", spec.get("entities", {}))
        self.deadlines = spec.get("deadlines", {})
        self.schedules = spec.get("schedules", {})
        self.state_machines = spec.get("stateMachines", {})
        self.commands = spec.get("commands", spec.get("commands", {}))

    def generate_all(self) -> str:
        """Generate all temporal tests"""
        test_cases = []

        # Generate from deadlines
        for deadline_name, deadline_def in self.deadlines.items():
            test_cases.extend(self._generate_deadline_tests(deadline_name, deadline_def))

        # Generate from schedules
        for schedule_name, schedule_def in self.schedules.items():
            test_cases.extend(self._generate_schedule_tests(schedule_name, schedule_def))

        # Generate from state machine timer transitions
        for sm_name, sm_def in self.state_machines.items():
            test_cases.extend(self._generate_timer_transition_tests(sm_name, sm_def))

        # Generate from datetime fields in entities
        for entity_name, entity_def in self.entities.items():
            test_cases.extend(self._generate_datetime_field_tests(entity_name, entity_def))

        if not test_cases:
            return self._render_empty_tests()

        return self._render_tests(test_cases)

    def _generate_deadline_tests(self, name: str, deadline_def: dict) -> list[TemporalTestCase]:
        """Generate tests for a deadline definition"""
        cases = []
        duration = deadline_def.get("duration", deadline_def.get("after", "24h"))
        action = deadline_def.get("action", deadline_def.get("onExpire"))
        entity = deadline_def.get("entity", "")

        # Test 1: Action after deadline should trigger/fail
        cases.append(TemporalTestCase(
            id=f"deadline_{name}_expired",
            description=f"Deadline '{name}': action after {duration} should trigger deadline behavior",
            target=name,
            pattern="deadline_expired",
            deadline_duration=duration,
            action=action,
            field=None,
        ))

        # Test 2: Action before deadline should succeed normally
        cases.append(TemporalTestCase(
            id=f"deadline_{name}_valid",
            description=f"Deadline '{name}': action before {duration} should succeed normally",
            target=name,
            pattern="deadline_valid",
            deadline_duration=duration,
            action=action,
            field=None,
        ))

        return cases

    def _generate_schedule_tests(self, name: str, schedule_def: dict) -> list[TemporalTestCase]:
        """Generate tests for a schedule definition"""
        cases = []
        cron = schedule_def.get("cron", schedule_def.get("schedule", ""))
        action = schedule_def.get("action", schedule_def.get("run", ""))

        cases.append(TemporalTestCase(
            id=f"schedule_{name}_trigger",
            description=f"Schedule '{name}': should trigger '{action}' at scheduled time",
            target=name,
            pattern="schedule_trigger",
            deadline_duration=cron,
            action=action,
            field=None,
        ))

        return cases

    def _generate_timer_transition_tests(self, sm_name: str, sm_def: dict) -> list[TemporalTestCase]:
        """Generate tests for timer-based state transitions"""
        cases = []
        transitions = sm_def.get("transitions", [])

        for transition in transitions:
            trigger = transition.get("trigger", "")
            if trigger == "timer":
                trans_id = transition.get("id", "")
                from_state = transition.get("from", "")
                to_state = transition.get("to", "")
                duration = transition.get("after", transition.get("duration", ""))

                cases.append(TemporalTestCase(
                    id=f"timer_{sm_name}_{trans_id}",
                    description=f"{sm_name}: should transition from {from_state} to {to_state} after {duration}",
                    target=sm_name,
                    pattern="time_transition",
                    deadline_duration=duration,
                    action=trans_id,
                    field=None,
                ))

        return cases

    def _generate_datetime_field_tests(self, entity_name: str, entity_def: dict) -> list[TemporalTestCase]:
        """Generate tests for datetime fields"""
        cases = []
        fields = entity_def.get("fields", {})

        for field_name, field_def in fields.items():
            field_type = field_def.get("type", "")
            if field_type == "datetime":
                cases.append(TemporalTestCase(
                    id=f"datetime_{entity_name}_{field_name}",
                    description=f"{entity_name}.{field_name}: datetime field should validate correctly",
                    target=entity_name,
                    pattern="datetime_field",
                    deadline_duration=None,
                    action=None,
                    field=field_name,
                ))

        return cases

    def _render_empty_tests(self) -> str:
        """Render placeholder when no temporal elements found"""
        return '''"""
Auto-generated Temporal Tests from TRIR specification

No deadlines, schedules, or temporal fields found.

@generated
"""

import pytest


class TestTemporal:
    """Temporal tests"""

    @pytest.mark.skip(reason="No temporal elements found")
    def test_placeholder(self):
        pass
'''

    def _render_tests(self, test_cases: list[TemporalTestCase]) -> str:
        """Render test cases to executable pytest code"""
        lines = [
            '"""',
            'Auto-generated Temporal Tests from TRIR specification',
            '',
            'These tests verify time-based behavior:',
            '- Deadline expiration triggers correct behavior',
            '- Scheduled jobs run at correct times',
            '- Time-based state transitions work correctly',
            '- Datetime fields validate properly',
            '',
            '@generated',
            '"""',
            '',
            'import pytest',
            'from datetime import datetime, timedelta',
            'from typing import Any, Callable',
            'from unittest.mock import patch, MagicMock',
            'import re',
            '',
            '',
            '# ========== Test Infrastructure ==========',
            '',
            'class TimeController:',
            '    """Helper for controlling time in tests"""',
            '',
            '    def __init__(self):',
            '        self._current_time = datetime.now()',
            '        self._frozen = False',
            '',
            '    def freeze(self, at: datetime = None):',
            '        """Freeze time at specified moment"""',
            '        self._frozen = True',
            '        self._current_time = at or datetime.now()',
            '',
            '    def advance(self, **kwargs):',
            '        """Advance time by specified duration"""',
            '        self._current_time += timedelta(**kwargs)',
            '',
            '    def advance_by_duration(self, duration_str: str):',
            '        """Advance time by duration string like "24h" or "7d" """',
            '        amount, unit = self._parse_duration(duration_str)',
            '        if unit == "s":',
            '            self.advance(seconds=amount)',
            '        elif unit == "m":',
            '            self.advance(minutes=amount)',
            '        elif unit == "h":',
            '            self.advance(hours=amount)',
            '        elif unit == "d":',
            '            self.advance(days=amount)',
            '',
            '    def now(self) -> datetime:',
            '        """Get current (possibly frozen) time"""',
            '        return self._current_time',
            '',
            '    @staticmethod',
            '    def _parse_duration(duration_str: str) -> tuple[int, str]:',
            '        """Parse duration string like "24h" into (24, "h")"""',
            '        if not duration_str:',
            '            return 0, "s"',
            '        match = re.match(r"(\\d+)([smhd])?", duration_str)',
            '        if match:',
            '            return int(match.group(1)), match.group(2) or "s"',
            '        return 0, "s"',
            '',
            '',
            'class DeadlineChecker:',
            '    """Helper for deadline tests"""',
            '',
            '    def __init__(self, time_controller: TimeController):',
            '        self.time = time_controller',
            '',
            '    def is_expired(self, created_at: datetime, duration_str: str) -> bool:',
            '        """Check if deadline has expired"""',
            '        amount, unit = TimeController._parse_duration(duration_str)',
            '        delta = {',
            '            "s": timedelta(seconds=amount),',
            '            "m": timedelta(minutes=amount),',
            '            "h": timedelta(hours=amount),',
            '            "d": timedelta(days=amount),',
            '        }.get(unit, timedelta())',
            '        deadline = created_at + delta',
            '        return self.time.now() > deadline',
            '',
            '',
            '# ========== Fixtures ==========',
            '',
            '@pytest.fixture',
            'def time_controller():',
            '    """Create time controller for tests"""',
            '    return TimeController()',
            '',
            '',
            '@pytest.fixture',
            'def deadline_checker(time_controller):',
            '    """Create deadline checker"""',
            '    return DeadlineChecker(time_controller)',
            '',
            '',
        ]

        # Group by pattern type
        by_pattern: dict[str, list[TemporalTestCase]] = {}
        for tc in test_cases:
            if tc.pattern not in by_pattern:
                by_pattern[tc.pattern] = []
            by_pattern[tc.pattern].append(tc)

        lines.append('# ========== Tests ==========')
        lines.append('')

        # Generate test classes by pattern
        pattern_class_names = {
            "deadline_expired": "TestDeadlineExpiration",
            "deadline_valid": "TestDeadlineValid",
            "schedule_trigger": "TestScheduleTrigger",
            "time_transition": "TestTimeTransition",
            "datetime_field": "TestDatetimeFields",
        }

        for pattern, cases in by_pattern.items():
            class_name = pattern_class_names.get(pattern, f"TestTemporal{pattern.title()}")
            lines.append(f'class {class_name}:')
            lines.append(f'    """Tests for {pattern.replace("_", " ")}"""')
            lines.append('')

            for tc in cases:
                lines.extend(self._render_test_method(tc))
                lines.append('')

        return '\n'.join(lines)

    def _render_test_method(self, tc: TemporalTestCase) -> list[str]:
        """Render a single test method"""
        lines = []
        method_name = f"test_{tc.id}"

        if tc.pattern == "deadline_expired":
            lines.append(f'    def {method_name}(self, time_controller, deadline_checker):')
            lines.append(f'        """{tc.description}"""')
            lines.append(f'        # Arrange: Create entity and freeze time')
            lines.append(f'        time_controller.freeze()')
            lines.append(f'        created_at = time_controller.now()')
            lines.append(f'        ')
            lines.append(f'        # Act: Advance time past deadline')
            lines.append(f'        time_controller.advance_by_duration("{tc.deadline_duration}")')
            lines.append(f'        time_controller.advance(seconds=1)  # Just past deadline')
            lines.append(f'        ')
            lines.append(f'        # Assert: Deadline should be expired')
            lines.append(f'        assert deadline_checker.is_expired(created_at, "{tc.deadline_duration}"), \\')
            lines.append(f'            "Deadline should be expired after {tc.deadline_duration}"')
            lines.append(f'        ')
            lines.append(f'        # Assert: Action should trigger deadline behavior')
            lines.append(f'        # TODO: Verify {tc.action} triggers or action is blocked')
            lines.append(f'        pytest.skip("Requires deadline handler implementation")')

        elif tc.pattern == "deadline_valid":
            lines.append(f'    def {method_name}(self, time_controller, deadline_checker):')
            lines.append(f'        """{tc.description}"""')
            lines.append(f'        # Arrange: Create entity and freeze time')
            lines.append(f'        time_controller.freeze()')
            lines.append(f'        created_at = time_controller.now()')
            lines.append(f'        ')
            lines.append(f'        # Act: Advance time but stay within deadline')
            lines.append(f'        # (advance half the duration)')
            lines.append(f'        time_controller.advance_by_duration("{tc.deadline_duration}")')
            lines.append(f'        time_controller.advance(seconds=-1)  # Just before deadline')
            lines.append(f'        ')
            lines.append(f'        # Assert: Deadline should NOT be expired')
            lines.append(f'        assert not deadline_checker.is_expired(created_at, "{tc.deadline_duration}"), \\')
            lines.append(f'            "Deadline should not be expired before {tc.deadline_duration}"')
            lines.append(f'        ')
            lines.append(f'        # Assert: Normal action should succeed')
            lines.append(f'        # TODO: Verify normal operation works')
            lines.append(f'        pytest.skip("Requires action implementation")')

        elif tc.pattern == "schedule_trigger":
            lines.append(f'    def {method_name}(self, time_controller):')
            lines.append(f'        """{tc.description}"""')
            lines.append(f'        # Arrange: Setup schedule monitor')
            lines.append(f'        schedule_cron = "{tc.deadline_duration}"')
            lines.append(f'        action_called = False')
            lines.append(f'        ')
            lines.append(f'        def mock_action():')
            lines.append(f'            nonlocal action_called')
            lines.append(f'            action_called = True')
            lines.append(f'        ')
            lines.append(f'        # Act: Simulate time reaching schedule trigger')
            lines.append(f'        # TODO: Integrate with actual scheduler')
            lines.append(f'        ')
            lines.append(f'        # Assert: Action should be called')
            lines.append(f'        # assert action_called, "Scheduled action should have been triggered"')
            lines.append(f'        pytest.skip("Requires scheduler implementation")')

        elif tc.pattern == "time_transition":
            lines.append(f'    def {method_name}(self, time_controller):')
            lines.append(f'        """{tc.description}"""')
            lines.append(f'        # Arrange: Create entity in initial state')
            lines.append(f'        time_controller.freeze()')
            lines.append(f'        initial_state = self._create_entity_in_state()')
            lines.append(f'        ')
            lines.append(f'        # Act: Advance time past transition threshold')
            lines.append(f'        time_controller.advance_by_duration("{tc.deadline_duration}")')
            lines.append(f'        ')
            lines.append(f'        # Assert: State should have transitioned')
            lines.append(f'        # TODO: Verify state machine processed timer transition')
            lines.append(f'        pytest.skip("Requires state machine timer implementation")')
            lines.append('')
            lines.append(f'    def _create_entity_in_state(self) -> dict:')
            lines.append(f'        """Create entity in appropriate initial state"""')
            lines.append(f'        return {{"state": "initial"}}')

        elif tc.pattern == "datetime_field":
            lines.append(f'    def {method_name}(self):')
            lines.append(f'        """{tc.description}"""')
            lines.append(f'        # Test valid datetime')
            lines.append(f'        valid_dt = datetime.now().isoformat()')
            lines.append(f'        # TODO: Validate {tc.target}.{tc.field} accepts valid datetime')
            lines.append(f'        ')
            lines.append(f'        # Test invalid datetime format')
            lines.append(f'        invalid_dt = "not-a-datetime"')
            lines.append(f'        # TODO: Validate {tc.target}.{tc.field} rejects invalid datetime')
            lines.append(f'        ')
            lines.append(f'        # Test edge cases')
            lines.append(f'        edge_cases = [')
            lines.append(f'            datetime.min.isoformat(),  # Minimum datetime')
            lines.append(f'            datetime.max.isoformat(),  # Maximum datetime')
            lines.append(f'            "2024-02-29T00:00:00",     # Leap year')
            lines.append(f'        ]')
            lines.append(f'        # TODO: Test edge cases for {tc.field}')
            lines.append(f'        pytest.skip("Requires field validation implementation")')

        return lines

    def _to_snake(self, name: str) -> str:
        """Convert to snake_case"""
        import re
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
