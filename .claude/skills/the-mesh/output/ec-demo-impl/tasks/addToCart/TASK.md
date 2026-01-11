# Task: addToCart

## 概要
商品をカートに追加

## 入力パラメータ

- `cartId`: string (必須)
- `productId`: string (必須)
- `quantity`: int (必須)

## 前提条件 (Preconditions)

1. {}

## 事後処理 (Post-actions)

- CREATE: {'target': 'CartItem', 'data': {'id': {'type': 'call', 'function': 'generateId'}, 'cartId': {'type': 'input', 'field': 'cartId'}, 'productId': {'type': 'input', 'field': 'productId'}, 'quantity': {'type': 'input', 'field': 'quantity'}, 'unitPrice': {'type': 'ref', 'path': 'product.price'}}}
- UPDATE: {'target': 'Product', 'id': {'type': 'input', 'field': 'productId'}, 'set': {'stock': {'type': 'binary', 'op': 'sub', 'left': {'type': 'self', 'field': 'stock'}, 'right': {'type': 'input', 'field': 'quantity'}}}}

## エラーケース

- なし

## 関連テスト

このタスク完了後、以下のテストがGREENであることを確認:

- `test_addToCart_at.py` (このタスクのAT)
- `test_unit.py` (UT)

### 影響を受ける可能性のある関連テスト
- `test_removeFromCart_at.py`

## テスト実行

```bash
# このタスクフォルダで実行
pytest  # Python
# または
npx jest  # Node.js
```