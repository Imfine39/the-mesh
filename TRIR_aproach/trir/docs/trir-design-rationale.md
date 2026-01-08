# TRIR (Typed Relational IR) 設計根拠

## 背景

### YAMLベースアプローチの問題点（なぜTRIRか）

一般的なYAMLベースの仕様記述には以下の問題がある：

| カテゴリ | 課題 | 深刻度 |
|---------|------|--------|
| **パーサー** | パースエラーが隠蔽され、不正なコード生成が進行しやすい | CRITICAL |
| **検証** | YAMLスキーマ検証が不十分、不正specが受け入れられる | CRITICAL |
| **参照** | FK参照（`invoice_id`→`invoice`）の整合性チェックが困難 | HIGH |
| **式言語** | ネストフィールドアクセス（`a.b.c`）の表現が曖昧 | HIGH |
| **式言語** | WHERE句の表現が文字列と辞書で一貫性がない | MEDIUM |
| **生成** | OpenAPI生成時に型情報が推測ベースで損失 | HIGH |
| **生成** | SQL制約（NOT NULL等）の自動生成が困難 | HIGH |

TRIRはこれらの問題を**根本から解決**するために設計された。

### 検討した選択肢

#### 1. 形式仕様言語（Alloy, TLA+）

| 言語 | 強み | 弱み |
|------|------|------|
| **Alloy** | 関係代数ベース、自動検証 | スケール限界、コード生成弱い |
| **TLA+** | 状態遷移に優れる、AWS実績 | 学習曲線高い |

**結論**: 参考にすべき設計だが、直接採用は不適

#### 2. DMN (Decision Model and Notation)

OMG標準。FEEL式言語は参考になる設計：
- 決定表（Decision Table）
- 依存関係図（DRD）
- 型推論付き式言語

**結論**: 式言語設計の参考に

#### 3. Protobuf / FlatBuffers

| 形式 | 強み | 弱み |
|------|------|------|
| Protobuf | スキーマ進化、サイズ効率 | 式の表現が冗長 |
| FlatBuffers | ゼロコピー、高速 | 順序ベースのスキーマ進化 |

**結論**: シリアライズ層としては有用だが、式表現には不向き

---

## 重要な設計決定

### 「AIがYAMLを編集する」は最適か？

**No。** YAMLはAIにとって編集しにくい：

| 問題 | 具体例 |
|------|--------|
| インデント地獄 | 深いネストでスペース数ミス → パースエラー |
| 型曖昧性 | `amount: 100` は int? string? |
| 位置特定困難 | 1000行YAMLの特定位置を修正 |
| 部分編集困難 | 1箇所変更でも全体再生成しがち |

### AIが得意なこと

```
✅ 構造化データの生成（JSON/辞書）
✅ 関数呼び出し（Tool Use / Function Calling）
✅ 明示的なスキーマに従った出力
❌ 自由形式テキストの正確な編集
❌ インデントやフォーマットの維持
```

### 式ASTの冗長性は問題か？

**No。** JSON ASTは人間が書くには冗長に見えるが、**AIがTool Callingで生成する**ため問題にならない：

```
人間が書く場合:  invoice.amount - sum(allocation.amount where invoice_id == self.id)
AIが生成する場合: { "op": "subtract", "left": {...}, "right": {...} }
```

| 観点 | 評価 |
|------|------|
| **AIの生成精度** | JSON Schemaに従った構造化出力はLLMが得意 |
| **検証容易性** | スキーマ検証で即時エラー検出 |
| **人間の可読性** | Human View (YAML) として出力するので問題なし |

**TRIRは「AIが書き、人間がレビューする」ワークフローに最適化されている。**

### 結論: TRIRファースト設計

```
┌─────────────────────────────────────────────────────────────────┐
│  AI Agent                                                       │
│  構造化ツール呼び出し（JSON AST）で直接IRを操作                   │
└──────────────────────────┬──────────────────────────────────────┘
                           │ Tool Call (即時検証)
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  TRIR Engine                                                    │
│  • JSON AST → 型付きIR変換                                      │
│  • 参照解決、型推論                                              │
│  • 依存グラフ自動構築                                            │
└──────────────────────────┬──────────────────────────────────────┘
                           │
          ┌────────────────┼────────────────┬──────────────┐
          ▼                ▼                ▼              ▼
    ┌──────────┐    ┌──────────┐    ┌──────────┐   ┌───────────┐
    │ Human    │    │ OpenAPI  │    │  Tests   │   │ Impact    │
    │ View     │    │          │    │          │   │ Analysis  │
    │ (YAML)   │    │          │    │          │   │           │
    └──────────┘    └──────────┘    └──────────┘   └───────────┘
```

