# The Mesh - アーキテクチャ設計書

## 概要

**The Mesh** は、仕様駆動開発（Specification-Driven Development）フレームワークです。
ビジネス要件を機械的に検証可能な形式で記述し、変更影響を自動追跡することを目指します。

## 設計思想

### Single Source of Truth (SSOT)

```
┌─────────────────────────────────────────────────────────────────┐
│                     Spec YAML (SSOT)                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐    │
│  │ REQ-*    │→ │ derived  │→ │functions │→ │ scenarios    │    │
│  │(要件)    │  │(数式)    │  │(API仕様) │  │(AT:検証)     │    │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────┘    │
└────────────────────────┬────────────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         ↓               ↓               ↓
   [OpenAPI生成]    [DB Schema]    [テスト実行]
```

### 三層モデル

| 層 | HTTP相当 | spec要素 | 責務 |
|----|---------|---------|------|
| 入力検証 | 400 Bad Request | pre | 構造的チェック（型、必須、呼び出し資格） |
| ビジネス | 409/422 | error | ビジネスルール違反 |
| 不変条件 | 500 | invariant | 常に成立すべき条件（バグ検出） |

## Spec YAML 構造

```yaml
meta:
  id: SPEC-XXX
  title: "仕様名"
  version: "v0.X"

# 要件定義（起点）
requirements:
  REQ-001:
    who: ユーザー種別
    why: 理由
    what: 達成すること
    conditions:
      - id: COND-001-1
        description: 具体的条件
        acceptance: [AT-001]  # 検証するシナリオ
        verifies:
          - expr: "検証式"

# 計算式（derived）
derived:
  remaining:
    description: 残額
    formula: "invoice.amount - sum(allocation.amount where allocation.invoice_id = invoice.id)"

# 関数定義（API仕様）
functions:
  allocate_payment:
    implements: [REQ-001, REQ-002]

    # pre: 構造的チェック（呼び出し資格）
    pre:
      - expr: "invoice.status == 'open'"
        reason: "説明"

    # post: 状態変更
    post:
      - action: "create allocation"
      - condition: "remaining(invoice) == 0"
        action: "invoice.status = closed"

    # error: ビジネスルール違反
    error:
      - code: OVER_ALLOCATION
        when: "remaining(invoice) < input.amount"

# シナリオ（検証）
scenarios:
  AT-001:
    title: シナリオ名
    verifies: [COND-001-1]
    given:
      invoice: { amount: 100000, status: open }
      allocation: []
    when:
      call: allocate_payment
      input: { amount: 80000 }
    then:
      success: true
      assert:
        - "remaining(invoice) == 20000"

# 状態定義（DB）
state:
  invoice:
    amount: int
    status: enum[open, closed]
```

## 式言語

Python式ベースで以下の構文をサポート：

| 構文 | 例 | 変換後（Python） |
|-----|-----|-----------------|
| フィールドアクセス | `invoice.amount` | `state['invoice']['amount']` |
| 入力参照 | `input.amount` | `input['amount']` |
| derived呼び出し | `remaining(invoice)` | `_eval_derived('remaining', 'invoice')` |
| 比較 | `a == b`, `a >= b` | そのまま |
| 論理含意 | `A implies B` | `(not (A) or (B))` |
| 集約 | `sum(x.f where x.k = y.k)` | `sum(i['f'] for i in state['x'] if i['k'] == state['y']['k'])` |

## ツール

### formula_evaluator.py

spec内の式を評価し、シナリオを実行する。

```bash
# 単一式の評価
python tools/formula_evaluator.py specs/accounting_v5_req_first.yaml \
  --eval "remaining(invoice)"

# 全シナリオ実行
python tools/formula_evaluator.py specs/accounting_v5_req_first.yaml \
  --all-scenarios
```

### change_simulator.py

変更の影響範囲を追跡する。

```bash
# derived変更の影響
python tools/change_simulator.py specs/accounting_v5_req_first.yaml \
  --simulate "derived:remaining:modify"
```

### その他のツール

| ツール | 機能 |
|-------|------|
| spec_analyzer.py | 依存関係グラフ抽出 |
| formula_parser.py | 式から依存関係を自動抽出 |
| bundle_generator.py | BUNDLE自動生成 |
| req_integrity_checker.py | REQ→AT整合性検証 |
| human_view_generator.py | Markdown出力 |
| openapi_generator.py | OpenAPI 3.0定義生成 |
| db_schema_generator.py | SQL/Prismaスキーマ生成 |
| test_generator.py | pytest テストコード生成 |

## 検証結果

全シナリオが機械的に実行可能：

| シナリオ | 結果 | 検証内容 |
|---------|------|---------|
| AT-001 | PASS | 部分消込で残額が正しく減少 |
| AT-002 | PASS | 全額消込で自動クローズ |
| AT-003 | PASS | 残額超過でOVER_ALLOCATIONエラー |

## 今後の展望

1. ~~**OpenAPI生成**: spec → OpenAPI自動変換~~ ✅ 実装済み
2. ~~**DBスキーマ生成**: state → SQL/Prisma~~ ✅ 実装済み
3. ~~**テストコード生成**: scenarios → 実行可能テスト~~ ✅ 実装済み
4. **CI統合**: GitHub Actionsでの自動検証
