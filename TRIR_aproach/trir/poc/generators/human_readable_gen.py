"""
Human-Readable Generator for TRIR Specifications

Generates human-friendly documentation from TRIR JSON AST:
- ER diagrams (Mermaid)
- State transition diagrams (Mermaid)
- Flowcharts (Mermaid)
- Entity tables (Markdown)
- Japanese requirements text
"""

import json
from dataclasses import dataclass
from typing import Any


@dataclass
class HumanReadableOutput:
    """Generated human-readable documentation"""
    er_diagram: str
    state_diagrams: dict[str, str]
    flowcharts: dict[str, str]
    entity_tables: str
    field_tables: dict[str, str]
    requirements_text: str
    derived_explanations: str
    function_explanations: str
    scenario_table: str
    invariant_list: str


class HumanReadableGenerator:
    """Generate human-readable documentation from TRIR spec"""

    def __init__(self, spec: dict):
        self.spec = spec
        self.meta = spec.get("meta", {})
        self.state = spec.get("state", {})
        self.derived = spec.get("derived", {})
        self.functions = spec.get("functions", {})
        self.scenarios = spec.get("scenarios", {})
        self.invariants = spec.get("invariants", [])
        self.requirements = spec.get("requirements", {})

    def generate_all(self) -> HumanReadableOutput:
        """Generate all human-readable outputs"""
        return HumanReadableOutput(
            er_diagram=self.generate_er_diagram(),
            state_diagrams=self.generate_state_diagrams(),
            flowcharts=self.generate_flowcharts(),
            entity_tables=self.generate_entity_tables(),
            field_tables=self.generate_field_tables(),
            requirements_text=self.generate_requirements_text(),
            derived_explanations=self.generate_derived_explanations(),
            function_explanations=self.generate_function_explanations(),
            scenario_table=self.generate_scenario_table(),
            invariant_list=self.generate_invariant_list(),
        )

    # =========================================================================
    # ER Diagram Generation
    # =========================================================================

    def generate_er_diagram(self) -> str:
        """Generate Mermaid ER diagram"""
        lines = ["erDiagram"]

        # Collect relationships
        relationships = []
        for entity_name, entity in self.state.items():
            fields = entity.get("fields", {})
            for field_name, field in fields.items():
                field_type = field.get("type", {})
                if isinstance(field_type, dict) and "ref" in field_type:
                    ref_entity = field_type["ref"]
                    # Determine cardinality
                    required = field.get("required", True)
                    if required:
                        relationships.append(f"    {ref_entity} ||--o{{ {entity_name} : \"has\"")
                    else:
                        relationships.append(f"    {ref_entity} |o--o{{ {entity_name} : \"has\"")

        # Add unique relationships
        for rel in set(relationships):
            lines.append(rel)

        lines.append("")

        # Add entity definitions
        for entity_name, entity in self.state.items():
            desc = entity.get("description", entity_name)
            lines.append(f"    {entity_name} {{")

            fields = entity.get("fields", {})
            for field_name, field in fields.items():
                field_type = self._get_field_type_str(field.get("type", "string"))
                required = field.get("required", True)
                pk = " PK" if field_name in ["id", f"{entity_name}_id"] else ""
                fk = ""
                if isinstance(field.get("type"), dict) and "ref" in field.get("type", {}):
                    fk = " FK"

                req_mark = "" if required else " \"optional\""
                lines.append(f"        {field_type} {field_name}{pk}{fk}{req_mark}")

            lines.append("    }")

        return "\n".join(lines)

    def _get_field_type_str(self, field_type: Any) -> str:
        """Convert field type to string representation"""
        if isinstance(field_type, str):
            return field_type
        if isinstance(field_type, dict):
            if "ref" in field_type:
                return "ref"
            if "enum" in field_type:
                return "enum"
            if "list" in field_type:
                return "list"
        return "unknown"

    # =========================================================================
    # State Diagram Generation
    # =========================================================================

    def generate_state_diagrams(self) -> dict[str, str]:
        """Generate state transition diagrams for enum fields"""
        diagrams = {}

        for entity_name, entity in self.state.items():
            fields = entity.get("fields", {})
            for field_name, field in fields.items():
                field_type = field.get("type", {})
                if isinstance(field_type, dict) and "enum" in field_type:
                    enum_values = field_type["enum"]
                    if field_name == "status":
                        diagram = self._generate_status_diagram(entity_name, enum_values)
                        diagrams[f"{entity_name}.{field_name}"] = diagram

        return diagrams

    def _generate_status_diagram(self, entity_name: str, enum_values: list) -> str:
        """Generate status state diagram by analyzing functions"""
        lines = ["stateDiagram-v2"]

        # Find initial state
        if enum_values:
            lines.append(f"    [*] --> {enum_values[0]}")

        # Analyze functions for transitions
        transitions = self._find_transitions(entity_name, "status")
        for from_state, to_state, trigger in transitions:
            lines.append(f"    {from_state} --> {to_state} : {trigger}")

        # Mark final states
        for val in enum_values:
            if val.upper() in ["CLOSED", "COMPLETED", "CANCELLED", "DELETED", "ARCHIVED"]:
                lines.append(f"    {val} --> [*]")

        return "\n".join(lines)

    def _find_transitions(self, entity_name: str, field_name: str) -> list[tuple]:
        """Find state transitions from function definitions"""
        transitions = []

        for func_name, func in self.functions.items():
            # Check pre conditions for "from" states
            from_states = []
            for pre in func.get("pre", []):
                expr = pre.get("expr", {})
                states = self._extract_status_constraint(expr, entity_name, field_name)
                if states:
                    from_states.extend(states)

            # Check post actions for "to" states
            for post in func.get("post", []):
                action = post.get("action", {})
                if "update" in action:
                    update_entity = action["update"]
                    if update_entity == entity_name:
                        set_values = action.get("set", {})
                        if field_name in set_values:
                            to_val = set_values[field_name]
                            if isinstance(to_val, dict) and to_val.get("type") == "literal":
                                to_state = to_val["value"]
                                for from_state in from_states or ["*"]:
                                    transitions.append((from_state, to_state, func_name))

        return transitions

    def _extract_status_constraint(self, expr: dict, entity_name: str, field_name: str) -> list:
        """Extract status values from expression"""
        if not isinstance(expr, dict):
            return []

        expr_type = expr.get("type")

        if expr_type == "binary":
            op = expr.get("op")
            left = expr.get("left", {})
            right = expr.get("right", {})

            # Check if this is a status comparison
            if left.get("type") == "ref":
                path = left.get("path", "")
                if f"{entity_name}.{field_name}" in path or path.endswith(f".{field_name}"):
                    if op == "eq" and right.get("type") == "literal":
                        return [right.get("value")]
                    if op == "in" and right.get("type") == "list":
                        return [item.get("value") for item in right.get("items", [])
                                if item.get("type") == "literal"]

            # Recurse into AND conditions
            if op == "and":
                return self._extract_status_constraint(left, entity_name, field_name) + \
                       self._extract_status_constraint(right, entity_name, field_name)

        return []

    # =========================================================================
    # Flowchart Generation
    # =========================================================================

    def generate_flowcharts(self) -> dict[str, str]:
        """Generate flowcharts for functions"""
        flowcharts = {}

        for func_name, func in self.functions.items():
            flowchart = self._generate_function_flowchart(func_name, func)
            flowcharts[func_name] = flowchart

        return flowcharts

    def _generate_function_flowchart(self, func_name: str, func: dict) -> str:
        """Generate flowchart for a single function"""
        lines = ["flowchart TD"]
        lines.append(f"    Start([{func_name}])")

        node_id = 0
        prev_node = "Start"

        # Pre conditions
        for i, pre in enumerate(func.get("pre", [])):
            node_id += 1
            reason = pre.get("reason", f"Pre condition {i+1}")
            lines.append(f"    Pre{node_id}{{\"Check: {reason}\"}}")
            lines.append(f"    {prev_node} --> Pre{node_id}")
            prev_node = f"Pre{node_id}"

        # Error cases
        for i, err in enumerate(func.get("error", [])):
            node_id += 1
            code = err.get("code", f"ERROR_{i+1}")
            reason = err.get("reason", "")
            lines.append(f"    Err{node_id}{{\"Check: {reason}\"}}")
            lines.append(f"    {prev_node} --> Err{node_id}")
            lines.append(f"    Err{node_id} -->|No| ErrEnd{node_id}[/\"{code}\"/]")
            lines.append(f"    Err{node_id} -->|Yes| Next{node_id}")
            prev_node = f"Next{node_id}"

        # Post actions
        for i, post in enumerate(func.get("post", [])):
            node_id += 1
            action = post.get("action", {})
            action_desc = self._describe_action(action)

            condition = post.get("condition")
            if condition:
                cond_desc = self._describe_expr_short(condition)
                lines.append(f"    Cond{node_id}{{\"If: {cond_desc}\"}}")
                lines.append(f"    {prev_node} --> Cond{node_id}")
                lines.append(f"    Cond{node_id} -->|Yes| Act{node_id}[\"{action_desc}\"]")
                lines.append(f"    Cond{node_id} -->|No| Skip{node_id}[Skip]")
                lines.append(f"    Act{node_id} --> Merge{node_id}")
                lines.append(f"    Skip{node_id} --> Merge{node_id}")
                prev_node = f"Merge{node_id}"
            else:
                lines.append(f"    Act{node_id}[\"{action_desc}\"]")
                lines.append(f"    {prev_node} --> Act{node_id}")
                prev_node = f"Act{node_id}"

        lines.append(f"    Success([Success])")
        lines.append(f"    {prev_node} --> Success")

        return "\n".join(lines)

    def _describe_action(self, action: dict) -> str:
        """Describe an action in short text"""
        if "create" in action:
            return f"Create {action['create']}"
        if "update" in action:
            entity = action["update"]
            fields = list(action.get("set", {}).keys())
            return f"Update {entity}.{', '.join(fields[:2])}"
        if "delete" in action:
            return f"Delete {action['delete']}"
        return "Action"

    def _describe_expr_short(self, expr: dict) -> str:
        """Short description of expression"""
        if not isinstance(expr, dict):
            return str(expr)

        expr_type = expr.get("type")

        if expr_type == "binary":
            op = expr.get("op", "?")
            left = self._describe_expr_short(expr.get("left", {}))
            right = self._describe_expr_short(expr.get("right", {}))
            op_symbols = {"eq": "==", "ne": "!=", "lt": "<", "le": "<=", "gt": ">", "ge": ">="}
            return f"{left} {op_symbols.get(op, op)} {right}"

        if expr_type == "ref":
            return expr.get("path", "?").split(".")[-1]

        if expr_type == "literal":
            return str(expr.get("value", "?"))

        if expr_type == "self":
            return f"self.{expr.get('field', '?')}"

        return "..."

    # =========================================================================
    # Table Generation
    # =========================================================================

    def generate_entity_tables(self) -> str:
        """Generate entity overview table"""
        lines = ["# エンティティ一覧", ""]
        lines.append("| エンティティ | 説明 | フィールド数 | 関連先 | 関連元 |")
        lines.append("|-------------|------|------------|--------|--------|")

        # Build relationship map
        refs_to = {}  # entity -> [target entities]
        refs_from = {}  # entity -> [source entities]

        for entity_name, entity in self.state.items():
            refs_to[entity_name] = []
            refs_from.setdefault(entity_name, [])

            for field_name, field in entity.get("fields", {}).items():
                field_type = field.get("type", {})
                if isinstance(field_type, dict) and "ref" in field_type:
                    ref_entity = field_type["ref"]
                    refs_to[entity_name].append(ref_entity)
                    refs_from.setdefault(ref_entity, []).append(entity_name)

        for entity_name, entity in self.state.items():
            desc = entity.get("description", "-")
            field_count = len(entity.get("fields", {}))
            refs_to_str = ", ".join(refs_to.get(entity_name, [])) or "-"
            refs_from_str = ", ".join(refs_from.get(entity_name, [])) or "-"

            lines.append(f"| {entity_name} | {desc} | {field_count} | {refs_to_str} | {refs_from_str} |")

        return "\n".join(lines)

    def generate_field_tables(self) -> dict[str, str]:
        """Generate field definition tables for each entity"""
        tables = {}

        for entity_name, entity in self.state.items():
            lines = [f"# {entity_name} フィールド定義", ""]
            desc = entity.get("description", "")
            if desc:
                lines.append(f"> {desc}")
                lines.append("")

            lines.append("| フィールド | 型 | 必須 | 説明 | 参照先 |")
            lines.append("|-----------|-----|-----|------|--------|")

            for field_name, field in entity.get("fields", {}).items():
                field_type = field.get("type", "string")
                type_str = self._format_field_type(field_type)
                required = "Yes" if field.get("required", True) else "No"
                field_desc = field.get("description", "-")
                ref = "-"
                if isinstance(field_type, dict) and "ref" in field_type:
                    ref = field_type["ref"]

                lines.append(f"| {field_name} | {type_str} | {required} | {field_desc} | {ref} |")

            tables[entity_name] = "\n".join(lines)

        return tables

    def _format_field_type(self, field_type: Any) -> str:
        """Format field type for display"""
        if isinstance(field_type, str):
            return field_type
        if isinstance(field_type, dict):
            if "ref" in field_type:
                return f"ref({field_type['ref']})"
            if "enum" in field_type:
                values = field_type["enum"]
                if len(values) <= 4:
                    return f"enum({', '.join(values)})"
                return f"enum({len(values)} values)"
            if "list" in field_type:
                return f"list({field_type['list']})"
        return str(field_type)

    # =========================================================================
    # Requirements Text Generation
    # =========================================================================

    def generate_requirements_text(self) -> str:
        """Generate Japanese requirements text"""
        lines = ["# 要件定義書", ""]

        # Meta information
        if self.meta:
            lines.append("## 概要")
            lines.append("")
            lines.append(f"**システム名**: {self.meta.get('title', '-')}")
            lines.append(f"**バージョン**: {self.meta.get('version', '-')}")
            if "description" in self.meta:
                lines.append(f"**説明**: {self.meta['description']}")
            lines.append("")

        # Requirements
        if self.requirements:
            lines.append("## 要件一覧")
            lines.append("")

            for req_id, req in self.requirements.items():
                lines.append(f"### {req_id}: {req.get('title', '-')}")
                lines.append("")
                lines.append(f"**対象者**: {req.get('who', '-')}")
                lines.append(f"**目的**: {req.get('why', '-')}")
                lines.append(f"**内容**: {req.get('what', '-')}")
                lines.append("")

                # Acceptance criteria
                if "acceptance" in req:
                    lines.append("**受入条件**:")
                    lines.append("")
                    for ac_id, ac in req["acceptance"].items():
                        ac_desc = ac.get("description", "-")
                        lines.append(f"- {ac_id}: {ac_desc}")
                    lines.append("")

        return "\n".join(lines)

    # =========================================================================
    # Derived Explanations
    # =========================================================================

    def generate_derived_explanations(self) -> str:
        """Generate explanations for derived fields"""
        lines = ["# 計算フィールド定義", ""]

        for derived_name, derived in self.derived.items():
            entity = derived.get("entity", "-")
            desc = derived.get("description", "-")
            formula = derived.get("formula", {})

            lines.append(f"## {derived_name}")
            lines.append("")
            lines.append(f"**対象エンティティ**: {entity}")
            lines.append(f"**説明**: {desc}")
            lines.append("")
            lines.append("**計算ロジック**:")
            lines.append("")
            lines.append(self._explain_formula(formula, indent=0))
            lines.append("")

        return "\n".join(lines)

    def _explain_formula(self, formula: dict, indent: int = 0) -> str:
        """Explain a formula in Japanese"""
        prefix = "  " * indent

        if not isinstance(formula, dict):
            return f"{prefix}{formula}"

        expr_type = formula.get("type")

        if expr_type == "agg":
            op = formula.get("op", "?")
            from_entity = formula.get("from", "?")
            expr = formula.get("expr", {})
            where = formula.get("where", {})

            op_names = {
                "sum": "合計", "count": "件数", "avg": "平均",
                "min": "最小", "max": "最大", "exists": "存在確認"
            }
            op_name = op_names.get(op, op)

            result = f"{prefix}{from_entity}の{op_name}"
            if expr.get("type") == "ref":
                result += f"({expr.get('path', '?').split('.')[-1]})"
            if where:
                result += f"\n{prefix}  条件: {self._explain_condition(where)}"
            return result

        if expr_type == "binary":
            op = formula.get("op", "?")
            left = self._explain_formula(formula.get("left", {}), indent)
            right = self._explain_formula(formula.get("right", {}), indent)

            op_names = {
                "add": "+", "sub": "-", "mul": "×", "div": "÷",
                "eq": "=", "ne": "!=", "lt": "<", "le": "<=", "gt": ">", "ge": ">="
            }
            return f"{left} {op_names.get(op, op)} {right}"

        if expr_type == "ref":
            return formula.get("path", "?")

        if expr_type == "self":
            return f"self.{formula.get('field', '?')}"

        if expr_type == "literal":
            return str(formula.get("value", "?"))

        return f"{prefix}{expr_type}: ..."

    def _explain_condition(self, cond: dict) -> str:
        """Explain a condition in short form"""
        if not isinstance(cond, dict):
            return str(cond)

        expr_type = cond.get("type")

        if expr_type == "binary":
            op = cond.get("op")
            left = self._explain_condition(cond.get("left", {}))
            right = self._explain_condition(cond.get("right", {}))

            if op == "and":
                return f"{left} かつ {right}"
            if op == "eq":
                return f"{left} = {right}"

            return f"{left} {op} {right}"

        if expr_type == "ref":
            return cond.get("path", "?").split(".")[-1]

        if expr_type == "self":
            return f"自身の{cond.get('field', '?')}"

        if expr_type == "literal":
            return f"'{cond.get('value', '?')}'"

        return "..."

    # =========================================================================
    # Function Explanations
    # =========================================================================

    def generate_function_explanations(self) -> str:
        """Generate explanations for functions"""
        lines = ["# 機能定義", ""]

        for func_name, func in self.functions.items():
            desc = func.get("description", "-")

            lines.append(f"## {func_name}")
            lines.append("")
            lines.append(f"**説明**: {desc}")
            lines.append("")

            # Input
            if "input" in func:
                lines.append("**入力パラメータ**:")
                lines.append("")
                for param_name, param in func["input"].items():
                    param_type = self._format_field_type(param.get("type", "?"))
                    param_desc = param.get("description", "")
                    lines.append(f"- `{param_name}` ({param_type}): {param_desc}")
                lines.append("")

            # Pre conditions
            if func.get("pre"):
                lines.append("**事前条件**:")
                lines.append("")
                for pre in func["pre"]:
                    reason = pre.get("reason", "-")
                    lines.append(f"- {reason}")
                lines.append("")

            # Error cases
            if func.get("error"):
                lines.append("**エラーケース**:")
                lines.append("")
                for err in func["error"]:
                    code = err.get("code", "ERROR")
                    reason = err.get("reason", "-")
                    lines.append(f"- `{code}`: {reason}")
                lines.append("")

            # Post actions
            if func.get("post"):
                lines.append("**実行結果**:")
                lines.append("")
                for post in func["post"]:
                    action = post.get("action", {})
                    action_desc = self._describe_action_detail(action)
                    condition = post.get("condition")
                    if condition:
                        cond_desc = self._explain_condition(condition)
                        lines.append(f"- {action_desc} (条件: {cond_desc})")
                    else:
                        lines.append(f"- {action_desc}")
                lines.append("")

        return "\n".join(lines)

    def _describe_action_detail(self, action: dict) -> str:
        """Describe an action in detail"""
        if "create" in action:
            entity = action["create"]
            return f"{entity}レコードを作成"
        if "update" in action:
            entity = action["update"]
            fields = list(action.get("set", {}).keys())
            return f"{entity}の{', '.join(fields)}を更新"
        if "delete" in action:
            return f"{action['delete']}レコードを削除"
        return "アクション実行"

    # =========================================================================
    # Scenario Table
    # =========================================================================

    def generate_scenario_table(self) -> str:
        """Generate scenario overview table"""
        lines = ["# テストシナリオ一覧", ""]
        lines.append("| ID | タイトル | 対象機能 | 検証要件 | 期待結果 |")
        lines.append("|----|---------|---------|---------|---------|")

        for scenario_id, scenario in self.scenarios.items():
            title = scenario.get("title", "-")
            func = scenario.get("when", {}).get("call", "-")
            verifies = ", ".join(scenario.get("verifies", ["-"]))

            # Determine expected result
            then = scenario.get("then", {})
            if then.get("success"):
                result = "成功"
            elif then.get("error"):
                result = f"エラー: {then.get('error')}"
            else:
                result = "-"

            lines.append(f"| {scenario_id} | {title} | {func} | {verifies} | {result} |")

        return "\n".join(lines)

    # =========================================================================
    # Invariant List
    # =========================================================================

    def generate_invariant_list(self) -> str:
        """Generate invariant list"""
        lines = ["# 不変条件一覧", ""]

        for inv in self.invariants:
            inv_id = inv.get("id", "-")
            entity = inv.get("entity", "-")
            desc = inv.get("description", "-")
            severity = inv.get("severity", "error")

            lines.append(f"## {inv_id}")
            lines.append("")
            lines.append(f"**対象**: {entity}")
            lines.append(f"**説明**: {desc}")
            lines.append(f"**重要度**: {severity}")
            lines.append("")

        return "\n".join(lines)


