"""TRIR to YAML Generator (Human View)"""

from typing import Any

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


class YAMLGenerator:
    """Generates human-readable YAML from TRIR specification"""

    def __init__(self, spec: dict[str, Any]):
        if not HAS_YAML:
            raise ImportError("PyYAML is required: pip install pyyaml")
        self.spec = spec

    def generate(self) -> str:
        """Generate full YAML view"""
        human_spec = self._transform_to_human_view(self.spec)
        return yaml.dump(human_spec, allow_unicode=True, default_flow_style=False, sort_keys=False)

    def generate_section(self, section: str) -> str:
        """Generate YAML for a specific section"""
        if section not in self.spec:
            return f"# Section '{section}' not found"

        human_section = {}
        if section == "state":
            human_section = self._transform_entities(self.spec["state"])
        elif section == "derived":
            human_section = self._transform_derived(self.spec["derived"])
        elif section == "functions":
            human_section = self._transform_functions(self.spec["functions"])
        elif section == "scenarios":
            human_section = self._transform_scenarios(self.spec["scenarios"])
        elif section == "invariants":
            human_section = self._transform_invariants(self.spec["invariants"])
        else:
            human_section = self.spec[section]

        return yaml.dump({section: human_section}, allow_unicode=True, default_flow_style=False, sort_keys=False)

    def _transform_to_human_view(self, spec: dict) -> dict:
        """Transform full spec to human-readable format"""
        return {
            "meta": spec.get("meta", {}),
            "state": self._transform_entities(spec.get("state", {})),
            "derived": self._transform_derived(spec.get("derived", {})),
            "functions": self._transform_functions(spec.get("functions", {})),
            "scenarios": self._transform_scenarios(spec.get("scenarios", {})),
            "invariants": self._transform_invariants(spec.get("invariants", []))
        }

    def _transform_entities(self, entities: dict) -> dict:
        """Transform entities to human-readable format"""
        result = {}
        for name, entity in entities.items():
            result[name] = {
                "description": entity.get("description", ""),
                "fields": {}
            }
            for field_name, field_def in entity.get("fields", {}).items():
                field_type = field_def.get("type")
                type_str = self._type_to_string(field_type)

                field_repr = type_str
                if not field_def.get("required", True):
                    field_repr += "?"
                if field_def.get("unique"):
                    field_repr += " [unique]"

                result[name]["fields"][field_name] = field_repr

        return result

    def _transform_derived(self, derived: dict) -> dict:
        """Transform derived formulas to human-readable format"""
        result = {}
        for name, d in derived.items():
            result[name] = {
                "on": d.get("entity", ""),
                "formula": self._expr_to_human(d.get("formula", {})),
                "returns": d.get("returns", "any")
            }
            if d.get("description"):
                result[name]["description"] = d["description"]
        return result

    def _transform_functions(self, functions: dict) -> dict:
        """Transform functions to human-readable format"""
        result = {}
        for name, func in functions.items():
            f = {
                "description": func.get("description", ""),
                "input": self._transform_input(func.get("input", {}))
            }

            if func.get("implements"):
                f["implements"] = func["implements"]

            if func.get("pre"):
                f["preconditions"] = [
                    {
                        "check": self._expr_to_human(p["expr"]),
                        "on": p.get("entity", ""),
                        "reason": p.get("reason", "")
                    }
                    for p in func["pre"]
                ]

            if func.get("error"):
                f["errors"] = [
                    {
                        "code": e["code"],
                        "when": self._expr_to_human(e["when"]),
                        "reason": e.get("reason", ""),
                        "status": e.get("http_status", 409)
                    }
                    for e in func["error"]
                ]

            if func.get("post"):
                f["effects"] = []
                for p in func["post"]:
                    effect = self._action_to_human(p["action"])
                    if p.get("condition"):
                        effect["if"] = self._expr_to_human(p["condition"])
                    if p.get("reason"):
                        effect["reason"] = p["reason"]
                    f["effects"].append(effect)

            result[name] = f
        return result

    def _transform_scenarios(self, scenarios: dict) -> dict:
        """Transform scenarios to human-readable format"""
        result = {}
        for sid, scenario in scenarios.items():
            s = {
                "title": scenario.get("title", ""),
                "given": scenario.get("given", {}),
                "when": f"{scenario['when']['call']}({scenario['when'].get('input', {})})",
                "then": {}
            }

            then = scenario.get("then", {})
            if "success" in then:
                s["then"]["success"] = then["success"]
            if "error" in then:
                s["then"]["error"] = then["error"]
            if then.get("assert"):
                s["then"]["assert"] = [
                    self._expr_to_human(a) for a in then["assert"]
                ]

            if scenario.get("verifies"):
                s["verifies"] = scenario["verifies"]

            result[sid] = s
        return result

    def _transform_invariants(self, invariants: list) -> list:
        """Transform invariants to human-readable format"""
        return [
            {
                "id": inv.get("id", ""),
                "on": inv.get("entity", ""),
                "rule": self._expr_to_human(inv.get("expr", {})),
                "description": inv.get("description", "")
            }
            for inv in invariants
        ]

    def _transform_input(self, input_def: dict) -> dict:
        """Transform input definition"""
        result = {}
        for name, field in input_def.items():
            type_str = self._type_to_string(field.get("type"))
            if not field.get("required", True):
                type_str += "?"
            result[name] = type_str
        return result

    def _type_to_string(self, field_type: Any) -> str:
        """Convert type definition to string"""
        if isinstance(field_type, str):
            return field_type

        if isinstance(field_type, dict):
            if "enum" in field_type:
                return f"enum({', '.join(repr(v) for v in field_type['enum'])})"
            if "ref" in field_type:
                return f"-> {field_type['ref']}"
            if "list" in field_type:
                inner = self._type_to_string(field_type["list"])
                return f"[{inner}]"

        return "any"

    def _expr_to_human(self, expr: dict) -> str:
        """Convert expression to human-readable string (Tagged Union format)"""
        if not isinstance(expr, dict):
            return str(expr)

        expr_type = expr.get("type")

        # Literal: { "type": "literal", "value": ... }
        if expr_type == "literal":
            v = expr.get("value")
            return repr(v) if isinstance(v, str) else str(v)

        # Self reference: { "type": "self", "field": "..." }
        if expr_type == "self":
            field = expr.get("field", "")
            return f"self.{field}" if field else "self"

        # Field reference: { "type": "ref", "path": "entity.field" }
        if expr_type == "ref":
            return expr.get("path", "")

        # Input reference: { "type": "input", "name": "..." }
        if expr_type == "input":
            return f"input.{expr.get('name', '')}"

        # Function call: { "type": "call", "name": "fn", "args": [...] }
        if expr_type == "call":
            args = expr.get("args", [])
            args_str = ", ".join(self._expr_to_human(a) for a in args)
            return f"{expr.get('name', '')}({args_str})"

        # Binary operation: { "type": "binary", "op": "add", "left": ..., "right": ... }
        if expr_type == "binary":
            op_map = {
                "eq": "==", "ne": "!=", "lt": "<", "le": "<=", "gt": ">", "ge": ">=",
                "add": "+", "sub": "-", "mul": "*", "div": "/", "mod": "%",
                "and": "AND", "or": "OR", "in": "IN", "not_in": "NOT IN"
            }
            op = op_map.get(expr.get("op", ""), expr.get("op", ""))
            left = self._expr_to_human(expr.get("left", {}))
            right = self._expr_to_human(expr.get("right", {}))
            return f"{left} {op} {right}"

        # Unary operation: { "type": "unary", "op": "not", "expr": ... }
        if expr_type == "unary":
            op_map = {"not": "NOT", "neg": "-", "is_null": "IS NULL", "is_not_null": "IS NOT NULL"}
            op = expr.get("op", "")
            op_str = op_map.get(op, op)
            inner = self._expr_to_human(expr.get("expr", {}))
            if op in ("is_null", "is_not_null"):
                return f"{inner} {op_str}"
            return f"{op_str} {inner}"

        # Aggregation: { "type": "agg", "op": "sum", "from": "entity", ... }
        if expr_type == "agg":
            agg = expr.get("op", "").upper()
            from_entity = expr.get("from", "")
            agg_expr = self._expr_to_human(expr.get("expr", {})) if "expr" in expr else ""

            result = f"{agg}("
            if agg_expr:
                result += f"{agg_expr} "
            result += f"FROM {from_entity}"
            if expr.get("where"):
                result += f" WHERE {self._expr_to_human(expr['where'])}"
            result += ")"
            return result

        # Conditional: { "type": "if", "cond": ..., "then": ..., "else": ... }
        if expr_type == "if":
            cond = self._expr_to_human(expr.get("cond", {}))
            then = self._expr_to_human(expr.get("then", {}))
            else_ = self._expr_to_human(expr.get("else", {}))
            return f"IF {cond} THEN {then} ELSE {else_}"

        # Case expression: { "type": "case", "branches": [...], "else": ... }
        if expr_type == "case":
            cases = " ".join(
                f"WHEN {self._expr_to_human(c['when'])} THEN {self._expr_to_human(c['then'])}"
                for c in expr.get("branches", [])
            )
            else_ = self._expr_to_human(expr.get("else", {}))
            return f"CASE {cases} ELSE {else_} END"

        # Date operation: { "type": "date", "op": "diff", "args": [...], "unit": "..." }
        if expr_type == "date":
            op = expr.get("op", "").upper()
            args = ", ".join(self._expr_to_human(a) for a in expr.get("args", []))
            unit = expr.get("unit", "")
            if unit:
                return f"DATE_{op}({args}, {unit})"
            return f"DATE_{op}({args})"

        # List operation: { "type": "list", "op": "contains", "list": ..., "args": [...] }
        if expr_type == "list":
            op = expr.get("op", "").upper()
            list_expr = self._expr_to_human(expr.get("list", {}))
            args = ", ".join(self._expr_to_human(a) for a in expr.get("args", []))
            return f"{list_expr}.{op}({args})"

        return str(expr)

    def _action_to_human(self, action: dict) -> dict:
        """Convert action to human-readable format"""
        if "create" in action:
            return {
                "create": action["create"],
                "with": {
                    k: self._expr_to_human(v)
                    for k, v in action.get("with", {}).items()
                }
            }
        if "update" in action:
            return {
                "update": action["update"],
                "set": {
                    k: self._expr_to_human(v)
                    for k, v in action.get("set", {}).items()
                }
            }
        if "delete" in action:
            return {
                "delete": action["delete"],
                "where": self._expr_to_human(action.get("where", {}))
            }
        return action
