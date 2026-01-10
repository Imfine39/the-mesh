"""Validation handlers for The Mesh."""

import copy
import json
from pathlib import Path
from typing import Any

from the_mesh.core.validator import MeshValidator
from the_mesh.core.errors import ValidationError
from the_mesh.core.utils import generate_fix_patches
from the_mesh.graph.graph import DependencyGraph
from the_mesh.core.storage import SpecStorage


def load_spec(storage: SpecStorage, spec: dict | None, spec_path: str | None) -> dict:
    """Load spec from dict or file path"""
    if spec:
        return spec
    if spec_path:
        path = Path(spec_path)
        if path.exists():
            with open(path) as f:
                return json.load(f)
        raise FileNotFoundError(f"Spec file not found: {spec_path}")
    raise ValueError("Either 'spec' or 'spec_path' must be provided")


def validate_spec(validator: MeshValidator, storage: SpecStorage, args: dict) -> dict:
    """Validate a complete Mesh specification"""
    spec = load_spec(storage, args.get("spec"), args.get("spec_path"))
    result = validator.validate(spec)

    return {
        "valid": result.valid,
        "errors": [e.to_structured().to_dict() for e in result.errors],
        "warnings": [e.to_structured().to_dict() for e in result.warnings],
        "error_count": len(result.errors),
        "warning_count": len(result.warnings),
        "fix_patches": result.get_fix_patches(),
    }


def validate_expression(validator: MeshValidator, storage: SpecStorage, args: dict) -> dict:
    """Validate a single expression"""
    expression = args["expression"]
    context = args.get("context", {})

    # Create a minimal spec for validation
    minimal_spec = {
        "meta": {"name": "expression_validation", "version": "1.0"},
        "state": {
            "entities": context.get("entities", {}),
            "derived": {
                "_temp_expr": {
                    "formula": expression,
                    "returns": "any"
                }
            }
        }
    }

    result = validator.validate(minimal_spec)

    # Filter errors to only those related to the expression
    expr_errors = [
        e for e in result.errors
        if "_temp_expr" in e.path or "expression" in e.path.lower()
    ]

    return {
        "valid": len(expr_errors) == 0,
        "errors": [e.to_structured().to_dict() for e in expr_errors],
    }


def validate_partial(validator: MeshValidator, storage: SpecStorage, args: dict) -> dict:
    """Validate only changed parts of a spec (incremental validation)"""
    base_spec = args["base_spec"]
    changes = args["changes"]

    # Apply changes to create new spec
    new_spec = copy.deepcopy(base_spec)

    for change in changes:
        op = change.get("op")
        path = change.get("path", "").strip("/").split("/")
        value = change.get("value")

        # Navigate to the target location
        current = new_spec
        for i, key in enumerate(path[:-1]):
            if isinstance(current, dict):
                current = current.get(key, {})
            elif isinstance(current, list) and key.isdigit():
                current = current[int(key)]

        # Apply the operation
        if path:
            final_key = path[-1]
            if op == "add" or op == "replace":
                if isinstance(current, dict):
                    current[final_key] = value
                elif isinstance(current, list) and final_key.isdigit():
                    if op == "add":
                        current.insert(int(final_key), value)
                    else:
                        current[int(final_key)] = value
            elif op == "remove":
                if isinstance(current, dict) and final_key in current:
                    del current[final_key]
                elif isinstance(current, list) and final_key.isdigit():
                    del current[int(final_key)]

    # Validate the modified spec
    result = validator.validate(new_spec)

    # Optionally filter to only errors in changed paths
    changed_paths = set()
    for change in changes:
        changed_paths.add(change.get("path", "").strip("/").replace("/", "."))

    return {
        "valid": result.valid,
        "errors": [e.to_structured().to_dict() for e in result.errors],
        "warnings": [e.to_structured().to_dict() for e in result.warnings],
        "changes_applied": len(changes),
    }


def get_fix_suggestion(validator: MeshValidator, storage: SpecStorage, args: dict) -> dict:
    """Get auto-fix suggestions for validation errors"""
    errors = args["errors"]

    # Convert dict errors back to ValidationError objects
    validation_errors = []
    for e in errors:
        validation_errors.append(ValidationError(
            path=e.get("path", ""),
            message=e.get("message", ""),
            severity=e.get("severity", "error"),
            code=e.get("code", ""),
            category=e.get("category", "schema"),
            expected=e.get("expected"),
            actual=e.get("actual"),
            valid_options=e.get("valid_options", []),
            auto_fixable=e.get("auto_fixable", False),
            fix_patch=e.get("fix_patch"),
        ))

    patches = generate_fix_patches(validation_errors)

    return {
        "patches": patches,
        "fixable_count": len(patches),
        "total_errors": len(errors),
    }


