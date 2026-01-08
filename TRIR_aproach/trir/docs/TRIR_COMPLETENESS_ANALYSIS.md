# TRIR フレームワーク 汎用性完全化分析

## 概要

本ドキュメントは、TRIR (Typed Relational IR) フレームワークを「どんな要件も表現できる汎用フレームワーク」にするための分析結果をまとめたものです。

### 分析観点

1. **プリミティブの完全性** - 10ドメイン横断 + 10形式手法との比較
2. **Human-Readable変換器** - AIが編集し、人間がレビューするワークフロー
3. **AI最適スキーマ設計** - AIが生成・編集しやすい構造

---

## 現状のTRIRプリミティブ

| カテゴリ | プリミティブ | 説明 |
|---------|------------|------|
| **state** | Entity, Field | エンティティ定義（型、FK、unique、enum、list） |
| **derived** | Formula | 計算フィールド（集計、条件分岐、日付演算） |
| **functions** | Function | 操作定義（input, pre, error, post） |
| **scenarios** | Scenario | テストケース（given, when, then） |
| **invariants** | Invariant | 不変条件 |
| **expressions** | Expression | 式AST（binary, unary, agg, ref, call, if, case, date, list, literal） |

### 現状の強み

- CRUDアプリケーションの基本ロジックを十分に記述可能
- 単純な集計・条件分岐・日付演算が充実
- invariantによる不変条件の表現が強力
- scenarioによるテスト記述が実用的
- Tagged Union形式によるJSON Schema検証

### 現状の限界

- 時間軸を跨ぐ参照（履歴、将来）が弱い
- 再帰・階層構造の表現が困難
- 複雑なワークフローの記述が不可能
- 外部システム連携の概念がない
- セキュリティ・権限の定義がない
- 統計・確率計算がサポートされていない

---

## 不足プリミティブの詳細分析

### 1. 時間・履歴

#### temporal_ref (過去時点参照)

**必要とするドメイン**: 会計、医療、HR、金融

```json
{
  "type": "temporal",
  "op": "snapshot",
  "entity": "exchange_rate",
  "at": { "type": "ref", "path": "invoice.period_end_date" }
}
```

**ユースケース**:
- 為替換算時の期末レート参照
- 契約時点の賃料参照
- 診断時点のカルテ情報

#### immutable_history (変更不可履歴)

**必要とするドメイン**: 医療、監査、コンプライアンス

```json
{
  "entity": "invoice",
  "audit": {
    "enabled": true,
    "immutable": true,
    "versioned": true,
    "track_fields": ["status", "amount"],
    "retention": { "period": "7 years", "regulation": "SOX" }
  }
}
```

#### state_history (previous/changed)

**出典**: TLA+

```json
{
  "type": "history",
  "op": "previous",
  "path": "order.status"
}
```

**ユースケース**: 状態変更の検出、差分比較

---

### 2. 状態・遷移

#### state_machine (階層状態、並行状態)

**出典**: State Charts

```json
{
  "state_machines": {
    "invoice_lifecycle": {
      "entity": "invoice",
      "field": "status",
      "initial": "draft",
      "states": {
        "draft": {},
        "processing": {
          "type": "parallel",
          "regions": {
            "payment": {
              "states": ["awaiting", "authorized", "captured"]
            },
            "fulfillment": {
              "states": ["picking", "packing", "shipped"]
            }
          }
        },
        "completed": { "type": "final" }
      },
      "transitions": [
        {
          "from": "draft",
          "to": "processing",
          "event": "submit",
          "guard": { "expr": "..." }
        }
      ]
    }
  }
}
```

#### temporal_property (safety/liveness)

**出典**: TLA+

```json
{
  "temporal_properties": {
    "eventual_completion": {
      "type": "liveness",
      "formula": {
        "op": "leads_to",
        "antecedent": { "order.status": "processing" },
        "consequent": { "order.status": { "in": ["completed", "cancelled"] } }
      }
    },
    "no_double_charge": {
      "type": "safety",
      "formula": {
        "op": "always",
        "expr": { "payment_count": { "le": 1 } }
      }
    }
  }
}
```

---

