# モックHTML形式仕様

## 概要

要件定義フェーズで使用するモックHTMLの形式仕様。data属性を使って意味情報を付与し、the-mesh specへの自動変換を可能にする。

## ファイル命名規則

```
{screen_name}.mock.html
```

例:
- `orders.mock.html`
- `order_detail.mock.html`
- `login.mock.html`

---

## data属性一覧

### 画面レベル属性

| 属性 | 説明 | 値の例 |
|-----|------|-------|
| `data-mesh-view` | View名（PascalCase） | `OrderListView` |
| `data-mesh-route` | ルートパス | `/orders`, `/orders/:id` |
| `data-mesh-title` | ページタイトル（マーカー） | - |
| `data-mesh-guard` | アクセス制御 | `auth`, `role:admin` |
| `data-mesh-layout` | レイアウトコンポーネント | `MainLayout`, `AuthLayout` |

```html
<html data-mesh-view="OrderListView"
      data-mesh-route="/orders"
      data-mesh-layout="MainLayout">
<head>
  <title data-mesh-title>注文一覧</title>
</head>
```

### コンポーネントレベル属性

| 属性 | 説明 | 値の例 |
|-----|------|-------|
| `data-mesh-component` | コンポーネント名 | `OrderCard`, `shared:Header` |
| `data-mesh-entity` | 対象エンティティ | `Order` |
| `data-mesh-type` | 表示タイプ | `list`, `detail`, `form`, `card` |
| `data-mesh-props` | 受け取るprops | `order, onDelete, isLoading` |

```html
<div data-mesh-component="OrderCard"
     data-mesh-entity="Order"
     data-mesh-type="card"
     data-mesh-props="order, onDelete">
  ...
</div>
```

#### 共有コンポーネント参照

`shared:` プレフィックスで共有コンポーネントを参照:

```html
<header data-mesh-component="shared:Header">
<nav data-mesh-component="shared:Pagination">
<footer data-mesh-component="shared:Footer">
```

### フィールドレベル属性

| 属性 | 説明 | 値の例 |
|-----|------|-------|
| `data-mesh-field` | バインドするフィールド | `Order.amount`, `user.email` |
| `data-mesh-format` | 表示フォーマット | `currency`, `date`, `datetime`, `percent` |
| `data-mesh-sortable` | ソート可能（フラグ） | - |
| `data-mesh-filter` | フィルター演算子 | `eq`, `ne`, `like`, `gte`, `lte` |
| `data-mesh-label` | ラベルテキスト | `開始日` |
| `data-mesh-placeholder` | プレースホルダー | `検索...` |

```html
<th data-mesh-field="Order.id" data-mesh-sortable>注文ID</th>
<td data-mesh-field="Order.amount" data-mesh-format="currency">¥10,000</td>

<input data-mesh-field="Order.status"
       data-mesh-filter="eq"
       data-mesh-label="ステータス">
```

### アクションレベル属性

| 属性 | 説明 | 値の例 |
|-----|------|-------|
| `data-mesh-action` | 呼び出す関数名 | `create_order`, `delete_order` |
| `data-mesh-navigate` | 遷移先パス | `/orders/{id}`, `/orders/new` |
| `data-mesh-confirm` | 確認ダイアログメッセージ | `本当に削除しますか？` |
| `data-mesh-visible` | 表示条件式 | `order.status == 'OPEN'` |
| `data-mesh-disabled` | 無効条件式 | `isLoading` |
| `data-mesh-role` | 必要な権限（カンマ区切り） | `admin`, `admin,manager` |

```html
<button data-mesh-action="delete_order"
        data-mesh-confirm="本当に削除しますか？"
        data-mesh-visible="order.status == 'OPEN'"
        data-mesh-role="admin">
  削除
</button>

<a data-mesh-navigate="/orders/{order.id}">詳細を見る</a>
```

### ループ・条件属性

| 属性 | 説明 | 値の例 |
|-----|------|-------|
| `data-mesh-each` | ループ変数 | `order in orders` |
| `data-mesh-if` | 条件付き表示 | `orders.length > 0` |
| `data-mesh-else` | else ブロック（フラグ） | - |

