"""
Spec Utilities for Test Generators

specから情報を正しく取得するための共通ユーティリティ。
命名規則からの推測ではなく、specの定義を使用する。
"""

from typing import Any
from dataclasses import dataclass, field


@dataclass
class FieldInfo:
    """エンティティフィールドの情報"""
    name: str
    type: str
    required: bool = False
    ref: str | None = None  # 参照先エンティティ
    enum: list[str] | None = None
    min: float | None = None
    max: float | None = None
    description: str | None = None


@dataclass
class EntityInfo:
    """エンティティの情報"""
    name: str
    fields: dict[str, FieldInfo] = field(default_factory=dict)
    parent: str | None = None  # 親エンティティ
    children: list[str] = field(default_factory=list)  # 子エンティティ
    description: str | None = None


@dataclass
class CommandInfo:
    """コマンド（関数）の情報"""
    name: str
    entity: str | None = None
    inputs: dict[str, FieldInfo] = field(default_factory=dict)
    outputs: dict[str, FieldInfo] = field(default_factory=dict)
    pre_conditions: list[dict] = field(default_factory=list)
    post_actions: list[dict] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)
    description: str | None = None


@dataclass
class ScenarioInfo:
    """シナリオの情報"""
    name: str
    given: list[dict] = field(default_factory=list)
    when: dict = field(default_factory=dict)
    then: list[dict] = field(default_factory=list)
    description: str | None = None


@dataclass
class DerivedFieldInfo:
    """計算フィールド（derived）の情報"""
    entity: str
    field: str
    formula: dict  # TRIR Expression
    key: str  # "Entity.field" 形式のキー


