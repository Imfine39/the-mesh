"""Mesh Post-Condition Test Generator for Jest

specの定義（ref, parent等）を使用して依存関係を正しく解決する。
命名規則からの推測ではなく、specの明示的な定義を優先。
"""

from typing import Any
from dataclasses import dataclass

from ..spec_utils import (
    SpecAnalyzer,
    TestDataGenerator,
    MockContextGenerator,
    GenerationMarker,
)


@dataclass
class PostConditionTest:
    """Post-condition テストケース"""
    id: str
    description: str
    command: str
    action_type: str  # 'create', 'update', 'delete'
    target_entity: str
    inputs: dict[str, Any]
    expected_fields: dict[str, Any]
    required_context: list[dict]  # 依存エンティティのセットアップ
    generation_type: str  # 'auto', 'template', 'manual'
    todo_reason: str | None = None


class JestPostConditionGenerator:
    """Post-condition テストジェネレーター"""

    def __init__(self, spec: dict[str, Any]):
        self.spec = spec
        self.analyzer = SpecAnalyzer(spec)
        self.data_gen = TestDataGenerator(self.analyzer)
        self.mock_gen = MockContextGenerator(self.analyzer)

    def generate_all(self) -> str:
        """全コマンドのpost-conditionテストを生成"""
        tests = self._collect_tests()
        return self._render(tests)

    def generate_for_command(self, command_name: str) -> str:
        """特定コマンドのpost-conditionテストを生成"""
        tests = self._collect_tests(command_filter=command_name)
        return self._render(tests)

    def _collect_tests(self, command_filter: str | None = None) -> list[PostConditionTest]:
        """specからテストケースを収集"""
        tests = []

        for cmd_name, cmd_info in self.analyzer.get_all_commands().items():
            if command_filter and cmd_name != command_filter:
                continue

            for i, post in enumerate(cmd_info.post_actions):
                action = post.get("action", {})

                if "create" in action:
                    tests.append(self._create_test_for_create(cmd_name, cmd_info, action, i))
                elif "update" in action:
                    tests.append(self._create_test_for_update(cmd_name, cmd_info, action, i))
                elif "delete" in action:
                    tests.append(self._create_test_for_delete(cmd_name, cmd_info, action, i))

        return tests

    def _create_test_for_create(self, cmd_name: str, cmd_info, action: dict, index: int) -> PostConditionTest:
        """create アクションのテストを作成"""
        create_def = action["create"]
        target_entity = create_def.get("target") if isinstance(create_def, dict) else create_def
        data_def = create_def.get("data", {}) if isinstance(create_def, dict) else {}

        # 期待されるフィールドを解析（target_entityを渡してderived判定に使用）
        expected_fields, generation_type, todo_reason = self._analyze_expected_fields(data_def, target_entity)

        # 入力サンプルを生成
        inputs = self.data_gen.generate_input_sample(cmd_name)

        # 依存エンティティを生成（specのref/parentを使用）
        required_context = self._generate_required_context(cmd_name, target_entity)

        return PostConditionTest(
            id=f"pc-{cmd_name}-creates-{target_entity.lower()}",
            description=f"{cmd_name}: should create {target_entity} with specified fields",
            command=cmd_name,
            action_type="create",
            target_entity=target_entity,
            inputs=inputs,
            expected_fields=expected_fields,
            required_context=required_context,
            generation_type=generation_type,
            todo_reason=todo_reason,
        )

    def _create_test_for_update(self, cmd_name: str, cmd_info, action: dict, index: int) -> PostConditionTest:
        """update アクションのテストを作成"""
        update_def = action["update"]
        target_entity = update_def.get("target") if isinstance(update_def, dict) else update_def
        set_def = update_def.get("set", {}) if isinstance(update_def, dict) else {}

        expected_fields, generation_type, todo_reason = self._analyze_expected_fields(set_def, target_entity)
        inputs = self.data_gen.generate_input_sample(cmd_name)
        required_context = self._generate_required_context(cmd_name, target_entity, include_target=True)

        return PostConditionTest(
            id=f"pc-{cmd_name}-updates-{target_entity.lower()}",
            description=f"{cmd_name}: should update {target_entity} with specified fields",
            command=cmd_name,
            action_type="update",
            target_entity=target_entity,
            inputs=inputs,
            expected_fields=expected_fields,
            required_context=required_context,
            generation_type=generation_type,
            todo_reason=todo_reason,
        )

    def _create_test_for_delete(self, cmd_name: str, cmd_info, action: dict, index: int) -> PostConditionTest:
        """delete アクションのテストを作成"""
        delete_def = action["delete"]
        target_entity = delete_def.get("target") if isinstance(delete_def, dict) else delete_def

        inputs = self.data_gen.generate_input_sample(cmd_name)
        required_context = self._generate_required_context(cmd_name, target_entity, include_target=True)

        return PostConditionTest(
            id=f"pc-{cmd_name}-deletes-{target_entity.lower()}",
            description=f"{cmd_name}: should delete {target_entity}",
            command=cmd_name,
            action_type="delete",
            target_entity=target_entity,
            inputs=inputs,
            expected_fields={},
            required_context=required_context,
            generation_type=GenerationMarker.AUTO,
            todo_reason=None,
        )

    def _analyze_expected_fields(self, data_def: dict, target_entity: str = "") -> tuple[dict, str, str | None]:
        """期待されるフィールドを解析

        Returns:
            (expected_fields, generation_type, todo_reason)
        """
        expected = {}
        has_complex_expr = False
        complex_fields = []
        derived_fields = []

        for field_name, expr in data_def.items():
            # derivedフィールドかチェック
            if target_entity and self.analyzer.is_derived_field(target_entity, field_name):
                derived_info = self.analyzer.get_derived_info(target_entity, field_name)
                if derived_info and self.analyzer.is_simple_formula(derived_info.formula):
                    # シンプルな計算式は検証可能
                    expected[field_name] = {
                        "type": "derived_simple",
                        "formula": derived_info.formula
                    }
                else:
                    # 複雑な計算式（集約など）は存在のみ検証
                    expected[field_name] = {"type": "derived_complex"}
                    derived_fields.append(field_name)
                continue

            if not isinstance(expr, dict):
                expected[field_name] = {"type": "literal", "value": expr}
                continue

            expr_type = expr.get("type")

            if expr_type == "literal":
                expected[field_name] = {"type": "literal", "value": expr.get("value")}

            elif expr_type == "input":
                field = expr.get("field") or expr.get("name")
                expected[field_name] = {"type": "input", "field": field}

            elif expr_type in ("call", "binary", "ref"):
                # 計算式や参照は値の検証が困難
                expected[field_name] = {"type": "exists_only"}
                has_complex_expr = True
                complex_fields.append(field_name)

            else:
                expected[field_name] = {"type": "exists_only"}
                has_complex_expr = True
                complex_fields.append(field_name)

        if has_complex_expr or derived_fields:
            reasons = []
            if complex_fields:
                reasons.append(f"complex expressions: {', '.join(complex_fields)}")
            if derived_fields:
                reasons.append(f"derived fields (aggregation): {', '.join(derived_fields)}")
            return (
                expected,
                GenerationMarker.TEMPLATE,
                " | ".join(reasons)
            )

        return expected, GenerationMarker.AUTO, None

    def _generate_required_context(
        self,
        cmd_name: str,
        target_entity: str,
        include_target: bool = False
    ) -> list[dict]:
        """テスト実行に必要なコンテキストを生成

        specのref/parent情報を使用して依存関係を解決
        """
        context = []
        setup_entities = set()

        # ターゲットエンティティを最初にセットアップ（update/delete）
        # これにより is_target フラグが確実に付与される
        if include_target:
            entity_sample = self.data_gen.generate_entity_sample(target_entity)
            context.append({
                "entity": target_entity,
                "data": entity_sample,
                "is_target": True,
            })
            setup_entities.add(target_entity)

            # ターゲットが参照するエンティティも追加
            target_refs = self.analyzer.get_entity_references(target_entity)
            for field_name, ref_entity in target_refs:
                if ref_entity not in setup_entities:
                    ref_sample = self.data_gen.generate_entity_sample(ref_entity)
                    context.append({
                        "entity": ref_entity,
                        "data": ref_sample,
                    })
                    setup_entities.add(ref_entity)

        # コマンドの入力から参照されるエンティティ
        command = self.analyzer.get_command(cmd_name)
        if command:
            for field_name, field_info in command.inputs.items():
                # 明示的なrefか、xxxIdパターンからの推論
                ref_entity = field_info.ref
                if not ref_entity:
                    ref_entity = self.data_gen._infer_reference(field_name)

                if ref_entity and ref_entity not in setup_entities:
                    entity_sample = self.data_gen.generate_entity_sample(ref_entity)
                    context.append({
                        "entity": ref_entity,
                        "data": entity_sample,
                    })
                    setup_entities.add(ref_entity)

                    # 子エンティティも追加（親エンティティの場合）
                    parent_entity = self.analyzer.get_entity(ref_entity)
                    if parent_entity:
                        for child_name in parent_entity.children:
                            if child_name not in setup_entities:
                                child_sample = self.data_gen.generate_entity_sample(child_name)
                                context.append({
                                    "entity": child_name,
                                    "data": child_sample,
                                })
                                setup_entities.add(child_name)

        return context

    def _render(self, tests: list[PostConditionTest]) -> str:
        """テストコードを生成"""
        lines = [
            "// @ts-nocheck",
            "/**",
            " * Auto-generated Post-Condition Tests from TRIR specification",
            " *",
            " * Tests verify that function implementations perform",
            " * the side effects (create/update/delete) specified in the spec.",
            " *",
            " * @generated by the-mesh",
            " */",
            "",
            "import { describe, it, expect, jest, beforeEach } from '@jest/globals';",
            "",
        ]

        # Import implementations
        commands = {t.command for t in tests}
        for cmd in sorted(commands):
            lines.append(f"import {{ {cmd} }} from '../../../src/{cmd}';")
        lines.append("")

        # MockContext interface and factory
        lines.append("// ========== Mock Context ==========")
        lines.append("")
        lines.append(self.mock_gen.generate_interface())
        lines.append("")
        lines.append(self.mock_gen.generate_factory())
        lines.append("")

        # Group tests by command
        by_command: dict[str, list[PostConditionTest]] = {}
        for test in tests:
            if test.command not in by_command:
                by_command[test.command] = []
            by_command[test.command].append(test)

        # Generate test suites
        lines.append("// ========== Post-Condition Tests ==========")
        lines.append("")

        for cmd_name, cmd_tests in by_command.items():
            lines.append(f"describe('PostCondition: {cmd_name}', () => {{")
            lines.append("  let ctx: ReturnType<typeof createMockContext>;")
            lines.append("")
            lines.append("  beforeEach(() => {")
            lines.append("    ctx = createMockContext();")
            lines.append("  });")

            for test in cmd_tests:
                lines.extend(self._render_test(test))

            lines.append("});")
            lines.append("")

        return "\n".join(lines)

    def _render_test(self, test: PostConditionTest) -> list[str]:
        """単一のテストを生成"""
        lines = []
        repo_name = f"{test.target_entity[0].lower()}{test.target_entity[1:]}Repository"

        # Generation marker
        marker = GenerationMarker.format_marker(test.generation_type, test.todo_reason)
        lines.append("")
        lines.append(f"  {marker}")

        if test.generation_type == GenerationMarker.TEMPLATE:
            lines.append(f"  {GenerationMarker.format_todo(test.todo_reason or 'Manual implementation required')}")

        lines.append(f"  it('{test.description}', async () => {{")

        # Arrange
        lines.append("    // Arrange")
        lines.append(f"    const inputData = {self._to_js(test.inputs)};")

        # Context setup (依存エンティティ)
        for ctx_item in test.required_context:
            entity = ctx_item["entity"]
            data = ctx_item["data"]
            is_target = ctx_item.get("is_target", False)

            if is_target:
                lines.append(f"    const existing = {self._to_js(data)};")
                lines.append(f"    ctx._set{entity}(existing);")
            else:
                lines.append(f"    ctx._set{entity}({self._to_js(data)});")

        lines.append("")

        # Act
        lines.append("    // Act")
        lines.append(f"    await {test.command}(inputData, ctx);")
        lines.append("")

        # Assert
        lines.append("    // Assert")
        lines.extend(self._render_assertions(test, repo_name))

        lines.append("  });")

        return lines

    def _render_assertions(self, test: PostConditionTest, repo_name: str) -> list[str]:
        """アサーションを生成"""
        lines = []

        if test.action_type == "create":
            lines.append(f"    expect(ctx.{repo_name}.create).toHaveBeenCalledTimes(1);")
            lines.append(f"    const callArgs = ctx.{repo_name}.create.mock.calls[0][0];")
            lines.append("")

            for field, expected in test.expected_fields.items():
                lines.append(f'    expect(callArgs).toHaveProperty("{field}");')

                if expected["type"] == "literal":
                    value = expected["value"]
                    lines.append(f"    expect(callArgs.{field}).toBe({self._to_js_value(value)});")

                elif expected["type"] == "input":
                    input_field = expected["field"]
                    lines.append(f"    expect(callArgs.{field}).toBe(inputData.{input_field});")

                elif expected["type"] == "derived_simple":
                    # シンプルな計算式は検証可能 (e.g., quantity * unitPrice)
                    formula = expected["formula"]
                    expr = self._formula_to_js_expr(formula, "callArgs")
                    lines.append(f"    expect(callArgs.{field}).toBe({expr});")

                elif expected["type"] == "derived_complex":
                    # 集約などの複雑な計算は存在のみ検証
                    lines.append(f"    // derived field with aggregation - verify type only")
                    lines.append(f"    expect(typeof callArgs.{field}).toBe('number');")

                # exists_only: フィールド存在のみ検証（値は検証しない）

        elif test.action_type == "update":
            lines.append(f"    expect(ctx.{repo_name}.update).toHaveBeenCalledTimes(1);")
            lines.append(f"    const [updateId, updateData] = ctx.{repo_name}.update.mock.calls[0];")
            lines.append("")

            for field, expected in test.expected_fields.items():
                lines.append(f'    expect(updateData).toHaveProperty("{field}");')

                if expected["type"] == "literal":
                    value = expected["value"]
                    lines.append(f"    expect(updateData.{field}).toBe({self._to_js_value(value)});")

                elif expected["type"] == "input":
                    input_field = expected["field"]
                    lines.append(f"    expect(updateData.{field}).toBe(inputData.{input_field});")

                elif expected["type"] == "derived_simple":
                    formula = expected["formula"]
                    expr = self._formula_to_js_expr(formula, "updateData")
                    lines.append(f"    expect(updateData.{field}).toBe({expr});")

                elif expected["type"] == "derived_complex":
                    lines.append(f"    // derived field with aggregation - verify type only")
                    lines.append(f"    expect(typeof updateData.{field}).toBe('number');")

        elif test.action_type == "delete":
            lines.append(f"    expect(ctx.{repo_name}.delete).toHaveBeenCalledTimes(1);")
            lines.append(f"    expect(ctx.{repo_name}.delete).toHaveBeenCalledWith(existing.id);")

        return lines

    def _formula_to_js_expr(self, formula: dict, context_var: str) -> str:
        """TRIR formulaをJavaScript式に変換"""
        formula_type = formula.get("type")

        if formula_type == "literal":
            return self._to_js_value(formula.get("value"))

        if formula_type == "self":
            field = formula.get("field")
            return f"{context_var}.{field}"

        if formula_type == "binary":
            left = self._formula_to_js_expr(formula.get("left", {}), context_var)
            right = self._formula_to_js_expr(formula.get("right", {}), context_var)
            op = formula.get("op")
            op_map = {"add": "+", "sub": "-", "mul": "*", "div": "/", "mod": "%"}
            js_op = op_map.get(op, "+")
            return f"({left} {js_op} {right})"

        return "/* unknown formula */"

    def _to_js(self, obj: dict) -> str:
        """dict を JavaScript オブジェクトリテラルに変換"""
        items = [f"{k}: {self._to_js_value(v)}" for k, v in obj.items()]
        return "{ " + ", ".join(items) + " }"

    def _to_js_value(self, val: Any) -> str:
        """値を JavaScript 値に変換"""
        if val is None:
            return "null"
        if isinstance(val, bool):
            return "true" if val else "false"
        if isinstance(val, str):
            return f'"{val}"'
        if isinstance(val, (int, float)):
            return str(val)
        if isinstance(val, dict):
            return self._to_js(val)
        if isinstance(val, list):
            return "[" + ", ".join(self._to_js_value(v) for v in val) + "]"
        return str(val)
