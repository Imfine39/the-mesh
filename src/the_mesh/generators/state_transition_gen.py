"""Mesh State Transition Test Generator

Generates tests to verify state machine behavior:
- Valid state transitions (trigger_function moves entity to correct state)
- Invalid state transitions (function call from invalid state fails)
- Guard condition verification (transition only occurs when guard is satisfied)
- Final state enforcement (cannot transition from final states)

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
    test_type: str  # 'valid_transition', 'invalid_transition', 'guard_pass', 'guard_fail', 'final_state'
    from_state: str
    to_state: str | None
    trigger_function: str
    guard: dict | None
    setup: dict[str, Any]
    inputs: dict[str, Any]
    expected_state: str | None  # Expected state after function call


class StateTransitionGenerator:
    """Generates state transition tests from TRIR specification"""

    def __init__(self, spec: dict[str, Any]):
        self.spec = spec
        self.state_machines = spec.get("stateMachines", {})
        self.entities = spec.get("entities", {})
        self.functions = spec.get("functions", {})

    def generate_all(self) -> str:
        """Generate all state transition tests"""
        tests = self._generate_tests()
        return self._render_pytest(tests)

    def generate_for_state_machine(self, sm_name: str) -> str:
        """Generate tests for a specific state machine"""
        tests = self._generate_tests(sm_filter=sm_name)
        return self._render_pytest(tests)

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

            # Build transition map: (from_state, trigger_function) -> transitions
            transition_map: dict[tuple[str, str], list[dict]] = {}
            for trans in transitions:
                key = (trans.get("from"), trans.get("trigger_function"))
                if key not in transition_map:
                    transition_map[key] = []
                transition_map[key].append(trans)

            # Generate valid transition tests
            for trans in transitions:
                tests.extend(self._generate_valid_transition_tests(
                    sm_name, entity, field, trans
                ))

                # If transition has guard, generate guard tests
                if trans.get("guard"):
                    tests.extend(self._generate_guard_tests(
                        sm_name, entity, field, trans
                    ))

            # Generate invalid transition tests
            tests.extend(self._generate_invalid_transition_tests(
                sm_name, entity, field, states, transitions, transition_map
            ))

            # Generate final state tests
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
            id=f"sm_{sm_name}_{from_state}_to_{to_state}_via_{trigger}",
            description=f"{entity}: {from_state} -> {to_state} via {trigger}",
            state_machine=sm_name,
            entity=entity,
            field=field,
            test_type="valid_transition",
            from_state=from_state,
            to_state=to_state,
            trigger_function=trigger,
            guard=guard,
            setup={
                f"_entity_{entity}": {
                    "id": f"{entity.upper()}_TEST_001",
                    field: from_state,
                }
            },
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

        # Guard pass test (already covered by valid transition)
        # Guard fail test - when guard is false, transition should not occur
        tests.append(StateTransitionTest(
            id=f"sm_{sm_name}_{from_state}_guard_fail_{trigger}",
            description=f"{entity}: {from_state} guard fail - should stay in {from_state}",
            state_machine=sm_name,
            entity=entity,
            field=field,
            test_type="guard_fail",
            from_state=from_state,
            to_state=to_state,
            trigger_function=trigger,
            guard=guard,
            setup={
                f"_entity_{entity}": {
                    "id": f"{entity.upper()}_TEST_001",
                    field: from_state,
                },
                "_guard_condition": "set to make guard FALSE",
            },
            inputs=self._get_function_inputs(func_def),
            expected_state=from_state,  # Should stay in from_state
        ))

        return tests

    def _generate_invalid_transition_tests(
        self, sm_name: str, entity: str, field: str, states: dict,
        transitions: list, transition_map: dict
    ) -> list[StateTransitionTest]:
        """Generate tests for invalid state transitions"""
        tests = []

        # Collect all trigger functions
        all_triggers = {t.get("trigger_function") for t in transitions}

        # For each state and each trigger, check if it's a valid transition
        for state in states.keys():
            for trigger in all_triggers:
                # Check if this (state, trigger) combination is valid
                valid_transitions = transition_map.get((state, trigger), [])
                if not valid_transitions:
                    # This is an invalid transition
                    func_def = self.functions.get(trigger, {})

                    tests.append(StateTransitionTest(
                        id=f"sm_{sm_name}_{state}_invalid_{trigger}",
                        description=f"{entity}: {trigger} from {state} should fail",
                        state_machine=sm_name,
                        entity=entity,
                        field=field,
                        test_type="invalid_transition",
                        from_state=state,
                        to_state=None,
                        trigger_function=trigger,
                        guard=None,
                        setup={
                            f"_entity_{entity}": {
                                "id": f"{entity.upper()}_TEST_001",
                                field: state,
                            }
                        },
                        inputs=self._get_function_inputs(func_def),
                        expected_state=state,  # Should remain unchanged
                    ))

        return tests

    def _generate_final_state_tests(
        self, sm_name: str, entity: str, field: str, states: dict,
        transitions: list
    ) -> list[StateTransitionTest]:
        """Generate tests for final state enforcement"""
        tests = []

        # Find final states
        final_states = [
            state for state, state_def in states.items()
            if isinstance(state_def, dict) and state_def.get("final", False)
        ]

        # Collect all trigger functions
        all_triggers = {t.get("trigger_function") for t in transitions}

        # For each final state, verify no transitions can occur
        for final_state in final_states:
            for trigger in list(all_triggers)[:2]:  # Limit to avoid too many tests
                func_def = self.functions.get(trigger, {})

                tests.append(StateTransitionTest(
                    id=f"sm_{sm_name}_{final_state}_final_no_{trigger}",
                    description=f"{entity}: no transitions from final state {final_state}",
                    state_machine=sm_name,
                    entity=entity,
                    field=field,
                    test_type="final_state",
                    from_state=final_state,
                    to_state=None,
                    trigger_function=trigger,
                    guard=None,
                    setup={
                        f"_entity_{entity}": {
                            "id": f"{entity.upper()}_TEST_001",
                            field: final_state,
                        }
                    },
                    inputs=self._get_function_inputs(func_def),
                    expected_state=final_state,  # Should remain unchanged
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
            defaults = {
                "string": "TEST_VALUE",
                "int": 10000,
                "float": 100.0,
                "bool": True,
                "datetime": "2024-01-01T00:00:00Z",
            }
            return defaults.get(field_type, None)
        if isinstance(field_type, dict):
            if "enum" in field_type:
                return field_type["enum"][0]
            if "ref" in field_type:
                return "REF_TEST_001"
        return None

    def _render_pytest(self, tests: list[StateTransitionTest]) -> str:
        """Render tests as pytest code"""
        lines = [
            '"""',
            'Auto-generated State Transition Tests from TRIR specification',
            '',
            'These tests verify that state machines behave correctly:',
            '- Valid transitions move to the correct state',
            '- Invalid transitions are rejected',
            '- Guard conditions are enforced',
            '- Final states cannot be exited',
            '',
            '@generated',
            '"""',
            '',
            'import pytest',
            'from typing import Any',
            '',
            '# TODO: Import your implementation and database fixtures',
            '# from your_module import execute_clearing, reverse_clearing, ...',
            '# from your_fixtures import db, create_test_entity, ...',
            '',
        ]

        # Group by state machine
        by_sm: dict[str, list[StateTransitionTest]] = {}
        for test in tests:
            if test.state_machine not in by_sm:
                by_sm[test.state_machine] = []
            by_sm[test.state_machine].append(test)

        for sm_name, sm_tests in by_sm.items():
            lines.append(f"class TestStateMachine_{self._to_pascal(sm_name)}:")
            lines.append(f'    """State transition tests for {sm_name}"""')
            lines.append("")

            # Sub-group by test type
            type_order = ['valid_transition', 'guard_fail', 'invalid_transition', 'final_state']
            type_titles = {
                'valid_transition': 'Valid Transitions',
                'guard_fail': 'Guard Condition Tests',
                'invalid_transition': 'Invalid Transitions',
                'final_state': 'Final State Enforcement',
            }

            for test_type in type_order:
                type_tests = [t for t in sm_tests if t.test_type == test_type]
                if not type_tests:
                    continue

                lines.append(f"    # ========== {type_titles.get(test_type, test_type)} ==========")
                lines.append("")

                for test in type_tests:
                    lines.append(f"    def test_{test.id}(self):")
                    lines.append(f'        """')
                    lines.append(f'        {test.description}')
                    lines.append(f'        """')

                    # Setup section
                    lines.append("        # Setup: Create entity in starting state")
                    for setup_key, setup_val in test.setup.items():
                        lines.append(f"        # {setup_key} = {self._to_py_repr(setup_val)}")
                    lines.append("")

                    # Execute section
                    lines.append("        # Execute")
                    lines.append(f"        # result = {self._to_snake(test.trigger_function)}({self._to_py_repr(test.inputs)})")
                    lines.append("")

                    # Assert section
                    lines.append("        # Assert")
                    if test.test_type == "valid_transition":
                        lines.append(f"        # updated = db.get_{self._to_snake(test.entity)}(entity_id)")
                        lines.append(f"        # assert updated.{test.field} == '{test.expected_state}'")
                    elif test.test_type == "guard_fail":
                        lines.append(f"        # Guard condition not met - entity should stay in original state")
                        lines.append(f"        # updated = db.get_{self._to_snake(test.entity)}(entity_id)")
                        lines.append(f"        # assert updated.{test.field} == '{test.from_state}'")
                    elif test.test_type == "invalid_transition":
                        lines.append(f"        # Transition should be rejected")
                        lines.append(f"        # assert result.success is False")
                        lines.append(f"        # assert 'invalid state' in result.error.lower() or result.error.code == 'INVALID_STATE'")
                    elif test.test_type == "final_state":
                        lines.append(f"        # Final state cannot be exited")
                        lines.append(f"        # assert result.success is False")
                        lines.append(f"        # assert result.error.code == 'FINAL_STATE' or 'cannot transition' in result.error.lower()")

                    lines.append("")
                    lines.append("        pytest.skip('TODO: Implement with actual state machine')")
                    lines.append("")

            lines.append("")

        return "\n".join(lines)

    def _to_pascal(self, name: str) -> str:
        """Convert to PascalCase"""
        return "".join(p.capitalize() for p in name.replace(".", "_").split("_"))

    def _to_snake(self, name: str) -> str:
        """Convert to snake_case"""
        return name.replace(".", "_").lower()

    def _to_py_repr(self, obj: Any) -> str:
        """Convert to Python repr"""
        if obj is None:
            return "None"
        if isinstance(obj, bool):
            return "True" if obj else "False"
        if isinstance(obj, str):
            return repr(obj)
        if isinstance(obj, dict):
            items = ", ".join(f"'{k}': {self._to_py_repr(v)}" for k, v in obj.items())
            return "{" + items + "}"
        if isinstance(obj, list):
            items = ", ".join(self._to_py_repr(v) for v in obj)
            return "[" + items + "]"
        return repr(obj)