### 3. 構造

#### tree_structure (階層展開)

**必要とするドメイン**: 製造BOM、組織、カテゴリ

```json
{
  "tree": "bom",
  "entity": "bom_item",
  "parent_field": "parent_item_id",
  "operations": {
    "expand": { "type": "recursive", "depth": "unlimited" },
    "aggregate": { "op": "sum", "field": "quantity" }
  }
}
```

#### recursive_ref (再帰参照)

**必要とするドメイン**: HR上長、承認階層

```json
{
  "type": "traverse",
  "start": { "type": "self", "field": "manager_id" },
  "until": { "op": "eq", "left": { "ref": "role" }, "right": "director" },
  "collect": "approvals",
  "max_depth": 10
}
```

---

### 4. ワークフロー

#### workflow (複数ステップ処理)

**出典**: Temporal, BPMN

```json
{
  "workflows": {
    "order_fulfillment": {
      "steps": [
        { "activity": "validate_order" },
        { "activity": "reserve_inventory" },
        { "activity": "process_payment" },
        { "activity": "ship_order" }
      ],
      "timeout": { "duration": { "days": 7 } }
    }
  }
}
```

#### saga (分散トランザクション)

**出典**: Temporal

```json
{
  "sagas": {
    "book_trip": {
      "steps": [
        {
          "forward": "book_flight",
          "compensate": "cancel_flight"
        },
        {
          "forward": "book_hotel",
          "compensate": "cancel_hotel"
        }
      ],
      "on_failure": "compensate_all"
    }
  }
}
```

#### approval_chain (承認フロー)

**出典**: BPMN

```json
{
  "approval_workflows": {
    "purchase_approval": {
      "steps": [
        {
          "name": "manager_approval",
          "type": "sequential",
          "approvers": { "ref": "requester.manager" },
          "timeout": { "days": 3 },
          "escalation": { "after": "2d", "to": "department_head" }
        },
        {
          "name": "finance_approval",
          "type": "parallel",
          "required": "majority",
          "condition": { "amount": { "gt": 100000 } }
        }
      ]
    }
  }
}
```

---

### 5. イベント

#### event (ドメインイベント定義)

**出典**: イベントソーシング

```json
{
  "events": {
    "PaymentAllocated": {
      "payload": {
        "invoice_id": { "type": "string" },
        "amount": { "type": "int" },
        "allocated_at": { "type": "datetime" }
      },
      "emitted_by": ["allocate_payment"],
      "publish_to": ["event_queue"]
    }
  }
}
```

#### projection (イベント→状態)

**出典**: CQRS

```json
{
  "projections": {
    "invoice_balance": {
      "from_events": ["PaymentAllocated", "AllocationCancelled"],
      "initial_state": { "remaining": { "ref": "invoice.amount" } },
      "handlers": {
        "PaymentAllocated": {
          "set": { "remaining": { "op": "sub", "left": "self.remaining", "right": "event.amount" } }
        }
      }
    }
  }
}
```

#### subscription (イベント購読)

```json
{
  "subscriptions": {
    "inventory_sync": {
      "source": "event_queue",
      "topic": "inventory.*",
      "handler": "sync_inventory",
      "dead_letter": { "topic": "inventory.dlq", "max_retries": 3 }
    }
  }
}
```

---

### 6. スケジュール

#### schedule (cron定期実行)

```json
{
  "schedules": {
    "daily_overdue_check": {
      "cron": "0 9 * * *",
      "timezone": "Asia/Tokyo",
      "action": { "call": "mark_overdue_invoices" }
    }
  }
}
```

#### delayed_action (遅延実行)

```json
{
  "delayed_actions": {
    "payment_reminder": {
      "trigger": { "entity": "invoice", "on": "create" },
      "delay": { "offset": "-3d", "from": "invoice.due_date" },
      "action": { "call": "send_reminder" },
      "cancel_when": { "invoice.status": { "ne": "open" } }
    }
  }
}
```

#### deadline (期限管理)

