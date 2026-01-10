"""Mesh JSON Schema Validator"""

import json
from pathlib import Path
from typing import Any, Literal

try:
    import jsonschema
    from jsonschema import Draft202012Validator, RefResolver
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False

# Import from split modules
from the_mesh.core.errors import StructuredError, ValidationError, ValidationResult
from the_mesh.core.cache import ValidationCache, ValidationContext, DEFAULT_VALIDATION_CONTEXT
from the_mesh.core.domain import (
    StateMachineValidationMixin,
    SagaValidationMixin,
    PolicyValidationMixin,
    MiscValidationMixin,
)
from the_mesh.generators.constraint_inference import (
    infer_preset_from_field_name,
    PRESETS,
)


# Error code prefixes
# SCH-xxx: Schema violations
# REF-xxx: Reference errors
# TYP-xxx: Type errors
# VAL-xxx: Validation errors
# FSM-xxx: State machine errors
# LGC-xxx: Logic errors
# CNS-xxx: Constraint errors


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



class MeshValidator(
    StateMachineValidationMixin,
    SagaValidationMixin,
    PolicyValidationMixin,
    MiscValidationMixin,
):
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

        # 19. Frontend view validation (FE-002, FE-003)
        view_errors = self._validate_views(spec)
        errors.extend(view_errors)

        # 20. Frontend route validation (FE-004)
        route_errors = self._validate_routes(spec)
        errors.extend(route_errors)

        # 21. Unused function warning (FE-005)
        unused_warnings = self._detect_unused_functions(spec)
        warnings.extend(unused_warnings)

        # 22. Field constraint validation (CNS-001~005)
        constraint_errors = self._validate_field_constraints(spec)
        errors.extend(constraint_errors)

        # 23. Constraint inference warnings (CNS-006)
        inference_warnings = self._generate_constraint_inference_warnings(spec)
        warnings.extend(inference_warnings)

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

    def _validate_views(self, spec: dict) -> list[ValidationError]:
        """
        FE-002, FE-003: Validate view definitions.

        Validates:
        - FE-002: View.entity references a valid entity
        - FE-002: View.fields[].name references a valid field in the entity
        - FE-003: View.actions[].function references a valid function

        Returns StructuredError with codes FE-002 or FE-003.
        """
        errors = []
        entities = set(spec.get("state", {}).keys())
        functions = set(spec.get("functions", {}).keys())
        views = spec.get("views", {})

        for view_name, view in views.items():
            # FE-002: Validate entity reference
            entity_name = view.get("entity", "")
            if entity_name and entity_name not in entities:
                errors.append(ValidationError(
                    path=f"views.{view_name}.entity",
                    message=f"View '{view_name}' references unknown entity '{entity_name}'",
                    code="FE-002",
                    category="reference",
                    expected=list(entities)[:10] if entities else [],
                    actual=entity_name
                ))
                continue  # Skip field validation if entity is invalid

            # FE-002: Validate field references
            entity_fields = set()
            if entity_name and entity_name in spec.get("state", {}):
                entity_fields = set(spec["state"][entity_name].get("fields", {}).keys())

            for i, field in enumerate(view.get("fields", [])):
                field_name = field.get("name", "") if isinstance(field, dict) else field
                if field_name and entity_fields and field_name not in entity_fields:
                    errors.append(ValidationError(
                        path=f"views.{view_name}.fields[{i}].name",
                        message=f"View field '{field_name}' not found in entity '{entity_name}'",
                        code="FE-002",
                        category="reference",
                        expected=list(entity_fields)[:10],
                        actual=field_name
                    ))

            # FE-003: Validate action function references
            for i, action in enumerate(view.get("actions", [])):
                func_name = action.get("function", "")
                if func_name and func_name not in functions:
                    errors.append(ValidationError(
                        path=f"views.{view_name}.actions[{i}].function",
                        message=f"View action '{action.get('name', '')}' references unknown function '{func_name}'",
                        code="FE-003",
                        category="reference",
                        expected=list(functions)[:10] if functions else [],
                        actual=func_name
                    ))

            # FE-002: Validate filter field references
            for i, filter_def in enumerate(view.get("filters", [])):
                filter_field = filter_def.get("field", "")
                if filter_field and entity_fields and filter_field not in entity_fields:
                    errors.append(ValidationError(
                        path=f"views.{view_name}.filters[{i}].field",
                        message=f"View filter field '{filter_field}' not found in entity '{entity_name}'",
                        code="FE-002",
                        category="reference",
                        expected=list(entity_fields)[:10],
                        actual=filter_field
                    ))

            # FE-002: Validate default sort field
            default_sort = view.get("defaultSort", {})
            sort_field = default_sort.get("field", "")
            if sort_field and entity_fields and sort_field not in entity_fields:
                errors.append(ValidationError(
                    path=f"views.{view_name}.defaultSort.field",
                    message=f"Default sort field '{sort_field}' not found in entity '{entity_name}'",
                    code="FE-002",
                    category="reference",
                    expected=list(entity_fields)[:10],
                    actual=sort_field
                ))

        return errors

    def _validate_routes(self, spec: dict) -> list[ValidationError]:
        """
        FE-004: Validate route definitions.

        Validates:
        - FE-004: Route.view references a valid view
        - Route.guards[].role references a valid role (if type is 'role')
        - Route.guards[].permission references a valid permission (if type is 'permission')

        Returns StructuredError with code FE-004.
        """
        errors = []
        views = set(spec.get("views", {}).keys())
        roles = set(spec.get("roles", {}).keys())
        routes = spec.get("routes", {})

        # Collect all permissions from roles
        all_permissions = set()
        for role_def in spec.get("roles", {}).values():
            perms = role_def.get("permissions", [])
            if isinstance(perms, list):
                for perm in perms:
                    if isinstance(perm, str):
                        all_permissions.add(perm)
                    elif isinstance(perm, dict):
                        all_permissions.add(perm.get("name", ""))

        for route_path, route in routes.items():
            # FE-004: Validate view reference
            view_name = route.get("view", "")
            if view_name and view_name not in views:
                errors.append(ValidationError(
                    path=f"routes.{route_path}.view",
                    message=f"Route '{route_path}' references unknown view '{view_name}'",
                    code="FE-004",
                    category="reference",
                    expected=list(views)[:10] if views else [],
                    actual=view_name
                ))

            # Validate route guards
            for i, guard in enumerate(route.get("guards", [])):
                guard_type = guard.get("type", "")

                # Validate role reference
                if guard_type == "role":
                    role_name = guard.get("role", "")
                    if role_name and roles and role_name not in roles:
                        errors.append(ValidationError(
                            path=f"routes.{route_path}.guards[{i}].role",
                            message=f"Route guard references unknown role '{role_name}'",
                            code="FE-004",
                            category="reference",
                            expected=list(roles)[:10],
                            actual=role_name
                        ))

                # Validate permission reference
                if guard_type == "permission":
                    perm_name = guard.get("permission", "")
                    if perm_name and all_permissions and perm_name not in all_permissions:
                        errors.append(ValidationError(
                            path=f"routes.{route_path}.guards[{i}].permission",
                            message=f"Route guard references unknown permission '{perm_name}'",
                            code="FE-004",
                            category="reference",
                            expected=list(all_permissions)[:10],
                            actual=perm_name
                        ))

        return errors

    def _detect_unused_functions(self, spec: dict) -> list[ValidationError]:
        """
        FE-005: Detect functions that are not used in any view.

        This is a warning (not an error) to help identify functions that may be
        missing from the UI.

        Returns ValidationError with code FE-005 and severity="warning".
        """
        warnings = []
        functions = set(spec.get("functions", {}).keys())
        views = spec.get("views", {})

        if not functions or not views:
            return warnings

        # Collect all functions used in views
        used_functions = set()
        for view in views.values():
            for action in view.get("actions", []):
                func_name = action.get("function", "")
                if func_name:
                    used_functions.add(func_name)

        # Also collect functions used in routes (guards with custom conditions)
        for route in spec.get("routes", {}).values():
            for guard in route.get("guards", []):
                # Custom guards might reference functions in their conditions
                pass  # For now, we only track view actions

        # Also collect functions used in other places:
        # - subscriptions handlers
        for sub in spec.get("subscriptions", {}).values():
            handler = sub.get("handler", "")
            if handler:
                used_functions.add(handler)

        # - saga steps
        for saga in spec.get("sagas", {}).values():
            for step in saga.get("steps", []):
                forward = step.get("forward", "")
                compensate = step.get("compensate", "")
                if forward:
                    used_functions.add(forward)
                if compensate:
                    used_functions.add(compensate)

        # - schedule actions
        for schedule in spec.get("schedules", {}).values():
            action = schedule.get("action", "")
            if isinstance(action, str):
                used_functions.add(action)
            elif isinstance(action, dict):
                used_functions.add(action.get("call", ""))

        # - state machine transitions (trigger_function)
        for sm in spec.get("stateMachines", {}).values():
            for trans in sm.get("transitions", []):
                trigger = trans.get("trigger_function", "")
                if trigger:
                    used_functions.add(trigger)

        # - deadline actions
        for deadline in spec.get("deadlines", {}).values():
            action = deadline.get("action", "")
            if action:
                used_functions.add(action)

        # Find unused functions
        unused = functions - used_functions

        for func_name in sorted(unused):
            # Skip internal or private functions (starting with _)
            if func_name.startswith("_"):
                continue

            warnings.append(ValidationError(
                path=f"functions.{func_name}",
                message=f"Function '{func_name}' is not used in any view or integration",
                code="FE-005",
                category="usage",
                severity="warning"
            ))

        return warnings

    def _validate_field_constraints(self, spec: dict) -> list[ValidationError]:
        """
        Validate field constraints in entity definitions.

        Error codes:
        - CNS-001: min > max
        - CNS-002: string type uses min/max instead of minLength/maxLength
        - CNS-003: Invalid regex pattern
        - CNS-004: minLength > maxLength
        - CNS-005: Unknown preset
        """
        import re
        from the_mesh.generators.constraint_inference import PRESETS

        errors = []
        entities = spec.get("state", {})

        valid_presets = set(PRESETS.keys())

        for entity_name, entity_def in entities.items():
            fields = entity_def.get("fields", {})

            for field_name, field_def in fields.items():
                base_path = f"state.{entity_name}.fields.{field_name}"
                field_type = field_def.get("type")

                # Determine if this is a string type
                is_string_type = (
                    field_type == "string" or
                    field_type == "text" or
                    (isinstance(field_type, dict) and "enum" in field_type)
                )

                # CNS-001: min > max
                if "min" in field_def and "max" in field_def:
                    if field_def["min"] > field_def["max"]:
                        errors.append(ValidationError(
                            path=base_path,
                            message=f"min ({field_def['min']}) cannot be greater than max ({field_def['max']})",
                            code="CNS-001",
                            category="constraint"
                        ))

                # CNS-002: string type uses min/max
                if is_string_type:
                    if "min" in field_def:
                        errors.append(ValidationError(
                            path=f"{base_path}.min",
                            message="Use 'minLength' instead of 'min' for string fields",
                            code="CNS-002",
                            category="constraint"
                        ))
                    if "max" in field_def:
                        errors.append(ValidationError(
                            path=f"{base_path}.max",
                            message="Use 'maxLength' instead of 'max' for string fields",
                            code="CNS-002",
                            category="constraint"
                        ))

                # CNS-003: Invalid regex pattern
                if "pattern" in field_def:
                    try:
                        re.compile(field_def["pattern"])
                    except re.error as e:
                        errors.append(ValidationError(
                            path=f"{base_path}.pattern",
                            message=f"Invalid regex pattern: {e}",
                            code="CNS-003",
                            category="constraint"
                        ))

                # CNS-004: minLength > maxLength
                if "minLength" in field_def and "maxLength" in field_def:
                    if field_def["minLength"] > field_def["maxLength"]:
                        errors.append(ValidationError(
                            path=base_path,
                            message=f"minLength ({field_def['minLength']}) cannot be greater than maxLength ({field_def['maxLength']})",
                            code="CNS-004",
                            category="constraint"
                        ))

                # CNS-005: Unknown preset
                if "preset" in field_def:
                    preset_name = field_def["preset"]
                    if preset_name not in valid_presets:
                        errors.append(ValidationError(
                            path=f"{base_path}.preset",
                            message=f"Unknown preset '{preset_name}'. Valid presets: {', '.join(sorted(valid_presets))}",
                            code="CNS-005",
                            category="constraint"
                        ))

        return errors

    def _generate_constraint_inference_warnings(self, spec: dict) -> list[ValidationError]:
        """
        Generate warnings for fields where constraints are inferred from field names.

        Warning code:
        - CNS-006: Constraint inferred from field name pattern

        This allows the LLM to review and confirm inferred constraints.
        """
        warnings = []
        entities = spec.get("state", {})

        for entity_name, entity_def in entities.items():
            fields = entity_def.get("fields", {})

            for field_name, field_def in fields.items():
                # Skip if preset is explicitly specified
                if "preset" in field_def:
                    continue

                # Skip if any explicit constraint is specified
                explicit_constraints = ["min", "max", "minLength", "maxLength", "pattern", "format"]
                if any(k in field_def for k in explicit_constraints):
                    continue

                # Check if field name matches inference rules
                inferred_preset = infer_preset_from_field_name(field_name)
                if inferred_preset:
                    preset_def = PRESETS.get(inferred_preset, {})
                    if preset_def:  # Only warn if preset has actual constraints
                        constraint_desc = ", ".join(f"{k}: {v}" for k, v in preset_def.items())

                        warnings.append(ValidationError(
                            path=f"state.{entity_name}.fields.{field_name}",
                            message=(
                                f"Inferred '{inferred_preset}' preset from field name ({constraint_desc}). "
                                f"Add 'preset: \"{inferred_preset}\"' to confirm, "
                                f"or 'preset: \"none\"' to disable inference."
                            ),
                            code="CNS-006",
                            category="constraint",
                            severity="warning"
                        ))

        return warnings
