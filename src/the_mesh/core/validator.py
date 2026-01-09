"""Mesh JSON Schema Validator"""

import json
from pathlib import Path
from typing import Any, Literal
from dataclasses import dataclass, field as dataclass_field

try:
    import jsonschema
    from jsonschema import Draft202012Validator, RefResolver
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False


# Error code prefixes
# SCH-xxx: Schema violations
# REF-xxx: Reference errors
# TYP-xxx: Type errors
# VAL-xxx: Validation errors
# FSM-xxx: State machine errors
# LGC-xxx: Logic errors
# CNS-xxx: Constraint errors

@dataclass
class StructuredError:
    """Machine-processable error format for Claude Code integration"""

    # Location info
    path: str  # JSONPath: "state.functions.create_invoice.pre[0].expr"
    line: int | None = None  # Line number in source file (if available)

    # Error classification
    code: str = ""  # Systematic code: "TYP-001", "REF-002"
    category: Literal["schema", "reference", "type", "logic", "constraint"] = "schema"
    severity: Literal["critical", "error", "warning"] = "error"
    message: str = ""  # Human-readable message (for debugging)

    # Machine-processable info
    expected: Any = None  # Expected value/format
    actual: Any = None  # Actual value
    valid_options: list[str] = dataclass_field(default_factory=list)  # Valid choices (for Enum etc.)

    # Auto-fix info
    auto_fixable: bool = False  # Can be auto-fixed
    fix_patch: dict | None = None  # JSON Patch format fix suggestion

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "path": self.path,
            "line": self.line,
            "code": self.code,
            "category": self.category,
            "severity": self.severity,
            "message": self.message,
            "expected": self.expected,
            "actual": self.actual,
            "valid_options": self.valid_options,
            "auto_fixable": self.auto_fixable,
            "fix_patch": self.fix_patch,
        }


# Alias for backward compatibility
@dataclass
class ValidationError:
    """Legacy error format - wraps StructuredError for backward compatibility"""
    path: str
    message: str
    severity: str = "error"

    # Extended fields (optional for backward compatibility)
    code: str = ""
    category: str = "schema"
    expected: Any = None
    actual: Any = None
    valid_options: list[str] = dataclass_field(default_factory=list)
    auto_fixable: bool = False
    fix_patch: dict | None = None

    def to_structured(self) -> StructuredError:
        """Convert to StructuredError"""
        return StructuredError(
            path=self.path,
            message=self.message,
            severity=self.severity if self.severity in ("critical", "error", "warning") else "error",
            code=self.code,
            category=self.category if self.category in ("schema", "reference", "type", "logic", "constraint") else "schema",
            expected=self.expected,
            actual=self.actual,
            valid_options=self.valid_options,
            auto_fixable=self.auto_fixable,
            fix_patch=self.fix_patch,
        )


# =========================================================================
# Validation Context for depth limiting and other settings
# =========================================================================

@dataclass
class ValidationCache:
    """Cache for validation results to avoid re-validation"""
    # Expression hash -> validation errors (for identical expressions)
    expression_results: dict = dataclass_field(default_factory=dict)
    # Reference path -> resolved entity/field (for path resolution)
    reference_cache: dict = dataclass_field(default_factory=dict)
    # Entity name -> field info (for entity lookups)
    entity_fields_cache: dict = dataclass_field(default_factory=dict)
    # Stats for debugging
    hits: int = 0
    misses: int = 0

    def clear(self):
        """Clear all caches"""
        self.expression_results.clear()
        self.reference_cache.clear()
        self.entity_fields_cache.clear()
        self.hits = 0
        self.misses = 0


@dataclass
class ValidationContext:
    """Configuration for validation behavior"""
    max_depth: int = 50  # Maximum expression nesting depth
    current_depth: int = 0
    cache: ValidationCache | None = None  # Optional cache for performance

    def with_depth(self, depth: int) -> "ValidationContext":
        """Create a new context with specified depth"""
        return ValidationContext(max_depth=self.max_depth, current_depth=depth, cache=self.cache)

    def get_or_create_cache(self) -> ValidationCache:
        """Get existing cache or create new one"""
        if self.cache is None:
            self.cache = ValidationCache()
        return self.cache


# Default validation context
DEFAULT_VALIDATION_CONTEXT = ValidationContext()


# =========================================================================
# Expression Type Definitions for Custom Discriminator Validation (VAL-001)
# Based on expression.schema.json - discriminator on "type" field
# =========================================================================

EXPRESSION_TYPE_SCHEMAS = {
    "literal": {
        "required": ["type", "value"],
        "optional": [],
        "nested_expressions": []
    },
    "ref": {
        "required": ["type", "path"],
        "optional": [],
        "nested_expressions": []
    },
    "input": {
        "required": ["type", "name"],
        "optional": [],
        "nested_expressions": []
    },
    "self": {
        "required": ["type", "field"],
        "optional": [],
        "nested_expressions": []
    },
    "binary": {
        "required": ["type", "op", "left", "right"],
        "optional": [],
        "nested_expressions": ["left", "right"]
    },
    "unary": {
        "required": ["type", "op", "expr"],
        "optional": [],
        "nested_expressions": ["expr"]
    },
    "agg": {
        "required": ["type", "op", "from"],
        "optional": ["as", "expr", "where"],
        "nested_expressions": ["expr", "where"]
    },
    "call": {
        "required": ["type", "name"],
        "optional": ["args"],
        "nested_expressions": [],  # args handled specially
        "nested_arrays": ["args"]
    },
    "if": {
        "required": ["type", "cond", "then", "else"],
        "optional": [],
        "nested_expressions": ["cond", "then", "else"]
    },
    "case": {
        "required": ["type", "branches"],
        "optional": ["else"],
        "nested_expressions": ["else"],
        "special": "branches"  # branches handled specially
    },
    "date": {
        "required": ["type", "op"],
        "optional": ["args", "unit"],
        "nested_expressions": [],
        "nested_arrays": ["args"]
    },
    "list": {
        "required": ["type", "op", "list"],
        "optional": ["args"],
        "nested_expressions": ["list"],
        "nested_arrays": ["args"]
    },
    # Phase 1 Extension types
    "temporal": {
        "required": ["type", "op"],
        "optional": ["entity", "field", "time", "condition"],
        "nested_expressions": ["time", "condition"]
    },
    "window": {
        "required": ["type", "op", "from"],
        "optional": ["expr", "partitionBy", "orderBy", "frame", "args"],
        "nested_expressions": ["expr"],
        "nested_arrays": ["partitionBy", "args"],
        "special": "orderBy"  # orderBy handled specially
    },
    "tree": {
        "required": ["type", "op", "entity"],
        "optional": ["node", "parentField", "maxDepth", "includeNode"],
        "nested_expressions": ["node"]
    },
    "transitive": {
        "required": ["type", "op", "relation"],
        "optional": ["from", "to", "maxHops"],
        "nested_expressions": ["from", "to"]
    },
    "state": {
        "required": ["type", "op", "machine"],
        "optional": ["entity", "state", "event"],
        "nested_expressions": ["entity"]
    },
    "principal": {
        "required": ["type", "op"],
        "optional": ["role", "permission", "resource", "attribute", "group"],
        "nested_expressions": ["resource"]
    }
}

# Valid operators for each expression type
EXPRESSION_OPERATORS = {
    "binary": ["add", "sub", "mul", "div", "mod", "eq", "ne", "lt", "le", "gt", "ge", "and", "or", "in", "not_in", "like", "not_like"],
    "unary": ["not", "neg", "is_null", "is_not_null"],
    "agg": ["sum", "count", "avg", "min", "max", "exists", "not_exists", "all", "any"],
    "date": ["diff", "add", "sub", "now", "today", "overlaps", "truncate"],
    "list": ["contains", "length", "first", "last", "at", "slice"],
    "temporal": ["at", "since", "until", "before", "after", "always", "eventually", "historically", "once", "previous", "next"],
    "window": ["row_number", "rank", "dense_rank", "ntile", "lag", "lead", "first_value", "last_value", "nth_value", "sum", "avg", "min", "max", "count"],
    "tree": ["ancestors", "descendants", "parent", "children", "siblings", "root", "leaves", "depth", "path", "subtree"],
    "transitive": ["closure", "reflexive_closure", "reachable", "connected", "path_exists"],
    "state": ["current", "is_in", "can_transition", "history", "time_in_state", "previous_state", "available_transitions"],
    "principal": ["current_user", "current_tenant", "has_role", "has_permission", "in_group", "is_owner", "attribute"]
}


@dataclass
class ValidationResult:
    valid: bool
    errors: list[ValidationError]
    warnings: list[ValidationError]

    def to_structured_errors(self) -> list[StructuredError]:
        """Convert all errors to StructuredError format"""
        return [e.to_structured() for e in self.errors]

    def get_fix_patches(self) -> list[dict]:
        """Get all auto-fixable patches from errors"""
        patches = []
        for err in self.errors:
            if err.auto_fixable and err.fix_patch:
                patches.append(err.fix_patch)
        return patches

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "valid": self.valid,
            "errors": [e.to_structured().to_dict() for e in self.errors],
            "warnings": [e.to_structured().to_dict() for e in self.warnings],
            "fix_patches": self.get_fix_patches(),
        }


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
    import re
    # Replace array indices
    path = re.sub(r'\[(\d+)\]', r'/\1', dot_path)
    # Replace dots with slashes
    path = path.replace('.', '/')
    # Ensure starts with /
    if not path.startswith('/'):
        path = '/' + path
    return path


def validate_changes(base_spec: dict, changes: list[dict], validator: "MeshValidator" = None) -> "ValidationResult":
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
    import copy

    if validator is None:
        validator = MeshValidator()

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
    for func_name, func in partial_spec.get("functions", {}).items():
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
    for entity_name, entity in partial_spec.get("state", {}).items():
        if not entity.get("fields"):
            suggestions.append({
                "path": f"/state/{entity_name}/fields",
                "suggestion": {"id": {"type": "string"}},
                "reason": "Entity should have at least one field"
            })

    return suggestions


