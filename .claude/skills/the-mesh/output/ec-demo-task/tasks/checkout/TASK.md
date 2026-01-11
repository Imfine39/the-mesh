# Task: checkout

## 概要
カートの内容で注文を確定

## 入力パラメータ

- `cartId`: string (必須)
- `userId`: string (必須)

## 前提条件 (Preconditions)

- なし

## 事後処理 (Post-actions)

- CREATE: {'target': 'Order', 'data': {'id': {'type': 'call', 'function': 'generateId'}, 'userId': {'type': 'input', 'field': 'userId'}, 'totalAmount': {'type': 'literal', 'value': 0}, 'status': {'type': 'literal', 'value': 'PENDING'}, 'createdAt': {'type': 'call', 'function': 'now'}}}

## エラーケース

- なし

## 関連テスト

このタスク完了後、以下のテストがGREENであることを確認:

- `test_checkout_at.py` (このタスクのAT)
- `test_unit.py` (UT)

### 影響を受ける可能性のある関連テスト
- `test_cancelOrder_at.py`

## テスト実行

```bash
# このタスクフォルダで実行
pytest  # Python
# または
npx jest  # Node.js
```