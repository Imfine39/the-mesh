# TRIR JSON AST Specification

## 概要

TRIR (Typed Relational IR) は、AI駆動の仕様記述のための中間表現形式。
YAMLを経由せず、構造化されたJSONで直接仕様を操作する。

## スキーマファイル

| ファイル | 内容 |
|---------|------|
| `schemas/trir/expression.schema.json` | 式（Expression）のAST定義 |
| `schemas/trir/schema.schema.json` | Entity, Function等の構造定義 |
| `schemas/trir/tools.schema.json` | AI用ツールインターフェース |

---

## Expression AST

### 基本構造

すべての式は以下のいずれかの形式:

```json
{ "lit": <value> }           // リテラル
{ "ref": "entity.field" }    // フィールド参照
{ "input": "param_name" }    // 入力パラメータ参照
{ "self": "field_name" }     // 自己参照（derived内）
{ "op": "...", "left": ..., "right": ... }  // 二項演算
{ "agg": "...", "from": "...", ... }        // 集計
```

### リテラル

```json
{ "lit": 100 }          // 整数
{ "lit": 3.14 }         // 浮動小数点
{ "lit": "hello" }      // 文字列
{ "lit": true }         // 真偽値
{ "lit": null }         // null
```

### 参照

```json
// フィールド参照
{ "ref": "invoice.amount" }
{ "ref": "invoice.customer.name" }  // ネスト可

// 入力参照（関数内）
{ "input": "amount" }

// 自己参照（derived内）
{ "self": "amount" }
```

### 二項演算

```json
// 算術: add, subtract, multiply, divide, modulo
{
  "op": "subtract",
  "left": { "self": "amount" },
  "right": { "ref": "allocation.amount" }
}

// 比較: eq, ne, lt, le, gt, ge
{
  "op": "eq",
  "left": { "ref": "invoice.status" },
  "right": { "lit": "open" }
}

// 論理: and, or
{
  "op": "and",
  "left": { "op": "eq", "left": { "ref": "item.invoice_id" }, "right": { "self": "id" } },
  "right": { "op": "eq", "left": { "ref": "item.status" }, "right": { "lit": "active" } }
}
```

### 単項演算

```json
{ "op": "not", "expr": { "ref": "invoice.is_cancelled" } }
{ "op": "is_null", "expr": { "ref": "invoice.paid_at" } }
{ "op": "is_not_null", "expr": { "ref": "invoice.paid_at" } }
```

### 集計

```json
// sum: 合計
{
  "agg": "sum",
  "from": "allocation",
  "as": "item",
  "expr": { "ref": "item.amount" },
  "where": {
    "op": "and",
    "left": { "op": "eq", "left": { "ref": "item.invoice_id" }, "right": { "self": "id" } },
    "right": { "op": "eq", "left": { "ref": "item.status" }, "right": { "lit": "active" } }
  }
}

// count: 件数
{
  "agg": "count",
  "from": "task",
  "where": { "op": "eq", "left": { "ref": "item.project_id" }, "right": { "self": "id" } }
}

// exists: 存在確認
{
  "agg": "exists",
  "from": "allocation",
  "where": { "op": "eq", "left": { "ref": "item.invoice_id" }, "right": { "input": "invoice_id" } }
}

// 利用可能: sum, count, avg, min, max, exists, not_exists, all, any
```

### 関数呼び出し（derived呼び出し）

```json
{
  "call": "remaining",
  "args": [{ "ref": "invoice" }]
}
```

### 条件式

```json
// if-then-else
{
  "if": { "op": "gt", "left": { "self": "amount" }, "right": { "lit": 1000 } },
  "then": { "lit": 100 },
  "else": { "lit": 50 }
}

// case式
{
  "case": [
    { "when": { "op": "eq", "left": { "ref": "item.status" }, "right": { "lit": "active" } }, "then": { "lit": 1.0 } },
    { "when": { "op": "eq", "left": { "ref": "item.status" }, "right": { "lit": "pending" } }, "then": { "lit": 0.5 } }
  ],
  "else": { "lit": 0 }
}
```

### 日付演算

```json
// 日付差分
{
  "date_op": "diff",
  "args": [{ "self": "check_in_date" }, { "self": "check_out_date" }],
  "unit": "days"
}

// 日付加算
{
  "date_op": "add",
  "args": [{ "self": "due_date" }, { "lit": 7 }],
  "unit": "days"
}

// 現在日時
{ "date_op": "now" }
{ "date_op": "today" }
```

---

## 実例: 会計システムの残額計算

### YAML（従来形式・人間ビュー）

```yaml
derived:
  remaining:
    formula:
      subtract:
        - "self.amount"
        - sum:
            expr: "item.amount"
            from: "allocation as item"
            where:
              and:
                - "item.invoice_id == self.id"
                - "item.status == 'active'"
```

### JSON AST（TRIR形式）

```json
{
  "op": "subtract",
  "left": { "self": "amount" },
  "right": {
    "agg": "sum",
    "from": "allocation",
    "as": "item",
    "expr": { "ref": "item.amount" },
    "where": {
      "op": "and",
      "left": {
        "op": "eq",
        "left": { "ref": "item.invoice_id" },
        "right": { "self": "id" }
      },
      "right": {
        "op": "eq",
        "left": { "ref": "item.status" },
        "right": { "lit": "active" }
      }
    }
  }
}
```

---

## ツール使用例

### Entity作成