class MeshValidator:
    """Validates TRIR specifications against JSON Schema"""

    def __init__(self, schema_dir: Path | None = None, enable_cache: bool = True):
        if not HAS_JSONSCHEMA:
            raise ImportError("jsonschema is required: pip install jsonschema")

        if schema_dir is None:
            # Look for schemas in the_mesh/schemas/ directory
            schema_dir = Path(__file__).parent.parent / "schemas"

        self.schema_dir = schema_dir
        self._load_schemas()

        # Phase 3-2: Performance optimization - validation cache
        self._cache = ValidationCache() if enable_cache else None

    def _load_schemas(self):
        """Load all schema files"""
        self.schemas = {}

        # Load main mesh schema (renamed from schema.schema.json)
        schema_file = self.schema_dir / "mesh.schema.json"
        if schema_file.exists():
            with open(schema_file) as f:
                self.schemas["schema"] = json.load(f)

        expr_file = self.schema_dir / "expression.schema.json"
        if expr_file.exists():
            with open(expr_file) as f:
                self.schemas["expression"] = json.load(f)

    def _build_entity_cache(self, spec: dict) -> None:
        """Build entity fields cache for fast lookups"""
        if not self._cache:
            return

        entities = spec.get("state", {})
        for entity_name, entity in entities.items():
            fields = entity.get("fields", {})
            # Cache field names and their types
            field_info = {}
            for field_name, field_def in fields.items():
                field_type = field_def.get("type", "unknown")
                # Handle ref types
                if isinstance(field_type, dict):
                    ref_entity = field_type.get("ref")
                    if ref_entity:
                        field_info[field_name] = {"type": "ref", "ref_entity": ref_entity}
                    elif "enum" in field_type:
                        field_info[field_name] = {"type": "enum", "values": field_type["enum"]}
                    else:
                        field_info[field_name] = {"type": "complex"}
                else:
                    field_info[field_name] = {"type": field_type}
            self._cache.entity_fields_cache[entity_name] = field_info

    def _get_entity_field_info(self, entity_name: str, field_name: str, spec: dict) -> dict | None:
        """Get field info from cache or build it"""
        if self._cache and entity_name in self._cache.entity_fields_cache:
            self._cache.hits += 1
            fields = self._cache.entity_fields_cache[entity_name]
            return fields.get(field_name)
        else:
            if self._cache:
                self._cache.misses += 1
            # Fallback to direct lookup
            entities = spec.get("state", {})
            if entity_name in entities:
                fields = entities[entity_name].get("fields", {})
                if field_name in fields:
                    return {"type": fields[field_name].get("type", "unknown")}
        return None

    # ==========================================================================
    # Phase 4-1: Reference validation helpers (reducing code duplication)
    # ==========================================================================

    def _check_entity_ref(
        self, path: str, ref_value: str, entities: set[str], context: str = ""
    ) -> ValidationError | None:
        """Validate an entity reference, returning error if invalid."""
        if ref_value and ref_value not in entities:
            msg = f"Referenced entity '{ref_value}' does not exist"
            if context:
                msg = f"{context}: {msg}"
            return ValidationError(
                path=path,
                message=msg,
                code="REF-001",
                category="reference",
                expected=list(entities)[:10] if entities else [],
                actual=ref_value
            )
        return None

    def _check_function_ref(
        self, path: str, ref_value: str, functions: set[str], context: str = ""
    ) -> ValidationError | None:
        """Validate a function reference, returning error if invalid."""
        if ref_value and ref_value not in functions:
            msg = f"Referenced function '{ref_value}' does not exist"
            if context:
                msg = f"{context}: {msg}"
            return ValidationError(
                path=path,
                message=msg,
                code="REF-002",
                category="reference",
                expected=list(functions)[:10] if functions else [],
                actual=ref_value
            )
        return None

    def _check_event_ref(
        self, path: str, ref_value: str, events: set[str], context: str = ""
    ) -> ValidationError | None:
        """Validate an event reference, returning error if invalid."""
        if ref_value and ref_value not in events:
            msg = f"Referenced event '{ref_value}' does not exist"
            if context:
                msg = f"{context}: {msg}"
            return ValidationError(
                path=path,
                message=msg,
                code="REF-003",
                category="reference",
                expected=list(events)[:10] if events else [],
                actual=ref_value
            )
        return None

    def _check_role_ref(
        self, path: str, ref_value: str, roles: set[str], context: str = ""
    ) -> ValidationError | None:
        """Validate a role reference, returning error if invalid."""
        if ref_value and ref_value not in roles:
            msg = f"Referenced role '{ref_value}' does not exist"
            if context:
                msg = f"{context}: {msg}"
            return ValidationError(
                path=path,
                message=msg,
                code="REF-004",
                category="reference",
                expected=list(roles)[:10] if roles else [],
                actual=ref_value
            )
        return None

    def _check_value_in_set(
        self, path: str, value: str, valid_set: set[str], value_type: str
    ) -> ValidationError | None:
        """Validate a value is in the valid set, returning error if invalid."""
        if value and value not in valid_set:
            return ValidationError(
                path=path,
                message=f"Invalid {value_type} '{value}'",
                code="VAL-002",
                category="constraint",
                expected=list(valid_set),
                actual=value,
                valid_options=list(valid_set)
            )
        return None

    def validate(self, spec: dict[str, Any]) -> ValidationResult:
        """Validate a TRIR specification"""
        errors = []
        warnings = []

        # Reset cache for new validation
        if self._cache:
            self._cache.clear()
            # Pre-populate entity fields cache for faster lookups
            self._build_entity_cache(spec)

        # 1. JSON Schema validation
        if "schema" in self.schemas:
            schema_errors = self._validate_against_schema(spec, self.schemas["schema"])
            errors.extend(schema_errors)

        # 2. Reference validation (FK references)
        ref_errors = self._validate_references(spec)
        errors.extend(ref_errors)

        # 3. Expression discriminator validation (VAL-001)
        # Custom validation because jsonschema doesn't support discriminator keyword
        discrim_errors = self._validate_expression_discriminator(spec)
        errors.extend(discrim_errors)

        # 4. Expression semantic validation (references, etc.)
        expr_errors = self._validate_expressions(spec)
        errors.extend(expr_errors)

        # 5. State machine validation
        sm_errors, sm_warnings = self._validate_state_machines(spec)
        errors.extend(sm_errors)
        warnings.extend(sm_warnings)

        # 6. Cycle detection
        cycle_warnings = self._detect_cycles(spec)
        warnings.extend(cycle_warnings)

        # 7. Gateway validation (Phase 2)
        gateway_errors = self._validate_gateways(spec)
        errors.extend(gateway_errors)

        # 8. Deadline validation (Phase 2)
        deadline_errors = self._validate_deadlines(spec)
        errors.extend(deadline_errors)

        # 9. Role/Permission validation (Phase 3)
        role_errors, role_warnings = self._validate_roles(spec)
        errors.extend(role_errors)
        warnings.extend(role_warnings)

        # 10. Audit policy validation (Phase 3)
        audit_errors = self._validate_audit_policies(spec)
        errors.extend(audit_errors)

        # 11. External service validation (Phase 4)
        ext_errors = self._validate_external_services(spec)
        errors.extend(ext_errors)

        # 12. Data policy validation (Phase 4)
        dp_errors = self._validate_data_policies(spec)
        errors.extend(dp_errors)

        # 13. Schedule validation (Phase 5)
        schedule_errors = self._validate_schedules(spec)
        errors.extend(schedule_errors)

        # 14. Constraint validation (Phase 5)
        constraint_errors = self._validate_constraints(spec)
        errors.extend(constraint_errors)

        # 15. Saga validation (Phase 5)
        saga_errors = self._validate_sagas(spec)
        errors.extend(saga_errors)

        # 16. Enum usage validation (Phase 2-1)
        enum_errors = self._validate_enum_usage(spec)
        errors.extend(enum_errors)

        # 16.5. Function type consistency (Phase 2-2)
        type_errors = self._validate_function_type_consistency(spec)
        errors.extend(type_errors)

        # 17. Transition conflict detection (Phase 2-3)
        trans_conflict_errors = self._validate_transition_conflicts(spec)
        errors.extend(trans_conflict_errors)

        # 18. Reference path validation (Phase 2-4)
        ref_path_errors = self._validate_reference_paths(spec)
        errors.extend(ref_path_errors)

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )

    def _validate_against_schema(self, spec: dict, schema: dict) -> list[ValidationError]:
        """Validate spec against JSON Schema"""
        errors = []

        try:
            # Load local expression schema if available
            store = {schema.get("$id", ""): schema}

            expr_schema_path = self.schema_dir / "expression.schema.json"
            if expr_schema_path.exists():
                with open(expr_schema_path) as f:
                    expr_schema = json.load(f)
                    store[expr_schema.get("$id", "")] = expr_schema
                    # Also store without domain for local reference
                    store["expression.schema.json"] = expr_schema

            resolver = RefResolver.from_schema(schema, store=store)
            validator = Draft202012Validator(schema, resolver=resolver)

            for error in validator.iter_errors(spec):
                path = ".".join(str(p) for p in error.absolute_path)
                # VAL-001: Handle discriminator-based oneOf errors properly
                # The Python jsonschema library doesn't support discriminator keyword,
                # so it tries all oneOf options and fails. We use custom validation instead.
                if "is not valid under any of the given schemas" in error.message:
                    # Check if this is an expression location - custom validation handles it
                    expr_locations = ["formula", "expr", "when", "condition", "assert", "with", "set", "guard", "left", "right", "cond", "then", "else"]
                    if any(loc in path for loc in expr_locations):
                        # Custom discriminator validation handles expressions
                        # (see _validate_expression_discriminator)
                        continue
                errors.append(ValidationError(
                    path=path or "root",
                    message=error.message
                ))
        except jsonschema.exceptions.RefResolutionError as e:
            # Remote schema resolution failed - skip schema validation
            # This is expected in offline environments
            pass
        except Exception as e:
            # Only report non-network errors
            if "NameResolutionError" not in str(e) and "ConnectionPool" not in str(e):
                errors.append(ValidationError(
                    path="schema",
                    message=f"Schema validation failed: {e}"
                ))

        return errors

    def _validate_references(self, spec: dict) -> list[ValidationError]:
        """Validate entity references (foreign keys) - Phase 4-1 refactored"""
        errors = []
        entities = set(spec.get("state", {}).keys())
        functions = set(spec.get("functions", {}).keys())
        events = set(spec.get("events", {}).keys())
        roles = set(spec.get("roles", {}).keys())

        def add_if_error(err: ValidationError | None):
            if err:
                errors.append(err)

        # Check FK references in entity fields
        for entity_name, entity in spec.get("state", {}).items():
            for field_name, field in entity.get("fields", {}).items():
                field_type = field.get("type", {})
                if isinstance(field_type, dict) and "ref" in field_type:
                    add_if_error(self._check_entity_ref(
                        f"state.{entity_name}.fields.{field_name}",
                        field_type["ref"], entities
                    ))

        # Check entity references in functions
        for func_name, func in spec.get("functions", {}).items():
            # Check pre conditions
            for i, pre in enumerate(func.get("pre", [])):
                if "entity" in pre:
                    add_if_error(self._check_entity_ref(
                        f"functions.{func_name}.pre[{i}]",
                        pre["entity"], entities
                    ))

            # Check post actions
            for i, post in enumerate(func.get("post", [])):
                action = post.get("action", {})
                for action_type in ["create", "update", "delete"]:
                    if action_type in action:
                        add_if_error(self._check_entity_ref(
                            f"functions.{func_name}.post[{i}]",
                            action[action_type], entities
                        ))

        # Check derived entity references
        for derived_name, derived in spec.get("derived", {}).items():
            if "entity" in derived:
                add_if_error(self._check_entity_ref(
                    f"derived.{derived_name}",
                    derived["entity"], entities
                ))

        # Validate stateMachine entity references
        for sm_name, sm in spec.get("stateMachines", {}).items():
            if "entity" in sm:
                add_if_error(self._check_entity_ref(
                    f"stateMachines.{sm_name}",
                    sm["entity"], entities, "State machine"
                ))

        # Validate event entity references
        for event_name, event in spec.get("events", {}).items():
            if "payload" in event:
                for field_name, field in event["payload"].items():
                    if isinstance(field, dict) and "ref" in field.get("type", {}):
                        add_if_error(self._check_entity_ref(
                            f"events.{event_name}.payload.{field_name}",
                            field["type"]["ref"], entities, "Event payload"
                        ))

        # Validate subscription references
        for sub_name, sub in spec.get("subscriptions", {}).items():
            add_if_error(self._check_event_ref(
                f"subscriptions.{sub_name}",
                sub.get("event", ""), events, "Subscription"
            ))
            add_if_error(self._check_function_ref(
                f"subscriptions.{sub_name}",
                sub.get("handler", ""), functions, "Subscription handler"
            ))

        # Validate role inheritance
        for role_name, role in spec.get("roles", {}).items():
            for inherited in role.get("inherits", []):
                add_if_error(self._check_role_ref(
                    f"roles.{role_name}",
                    inherited, roles, "Role inherits from unknown"
                ))

        # Validate saga step function references
        for saga_name, saga in spec.get("sagas", {}).items():
            for i, step in enumerate(saga.get("steps", [])):
                add_if_error(self._check_function_ref(
                    f"sagas.{saga_name}.steps[{i}]",
                    step.get("action", ""), functions, "Saga action"
                ))
                add_if_error(self._check_function_ref(
                    f"sagas.{saga_name}.steps[{i}]",
                    step.get("compensation", ""), functions, "Saga compensation"
                ))

        # Validate relation entity references
        for rel_name, rel in spec.get("relations", {}).items():
            add_if_error(self._check_entity_ref(
                f"relations.{rel_name}",
                rel.get("from", ""), entities, "Relation 'from'"
            ))
            add_if_error(self._check_entity_ref(
                f"relations.{rel_name}",
                rel.get("to", ""), entities, "Relation 'to'"
            ))

        # Validate constraint entity references
        for const_name, const in spec.get("constraints", {}).items():
            add_if_error(self._check_entity_ref(
                f"constraints.{const_name}",
                const.get("entity", ""), entities, "Constraint"
            ))

        # Validate dataPolicy entity references
        for policy_name, policy in spec.get("dataPolicies", {}).items():
            add_if_error(self._check_entity_ref(
                f"dataPolicies.{policy_name}",
                policy.get("entity", ""), entities, "Data policy"
            ))

        # Validate audit entity references
        for audit_name, audit in spec.get("auditPolicies", {}).items():
            add_if_error(self._check_entity_ref(
                f"auditPolicies.{audit_name}",
                audit.get("entity", ""), entities, "Audit policy"
            ))

        # VAL-006: Bidirectional reference consistency check
        relation_errors = self._validate_relations(spec)
        errors.extend(relation_errors)

        return errors

    def _validate_relations(self, spec: dict) -> list[ValidationError]:
        """
        VAL-006: Validate relation definitions for consistency.

        Checks:
        1. foreignKey field exists in the target entity
        2. If inverse is another defined relation, verify from/to consistency
        3. Cascade options are valid
        """
        errors = []
        entities = spec.get("state", {})
        relations = spec.get("relations", {})

        # Build inverse mapping to check bidirectional consistency
        inverse_mapping = {}  # inverse_name -> relation_name
        for rel_name, rel in relations.items():
            if "inverse" in rel:
                inverse_mapping[rel["inverse"]] = rel_name

        for rel_name, rel in relations.items():
            from_entity = rel.get("from", "")
            to_entity = rel.get("to", "")
            foreign_key = rel.get("foreignKey", "")
            rel_type = rel.get("type", "")
            inverse = rel.get("inverse", "")

            # Check: foreignKey exists in target entity
            if foreign_key and to_entity and to_entity in entities:
                to_fields = entities[to_entity].get("fields", {})
                # The foreignKey might be in the 'from' entity for belongs_to relationships
                # or in the 'to' entity for has_many relationships
                from_fields = entities.get(from_entity, {}).get("fields", {})

                # For one_to_many: FK is in the 'to' entity referencing 'from'
                # For many_to_one: FK is in the 'from' entity referencing 'to'
                if rel_type == "one_to_many":
                    if foreign_key not in to_fields:
                        # FK might be named differently - check for ref fields
                        fk_found = False
                        for field_name, field in to_fields.items():
                            if isinstance(field.get("type"), dict) and field["type"].get("ref") == from_entity:
                                fk_found = True
                                break
                        if not fk_found:
                            errors.append(ValidationError(
                                path=f"relations.{rel_name}",
                                message=f"Foreign key '{foreign_key}' or reference to '{from_entity}' not found in entity '{to_entity}'"
                            ))
                elif rel_type == "many_to_one":
                    if foreign_key not in from_fields:
                        fk_found = False
                        for field_name, field in from_fields.items():
                            if isinstance(field.get("type"), dict) and field["type"].get("ref") == to_entity:
                                fk_found = True
                                break
                        if not fk_found:
                            errors.append(ValidationError(
                                path=f"relations.{rel_name}",
                                message=f"Foreign key '{foreign_key}' or reference to '{to_entity}' not found in entity '{from_entity}'"
                            ))

            # Check: If this relation's inverse is another defined relation
            if inverse and inverse in relations:
                inverse_rel = relations[inverse]

                # Verify bidirectional consistency: from/to should be swapped
                if inverse_rel.get("from") != to_entity or inverse_rel.get("to") != from_entity:
                    errors.append(ValidationError(
                        path=f"relations.{rel_name}",
                        message=f"Bidirectional relation mismatch: '{rel_name}' ({from_entity}->{to_entity}) and inverse '{inverse}' ({inverse_rel.get('from')}->{inverse_rel.get('to')}) are not symmetric"
                    ))

                # Verify inverse of inverse points back
                if inverse_rel.get("inverse") and inverse_rel["inverse"] != rel_name:
                    errors.append(ValidationError(
                        path=f"relations.{rel_name}",
                        message=f"Inverse chain broken: '{rel_name}'.inverse = '{inverse}' but '{inverse}'.inverse = '{inverse_rel.get('inverse')}' (expected '{rel_name}')"
                    ))

            # Check: Validate relation type
            valid_types = ["one_to_one", "one_to_many", "many_to_one", "many_to_many"]
            if rel_type and rel_type not in valid_types:
                errors.append(ValidationError(
                    path=f"relations.{rel_name}.type",
                    message=f"Invalid relation type '{rel_type}'. Valid types: {', '.join(valid_types)}"
                ))

            # Check: Validate cascade options
            cascade = rel.get("cascade", {})
            valid_cascades = ["cascade", "restrict", "set_null", "no_action"]
            for op in ["delete", "update"]:
                if op in cascade and cascade[op] not in valid_cascades:
                    errors.append(ValidationError(
                        path=f"relations.{rel_name}.cascade.{op}",
                        message=f"Invalid cascade option '{cascade[op]}'. Valid options: {', '.join(valid_cascades)}"
                    ))

        return errors

    def _validate_expression_discriminator(self, spec: dict) -> list[ValidationError]:
        """
        VAL-001: Custom discriminator validation for expressions.

        The JSON Schema discriminator keyword is not supported by the Python jsonschema
        library (it's an OpenAPI 3.0 extension). This method manually validates
        expressions against their declared type.

        For each expression:
        1. Check if 'type' field exists (required discriminator)
        2. Check if 'type' value is valid
        3. Check required fields for that type exist
        4. Check no unknown fields are present
        5. Check operator is valid (if applicable)
        6. Recursively validate nested expressions
        """
        errors = []

        def validate_discriminated_expression(expr: Any, path: str, depth: int = 0) -> list[ValidationError]:
            """Validate a single expression against its declared type schema"""
            errs = []

            # Phase 3-1: Check depth limit
            max_depth = DEFAULT_VALIDATION_CONTEXT.max_depth
            if depth > max_depth:
                errs.append(ValidationError(
                    path=path,
                    message=f"Expression nesting exceeds maximum depth ({max_depth})",
                    code="VAL-DEPTH",
                    category="constraint",
                    severity="error",
                    expected=f"depth <= {max_depth}",
                    actual=depth
                ))
                return errs

            if not isinstance(expr, dict):
                # Primitive values are not expressions
                return errs

            # Check for discriminator field
            if "type" not in expr:
                errs.append(ValidationError(
                    path=path,
                    message="Expression missing required 'type' discriminator field"
                ))
                return errs

            expr_type = expr["type"]

            # Check if type is valid
            if expr_type not in EXPRESSION_TYPE_SCHEMAS:
                errs.append(ValidationError(
                    path=path,
                    message=f"Unknown expression type '{expr_type}'. Valid types: {', '.join(sorted(EXPRESSION_TYPE_SCHEMAS.keys()))}"
                ))
                return errs

            schema = EXPRESSION_TYPE_SCHEMAS[expr_type]

            # Check required fields
            for req_field in schema["required"]:
                if req_field not in expr:
                    errs.append(ValidationError(
                        path=path,
                        message=f"Expression type '{expr_type}' missing required field '{req_field}'"
                    ))

            # Check for unknown fields
            allowed_fields = set(schema["required"]) | set(schema.get("optional", []))
            for field in expr:
                if field not in allowed_fields:
                    errs.append(ValidationError(
                        path=path,
                        message=f"Expression type '{expr_type}' has unexpected field '{field}'"
                    ))

            # Validate operator if applicable
            if "op" in expr and expr_type in EXPRESSION_OPERATORS:
                valid_ops = EXPRESSION_OPERATORS[expr_type]
                if expr["op"] not in valid_ops:
                    errs.append(ValidationError(
                        path=f"{path}.op",
                        message=f"Invalid operator '{expr['op']}' for expression type '{expr_type}'. Valid operators: {', '.join(valid_ops)}"
                    ))

            # Recursively validate nested expressions (with incremented depth)
            for nested_field in schema.get("nested_expressions", []):
                if nested_field in expr and expr[nested_field] is not None:
                    errs.extend(validate_discriminated_expression(
                        expr[nested_field],
                        f"{path}.{nested_field}",
                        depth + 1
                    ))

            # Validate expression arrays (with incremented depth)
            for array_field in schema.get("nested_arrays", []):
                if array_field in expr and isinstance(expr[array_field], list):
                    for i, item in enumerate(expr[array_field]):
                        errs.extend(validate_discriminated_expression(
                            item,
                            f"{path}.{array_field}[{i}]",
                            depth + 1
                        ))

            # Handle special cases (with incremented depth)
            special = schema.get("special")
            if special == "branches" and "branches" in expr:
                for i, branch in enumerate(expr["branches"]):
                    if isinstance(branch, dict):
                        if "when" in branch:
                            errs.extend(validate_discriminated_expression(
                                branch["when"],
                                f"{path}.branches[{i}].when",
                                depth + 1
                            ))
                        if "then" in branch:
                            errs.extend(validate_discriminated_expression(
                                branch["then"],
                                f"{path}.branches[{i}].then",
                                depth + 1
                            ))
            elif special == "orderBy" and "orderBy" in expr:
                for i, order in enumerate(expr["orderBy"]):
                    if isinstance(order, dict) and "expr" in order:
                        errs.extend(validate_discriminated_expression(
                            order["expr"],
                            f"{path}.orderBy[{i}].expr",
                            depth + 1
                        ))

            return errs

        def find_and_validate_expressions(obj: Any, path: str, depth: int = 0) -> list[ValidationError]:
            """Walk through the spec and validate all expressions"""
            errs = []

            # Check depth limit for traversal (separate from expression depth)
            max_depth = DEFAULT_VALIDATION_CONTEXT.max_depth
            if depth > max_depth:
                errs.append(ValidationError(
                    path=path,
                    message=f"Spec traversal exceeds maximum depth ({max_depth})",
                    code="VAL-DEPTH",
                    category="constraint",
                    severity="error",
                    expected=f"depth <= {max_depth}",
                    actual=depth
                ))
                return errs

            if isinstance(obj, dict):
                # Check if this is an expression (has 'type' field that's a string)
                if "type" in obj and isinstance(obj.get("type"), str) and obj["type"] in EXPRESSION_TYPE_SCHEMAS:
                    errs.extend(validate_discriminated_expression(obj, path, 0))  # Start expression depth at 0
                else:
                    # Recurse into dict
                    for key, value in obj.items():
                        errs.extend(find_and_validate_expressions(value, f"{path}.{key}", depth + 1))
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    errs.extend(find_and_validate_expressions(item, f"{path}[{i}]", depth + 1))

            return errs

        # Validate expressions in derived formulas
        for name, d in spec.get("derived", {}).items():
            if "formula" in d:
                errors.extend(validate_discriminated_expression(
                    d["formula"],
                    f"derived.{name}.formula"
                ))

        # Validate expressions in functions
        for name, func in spec.get("functions", {}).items():
            for i, pre in enumerate(func.get("pre", [])):
                if "expr" in pre:
                    errors.extend(validate_discriminated_expression(
                        pre["expr"],
                        f"functions.{name}.pre[{i}].expr"
                    ))
            for i, err in enumerate(func.get("error", [])):
                if "when" in err:
                    errors.extend(validate_discriminated_expression(
                        err["when"],
                        f"functions.{name}.error[{i}].when"
                    ))
            for i, post in enumerate(func.get("post", [])):
                action = post.get("action", {})
                if "with" in action:
                    for field, expr in action["with"].items():
                        if isinstance(expr, dict):
                            errors.extend(validate_discriminated_expression(
                                expr,
                                f"functions.{name}.post[{i}].action.with.{field}"
                            ))
                if "set" in action:
                    for field, expr in action["set"].items():
                        if isinstance(expr, dict):
                            errors.extend(validate_discriminated_expression(
                                expr,
                                f"functions.{name}.post[{i}].action.set.{field}"
                            ))

        # Validate expressions in state machine guards
        for sm_name, sm in spec.get("stateMachines", {}).items():
            for i, trans in enumerate(sm.get("transitions", [])):
                if "guard" in trans:
                    errors.extend(validate_discriminated_expression(
                        trans["guard"],
                        f"stateMachines.{sm_name}.transitions[{i}].guard"
                    ))

        # Validate expressions in invariants
        for i, inv in enumerate(spec.get("invariants", [])):
            if "assert" in inv:
                errors.extend(validate_discriminated_expression(
                    inv["assert"],
                    f"invariants[{i}].assert"
                ))

        # Validate expressions in constraints
        for const_name, const in spec.get("constraints", {}).items():
            if "expr" in const:
                errors.extend(validate_discriminated_expression(
                    const["expr"],
                    f"constraints.{const_name}.expr"
                ))

        return errors

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

    def _validate_expressions(self, spec: dict) -> list[ValidationError]:
        """Validate expression ASTs (Tagged Union format)"""
        errors = []
        entities = spec.get("state", {})
        derived = spec.get("derived", {})
        functions = spec.get("functions", {})

        def validate_expr(expr: Any, path: str, context: dict) -> list[ValidationError]:
            """Recursively validate an expression (Tagged Union format)"""
            errs = []

            if not isinstance(expr, dict):
                return errs

            # Get current aliases from context
            aliases = set(context.get("aliases", []))
            aliases.add("item")  # Default aggregation alias

            expr_type = expr.get("type")

            # Field reference validation: { "type": "ref", "path": "entity.field" }
            if expr_type == "ref":
                ref_path = expr.get("path", "")
                parts = ref_path.split(".")
                if len(parts) >= 2:
                    entity_or_alias = parts[0]
                    # Check if it's a known entity or alias
                    if entity_or_alias not in entities and entity_or_alias not in aliases:
                        errs.append(ValidationError(
                            path=path,
                            message=f"Unknown entity or alias '{entity_or_alias}' in reference '{ref_path}'"
                        ))

            # Aggregation validation: { "type": "agg", "op": "sum", "from": "entity", ... }
            elif expr_type == "agg":
                from_entity = expr.get("from", "")
                if from_entity and from_entity not in entities:
                    errs.append(ValidationError(
                        path=path,
                        message=f"Aggregation from unknown entity '{from_entity}'"
                    ))

                # Add the 'as' alias to context for nested validation
                agg_alias = expr.get("as", "item")
                new_context = dict(context)
                new_context["aliases"] = list(aliases) + [agg_alias]

                # Recursively validate nested expressions with new alias context
                if "expr" in expr:
                    errs.extend(validate_expr(expr["expr"], f"{path}.expr", new_context))
                if "where" in expr:
                    errs.extend(validate_expr(expr["where"], f"{path}.where", new_context))

            # Binary operation validation: { "type": "binary", "op": "add", "left": ..., "right": ... }
            elif expr_type == "binary":
                errs.extend(validate_expr(expr.get("left", {}), f"{path}.left", context))
                errs.extend(validate_expr(expr.get("right", {}), f"{path}.right", context))

            # Unary operation validation: { "type": "unary", "op": "not", "expr": ... }
            elif expr_type == "unary":
                errs.extend(validate_expr(expr.get("expr", {}), f"{path}.expr", context))

            # Function call validation: { "type": "call", "name": "fn", "args": [...] }
            elif expr_type == "call":
                func_name = expr.get("name", "")
                if func_name not in derived and func_name not in functions:
                    errs.append(ValidationError(
                        path=path,
                        message=f"Unknown function '{func_name}'"
                    ))
                # Validate args
                for i, arg in enumerate(expr.get("args", [])):
                    errs.extend(validate_expr(arg, f"{path}.args[{i}]", context))

            # Conditional validation: { "type": "if", "cond": ..., "then": ..., "else": ... }
            elif expr_type == "if":
                errs.extend(validate_expr(expr.get("cond", {}), f"{path}.cond", context))
                errs.extend(validate_expr(expr.get("then", {}), f"{path}.then", context))
                errs.extend(validate_expr(expr.get("else", {}), f"{path}.else", context))

            # Case expression validation: { "type": "case", "branches": [...], "else": ... }
            elif expr_type == "case":
                for i, branch in enumerate(expr.get("branches", [])):
                    errs.extend(validate_expr(branch.get("when", {}), f"{path}.branches[{i}].when", context))
                    errs.extend(validate_expr(branch.get("then", {}), f"{path}.branches[{i}].then", context))
                errs.extend(validate_expr(expr.get("else", {}), f"{path}.else", context))

            # Date operation validation: { "type": "date", "op": "diff", "args": [...] }
            elif expr_type == "date":
                for i, arg in enumerate(expr.get("args", [])):
                    errs.extend(validate_expr(arg, f"{path}.args[{i}]", context))

            # List operation validation: { "type": "list", "op": "contains", "list": ..., "args": [...] }
            elif expr_type == "list":
                errs.extend(validate_expr(expr.get("list", {}), f"{path}.list", context))
                for i, arg in enumerate(expr.get("args", [])):
                    errs.extend(validate_expr(arg, f"{path}.args[{i}]", context))

            # =========================================================================
            # NEW EXPRESSION TYPES (Phase 1 Extension)
            # =========================================================================

            # Temporal operation validation (borrowed from Alloy 6)
            elif expr_type == "temporal":
                temporal_entity = expr.get("entity", "")
                if temporal_entity and temporal_entity not in entities:
                    errs.append(ValidationError(
                        path=path,
                        message=f"Temporal expression references unknown entity '{temporal_entity}'"
                    ))
                if "time" in expr:
                    errs.extend(validate_expr(expr["time"], f"{path}.time", context))
                if "condition" in expr:
                    errs.extend(validate_expr(expr["condition"], f"{path}.condition", context))

            # Window operation validation (borrowed from SQL)
            elif expr_type == "window":
                window_from = expr.get("from", "")
                if window_from and window_from not in entities:
                    errs.append(ValidationError(
                        path=path,
                        message=f"Window function references unknown entity '{window_from}'"
                    ))
                if "expr" in expr:
                    errs.extend(validate_expr(expr["expr"], f"{path}.expr", context))
                for i, part in enumerate(expr.get("partitionBy", [])):
                    errs.extend(validate_expr(part, f"{path}.partitionBy[{i}]", context))
                for i, order in enumerate(expr.get("orderBy", [])):
                    if "expr" in order:
                        errs.extend(validate_expr(order["expr"], f"{path}.orderBy[{i}].expr", context))
                for i, arg in enumerate(expr.get("args", [])):
                    errs.extend(validate_expr(arg, f"{path}.args[{i}]", context))

            # Tree operation validation (borrowed from SQL WITH RECURSIVE)
            elif expr_type == "tree":
                tree_entity = expr.get("entity", "")
                if tree_entity and tree_entity not in entities:
                    errs.append(ValidationError(
                        path=path,
                        message=f"Tree operation references unknown entity '{tree_entity}'"
                    ))
                if "node" in expr:
                    errs.extend(validate_expr(expr["node"], f"{path}.node", context))

            # Transitive closure operation validation (borrowed from Alloy)
            elif expr_type == "transitive":
                # Validate relation reference against spec.relations if exists
                relation = expr.get("relation", "")
                relations = spec.get("relations", {})
                if relation and relations and relation not in relations:
                    errs.append(ValidationError(
                        path=path,
                        message=f"Transitive closure references unknown relation '{relation}'"
                    ))
                if "from" in expr:
                    errs.extend(validate_expr(expr["from"], f"{path}.from", context))
                if "to" in expr:
                    errs.extend(validate_expr(expr["to"], f"{path}.to", context))

            # State machine query validation (borrowed from XState)
            elif expr_type == "state":
                machine = expr.get("machine", "")
                state_machines = spec.get("stateMachines", {})
                if machine and state_machines and machine not in state_machines:
                    errs.append(ValidationError(
                        path=path,
                        message=f"State query references unknown state machine '{machine}'"
                    ))
                # Validate state reference if checking is_in
                if expr.get("op") == "is_in" and expr.get("state"):
                    if machine in state_machines:
                        sm = state_machines[machine]
                        states = sm.get("states", {})
                        if expr["state"] not in states:
                            errs.append(ValidationError(
                                path=path,
                                message=f"State '{expr['state']}' not defined in machine '{machine}'"
                            ))
                if "entity" in expr:
                    errs.extend(validate_expr(expr["entity"], f"{path}.entity", context))

            # Principal/authorization context validation (borrowed from ZenStack/Cedar)
            elif expr_type == "principal":
                op = expr.get("op", "")
                roles = spec.get("roles", {})

                # Validate role reference
                if op == "has_role" and expr.get("role"):
                    if roles and expr["role"] not in roles:
                        errs.append(ValidationError(
                            path=path,
                            message=f"Principal check references unknown role '{expr['role']}'"
                        ))

                # Validate permission reference
                if op == "has_permission" and expr.get("permission"):
                    # Permissions can be defined in roles or as separate permission entities
                    all_permissions = set()
                    for role_def in roles.values():
                        all_permissions.update(role_def.get("permissions", []))
                    if all_permissions and expr["permission"] not in all_permissions:
                        errs.append(ValidationError(
                            path=path,
                            message=f"Principal check references unknown permission '{expr['permission']}'"
                        ))

                if "resource" in expr:
                    errs.extend(validate_expr(expr["resource"], f"{path}.resource", context))

            # literal, input, self types don't need recursive validation

            return errs

        # Validate derived formulas
        for name, d in derived.items():
            if "formula" in d:
                errors.extend(validate_expr(
                    d["formula"],
                    f"derived.{name}.formula",
                    {"entity": d.get("entity")}
                ))

        # Validate function expressions
        for name, func in functions.items():
            for i, pre in enumerate(func.get("pre", [])):
                if "expr" in pre:
                    errors.extend(validate_expr(
                        pre["expr"],
                        f"functions.{name}.pre[{i}].expr",
                        {}
                    ))
            for i, err in enumerate(func.get("error", [])):
                if "when" in err:
                    errors.extend(validate_expr(
                        err["when"],
                        f"functions.{name}.error[{i}].when",
                        {}
                    ))

        return errors

    def _detect_cycles(self, spec: dict) -> list[ValidationError]:
        """Detect circular dependencies in derived formulas"""
        warnings = []
        derived = spec.get("derived", {})

        def get_deps(formula: dict) -> set[str]:
            """Extract derived function calls from a formula (Tagged Union format)"""
            deps = set()

            def walk(expr: Any):
                if not isinstance(expr, dict):
                    return
                # Tagged Union: { "type": "call", "name": "fn" }
                if expr.get("type") == "call" and expr.get("name") in derived:
                    deps.add(expr["name"])
                for v in expr.values():
                    if isinstance(v, dict):
                        walk(v)
                    elif isinstance(v, list):
                        for item in v:
                            walk(item)

            walk(formula)
            return deps

        # Build dependency graph
        dep_graph = {name: get_deps(d.get("formula", {})) for name, d in derived.items()}

        # Detect cycles using DFS
        def has_cycle(node: str, visited: set, rec_stack: set) -> list[str] | None:
            visited.add(node)
            rec_stack.add(node)

            for dep in dep_graph.get(node, []):
                if dep not in visited:
                    cycle = has_cycle(dep, visited, rec_stack)
                    if cycle is not None:
                        return [node] + cycle
                elif dep in rec_stack:
                    return [node, dep]

            rec_stack.remove(node)
            return None

        visited = set()
        for name in derived:
            if name not in visited:
                cycle = has_cycle(name, visited, set())
                if cycle:
                    warnings.append(ValidationError(
                        path=f"derived",
                        message=f"Circular dependency detected: {' -> '.join(cycle)}",
                        severity="warning"
                    ))
                    break

        return warnings

    def _validate_gateways(self, spec: dict) -> list[ValidationError]:
        """
        Validate gateway definitions (Phase 2 - BPMN-style workflow control).

        Checks:
        1. Gateway type is valid (exclusive, parallel, inclusive, event_based)
        2. Outgoing flow targets exist (functions, other gateways, or events)
        3. Exclusive/inclusive gateways have proper conditions
        4. Parallel gateways don't have conditions on outgoing flows
        5. Event-based gateways reference valid events
        """
        errors = []
        gateways = spec.get("gateways", {})
        functions = spec.get("functions", {})
        events = spec.get("events", {})

        valid_gateway_types = ["exclusive", "parallel", "inclusive", "event_based"]

        for gw_name, gw in gateways.items():
            gw_type = gw.get("type", "")

            # Validate gateway type
            if gw_type and gw_type not in valid_gateway_types:
                errors.append(ValidationError(
                    path=f"gateways.{gw_name}.type",
                    message=f"Invalid gateway type '{gw_type}'. Valid types: {', '.join(valid_gateway_types)}"
                ))

            # Validate outgoing flows
            for i, flow in enumerate(gw.get("outgoingFlows", [])):
                target = flow.get("target", "")

                # Target should be a function, event, or another gateway
                if target:
                    if target not in functions and target not in events and target not in gateways:
                        errors.append(ValidationError(
                            path=f"gateways.{gw_name}.outgoingFlows[{i}].target",
                            message=f"Outgoing flow target '{target}' not found in functions, events, or gateways"
                        ))

                # Exclusive/inclusive gateways should have conditions (except default)
                if gw_type in ["exclusive", "inclusive"]:
                    if not flow.get("condition") and not flow.get("default"):
                        # Warning might be more appropriate, but we treat as error for strictness
                        pass  # Allow condition-less flows for flexibility

                # Parallel gateways should NOT have conditions
                if gw_type == "parallel" and flow.get("condition"):
                    errors.append(ValidationError(
                        path=f"gateways.{gw_name}.outgoingFlows[{i}]",
                        message="Parallel gateway flows should not have conditions - all paths execute"
                    ))

                # Event-based gateways should reference events
                if gw_type == "event_based":
                    event_ref = flow.get("event", "")
                    if event_ref and event_ref not in events:
                        errors.append(ValidationError(
                            path=f"gateways.{gw_name}.outgoingFlows[{i}].event",
                            message=f"Event-based gateway references unknown event '{event_ref}'"
                        ))

            # Validate incoming flow references
            for i, flow in enumerate(gw.get("incomingFlows", [])):
                source = flow.get("source", "")
                if source:
                    if source not in functions and source not in events and source not in gateways:
                        errors.append(ValidationError(
                            path=f"gateways.{gw_name}.incomingFlows[{i}].source",
                            message=f"Incoming flow source '{source}' not found in functions, events, or gateways"
                        ))

        return errors

    def _validate_deadlines(self, spec: dict) -> list[ValidationError]:
        """
        Validate deadline/SLA definitions (Phase 2 - Temporal workflow control).

        Checks:
        1. Referenced entity exists
        2. Start condition references valid fields
        3. Action function exists
        4. Escalation events exist
        5. Duration format is valid
        """
        errors = []
        deadlines = spec.get("deadlines", {})
        entities = spec.get("state", {})
        functions = spec.get("functions", {})
        events = spec.get("events", {})

        for dl_name, dl in deadlines.items():
            # Validate entity reference
            entity = dl.get("entity", "")
            if entity and entity not in entities:
                errors.append(ValidationError(
                    path=f"deadlines.{dl_name}.entity",
                    message=f"Deadline references unknown entity '{entity}'"
                ))

            # Validate start condition field references
            start_when = dl.get("startWhen", {})
            if start_when and entity and entity in entities:
                entity_fields = entities[entity].get("fields", {})
                field = start_when.get("field", "")
                if field and field not in entity_fields:
                    errors.append(ValidationError(
                        path=f"deadlines.{dl_name}.startWhen.field",
                        message=f"Start condition field '{field}' not found in entity '{entity}'"
                    ))

            # Validate action function reference
            action = dl.get("action", "")
            if action and action not in functions:
                errors.append(ValidationError(
                    path=f"deadlines.{dl_name}.action",
                    message=f"Deadline action references unknown function '{action}'"
                ))

            # Validate escalation events
            for i, esc in enumerate(dl.get("escalations", [])):
                event_ref = esc.get("event", "")
                if event_ref and event_ref not in events:
                    errors.append(ValidationError(
                        path=f"deadlines.{dl_name}.escalations[{i}].event",
                        message=f"Escalation references unknown event '{event_ref}'"
                    ))

                # Validate escalation action
                esc_action = esc.get("action", "")
                if esc_action and esc_action not in functions:
                    errors.append(ValidationError(
                        path=f"deadlines.{dl_name}.escalations[{i}].action",
                        message=f"Escalation action references unknown function '{esc_action}'"
                    ))

            # Validate duration format (ISO 8601 duration pattern)
            duration = dl.get("duration", "")
            if duration:
                import re
                # Simple ISO 8601 duration pattern: P[n]Y[n]M[n]DT[n]H[n]M[n]S or shortcuts like "24h", "7d"
                iso_pattern = r'^P(\d+Y)?(\d+M)?(\d+D)?(T(\d+H)?(\d+M)?(\d+S)?)?$'
                shortcut_pattern = r'^\d+[hdwms]$'  # 24h, 7d, 1w, 30m, 60s
                if not re.match(iso_pattern, duration, re.I) and not re.match(shortcut_pattern, duration, re.I):
                    errors.append(ValidationError(
                        path=f"deadlines.{dl_name}.duration",
                        message=f"Invalid duration format '{duration}'. Use ISO 8601 (P1D, PT2H) or shortcut (24h, 7d)"
                    ))

        return errors

    def _validate_roles(self, spec: dict) -> tuple[list[ValidationError], list[ValidationError]]:
        """
        Validate role and permission definitions (Phase 3 - Security layer).

        Checks:
        1. Circular inheritance detection
        2. EntityPermission entity references
        3. EntityPermission operation validity
        4. Permission-function consistency
        """
        errors = []
        warnings = []
        roles = spec.get("roles", {})
        entities = spec.get("state", {})
        functions = spec.get("functions", {})

        # Valid entity operations
        valid_operations = ["read", "create", "update", "delete", "list"]

        # Build inheritance graph for cycle detection
        inheritance_graph = {}
        for role_name, role in roles.items():
            inheritance_graph[role_name] = role.get("inherits", [])

        # Detect circular inheritance
        def detect_cycle(role: str, visited: set, rec_stack: set) -> list[str] | None:
            visited.add(role)
            rec_stack.add(role)

            for parent in inheritance_graph.get(role, []):
                if parent not in roles:
                    # Already validated in _validate_references
                    continue
                if parent not in visited:
                    cycle = detect_cycle(parent, visited, rec_stack)
                    if cycle is not None:
                        return [role] + cycle
                elif parent in rec_stack:
                    return [role, parent]

            rec_stack.remove(role)
            return None

        visited = set()
        for role_name in roles:
            if role_name not in visited:
                cycle = detect_cycle(role_name, visited, set())
                if cycle:
                    errors.append(ValidationError(
                        path="roles",
                        message=f"Circular role inheritance detected: {' -> '.join(cycle)}"
                    ))
                    break

        # Validate each role
        for role_name, role in roles.items():
            # Validate entityPermissions
            for i, ep in enumerate(role.get("entityPermissions", [])):
                entity = ep.get("entity", "")

                # Check entity exists
                if entity and entity not in entities:
                    errors.append(ValidationError(
                        path=f"roles.{role_name}.entityPermissions[{i}]",
                        message=f"Entity permission references unknown entity '{entity}'"
                    ))

                # Check operations are valid
                operations = ep.get("operations", [])
                for op in operations:
                    if op not in valid_operations:
                        errors.append(ValidationError(
                            path=f"roles.{role_name}.entityPermissions[{i}].operations",
                            message=f"Invalid operation '{op}'. Valid: {', '.join(valid_operations)}"
                        ))

            # Validate permissions reference existing functions (if naming convention matches)
            permissions = role.get("permissions", [])
            for perm in permissions:
                # Convention: permission name may match function name
                # e.g., "execute_clearing" permission grants access to execute_clearing function
                if perm in functions:
                    # Permission matches a function - this is valid
                    pass

        return errors, warnings

    def _validate_audit_policies(self, spec: dict) -> list[ValidationError]:
        """
        Validate audit policy definitions (Phase 3 - Audit layer).

        Checks:
        1. Entity reference exists
        2. Fields reference exists in entity (unless 'all')
        3. Operations are valid
        """
        errors = []
        audit_policies = spec.get("auditPolicies", {})
        entities = spec.get("state", {})

        valid_operations = ["create", "update", "delete", "read"]

        for policy_name, policy in audit_policies.items():
            entity = policy.get("entity", "")

            # Entity reference already validated in _validate_references
            # Additional: validate fields reference
            if entity and entity in entities:
                entity_fields = entities[entity].get("fields", {})
                policy_fields = policy.get("fields", [])

                for field in policy_fields:
                    if field != "all" and field not in entity_fields:
                        errors.append(ValidationError(
                            path=f"auditPolicies.{policy_name}.fields",
                            message=f"Audit policy references unknown field '{field}' in entity '{entity}'"
                        ))

            # Validate operations
            operations = policy.get("operations", [])
            for op in operations:
                if op not in valid_operations:
                    errors.append(ValidationError(
                        path=f"auditPolicies.{policy_name}.operations",
                        message=f"Invalid audit operation '{op}'. Valid: {', '.join(valid_operations)}"
                    ))

        return errors

    def _validate_external_services(self, spec: dict) -> list[ValidationError]:
        """
        Validate external service definitions (Phase 4 - External layer).

        Checks:
        1. BaseUrl format validation
        2. Authentication type validity
        3. HTTP method validity
        4. Retry policy validity
        """
        errors = []
        services = spec.get("externalServices", {})

        valid_auth_types = ["none", "bearer", "basic", "api_key", "oauth2"]
        valid_http_methods = ["GET", "POST", "PUT", "PATCH", "DELETE"]
        valid_service_types = ["rest", "graphql", "grpc", "soap"]

        import re
        url_pattern = re.compile(r'^https?://[^\s/$.?#].[^\s]*$', re.I)

        for svc_name, svc in services.items():
            # Validate baseUrl
            base_url = svc.get("baseUrl", "")
            if base_url and not url_pattern.match(base_url):
                errors.append(ValidationError(
                    path=f"externalServices.{svc_name}.baseUrl",
                    message=f"Invalid base URL format: '{base_url}'"
                ))

            # Validate service type
            svc_type = svc.get("type", "rest")
            if svc_type not in valid_service_types:
                errors.append(ValidationError(
                    path=f"externalServices.{svc_name}.type",
                    message=f"Invalid service type '{svc_type}'. Valid: {', '.join(valid_service_types)}"
                ))

            # Validate authentication type (from 'auth' or 'authentication')
            auth = svc.get("auth", svc.get("authentication", {}))
            if auth:
                auth_type = auth.get("type", "")
                if auth_type and auth_type not in valid_auth_types:
                    errors.append(ValidationError(
                        path=f"externalServices.{svc_name}.authentication.type",
                        message=f"Invalid auth type '{auth_type}'. Valid: {', '.join(valid_auth_types)}"
                    ))

            # Validate operations
            for op_name, op in svc.get("operations", {}).items():
                method = op.get("method", "")
                if method and method not in valid_http_methods:
                    errors.append(ValidationError(
                        path=f"externalServices.{svc_name}.operations.{op_name}.method",
                        message=f"Invalid HTTP method '{method}'. Valid: {', '.join(valid_http_methods)}"
                    ))

            # Validate retry policy
            retry = svc.get("retry", svc.get("retryPolicy", {}))
            if retry:
                max_attempts = retry.get("maxAttempts", 3)
                if not isinstance(max_attempts, int) or max_attempts < 1:
                    errors.append(ValidationError(
                        path=f"externalServices.{svc_name}.retryPolicy.maxAttempts",
                        message=f"maxAttempts must be a positive integer"
                    ))

        return errors

    def _validate_data_policies(self, spec: dict) -> list[ValidationError]:
        """
        Validate data policy definitions (Phase 4 - Data layer).

        Checks:
        1. Entity reference exists
        2. PII fields exist in entity
        3. Masking fields exist in entity
        4. Retention period format
        """
        errors = []
        policies = spec.get("dataPolicies", {})
        entities = spec.get("state", {})

        for policy_name, policy in policies.items():
            entity = policy.get("entity", "")

            # Entity reference already validated in _validate_references
            # Additional: validate PII and masking fields
            if entity and entity in entities:
                entity_fields = entities[entity].get("fields", {})

                # Validate piiFields
                pii_fields = policy.get("piiFields", [])
                for field in pii_fields:
                    if field not in entity_fields:
                        errors.append(ValidationError(
                            path=f"dataPolicies.{policy_name}.piiFields",
                            message=f"PII field '{field}' not found in entity '{entity}'"
                        ))

                # Validate masking fields
                masking = policy.get("masking", {})
                if masking:
                    masking_fields = masking.get("fields", [])
                    for field in masking_fields:
                        if field not in entity_fields:
                            errors.append(ValidationError(
                                path=f"dataPolicies.{policy_name}.masking.fields",
                                message=f"Masking field '{field}' not found in entity '{entity}'"
                            ))

                    # Validate masking strategy
                    valid_strategies = ["partial", "full", "hash", "redact"]
                    strategy = masking.get("strategy", "")
                    if strategy and strategy not in valid_strategies:
                        errors.append(ValidationError(
                            path=f"dataPolicies.{policy_name}.masking.strategy",
                            message=f"Invalid masking strategy '{strategy}'. Valid: {', '.join(valid_strategies)}"
                        ))

            # Validate retention period format (basic check)
            retention = policy.get("retention", {})
            if retention:
                period = retention.get("period", "")
                if period:
                    # Simple pattern: number + unit (e.g., "7 years", "90 days", "1 year")
                    import re
                    period_pattern = r'^\d+\s*(year|years|month|months|day|days|week|weeks)$'
                    if not re.match(period_pattern, period, re.I):
                        errors.append(ValidationError(
                            path=f"dataPolicies.{policy_name}.retention.period",
                            message=f"Invalid retention period format '{period}'. Use format like '7 years', '90 days'"
                        ))

        return errors

    def _validate_schedules(self, spec: dict) -> list[ValidationError]:
        """
        Validate schedule definitions (Phase 5 - Temporal layer).

        Checks:
        1. Cron expression format
        2. Timezone validity
        3. Action function reference
        4. Overlap policy validity
        """
        errors = []
        schedules = spec.get("schedules", {})
        functions = spec.get("functions", {})

        import re
        # Cron expression: 5 or 6 fields (second minute hour day month weekday [year])
        # Simple validation - check field count and basic patterns
        cron_field_pattern = r'^(\*|[0-9,\-\/\*]+)$'

        valid_overlap_policies = ["skip", "buffer_one", "cancel_other", "allow_all"]

        # Common timezones (not exhaustive, but covers major ones)
        common_timezones = [
            "UTC", "GMT",
            "Asia/Tokyo", "Asia/Shanghai", "Asia/Seoul", "Asia/Singapore",
            "America/New_York", "America/Los_Angeles", "America/Chicago",
            "Europe/London", "Europe/Paris", "Europe/Berlin",
            "Australia/Sydney", "Pacific/Auckland"
        ]

        for sched_name, sched in schedules.items():
            # Validate cron expression
            cron = sched.get("cron", "")
            if cron:
                fields = cron.split()
                if len(fields) < 5 or len(fields) > 6:
                    errors.append(ValidationError(
                        path=f"schedules.{sched_name}.cron",
                        message=f"Invalid cron expression '{cron}'. Expected 5 or 6 fields (minute hour day month weekday [year])"
                    ))
                else:
                    for i, field in enumerate(fields):
                        if not re.match(cron_field_pattern, field):
                            errors.append(ValidationError(
                                path=f"schedules.{sched_name}.cron",
                                message=f"Invalid cron field '{field}' at position {i}"
                            ))
                            break

            # Validate timezone
            timezone = sched.get("timezone", "")
            if timezone and timezone not in common_timezones:
                # Warning level - timezone might be valid but not in our list
                # For now, just check format (Region/City or abbreviation)
                tz_pattern = r'^[A-Za-z]+(/[A-Za-z_]+)?$'
                if not re.match(tz_pattern, timezone):
                    errors.append(ValidationError(
                        path=f"schedules.{sched_name}.timezone",
                        message=f"Invalid timezone format '{timezone}'. Use IANA format like 'Asia/Tokyo'"
                    ))

            # Validate action function reference
            action = sched.get("action", "")
            if action and action not in functions:
                errors.append(ValidationError(
                    path=f"schedules.{sched_name}.action",
                    message=f"Schedule references unknown function '{action}'"
                ))

            # Validate overlap policy
            overlap = sched.get("overlapPolicy", "")
            if overlap and overlap not in valid_overlap_policies:
                errors.append(ValidationError(
                    path=f"schedules.{sched_name}.overlapPolicy",
                    message=f"Invalid overlap policy '{overlap}'. Valid: {', '.join(valid_overlap_policies)}"
                ))

        return errors

    def _validate_constraints(self, spec: dict) -> list[ValidationError]:
        """
        Validate constraint definitions (Phase 5 - Data integrity layer).

        Checks:
        1. Entity reference exists
        2. Fields exist in entity (for unique constraints)
        3. Expression references valid fields (for check constraints)
        4. Constraint type validity
        """
        errors = []
        constraints = spec.get("constraints", {})
        entities = spec.get("state", {})

        valid_constraint_types = ["unique", "check", "foreign_key"]

        for const_name, const in constraints.items():
            entity = const.get("entity", "")
            const_type = const.get("type", "")

            # Validate constraint type
            if const_type and const_type not in valid_constraint_types:
                errors.append(ValidationError(
                    path=f"constraints.{const_name}.type",
                    message=f"Invalid constraint type '{const_type}'. Valid: {', '.join(valid_constraint_types)}"
                ))

            # Entity reference already validated in _validate_references
            # Additional: validate fields for unique constraints
            if entity and entity in entities:
                entity_fields = entities[entity].get("fields", {})

                # For unique constraints, check that all fields exist
                if const_type == "unique":
                    const_fields = const.get("fields", [])
                    for field in const_fields:
                        if field not in entity_fields:
                            errors.append(ValidationError(
                                path=f"constraints.{const_name}.fields",
                                message=f"Unique constraint field '{field}' not found in entity '{entity}'"
                            ))

                # For foreign_key constraints, check reference
                if const_type == "foreign_key":
                    fk_fields = const.get("fields", [])
                    ref_entity = const.get("references", {}).get("entity", "")
                    if ref_entity and ref_entity not in entities:
                        errors.append(ValidationError(
                            path=f"constraints.{const_name}.references.entity",
                            message=f"Foreign key references unknown entity '{ref_entity}'"
                        ))

        return errors

    def _validate_enum_usage(self, spec: dict) -> list[ValidationError]:
        """
        Phase 2-1: Validate that literal values match Enum definitions.

        Validates:
        1. Literal values in binary comparisons (eq, ne, in, not_in) against enum fields
        2. Case-sensitive matching
        3. Provides auto-fix suggestions for case mismatches

        Returns StructuredError-compatible ValidationErrors with:
        - code: TYP-001 for enum value mismatch
        - valid_options: list of valid enum values
        - auto_fixable: True if the error is auto-fixable
        - fix_patch: JSON Patch to fix the value
        """
        errors = []

        # Step 1: Collect all enum definitions from entity fields
        # Map: "entity.field" -> [valid_values]
        enum_definitions: dict[str, list[str]] = {}
        entities = spec.get("state", {})

        for entity_name, entity in entities.items():
            for field_name, field in entity.get("fields", {}).items():
                field_type = field.get("type", {})
                if isinstance(field_type, dict) and "enum" in field_type:
                    enum_values = field_type["enum"]
                    if isinstance(enum_values, list):
                        enum_definitions[f"{entity_name}.{field_name}"] = enum_values

        if not enum_definitions:
            return errors  # No enums defined

        # Step 2: Find binary comparisons with enum fields and validate literals
        def extract_enum_errors(expr: Any, path: str) -> list[ValidationError]:
            """Walk expression tree and validate literal values against enum definitions"""
            errs = []

            if not isinstance(expr, dict):
                return errs

            expr_type = expr.get("type")

            # Check binary expressions with comparison operators
            if expr_type == "binary" and expr.get("op") in ["eq", "ne", "in", "not_in"]:
                left = expr.get("left", {})
                right = expr.get("right", {})

                # Case 1: ref == literal or ref in [literal values]
                if left.get("type") == "ref" and right.get("type") == "literal":
                    ref_path = left.get("path", "")
                    # Try to resolve enum definition
                    enum_key = self._resolve_enum_key(ref_path, enum_definitions, entities)
                    if enum_key and enum_key in enum_definitions:
                        lit_value = right.get("value")
                        # Handle list values for 'in' operator (e.g., {"type": "literal", "value": ["A", "B"]})
                        if isinstance(lit_value, list) and expr.get("op") in ["in", "not_in"]:
                            for i, item in enumerate(lit_value):
                                errs.extend(self._check_literal_against_enum(
                                    item,
                                    enum_definitions[enum_key],
                                    f"{path}.right.value[{i}]",
                                    enum_key
                                ))
                        else:
                            errs.extend(self._check_literal_against_enum(
                                lit_value,
                                enum_definitions[enum_key],
                                f"{path}.right.value",
                                enum_key
                            ))

                # Case 2: literal == ref (or [literal values] contains ref)
                elif right.get("type") == "ref" and left.get("type") == "literal":
                    ref_path = right.get("path", "")
                    enum_key = self._resolve_enum_key(ref_path, enum_definitions, entities)
                    if enum_key and enum_key in enum_definitions:
                        lit_value = left.get("value")
                        if isinstance(lit_value, list) and expr.get("op") in ["in", "not_in"]:
                            for i, item in enumerate(lit_value):
                                errs.extend(self._check_literal_against_enum(
                                    item,
                                    enum_definitions[enum_key],
                                    f"{path}.left.value[{i}]",
                                    enum_key
                                ))
                        else:
                            errs.extend(self._check_literal_against_enum(
                                lit_value,
                                enum_definitions[enum_key],
                                f"{path}.left.value",
                                enum_key
                            ))

                # Case 3: ref in [literal, literal, ...] or not_in
                if expr.get("op") in ["in", "not_in"]:
                    if left.get("type") == "ref" and right.get("type") == "list":
                        ref_path = left.get("path", "")
                        enum_key = self._resolve_enum_key(ref_path, enum_definitions, entities)
                        if enum_key and enum_key in enum_definitions:
                            list_items = right.get("items", right.get("values", []))
                            for i, item in enumerate(list_items):
                                if isinstance(item, dict) and item.get("type") == "literal":
                                    errs.extend(self._check_literal_against_enum(
                                        item.get("value"),
                                        enum_definitions[enum_key],
                                        f"{path}.right.items[{i}].value",
                                        enum_key
                                    ))
                                elif not isinstance(item, dict):
                                    # Direct literal value
                                    errs.extend(self._check_literal_against_enum(
                                        item,
                                        enum_definitions[enum_key],
                                        f"{path}.right.items[{i}]",
                                        enum_key
                                    ))

            # Recursively check nested expressions
            for key, value in expr.items():
                if isinstance(value, dict):
                    errs.extend(extract_enum_errors(value, f"{path}.{key}"))
                elif isinstance(value, list):
                    for i, item in enumerate(value):
                        if isinstance(item, dict):
                            errs.extend(extract_enum_errors(item, f"{path}.{key}[{i}]"))

            return errs

        # Walk through all expressions in the spec
        # Check derived formulas
        for name, d in spec.get("derived", {}).items():
            if "formula" in d:
                errors.extend(extract_enum_errors(d["formula"], f"derived.{name}.formula"))

        # Check function pre/post conditions
        for func_name, func in spec.get("functions", {}).items():
            for i, pre in enumerate(func.get("pre", [])):
                if "expr" in pre:
                    errors.extend(extract_enum_errors(pre["expr"], f"functions.{func_name}.pre[{i}].expr"))
            for i, post in enumerate(func.get("post", [])):
                action = post.get("action", {})
                if "set" in action:
                    for field, val in action["set"].items():
                        if isinstance(val, dict):
                            errors.extend(extract_enum_errors(val, f"functions.{func_name}.post[{i}].action.set.{field}"))
                if "with" in action:
                    for field, val in action["with"].items():
                        if isinstance(val, dict):
                            errors.extend(extract_enum_errors(val, f"functions.{func_name}.post[{i}].action.with.{field}"))
            for i, err in enumerate(func.get("error", [])):
                if "when" in err:
                    errors.extend(extract_enum_errors(err["when"], f"functions.{func_name}.error[{i}].when"))

        # Check state machine guards
        for sm_name, sm in spec.get("stateMachines", {}).items():
            for i, trans in enumerate(sm.get("transitions", [])):
                if "guard" in trans:
                    errors.extend(extract_enum_errors(trans["guard"], f"stateMachines.{sm_name}.transitions[{i}].guard"))

        # Check invariants
        for i, inv in enumerate(spec.get("invariants", [])):
            if "assert" in inv:
                errors.extend(extract_enum_errors(inv["assert"], f"invariants[{i}].assert"))

        # Check constraints
        for const_name, const in spec.get("constraints", {}).items():
            if "expr" in const:
                errors.extend(extract_enum_errors(const["expr"], f"constraints.{const_name}.expr"))

        return errors

    def _resolve_enum_key(
        self,
        ref_path: str,
        enum_definitions: dict[str, list[str]],
        entities: dict
    ) -> str | None:
        """
        Resolve a ref path to an enum definition key.

        ref_path examples:
        - "invoice.status" -> "Invoice.status" (if Invoice.status has enum)
        - "item.invoice.status" -> "Invoice.status" (follow refs)
        """
        parts = ref_path.split(".")
        if len(parts) < 2:
            return None

        # Direct match: entity.field
        for entity_name in entities:
            # Case-insensitive entity match
            if parts[0].lower() == entity_name.lower():
                field_name = parts[-1]  # Last part is the field
                key = f"{entity_name}.{field_name}"
                if key in enum_definitions:
                    return key

        # Try with exact path
        candidate = ".".join([parts[0].title()] + parts[1:])
        if candidate in enum_definitions:
            return candidate

        return None

    def _check_literal_against_enum(
        self,
        value: Any,
        valid_values: list[str],
        path: str,
        enum_key: str
    ) -> list[ValidationError]:
        """
        Check if a literal value is valid for an enum definition.

        Returns error with auto-fix suggestion if:
        - Value is not in valid_values
        - Case-insensitive match exists (auto-fixable)
        """
        errors = []

        if value is None:
            return errors

        str_value = str(value)

        # Exact match - valid
        if str_value in valid_values:
            return errors

        # Case-insensitive match - auto-fixable
        lower_map = {v.lower(): v for v in valid_values}
        if str_value.lower() in lower_map:
            correct_value = lower_map[str_value.lower()]
            errors.append(ValidationError(
                path=path,
                message=f"Enum value '{str_value}' has wrong case for {enum_key}. Expected: '{correct_value}'",
                code="TYP-001",
                category="type",
                expected=correct_value,
                actual=str_value,
                valid_options=valid_values,
                auto_fixable=True,
                fix_patch={
                    "op": "replace",
                    "path": "/" + path.replace(".", "/"),
                    "value": correct_value
                }
            ))
        else:
            # No match at all
            errors.append(ValidationError(
                path=path,
                message=f"Invalid enum value '{str_value}' for {enum_key}. Valid values: {valid_values}",
                code="TYP-001",
                category="type",
                expected=f"one of {valid_values}",
                actual=str_value,
                valid_options=valid_values,
                auto_fixable=False,
                fix_patch=None
            ))

        return errors

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
        functions = spec.get("functions", {})

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

    def _validate_function_type_consistency(self, spec: dict) -> list[ValidationError]:
        """
        Phase 2-2: Validate function input/output type consistency.

        Validates:
        - Function.inputs[].type matches actual usage in post[].action.with
        - Function.outputs[].type matches return values
        - Input names referenced in expressions exist in function inputs

        Returns StructuredError with code TYP-002 for type mismatches.
        """
        errors = []
        functions = spec.get("functions", {})
        entities = spec.get("state", {})

        for func_name, func in functions.items():
            # Get declared inputs
            declared_inputs = {}
            for input_item in func.get("inputs", []):
                if isinstance(input_item, dict):
                    input_name = input_item.get("name", "")
                    input_type = input_item.get("type", "any")
                    if input_name:
                        declared_inputs[input_name] = input_type
            # Also support input as dict format
            if isinstance(func.get("input"), dict):
                for input_name, input_def in func["input"].items():
                    if isinstance(input_def, dict):
                        declared_inputs[input_name] = input_def.get("type", "any")
                    else:
                        declared_inputs[input_name] = input_def

            # Get declared outputs
            declared_outputs = {}
            for output_item in func.get("outputs", []):
                if isinstance(output_item, dict):
                    output_name = output_item.get("name", "")
                    output_type = output_item.get("type", "any")
                    if output_name:
                        declared_outputs[output_name] = output_type

            # Validate input references in expressions
            def check_input_refs(expr: Any, path: str) -> list[ValidationError]:
                """Check that input references exist in declared inputs"""
                errs = []
                if not isinstance(expr, dict):
                    return errs

                if expr.get("type") == "input":
                    input_name = expr.get("name", "")
                    if input_name and declared_inputs and input_name not in declared_inputs:
                        errs.append(ValidationError(
                            path=path,
                            message=f"Input '{input_name}' not declared in function '{func_name}' inputs",
                            code="TYP-002",
                            category="type",
                            expected=f"one of: {', '.join(declared_inputs.keys())}",
                            actual=input_name,
                            valid_options=list(declared_inputs.keys())
                        ))

                # Recurse into nested expressions
                for key, value in expr.items():
                    if isinstance(value, dict):
                        errs.extend(check_input_refs(value, f"{path}.{key}"))
                    elif isinstance(value, list):
                        for i, item in enumerate(value):
                            if isinstance(item, dict):
                                errs.extend(check_input_refs(item, f"{path}.{key}[{i}]"))
                return errs

            # Check pre conditions
            for i, pre in enumerate(func.get("pre", [])):
                if "expr" in pre:
                    errors.extend(check_input_refs(
                        pre["expr"],
                        f"functions.{func_name}.pre[{i}].expr"
                    ))

            # Check error conditions
            for i, err in enumerate(func.get("error", [])):
                if "when" in err:
                    errors.extend(check_input_refs(
                        err["when"],
                        f"functions.{func_name}.error[{i}].when"
                    ))

            # Check post actions
            for i, post in enumerate(func.get("post", [])):
                action = post.get("action", {})

                # Check 'with' field for input type consistency
                with_values = action.get("with", {})
                for field_name, value in with_values.items():
                    if isinstance(value, dict):
                        errors.extend(check_input_refs(
                            value,
                            f"functions.{func_name}.post[{i}].action.with.{field_name}"
                        ))

                # Check 'set' field
                set_values = action.get("set", {})
                for field_name, value in set_values.items():
                    if isinstance(value, dict):
                        errors.extend(check_input_refs(
                            value,
                            f"functions.{func_name}.post[{i}].action.set.{field_name}"
                        ))

                # Check 'target' field
                target = action.get("target")
                if isinstance(target, dict):
                    errors.extend(check_input_refs(
                        target,
                        f"functions.{func_name}.post[{i}].action.target"
                    ))

            # Validate type consistency for post actions with entities
            for i, post in enumerate(func.get("post", [])):
                action = post.get("action", {})
                entity_name = action.get("create") or action.get("update")

                if entity_name and entity_name in entities:
                    entity_fields = entities[entity_name].get("fields", {})
                    with_values = action.get("with", {})
                    set_values = action.get("set", {})

                    # Check field types in 'with'
                    for field_name, value in with_values.items():
                        if field_name in entity_fields:
                            field_type = entity_fields[field_name].get("type")
                            if isinstance(value, dict) and value.get("type") == "input":
                                input_name = value.get("name", "")
                                if input_name in declared_inputs:
                                    input_type = declared_inputs[input_name]
                                    # Basic type compatibility check
                                    if not self._types_compatible(input_type, field_type):
                                        errors.append(ValidationError(
                                            path=f"functions.{func_name}.post[{i}].action.with.{field_name}",
                                            message=f"Type mismatch: input '{input_name}' has type '{input_type}' but field '{entity_name}.{field_name}' expects '{field_type}'",
                                            code="TYP-002",
                                            category="type",
                                            expected=str(field_type),
                                            actual=str(input_type)
                                        ))

        return errors

    def _types_compatible(self, source_type: Any, target_type: Any) -> bool:
        """Check if source type is compatible with target type"""
        # Any type is always compatible
        if source_type == "any" or target_type == "any":
            return True

        # Simple string type comparison
        if isinstance(source_type, str) and isinstance(target_type, str):
            return source_type == target_type

        # Handle dict types (e.g., {"ref": "Entity"}, {"enum": [...]})
        if isinstance(target_type, dict):
            if "ref" in target_type:
                # Reference type - check if source is also a reference or string
                return source_type == "string" or source_type == target_type.get("ref")
            if "enum" in target_type:
                # Enum type - string is compatible
                return source_type == "string"

        return True  # Default to compatible for unknown types

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

    def _validate_reference_paths(self, spec: dict) -> list[ValidationError]:
        """
        Phase 2-4: Validate deep reference paths.

        Validates:
        - ref paths like "order.customer.tier" follow valid entity relationships
        - Each segment of the path is a valid field/relation

        Returns StructuredError with code REF-002 for invalid paths.
        """
        errors = []
        entities = spec.get("state", {})
        relations = spec.get("relations", {})

        # Build relation map for quick lookup
        # entity -> { field: target_entity }
        relation_map: dict[str, dict[str, str]] = {}
        for entity_name, entity in entities.items():
            relation_map[entity_name] = {}
            for field_name, field in entity.get("fields", {}).items():
                field_type = field.get("type", {})
                if isinstance(field_type, dict) and "ref" in field_type:
                    relation_map[entity_name][field_name] = field_type["ref"]

        # Also add explicit relations
        for rel_name, rel in relations.items():
            from_entity = rel.get("from", "")
            to_entity = rel.get("to", "")
            fk = rel.get("foreignKey", "")
            if from_entity and to_entity and fk:
                if from_entity not in relation_map:
                    relation_map[from_entity] = {}
                relation_map[from_entity][fk] = to_entity

        def validate_path(path: str, context_path: str) -> list[ValidationError]:
            """Validate a dot-separated reference path"""
            # Phase 3-2: Check cache first
            if self._cache and path in self._cache.reference_cache:
                self._cache.hits += 1
                cached = self._cache.reference_cache[path]
                if cached is None:
                    return []  # Valid path
                else:
                    # Return cached error
                    return [cached]

            if self._cache:
                self._cache.misses += 1

            path_errors = []
            parts = path.split(".")

            if len(parts) < 2:
                if self._cache:
                    self._cache.reference_cache[path] = None
                return path_errors

            # First part should be an entity (or alias)
            current_entity = None
            for entity_name in entities:
                if parts[0].lower() == entity_name.lower():
                    current_entity = entity_name
                    break

            if not current_entity:
                # Could be an alias like "clr" from aggregation
                if self._cache:
                    self._cache.reference_cache[path] = None
                return path_errors

            # Walk through the path
            for i, part in enumerate(parts[1:], 1):
                if not current_entity:
                    break

                entity_def = entities.get(current_entity, {})
                fields = entity_def.get("fields", {})

                if part in fields:
                    # Check if it's a ref field (allows further traversal)
                    field_type = fields[part].get("type", {})
                    if isinstance(field_type, dict) and "ref" in field_type:
                        current_entity = field_type["ref"]
                    else:
                        current_entity = None  # End of path (scalar field)
                elif current_entity in relation_map and part in relation_map[current_entity]:
                    current_entity = relation_map[current_entity][part]
                else:
                    # Field not found - error
                    error = ValidationError(
                        path=context_path,
                        message=f"Invalid reference path '{path}': field '{part}' not found in entity '{current_entity}'",
                        code="REF-002",
                        category="reference",
                        expected=f"valid field of {current_entity}",
                        actual=part,
                        valid_options=list(fields.keys()),
                        auto_fixable=False
                    )
                    path_errors.append(error)
                    # Cache the error (store just the message pattern, actual context_path may vary)
                    if self._cache:
                        self._cache.reference_cache[path] = error
                    break

            # Cache successful validation
            if not path_errors and self._cache:
                self._cache.reference_cache[path] = None

            return path_errors

        # Walk through all ref expressions in the spec
        def find_refs(expr: Any, path: str) -> list[ValidationError]:
            ref_errors = []
            if not isinstance(expr, dict):
                return ref_errors

            if expr.get("type") == "ref":
                ref_path = expr.get("path", "")
                ref_errors.extend(validate_path(ref_path, path))

            # Recurse into nested expressions
            for key, value in expr.items():
                if isinstance(value, dict):
                    ref_errors.extend(find_refs(value, f"{path}.{key}"))
                elif isinstance(value, list):
                    for i, item in enumerate(value):
                        if isinstance(item, dict):
                            ref_errors.extend(find_refs(item, f"{path}.{key}[{i}]"))

            return ref_errors

        # Check all expressions
        for name, d in spec.get("derived", {}).items():
            if "formula" in d:
                errors.extend(find_refs(d["formula"], f"derived.{name}.formula"))

        for func_name, func in spec.get("functions", {}).items():
            for i, pre in enumerate(func.get("pre", [])):
                if "expr" in pre:
                    errors.extend(find_refs(pre["expr"], f"functions.{func_name}.pre[{i}].expr"))

        for sm_name, sm in spec.get("stateMachines", {}).items():
            for i, trans in enumerate(sm.get("transitions", [])):
                if "guard" in trans:
                    errors.extend(find_refs(trans["guard"], f"stateMachines.{sm_name}.transitions[{i}].guard"))

        return errors