**YAMLは出力専用ビュー**（人間レビュー用）になる。

---

## TRIR設計原則

### 1. 曖昧さゼロ

- 全ての参照はIDベース（文字列名ではない）
- 式は型付きAST（パース済み）
- 不正な構造は構築不可能

### 2. 即時検証

- ツール呼び出し時点で型エラー検出
- 参照整合性はIR構築時に検証
- エラーが後段で発覚しない

### 3. 部分編集可能

- ノードIDベースで局所変更
- 影響範囲は依存グラフで自動計算
- 並列操作対応

### 4. 依存グラフ内蔵

- Entity間の参照関係
- Function→Entity依存
- Derived→Entity/Derived依存
- 影響範囲計算が組み込み

---

## Spec-Driven Implementation

TRIRは実装タスクにおいて「仕様駆動開発」を可能にする。

### ワークフロー

```
┌─────────────────────────────────────────────────────────────────┐
│  Task: "allocate_payment関数を実装せよ"                          │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  TRIR Engine: 依存グラフから関連スライスを抽出                    │
│                                                                 │
│  ✅ Function: allocate_payment (pre, error, post)               │
│  ✅ Entity: invoice, payment, allocation                        │
│  ✅ Derived: remaining                                          │
│  ✅ Scenario: AT-001, AT-002, AT-003 (テストケース)              │
│  ❌ 無関係なEntity/Function (顧客管理など)                       │
└──────────────────────────┬──────────────────────────────────────┘
                           │
          ┌────────────────┴────────────────┐
          ▼                                 ▼
┌──────────────────┐              ┌──────────────────┐
│  AI Context      │              │  生成されたTest   │
│  (最小限の仕様)   │              │  (完了条件)       │
└──────────────────┘              └──────────────────┘
          │                                 │
          └────────────┬────────────────────┘
                       ▼
              ┌─────────────────┐
              │  AI が実装      │
              │  テストをパス   │
              │  → タスク完了   │
              └─────────────────┘
```

### 利点

| 観点 | 効果 |
|------|------|
| **コンテキスト最小化** | 無関係な仕様を渡さないのでAIのトークン効率が良い |
| **明確な完了条件** | Scenarioから生成されたテストが「Done」の定義 |
| **仕様との整合性保証** | テストは仕様から自動生成されるので乖離しない |
| **並列開発** | 異なるFunctionを別のAIエージェントが同時に実装可能 |

### 実装タスクの流れ

1. **タスク受領**: `implement: allocate_payment`
2. **スライス抽出**: TRIR Engineが依存グラフを辿り関連部分のみ抽出
3. **テスト生成**: Scenarioからpytestコードを自動生成
4. **コンテキスト構築**: 仕様スライス + 生成テスト + 既存コード（あれば）
5. **AI実装**: テストをパスするコードを生成
6. **検証**: 全テストがパス → タスク完了

### Scenario = 実行可能な受け入れ条件

```json
// TRIR Scenario
{
  "id": "AT-001",
  "title": "部分消込で残額が減少する",
  "given": { "invoice": { "amount": 100000, "status": "open" } },
  "when": { "call": "allocate_payment", "input": { "amount": 80000 } },
  "then": {
    "success": true,
    "assert": [{ "op": "eq", "left": { "call": "remaining" }, "right": { "lit": 20000 } }]
  }
}
```

↓ 自動生成

```python
# Generated pytest
def test_at_001_partial_allocation_reduces_remaining():
    # Given
    invoice = create_invoice(amount=100000, status="open")

    # When
    result = allocate_payment(invoice_id=invoice.id, amount=80000)

    # Then
    assert result.success
    assert remaining(invoice) == 20000
```

**AIはこのテストをパスする実装を書くだけで良い。**

---

## Invariantによるリグレッション防止

変更を加えると、既存の正常な部分が壊れることがある（リグレッション）。TRIRはこれを2層で防ぐ。

