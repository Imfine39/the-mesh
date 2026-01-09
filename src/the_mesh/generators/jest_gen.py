"""TRIR to Jest (JavaScript/TypeScript) Generator"""

from typing import Any


class JestGenerator:
    """Generates Jest test code from TRIR scenarios"""

    def __init__(self, spec: dict[str, Any], typescript: bool = False):
        """
        Initialize JestGenerator.

        Args:
            spec: TRIR specification
            typescript: If True, generate TypeScript code; otherwise JavaScript
        """
        self.spec = spec
        self.typescript = typescript
        self.entities = spec.get("state", {})
        self.derived = spec.get("derived", {})
        self.functions = spec.get("functions", {})
        self.scenarios = spec.get("scenarios", {})
        self.invariants = spec.get("invariants", [])

    def generate_all(self) -> str:
        """Generate Jest test code for all scenarios"""
        ext = "ts" if self.typescript else "js"

        lines = [
            f"/**",
            f" * Auto-generated tests from TRIR specification",
            f" * @generated",
            f" */",
            "",
        ]

        # Imports
        if self.typescript:
            lines.extend([
                "import { describe, test, expect, beforeEach } from '@jest/globals';",
                "",
                "// TODO: Import your implementation modules",
                "// import { db } from './db';",
                "// import { createInvoice, matchReceipt } from './ar';",
                "",
                "// Type definitions",
                self._generate_type_definitions(),
                "",
            ])
        else:
            lines.extend([
                "// TODO: Import your implementation modules",
                "// const { db } = require('./db');",
                "// const { createInvoice, matchReceipt } = require('./ar');",
                "",
            ])

        lines.extend([
            "// ========== Factory Functions ==========",
            "",
            self._generate_factories(),
            "",
            "// ========== Helper Functions ==========",
            "",
            self._generate_helpers(),
            "",
            "// ========== Scenario Tests ==========",
            "",
        ])

        # Group scenarios by function they test
        scenarios_by_function: dict[str, list[tuple[str, dict]]] = {}
        for scenario_id, scenario in self.scenarios.items():
            func_name = scenario.get("when", {}).get("call", "misc")
            if func_name not in scenarios_by_function:
                scenarios_by_function[func_name] = []
            scenarios_by_function[func_name].append((scenario_id, scenario))

        for func_name, scenarios in scenarios_by_function.items():
            lines.append(f"describe('{func_name}', () => {{")
            for scenario_id, scenario in scenarios:
                lines.append(self._generate_scenario_test(scenario_id, scenario, indent=1))
                lines.append("")
            lines.append("});")
            lines.append("")

        # Invariant tests
        if self.invariants:
            lines.append("// ========== Invariant Tests ==========")
            lines.append("")
            lines.append("describe('Invariants', () => {")
            lines.append(self._generate_invariant_tests(indent=1))
            lines.append("});")

        return "\n".join(lines)

    def generate_for_function(self, function_name: str) -> str:
        """Generate Jest test code for scenarios testing a specific function"""
        relevant_scenarios = {
            sid: s for sid, s in self.scenarios.items()
            if s.get("when", {}).get("call") == function_name
        }

        relevant_invariants = []
        func = self.functions.get(function_name, {})
        modified_entities = set()
        for post in func.get("post", []):
            action = post.get("action", {})
            for action_type in ["create", "update", "delete"]:
                if action_type in action:
                    modified_entities.add(action[action_type])

        for inv in self.invariants:
            if inv.get("entity") in modified_entities:
                relevant_invariants.append(inv)

        lines = [
            f"/**",
            f" * Auto-generated tests for {function_name}",
            f" * @generated",
            f" */",
            "",
        ]

        if self.typescript:
            lines.extend([
                "import { describe, test, expect, beforeEach } from '@jest/globals';",
                "",
                "// TODO: Import your implementation modules",
                "",
                self._generate_type_definitions(),
                "",
            ])
        else:
            lines.extend([
                "// TODO: Import your implementation modules",
                "",
            ])

        lines.extend([
            "// ========== Factory Functions ==========",
            "",
            self._generate_factories(),
            "",
            "// ========== Helper Functions ==========",
            "",
            self._generate_helpers(),
            "",
            f"// ========== Tests for {function_name} ==========",
            "",
            f"describe('{function_name}', () => {{",
        ])

        for scenario_id, scenario in relevant_scenarios.items():
            lines.append(self._generate_scenario_test(scenario_id, scenario, indent=1))
            lines.append("")

        if relevant_invariants:
            lines.append("  // Invariant Checks")
            for inv in relevant_invariants:
                lines.append(self._generate_single_invariant_test(inv, indent=1))
                lines.append("")

        lines.append("});")

        return "\n".join(lines)

    def _generate_type_definitions(self) -> str:
        """Generate TypeScript type definitions for entities"""
        if not self.typescript:
            return ""

        lines = []
        for entity_name, entity in self.entities.items():
            pascal_name = self._to_pascal_case(entity_name)
            lines.append(f"interface {pascal_name} {{")

            fields = entity.get("fields", {})
            for field_name, field_def in fields.items():
                ts_type = self._get_ts_type(field_def)
                optional = "" if field_def.get("required", False) else "?"
                lines.append(f"  {field_name}{optional}: {ts_type};")

            lines.append("}")
            lines.append("")

        return "\n".join(lines)

    def _generate_factories(self) -> str:
        """Generate factory functions for creating test entities"""
        lines = []

        for entity_name, entity in self.entities.items():
            pascal_name = self._to_pascal_case(entity_name)

            if self.typescript:
                lines.append(f"function create{pascal_name}(overrides: Partial<{pascal_name}> = {{}}): {pascal_name} {{")
            else:
                lines.append(f"function create{pascal_name}(overrides = {{}}) {{")

            lines.append("  return {")

            fields = entity.get("fields", {})
            for field_name, field_def in fields.items():
                default = self._get_default_value(field_name, field_def)
                lines.append(f"    {field_name}: overrides.{field_name} ?? {default},")

            lines.append("  };")
            lines.append("}")
            lines.append("")

        return "\n".join(lines)

    def _generate_helpers(self) -> str:
        """Generate helper functions for derived values"""
        lines = []

        for name, derived in self.derived.items():
            entity = derived.get("entity", "")
            camel_name = self._to_camel_case(name)

            if self.typescript:
                pascal_entity = self._to_pascal_case(entity) if entity else "any"
                lines.append(f"function {camel_name}({entity}: {pascal_entity}): number | string | boolean {{")
            else:
                lines.append(f"function {camel_name}({entity}) {{")

            lines.append(f"  /**")
            lines.append(f"   * {derived.get('description', f'Calculate {name}')}")
            lines.append(f"   */")
            lines.append(f"  // TODO: Implement based on formula")
            lines.append(f"  // Formula: {self._expr_to_pseudo(derived.get('formula', {}))}")
            lines.append(f"  throw new Error('Not implemented');")
            lines.append("}")
            lines.append("")

        return "\n".join(lines)

    def _generate_scenario_test(self, scenario_id: str, scenario: dict, indent: int = 0) -> str:
        """Generate a single test from a scenario"""
        ind = "  " * indent
        lines = []

        safe_id = scenario_id.upper().replace("-", "_")
        title = scenario.get("title", scenario_id)

        lines.append(f"{ind}test('{safe_id}: {self._escape_js_string(title)}', async () => {{")

        # Given
        given = scenario.get("given", {})
        if given:
            lines.append(f"{ind}  // Given")
            for entity_name, data in given.items():
                if entity_name not in self.entities:
                    continue
                pascal_name = self._to_pascal_case(entity_name)
                if isinstance(data, list):
                    for i, item in enumerate(data):
                        lines.append(f"{ind}  const {entity_name}{i} = create{pascal_name}({self._to_js_object(item)});")
                elif isinstance(data, dict):
                    lines.append(f"{ind}  const {entity_name} = create{pascal_name}({self._to_js_object(data)});")
            lines.append("")

        # When
        when = scenario.get("when", {})
        func_name = when.get("call", "unknownFunction")
        input_data = when.get("input", {})
        camel_func = self._to_camel_case(func_name)

        lines.append(f"{ind}  // When")
        if input_data:
            lines.append(f"{ind}  const result = await {camel_func}({self._to_js_object(input_data)});")
        else:
            lines.append(f"{ind}  const result = await {camel_func}();")
        lines.append("")

        # Then
        then = scenario.get("then", {})
        lines.append(f"{ind}  // Then")

        if then.get("success") is True:
            lines.append(f"{ind}  expect(result.success).toBe(true);")
        elif then.get("success") is False:
            lines.append(f"{ind}  expect(result.success).toBe(false);")
            if "error" in then:
                lines.append(f"{ind}  expect(result.error).toBe('{self._escape_js_string(then['error'])}');")

        for i, assertion in enumerate(then.get("assert", [])):
            lines.append(f"{ind}  // Assertion {i + 1}: {self._expr_to_pseudo(assertion)}")
            lines.append(f"{ind}  {self._generate_assertion(assertion)}")

        lines.append(f"{ind}}});")

        return "\n".join(lines)

    def _generate_invariant_tests(self, indent: int = 0) -> str:
        """Generate tests for all invariants"""
        if not self.invariants:
            return "  // No invariants defined"

        lines = []
        for inv in self.invariants:
            lines.append(self._generate_single_invariant_test(inv, indent))
            lines.append("")

        return "\n".join(lines)

    def _generate_single_invariant_test(self, inv: dict, indent: int = 0) -> str:
        """Generate test for a single invariant"""
        ind = "  " * indent
        inv_id = inv.get("id", "unknown").upper().replace("-", "_")
        entity = inv.get("entity", "entity")
        pascal_entity = self._to_pascal_case(entity)
        description = inv.get("description", inv_id)

        lines = [
            f"{ind}test('INVARIANT_{inv_id}: {self._escape_js_string(description)}', async () => {{",
            f"{ind}  // Get all {entity} instances",
            f"{ind}  const items = await db.getAll{pascal_entity}();",
            f"{ind}  ",
            f"{ind}  for (const {entity} of items) {{",
            f"{ind}    // Check: {self._expr_to_pseudo(inv.get('expr', {}))}",
            f"{ind}    {self._generate_invariant_check(inv.get('expr', {}), entity)}",
            f"{ind}  }}",
            f"{ind}}});",
        ]

        return "\n".join(lines)

    def _generate_assertion(self, expr: dict) -> str:
        """Generate Jest assertion from expression"""
        js_expr = self._expr_to_js(expr)
        return f"expect({js_expr}).toBe(true);"

    def _generate_invariant_check(self, expr: dict, entity_var: str) -> str:
        """Generate Jest assertion for invariant check"""
        js_expr = self._expr_to_js(expr, entity_var)
        return f"expect({js_expr}).toBe(true);"

    def _expr_to_js(self, expr: dict, entity_var: str = "") -> str:
        """Convert TRIR expression to JavaScript code (Tagged Union format)"""
        if not isinstance(expr, dict):
            return self._to_js_literal(expr)

        expr_type = expr.get("type")

        # Literal: { "type": "literal", "value": ... }
        if expr_type == "literal":
            return self._to_js_literal(expr.get("value"))

        # Self reference: { "type": "self", "field": "..." }
        if expr_type == "self":
            field = expr.get("field", "")
            if entity_var:
                return f"{entity_var}.{field}" if field else entity_var
            return f"this.{field}" if field else "this"

        # Field reference: { "type": "ref", "path": "entity.field" }
        if expr_type == "ref":
            return expr.get("path", "").replace(".", "?.")

        # Input reference: { "type": "input", "name": "..." }
        if expr_type == "input":
            return expr.get("name", "")

        # Function call: { "type": "call", "name": "fn", "args": [...] }
        if expr_type == "call":
            func = self._to_camel_case(expr.get("name", ""))
            args = expr.get("args", [])
            args_str = ", ".join(self._expr_to_js(a, entity_var) for a in args)
            return f"{func}({args_str})"

        # Binary operation: { "type": "binary", "op": "add", "left": ..., "right": ... }
        if expr_type == "binary":
            op_map = {
                "eq": "===", "ne": "!==", "lt": "<", "le": "<=", "gt": ">", "ge": ">=",
                "add": "+", "sub": "-", "mul": "*", "div": "/", "mod": "%",
                "and": "&&", "or": "||",
                "in": "includes",  # Special handling below
                "like": "match",   # Special handling below
            }
            op = expr.get("op", "")
            left = self._expr_to_js(expr.get("left", {}), entity_var)
            right = self._expr_to_js(expr.get("right", {}), entity_var)

            if op == "in":
                return f"{right}.includes({left})"
            if op == "like":
                # Convert SQL LIKE pattern to regex
                return f"{left}.match({right})"

            js_op = op_map.get(op, op)
            return f"({left} {js_op} {right})"

        # Unary operation: { "type": "unary", "op": "not", "expr": ... }
        if expr_type == "unary":
            op = expr.get("op", "")
            inner = self._expr_to_js(expr.get("expr", {}), entity_var)
            if op == "not":
                return f"(!{inner})"
            if op == "neg":
                return f"(-{inner})"
            if op == "is_null":
                return f"({inner} == null)"
            if op == "is_not_null":
                return f"({inner} != null)"
            return f"({op}({inner}))"

        # Aggregation: { "type": "agg", "op": "sum", "from": "entity", ... }
        if expr_type == "agg":
            agg_op = expr.get("op", "")
            from_entity = expr.get("from", "items")
            agg_expr = expr.get("expr", {})
            field = self._get_agg_field(agg_expr)

            if agg_op == "sum":
                return f"{from_entity}List.reduce((acc, item) => acc + item.{field}, 0)"
            elif agg_op == "count":
                return f"{from_entity}List.length"
            elif agg_op == "exists":
                return f"{from_entity}List.length > 0"
            elif agg_op == "avg":
                return f"({from_entity}List.reduce((acc, item) => acc + item.{field}, 0) / {from_entity}List.length)"
            elif agg_op == "min":
                return f"Math.min(...{from_entity}List.map(item => item.{field}))"
            elif agg_op == "max":
                return f"Math.max(...{from_entity}List.map(item => item.{field}))"
            elif agg_op == "all":
                where = expr.get("where", {})
                if where:
                    return f"{from_entity}List.every(item => {self._expr_to_js(where, 'item')})"
                return f"{from_entity}List.every(Boolean)"
            elif agg_op == "any":
                where = expr.get("where", {})
                if where:
                    return f"{from_entity}List.some(item => {self._expr_to_js(where, 'item')})"
                return f"{from_entity}List.some(Boolean)"

        # If-then-else: { "type": "if", "cond": ..., "then": ..., "else": ... }
        if expr_type == "if":
            cond = self._expr_to_js(expr.get("cond", {}), entity_var)
            then = self._expr_to_js(expr.get("then", {}), entity_var)
            else_ = self._expr_to_js(expr.get("else", {}), entity_var)
            return f"({cond} ? {then} : {else_})"

        # Case expression: { "type": "case", "branches": [...], "else": ... }
        if expr_type == "case":
            result = self._expr_to_js(expr.get("else", {}), entity_var)
            for branch in reversed(expr.get("branches", [])):
                cond = self._expr_to_js(branch.get("when", {}), entity_var)
                then = self._expr_to_js(branch.get("then", {}), entity_var)
                result = f"({cond} ? {then} : {result})"
            return result

        # Date operations: { "type": "date", "op": "diff", ... }
        if expr_type == "date":
            date_op = expr.get("op", "")
            if date_op == "now":
                return "new Date()"
            elif date_op == "diff":
                left = self._expr_to_js(expr.get("left", {}), entity_var)
                right = self._expr_to_js(expr.get("right", {}), entity_var)
                unit = expr.get("unit", "days")
                if unit == "days":
                    return f"Math.floor((new Date({left}) - new Date({right})) / (1000 * 60 * 60 * 24))"
                elif unit == "hours":
                    return f"Math.floor((new Date({left}) - new Date({right})) / (1000 * 60 * 60))"
            elif date_op == "add":
                base = self._expr_to_js(expr.get("date", {}), entity_var)
                amount = self._expr_to_js(expr.get("amount", {}), entity_var)
                unit = expr.get("unit", "days")
                if unit == "days":
                    return f"new Date(new Date({base}).getTime() + {amount} * 24 * 60 * 60 * 1000)"

        # List operations: { "type": "list", "op": "contains", ... }
        if expr_type == "list":
            list_op = expr.get("op", "")
            list_expr = self._expr_to_js(expr.get("list", {}), entity_var)
            if list_op == "contains":
                item = self._expr_to_js(expr.get("item", {}), entity_var)
                return f"{list_expr}.includes({item})"
            elif list_op == "length":
                return f"{list_expr}.length"
            elif list_op == "first":
                return f"{list_expr}[0]"
            elif list_op == "last":
                return f"{list_expr}[{list_expr}.length - 1]"

        return f"/* TODO: {expr} */"

    def _get_agg_field(self, expr: dict) -> str:
        """Extract field name from aggregation expression"""
        if expr.get("type") == "ref":
            parts = expr.get("path", "").split(".")
            return parts[-1] if len(parts) > 1 else parts[0]
        if expr.get("type") == "self":
            return expr.get("field", "value")
        return "value"

    def _expr_to_pseudo(self, expr: dict) -> str:
        """Convert expression to pseudo-code for comments"""
        if not isinstance(expr, dict):
            return str(expr)

        expr_type = expr.get("type")

        if expr_type == "literal":
            return repr(expr.get("value"))
        if expr_type == "self":
            field = expr.get("field", "")
            return f"self.{field}" if field else "self"
        if expr_type == "ref":
            return expr.get("path", "")
        if expr_type == "input":
            return f"input.{expr.get('name', '')}"
        if expr_type == "call":
            return f"{expr.get('name', '')}(...)"
        if expr_type == "binary":
            op = expr.get("op", "")
            return f"{self._expr_to_pseudo(expr.get('left', {}))} {op} {self._expr_to_pseudo(expr.get('right', {}))}"
        if expr_type == "unary":
            op = expr.get("op", "")
            return f"{op}({self._expr_to_pseudo(expr.get('expr', {}))})"
        if expr_type == "agg":
            return f"{expr.get('op', '')}({expr.get('from', '')})"
        if expr_type == "if":
            return f"IF({self._expr_to_pseudo(expr.get('cond', {}))}) THEN ... ELSE ..."
        if expr_type == "case":
            return "CASE ... END"

        return str(expr)

    def _get_default_value(self, field_name: str, field_def: dict) -> str:
        """Get default value for a field (JavaScript)"""
        field_type = field_def.get("type")

        if isinstance(field_type, str):
            defaults = {
                "string": f"'{field_name.upper()}-001'",
                "int": "0",
                "float": "0.0",
                "bool": "false",
                "datetime": "'2024-01-01T00:00:00Z'",
                "text": "''"
            }
            return defaults.get(field_type, "null")

        if isinstance(field_type, dict):
            if "enum" in field_type:
                return f"'{field_type['enum'][0]}'"
            if "ref" in field_type:
                return f"'{field_type['ref'].upper()}-001'"
            if "list" in field_type:
                return "[]"

        return "null"

    def _get_ts_type(self, field_def: dict) -> str:
        """Get TypeScript type for a field"""
        field_type = field_def.get("type")

        if isinstance(field_type, str):
            type_map = {
                "string": "string",
                "int": "number",
                "float": "number",
                "bool": "boolean",
                "datetime": "string",
                "text": "string"
            }
            return type_map.get(field_type, "unknown")

        if isinstance(field_type, dict):
            if "enum" in field_type:
                values = " | ".join(f"'{v}'" for v in field_type["enum"])
                return values
            if "ref" in field_type:
                return "string"  # ID reference
            if "list" in field_type:
                inner = self._get_ts_type({"type": field_type["list"]})
                return f"{inner}[]"

        return "unknown"

    def _to_pascal_case(self, name: str) -> str:
        """Convert snake_case to PascalCase"""
        return "".join(word.capitalize() for word in name.split("_"))

    def _to_camel_case(self, name: str) -> str:
        """Convert snake_case to camelCase"""
        parts = name.split("_")
        return parts[0] + "".join(word.capitalize() for word in parts[1:])

    def _escape_js_string(self, s: str) -> str:
        """Escape string for JavaScript"""
        return s.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")

    def _to_js_literal(self, value: Any) -> str:
        """Convert Python value to JavaScript literal"""
        if value is None:
            return "null"
        if value is True:
            return "true"
        if value is False:
            return "false"
        if isinstance(value, str):
            return f"'{self._escape_js_string(value)}'"
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, list):
            items = ", ".join(self._to_js_literal(v) for v in value)
            return f"[{items}]"
        if isinstance(value, dict):
            return self._to_js_object(value)
        return str(value)

    def _to_js_object(self, obj: dict) -> str:
        """Convert dict to JavaScript object literal"""
        if not obj:
            return "{}"
        items = []
        for k, v in obj.items():
            js_val = self._to_js_literal(v)
            # Use shorthand if key matches simple variable
            items.append(f"{k}: {js_val}")
        return "{ " + ", ".join(items) + " }"

    def _sanitize_name(self, name: str) -> str:
        """Sanitize string to valid JavaScript identifier"""
        import re
        name = re.sub(r'[^\w]', '_', name)
        name = re.sub(r'_+', '_', name)
        name = name.strip('_')
        # Ensure it doesn't start with a number
        if name and name[0].isdigit():
            name = '_' + name
        return name[:50] if name else "test"
