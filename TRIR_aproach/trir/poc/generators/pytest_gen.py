"""TRIR to pytest Generator"""

from typing import Any


class PytestGenerator:
    """Generates pytest code from TRIR scenarios"""

    def __init__(self, spec: dict[str, Any]):
        self.spec = spec
        self.entities = spec.get("state", {})
        self.derived = spec.get("derived", {})
        self.functions = spec.get("functions", {})
        self.scenarios = spec.get("scenarios", {})
        self.invariants = spec.get("invariants", [])

    def generate_all(self) -> str:
        """Generate pytest code for all scenarios"""
        lines = [
            '"""Auto-generated tests from TRIR specification"""',
            "",
            "import pytest",
            "from typing import Any",
            "",
            "",
            "# ========== Test Fixtures ==========",
            "",
            self._generate_fixtures(),
            "",
            "# ========== Helper Functions ==========",
            "",
            self._generate_helpers(),
            "",
            "# ========== Scenario Tests ==========",
            "",
        ]

        for scenario_id, scenario in self.scenarios.items():
            lines.append(self._generate_scenario_test(scenario_id, scenario))
            lines.append("")

        lines.append("# ========== Invariant Tests ==========")
        lines.append("")
        lines.append(self._generate_invariant_tests())

        return "\n".join(lines)

    def generate_for_function(self, function_name: str) -> str:
        """Generate pytest code for scenarios testing a specific function"""
        relevant_scenarios = {
            sid: s for sid, s in self.scenarios.items()
            if s.get("when", {}).get("call") == function_name
        }

        relevant_invariants = []
        func = self.functions.get(function_name, {})
        # Get entities modified by this function
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
            f'"""Auto-generated tests for {function_name}"""',
            "",
            "import pytest",
            "from typing import Any",
            "",
            "",
            "# ========== Test Fixtures ==========",
            "",
            self._generate_fixtures(),
            "",
            "# ========== Helper Functions ==========",
            "",
            self._generate_helpers(),
            "",
            f"# ========== Tests for {function_name} ==========",
            "",
        ]

        for scenario_id, scenario in relevant_scenarios.items():
            lines.append(self._generate_scenario_test(scenario_id, scenario))
            lines.append("")

        if relevant_invariants:
            lines.append("# ========== Invariant Checks ==========")
            lines.append("")
            for inv in relevant_invariants:
                lines.append(self._generate_single_invariant_test(inv))
                lines.append("")

        return "\n".join(lines)

    def _generate_fixtures(self) -> str:
        """Generate pytest fixtures for entities"""
        lines = []

        for entity_name, entity in self.entities.items():
            lines.append(f"@pytest.fixture")
            lines.append(f"def create_{entity_name}(db):")
            lines.append(f'    """Create a {entity_name} instance"""')
            lines.append(f"    def _create(**kwargs):")

            # Generate default values
            fields = entity.get("fields", {})
            defaults = []
            for field_name, field_def in fields.items():
                default = self._get_default_value(field_name, field_def)
                defaults.append(f'        {field_name} = kwargs.get("{field_name}", {default})')

            lines.extend(defaults)
            lines.append(f"        return db.create_{entity_name}(")
            for field_name in fields.keys():
                lines.append(f"            {field_name}={field_name},")
            lines.append("        )")
            lines.append("    return _create")
            lines.append("")

        return "\n".join(lines)

    def _generate_helpers(self) -> str:
        """Generate helper functions for derived values"""
        lines = []

        for name, derived in self.derived.items():
            entity = derived.get("entity", "")
            lines.append(f"def {name}({entity}: Any) -> Any:")
            lines.append(f'    """')
            lines.append(f'    {derived.get("description", f"Calculate {name}")}')
            lines.append(f'    """')
            lines.append(f"    # TODO: Implement based on formula")
            lines.append(f"    # Formula: {self._expr_to_pseudo(derived.get('formula', {}))}")
            lines.append(f"    raise NotImplementedError()")
            lines.append("")

        return "\n".join(lines)

    def _generate_scenario_test(self, scenario_id: str, scenario: dict) -> str:
        """Generate a single test from a scenario"""
        lines = []

        # Function name from id
        safe_id = scenario_id.lower().replace("-", "_")
        title = scenario.get("title", "").replace(" ", "_").replace("が", "_").replace("で", "_").replace("する", "")

        lines.append(f"def test_{safe_id}_{self._sanitize_name(title)}(")

        # Add fixtures for entities in given
        given = scenario.get("given", {})
        fixture_args = []
        for entity_name in given.keys():
            if entity_name in self.entities:
                fixture_args.append(f"create_{entity_name}")
        fixture_args.append("db")
        lines.append(f"    {', '.join(fixture_args)}")
        lines.append("):")

        lines.append(f'    """')
        lines.append(f'    {scenario.get("title", scenario_id)}')
        if scenario.get("verifies"):
            lines.append(f'    Verifies: {", ".join(scenario["verifies"])}')
        lines.append(f'    """')

        # Given
        lines.append("    # Given")
        for entity_name, data in given.items():
            if entity_name not in self.entities:
                continue
            if isinstance(data, list):
                for i, item in enumerate(data):
                    lines.append(f"    {entity_name}_{i} = create_{entity_name}(**{repr(item)})")
            elif isinstance(data, dict):
                lines.append(f"    {entity_name} = create_{entity_name}(**{repr(data)})")

        lines.append("")

        # When
        when = scenario.get("when", {})
        func_name = when.get("call", "unknown")
        input_data = when.get("input", {})

        lines.append("    # When")
        lines.append(f"    result = {func_name}(")
        for key, value in input_data.items():
            lines.append(f"        {key}={repr(value)},")
        lines.append("    )")
        lines.append("")

        # Then
        then = scenario.get("then", {})
        lines.append("    # Then")

        if then.get("success") is True:
            lines.append("    assert result.success is True")
        elif then.get("success") is False:
            lines.append("    assert result.success is False")
            if "error" in then:
                lines.append(f'    assert result.error == "{then["error"]}"')

        for i, assertion in enumerate(then.get("assert", [])):
            lines.append(f"    # Assertion {i + 1}: {self._expr_to_pseudo(assertion)}")
            lines.append(f"    {self._generate_assertion(assertion)}")

        return "\n".join(lines)

    def _generate_invariant_tests(self) -> str:
        """Generate tests for all invariants"""
        if not self.invariants:
            return "# No invariants defined"

        lines = []
        for inv in self.invariants:
            lines.append(self._generate_single_invariant_test(inv))
            lines.append("")

        return "\n".join(lines)

    def _generate_single_invariant_test(self, inv: dict) -> str:
        """Generate test for a single invariant"""
        inv_id = inv.get("id", "unknown").lower().replace("-", "_")
        entity = inv.get("entity", "entity")

        lines = [
            f"def test_invariant_{inv_id}(db, create_{entity}):",
            f'    """',
            f'    Invariant: {inv.get("description", inv_id)}',
            f'    """',
            f"    # Get all {entity} instances",
            f"    for {entity} in db.get_all_{entity}():",
            f"        # Check: {self._expr_to_pseudo(inv.get('expr', {}))}",
            f"        {self._generate_invariant_check(inv.get('expr', {}), entity)}",
        ]

        return "\n".join(lines)

    def _generate_assertion(self, expr: dict) -> str:
        """Generate Python assertion from expression"""
        return f"assert {self._expr_to_python(expr)}"

    def _generate_invariant_check(self, expr: dict, entity_var: str) -> str:
        """Generate Python code for invariant check"""
        return f"assert {self._expr_to_python(expr, entity_var)}"

    def _expr_to_python(self, expr: dict, entity_var: str = "") -> str:
        """Convert TRIR expression to Python code (Tagged Union format)"""
        if not isinstance(expr, dict):
            return repr(expr)

        expr_type = expr.get("type")

        # Literal: { "type": "literal", "value": ... }
        if expr_type == "literal":
            return repr(expr.get("value"))

        # Self reference: { "type": "self", "field": "..." }
        if expr_type == "self":
            field = expr.get("field", "")
            if entity_var:
                return f"{entity_var}.{field}" if field else entity_var
            return f"self.{field}" if field else "self"

        # Field reference: { "type": "ref", "path": "entity.field" }
        if expr_type == "ref":
            return expr.get("path", "").replace(".", "_")

        # Input reference: { "type": "input", "name": "..." }
        if expr_type == "input":
            return expr.get("name", "")

        # Function call: { "type": "call", "name": "fn", "args": [...] }
        if expr_type == "call":
            func = expr.get("name", "")
            args = expr.get("args", [])
            args_str = ", ".join(self._expr_to_python(a, entity_var) for a in args)
            return f"{func}({args_str})"

        # Binary operation: { "type": "binary", "op": "add", "left": ..., "right": ... }
        if expr_type == "binary":
            op_map = {
                "eq": "==", "ne": "!=", "lt": "<", "le": "<=", "gt": ">", "ge": ">=",
                "add": "+", "sub": "-", "mul": "*", "div": "/", "mod": "%",
                "and": "and", "or": "or"
            }
            op = op_map.get(expr.get("op", ""), expr.get("op", ""))
            left = self._expr_to_python(expr.get("left", {}), entity_var)
            right = self._expr_to_python(expr.get("right", {}), entity_var)
            return f"({left} {op} {right})"

        # Unary operation: { "type": "unary", "op": "not", "expr": ... }
        if expr_type == "unary":
            op_map = {"not": "not ", "neg": "-", "is_null": " is None", "is_not_null": " is not None"}
            op = expr.get("op", "")
            inner = self._expr_to_python(expr.get("expr", {}), entity_var)
            if op in ("is_null", "is_not_null"):
                return f"({inner}{op_map[op]})"
            return f"({op_map.get(op, op)}{inner})"

        # Aggregation: { "type": "agg", "op": "sum", "from": "entity", ... }
        if expr_type == "agg":
            agg_op = expr.get("op", "")
            from_entity = expr.get("from", "items")
            agg_expr = expr.get("expr", {})

            if agg_op == "sum":
                return f"sum(item.{self._get_agg_field(agg_expr)} for item in {from_entity}_list)"
            elif agg_op == "count":
                return f"len({from_entity}_list)"
            elif agg_op == "exists":
                return f"any({from_entity}_list)"
            elif agg_op == "avg":
                field = self._get_agg_field(agg_expr)
                return f"(sum(item.{field} for item in {from_entity}_list) / len({from_entity}_list))"
            elif agg_op == "min":
                return f"min(item.{self._get_agg_field(agg_expr)} for item in {from_entity}_list)"
            elif agg_op == "max":
                return f"max(item.{self._get_agg_field(agg_expr)} for item in {from_entity}_list)"

        # If-then-else: { "type": "if", "cond": ..., "then": ..., "else": ... }
        if expr_type == "if":
            cond = self._expr_to_python(expr.get("cond", {}), entity_var)
            then = self._expr_to_python(expr.get("then", {}), entity_var)
            else_ = self._expr_to_python(expr.get("else", {}), entity_var)
            return f"({then} if {cond} else {else_})"

        # Case expression: { "type": "case", "branches": [...], "else": ... }
        if expr_type == "case":
            # Convert to nested if-else
            result = self._expr_to_python(expr.get("else", {}), entity_var)
            for branch in reversed(expr.get("branches", [])):
                cond = self._expr_to_python(branch.get("when", {}), entity_var)
                then = self._expr_to_python(branch.get("then", {}), entity_var)
                result = f"({then} if {cond} else {result})"
            return result

        return f"/* {expr} */"

    def _get_agg_field(self, expr: dict) -> str:
        """Extract field name from aggregation expression (Tagged Union format)"""
        if expr.get("type") == "ref":
            parts = expr.get("path", "").split(".")
            return parts[-1] if len(parts) > 1 else parts[0]
        return "value"

    def _expr_to_pseudo(self, expr: dict) -> str:
        """Convert expression to pseudo-code for comments (Tagged Union format)"""
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
        """Get default value for a field"""
        field_type = field_def.get("type")

        if isinstance(field_type, str):
            defaults = {
                "string": f'"{field_name.upper()}-001"',
                "int": "0",
                "float": "0.0",
                "bool": "False",
                "datetime": '"2024-01-01T00:00:00Z"',
                "text": '""'
            }
            return defaults.get(field_type, "None")

        if isinstance(field_type, dict):
            if "enum" in field_type:
                return repr(field_type["enum"][0])
            if "ref" in field_type:
                return f'"{field_type["ref"].upper()}-001"'

        return "None"

    def _sanitize_name(self, name: str) -> str:
        """Sanitize string to valid Python identifier"""
        import re
        # Remove non-ASCII and special characters
        name = re.sub(r'[^\w]', '_', name)
        name = re.sub(r'_+', '_', name)
        name = name.strip('_').lower()
        return name[:50] if name else "test"