class SpecAnalyzer:
    """TRIR Specを解析してテスト生成に必要な情報を提供"""

    def __init__(self, spec: dict[str, Any]):
        self.spec = spec
        self._entities: dict[str, EntityInfo] = {}
        self._commands: dict[str, CommandInfo] = {}
        self._scenarios: dict[str, ScenarioInfo] = {}
        self._derived: dict[str, DerivedFieldInfo] = {}  # "Entity.field" -> DerivedFieldInfo
        self._analyze()

    def _analyze(self):
        """specを解析して構造化データを作成"""
        self._analyze_entities()
        self._analyze_commands()
        self._analyze_scenarios()
        self._analyze_derived()
        self._resolve_relationships()

    def _analyze_entities(self):
        """entities セクションを解析"""
        entities = self.spec.get("entities", {})
        for name, entity_def in entities.items():
            entity = EntityInfo(
                name=name,
                parent=entity_def.get("parent"),
                description=entity_def.get("description"),
            )

            for field_name, field_def in entity_def.get("fields", {}).items():
                if isinstance(field_def, dict):
                    entity.fields[field_name] = FieldInfo(
                        name=field_name,
                        type=field_def.get("type", "string"),
                        required=field_def.get("required", False),
                        ref=field_def.get("ref"),
                        enum=field_def.get("enum"),
                        min=field_def.get("min"),
                        max=field_def.get("max"),
                        description=field_def.get("description"),
                    )
                else:
                    # シンプルな型定義 (e.g., "id": "string")
                    entity.fields[field_name] = FieldInfo(
                        name=field_name,
                        type=field_def if isinstance(field_def, str) else "string",
                    )

            self._entities[name] = entity

    def _analyze_commands(self):
        """commands セクションを解析"""
        commands = self.spec.get("commands", {})
        for name, cmd_def in commands.items():
            command = CommandInfo(
                name=name,
                entity=cmd_def.get("entity"),
                description=cmd_def.get("description"),
                pre_conditions=cmd_def.get("pre", []),
                post_actions=cmd_def.get("post", []),
                errors=cmd_def.get("errors", []),
            )

            # Input fields
            for field_name, field_def in cmd_def.get("input", {}).items():
                if isinstance(field_def, dict):
                    command.inputs[field_name] = FieldInfo(
                        name=field_name,
                        type=field_def.get("type", "string"),
                        required=field_def.get("required", False),
                        ref=field_def.get("ref"),
                        min=field_def.get("min"),
                        max=field_def.get("max"),
                    )
                else:
                    command.inputs[field_name] = FieldInfo(
                        name=field_name,
                        type=field_def if isinstance(field_def, str) else "string",
                    )

            # Output fields
            for field_name, field_def in cmd_def.get("output", {}).items():
                if isinstance(field_def, dict):
                    command.outputs[field_name] = FieldInfo(
                        name=field_name,
                        type=field_def.get("type", "string"),
                    )

            self._commands[name] = command

    def _analyze_scenarios(self):
        """scenarios セクションを解析"""
        scenarios = self.spec.get("scenarios", {})
        for name, scenario_def in scenarios.items():
            self._scenarios[name] = ScenarioInfo(
                name=name,
                given=scenario_def.get("given", []),
                when=scenario_def.get("when", {}),
                then=scenario_def.get("then", []),
                description=scenario_def.get("description"),
            )

    def _analyze_derived(self):
        """derived セクションを解析"""
        derived = self.spec.get("derived", {})
        for key, derived_def in derived.items():
            # "Entity.field" 形式のキーを解析
            if isinstance(derived_def, dict):
                entity = derived_def.get("entity", "")
                field_name = derived_def.get("field", "")
                formula = derived_def.get("formula", {})
            else:
                # 文字列の場合（未変換の式）
                if "." in key:
                    entity, field_name = key.split(".", 1)
                else:
                    entity, field_name = "", key
                formula = {"type": "raw", "expr": str(derived_def)}

            self._derived[key] = DerivedFieldInfo(
                entity=entity,
                field=field_name,
                formula=formula,
                key=key,
            )

    def _resolve_relationships(self):
        """エンティティ間の関係を解決（親子関係など）"""
        for entity in self._entities.values():
            if entity.parent and entity.parent in self._entities:
                self._entities[entity.parent].children.append(entity.name)

    # ========== Public API ==========

    def get_entity(self, name: str) -> EntityInfo | None:
        """エンティティ情報を取得"""
        return self._entities.get(name)

    def get_all_entities(self) -> dict[str, EntityInfo]:
        """全エンティティを取得"""
        return self._entities

    def get_command(self, name: str) -> CommandInfo | None:
        """コマンド情報を取得"""
        return self._commands.get(name)

    def get_all_commands(self) -> dict[str, CommandInfo]:
        """全コマンドを取得"""
        return self._commands

    def get_scenario(self, name: str) -> ScenarioInfo | None:
        """シナリオ情報を取得"""
        return self._scenarios.get(name)

    def get_scenarios_for_command(self, command_name: str) -> list[ScenarioInfo]:
        """特定のコマンドに関連するシナリオを取得"""
        return [
            s for s in self._scenarios.values()
            if s.when.get("command") == command_name
        ]

    def get_entity_references(self, entity_name: str) -> list[tuple[str, str]]:
        """エンティティが参照する他エンティティを取得

        Returns:
            list of (field_name, referenced_entity_name)
        """
        entity = self._entities.get(entity_name)
        if not entity:
            return []

        refs = []
        for field_name, field_info in entity.fields.items():
            if field_info.ref:
                refs.append((field_name, field_info.ref))
        return refs

    def get_referencing_entities(self, entity_name: str) -> list[tuple[str, str]]:
        """このエンティティを参照している他エンティティを取得

        Returns:
            list of (referencing_entity_name, field_name)
        """
        refs = []
        for other_name, other_entity in self._entities.items():
            for field_name, field_info in other_entity.fields.items():
                if field_info.ref == entity_name:
                    refs.append((other_name, field_name))
        return refs

    def get_post_action_entities(self, command_name: str) -> set[str]:
        """コマンドの post アクションで操作されるエンティティを取得"""
        command = self._commands.get(command_name)
        if not command:
            return set()

        entities = set()
        for post in command.post_actions:
            action = post.get("action", {})
            for action_type in ("create", "update", "delete"):
                if action_type in action:
                    action_def = action[action_type]
                    if isinstance(action_def, dict):
                        target = action_def.get("target")
                        if target:
                            entities.add(target)
                    elif isinstance(action_def, str):
                        entities.add(action_def)
        return entities

    def get_required_dependencies(self, command_name: str) -> set[str]:
        """コマンド実行に必要な依存エンティティを取得

        入力フィールドの ref と、post アクションのターゲットの依存を解析
        """
        command = self._commands.get(command_name)
        if not command:
            return set()

        deps = set()

        # 入力フィールドの参照先
        for field_info in command.inputs.values():
            if field_info.ref:
                deps.add(field_info.ref)

        # Post アクションのターゲットの依存
        for entity_name in self.get_post_action_entities(command_name):
            entity = self._entities.get(entity_name)
            if entity:
                # エンティティの参照先も依存
                for _, ref_entity in self.get_entity_references(entity_name):
                    deps.add(ref_entity)

        return deps

    # ========== Derived Fields API ==========

    def is_derived_field(self, entity_name: str, field_name: str) -> bool:
        """フィールドが計算フィールド（derived）かどうかを判定"""
        key = f"{entity_name}.{field_name}"
        return key in self._derived

    def get_derived_info(self, entity_name: str, field_name: str) -> DerivedFieldInfo | None:
        """計算フィールドの情報を取得"""
        key = f"{entity_name}.{field_name}"
        return self._derived.get(key)

    def get_all_derived(self) -> dict[str, DerivedFieldInfo]:
        """全ての計算フィールドを取得"""
        return self._derived

    def get_derived_for_entity(self, entity_name: str) -> list[DerivedFieldInfo]:
        """特定エンティティの計算フィールドを取得"""
        return [d for d in self._derived.values() if d.entity == entity_name]

    def is_simple_formula(self, formula: dict) -> bool:
        """formulaがシンプルな計算（テストで検証可能）かどうかを判定

        シンプルな計算:
        - self.field * self.field (同一エンティティ内のフィールド演算)
        - リテラル値との演算

        複雑な計算:
        - 集約関数（sum, count, avg等）
        - 他エンティティへの参照
        - 条件分岐
        """
        if not isinstance(formula, dict):
            return False

        formula_type = formula.get("type")

        if formula_type == "literal":
            return True

        if formula_type == "self":
            return True

        if formula_type == "binary":
            # 両辺がシンプルならシンプル
            left = formula.get("left", {})
            right = formula.get("right", {})
            return self.is_simple_formula(left) and self.is_simple_formula(right)

        # agg, ref, call, if 等は複雑
        return False