```json
{
  "deadlines": {
    "invoice_payment": {
      "entity": "invoice",
      "deadline_field": "due_date",
      "sla": {
        "warning": "-7d",
        "critical": "-1d",
        "breach": "0d"
      },
      "escalation": {
        "breach": { "emit": "PaymentOverdue", "action": { "call": "mark_overdue" } }
      }
    }
  }
}
```

---

### 7. 非同期処理

#### async_function (非同期実行)

```json
{
  "async_functions": {
    "send_email": {
      "execution": {
        "mode": "async",
        "queue": "email_queue",
        "timeout": { "seconds": 30 },
        "retry": {
          "max_attempts": 5,
          "backoff": { "type": "exponential", "initial": "1s", "max": "5m" }
        }
      }
    }
  }
}
```

#### queue (キュー定義)

```json
{
  "queues": {
    "email_queue": {
      "concurrency": 10,
      "priority": "normal",
      "visibility_timeout": "5m"
    }
  }
}
```

---

### 8. 集計・計算

#### window_function (rank, lag, lead)

**出典**: SQL

```json
{
  "type": "window",
  "op": "rank",
  "partition_by": ["customer_id"],
  "order_by": [{ "field": "created_at", "desc": true }]
}
```

#### group_constraint (グループ制約)

**ユースケース**: 会計仕訳の貸借一致

```json
{
  "group_constraints": {
    "debit_credit_balance": {
      "entity": "journal_line",
      "group_by": "journal_id",
      "constraint": {
        "op": "eq",
        "left": { "agg": "sum", "field": "debit" },
        "right": { "agg": "sum", "field": "credit" }
      }
    }
  }
}
```

#### lookup_table (区間テーブル)

**ユースケース**: 累進課税、料金表

```json
{
  "type": "lookup",
  "table": "tax_bracket",
  "key": "taxable_income",
  "return": "rate"
}
```

---

### 9. 外部連携

#### external_service (API定義)

```json
{
  "external_services": {
    "payment_gateway": {
      "type": "rest",
      "base_url": { "env": "PAYMENT_GATEWAY_URL" },
      "auth": { "type": "bearer", "token": { "env": "API_KEY" } },
      "timeout_ms": 5000,
      "retry": { "max_attempts": 3, "retry_on": [502, 503, 504] },
      "circuit_breaker": { "failure_threshold": 5, "recovery_timeout_ms": 30000 }
    }
  }
}
```

#### external_call (呼び出しマッピング)

```json
{
  "external_calls": {
    "charge_card": {
      "service": "payment_gateway",
      "method": "POST",
      "path": "/v1/charges",
      "request": {
        "mapping": {
          "amount": { "input": "amount" },
          "currency": { "literal": "JPY" }
        }
      },
      "response": {
        "success_when": { "response.status": "succeeded" },
        "mapping": { "transaction_id": "response.id" }
      }
    }
  }
}
```

#### webhook (受信定義)

```json
{
  "webhooks": {
    "stripe_webhook": {
      "path": "/webhooks/stripe",
      "auth": { "type": "signature", "secret": { "env": "WEBHOOK_SECRET" } },
      "events": {
        "payment_intent.succeeded": {
          "handler": "process_payment_success",
          "mapping": { "transaction_id": "payload.data.object.id" }
        }
      },
      "idempotency": { "key": "payload.id", "ttl_hours": 24 }
    }
  }
}
```

---

### 10. セキュリティ

#### role / permission (RBAC)

```json
{
  "security": {
    "roles": {
      "accountant": {
        "permissions": [
          { "resource": "invoice", "actions": ["read", "update"] },
          { "resource": "allocation", "actions": ["create", "read"] }
        ]
      },
      "finance_manager": {
        "inherits": ["accountant"],
        "permissions": [
          { "resource": "invoice", "actions": ["delete"] }
        ]
      }
    }
  }
}
```

#### row_level_security (RLS)

```json
{
  "row_level_security": {
    "policies": [
      {
        "name": "tenant_isolation",
        "condition": {
          "op": "eq",
          "left": { "ref": "self.tenant_id" },
          "right": { "principal": "tenant_id" }
        }
      }
    ]
  }
}
```

#### audit (監査証跡)

