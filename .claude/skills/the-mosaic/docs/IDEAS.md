# The Mosaic - 設計アイデア

## 概要

要件定義フェーズでモックHTMLを使ってやり取りし、最終的にthe-mesh specに変換するフレームワーク。

## 背景・課題

### 現状の流れ
```
要件定義 → モック/ワイヤーフレーム → ??? → the-mesh → 実装
```

**問題**: モック → the-mesh の橋渡しが未定義

### the-meshのバックエンド側でうまくいっている理由

```
TRIR Spec (functions)
├── input: 入力の型・制約
├── pre: 事前条件（バリデーション）
├── post: 事後条件（何が保存されるか）
└── error: エラーケース

→ テスト自動生成 → 実装がテストをパス = 仕様通り
```

**核心**: 「何を検証すべきか」が仕様から導出可能

---

## フロントエンドで考えるべきバグ類型

| バグ類型 | 例 | 仕様で防げるか？ |
|---------|---|----------------|
| **型の不整合** | APIレスポンスと画面表示の型ズレ | ✅ TypeScript/Zod |
| **表示条件ミス** | 権限がないのにボタン表示 | ⚠️ 仕様化可能（要対応） |
| **フォームバリデーション** | 必須項目の抜け | ✅ Zod |
| **状態遷移ミス** | 送信中に再送信可能 | ⚠️ StateMachine拡張? |
| **API連携ミス** | 存在しないエンドポイント呼び出し | ✅ OpenAPI |
| **ナビゲーションバグ** | 不正な画面遷移 | ⚠️ routes定義で可能 |

---

## モックから抽出すべき情報

```
モック/ワイヤーフレーム
├── 画面一覧 → routes
├── 各画面の構成要素 → views.fields
├── アクション（ボタン等） → views.actions
├── 表示条件 → views.fields[].visible_when?
├── 権限制御 → routes.guards
└── フォームバリデーション → functions.input + pre
```

---

## タスク粒度の検討

### Option A: View（画面）単位

```json
{
  "views": {
    "OrderListView": {
      "entity": "Order",
      "type": "list",
      "components": ["OrderCard", "Pagination", "SearchForm"],
      "functions": ["list_orders", "delete_order"]
    }
  }
}
```

**メリット**: ユーザーストーリーに近い、モックとの対応が明確
**デメリット**: 共通コンポーネントの変更時に影響が大きい

### Option B: Component単位

```json
{
  "components": {
    "OrderCard": {
      "props": {
        "order": { "type": { "ref": "Order" } },
        "onDelete": { "type": "function" }
      },
      "state": ["isDeleting"],
      "tests": ["renders order info", "calls onDelete when clicked"]
    }
  }
}
```

**メリット**: 再利用性が高い、テストが局所的
**デメリット**: 画面全体の動作確認が別途必要

### Option C: Feature単位（推奨案）

```json
{
  "features": {
    "order_management": {
      "routes": ["/orders", "/orders/:id"],
      "views": ["OrderListView", "OrderDetailView"],
      "functions": ["create_order", "list_orders", "update_order"],
      "components": {
        "shared": ["OrderCard", "OrderForm"],
        "local": ["OrderListHeader"]
      }
    }
  }
}
```

**推奨**: Feature単位をベースに、共通コンポーネントは別タスクとして切り出す

---

## 共通部分の扱い

```
共通コンポーネント（Header, Button, Form など）
│
├── 独立したタスクとして管理
│   tasks/shared/Button/
│   tasks/shared/FormInput/
│
└── 依存関係グラフで追跡
    OrderCard → Button を使用
    → Button 変更時、OrderCard のテストも再実行対象
```

### DependencyGraph 拡張案

```python
class NodeType(Enum):
    # 既存
    ENTITY = "entity"
    FUNCTION = "function"

    # フロントエンド追加
    VIEW = "view"
    ROUTE = "route"
    COMPONENT = "component"
    FEATURE = "feature"
```

---

## やり取りの流れ

### 1回目: 初期モック
```
User: 注文一覧画面のモックを作って

Claude: [orders.mock.html を生成]
        ・一覧表示
        ・検索・フィルター
        ・ページネーション
```

### 2回目: フィードバック
```
User: ステータスで色分けしたい
      管理者だけ削除ボタン見せて

Claude: [モック更新]
        data-mesh-style="status:OPEN=blue"
        data-mesh-role="admin" 追加
```

### 3回目: 確定 → spec生成
```
User: これでOK、specに変換して

Claude: [mesh-parse 実行]
        views/routes/components 生成
        既存specにマージ
```

---

## 要件定義フェーズで決めるもの/決めないもの

| 決める | 決めない |
|-------|---------|
| 画面構成 | 具体的なスタイル |
| データ項目 | アニメーション |
| アクション | エラーメッセージ文言 |
| 表示条件 | APIエンドポイント詳細 |
| 権限 | 実装詳細 |

---

## バックエンドspecとの連携

```
モックから抽出した action: "create_order"
            ↓
既存spec の functions.create_order と自動リンク
            ↓
input/output の型が一致するかチェック
```

---

## 次のステップ

1. [ ] MOCK_FORMAT.md の詳細化
2. [ ] パーサー実装（mock HTML → JSON）
3. [ ] the-mesh schema への views/routes/components 定義追加
4. [ ] テスト生成（コンポーネントテスト、E2Eテスト）
5. [ ] タスクパッケージ生成（フロントエンド版）

---

## 検討事項

### Q1: data属性方式の代替案

**現案: data属性**
```html
<button data-mesh-action="create_order" data-mesh-role="admin">
```

**代替1: コメントベース**
```html
<!-- mesh: {action: "create_order", role: "admin"} -->
<button>新規作成</button>
```

**代替2: 別ファイル**
```
orders.mock.html  # 純粋なHTML
orders.mock.json  # メタ情報
```

### Q2: フレームワーク非依存 vs 特定フレームワーク

- React/Next.js 特化？
- Vue/Nuxt 対応？
- フレームワーク非依存のHTML/CSS？

### Q3: デザインシステムとの統合

- Tailwind CSS?
- 既存デザインシステム?
- カスタムコンポーネントライブラリ?
