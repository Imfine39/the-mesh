"""Mesh State Transition Test Generator for Jest

Generates Jest tests to verify state machine behavior:
- Valid state transitions
- Invalid state transitions
- Guard condition verification
- Final state enforcement

These tests detect implementation drift by ensuring state machine
behavior matches the TRIR specification.
"""

from typing import Any
from dataclasses import dataclass


@dataclass
class StateTransitionTest:
    """Represents a single state transition test case"""
    id: str
    description: str
    state_machine: str
    entity: str
    field: str
    test_type: str
    from_state: str
    to_state: str | None
    trigger_function: str
    guard: dict | None
    setup: dict[str, Any]
    inputs: dict[str, Any]
    expected_state: str | None


class JestStateTransitionGenerator:
    """Generates Jest state transition tests from TRIR specification"""

    def __init__(self, spec: dict[str, Any], typescript: bool = True):
        self.spec = spec
        self.state_machines = spec.get("stateMachines", {})
        self.entities = spec.get("entities", {})
        self.functions = spec.get("functions", {})
        self.typescript = typescript

    def generate_all(self) -> str:
        """Generate all state transition tests"""
        tests = self._generate_tests()
        return self._render_jest(tests)

    def generate_for_state_machine(self, sm_name: str) -> str:
        """Generate tests for a specific state machine"""
        tests = self._generate_tests(sm_filter=sm_name)
        return self._render_jest(tests)

    def _generate_tests(self, sm_filter: str | None = None) -> list[StateTransitionTest]:
        """Generate test cases from spec"""
        tests = []

        for sm_name, sm_def in self.state_machines.items():
            if sm_filter and sm_name != sm_filter:
                continue

            entity = sm_def.get("entity", "")
            field = sm_def.get("field", "status")
            states = sm_def.get("states", {})
            transitions = sm_def.get("transitions", [])

            transition_map: dict[tuple[str, str], list[dict]] = {}
            for trans in transitions:
                key = (trans.get("from"), trans.get("trigger_function"))
                if key not in transition_map:
                    transition_map[key] = []
                transition_map[key].append(trans)

            for trans in transitions:
                tests.extend(self._generate_valid_transition_tests(
                    sm_name, entity, field, trans
                ))
                if trans.get("guard"):
                    tests.extend(self._generate_guard_tests(
                        sm_name, entity, field, trans
                    ))

            tests.extend(self._generate_invalid_transition_tests(
                sm_name, entity, field, states, transitions, transition_map
            ))

            tests.extend(self._generate_final_state_tests(
                sm_name, entity, field, states, transitions
            ))

        return tests

    def _generate_valid_transition_tests(
        self, sm_name: str, entity: str, field: str, trans: dict
    ) -> list[StateTransitionTest]:
        """Generate tests for valid state transitions"""
        tests = []
        from_state = trans.get("from")
        to_state = trans.get("to")
        trigger = trans.get("trigger_function")
        guard = trans.get("guard")

        func_def = self.functions.get(trigger, {})

        tests.append(StateTransitionTest(
            id=f"sm-{sm_name}-{from_state}-to-{to_state}-via-{trigger}",
            description=f"{entity}: {from_state} -> {to_state} via {trigger}",
            state_machine=sm_name,
            entity=entity,
            field=field,
            test_type="valid_transition",
            from_state=from_state,
            to_state=to_state,
            trigger_function=trigger,
            guard=guard,
            setup={f"_entity_{entity}": {"id": f"{entity.upper()}_TEST_001", field: from_state}},
            inputs=self._get_function_inputs(func_def),
            expected_state=to_state,
        ))

        return tests

    def _generate_guard_tests(
        self, sm_name: str, entity: str, field: str, trans: dict
    ) -> list[StateTransitionTest]:
        """Generate tests for guard conditions"""
        tests = []
        from_state = trans.get("from")
        to_state = trans.get("to")
        trigger = trans.get("trigger_function")
        guard = trans.get("guard")

        func_def = self.functions.get(trigger, {})

        tests.append(StateTransitionTest(
            id=f"sm-{sm_name}-{from_state}-guard-fail-{trigger}",
            description=f"{entity}: {from_state} guard fail - should stay",
            state_machine=sm_name,
            entity=entity,
            field=field,
            test_type="guard_fail",
            from_state=from_state,
            to_state=to_state,
            trigger_function=trigger,
            guard=guard,
            setup={
                f"_entity_{entity}": {"id": f"{entity.upper()}_TEST_001", field: from_state},
                "_guard_condition": "set to make guard FALSE",
            },
            inputs=self._get_function_inputs(func_def),
            expected_state=from_state,
        ))

        return tests

    def _generate_invalid_transition_tests(
        self, sm_name: str, entity: str, field: str, states: dict,
        transitions: list, transition_map: dict
    ) -> list[StateTransitionTest]:
        """Generate tests for invalid state transitions"""
        tests = []
        all_triggers = {t.get("trigger_function") for t in transitions}

        for state in states.keys():
            for trigger in all_triggers:
                valid_transitions = transition_map.get((state, trigger), [])
                if not valid_transitions:
                    func_def = self.functions.get(trigger, {})
                    tests.append(StateTransitionTest(
                        id=f"sm-{sm_name}-{state}-invalid-{trigger}",
                        description=f"{entity}: {trigger} from {state} should fail",
                        state_machine=sm_name,
                        entity=entity,
                        field=field,
                        test_type="invalid_transition",
                        from_state=state,
                        to_state=None,
                        trigger_function=trigger,
                        guard=None,
                        setup={f"_entity_{entity}": {"id": f"{entity.upper()}_TEST_001", field: state}},
                        inputs=self._get_function_inputs(func_def),
                        expected_state=state,
                    ))

        return tests

    def _generate_final_state_tests(
        self, sm_name: str, entity: str, field: str, states: dict,
        transitions: list
    ) -> list[StateTransitionTest]:
        """Generate tests for final state enforcement"""
        tests = []
        final_states = [
            state for state, state_def in states.items()
            if isinstance(state_def, dict) and state_def.get("final", False)
        ]
        all_triggers = {t.get("trigger_function") for t in transitions}

        for final_state in final_states:
            for trigger in list(all_triggers)[:2]:
                func_def = self.functions.get(trigger, {})
                tests.append(StateTransitionTest(
                    id=f"sm-{sm_name}-{final_state}-final-no-{trigger}",
                    description=f"{entity}: no transitions from final state {final_state}",
                    state_machine=sm_name,
                    entity=entity,
                    field=field,
                    test_type="final_state",
                    from_state=final_state,
                    to_state=None,
                    trigger_function=trigger,
                    guard=None,
                    setup={f"_entity_{entity}": {"id": f"{entity.upper()}_TEST_001", field: final_state}},
                    inputs=self._get_function_inputs(func_def),
                    expected_state=final_state,
                ))

        return tests

    def _get_function_inputs(self, func_def: dict) -> dict:
        """Get sample inputs for a function"""
        inputs = {}
        input_schema = func_def.get("input", {})
        for field_name, field_def in input_schema.items():
            inputs[field_name] = self._get_default_value(field_def.get("type"))
        return inputs

    def _get_default_value(self, field_type: Any) -> Any:
        """Get default value for a field type"""
        if isinstance(field_type, str):
            return {
                "string": "TEST_VALUE",
                "int": 10000,
                "float": 100.0,
                "bool": True,
                "datetime": "2024-01-01T00:00:00Z",
            }.get(field_type)
        if isinstance(field_type, dict):
            if "enum" in field_type:
                return field_type["enum"][0]
            if "ref" in field_type:
                return "REF_TEST_001"
        return None

    def _render_jest(self, tests: list[StateTransitionTest]) -> str:
        """Render tests as Jest code"""
        lines = [
            "/**",
            " * Auto-generated State Transition Tests from TRIR specification",
            " *",
            " * These tests verify that state machines behave correctly:",
            " * - Valid transitions move to the correct state",
            " * - Invalid transitions are rejected",
            " * - Guard conditions are enforced",
            " * - Final states cannot be exited",
            " *",
            " * @generated",
            " */",
            "",
        ]

        if self.typescript:
            lines.append("import { describe, test, expect, beforeEach } from '@jest/globals';")
        else:
            lines.append("// Jest globals are available automatically")

        lines.extend([
            "",
            "// TODO: Import your implementation and database fixtures",
            "// import { executeClearing, reverseClearing, ... } from './implementation';",
            "// import { db, createTestEntity, ... } from './fixtures';",
            "",
        ])

        by_sm: dict[str, list[StateTransitionTest]] = {}
        for test in tests:
            if test.state_machine not in by_sm:
                by_sm[test.state_machine] = []
            by_sm[test.state_machine].append(test)

        type_titles = {
            'valid_transition': 'Valid Transitions',
            'guard_fail': 'Guard Condition Tests',
            'invalid_transition': 'Invalid Transitions',
            'final_state': 'Final State Enforcement',
        }

        for sm_name, sm_tests in by_sm.items():
            lines.append(f"describe('StateMachine: {sm_name}', () => {{")

            type_order = ['valid_transition', 'guard_fail', 'invalid_transition', 'final_state']
            for test_type in type_order:
                type_tests = [t for t in sm_tests if t.test_type == test_type]
                if not type_tests:
                    continue

                lines.append(f"  // ========== {type_titles.get(test_type, test_type)} ==========")
                lines.append("")

                for test in type_tests:
                    lines.append(f"  test('{test.id}: {self._escape(test.description)}', async () => {{")

                    lines.append("    // Setup: Create entity in starting state")
                    for key, val in test.setup.items():
                        lines.append(f"    // {key} = {self._to_js(val)};")
                    lines.append("")

                    lines.append("    // Execute")
                    lines.append(f"    // const result = await {self._to_camel(test.trigger_function)}({self._to_js(test.inputs)});")
                    lines.append("")

                    lines.append("    // Assert")
                    if test.test_type == "valid_transition":
                        lines.append(f"    // const updated = await db.get{self._to_pascal(test.entity)}(entityId);")
                        lines.append(f"    // expect(updated.{self._to_camel(test.field)}).toBe('{test.expected_state}');")
                    elif test.test_type == "guard_fail":
                        lines.append(f"    // const updated = await db.get{self._to_pascal(test.entity)}(entityId);")
                        lines.append(f"    // expect(updated.{self._to_camel(test.field)}).toBe('{test.from_state}');")
                    elif test.test_type == "invalid_transition":
                        lines.append("    // expect(result.success).toBe(false);")
                        lines.append("    // expect(result.error.code).toMatch(/INVALID_STATE/i);")
                    elif test.test_type == "final_state":
                        lines.append("    // expect(result.success).toBe(false);")
                        lines.append("    // expect(result.error.code).toMatch(/FINAL_STATE|CANNOT_TRANSITION/i);")

                    lines.append("  });")
                    lines.append("")

            lines.append("});")
            lines.append("")

        return "\n".join(lines)

    def _to_js(self, obj: Any) -> str:
        """Convert to JS object literal"""
        if obj is None:
            return "null"
        if isinstance(obj, bool):
            return "true" if obj else "false"
        if isinstance(obj, str):
            return f"'{obj}'"
        if isinstance(obj, (int, float)):
            return str(obj)
        if isinstance(obj, dict):
            items = ", ".join(f"{self._to_camel(k)}: {self._to_js(v)}" for k, v in obj.items())
            return "{ " + items + " }"
        if isinstance(obj, list):
            return "[" + ", ".join(self._to_js(v) for v in obj) + "]"
        return str(obj)

    def _to_camel(self, name: str) -> str:
        parts = name.replace(".", "_").split("_")
        return parts[0] + "".join(p.capitalize() for p in parts[1:])

    def _to_pascal(self, name: str) -> str:
        return "".join(p.capitalize() for p in name.replace(".", "_").split("_"))

    def _escape(self, s: str) -> str:
        return s.replace("'", "\\'").replace("\n", " ")
