"""Mesh to Jest Temporal Test Generator

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


class JestTemporalGenerator:
    """Generates Jest temporal tests from TRIR specification"""

    def __init__(self, spec: dict[str, Any]):
        self.spec = spec
        self.entities = spec.get("entities", {})
        self.deadlines = spec.get("deadlines", {})
        self.schedules = spec.get("schedules", {})
        self.state_machines = spec.get("stateMachines", {})
        self.commands = spec.get("commands", {})

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
        return '''/**
 * Auto-generated Temporal Tests from TRIR specification
 *
 * No deadlines, schedules, or temporal fields found.
 *
 * @generated
 */

describe('Temporal Tests (disabled)', () => {
  test.skip('placeholder', () => {
    // No temporal elements found
  });
});
'''

    def _render_tests(self, test_cases: list[TemporalTestCase]) -> str:
        """Render test cases to executable Jest code"""
        lines = [
            '/**',
            ' * Auto-generated Temporal Tests from TRIR specification',
            ' *',
            ' * These tests verify time-based behavior:',
            ' * - Deadline expiration triggers correct behavior',
            ' * - Scheduled jobs run at correct times',
            ' * - Time-based state transitions work correctly',
            ' * - Datetime fields validate properly',
            ' *',
            ' * @generated',
            ' */',
            '',
            '// ========== Test Infrastructure ==========',
            '',
            'interface DurationUnit {',
            '  amount: number;',
            '  unit: "s" | "m" | "h" | "d";',
            '}',
            '',
            'class TimeController {',
            '  private currentTime: Date;',
            '  private frozen: boolean = false;',
            '',
            '  constructor() {',
            '    this.currentTime = new Date();',
            '  }',
            '',
            '  freeze(at?: Date): void {',
            '    this.frozen = true;',
            '    this.currentTime = at || new Date();',
            '  }',
            '',
            '  advance(ms: number): void {',
            '    this.currentTime = new Date(this.currentTime.getTime() + ms);',
            '  }',
            '',
            '  advanceByDuration(durationStr: string): void {',
            '    const { amount, unit } = this.parseDuration(durationStr);',
            '    const multipliers = { s: 1000, m: 60000, h: 3600000, d: 86400000 };',
            '    this.advance(amount * multipliers[unit]);',
            '  }',
            '',
            '  now(): Date {',
            '    return this.currentTime;',
            '  }',
            '',
            '  private parseDuration(durationStr: string): DurationUnit {',
            '    if (!durationStr) return { amount: 0, unit: "s" };',
            '    const match = durationStr.match(/^(\\d+)([smhd])?$/);',
            '    if (match) {',
            '      return {',
            '        amount: parseInt(match[1], 10),',
            '        unit: (match[2] || "s") as DurationUnit["unit"],',
            '      };',
            '    }',
            '    return { amount: 0, unit: "s" };',
            '  }',
            '}',
            '',
            'class DeadlineChecker {',
            '  constructor(private timeController: TimeController) {}',
            '',
            '  isExpired(createdAt: Date, durationStr: string): boolean {',
            '    const { amount, unit } = this.parseDuration(durationStr);',
            '    const multipliers = { s: 1000, m: 60000, h: 3600000, d: 86400000 };',
            '    const deadline = new Date(createdAt.getTime() + amount * multipliers[unit]);',
            '    return this.timeController.now() > deadline;',
            '  }',
            '',
            '  private parseDuration(durationStr: string): DurationUnit {',
            '    if (!durationStr) return { amount: 0, unit: "s" };',
            '    const match = durationStr.match(/^(\\d+)([smhd])?$/);',
            '    if (match) {',
            '      return {',
            '        amount: parseInt(match[1], 10),',
            '        unit: (match[2] || "s") as DurationUnit["unit"],',
            '      };',
            '    }',
            '    return { amount: 0, unit: "s" };',
            '  }',
            '}',
            '',
            'function createTimeController(): TimeController {',
            '  return new TimeController();',
            '}',
            '',
            'function createDeadlineChecker(timeController: TimeController): DeadlineChecker {',
            '  return new DeadlineChecker(timeController);',
            '}',
            '',
        ]

        # Group by pattern type
        by_pattern: dict[str, list[TemporalTestCase]] = {}
        for tc in test_cases:
            if tc.pattern not in by_pattern:
                by_pattern[tc.pattern] = []
            by_pattern[tc.pattern].append(tc)

        lines.append('// ========== Tests ==========')
        lines.append('')

        # Generate test classes by pattern
        pattern_class_names = {
            "deadline_expired": "Temporal: Deadline Expiration",
            "deadline_valid": "Temporal: Deadline Valid",
            "schedule_trigger": "Temporal: Schedule Trigger",
            "time_transition": "Temporal: Time Transition",
            "datetime_field": "Temporal: Datetime Fields",
        }

        for pattern, cases in by_pattern.items():
            class_name = pattern_class_names.get(pattern, f"Temporal: {pattern}")
            lines.append(f"describe('{class_name}', () => {{")
            lines.append('  let timeController: TimeController;')
            lines.append('  let deadlineChecker: DeadlineChecker;')
            lines.append('')
            lines.append('  beforeEach(() => {')
            lines.append('    timeController = createTimeController();')
            lines.append('    deadlineChecker = createDeadlineChecker(timeController);')
            lines.append('  });')
            lines.append('')

            for tc in cases:
                lines.extend(self._render_test_method(tc))
                lines.append('')

            lines.append('});')
            lines.append('')

        return '\n'.join(lines)

    def _render_test_method(self, tc: TemporalTestCase) -> list[str]:
        """Render a single test method"""
        lines = []

        if tc.pattern == "deadline_expired":
            lines.append(f"  test('{tc.description}', () => {{")
            lines.append(f'    // Arrange: Create entity and freeze time')
            lines.append(f'    timeController.freeze();')
            lines.append(f'    const createdAt = timeController.now();')
            lines.append(f'    ')
            lines.append(f'    // Act: Advance time past deadline')
            lines.append(f'    timeController.advanceByDuration("{tc.deadline_duration}");')
            lines.append(f'    timeController.advance(1000); // Just past deadline')
            lines.append(f'    ')
            lines.append(f'    // Assert: Deadline should be expired')
            lines.append(f'    expect(deadlineChecker.isExpired(createdAt, "{tc.deadline_duration}")).toBe(true);')
            lines.append(f'    ')
            lines.append(f'    // Assert: Action should trigger deadline behavior')
            lines.append(f'    // TODO: Verify {tc.action} triggers or action is blocked')
            lines.append(f'    throw new Error("Requires deadline handler implementation");')
            lines.append('  });')

        elif tc.pattern == "deadline_valid":
            lines.append(f"  test('{tc.description}', () => {{")
            lines.append(f'    // Arrange: Create entity and freeze time')
            lines.append(f'    timeController.freeze();')
            lines.append(f'    const createdAt = timeController.now();')
            lines.append(f'    ')
            lines.append(f'    // Act: Advance time but stay within deadline')
            lines.append(f'    timeController.advanceByDuration("{tc.deadline_duration}");')
            lines.append(f'    timeController.advance(-1000); // Just before deadline')
            lines.append(f'    ')
            lines.append(f'    // Assert: Deadline should NOT be expired')
            lines.append(f'    expect(deadlineChecker.isExpired(createdAt, "{tc.deadline_duration}")).toBe(false);')
            lines.append(f'    ')
            lines.append(f'    // Assert: Normal action should succeed')
            lines.append(f'    // TODO: Verify normal operation works')
            lines.append(f'    throw new Error("Requires action implementation");')
            lines.append('  });')

        elif tc.pattern == "schedule_trigger":
            lines.append(f"  test('{tc.description}', () => {{")
            lines.append(f'    // Arrange: Setup schedule monitor')
            lines.append(f'    const scheduleCron = "{tc.deadline_duration}";')
            lines.append(f'    let actionCalled = false;')
            lines.append(f'    ')
            lines.append(f'    const mockAction = (): void => {{')
            lines.append(f'      actionCalled = true;')
            lines.append(f'    }};')
            lines.append(f'    ')
            lines.append(f'    // Act: Simulate time reaching schedule trigger')
            lines.append(f'    // TODO: Integrate with actual scheduler')
            lines.append(f'    ')
            lines.append(f'    // Assert: Action should be called')
            lines.append(f'    // expect(actionCalled).toBe(true);')
            lines.append(f'    throw new Error("Requires scheduler implementation");')
            lines.append('  });')

        elif tc.pattern == "time_transition":
            lines.append(f"  test('{tc.description}', () => {{")
            lines.append(f'    // Arrange: Create entity in initial state')
            lines.append(f'    timeController.freeze();')
            lines.append(f'    const initialState = {{ state: "initial" }};')
            lines.append(f'    ')
            lines.append(f'    // Act: Advance time past transition threshold')
            lines.append(f'    timeController.advanceByDuration("{tc.deadline_duration}");')
            lines.append(f'    ')
            lines.append(f'    // Assert: State should have transitioned')
            lines.append(f'    // TODO: Verify state machine processed timer transition')
            lines.append(f'    throw new Error("Requires state machine timer implementation");')
            lines.append('  });')

        elif tc.pattern == "datetime_field":
            lines.append(f"  test('{tc.description}', () => {{")
            lines.append(f'    // Test valid datetime')
            lines.append(f'    const validDt = new Date().toISOString();')
            lines.append(f'    // TODO: Validate {tc.target}.{tc.field} accepts valid datetime')
            lines.append(f'    ')
            lines.append(f'    // Test invalid datetime format')
            lines.append(f'    const invalidDt = "not-a-datetime";')
            lines.append(f'    // TODO: Validate {tc.target}.{tc.field} rejects invalid datetime')
            lines.append(f'    ')
            lines.append(f'    // Test edge cases')
            lines.append(f'    const edgeCases = [')
            lines.append(f'      new Date(0).toISOString(),           // Minimum datetime (epoch)')
            lines.append(f'      new Date(8640000000000000).toISOString(), // Maximum safe date')
            lines.append(f'      "2024-02-29T00:00:00.000Z",          // Leap year')
            lines.append(f'    ];')
            lines.append(f'    // TODO: Test edge cases for {tc.field}')
            lines.append(f'    throw new Error("Requires field validation implementation");')
            lines.append('  });')

        return lines

    def _to_snake(self, name: str) -> str:
        """Convert to snake_case"""
        import re
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
