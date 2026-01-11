# Test Generator Analysis

## 目的
各テストジェネレーターが「何をspecから使うべきか」「何が自動生成可能か」「何が不可能か」を明確にする。

---

## Spec から取得可能な情報

```
entities:
  - fields: {name, type, required, ref, enum, min, max, description}
  - parent: 親エンティティ名

commands:
  - input: {name, type, required, min, max}
  - output: {name, type}
  - pre: [{expr, reason}]  # 事前条件
  - post: [{action: create/update/delete, target, data/set/id}]
  - errors: [{code, status, message}]

scenarios:
  - given: [{entity, id, data}]  # テストデータ
  - when: {command, input}
  - then: [{entity, id, expect} | {output: {...}}]

stateMachines:
  - entity: 対象エンティティ
  - field: 状態フィールド
  - states: [状態リスト]
  - transitions: [{from, to, command, guard?}]

derived:
  - 計算フィールド定義

invariants:
  - ビジネスルール（常に成り立つべき条件）

roles:
  - 権限定義
```

---

## テストタイプ別分析

### 1. AT (Acceptance Test) - シナリオベース

**使用するspec情報:**
- `scenarios` (given/when/then)

**自動生成可能:**
- [x] テスト構造（describe/it）
- [x] given からのテストデータ setup
- [x] when からの関数呼び出し
- [x] then からのアサーション

**自動生成不可能/困難:**
- [ ] scenariosが定義されてない場合のテストデータ
- [ ] 複雑な事前状態（複数エンティティの関連）
- [ ] 暗黙の依存関係

**対応方針:**
```
scenarios が存在する場合:
  → 完全自動生成可能

scenarios が存在しない場合:
  → テンプレート + TODO コメント生成
  → AI手書きまたはユーザー定義が必要
```

---

### 2. UT (Unit Test) - 境界値/エッジケース

**使用するspec情報:**
- `entities.fields` (type, required, min, max, enum)
- `commands.input` (type, required, min, max)

**自動生成可能:**
- [x] 必須フィールド欠落テスト
- [x] 型違反テスト（string に number など）
- [x] min/max 境界値テスト
- [x] enum 不正値テスト

**自動生成不可能/困難:**
- [ ] ビジネスロジック固有の境界値
- [ ] フィールド間の依存関係
- [ ] 組み合わせ爆発するケース

**対応方針:**
```
min/max/enum/required が定義されている場合:
  → 自動生成

それ以外の境界値:
  → 基本テンプレート + TODO
```

---

### 3. PC (PostCondition) - 副作用検証

**使用するspec情報:**
- `commands.post` (create/update/delete アクション)
- `entities` (フィールド定義、ref、parent)

**自動生成可能:**
- [x] create アクションの検証（repository.create 呼び出し）
- [x] update アクションの検証（repository.update 呼び出し）
- [x] delete アクションの検証（repository.delete 呼び出し）
- [x] ref/parent からの依存エンティティ setup

**自動生成不可能/困難:**
- [ ] 計算フィールドの期待値（derived が定義されてない場合）
- [ ] 複雑なビジネスロジックによる値変換
- [ ] 条件分岐による異なる副作用

**対応方針:**
```
post アクションが明示的な場合:
  → アクション発生の検証は自動生成
  → フィールド値は:
    - literal → 値を検証
    - input参照 → 入力値と一致を検証
    - 計算式/ref → 存在のみ検証 + TODO

依存エンティティ:
  → entities.fields.ref を使用（xxxId 推測ではなく）
  → entities.parent を使用
```

---

### 4. ST (State Transition) - 状態遷移

**使用するspec情報:**
- `stateMachines` (states, transitions)

**自動生成可能:**
- [x] 有効な遷移テスト（transition.command 実行で from → to）
- [x] 無効な遷移テスト（定義されてない遷移は失敗）
- [x] ガード条件テスト（guard が満たされない場合は失敗）

**自動生成不可能/困難:**
- [ ] stateMachines が定義されてない場合
- [ ] 複合状態（複数フィールドの組み合わせ）

**対応方針:**
```
stateMachines が定義されている場合:
  → 完全自動生成

定義されてない場合:
  → enum フィールドから推測してテンプレート生成
  → TODO コメントで遷移定義を促す
```

---

### 5. Idempotency - 冪等性

**使用するspec情報:**
- `commands` (特に create 以外)
- `testStrategies.idempotency.targets`

**自動生成可能:**
- [x] 同じ入力で2回実行して同じ結果
- [x] 副作用が1回分のみ

**自動生成不可能/困難:**
- [ ] どの操作が冪等であるべきか（ビジネス要件）
- [ ] 冪等性を保証するキー（どのフィールドで重複判定？）

**対応方針:**
```
testStrategies.idempotency.targets が定義されている場合:
  → 対象コマンドのみテスト生成

定義されてない場合:
  → update/get 系は冪等想定でテンプレート
  → create 系は TODO
```

---

### 6. Concurrency - 並行性

**使用するspec情報:**
- `testStrategies.concurrency`
- `entities` (楽観ロックフィールド: version, updatedAt)

**自動生成可能:**
- [x] 並列実行のテスト構造
- [x] 競合検出テスト（同じリソースへの同時書き込み）

