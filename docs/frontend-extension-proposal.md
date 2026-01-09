# The Mesh フロントエンド拡張設計提案

## 背景

The Meshはバックエンド（Python/TypeScript）向けに設計された仕様駆動開発フレームワーク。
フロントエンド対応は後付けで追加されたため、バックエンドと比較して機能が限定的。

## 現状のバックエンドフロー

```
┌─────────────────────────────────────────────────────────────────────────┐
│  1. 仕様作成フェーズ                                                      │
├─────────────────────────────────────────────────────────────────────────┤
│  spec_create_from_template → spec_write → spec_update_section           │
│       ↓                                                                 │
│  ~/.mesh/specs/{id}.mesh.json に保存                                    │
│       ↓                                                                 │
│  validate_spec で自動検証（21フェーズ）                                  │
└─────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────┐
│  2. コード生成フェーズ                                                    │
├─────────────────────────────────────────────────────────────────────────┤
│  generate_task_package(function_name, language)                         │
│       ↓                                                                 │
│  ┌───────────────────────────────────────────────────────┐              │
│  │ 生成物:                                                │              │
│  │  .mesh/tests/at/test_{func}_at.py  ← ATテスト         │              │
│  │  .mesh/tests/ut/test_unit.py       ← UTテスト         │              │
│  │  tasks/{func}/TASK.md              ← 実装要件書       │              │
│  │  tasks/{func}/context.json         ← 必要コンテキスト  │              │
│  │  tasks/{func}/pytest.ini           ← テスト設定       │              │
│  │  src/{func}.py                     ← 実装スケルトン    │              │
│  └───────────────────────────────────────────────────────┘              │
└─────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────┐
│  3. 影響分析フェーズ                                                      │
├─────────────────────────────────────────────────────────────────────────┤
│  analyze_impact(spec, change)                                           │
│       ↓                                                                 │
│  DependencyGraph でエンティティ/関数/derived/scenario の依存関係解析     │
│       ↓                                                                 │
│  affected_entities, affected_functions, breaking_changes を返却         │
└─────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────┐
│  4. コンテキストバンドルフェーズ                                           │
├─────────────────────────────────────────────────────────────────────────┤
│  get_function_context(function_name)                                    │
│       ↓                                                                 │
│  graph.get_slice() で最小限のコンテキスト抽出:                           │
│    - function_def（関数定義）                                            │
│    - entities（依存エンティティ）                                        │
│    - derived（依存computed）                                             │
│    - scenarios（関連テストケース）                                       │
│    - invariants（関連不変条件）                                          │
└─────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────┐
│  5. タスク管理フェーズ                                                    │
├─────────────────────────────────────────────────────────────────────────┤
│  activate_task(function_name)                                           │
│       ↓ git worktree作成（task/{func}_{short_id}ブランチ）              │
│       ↓ .mesh/state.json に状態保存                                     │
│                                                                         │
│  check_edit_permission(file_path)                                       │
│       → アクティブタスクのimplファイルのみ編集可                         │
│       → tasks/{func}/* は読み取り専用                                   │
│       → .mesh/tests/* は読み取り専用                                    │
│                                                                         │
│  complete_task(function_name, test_results)                             │
│       ↓ テスト結果確認（failed があればエラー）                          │
│       ↓ commit_and_push                                                 │
│       ↓ create_pull_request（auto_pr=true時）                           │
│       ↓ worktree cleanup（cleanup_worktree=true時）                     │
└─────────────────────────────────────────────────────────────────────────┘
```

### バックエンドの設計思想

1. **Single Source of Truth**: `.mesh.json`仕様ファイルが全ての起点
2. **自動生成**: テスト・スケルトンはspecから自動生成（手動編集禁止）
3. **スコープ制限**: アクティブタスクの実装ファイルのみ編集可能
4. **テスト駆動**: テストがパスしないとタスク完了できない
5. **Git統合**: worktree/branch/PRが自動管理される

---

## 現状のフロントエンド対応