```html
<tbody>
  <tr data-mesh-each="order in orders">
    <td data-mesh-field="order.id">ORD-001</td>
    ...
  </tr>
</tbody>

<div data-mesh-if="orders.length == 0">
  注文がありません
</div>
```

### フォーム属性

| 属性 | 説明 | 値の例 |
|-----|------|-------|
| `data-mesh-form` | フォーム名 | `OrderForm`, `LoginForm` |
| `data-mesh-submit` | 送信時アクション | `create_order` |
| `data-mesh-input` | 入力フィールド名 | `amount`, `customer_id` |
| `data-mesh-required` | 必須フラグ | - |
| `data-mesh-validation` | バリデーションルール | `min:0`, `max:100`, `email` |

```html
<form data-mesh-form="CreateOrderForm"
      data-mesh-submit="create_order">

  <input data-mesh-input="customer_id"
         data-mesh-required
         data-mesh-label="顧客ID">

  <input data-mesh-input="amount"
         data-mesh-required
         data-mesh-validation="min:0"
         data-mesh-label="金額"
         type="number">

  <button type="submit"
          data-mesh-disabled="isSubmitting">
    作成
  </button>
</form>
```

### スタイル・状態属性

| 属性 | 説明 | 値の例 |
|-----|------|-------|
| `data-mesh-style` | 条件付きスタイル | `status:OPEN=blue,PAID=green` |
| `data-mesh-loading` | ローディング状態表示 | - |
| `data-mesh-error` | エラー表示エリア | - |

```html
<span data-mesh-field="order.status"
      data-mesh-style="status:OPEN=text-blue-500,PAID=text-green-500">
  未処理
</span>

<div data-mesh-loading>読み込み中...</div>
<div data-mesh-error>エラーが発生しました</div>
```

---

## 完全なサンプル

```html
<!-- orders.mock.html -->
<!DOCTYPE html>
<html data-mesh-view="OrderListView"
      data-mesh-route="/orders"
      data-mesh-layout="MainLayout">
<head>
  <meta charset="UTF-8">
  <title data-mesh-title>注文一覧</title>
</head>
<body>

  <!-- 共通ヘッダー -->
  <header data-mesh-component="shared:Header">
    <nav data-mesh-guard="auth">
      <span>ログイン中: user@example.com</span>
    </nav>
  </header>

  <main>
    <!-- ページヘッダー -->
    <div data-mesh-component="PageHeader">
      <h1>注文一覧</h1>
      <button data-mesh-action="create_order"
              data-mesh-navigate="/orders/new"
              data-mesh-role="admin,manager">
        新規作成
      </button>
    </div>

    <!-- 検索フォーム -->
    <form data-mesh-component="OrderSearchForm">
      <select data-mesh-field="Order.status"
              data-mesh-filter="eq"
              data-mesh-label="ステータス">
        <option value="">すべて</option>
        <option value="OPEN">未処理</option>
        <option value="PAID">支払済</option>
        <option value="SHIPPED">発送済</option>
      </select>

      <input data-mesh-field="Order.created_at"
             data-mesh-filter="gte"
             data-mesh-label="開始日"
             type="date">

      <input data-mesh-field="Order.created_at"
             data-mesh-filter="lte"
             data-mesh-label="終了日"
             type="date">

      <button type="submit">検索</button>
    </form>

    <!-- ローディング表示 -->
    <div data-mesh-loading>
      読み込み中...
    </div>

    <!-- エラー表示 -->
    <div data-mesh-error>
      データの取得に失敗しました
    </div>

    <!-- 注文一覧テーブル -->
    <table data-mesh-component="OrderTable"
           data-mesh-entity="Order"
           data-mesh-type="list">
      <thead>
        <tr>
          <th data-mesh-field="Order.id" data-mesh-sortable>注文ID</th>
          <th data-mesh-field="Order.customer.name">顧客名</th>
          <th data-mesh-field="Order.amount" data-mesh-sortable>金額</th>
          <th data-mesh-field="Order.status">ステータス</th>
          <th data-mesh-field="Order.created_at" data-mesh-sortable>作成日</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr data-mesh-each="order in orders">
          <td data-mesh-field="order.id">ORD-001</td>
          <td data-mesh-field="order.customer.name">山田太郎</td>
          <td data-mesh-field="order.amount" data-mesh-format="currency">¥10,000</td>
          <td>
            <span data-mesh-field="order.status"
                  data-mesh-style="status:OPEN=bg-blue-100,PAID=bg-green-100,SHIPPED=bg-gray-100">
              未処理
            </span>
          </td>
          <td data-mesh-field="order.created_at" data-mesh-format="date">2024-01-15</td>
          <td>
            <button data-mesh-action="view_order"
                    data-mesh-navigate="/orders/{order.id}">
              詳細
            </button>
            <button data-mesh-action="delete_order"
                    data-mesh-confirm="注文ID: {order.id} を削除しますか？"
                    data-mesh-visible="order.status == 'OPEN'"
                    data-mesh-role="admin">
              削除
            </button>
          </td>
        </tr>
      </tbody>
    </table>

    <!-- 空状態 -->
    <div data-mesh-if="orders.length == 0"
         data-mesh-component="EmptyState">
      <p>注文がありません</p>
      <button data-mesh-navigate="/orders/new">最初の注文を作成</button>
    </div>

    <!-- ページネーション -->
    <nav data-mesh-component="shared:Pagination"
         data-mesh-props="totalPages, currentPage, onPageChange">
      <button data-mesh-disabled="currentPage == 1">前へ</button>
      <span>1 / 10</span>
      <button data-mesh-disabled="currentPage == totalPages">次へ</button>
    </nav>
  </main>

  <!-- 共通フッター -->
  <footer data-mesh-component="shared:Footer">
    <p>&copy; 2024 Example Corp.</p>
  </footer>

</body>
</html>
```

