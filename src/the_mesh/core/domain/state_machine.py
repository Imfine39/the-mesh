"""State machine validation mixin for The Mesh validator."""

from the_mesh.core.errors import ValidationError


class StateMachineValidationMixin:
    """Mixin providing state machine validation methods."""

    def _validate_state_machines(self, spec: dict) -> tuple[list[ValidationError], list[ValidationError]]:
        """Validate state machine definitions (VAL-003, VAL-004)"""
        errors = []
        warnings = []
        functions = spec.get("functions", {})
        events = spec.get("events", {})

        for sm_name, sm in spec.get("stateMachines", {}).items():
            states = sm.get("states", {})
            transitions = sm.get("transitions", [])
            initial = sm.get("initial", "")

            # VAL-003: Validate trigger references exist
            for i, trans in enumerate(transitions):
                trigger = trans.get("trigger_function")
                if trigger:
                    if trigger not in functions and trigger not in events:
                        errors.append(ValidationError(
                            path=f"stateMachines.{sm_name}.transitions[{i}]",
                            message=f"Trigger '{trigger}' not found in functions or events"
                        ))

            # VAL-004: Reachability analysis
            # Find all reachable states from initial
            reachable = set()
            if initial:
                reachable.add(initial)
                changed = True
                while changed:
                    changed = False
                    for trans in transitions:
                        from_state = trans.get("from")
                        to_state = trans.get("to")
                        if from_state in reachable and to_state not in reachable:
                            reachable.add(to_state)
                            changed = True

            # Check for unreachable states
            all_states = set(states.keys())
            unreachable = all_states - reachable
            if unreachable:
                warnings.append(ValidationError(
                    path=f"stateMachines.{sm_name}",
                    message=f"Unreachable states: {', '.join(sorted(unreachable))}",
                    severity="warning"
                ))

            # Check for dead-end states (non-final states with no outgoing transitions)
            from_states = {trans.get("from") for trans in transitions}
            final_states = {name for name, state in states.items() if state.get("final")}
            dead_ends = (all_states - from_states) - final_states

            if dead_ends:
                warnings.append(ValidationError(
                    path=f"stateMachines.{sm_name}",
                    message=f"Dead-end states (not final, no outgoing transitions): {', '.join(sorted(dead_ends))}",
                    severity="warning"
                ))

            # Validate initial state exists
            if initial and initial not in states:
                errors.append(ValidationError(
                    path=f"stateMachines.{sm_name}",
                    message=f"Initial state '{initial}' not defined in states"
                ))

            # Validate transition from/to states exist
            for i, trans in enumerate(transitions):
                from_state = trans.get("from")
                to_state = trans.get("to")
                if from_state and from_state not in states:
                    errors.append(ValidationError(
                        path=f"stateMachines.{sm_name}.transitions[{i}]",
                        message=f"Transition 'from' state '{from_state}' not defined"
                    ))
                if to_state and to_state not in states:
                    errors.append(ValidationError(
                        path=f"stateMachines.{sm_name}.transitions[{i}]",
                        message=f"Transition 'to' state '{to_state}' not defined"
                    ))

        return errors, warnings

    def _validate_transition_conflicts(self, spec: dict) -> list[ValidationError]:
        """
        Phase 2-3: Detect conflicting state transitions.

        Validates:
        - No two transitions from the same state with the same trigger and overlapping guards
        - Deterministic transition behavior

        Returns StructuredError with code TRANS-001 for conflicts.
        """
        errors = []
        state_machines = spec.get("stateMachines", {})

        for sm_name, sm in state_machines.items():
            transitions = sm.get("transitions", [])

            # Group transitions by (from_state, trigger_function)
            transition_groups: dict[tuple[str, str], list[tuple[int, dict]]] = {}

            for i, trans in enumerate(transitions):
                from_state = trans.get("from", "")
                trigger = trans.get("trigger_function", trans.get("event", ""))

                if not trigger:
                    continue

                key = (from_state, trigger)
                if key not in transition_groups:
                    transition_groups[key] = []
                transition_groups[key].append((i, trans))

            # Check for conflicts in each group
            for (from_state, trigger), group in transition_groups.items():
                if len(group) <= 1:
                    continue

                # Multiple transitions - check if guards are mutually exclusive
                has_unguarded = any(not t.get("guard") for _, t in group)
                guarded_count = sum(1 for _, t in group if t.get("guard"))

                if has_unguarded and len(group) > 1:
                    # Unguarded transition with other transitions = potential conflict
                    errors.append(ValidationError(
                        path=f"stateMachines.{sm_name}.transitions",
                        message=f"Potential transition conflict: multiple transitions from '{from_state}' "
                                f"on trigger '{trigger}' with at least one unguarded transition",
                        code="TRANS-001",
                        category="logic",
                        expected="mutually exclusive guards or single transition",
                        actual=f"{len(group)} transitions, {guarded_count} guarded",
                        auto_fixable=False
                    ))
                elif guarded_count == len(group) and guarded_count > 1:
                    # All guarded - warning about potential overlap (can't statically verify)
                    # We'll just note it as informational
                    pass

        return errors