| 機能 | 状態 | 内容 |
|------|------|------|
| `views` | スキーマ定義あり | entity + fields + actions + filters |
| `routes` | スキーマ定義あり | view + guards + params |
| バリデーション | 基本的 | FE-002〜005（参照チェック程度）|
| TypeScript生成 | あり | エンティティ/関数の型のみ |
| Zod生成 | あり | 入力バリデーションのみ |
| OpenAPI生成 | あり | API定義のみ |

### 欠けているもの

```
バックエンド           フロントエンド
─────────────────     ─────────────────
functions        ←→   views/routes      ← 対応関係が弱い
scenarios        ←→   ???               ← E2Eテストシナリオがない
generate_task_package  ???               ← コンポーネントスケルトンがない
activate_task    ←→   ???               ← view/page単位のタスク管理がない
get_function_context   ???               ← view実装に必要なコンテキスト取得がない
DependencyGraph  ←→   ???               ← view間の依存関係がない
```

---

## フロントエンド拡張設計提案

### 1. Spec構造の拡張

```json
{
  "views": {
    "InvoiceList": {
      "type": "list",
      "entity": "invoice",
      "fields": [...],
      "actions": [{ "function": "allocate_payment", ... }]
    }
  },
  "pages": {
    "InvoicePage": {
      "description": "請求書管理ページ",
      "views": ["InvoiceList", "InvoiceDetail"],
      "dataFetching": {
        "queries": ["listInvoices", "getInvoice"],
        "mutations": ["allocate_payment"]
      }
    }
  },
  "components": {
    "InvoiceStatusBadge": {
      "type": "display",
      "entity": "invoice",
      "field": "status",
      "variants": {...}
    }
  },
  "frontendScenarios": {
    "FE-AT-001": {
      "title": "請求書一覧から消込を実行できる",
      "page": "InvoicePage",
      "steps": [
        { "action": "navigate", "to": "/invoices" },
        { "action": "click", "target": "row[0].action.allocate" },
        { "action": "fill", "field": "amount", "value": 80000 },
        { "action": "submit" },
        { "assert": "toast.success", "message": "消込完了" }
      ]
    }
  }
}
```

### 2. フロントエンドタスクパッケージ生成

```
generate_frontend_task_package(page_name, framework="react")
    ↓
.mesh/frontend/tests/e2e/{page}.spec.ts    ← Playwright/Cypressテスト
.mesh/frontend/tests/unit/{page}.test.tsx  ← コンポーネントテスト
tasks/frontend/{page}/TASK.md              ← 実装要件
tasks/frontend/{page}/context.json         ← 必要なview/entity/function
src/pages/{page}/index.tsx                 ← ページスケルトン
src/pages/{page}/components/*.tsx          ← コンポーネントスケルトン
```

### 3. フロントエンド用DependencyGraph

```
page → views → entity
           ↘ actions → functions → entities
               ↘ dataFetching → queries/mutations
```

### 4. タスク管理の拡張

```python
# バックエンドと同様のフロー
activate_frontend_task(page_name="InvoicePage", framework="react")
    → git worktree作成
    → tasks/frontend/{page}/配下のファイルは読み取り専用
    → src/pages/{page}/配下のみ編集可能

complete_frontend_task(page_name, test_results)
    → E2Eテスト結果確認
    → commit & PR
```

---

## 実装アプローチ案

### アプローチA: スキーマ拡張優先
1. `pages`, `components`, `frontendScenarios`の定義をスキーマに追加
2. バリデーターを拡張
3. 生成器を実装

### アプローチB: 生成器優先
1. 既存のviews/routesからコンポーネント生成器を実装
2. E2Eテスト生成器を実装
3. 必要に応じてスキーマを拡張

### アプローチC: タスク管理優先
1. フロントエンド用のタスクマネージャーを実装
2. 既存のviews/routesベースでスケルトン生成
3. 段階的にスキーマを拡張

---

## 次のステップ

詳細な実装計画の策定が必要:
- 各アプローチのPros/Cons
- 具体的な実装ステップ
- 優先順位付け