**自動生成不可能/困難:**
- [ ] 期待される振る舞い（どれが勝つか、エラーか）
- [ ] デッドロックシナリオ
- [ ] 実行順序の制御

**対応方針:**
```
ほぼすべてテンプレート + TODO
並行テストは環境依存が大きいため、構造のみ提供
```

---

### 7. Authorization - 認可

**使用するspec情報:**
- `roles`
- `commands` に紐づく権限定義

**自動生成可能:**
- [x] ロールごとのアクセステスト構造

**自動生成不可能/困難:**
- [ ] roles が定義されてない場合
- [ ] 複雑な権限ルール（リソース所有者のみなど）

**対応方針:**
```
roles が定義されている場合:
  → ロール × コマンド のマトリックステスト

定義されてない場合:
  → TODO のみ
```

---

### 8. Empty/Null - null ハンドリング

**使用するspec情報:**
- `entities.fields.required`
- `commands.input.required`

**自動生成可能:**
- [x] required=false のフィールドに null を渡すテスト
- [x] required=true のフィールドに null を渡すテスト（エラー期待）

**自動生成不可能/困難:**
- [ ] null の意味がビジネスロジック依存の場合

**対応方針:**
```
required フラグがある場合:
  → 自動生成

ない場合:
  → 全フィールド null テストをテンプレート生成
```

---

### 9. Reference Integrity - 参照整合性

**使用するspec情報:**
- `entities.fields.ref`
- `entities.parent`

**自動生成可能:**
- [x] 存在しない参照への操作テスト
- [x] 参照先削除時のテスト

**自動生成不可能/困難:**
- [ ] カスケード削除 vs 削除拒否（どちらが期待動作か）
- [ ] 孤児レコードの扱い

**対応方針:**
```
ref/parent が定義されている場合:
  → 参照先不在テストは自動生成
  → 削除時の挙動は TODO（CASCADE/RESTRICT の指定があれば対応）

定義されてない場合:
  → xxxId フィールドから推測してテンプレート（非推奨）
```

---

### 10. Temporal - 時間関連

**使用するspec情報:**
- `entities.fields` (type: datetime)
- `deadlines`
- `schedules`

**自動生成可能:**
- [x] 日付境界テスト（月末、年末）
- [x] タイムゾーンテスト構造

**自動生成不可能/困難:**
- [ ] ビジネス日付ロジック（営業日計算など）
- [ ] 相対時間の扱い

**対応方針:**
```
datetime フィールドがある場合:
  → 基本的な境界値テスト

deadlines/schedules がある場合:
  → 期限切れテスト構造

それ以外:
  → TODO
```

---

## 共通の設計原則

### 1. Spec情報の正しい使用

```python
# ❌ 悪い例：命名規則から推測
if field_name.endswith("Id"):
    entity_name = field_name[:-2].capitalize()

# ✅ 良い例：spec の ref を使用
if field_def.get("ref"):
    ref_entity = field_def["ref"]
```

### 2. 自動生成不可能な部分のマーキング

```typescript
// @mesh-generated: auto
it('should create CartItem', async () => {
  // 自動生成コード
});

// @mesh-generated: template
// TODO: 以下のテストは手動で実装が必要です
// - 理由: 計算ロジックがspecに定義されていません
it.todo('should calculate totalAmount correctly');
```

### 3. テストデータ生成の優先順位

1. `scenarios.given` があれば使用
2. `entities.fields` の定義から生成
3. デフォルト値でテンプレート生成 + TODO

### 4. MockContext の構造

```typescript
// entities から自動生成
interface MockContext {
  // entities の各エントリに対して
  [entityName]Repository: {
    create, get, getAll, update, delete,
    // ref フィールドに対して findByXxx を追加
  }
  // ヘルパー
  _set[EntityName]: (data) => void
}
```

---

## 実装状況

### 完了済み (2025-01)

1. [x] specから情報を取得するユーティリティを共通化
   - `spec_utils.py` を作成
   - `SpecAnalyzer`, `TestDataGenerator`, `MockContextGenerator`, `GenerationMarker` を実装

2. [x] `@mesh-generated: auto | template | manual` マーカーを導入
   - PC (PostCondition) ジェネレーターに実装
   - `auto`: 完全自動テスト可能
   - `template`: 一部手動実装が必要 (TODOコメント付き)

3. [x] PC (PostCondition) ジェネレーターを書き直し
   - specの`ref`/`parent`を使用して依存関係を正しく解決
   - `xxxId` パターンからのフォールバック推論も実装
   - 計算式(call/binary/ref)は `exists_only` チェックに

### ジェネレーター状況

| ジェネレーター | 状態 | 備考 |
|--------------|------|------|
| AT (jest_gen.py) | ◯ 問題なし | scenarios を直接使う |
| UT (jest_unit_gen.py) | ◯ 問題なし | constraint_inference で境界値生成 |
| ST (jest_state_transition_gen.py) | ◯ 問題なし | stateMachines を使う |
| PC (jest_postcondition_gen.py) | ◯ 書き直し完了 | spec_utils を使用 |

### 残作業

1. [ ] テスト実行時に TODO テストをレポート
2. [ ] 他ジェネレーター (idempotency, concurrency, etc.) のspec_utils対応