### Scenario vs Invariant

| | Scenario | Invariant |
|---|----------|-----------|
| **何をテスト** | 特定の操作の結果 | 常に成り立つ制約 |
| **数** | 多い（数十〜数百） | 少ない（数個〜十数個） |
| **実行タイミング** | 対象Functionの変更時 | **全ての変更の後** |
| **例** | 「80000消込んだら残額が20000」 | 「残額は常に0以上」 |

### Invariantの例（会計システム）

```json
// INV-001: 残額は常に0以上
{
  "id": "INV-001",
  "entity": "invoice",
  "expr": { "op": "ge", "left": { "call": "remaining" }, "right": { "lit": 0 } },
  "description": "残額は常に0以上（マイナス残高禁止）"
}

// INV-002: 過剰消込禁止
{
  "id": "INV-002",
  "entity": "invoice",
  "expr": {
    "op": "le",
    "left": { "agg": "sum", "from": "allocation", "expr": { "ref": "item.amount" }, "where": { "op": "eq", "left": { "ref": "item.invoice_id" }, "right": { "self": "id" } } },
    "right": { "self": "amount" }
  },
  "description": "消込合計は請求額を超えない"
}

// INV-003: クローズ条件
{
  "id": "INV-003",
  "entity": "invoice",
  "expr": {
    "op": "eq",
    "left": { "op": "eq", "left": { "self": "status" }, "right": { "lit": "closed" } },
    "right": { "op": "eq", "left": { "call": "remaining" }, "right": { "lit": 0 } }
  },
  "description": "status=closed ↔ remaining=0"
}
```

**この3つだけで、どんな変更でも「会計として壊れていないか」をチェックできる。**

### 変更時リグレッション検出フロー

```
┌─────────────────────────────────────────────────────────────────┐
│  変更: invoice.amount の型を int → float に変更                  │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  1. analyze_impact で影響範囲を特定                              │
│                                                                 │
│  affected_functions: [allocate_payment, cancel_invoice]         │
│  affected_derived: [remaining, total_allocated]                 │
│  affected_scenarios: [AT-001, AT-002, AT-003, AT-007]          │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  2. 影響を受けるScenarioを実行                                   │
│                                                                 │
│  ✅ AT-001: passed                                              │
│  ✅ AT-002: passed                                              │
│  ❌ AT-003: FAILED (期待値との型不一致)                          │
│  ✅ AT-007: passed                                              │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  3. 全Invariantをチェック                                       │
│                                                                 │
│  ✅ INV-001: satisfied                                          │
│  ✅ INV-002: satisfied                                          │
│  ❌ INV-003: VIOLATED (float比較で精度問題)                      │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  結果: 変更を拒否 or 修正を要求                                  │
│                                                                 │
│  - AT-003を修正するか                                           │
│  - INV-003の比較ロジックを調整するか                             │
│  - そもそもfloatへの変更を再検討するか                           │
└─────────────────────────────────────────────────────────────────┘
```

### 2層防御の意味

```
Scenario: 「この操作でこうなる」 → 個別の正しさを保証
Invariant: 「何をしても壊れない」 → 全体の整合性を保証
```

| 層 | 役割 | 検出できるバグ |
|----|------|---------------|
| **Scenario** | 機能の振る舞い | 仕様通りに動かない |
| **Invariant** | システムの不変条件 | データ整合性の破壊 |

**Scenarioが通ってもInvariantが破れることがある。** 例えば、個別の消込処理は正しく動いても、並列実行で過剰消込が発生するケースなど。

Invariantは「絶対に壊れてはいけないルール」として、Scenarioでカバーしきれないエッジケースを守る。

---

## 参考文献

- [Alloy Specification Language](https://alloytools.org/)
- [TLA+ at Amazon](https://lamport.azurewebsites.net/tla/formal-methods-amazon.pdf)
- [DMN - Decision Model and Notation](https://en.wikipedia.org/wiki/Decision_Model_and_Notation)
- [IR in Compiler Design (UIUC)](https://courses.grainger.illinois.edu/cs426/fa2022/Notes/5ir.pdf)
- [FlatBuffers](https://flatbuffers.dev/)
- [Martin Fowler - Business Readable DSL](https://martinfowler.com/bliki/BusinessReadableDSL.html)