class TestDataGenerator:
    """テストデータを生成するユーティリティ"""

    def __init__(self, analyzer: SpecAnalyzer):
        self.analyzer = analyzer

    def generate_entity_sample(self, entity_name: str, overrides: dict | None = None) -> dict:
        """エンティティのサンプルデータを生成

        Args:
            entity_name: エンティティ名
            overrides: 上書きするフィールド値

        Returns:
            サンプルデータ（dict）
        """
        entity = self.analyzer.get_entity(entity_name)
        if not entity:
            return {"id": f"{entity_name.upper()}-001"}

        sample = {}
        for field_name, field_info in entity.fields.items():
            sample[field_name] = self._generate_field_value(field_info, entity_name)

        if overrides:
            sample.update(overrides)

        return sample

    def _generate_field_value(self, field_info: FieldInfo, entity_name: str) -> Any:
        """フィールドの値を生成"""
        # ID フィールド
        if field_info.name == "id":
            return f"{entity_name.upper()}-001"

        # Enum フィールド - 最初の値を使用
        if field_info.enum:
            return field_info.enum[0]

        # 参照フィールド - 参照先エンティティのID形式
        if field_info.ref:
            return f"{field_info.ref.upper()}-001"

        # 型に基づくデフォルト値
        return self._get_default_for_type(field_info)

    def _get_default_for_type(self, field_info: FieldInfo) -> Any:
        """型に基づくデフォルト値を取得"""
        type_defaults = {
            "string": f"{field_info.name.upper()}-001",
            "text": "Sample text content",
            "int": field_info.min if field_info.min is not None else 100,
            "float": field_info.min if field_info.min is not None else 100.0,
            "bool": True,
            "boolean": True,
            "datetime": "2024-01-01T00:00:00Z",
            "date": "2024-01-01",
        }
        return type_defaults.get(field_info.type, "test")

    def generate_input_sample(self, command_name: str, overrides: dict | None = None) -> dict:
        """コマンドの入力サンプルを生成"""
        command = self.analyzer.get_command(command_name)
        if not command:
            return {}

        sample = {}
        for field_name, field_info in command.inputs.items():
            # 参照フィールドは参照先のID形式を使用
            if field_info.ref:
                sample[field_name] = f"{field_info.ref.upper()}-001"
            else:
                # Fallback: xxxId パターンから参照を推測（警告付き）
                inferred_ref = self._infer_reference(field_name)
                if inferred_ref:
                    sample[field_name] = f"{inferred_ref.upper()}-001"
                else:
                    sample[field_name] = self._get_default_for_type(field_info)

        if overrides:
            sample.update(overrides)

        return sample

    def _infer_reference(self, field_name: str) -> str | None:
        """フィールド名から参照先エンティティを推測（フォールバック）

        Warning: specにref定義がない場合のフォールバック。
        本来はspecに明示的にrefを定義すべき。
        """
        if not field_name.endswith("Id"):
            return None

        # xxxId -> Xxx
        entity_name = field_name[:-2]
        entity_name = entity_name[0].upper() + entity_name[1:]

        # エンティティが存在するか確認
        if self.analyzer.get_entity(entity_name):
            return entity_name

        return None

    def generate_test_context(self, command_name: str) -> list[dict]:
        """コマンド実行に必要なコンテキスト（依存エンティティ）を生成

        Returns:
            list of {entity: name, data: sample_data}
        """
        deps = self.analyzer.get_required_dependencies(command_name)
        context = []

        for entity_name in deps:
            entity = self.analyzer.get_entity(entity_name)
            if entity:
                # 子エンティティも設定
                context.append({
                    "entity": entity_name,
                    "data": self.generate_entity_sample(entity_name),
                })

                # 子エンティティがあれば追加
                for child_name in entity.children:
                    child_sample = self.generate_entity_sample(child_name)
                    # 親への参照を設定
                    parent_ref_field = f"{entity_name[0].lower()}{entity_name[1:]}Id"
                    if parent_ref_field in child_sample:
                        child_sample[parent_ref_field] = f"{entity_name.upper()}-001"
                    context.append({
                        "entity": child_name,
                        "data": child_sample,
                    })

        return context