def generate_markdown_bundle(spec: dict) -> str:
    """Generate a single markdown document with all sections"""
    gen = HumanReadableGenerator(spec)
    output = gen.generate_all()

    sections = []

    # Title
    title = spec.get("meta", {}).get("title", "TRIR Specification")
    sections.append(f"# {title}")
    sections.append("")
    sections.append("*このドキュメントはTRIR仕様から自動生成されました*")
    sections.append("")
    sections.append("---")
    sections.append("")

    # Requirements
    sections.append(output.requirements_text)
    sections.append("")
    sections.append("---")
    sections.append("")

    # Entity overview
    sections.append(output.entity_tables)
    sections.append("")
    sections.append("---")
    sections.append("")

    # ER Diagram
    sections.append("# ER図")
    sections.append("")
    sections.append("```mermaid")
    sections.append(output.er_diagram)
    sections.append("```")
    sections.append("")
    sections.append("---")
    sections.append("")

    # Field tables
    sections.append("# フィールド定義")
    sections.append("")
    for entity_name, table in output.field_tables.items():
        sections.append(table)
        sections.append("")
    sections.append("---")
    sections.append("")

    # Derived
    sections.append(output.derived_explanations)
    sections.append("")
    sections.append("---")
    sections.append("")

    # Functions
    sections.append(output.function_explanations)
    sections.append("")

    # Flowcharts
    sections.append("## フローチャート")
    sections.append("")
    for func_name, flowchart in output.flowcharts.items():
        sections.append(f"### {func_name}")
        sections.append("")
        sections.append("```mermaid")
        sections.append(flowchart)
        sections.append("```")
        sections.append("")
    sections.append("---")
    sections.append("")

    # State diagrams
    if output.state_diagrams:
        sections.append("# 状態遷移図")
        sections.append("")
        for key, diagram in output.state_diagrams.items():
            sections.append(f"## {key}")
            sections.append("")
            sections.append("```mermaid")
            sections.append(diagram)
            sections.append("```")
            sections.append("")
        sections.append("---")
        sections.append("")

    # Scenarios
    sections.append(output.scenario_table)
    sections.append("")
    sections.append("---")
    sections.append("")

    # Invariants
    sections.append(output.invariant_list)

    return "\n".join(sections)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python human_readable_gen.py <spec.trir.json> [output.md]")
        sys.exit(1)

    with open(sys.argv[1]) as f:
        spec = json.load(f)

    markdown = generate_markdown_bundle(spec)

    if len(sys.argv) >= 3:
        with open(sys.argv[2], "w") as f:
            f.write(markdown)
        print(f"Generated: {sys.argv[2]}")
    else:
        print(markdown)