def suggest_completion(validator: MeshValidator, storage: SpecStorage, args: dict) -> dict:
    """Suggest completions for missing required fields"""
    partial_spec = args["partial_spec"]
    suggestions = []

    # Check for missing meta fields
    if "meta" not in partial_spec:
        suggestions.append({
            "path": "/meta",
            "suggestion": {"name": "untitled", "version": "1.0"},
            "reason": "meta is required"
        })

    # Check for missing state
    if "state" not in partial_spec:
        suggestions.append({
            "path": "/state",
            "suggestion": {"entities": {}},
            "reason": "state is required"
        })

    state = partial_spec.get("state", {})

    # Check SagaSteps for missing forward
    for saga_name, saga in state.get("sagas", {}).items():
        for i, step in enumerate(saga.get("steps", [])):
            if "forward" not in step and "action" not in step:
                suggestions.append({
                    "path": f"/state/sagas/{saga_name}/steps/{i}/forward",
                    "suggestion": f"execute_{step.get('name', 'step')}",
                    "reason": "SagaStep requires 'forward' field"
                })

    # Check UpdateActions for missing target
    for func_name, func in state.get("functions", {}).items():
        for i, post in enumerate(func.get("post", [])):
            action = post.get("action", {})
            if "update" in action and "target" not in action:
                suggestions.append({
                    "path": f"/state/functions/{func_name}/post/{i}/action/target",
                    "suggestion": {"type": "input", "name": "id"},
                    "reason": "UpdateAction requires 'target' field"
                })

    # Check DerivedFormula for missing returns
    for derived_name, derived in state.get("derived", {}).items():
        if "returns" not in derived:
            suggestions.append({
                "path": f"/state/derived/{derived_name}/returns",
                "suggestion": "number",
                "reason": "DerivedFormula requires 'returns' field"
            })

    return {
        "suggestions": suggestions,
        "count": len(suggestions),
    }


def analyze_impact(validator: MeshValidator, storage: SpecStorage, args: dict) -> dict:
    """Analyze impact of a change on the specification"""
    spec = args["spec"]
    change = args["change"]

    # Build dependency graph
    graph = DependencyGraph()
    graph.build_from_spec(spec)

    # Determine what's being changed
    change_path = change.get("path", "").strip("/")
    change_type = change.get("type", "modify")  # add, modify, remove

    # Parse change_path to get target_type and target_name
    # Format: "state/entities/Invoice" or "state.entities.Invoice"
    parts = change_path.replace("/", ".").split(".")
    target_type = "unknown"
    target_name = change_path

    if len(parts) >= 3 and parts[0] == "state":
        category = parts[1]  # entities, derived, functions, etc.
        target_name = parts[2] if len(parts) > 2 else ""
        type_map = {
            "entities": "entity",
            "derived": "derived",
            "functions": "function",
            "scenarios": "scenario",
            "invariants": "invariant",
            "stateMachines": "stateMachine",
            "events": "event",
            "subscriptions": "subscription",
            "sagas": "saga",
            "roles": "role",
            "gateways": "gateway",
            "deadlines": "deadline",
        }
        target_type = type_map.get(category, "unknown")

    # Find affected elements
    impact = graph.analyze_impact(target_type, target_name, change_type)

    # Calculate total affected
    total_affected = (
        len(impact.affected_entities) +
        len(impact.affected_derived) +
        len(impact.affected_functions) +
        len(impact.affected_scenarios) +
        len(impact.affected_invariants) +
        len(impact.affected_state_machines) +
        len(impact.affected_events) +
        len(impact.affected_subscriptions) +
        len(impact.affected_sagas) +
        len(impact.affected_roles) +
        len(impact.affected_gateways) +
        len(impact.affected_deadlines)
    )

    # Determine if breaking change
    is_breaking = (
        change_type == "remove" and
        (len(impact.affected_functions) > 0 or
         len(impact.affected_scenarios) > 0 or
         len(impact.breaking_changes) > 0)
    )

    return {
        "change_path": change_path,
        "change_type": change_type,
        "affected_entities": list(impact.affected_entities),
        "affected_derived": list(impact.affected_derived),
        "affected_functions": list(impact.affected_functions),
        "affected_scenarios": list(impact.affected_scenarios),
        "affected_invariants": list(impact.affected_invariants),
        "affected_state_machines": list(impact.affected_state_machines),
        "affected_events": list(impact.affected_events),
        "affected_sagas": list(impact.affected_sagas),
        "affected_roles": list(impact.affected_roles),
        "total_affected": total_affected,
        "breaking_change": is_breaking,
        "breaking_changes": impact.breaking_changes,
    }


