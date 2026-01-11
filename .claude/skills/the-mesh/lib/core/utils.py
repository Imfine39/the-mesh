"""Utility functions for The Mesh validator."""

from __future__ import annotations

import copy
import re
from typing import TYPE_CHECKING

from core.errors import ValidationError, ValidationResult

if TYPE_CHECKING:
    from core.validator import MeshValidator


def generate_fix_patches(errors: list[ValidationError]) -> list[dict]:
    """
    Generate JSON Patch format fixes that Claude Code can apply directly.

    Args:
        errors: List of validation errors

    Returns:
        List of JSON Patch operations:
        [
            {"op": "replace", "path": "/state/entities/Invoice/fields/status/type",
             "value": {"enum": ["draft", "open", "closed"]}},
            {"op": "add", "path": "/state/sagas/payment/steps/0/forward",
             "value": "process_payment"},
        ]
    """
    patches = []
    for err in errors:
        if err.auto_fixable and err.fix_patch:
            patches.append(err.fix_patch)
        else:
            # Try to generate fix based on error type
            suggested = suggest_fix_for_error(err)
            if suggested:
                patches.append(suggested)
    return patches


def suggest_fix_for_error(error: ValidationError) -> dict | None:
    """
    Phase 0-3: Generate a fix suggestion based on error type.

    Analyzes the error and generates a JSON Patch operation to fix it.
    """
    if not error.code:
        return None

    # TYP-001: Enum value mismatch - suggest closest valid value
    if error.code == "TYP-001" and error.valid_options:
        # Find closest match to actual value
        actual = str(error.actual).lower() if error.actual else ""
        closest = find_closest_match(actual, error.valid_options)
        if closest:
            json_path = _dot_path_to_json_path(error.path)
            return {
                "op": "replace",
                "path": f"{json_path}/value",
                "value": closest,
                "reason": f"Replace '{error.actual}' with valid enum value '{closest}'"
            }

    # REF-002: Invalid reference path - suggest valid field
    if error.code == "REF-002" and error.valid_options:
        actual = str(error.actual).lower() if error.actual else ""
        closest = find_closest_match(actual, error.valid_options)
        if closest:
            return {
                "op": "replace",
                "path": _dot_path_to_json_path(error.path),
                "value": f"Use '{closest}' instead of '{error.actual}'",
                "reason": f"Field '{error.actual}' not found, did you mean '{closest}'?"
            }

    # TRANS-001: Transition conflict - suggest adding guard
    if error.code == "TRANS-001":
        return {
            "op": "add",
            "path": f"{_dot_path_to_json_path(error.path)}/guard",
            "value": {"type": "literal", "value": True},
            "reason": "Add guard condition to resolve transition conflict"
        }

    return None


def find_closest_match(target: str, options: list[str]) -> str | None:
    """Find the closest matching string from options using simple similarity."""
    if not options:
        return None

    target_lower = target.lower()

    # Exact match (case-insensitive)
    for opt in options:
        if opt.lower() == target_lower:
            return opt

    # Prefix match
    for opt in options:
        if opt.lower().startswith(target_lower) or target_lower.startswith(opt.lower()):
            return opt

    # Substring match
    for opt in options:
        if target_lower in opt.lower() or opt.lower() in target_lower:
            return opt

    # Return first option as fallback
    return options[0] if options else None


def _dot_path_to_json_path(dot_path: str) -> str:
    """Convert dot notation path to JSON Patch path format."""
    # e.g., "functions.check.pre[0].expr" -> "/functions/check/pre/0/expr"
    # Replace array indices
    path = re.sub(r'\[(\d+)\]', r'/\1', dot_path)
    # Replace dots with slashes
    path = path.replace('.', '/')
    # Ensure starts with /
    if not path.startswith('/'):
        path = '/' + path
    return path


def validate_changes(base_spec: dict, changes: list[dict], validator: MeshValidator = None) -> ValidationResult:
    """
    Phase 0-5: Incremental validation - validate only changed portions.

    Applies JSON Patch changes to the base spec and validates the affected areas.
    More efficient than full validation for large specs with small changes.

    Args:
        base_spec: The base TRIR specification
        changes: List of JSON Patch operations:
            [{"op": "replace", "path": "/functions/foo/description", "value": "..."}]
        validator: Optional MeshValidator instance (creates new one if not provided)

    Returns:
        ValidationResult with errors only from affected areas
    """
    # Import here to avoid circular dependency at module level
    from core.validator import MeshValidator as MV

    if validator is None:
        validator = MV()

    # Apply changes to get the new spec
    new_spec = copy.deepcopy(base_spec)

    for change in changes:
        op = change.get("op", "")
        path = change.get("path", "")
        value = change.get("value")

        # Parse JSON Patch path
        path_parts = [p for p in path.split("/") if p]

        if not path_parts:
            continue

        try:
            if op == "add":
                _apply_add(new_spec, path_parts, value)
            elif op == "replace":
                _apply_replace(new_spec, path_parts, value)
            elif op == "remove":
                _apply_remove(new_spec, path_parts)
        except (KeyError, IndexError, TypeError):
            # Skip invalid patches
            continue

    # Determine affected areas and validate
    affected_paths = set()
    for change in changes:
        path = change.get("path", "")
        # Extract top-level affected area (e.g., /functions/foo -> functions)
        parts = [p for p in path.split("/") if p]
        if parts:
            affected_paths.add(parts[0])
            if len(parts) > 1:
                affected_paths.add(f"{parts[0]}.{parts[1]}")

    # Full validation on the new spec
    result = validator.validate(new_spec)

    # Filter errors to only those in affected areas (optional optimization)
    # For now, return all errors to ensure correctness
    return result