```json
{
  "audit": {
    "enabled": true,
    "entities": ["invoice", "payment"],
    "track": ["who", "when", "what", "old_values", "new_values"],
    "retention": { "period": "7 years" },
    "integrity": { "hash_chain": true, "algorithm": "SHA-256" }
  }
}
```

---

### 11. 環境・運用

#### feature_flag (フィーチャーフラグ)

```json
{
  "feature_flags": {
    "new_payment_flow": {
      "type": "boolean",
      "default": false,
      "rollout": {
        "strategy": "percentage",
        "percentage": 10,
        "sticky_by": "customer_id"
      }
    }
  }
}
```

#### observability (メトリクス/ログ/アラート)

```json
{
  "observability": {
    "metrics": {
      "invoice_processing_duration": {
        "type": "histogram",
        "unit": "milliseconds",
        "labels": ["status", "customer_tier"]
      }
    },
    "alerts": {
      "high_failure_rate": {
        "condition": { "metric": "payment_failures", "threshold": 0.1 },
        "severity": "critical",
        "notify": ["pagerduty:team"]
      }
    }
  }
}
```

#### test_double (モック/スタブ)

```json
{
  "test_doubles": {
    "mock_payment_gateway": {
      "mocks": "payment_gateway",
      "responses": {
        "successful_charge": {
          "match": { "method": "POST", "path": "/v1/charges" },
          "respond": { "status": 200, "body": { "status": "succeeded" } }
        }
      }
    }
  }
}
```

---

## Human-Readable変換器の設計

### 変換ターゲット一覧

| 形式 | 用途 | 対象者 | 優先度 |
|------|------|--------|--------|
| ER図 (Mermaid) | データ構造全体の把握 | 開発者、DBA | 高 |
| フローチャート | 関数ロジックの確認 | 開発者、QA | 高 |
| 状態遷移図 | ステータス遷移の確認 | 業務担当、開発者 | 高 |
| シーケンス図 | シナリオの流れ | 全員 | 中 |
| エンティティ一覧表 | 概要把握 | 全員 | 高 |
| フィールド定義表 | 詳細定義確認 | 開発者 | 高 |
| テストケース表 | カバレッジ確認 | QA | 高 |
| 日本語要件文 | ビジネス確認 | 業務担当、PM | 高 |
| 差分+影響分析 | レビュー | 全員 | 高 |
| インタラクティブUI | 大規模仕様探索 | 開発者 | 中 |

### フィードバックループ

```
1. AI編集 → TRIR JSON更新
       │
       ▼
2. 自動変換 → 複数形式生成
       │
       ├─→ ER図（構造変更時）
       ├─→ フローチャート（ロジック変更時）
       ├─→ 差分表示（常時）
       └─→ 自然言語サマリ（常時）
       │
       ▼
3. 人間レビュー
       │
       ├─→ ✅ OK → 次のステップ
       │
       └─→ ❌ 修正要求 → AIが解釈 → 1に戻る
```

---

## AI最適スキーマ設計

### 1. 構造化エラーメッセージ

```python
@dataclass
class AIFriendlyError:
    path: str                    # JSONパス
    message: str                 # 人間向けメッセージ
    error_code: str              # 機械処理用コード
    context: dict                # 周辺情報
    suggestions: list[dict]      # 修正候補（confidence付き）
```

### 2. 部分更新 (JSON Patch)

```json
{
  "operations": [
    { "op": "add", "path": "/state/product", "value": {...} },
    { "op": "replace", "path": "/functions/place_order/error/0", "value": {...} },
    { "op": "remove", "path": "/scenarios/AT-003" }
  ]
}
```

### 3. Shorthand記法（AI生成後に正規化）

```json
// AIが生成する簡略形
{ "eq": ["invoice.status", "open"] }

// エンジンが正規化
{
  "type": "binary",
  "op": "eq",
  "left": { "type": "ref", "path": "invoice.status" },
  "right": { "type": "literal", "value": "open" }
}
```

### 4. 命名規則の強制

