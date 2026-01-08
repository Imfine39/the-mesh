# 式言語仕様 (Formula Language Specification)

## 概要

spec YAML内で使用する式言語の仕様を定義する。
Python式ベースであり、`formula_evaluator.py`によって評価される。

## 基本構文

### 1. フィールドアクセス

```
entity.field
```

**例:**
```yaml
"invoice.amount"      # → state['invoice']['amount']
"invoice.status"      # → state['invoice']['status']
```

### 2. 入力参照

```
input.field
```

**例:**
```yaml
"input.amount"        # → input['amount']
```

### 3. 比較演算子

```
==  !=  >  <  >=  <=
```

**例:**
```yaml
"invoice.status == 'open'"
"remaining(invoice) >= input.amount"
```

### 4. 論理演算子

```
and  or  not  implies
```

**例:**
```yaml
"invoice.status == 'open' and input.amount > 0"
"remaining(invoice) == 0 implies invoice.status == 'closed'"
```

`implies`は論理含意（A → B = ¬A ∨ B）として評価される。

### 5. derived関数呼び出し

```
derived_name(entity)
```

**例:**
```yaml
"remaining(invoice)"  # → invoiceの残額を計算
```

derived関数は`derived:`セクションで定義された計算式を参照する。

### 6. 集約関数（sum with where）

```
sum(item.field where item.foreign_key = target.id)
```

**例:**
```yaml
"sum(allocation.amount where allocation.invoice_id = invoice.id)"
```

**変換後:**
```python
sum(item['amount'] for item in state['allocation']
    if item['invoice_id'] == state['invoice']['id'])
```

### 7. エラーチェック

```
error(ERROR_CODE)
```

**例:**
```yaml
"input.amount > remaining(invoice) implies error(OVER_ALLOCATION)"
```

シナリオ実行時のエラー状態と照合される。

## 型

### サポートする型

| 型 | 例 | 備考 |
|---|---|------|
| int | `100000` | 整数 |
| string | `'open'` | シングルクォート |
| bool | `true`, `false` | 真偽値 |
| enum | `enum[open, closed]` | 列挙型（state定義用） |
| list | `[]` | コレクション（allocation等） |

## 制限事項

### セキュリティ制限

以下の操作は禁止されている：
- `import`文
- 組み込み関数（sum, len, abs, min, max以外）
- ファイル操作
- ネットワーク操作

### 未サポート構文

現在のPoCでは以下は未対応：
- ネストした関数呼び出し: `f(g(x))`
- 複雑な条件式: `if-else`
- ラムダ式
- 日付/時刻演算

## 使用例

### derived定義

```yaml
derived:
  remaining:
    description: 請求の残額
    formula: "invoice.amount - sum(allocation.amount where allocation.invoice_id = invoice.id)"

  net_amount:
    description: 税込み・割引後の金額
    formula: "invoice.amount * (1 - invoice.discount_rate) + invoice.tax_amount"
```

### pre条件

```yaml
pre:
  - expr: "invoice.status == 'open'"
    reason: "クローズ済み請求には消込できない"
```

### error条件

```yaml
error:
  - code: OVER_ALLOCATION
    when: "remaining(invoice) < input.amount"
```

### シナリオassert

```yaml
then:
  assert:
    - "remaining(invoice) == 20000"
    - "invoice.status == 'open'"
```

### verifies（要件検証式）

```yaml
verifies:
  - expr: "remaining(invoice) == 0 implies invoice.status == 'closed'"
```

## 評価フロー

```
1. 式をパース
2. Python式に変換
   - entity.field → state['entity']['field']
   - derived(x) → _eval_derived('derived', 'x')
   - sum(...where...) → リスト内包表記
   - implies → not A or B
3. AST安全性検証
4. 制限環境でeval実行
5. 結果を返却
```

## 拡張予定

- [ ] 日付/時刻演算: `now()`, `date_diff()`
- [ ] 文字列操作: `concat()`, `length()`
- [ ] 条件式: `if(cond, then, else)`
- [ ] 複数エンティティの結合: `join()`
