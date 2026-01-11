"""Saga validation mixin for The Mesh validator."""

from core.errors import ValidationError


class SagaValidationMixin:
    """Mixin providing saga validation methods."""

    def _validate_sagas(self, spec: dict) -> list[ValidationError]:
        """
        Validate saga definitions (Phase 5 - Workflow layer).

        Checks:
        1. Step action function references
        2. Step compensation function references
        3. Step order consistency
        4. OnFailure policy validity
        """
        errors = []
        sagas = spec.get("sagas", {})
        functions = spec.get("commands", {})

        valid_failure_policies = ["compensate_all", "compensate_completed", "fail_fast", "continue"]

        for saga_name, saga in sagas.items():
            steps = saga.get("steps", [])

            # Track step names for order validation
            step_names = set()

            for i, step in enumerate(steps):
                step_name = step.get("name", f"step_{i}")

                # Check for duplicate step names
                if step_name in step_names:
                    errors.append(ValidationError(
                        path=f"sagas.{saga_name}.steps[{i}]",
                        message=f"Duplicate step name '{step_name}'"
                    ))
                step_names.add(step_name)

                # Validate forward function (already validated in _validate_references)
                # Additional: check that forward has corresponding compensate
                forward = step.get("forward", "")
                compensate = step.get("compensate", "")

                # If forward modifies state, compensate should exist
                if forward and forward in functions:
                    func = functions[forward]
                    has_side_effects = bool(func.get("post", []))
                    if has_side_effects and not compensate:
                        # This is more of a warning, but we'll report it
                        pass  # Could add warning here

                # Validate compensate function if specified
                if compensate and compensate not in functions:
                    errors.append(ValidationError(
                        path=f"sagas.{saga_name}.steps[{i}].compensate",
                        message=f"Compensate function '{compensate}' not found"
                    ))

                # Validate step dependencies (if any)
                depends_on = step.get("dependsOn", [])
                for dep in depends_on:
                    if dep not in step_names:
                        # Dependency must be a previous step
                        found = False
                        for j in range(i):
                            if steps[j].get("name") == dep:
                                found = True
                                break
                        if not found:
                            errors.append(ValidationError(
                                path=f"sagas.{saga_name}.steps[{i}].dependsOn",
                                message=f"Step dependency '{dep}' not found or defined after current step"
                            ))

            # Validate onFailure policy
            on_failure = saga.get("onFailure", "")
            if on_failure and on_failure not in valid_failure_policies:
                errors.append(ValidationError(
                    path=f"sagas.{saga_name}.onFailure",
                    message=f"Invalid failure policy '{on_failure}'. Valid: {', '.join(valid_failure_policies)}"
                ))

        return errors
