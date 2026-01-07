# 計算可能な仕様書：検証結果・テンプレ・サンプル（会計ドメイン）

## 1. 検証結果（試作の結論）

**結論:**  
仕様書を「関数 + 状態 + 不変条件 + 導出式」として表現すると、**仕様の変更がどの処理結果に影響するかを機械的に追跡できる**。  
特に、**導出式（例: `remaining(invoice)`）の変更**は、消し込みや請求ステータス更新など複数の関数に波及するため、  
**依存関係の解決で影響範囲を算出できる**。

**今回の試作で確認できたポイント**

1. **API/処理を関数として定義できる**  
   入力・前提条件・状態変化を明示すれば、仕様の“計算可能化”が成立する。
2. **DB相当の状態を State として分離できる**  
   仕様書内で状態を定義し、関数は状態を参照・更新する形にできる。
3. **導出式が「影響の起点」になる**  
   `remaining(invoice)` の定義を変えると、消し込み判定や請求のステータス遷移が変わる。
4. **変更影響は依存関係から辿れる**  
   どの関数がどの導出式に依存するかを明示すれば、影響範囲を自動で列挙できる。

---

## 2. テンプレート（計算可能仕様書の最小構成）

以下のテンプレは、**会計ドメインに限らず汎用**で使える最小構成。

```yaml
meta:
  title: "<仕様タイトル>"
  version: "v0.1"

state:
  <entity_name>:
    <field>: <type>
    ...

functions:
  <function_name>(input):
    pre:
      - <前提条件>
    post:
      - <状態の更新>
    error:
      - <エラー条件>

derived:
  <derived_name>(<params>) = <導出式>

invariants:
  - <常に成立すべき不変条件>
```

**設計のポイント**

* `state` は **永続化されるもの**（DB相当）だけを書く。  
* `derived` は **状態から計算される値**（DBに持たないもの）を書く。  
* `functions` は **入力→状態更新**の関数として書く（副作用を明示）。  
* `invariants` は **常に守るルール**を宣言する（破ったらエラー）。

---

## 3. サンプル（会計：売上・入金・消し込み）

以下は **最小構成の“計算可能仕様書”サンプル**。

```yaml
meta:
  title: "Accounting Spec (Minimal)"
  version: "v0.1"

state:
  invoice:
    id: string
    customer_id: string
    amount: int
    status: ["open","closed"]
  payment:
    id: string
    customer_id: string
    amount: int
  allocation:
    invoice_id: string
    payment_id: string
    amount: int

functions:
  create_invoice(input):
    pre:
      - input.amount > 0
    post:
      - invoice.amount = input.amount
      - invoice.status = "open"

  register_payment(input):
    pre:
      - input.amount > 0
    post:
      - payment.amount = input.amount

  allocate_payment(input):
    pre:
      - invoice.status == "open"
      - payment.amount >= input.amount
      - remaining(invoice) >= input.amount
    post:
      - allocation.amount = input.amount
      - if remaining(invoice) == 0 then invoice.status = "closed"
    error:
      - if remaining(invoice) < input.amount then "OVER_ALLOCATION"

derived:
  remaining(invoice) = invoice.amount - sum(allocation.amount where invoice_id=invoice.id)

invariants:
  - remaining(invoice) >= 0
```

---

## 4. 影響検出のイメージ（仕様変更が波及する例）

### 変更例

`remaining(invoice)` の計算式を変更したとする。  
（例: 税額や割引を加味するよう変更）

### 影響

* `allocate_payment` の **前提条件 (`pre`)** に影響  
* `allocate_payment` の **ステータス更新条件** に影響  
* `invariants` の **成立条件** に影響

つまり、**導出式 → 関数 → 不変条件**の依存が辿れるため、  
**どの仕様結果が変わるかを機械的に列挙できる**。

---

## 5. 次にやると良いこと（実運用に向けて）

1. **DSLの形式を決める**（YAML/JSON/小さなPython DSLなど）
2. **仕様Lint** を作る  
   * 未定義参照  
   * 依存の循環  
   * 不変条件の不整合
3. **実行可能テスト** を定義する  
   * 正常ケース  
   * 異常ケース  
   * 境界値

---

## 6. まとめ

* 仕様書を「関数 + 状態 + 導出式 + 不変条件」に落とすと、**計算可能な仕様**になる。  
* 仕様変更は **依存関係から影響範囲を自動計算できる**。  
* 会計ドメイン（売上/入金/消し込み）は**最小構成でも成立する題材**。

---

## 7. 補足：いちばん注力すべきは「式を正しく作る」こと

**このアプローチの成否は「式（導出式・前提条件・不変条件）をどこまで正確に書けるか」に強く依存する。**  
式が正確であれば、以下が機械的に確定しやすくなる。

* **影響範囲**：どの関数・条件が変わるかを依存関係から追跡できる  
* **目指すべきゴール**：最終状態（期待結果）が式で固定される  
* **テスト観点**：境界値や異常系が式から直接導出できる  
* **実装漏れの検知**：式と実装の差分がテストで顕在化しやすい

**結論として、最も重要なのは「正しい式を作る」工程。**  
ここが固まれば、以降の実装・影響分析・テスト設計は極めて機械的に進められる。

---

## 8. 追加論点：エッジケースは式側で徹底的に扱うべき

**エッジケースは「式を正しくするための材料」なので、式側で徹底的に吸収する必要がある。**  
具体的には、以下を式として明文化する。

* **境界値**（0円、上限、端数、締め日）
* **例外系**（重複入金、過入金、未入金、消し込み不能）
* **状態遷移の例外**（締め後の修正、取り消し、再計上）
* **時間依存**（当日/翌日/締め後の扱い）

これらは **UI/画面の都合ではなく、式の正しさの問題**。 
画面側は「式が許可する入力/操作のみを提供する」形に寄せた方が、仕様ブレが起きにくい。

---

## 9. 画面と式の役割分担（議論のたたき台）

**式（仕様）側が担うこと**

* 計算ルール・前提条件・不変条件
* 状態遷移の正しさ（いつ何が可能か）
* 影響範囲やテスト観点の根拠

**画面（UI）側が担うこと**

* 入力の導線・視認性・操作体験
* 式に沿った入力制約（無効入力を防ぐ）
* 式の結果をわかりやすく表示する

> 方向性としては **「式が正、画面はその表現と補助」**。  
> 画面の都合で式を変えるのではなく、式が先に確定して画面が追随する流れが安定しやすい。
