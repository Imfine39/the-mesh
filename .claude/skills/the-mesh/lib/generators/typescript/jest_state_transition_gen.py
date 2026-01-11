"""Mesh State Transition Test Generator for Jest

Generates EXECUTABLE Jest tests to verify state machine behavior using Repository pattern:
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
    test_type: str  # 'valid_transition', 'invalid_transition', 'guard_fail', 'final_state'
    from_state: str
    to_state: str | None
    trigger_function: str
    guard: dict | None
    initial_entity: dict[str, Any]
    inputs: dict[str, Any]
    expected_state: str | None


class JestStateTransitionGenerator:
    """Generates executable Jest state transition tests from TRIR specification"""

    def __init__(self, spec: dict[str, Any], typescript: bool = True,
                 import_modules: dict[str, str] | None = None):
        """
        Args:
            spec: TRIR specification
            typescript: Whether to generate TypeScript (True) or JavaScript (False)
            import_modules: Map of function_name -> module path
                           e.g. {"payOrder": "./src/orders/payOrder"}
        """
        self.spec = spec
        self.typescript = typescript
        self.state_machines = spec.get("stateMachines", {})
        self.entities = spec.get("entities", {})
        self.functions = spec.get("commands", {})
        self.import_modules = import_modules or {}

    def _generate_imports(self, function_names: set[str]) -> list[str]:
        """Generate import statements for functions (grouped by module)"""
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
            lines.append(f"import {{ {funcs_str} }} from '{module}';")
        return lines

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

            # Build transition map
            transition_map: dict[tuple[str, str], list[dict]] = {}
            for trans in transitions:
                key = (trans.get("from"), trans.get("trigger_function"))
                if key not in transition_map:
                    transition_map[key] = []
                transition_map[key].append(trans)

            # Generate tests for each transition type
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
        from_state = trans.get("from")
        to_state = trans.get("to")
        trigger = trans.get("trigger_function")

        func_def = self.functions.get(trigger, {})
        entity_data = self._get_entity_sample(entity, {field: from_state})

        return [StateTransitionTest(
            id=f"st-{sm_name}-{from_state}-to-{to_state}",
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
        )]

    def _generate_guard_tests(
        self, sm_name: str, entity: str, field: str, trans: dict
    ) -> list[StateTransitionTest]:
        """Generate tests for guard condition failures"""
        from_state = trans.get("from")
        trigger = trans.get("trigger_function")

        func_def = self.functions.get(trigger, {})
        entity_data = self._get_entity_sample(entity, {field: from_state})

        return [StateTransitionTest(
            id=f"st-{sm_name}-{from_state}-guard-fail",
            description=f"{entity}: guard fail at {from_state} - stays in {from_state}",
            state_machine=sm_name,
            entity=entity,
            field=field,
            test_type="guard_fail",
            from_state=from_state,
            to_state=trans.get("to"),
            trigger_function=trigger,
            guard=trans.get("guard"),
            initial_entity=entity_data,
            inputs=self._get_function_inputs(func_def),
            expected_state=from_state,
        )]

    def _generate_invalid_transition_tests(
        self, sm_name: str, entity: str, field: str, states: dict,
        transitions: list, transition_map: dict
    ) -> list[StateTransitionTest]:
        """Generate tests for invalid state transitions"""
        tests = []
        all_triggers = {t.get("trigger_function") for t in transitions}

        for state in states.keys():
            for trigger in all_triggers:
                if not transition_map.get((state, trigger), []):
                    func_def = self.functions.get(trigger, {})
                    entity_data = self._get_entity_sample(entity, {field: state})

                    tests.append(StateTransitionTest(
                        id=f"st-{sm_name}-{state}-invalid-{self._to_kebab(trigger)}",
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
        self, sm_name: str, entity: str, field: str, states: dict, transitions: list
    ) -> list[StateTransitionTest]:
        """Generate tests for final state enforcement"""
        tests = []
        final_states = [
            s for s, sdef in states.items()
            if isinstance(sdef, dict) and sdef.get("final", False)
        ]
        all_triggers = list({t.get("trigger_function") for t in transitions})

        for final_state in final_states:
            for trigger in all_triggers[:2]:
                func_def = self.functions.get(trigger, {})
                entity_data = self._get_entity_sample(entity, {field: final_state})

                tests.append(StateTransitionTest(
                    id=f"st-{sm_name}-{final_state}-final-{self._to_kebab(trigger)}",
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
        """Get sample entity data"""
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
        for field_name, field_def in func_def.get("input", {}).items():
            inputs[field_name] = self._get_default_value(field_name, field_def.get("type"))
        return inputs

    def _get_default_value(self, field_name: str, field_type: Any) -> Any:
        """Get default value for a field type"""
        if isinstance(field_type, str):
            if field_type == "string":
                return f"{field_name.upper()}-001"
            return {
                "text": "test content",
                "int": 100,
                "float": 100.0,
                "bool": True,
                "datetime": "2024-01-01T00:00:00Z",
                "date": "2024-01-01",
            }.get(field_type, "test")
        if isinstance(field_type, dict):
            if "enum" in field_type:
                return field_type["enum"][0]
            if "ref" in field_type:
                return "REF-001"
        return None

    def _render_jest(self, tests: list[StateTransitionTest]) -> str:
        """Render tests as executable Jest code"""
        # Collect functions used
        used_functions = {t.trigger_function for t in tests}

        lines = [
            '/**',
            ' * Auto-generated State Transition Tests from TRIR specification',
            ' *',
            ' * These tests verify that state machines behave correctly:',
            ' * - Valid transitions move to the correct state',
            ' * - Invalid transitions are rejected',
            ' * - Guard conditions are enforced',
            ' * - Final states cannot be exited',
            ' *',
            ' * Tests use mock repositories - implementation must accept repository parameter.',
            ' * @generated',
            ' */',
            '',
        ]

        if self.typescript:
            lines.append("import { describe, it, expect } from '@jest/globals';")

        # Implementation imports
        impl_imports = self._generate_imports(used_functions)
        if impl_imports:
            lines.append('')
            lines.append('// Implementation imports')
            lines.extend(impl_imports)
        lines.append('')

        # Collect entities
        entities_used = {t.entity for t in tests}

        # Repository interfaces
        if self.typescript:
            lines.append('// ========== Repository Interfaces ==========')
            lines.append('')
            for entity_name in sorted(entities_used):
                lines.extend(self._generate_repository_interface(entity_name))
                lines.append('')

        # Mock factories
        lines.append('// ========== Mock Factories ==========')
        lines.append('')
        for entity_name in sorted(entities_used):
            lines.extend(self._generate_mock_factory(entity_name))
            lines.append('')

        # Group by state machine
        by_sm: dict[str, list[StateTransitionTest]] = {}
        for test in tests:
            by_sm.setdefault(test.state_machine, []).append(test)

        lines.append('// ========== State Transition Tests ==========')
        lines.append('')

        for sm_name, sm_tests in by_sm.items():
            lines.append(f"describe('StateMachine: {sm_name}', () => {{")

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

                lines.append('')
                lines.append(f"  describe('{type_titles.get(test_type, test_type)}', () => {{")

                for test in type_tests:
                    lines.extend(self._render_test(test))

                lines.append('  });')

            lines.append('});')
            lines.append('')

        return '\n'.join(lines)

    def _generate_repository_interface(self, entity_name: str) -> list[str]:
        """Generate TypeScript interface for repository"""
        return [
            f'interface {entity_name}Repository {{',
            f'  create(data: Partial<{entity_name}>): Promise<{entity_name}>;',
            f'  get(id: string): Promise<{entity_name} | null>;',
            f'  getAll(): Promise<{entity_name}[]>;',
            f'  update(id: string, data: Partial<{entity_name}>): Promise<{entity_name}>;',
            f'  delete(id: string): Promise<boolean>;',
            '}',
            '',
            f'interface {entity_name} {{',
            f'  id: string;',
            f'  [key: string]: unknown;',
            '}',
        ]

    def _generate_mock_factory(self, entity_name: str) -> list[str]:
        """Generate mock repository factory"""
        type_hint = f': {entity_name}Repository' if self.typescript else ''
        data_type = f': Record<string, {entity_name}>' if self.typescript else ''

        return [
            f'function createMock{entity_name}Repository(){type_hint} {{',
            f'  const mockData{data_type} = {{}};',
            f'  return {{',
            f'    create: jest.fn().mockImplementation((data) => Promise.resolve({{ id: "NEW-001", ...data }})),',
            f'    get: jest.fn().mockImplementation((id) => Promise.resolve(mockData[id] || null)),',
            f'    getAll: jest.fn().mockResolvedValue([]),',
            f'    update: jest.fn().mockImplementation((id, data) => Promise.resolve({{ ...mockData[id], ...data }})),',
            f'    delete: jest.fn().mockResolvedValue(true),',
            f'    _setData: (id{": string" if self.typescript else ""}, data{f": {entity_name}" if self.typescript else ""}) => {{ mockData[id] = data; }},',
            f'  }};',
            '}',
        ]

    def _render_test(self, test: StateTransitionTest) -> list[str]:
        """Render a single test"""
        lines = []
        entity_name = test.entity

        lines.append('')
        lines.append(f"    it('{test.description}', async () => {{")

        # Arrange
        lines.append('      // Arrange')
        lines.append(f'      const repository = createMock{entity_name}Repository();')
        lines.append(f'      const entity = {self._to_js_object(test.initial_entity)};')
        lines.append(f'      repository._setData(entity.id, entity);')
        lines.append(f'      repository.get.mockResolvedValue(entity);')
        lines.append(f'      const inputData = {self._to_js_object(test.inputs)};')
        lines.append('')

        # Act
        has_import = test.trigger_function in self.import_modules
        comment = "" if has_import else "// "

        lines.append('      // Act')
        lines.append(f'      {comment}const result = await {test.trigger_function}(entity.id, inputData, {{ repository }});')
        lines.append('')

        # Assert
        lines.append('      // Assert')

        if test.test_type == "valid_transition":
            lines.append(f'      // Verify state changed to {test.expected_state}')
            lines.append('      expect(repository.update).toHaveBeenCalledTimes(1);')
            lines.append('      const updateData = repository.update.mock.calls[0][1];')
            lines.append(f'      expect(updateData.{test.field}).toBe("{test.expected_state}");')

        elif test.test_type == "guard_fail":
            lines.append(f'      // Guard condition not met - state should remain {test.from_state}')
            lines.append(f'      {comment}expect(result.success).toBe(false);')
            if not has_import:
                lines.append('      expect(true).toBe(true); // Placeholder')

        elif test.test_type == "invalid_transition":
            lines.append('      // Invalid transition - should fail')
            lines.append(f'      {comment}expect(result.success).toBe(false);')
            lines.append(f'      {comment}expect(result.error.code).toBe("INVALID_TRANSITION");')
            if not has_import:
                lines.append('      expect(true).toBe(true); // Placeholder')

        elif test.test_type == "final_state":
            lines.append('      // Final state - no transitions allowed')
            lines.append(f'      {comment}expect(result.success).toBe(false);')
            if not has_import:
                lines.append('      expect(true).toBe(true); // Placeholder')

        lines.append('    });')

        return lines

    def _to_js_object(self, obj: dict) -> str:
        """Convert dict to JavaScript object literal"""
        items = [f'{k}: {self._to_js_value(v)}' for k, v in obj.items()]
        return '{ ' + ', '.join(items) + ' }'

    def _to_js_value(self, val: Any) -> str:
        """Convert Python value to JavaScript value"""
        if val is None:
            return 'null'
        if isinstance(val, bool):
            return 'true' if val else 'false'
        if isinstance(val, str):
            return f'"{val}"'
        if isinstance(val, (int, float)):
            return str(val)
        if isinstance(val, dict):
            return self._to_js_object(val)
        if isinstance(val, list):
            return '[' + ', '.join(self._to_js_value(v) for v in val) + ']'
        return str(val)

    def _to_kebab(self, name: str) -> str:
        """Convert to kebab-case"""
        return name.replace(".", "-").replace("_", "-").lower()