class MockContextGenerator:
    """MockContext の構造を生成するユーティリティ"""

    def __init__(self, analyzer: SpecAnalyzer):
        self.analyzer = analyzer

    def generate_interface(self, language: str = "typescript") -> str:
        """MockContext インターフェースを生成"""
        if language == "typescript":
            return self._generate_typescript_interface()
        elif language == "python":
            return self._generate_python_protocol()
        else:
            raise ValueError(f"Unsupported language: {language}")

    def _generate_typescript_interface(self) -> str:
        """TypeScript インターフェースを生成"""
        lines = ["interface MockContext {"]

        for entity_name, entity in self.analyzer.get_all_entities().items():
            repo_name = f"{entity_name[0].lower()}{entity_name[1:]}Repository"
            lines.append(f"  {repo_name}: {{")
            lines.append("    create: jest.Mock;")
            lines.append("    get: jest.Mock;")
            lines.append("    getAll: jest.Mock;")
            lines.append("    update: jest.Mock;")
            lines.append("    delete: jest.Mock;")

            # ref フィールドに対して findByXxx を追加
            for field_name, field_info in entity.fields.items():
                if field_info.ref:
                    method_name = f"findBy{field_name[0].upper()}{field_name[1:]}"
                    lines.append(f"    {method_name}?: jest.Mock;")

            lines.append("  };")

        # Helper methods
        for entity_name in self.analyzer.get_all_entities():
            lines.append(f"  _set{entity_name}: (data: any) => void;")

        lines.append("}")
        return "\n".join(lines)

    def _generate_python_protocol(self) -> str:
        """Python Protocol を生成"""
        lines = ["from typing import Protocol, Any", "", "class MockContext(Protocol):"]

        for entity_name in self.analyzer.get_all_entities():
            repo_name = f"{entity_name[0].lower()}{entity_name[1:]}_repository"
            lines.append(f"    {repo_name}: Any")

        return "\n".join(lines)

    def generate_factory(self, language: str = "typescript") -> str:
        """MockContext ファクトリ関数を生成"""
        if language == "typescript":
            return self._generate_typescript_factory()
        else:
            raise ValueError(f"Unsupported language: {language}")

    def _generate_typescript_factory(self) -> str:
        """TypeScript ファクトリ関数を生成"""
        lines = ["function createMockContext(): MockContext {"]

        # Data stores
        for entity_name in self.analyzer.get_all_entities():
            var_name = f"{entity_name.lower()}s"
            lines.append(f"  const {var_name}: Record<string, any> = {{}};")
        lines.append("")

        lines.append("  return {")

        for entity_name, entity in self.analyzer.get_all_entities().items():
            repo_name = f"{entity_name[0].lower()}{entity_name[1:]}Repository"
            var_name = f"{entity_name.lower()}s"

            lines.append(f"    {repo_name}: {{")
            lines.append(f"      create: jest.fn().mockImplementation((data: any) =>")
            lines.append(f'        Promise.resolve({{ id: "NEW-{entity_name.upper()}", ...data }})),')
            lines.append(f"      get: jest.fn().mockImplementation((id: string) =>")
            lines.append(f"        Promise.resolve({var_name}[id] || null)),")
            lines.append(f"      getAll: jest.fn().mockImplementation(() =>")
            lines.append(f"        Promise.resolve(Object.values({var_name}))),")
            lines.append(f"      update: jest.fn().mockImplementation((id: string, data: any) => {{")
            lines.append(f"        const updated = {{ ...{var_name}[id], ...data }};")
            lines.append(f"        {var_name}[id] = updated;")
            lines.append(f"        return Promise.resolve(updated);")
            lines.append(f"      }}),")
            lines.append(f"      delete: jest.fn().mockImplementation((id: string) => Promise.resolve(true)),")

            # findByXxx methods
            for field_name, field_info in entity.fields.items():
                if field_info.ref:
                    method_name = f"findBy{field_name[0].upper()}{field_name[1:]}"
                    lines.append(f"      {method_name}: jest.fn().mockImplementation(({field_name}: string) =>")
                    lines.append(f"        Promise.resolve(Object.values({var_name}).filter((e: any) => e.{field_name} === {field_name}))),")

            lines.append("    },")

        # Helper methods
        for entity_name in self.analyzer.get_all_entities():
            var_name = f"{entity_name.lower()}s"
            lines.append(f"    _set{entity_name}: (data: any) => {{ {var_name}[data.id] = data; }},")

        lines.append("  };")
        lines.append("}")

        return "\n".join(lines)


# ========== Test Generation Markers ==========

class GenerationMarker:
    """テスト生成のマーカーを管理"""

    AUTO = "auto"        # 完全自動生成
    TEMPLATE = "template"  # テンプレート（手動実装が必要）
    MANUAL = "manual"    # 手動実装が必要

    @staticmethod
    def format_marker(marker_type: str, reason: str | None = None) -> str:
        """マーカーコメントを生成"""
        if reason:
            return f"// @mesh-generated: {marker_type} - {reason}"
        return f"// @mesh-generated: {marker_type}"

    @staticmethod
    def format_todo(reason: str) -> str:
        """TODO コメントを生成"""
        return f"// TODO: {reason}"