| 種別 | パターン | 例 |
|------|----------|-----|
| Entity | `snake_case` (単数形) | `order_item` |
| Function | `verb_noun` | `create_order` |
| Derived | `entity_property` | `order_subtotal` |
| Error | `UPPER_SNAKE_CASE` | `OVER_ALLOCATION` |
| Scenario | `XX-NNN` | `CLR-001` |
| Invariant | `INV-NNN` | `INV-001` |

### 5. トークン制限付きスライス

```python
def get_slice_with_limit(function_name: str, max_tokens: int = 4000) -> dict:
    """関連部分のみを抽出（トークン数制限付き）"""
    # 優先度順に削減: シナリオ → 関連度の低いエンティティ → description
```

---

## 実装ロードマップ

### Phase 1: 基盤（最も多くのドメインで必要）

| プリミティブ | 理由 |
|------------|------|
| `state_machine` | 複雑な状態遷移の現実的モデル化に必須 |
| `temporal_ref` | 過去時点参照（会計、医療、HR、金融） |
| `workflow` + `compensation` | 障害復旧の定義がないと本番運用不可 |
| `event` + `subscription` | イベント駆動アーキテクチャの基盤 |
| 構造化エラーメッセージ | AIの自己修正率向上 |

### Phase 2: セキュリティ・運用

| プリミティブ | 理由 |
|------------|------|
| `role` / `permission` | 最も基本的なセキュリティ |
| `audit` | コンプライアンスの基盤 |
| `row_level_security` | データ分離の基盤 |
| `schedule` / `deadline` | 期限管理は多くのドメインで必須 |
| Human-Readable変換器 | レビューワークフローの実現 |

### Phase 3: 外部連携

| プリミティブ | 理由 |
|------------|------|
| `external_service` / `external_call` | 決済、通知などの外部API |
| `webhook` | リアルタイム連携 |
| `async_function` / `retry_policy` | 耐障害性の基盤 |
| `test_double` | 外部依存のテスト |
| `observability` | 運用監視 |

### Phase 4: 高度な機能

| プリミティブ | 理由 |
|------------|------|
| `tree_structure` / `recursive_ref` | 階層データ（BOM、組織） |
| `window_function` | ビジネスレポート |
| `feature_flag` | 段階的リリース |
| `temporal_property` | 活性の保証 |
| `approval_chain` | 業務システム |

---

## 分析に使用したドメイン

1. 会計・財務（仕訳、決算、連結、税務）
2. 在庫・物流（入出庫、ロット、シリアル、倉庫間移動）
3. 人事・給与（勤怠、給与計算、評価、採用）
4. EC・販売（カート、注文、配送、返品）
5. 医療（電子カルテ、処方、予約）
6. 製造（BOM、工程、品質管理）
7. 不動産（契約、賃貸、管理費）
8. 金融（取引、リスク計算、規制対応）
9. 教育（履修、成績、出席）
10. プロジェクト管理（タスク、リソース、マイルストーン）

## 参考にした形式手法・言語

1. **Alloy** - 関係論理、制約充足
2. **TLA+** - 時相論理、状態遷移、活性・安全性
3. **Z notation** - スキーマ、操作仕様
4. **Event-B** - イベント、精緻化
5. **Petri Net** - 並行性、同期
6. **BPMN** - ビジネスプロセス、ゲートウェイ
7. **State Charts** - 階層状態、並行状態
8. **GraphQL** - クエリ、ミューテーション、サブスクリプション
9. **SQL** - 集合演算、ウィンドウ関数
10. **Temporal** - サガ、補償、リトライ

---

## 結論

TRIRは現状で「単一エンティティに対するCRUDと基本的なビジネスルール」には十分な表現力を持つ。

しかし、本分析により以下の領域で拡張が必要であることが明らかになった：

1. **時間軸**: 「過去のデータ」「いつか完了する」「タイムアウト」
2. **状態の複雑さ**: 階層状態、並行状態、履歴状態
3. **分散処理**: サガ、補償、リトライ
4. **外部世界**: API連携、Webhook、キュー
5. **セキュリティ**: 権限、監査、テナント分離
6. **運用**: メトリクス、アラート、フィーチャーフラグ

これらを段階的に追加することで、TRIRは「どんな要件も表現できる汎用フレームワーク」へと進化する。