---

## 変換結果（the-mesh spec）

上記モックから生成されるspec:

```json
{
  "views": {
    "OrderListView": {
      "description": "注文一覧",
      "entity": "Order",
      "type": "list",
      "fields": [
        {"field": "id", "sortable": true},
        {"field": "customer.name"},
        {"field": "amount", "sortable": true, "format": "currency"},
        {"field": "status", "style": {"OPEN": "bg-blue-100", "PAID": "bg-green-100", "SHIPPED": "bg-gray-100"}},
        {"field": "created_at", "sortable": true, "format": "date"}
      ],
      "filters": [
        {"field": "status", "op": "eq"},
        {"field": "created_at", "op": "gte"},
        {"field": "created_at", "op": "lte"}
      ],
      "actions": [
        {"function": "view_order", "navigate": "/orders/{id}"},
        {"function": "delete_order", "confirm": "注文ID: {id} を削除しますか？", "visible_when": "status == 'OPEN'", "roles": ["admin"]},
        {"function": "create_order", "navigate": "/orders/new", "roles": ["admin", "manager"]}
      ],
      "components": {
        "local": ["PageHeader", "OrderSearchForm", "OrderTable", "EmptyState"],
        "shared": ["Header", "Pagination", "Footer"]
      }
    }
  },
  "routes": {
    "/orders": {
      "view": "OrderListView",
      "title": "注文一覧",
      "layout": "MainLayout",
      "guards": [{"type": "auth"}]
    }
  },
  "components": {
    "OrderSearchForm": {
      "type": "form",
      "fields": ["status", "created_at"]
    },
    "OrderTable": {
      "type": "list",
      "entity": "Order"
    },
    "EmptyState": {
      "type": "empty"
    }
  }
}
```

---

## パーサー仕様（予定）

```bash
# モックHTMLをパース
mesh-mosaic parse orders.mock.html

# 既存specにマージ
mesh-mosaic merge orders.mock.html --spec project.json

# 検証（specとの整合性チェック）
mesh-mosaic validate orders.mock.html --spec project.json
```