```json
// Tool: create_entity
{
  "name": "invoice",
  "description": "請求書",
  "fields": {
    "id": { "type": "string", "required": true },
    "customer_id": { "type": { "ref": "customer" }, "required": true },
    "amount": { "type": "int", "required": true },
    "status": { "type": { "enum": ["open", "closed", "cancelled"] }, "required": true },
    "due_date": { "type": "datetime", "required": true }
  }
}
```

### Function作成

```json
// Tool: create_function
{
  "name": "allocate_payment",
  "description": "支払いを請求書に消込",
  "implements": ["REQ-001", "REQ-002"],
  "input": {
    "invoice_id": { "type": "string", "required": true },
    "payment_id": { "type": "string", "required": true },
    "amount": { "type": "int", "required": true }
  }
}
```

### 前提条件追加

```json
// Tool: add_precondition
{
  "function": "allocate_payment",
  "expr": {
    "op": "eq",
    "left": { "ref": "invoice.status" },
    "right": { "lit": "open" }
  },
  "entity": "invoice",
  "reason": "オープン状態の請求書のみ消込可能"
}
```

### エラーケース追加

```json
// Tool: add_error_case
{
  "function": "allocate_payment",
  "code": "OVER_ALLOCATION",
  "when": {
    "op": "lt",
    "left": { "call": "remaining", "args": [{ "ref": "invoice" }] },
    "right": { "input": "amount" }
  },
  "reason": "消込額が残額を超過",
  "http_status": 409
}
```

### Post Action追加

```json
// Tool: add_post_action
{
  "function": "allocate_payment",
  "action": {
    "create": "allocation",
    "with": {
      "invoice_id": { "input": "invoice_id" },
      "payment_id": { "input": "payment_id" },
      "amount": { "input": "amount" },
      "status": { "lit": "active" }
    }
  },
  "reason": "消込レコード作成"
}

// 条件付きアクション
{
  "function": "allocate_payment",
  "action": {
    "update": "invoice",
    "set": {
      "status": { "lit": "closed" }
    }
  },
  "condition": {
    "op": "eq",
    "left": { "call": "remaining", "args": [{ "ref": "invoice" }] },
    "right": { "lit": 0 }
  },
  "reason": "残額ゼロで自動クローズ"
}
```

### Derived作成

```json
// Tool: create_derived
{
  "name": "remaining",
  "entity": "invoice",
  "formula": {
    "op": "subtract",
    "left": { "self": "amount" },
    "right": {
      "agg": "sum",
      "from": "allocation",
      "as": "item",
      "expr": { "ref": "item.amount" },
      "where": {
        "op": "and",
        "left": { "op": "eq", "left": { "ref": "item.invoice_id" }, "right": { "self": "id" } },
        "right": { "op": "eq", "left": { "ref": "item.status" }, "right": { "lit": "active" } }
      }
    }
  },
  "description": "残額（請求額 - 消込済み額）",
  "returns": "int"
}
```

### シナリオ作成

```json
// Tool: create_scenario
{
  "id": "AT-001",
  "title": "部分消込で残額が減少する",
  "verifies": ["COND-001-1"],
  "given": {
    "customer": { "id": "CUST-001", "name": "テスト株式会社" },
    "invoice": { "id": "INV-001", "customer_id": "CUST-001", "amount": 100000, "status": "open" },
    "payment": { "id": "PAY-001", "customer_id": "CUST-001", "amount": 80000 },
    "allocation": []
  },
  "when": {
    "call": "allocate_payment",
    "input": { "invoice_id": "INV-001", "payment_id": "PAY-001", "amount": 80000 }
  },
  "then": {
    "success": true,
    "assert": [
      {
        "op": "eq",
        "left": { "call": "remaining", "args": [{ "ref": "invoice" }] },
        "right": { "lit": 20000 }
      },
      {
        "op": "eq",
        "left": { "ref": "invoice.status" },
        "right": { "lit": "open" }
      }
    ]
  }
}
```

---

## 変換フロー

```
AI Tool Calls (JSON AST)
        │
        ▼
┌───────────────────┐
│  TRIR Engine      │
│  ・即時検証       │
│  ・型推論         │
│  ・依存グラフ構築 │
└───────────────────┘
        │
        ├──→ Human View (YAML) ──→ 人間レビュー
        │
        ├──→ OpenAPI 3.0
        │
        ├──→ SQL/Prisma Schema
        │
        └──→ pytest Test Code
```

---

## 型システム

### 基本型

| 型 | JSON表現 | 説明 |
|----|----------|------|
| string | `"string"` | 文字列 |
| int | `"int"` | 整数 |
| float | `"float"` | 浮動小数点 |
| bool | `"bool"` | 真偽値 |
| datetime | `"datetime"` | 日時 |
| text | `"text"` | 長文テキスト |

### 複合型

```json
// Enum
{ "enum": ["open", "closed", "cancelled"] }

// List
{ "list": "string" }
{ "list": { "enum": ["high", "medium", "low"] } }

// Foreign Key Reference
{ "ref": "customer" }
{ "ref": "customer", "field": "id", "on_delete": "cascade" }
```

---

## バリデーション

ツール呼び出し時に以下を即時検証:

1. **参照整合性**: 存在しないEntity/Fieldへの参照
2. **型整合性**: 比較演算の型一致、集計対象の型
3. **循環依存**: Derived間の循環参照
4. **必須フィールド**: required=trueのフィールドがnull許容の式
5. **Enum値**: 定義されていないEnum値の使用