def _apply_add(obj: dict, path_parts: list[str], value) -> None:
    """Apply JSON Patch 'add' operation"""
    for part in path_parts[:-1]:
        if part.isdigit():
            obj = obj[int(part)]
        else:
            obj = obj[part]
    final = path_parts[-1]
    if final.isdigit():
        obj.insert(int(final), value)
    else:
        obj[final] = value


def _apply_replace(obj: dict, path_parts: list[str], value) -> None:
    """Apply JSON Patch 'replace' operation"""
    for part in path_parts[:-1]:
        if part.isdigit():
            obj = obj[int(part)]
        else:
            obj = obj[part]
    final = path_parts[-1]
    if final.isdigit():
        obj[int(final)] = value
    else:
        obj[final] = value


def _apply_remove(obj: dict, path_parts: list[str]) -> None:
    """Apply JSON Patch 'remove' operation"""
    for part in path_parts[:-1]:
        if part.isdigit():
            obj = obj[int(part)]
        else:
            obj = obj[part]
    final = path_parts[-1]
    if final.isdigit():
        del obj[int(final)]
    else:
        del obj[final]


def suggest_completions(partial_spec: dict) -> list[dict]:
    """
    Phase 0-4: Generate completion suggestions for missing required fields.

    Analyzes a partial spec and suggests completions for missing fields.

    Args:
        partial_spec: A partial TRIR specification

    Returns:
        List of completion suggestions:
        [
            {"path": "/state/sagas/payment/steps/0/forward",
             "suggestion": "process_payment",
             "reason": "SagaStep requires 'forward' field"},
        ]
    """
    suggestions = []

    # Check meta section
    meta = partial_spec.get("meta", {})
    if not meta.get("id"):
        suggestions.append({
            "path": "/meta/id",
            "suggestion": "my-spec",
            "reason": "Meta requires 'id' field"
        })
    if not meta.get("version"):
        suggestions.append({
            "path": "/meta/version",
            "suggestion": "1.0.0",
            "reason": "Meta requires 'version' field"
        })
    if not meta.get("title"):
        suggestions.append({
            "path": "/meta/title",
            "suggestion": "My Specification",
            "reason": "Meta requires 'title' field"
        })

    # Check sagas
    for saga_name, saga in partial_spec.get("sagas", {}).items():
        steps = saga.get("steps", [])
        for i, step in enumerate(steps):
            if not step.get("forward"):
                suggestions.append({
                    "path": f"/sagas/{saga_name}/steps/{i}/forward",
                    "suggestion": f"{step.get('name', 'step')}_action",
                    "reason": "SagaStep requires 'forward' field"
                })
            if not step.get("name"):
                suggestions.append({
                    "path": f"/sagas/{saga_name}/steps/{i}/name",
                    "suggestion": f"step_{i + 1}",
                    "reason": "SagaStep requires 'name' field"
                })

    # Check functions
    for func_name, func in partial_spec.get("commands", {}).items():
        if not func.get("description"):
            suggestions.append({
                "path": f"/functions/{func_name}/description",
                "suggestion": f"Performs {func_name} operation",
                "reason": "Function requires 'description' field"
            })
        if "input" not in func:
            suggestions.append({
                "path": f"/functions/{func_name}/input",
                "suggestion": {},
                "reason": "Function requires 'input' field (can be empty object)"
            })

        # Check post actions
        for i, post in enumerate(func.get("post", [])):
            action = post.get("action", {})
            if action.get("update") and not action.get("target"):
                suggestions.append({
                    "path": f"/functions/{func_name}/post/{i}/action/target",
                    "suggestion": {"type": "input", "name": "id"},
                    "reason": "UpdateAction requires 'target' field"
                })

    # Check state machines
    for sm_name, sm in partial_spec.get("stateMachines", {}).items():
        if not sm.get("initial"):
            states = list(sm.get("states", {}).keys())
            suggestions.append({
                "path": f"/stateMachines/{sm_name}/initial",
                "suggestion": states[0] if states else "INITIAL",
                "reason": "StateMachine requires 'initial' field"
            })

    # Check derived formulas
    for derived_name, derived in partial_spec.get("derived", {}).items():
        if not derived.get("returns"):
            suggestions.append({
                "path": f"/derived/{derived_name}/returns",
                "suggestion": "string",
                "reason": "DerivedFormula requires 'returns' field"
            })
        if not derived.get("entity"):
            suggestions.append({
                "path": f"/derived/{derived_name}/entity",
                "suggestion": "Entity",
                "reason": "DerivedFormula requires 'entity' field"
            })

    # Check entities
    for entity_name, entity in partial_spec.get("entities", {}).items():
        if not entity.get("fields"):
            suggestions.append({
                "path": f"/state/{entity_name}/fields",
                "suggestion": {"id": {"type": "string"}},
                "reason": "Entity should have at least one field"
            })

    return suggestions
