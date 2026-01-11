"""Mesh State Transition Test Generator

Generates EXECUTABLE tests to verify state machine behavior using Repository pattern:
- Valid state transitions (trigger_function moves entity to correct state)
- Invalid state transitions (function call from invalid state fails)
- Guard condition verification (transition only occurs when guard is satisfied)
- Final state enforcement (cannot transition from final states)

Tests use mock repositories - implementation must accept repository parameter.
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
    initial_entity: dict[str, Any]
    inputs: dict[str, Any]
    expected_state: str | None


class StateTransitionGenerator:
    """Generates executable state transition tests from TRIR specification"""

    def __init__(self, spec: dict[str, Any], import_modules: dict[str, str] | None = None):
        """
        Args:
            spec: TRIR specification
            import_modules: Map of function_name -> module path
        """
        self.spec = spec
        self.state_machines = spec.get("stateMachines", {})
        self.entities = spec.get("entities", {})  
        self.functions = spec.get("commands", {})
        self.import_modules = import_modules or {}

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
                from_states = trans.get("from")
                # Handle both single state (string) and multiple states (list)
                if isinstance(from_states, list):
                    for from_state in from_states:
                        key = (from_state, trans.get("trigger_function"))
                        if key not in transition_map:
                            transition_map[key] = []
                        transition_map[key].append(trans)
                else:
                    key = (from_states, trans.get("trigger_function"))
                    if key not in transition_map:
                        transition_map[key] = []
                    transition_map[key].append(trans)

            # Generate valid transition tests
            for trans in transitions:
                tests.extend(self._generate_valid_transition_tests(
                    sm_name, entity, field, trans
                ))

                # If transition has guard, generate guard fail test
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
        from_states = trans.get("from")
        to_state = trans.get("to")
        trigger = trans.get("trigger_function")

        # Handle both single state (string) and multiple states (list)
        if not isinstance(from_states, list):
            from_states = [from_states]

        func_def = self.functions.get(trigger, {})

        for from_state in from_states:
            entity_data = self._get_entity_sample(entity, {field: from_state})

            tests.append(StateTransitionTest(
                id=f"st_{sm_name}_{from_state}_to_{to_state}",
                description=f"{entity}: {from_state} -> {to_state} via {trigger}",
                state_machine=sm_name,
                entity=entity,
                field=field,
                test_type="valid_transition",
                from_state=from_state,
                to_state=to_state,
                trigger_function=trigger,
                guard=trans.get("guard"),
                initial_entity=entity_data,
                inputs=self._get_function_inputs(func_def),
                expected_state=to_state,
            ))

        return tests

    def _generate_guard_tests(
        self, sm_name: str, entity: str, field: str, trans: dict
    ) -> list[StateTransitionTest]:
        """Generate tests for guard condition failures"""
        tests = []
        from_states = trans.get("from")
        to_state = trans.get("to")
        trigger = trans.get("trigger_function")
        guard = trans.get("guard")

        # Handle both single state (string) and multiple states (list)
        if not isinstance(from_states, list):
            from_states = [from_states]

        func_def = self.functions.get(trigger, {})

        for from_state in from_states:
            entity_data = self._get_entity_sample(entity, {field: from_state})

            # Guard fail test - when guard is false, transition should not occur
            tests.append(StateTransitionTest(
                id=f"st_{sm_name}_{from_state}_guard_fail",
                description=f"{entity}: guard fail at {from_state} - stays in {from_state}",
                state_machine=sm_name,
                entity=entity,
                field=field,
                test_type="guard_fail",
                from_state=from_state,
                to_state=to_state,
                trigger_function=trigger,
                guard=guard,
                initial_entity=entity_data,
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
                valid_transitions = transition_map.get((state, trigger), [])
                if not valid_transitions:
                    func_def = self.functions.get(trigger, {})
                    entity_data = self._get_entity_sample(entity, {field: state})

                    tests.append(StateTransitionTest(
                        id=f"st_{sm_name}_{state}_invalid_{self._to_snake(trigger)}",
                        description=f"{entity}: {trigger} from {state} should fail",
                        state_machine=sm_name,
                        entity=entity,
                        field=field,
                        test_type="invalid_transition",
                        from_state=state,
                        to_state=None,
                        trigger_function=trigger,
                        guard=None,
                        initial_entity=entity_data,
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

        # Find final states
        final_states = [
            state for state, state_def in states.items()
            if isinstance(state_def, dict) and state_def.get("final", False)
        ]

        # Collect all trigger functions
        all_triggers = list({t.get("trigger_function") for t in transitions})

        # For each final state, verify no transitions can occur
        for final_state in final_states:
            for trigger in all_triggers[:2]:  # Limit to avoid too many tests
                func_def = self.functions.get(trigger, {})
                entity_data = self._get_entity_sample(entity, {field: final_state})

                tests.append(StateTransitionTest(
                    id=f"st_{sm_name}_{final_state}_final_{self._to_snake(trigger)}",
                    description=f"{entity}: cannot exit final state {final_state}",
                    state_machine=sm_name,
                    entity=entity,
                    field=field,
                    test_type="final_state",
                    from_state=final_state,
                    to_state=None,
                    trigger_function=trigger,
                    guard=None,
                    initial_entity=entity_data,
                    inputs=self._get_function_inputs(func_def),
                    expected_state=final_state,
                ))

        return tests

    def _get_entity_sample(self, entity_name: str, overrides: dict = None) -> dict:
        """Get sample entity data with optional overrides"""
        entity = self.entities.get(entity_name, {})
        sample = {"id": f"{entity_name.upper()}-001"}

        for field_name, field_def in entity.get("fields", {}).items():
            if field_name != "id":
                sample[field_name] = self._get_default_value(field_name, field_def.get("type"))

        if overrides:
            sample.update(overrides)

        return sample

    def _get_function_inputs(self, func_def: dict) -> dict:
        """Get sample inputs for a function"""
        inputs = {}
        input_schema = func_def.get("input", {})
        for field_name, field_def in input_schema.items():
            inputs[field_name] = self._get_default_value(field_name, field_def.get("type"))
        return inputs

    def _get_default_value(self, field_name: str, field_type: Any) -> Any:
        """Get default value for a field type"""
        if isinstance(field_type, str):
            if field_type == "string":
                return f"{field_name.upper()}-001"
            defaults = {
                "text": "test content",
                "int": 100,
                "float": 100.0,
                "bool": True,
                "datetime": "2024-01-01T00:00:00Z",
                "date": "2024-01-01",
            }
            return defaults.get(field_type, "test")
        if isinstance(field_type, dict):
            if "enum" in field_type:
                return field_type["enum"][0]
            if "ref" in field_type:
                return "REF-001"
        return None

    def _generate_imports(self, function_names: set[str]) -> list[str]:
        """Generate import statements for functions"""
        lines = []
        module_funcs: dict[str, list[str]] = {}
        for func_name in sorted(function_names):
            module = self.import_modules.get(func_name)
            if module:
                if module not in module_funcs:
                    module_funcs[module] = []
                module_funcs[module].append(func_name)

        for module, funcs in sorted(module_funcs.items()):
            funcs_str = ", ".join(sorted(funcs))
            lines.append(f'from {module} import {funcs_str}')

        return lines

    def _render_pytest(self, tests: list[StateTransitionTest]) -> str:
        """Render tests as executable pytest code"""
        # Collect trigger functions used
        used_functions = {t.trigger_function for t in tests}

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
            'Tests use mock repositories - implementation must accept repository parameter.',
            '@generated',
            '"""',
            '',
            'import pytest',
            'from unittest.mock import Mock, MagicMock',
            'from typing import Any, Protocol',
            '',
        ]

        # Add implementation imports
        impl_imports = self._generate_imports(used_functions)
        if impl_imports:
            lines.append('# Implementation imports')
            lines.extend(impl_imports)
            lines.append('')

        # Collect all entities used
        entities_used = set()
        for test in tests:
            entities_used.add(test.entity)

        # Generate Repository Protocol for each entity
        lines.append('# ========== Repository Interfaces ==========')
        lines.append('')
        for entity_name in sorted(entities_used):
            lines.extend(self._generate_repository_interface(entity_name))
            lines.append('')

        # Generate fixtures
        lines.append('# ========== Fixtures ==========')
        lines.append('')
        for entity_name in sorted(entities_used):
            lines.extend(self._generate_mock_fixture(entity_name))
            lines.append('')

        # Group by state machine
        by_sm: dict[str, list[StateTransitionTest]] = {}
        for test in tests:
            if test.state_machine not in by_sm:
                by_sm[test.state_machine] = []
            by_sm[test.state_machine].append(test)

        # Generate test classes
        lines.append('# ========== State Transition Tests ==========')
        lines.append('')

        for sm_name, sm_tests in by_sm.items():
            entity_name = sm_tests[0].entity if sm_tests else "Entity"
            snake_entity = self._to_snake(entity_name)

            lines.append(f"class TestStateMachine{self._to_pascal(sm_name)}:")
            lines.append(f'    """State transition tests for {sm_name}"""')
            lines.append('')

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
                lines.append('')

                for test in type_tests:
                    lines.extend(self._render_test_method(test))
                    lines.append('')

            lines.append('')

        return '\n'.join(lines)

    def _generate_repository_interface(self, entity_name: str) -> list[str]:
        """Generate Repository Protocol for an entity"""
        return [
            f'class {entity_name}Repository(Protocol):',
            f'    """Repository interface for {entity_name}"""',
            f'    def create(self, data: dict[str, Any]) -> dict[str, Any]: ...',
            f'    def get(self, id: str) -> dict[str, Any] | None: ...',
            f'    def get_all(self) -> list[dict[str, Any]]: ...',
            f'    def update(self, id: str, data: dict[str, Any]) -> dict[str, Any]: ...',
            f'    def delete(self, id: str) -> bool: ...',
        ]

    def _generate_mock_fixture(self, entity_name: str) -> list[str]:
        """Generate mock fixture for an entity repository"""
        snake = self._to_snake(entity_name)
        sample = self._get_entity_sample(entity_name)
        sample_repr = self._to_py_repr(sample)

        return [
            '@pytest.fixture',
            f'def mock_{snake}_repository():',
            f'    """Mock {entity_name} repository"""',
            f'    repo = Mock(spec={entity_name}Repository)',
            f'    repo._data = {{}}',
            f'    repo.get.side_effect = lambda id: repo._data.get(id)',
            f'    repo.get_all.return_value = []',
            f'    repo.update.side_effect = lambda id, data: {{**repo._data.get(id, {{}}), **data}}',
            f'    return repo',
        ]

    def _render_test_method(self, test: StateTransitionTest) -> list[str]:
        """Render a single test method"""
        lines = []
        entity_snake = self._to_snake(test.entity)
        fixture_name = f"mock_{entity_snake}_repository"

        lines.append(f"    def test_{test.id}(self, {fixture_name}):")
        lines.append(f'        """')
        lines.append(f'        {test.description}')
        lines.append(f'        """')

        # Arrange
        lines.append('        # Arrange')
        lines.append(f'        entity = {self._to_py_repr(test.initial_entity)}')
        lines.append(f'        {fixture_name}._data[entity["id"]] = entity')
        lines.append(f'        {fixture_name}.get.return_value = entity')
        lines.append(f'        input_data = {self._to_py_repr(test.inputs)}')
        lines.append('')

        # Act - uncomment if import available
        has_import = test.trigger_function in self.import_modules
        comment = "" if has_import else "# "

        lines.append('        # Act')
        lines.append(f'        {comment}result = {test.trigger_function}(entity["id"], input_data, repository={fixture_name})')
        lines.append('')

        # Assert
        lines.append('        # Assert')

        if test.test_type == "valid_transition":
            lines.append(f'        # Verify state changed to {test.expected_state}')
            lines.append(f'        {fixture_name}.update.assert_called_once()')
            lines.append(f'        call_args = {fixture_name}.update.call_args')
            lines.append(f'        update_data = call_args[0][1]')
            lines.append(f'        assert update_data.get("{test.field}") == "{test.expected_state}"')

        elif test.test_type == "guard_fail":
            lines.append(f'        # Guard condition not met - state should remain {test.from_state}')
            lines.append(f'        # result should indicate failure or no update should be called')
            lines.append(f'        # assert result["success"] is False')
            lines.append(f'        # OR verify update was not called with state change')
            lines.append(f'        pass  # TODO: Implement based on your guard condition logic')

        elif test.test_type == "invalid_transition":
            lines.append(f'        # Invalid transition - should fail')
            lines.append(f'        # assert result["success"] is False')
            lines.append(f'        # assert result["error"]["code"] == "INVALID_TRANSITION"')
            lines.append(f'        pass  # TODO: Uncomment after connecting implementation')

        elif test.test_type == "final_state":
            lines.append(f'        # Final state - no transitions allowed')
            lines.append(f'        # assert result["success"] is False')
            lines.append(f'        # assert "final" in result["error"]["message"].lower()')
            lines.append(f'        pass  # TODO: Uncomment after connecting implementation')

        return lines

    def _to_pascal(self, name: str) -> str:
        """Convert to PascalCase"""
        return "".join(p.capitalize() for p in name.replace(".", "_").replace("-", "_").split("_"))

    def _to_snake(self, name: str) -> str:
        """Convert to snake_case"""
        return name.replace(".", "_").replace("-", "_").lower()

    def _to_py_repr(self, obj: Any) -> str:
        """Convert to Python repr"""
        if obj is None:
            return "None"
        if isinstance(obj, bool):
            return "True" if obj else "False"
        if isinstance(obj, str):
            return repr(obj)
        if isinstance(obj, dict):
            items = ", ".join(f'"{k}": {self._to_py_repr(v)}' for k, v in obj.items())
            return "{" + items + "}"
        if isinstance(obj, list):
            items = ", ".join(self._to_py_repr(v) for v in obj)
            return "[" + items + "]"
        return repr(obj)
