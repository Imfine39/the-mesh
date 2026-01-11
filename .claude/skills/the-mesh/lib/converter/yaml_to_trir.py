"""
Structured YAML to TRIR JSON converter.

This module provides mechanical (deterministic) conversion from
the customer-friendly Structured YAML format to the TRIR format
used by the-mesh for validation and test generation.

The conversion is 1-to-1 and requires no AI interpretation.
"""

from typing import Any
import copy

# Formula parser for derived section
parse_formula = None
try:
    from dsl.formula_parser import parse_formula
except ImportError:
    try:
        # Alternative import path
        import sys
        import os
        dsl_path = os.path.join(os.path.dirname(__file__), '..', 'dsl')
        if dsl_path not in sys.path:
            sys.path.insert(0, dsl_path)
        from formula_parser import parse_formula
    except ImportError:
        pass  # Optional dependency


class YAMLToTRIRConverter:
    """Structured YAML -> TRIR JSON converter."""

    # Type mapping from structured YAML keywords to TRIR type definitions
    TYPE_MAPPING = {
        "id": {"type": "string", "preset": "id"},
        "money": {"type": "float", "preset": "money"},
        "count": {"type": "int", "preset": "count"},
        "string": {"type": "string"},
        "int": {"type": "int"},
        "float": {"type": "float"},
        "bool": {"type": "bool"},
        "boolean": {"type": "boolean"},
        "datetime": {"type": "datetime"},
        "text": {"type": "text"},
    }

    # Operator mapping from structured YAML to TRIR
    OP_MAPPING = {
        "==": "eq",
        "!=": "ne",
        "<": "lt",
        "<=": "le",
        ">": "gt",
        ">=": "ge",
        "in": "in",
        "not_in": "not_in",
    }

    def convert(self, yaml_spec: dict) -> dict:
        """
        Main conversion entry point.

        Args:
            yaml_spec: Parsed structured YAML specification

        Returns:
            TRIR-format JSON specification
        """
        trir = {}

        # Convert meta (1:1 mapping)
        if "meta" in yaml_spec:
            trir["meta"] = copy.deepcopy(yaml_spec["meta"])

        # Convert entities
        if "entities" in yaml_spec:
            trir["entities"] = self._convert_entities(yaml_spec["entities"])

        # Convert state machines
        if "stateMachines" in yaml_spec:
            trir["stateMachines"] = self._convert_state_machines(yaml_spec["stateMachines"])

        # Convert commands
        if "commands" in yaml_spec:
            trir["commands"] = self._convert_commands(yaml_spec["commands"])

        # Convert queries
        if "queries" in yaml_spec:
            trir["queries"] = self._convert_queries(yaml_spec["queries"])

        # Convert sagas
        if "sagas" in yaml_spec:
            trir["sagas"] = self._convert_sagas(yaml_spec["sagas"])

        # Convert invariants
        if "invariants" in yaml_spec:
            trir["invariants"] = self._convert_invariants(yaml_spec["invariants"])

        # Convert roles
        if "roles" in yaml_spec:
            trir["roles"] = self._convert_roles(yaml_spec["roles"])

        # Convert scenarios (pass through as-is, they're already in correct format)
        if "scenarios" in yaml_spec:
            trir["scenarios"] = copy.deepcopy(yaml_spec["scenarios"])

        # Convert test strategies
        if "testStrategies" in yaml_spec:
            trir["testStrategies"] = copy.deepcopy(yaml_spec["testStrategies"])

        # Convert derived formulas
        if "derived" in yaml_spec:
            trir["derived"] = self._convert_derived(yaml_spec["derived"])

        return trir

    def _convert_entities(self, entities: dict) -> dict:
        """Convert entities section."""
        result = {}
        for name, entity in entities.items():
            result[name] = self._convert_entity(entity)
        return result

    def _convert_entity(self, entity: dict) -> dict:
        """Convert a single entity definition."""
        result = {}

        if "description" in entity:
            result["description"] = entity["description"]

        if entity.get("aggregateRoot"):
            result["aggregateRoot"] = True

        if "parent" in entity:
            result["parent"] = entity["parent"]

        if "fields" in entity:
            result["fields"] = {}
            for field_name, field_def in entity["fields"].items():
                result["fields"][field_name] = self._convert_field(field_def)

        return result

    def _convert_field(self, field_def: dict) -> dict:
        """Convert a field definition."""
        result = {}
        field_type = field_def.get("type")

        # Handle basic types
        if field_type in self.TYPE_MAPPING:
            type_info = self.TYPE_MAPPING[field_type]
            result["type"] = type_info["type"]
            if "preset" in type_info:
                result["preset"] = type_info["preset"]

        # Handle enum type (either type: enum or enum: [...])
        elif field_type == "enum":
            if "values" in field_def:
                result["type"] = {"enum": field_def["values"]}
            else:
                result["type"] = "string"

        # Handle ref type (type: ref + ref: Entity)
        elif field_type == "ref":
            if "ref" in field_def:
                result["type"] = {"ref": field_def["ref"]}
            else:
                result["type"] = "string"

        # Handle list type
        elif field_type == "list":
            # For now, treat as list of strings
            result["type"] = {"list": "string"}

        else:
            # Fallback: keep the type as-is if it's a string, otherwise string
            if isinstance(field_type, str):
                result["type"] = field_type
            else:
                result["type"] = "string"

        # Preserve enum values if specified separately (enum: [...])
        if "enum" in field_def and isinstance(field_def["enum"], list):
            result["enum"] = field_def["enum"]

        # Preserve ref if specified separately (ref: Entity) - for FK reference
        if "ref" in field_def and isinstance(field_def["ref"], str):
            result["ref"] = field_def["ref"]

        # Copy other field properties
        if field_def.get("required"):
            result["required"] = True
        if field_def.get("unique"):
            result["unique"] = True
        if "min" in field_def:
            result["min"] = field_def["min"]
        if "max" in field_def:
            result["max"] = field_def["max"]
        if "default" in field_def:
            result["default"] = field_def["default"]
        if "description" in field_def:
            result["description"] = field_def["description"]

        return result

    def _convert_state_machines(self, state_machines: dict) -> dict:
        """Convert state machines section."""
        result = {}
        for name, sm in state_machines.items():
            result[name] = self._convert_state_machine(sm)
        return result

    def _convert_state_machine(self, sm: dict) -> dict:
        """Convert a single state machine definition."""
        result = {
            "entity": sm["entity"],
            "field": sm["field"],
            "initial": sm["initial"],
        }

        # Convert states
        if "states" in sm:
            result["states"] = {}
            for state_name, state_def in sm["states"].items():
                result["states"][state_name] = self._convert_state(state_def)

        # Convert transitions
        if "transitions" in sm:
            result["transitions"] = [
                self._convert_transition(t) for t in sm["transitions"]
            ]

        return result

    def _convert_state(self, state_def: dict) -> dict:
        """Convert a state definition."""
        result = {}
        if "description" in state_def:
            result["description"] = state_def["description"]
        if state_def.get("final"):
            result["final"] = True
        if state_def.get("confirmed"):
            # Map 'confirmed' to a custom property
            result["confirmed"] = True
        return result

    def _convert_transition(self, transition: dict) -> dict:
        """Convert a transition definition."""
        result = {}

        if "id" in transition:
            result["id"] = transition["id"]

        # Handle 'from' (can be string or array)
        if "from" in transition:
            result["from"] = transition["from"]

        if "to" in transition:
            result["to"] = transition["to"]

        if "trigger" in transition:
            result["trigger"] = transition["trigger"]

        if "trigger_function" in transition:
            result["trigger_function"] = transition["trigger_function"]

        if "guard" in transition:
            result["guard"] = self._convert_expression(transition["guard"])

        if "error" in transition:
            result["error"] = transition["error"]

        if "actions" in transition:
            result["actions"] = transition["actions"]

        return result

    def _convert_expression(self, expr: dict) -> dict:
        """
        Convert an expression (3-level support).

        Level 1: Simple condition { field, op, value/ref }
        Level 2: Compound condition { and/or/not }
        Level 3: Raw TRIR expression { expr: {...} }
        """
        # Level 3: Raw TRIR expression (escape hatch)
        if "expr" in expr and isinstance(expr["expr"], dict):
            # Check if it's a nested simple expression or raw TRIR
            nested = expr["expr"]
            if "type" in nested:
                # It's already a TRIR expression, return as-is
                return nested
            else:
                # Might be wrapped, unwrap and convert
                return self._convert_expression(nested)

        # Level 2: Compound conditions
        if "and" in expr:
            return {
                "type": "binary",
                "op": "and",
                "left": self._convert_expression(expr["and"][0]),
                "right": self._convert_and_chain(expr["and"][1:]) if len(expr["and"]) > 1 else {"type": "literal", "value": True}
            }

        if "or" in expr:
            return {
                "type": "binary",
                "op": "or",
                "left": self._convert_expression(expr["or"][0]),
                "right": self._convert_or_chain(expr["or"][1:]) if len(expr["or"]) > 1 else {"type": "literal", "value": False}
            }

        if "not" in expr:
            return {
                "type": "unary",
                "op": "not",
                "operand": self._convert_expression(expr["not"])
            }

        # Level 1: Simple condition
        if "field" in expr and "op" in expr:
            return self._convert_simple_condition(expr)

        # Fallback: return as-is (might be already TRIR)
        return expr

    def _convert_and_chain(self, exprs: list) -> dict:
        """Convert remaining AND expressions into a chain."""
        if len(exprs) == 1:
            return self._convert_expression(exprs[0])
        return {
            "type": "binary",
            "op": "and",
            "left": self._convert_expression(exprs[0]),
            "right": self._convert_and_chain(exprs[1:])
        }

    def _convert_or_chain(self, exprs: list) -> dict:
        """Convert remaining OR expressions into a chain."""
        if len(exprs) == 1:
            return self._convert_expression(exprs[0])
        return {
            "type": "binary",
            "op": "or",
            "left": self._convert_expression(exprs[0]),
            "right": self._convert_or_chain(exprs[1:])
        }

    def _convert_simple_condition(self, expr: dict) -> dict:
        """
        Convert a simple condition to TRIR binary expression.

        Field reference format:
        - input:fieldName -> { type: input, name: fieldName }
        - self:fieldName -> { type: ref, path: fieldName }
        - EntityName:fieldName -> { type: ref, path: EntityName.fieldName }
        """
        field_ref = expr["field"]
        op = self.OP_MAPPING.get(expr["op"], expr["op"])

        # Parse field reference
        left = self._parse_field_reference(field_ref)

        # Parse value or ref
        if "ref" in expr:
            right = self._parse_field_reference(expr["ref"])
        elif "value" in expr:
            value = expr["value"]
            # Handle special null value
            if value is None:
                right = {"type": "literal", "value": None}
            # Handle list values for 'in' operator
            elif isinstance(value, list):
                right = {"type": "list", "items": [{"type": "literal", "value": v} for v in value]}
            else:
                right = {"type": "literal", "value": value}
        else:
            right = {"type": "literal", "value": None}

        return {
            "type": "binary",
            "op": op,
            "left": left,
            "right": right
        }

    def _parse_field_reference(self, field_ref: str) -> dict:
        """
        Parse a field reference string into TRIR expression.

        Formats:
        - input:fieldName -> { type: input, name: fieldName }
        - self:fieldName -> { type: ref, path: fieldName }
        - EntityName:fieldName -> { type: ref, path: EntityName.fieldName }
        - principal:id -> { type: principal, field: id }
        """
        if ":" in field_ref:
            prefix, field = field_ref.split(":", 1)

            if prefix == "input":
                return {"type": "input", "name": field}
            elif prefix == "self":
                return {"type": "ref", "path": field}
            elif prefix == "principal":
                return {"type": "principal", "field": field}
            else:
                # Entity reference
                return {"type": "ref", "path": f"{prefix}.{field}"}
        else:
            # No prefix, assume direct field reference
            return {"type": "ref", "path": field_ref}

    def _convert_commands(self, commands: dict) -> dict:
        """Convert commands section."""
        result = {}
        for name, cmd in commands.items():
            result[name] = self._convert_command(cmd)
        return result

    def _convert_command(self, cmd: dict) -> dict:
        """Convert a single command definition."""
        result = {}

        if "description" in cmd:
            result["description"] = cmd["description"]

        if "entity" in cmd:
            result["entity"] = cmd["entity"]

        if "input" in cmd:
            result["input"] = {}
            for field_name, field_def in cmd["input"].items():
                result["input"][field_name] = self._convert_field(field_def)

        if "output" in cmd:
            result["output"] = {}
            for field_name, field_def in cmd["output"].items():
                result["output"][field_name] = self._convert_field(field_def)

        if "pre" in cmd:
            result["pre"] = []
            for pre in cmd["pre"]:
                converted = {"expr": self._convert_expression(pre.get("expr", pre))}
                if "error" in pre:
                    converted["reason"] = pre["error"]
                result["pre"].append(converted)

        if "post" in cmd:
            result["post"] = []
            for post in cmd["post"]:
                result["post"].append(self._convert_post_action(post))

        if "triggers" in cmd:
            result["triggers"] = cmd["triggers"]

        if "saga" in cmd:
            result["saga"] = cmd["saga"]

        # Convert errors
        if "errors" in cmd:
            result["errors"] = copy.deepcopy(cmd["errors"])

        return result

    def _convert_post_action(self, post: dict) -> dict:
        """Convert a post action definition."""
        result = {}

        # Preserve id if present
        if "id" in post:
            result["id"] = post["id"]

        action = post.get("action", {})

        if "create" in action:
            create_val = action["create"]
            # New format: create: { target: ..., data: {...} }
            if isinstance(create_val, dict) and "target" in create_val:
                create_result = {"target": create_val["target"]}
                if "data" in create_val:
                    create_result["data"] = {}
                    for field_name, value_expr in create_val["data"].items():
                        if isinstance(value_expr, dict) and "type" in value_expr:
                            create_result["data"][field_name] = value_expr
                        else:
                            create_result["data"][field_name] = self._convert_expression(value_expr)
                result["action"] = {"create": create_result}
            # Old format: create: "Entity" + with: {...}
            else:
                result["action"] = {"create": create_val}
                if "with" in action:
                    result["action"]["with"] = {}
                    for field_name, value_expr in action["with"].items():
                        if isinstance(value_expr, dict) and "type" in value_expr:
                            result["action"]["with"][field_name] = value_expr
                        else:
                            result["action"]["with"][field_name] = self._convert_expression(value_expr)

        elif "update" in action:
            update_val = action["update"]
            # New format: update: { target: ..., id: {...}, set: {...} }
            if isinstance(update_val, dict) and "target" in update_val:
                update_result = {"target": update_val["target"]}
                if "id" in update_val:
                    update_result["id"] = update_val["id"]
                if "set" in update_val:
                    update_result["set"] = {}
                    for field_name, value_expr in update_val["set"].items():
                        if isinstance(value_expr, dict) and "type" in value_expr:
                            update_result["set"][field_name] = value_expr
                        else:
                            update_result["set"][field_name] = self._convert_expression(value_expr)
                result["action"] = {"update": update_result}
            # Old format: update: "Entity" + set: {...}
            else:
                result["action"] = {"update": update_val}
                if "set" in action:
                    result["action"]["set"] = {}
                    for field_name, value_expr in action["set"].items():
                        if isinstance(value_expr, dict) and "type" in value_expr:
                            result["action"]["set"][field_name] = value_expr
                        else:
                            result["action"]["set"][field_name] = self._convert_expression(value_expr)

        elif "delete" in action:
            delete_val = action["delete"]
            # New format: delete: { target: ..., id: {...} }
            if isinstance(delete_val, dict) and "target" in delete_val:
                delete_result = {"target": delete_val["target"]}
                if "id" in delete_val:
                    delete_result["id"] = delete_val["id"]
                result["action"] = {"delete": delete_result}
            # Old format: delete: "Entity"
            else:
                result["action"] = {"delete": delete_val}
                if "where" in action:
                    result["action"]["where"] = self._convert_expression(action["where"])

        return result

    def _convert_queries(self, queries: dict) -> dict:
        """Convert queries section."""
        result = {}
        for name, query in queries.items():
            result[name] = self._convert_query(query)
        return result

    def _convert_query(self, query: dict) -> dict:
        """Convert a single query definition."""
        result = {}

        if "description" in query:
            result["description"] = query["description"]

        if "entity" in query:
            result["entity"] = query["entity"]

        if "filter" in query:
            result["filter"] = self._convert_expression(query["filter"])

        if "orderBy" in query:
            result["orderBy"] = query["orderBy"]

        if "pagination" in query:
            result["pagination"] = query["pagination"]

        return result

    def _convert_sagas(self, sagas: dict) -> dict:
        """Convert sagas section."""
        result = {}
        for name, saga in sagas.items():
            result[name] = self._convert_saga(saga)
        return result

    def _convert_saga(self, saga: dict) -> dict:
        """Convert a single saga definition."""
        result = {}

        if "description" in saga:
            result["description"] = saga["description"]

        if "steps" in saga:
            result["steps"] = [
                {
                    "name": step["name"],
                    "forward": step["forward"],
                    **({"compensate": step["compensate"]} if "compensate" in step else {})
                }
                for step in saga["steps"]
            ]

        if "onFailure" in saga:
            result["onFailure"] = saga["onFailure"]

        return result

    def _convert_invariants(self, invariants: list) -> list:
        """Convert invariants section."""
        return [self._convert_invariant(inv) for inv in invariants]

    def _convert_invariant(self, inv: dict) -> dict:
        """Convert a single invariant definition."""
        result = {
            "id": inv["id"],
            "entity": inv["entity"],
            "expr": self._convert_expression(inv["expr"])
        }

        if "description" in inv:
            result["description"] = inv["description"]

        if "when" in inv:
            result["when"] = self._convert_expression(inv["when"])

        if "severity" in inv:
            result["severity"] = inv["severity"]

        if "violation" in inv:
            result["violation"] = inv["violation"]

        return result

    def _convert_roles(self, roles: dict) -> dict:
        """Convert roles section."""
        result = {}
        for name, role in roles.items():
            result[name] = self._convert_role(role)
        return result

    def _convert_role(self, role: dict) -> dict:
        """Convert a single role definition."""
        result = {}

        if "description" in role:
            result["description"] = role["description"]

        if "permissions" in role:
            result["permissions"] = []
            for perm in role["permissions"]:
                converted = {
                    "resource": perm["resource"],
                    "actions": perm["actions"]
                }
                if "condition" in perm:
                    converted["condition"] = self._convert_expression(perm["condition"])
                result["permissions"].append(converted)

        return result

    def _convert_derived(self, derived: dict) -> dict:
        """
        Convert derived formulas section.

        Input format (YAML):
            derived:
              Order.totalAmount: "sum(orderItems.quantity * orderItems.unitPrice)"
              CartItem.subtotal: "self.quantity * self.unitPrice"

        Output format (TRIR):
            derived:
              Order.totalAmount:
                entity: Order
                formula: { ... parsed TRIR expression ... }
              CartItem.subtotal:
                entity: CartItem
                formula: { ... }
        """
        if parse_formula is None:
            # Formula parser not available, pass through as-is
            return copy.deepcopy(derived)

        result = {}
        for key, formula in derived.items():
            # Key format: "Entity.field" or just "field"
            if "." in key:
                entity, field = key.split(".", 1)
            else:
                entity = ""
                field = key

            # Parse formula string to TRIR expression
            if isinstance(formula, str):
                try:
                    parsed_formula = parse_formula(formula)
                except Exception as e:
                    # If parsing fails, store error info
                    result[key] = {
                        "entity": entity,
                        "field": field,
                        "formula": {"type": "literal", "value": None},
                        "_error": f"Failed to parse formula: {e}",
                        "_original": formula,
                    }
                    continue
            elif isinstance(formula, dict):
                # Already in TRIR format
                parsed_formula = formula.get("formula", formula)
            else:
                parsed_formula = {"type": "literal", "value": formula}

            result[key] = {
                "entity": entity,
                "field": field,
                "formula": parsed_formula,
            }

            # Add description if provided (when formula is dict)
            if isinstance(formula, dict) and "description" in formula:
                result[key]["description"] = formula["description"]

        return result