def check_reference(validator: MeshValidator, storage: SpecStorage, args: dict) -> dict:
    """Check if a reference path is valid in the spec"""
    spec = args["spec"]
    reference = args["reference"]

    state = spec.get("state", {})
    entities = state.get("entities", {})
    derived = state.get("derived", {})

    parts = reference.split(".")
    if not parts:
        return {"valid": False, "error": "Empty reference"}

    # First part should be an entity name or 'self'
    first = parts[0]
    if first == "self":
        return {
            "valid": True,
            "note": "'self' reference - context dependent",
            "remaining_path": ".".join(parts[1:])
        }

    if first not in entities:
        # Check if it's a derived formula
        if first in derived:
            return {"valid": True, "type": "derived", "name": first}
        return {
            "valid": False,
            "error": f"Unknown entity: {first}",
            "valid_entities": list(entities.keys())
        }

    # Navigate through the reference path
    current_entity = entities[first]
    path_so_far = first

    for i, part in enumerate(parts[1:], 1):
        fields = current_entity.get("fields", {})
        if part not in fields:
            return {
                "valid": False,
                "error": f"Unknown field '{part}' in {path_so_far}",
                "valid_fields": list(fields.keys())
            }

        field = fields[part]
        field_type = field.get("type", {})
        path_so_far += f".{part}"

        # Check if it's a reference to another entity
        if isinstance(field_type, dict) and "ref" in field_type:
            ref_target = field_type["ref"]
            if ref_target in entities:
                current_entity = entities[ref_target]
            else:
                return {
                    "valid": False,
                    "error": f"Invalid reference target: {ref_target}",
                    "at_path": path_so_far
                }
        elif i < len(parts) - 1:
            # Trying to traverse through a non-reference field
            return {
                "valid": False,
                "error": f"Cannot traverse through non-reference field: {part}",
                "at_path": path_so_far,
                "field_type": field_type
            }

    return {
        "valid": True,
        "resolved_path": path_so_far,
        "final_entity": current_entity.get("_kind", "entity")
    }


def get_entity_schema(validator: MeshValidator, storage: SpecStorage, args: dict) -> dict:
    """Get schema information for an entity"""
    spec = args["spec"]
    entity_name = args["entity_name"]

    entities = spec.get("state", {}).get("entities", {})

    if entity_name not in entities:
        return {
            "found": False,
            "error": f"Entity not found: {entity_name}",
            "available_entities": list(entities.keys())
        }

    entity = entities[entity_name]
    fields = entity.get("fields", {})

    # Build field info
    field_info = {}
    for field_name, field in fields.items():
        field_type = field.get("type")
        info = {
            "type": field_type,
            "required": field.get("required", False),
        }
        if "default" in field:
            info["default"] = field["default"]
        if isinstance(field_type, dict):
            if "enum" in field_type:
                info["enum_values"] = field_type["enum"]
            if "ref" in field_type:
                info["references"] = field_type["ref"]
        field_info[field_name] = info

    return {
        "found": True,
        "entity_name": entity_name,
        "fields": field_info,
        "field_count": len(fields),
        "indexes": entity.get("indexes", []),
    }


def list_valid_values(validator: MeshValidator, storage: SpecStorage, args: dict) -> dict:
    """List valid values for a field"""
    spec = args["spec"]
    field_path = args["field_path"]

    parts = field_path.split(".")
    if len(parts) != 2:
        return {"error": "field_path should be 'EntityName.fieldName'"}

    entity_name, field_name = parts
    entities = spec.get("state", {}).get("entities", {})

    if entity_name not in entities:
        return {
            "found": False,
            "error": f"Entity not found: {entity_name}",
            "available_entities": list(entities.keys())
        }

    entity = entities[entity_name]
    fields = entity.get("fields", {})

    if field_name not in fields:
        return {
            "found": False,
            "error": f"Field not found: {field_name}",
            "available_fields": list(fields.keys())
        }

    field = fields[field_name]
    field_type = field.get("type")

    result = {
        "found": True,
        "field_path": field_path,
        "field_type": field_type,
    }

    if isinstance(field_type, dict):
        if "enum" in field_type:
            result["valid_values"] = field_type["enum"]
            result["value_type"] = "enum"
        elif "ref" in field_type:
            ref_target = field_type["ref"]
            result["references"] = ref_target
            result["value_type"] = "reference"
            # List existing IDs if available
            if ref_target in entities:
                result["note"] = f"Reference to {ref_target} entity"
    elif field_type in ("string", "int", "float", "bool", "datetime"):
        result["value_type"] = field_type

    return result


def get_dependencies(validator: MeshValidator, storage: SpecStorage, args: dict) -> dict:
    """Get dependencies for a given element in the spec"""
    spec = args["spec"]
    element_path = args["element_path"]

    # Build dependency graph
    graph = DependencyGraph()
    graph.build_from_spec(spec)

    # Get dependencies
    node_id = element_path.replace("/", ".")

    deps = graph.get_dependencies(node_id)
    dependents = graph.get_dependents(node_id)

    return {
        "element": element_path,
        "dependencies": list(deps),
        "dependents": list(dependents),
        "dependency_count": len(deps),
        "dependent_count": len(dependents),
    }


# Handler registry
HANDLERS = {
    "validate_spec": validate_spec,
    "validate_expression": validate_expression,
    "validate_partial": validate_partial,
    "get_fix_suggestion": get_fix_suggestion,
    "suggest_completion": suggest_completion,
    "analyze_impact": analyze_impact,
    "check_reference": check_reference,
    "get_entity_schema": get_entity_schema,
    "list_valid_values": list_valid_values,
    "get_dependencies": get_dependencies,
}
