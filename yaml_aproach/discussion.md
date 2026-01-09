# SDD議論 統合メモ（作業用）

## 目的

* これまでの議論を一元化し、仕様駆動開発（SDD）の実運用に耐える形に整理する
* Claude Code / Skills / agent.md 等への落とし込み前提で、抜け漏れを防ぐ

## 前提・憲法（合意事項）

* Spec-first / Test-first
* 推測実装・暗黙知の禁止
* レイヤー間トレーサビリティ（経営→要件→テスト）

## レイヤー整理（統合版：仕様駆動×アジャイル×AI並列）

### 重要：レイヤーは「情報の安定度」と「正の仕様（Source of truth）」で分ける

* Layer A：揺れてよい（探索・発見・反復）
* Layer B：守る＝正（機械が守る契約・実行可能）
* Layer C：実装（コード）

> 以前の整理（A/B/C/D）で言うと、**D（テスト）を B に統合**した形。
> 「正の仕様＝実行可能なもの（テスト/契約/マイグレーション）」を最優先にする。

### Layer A（揺れてよい）

* 業務文章（困りごと・期待結果）
* モックへのコメント
* エッジケースの気づき（Backlog）
* 要求ID（REQ-*）

### Layer B（守る＝正 / Source of truth）

* 受け入れ基準テスト（AT-* / Given-When-Then）
* OpenAPI / event schema
* DB migrations（＋互換性ルール）

#### Layer B は「ズラーっとテストが並ぶ」？（答え：並ぶが、無限に増やさない）

* 原則：**REQ は必ず 1本以上のATに紐づく**（REQ→ATカバレッジ）
* ただし：**REQ=AT 1対1に固定しない**（1つのATが複数REQをカバーしてOK）
* ケース爆発は「Edge Case Backlog → ディシジョンテーブル化」で段階的に成熟させる

#### Layer B の中身（具体像）

1. **AT（受入テスト）**

* UIモック段階：Playwright等で「遷移/表示/入力制約」のスモーク保証
* 本実装段階：同じATを本番経路で流し回帰テストにする
* AT には機械検出できる形で REQ-* を紐付ける（frontmatter or テストメタ）

2. **API契約（OpenAPI）**

* OpenAPI は “正” の契約として差分比較し、breaking をCIで落とす
* いわゆる APIテスト（APIT）が必要なら、次の2つを分ける

  * **契約テスト**：OpenAPI準拠（schema/型/必須など）を検証
  * **挙動テスト**：代表ケースで endpoint の振る舞いを検証（必要最小限）

3. **DB契約（migrations + policy）**

* migration は “正” の履歴であり、破壊的変更（削除/型変更/必須化など）を方針で縛る
* 破壊が必要なら RFC + 移行戦略（Expand→Migrate→Contract）

4. **マスタ（master）の扱い**

* master は「参照整合や業務ルールの前提」になりやすいので、Layer B に寄せて扱うと事故りにくい

  * **スキーマ/制約**：migration（テーブル・制約）
  * **データの前提**：seed/fixture（必要なら）
  * **不変条件**：domain/rule-sets への依存として frontmatter の depends_on に載せる
* master の変更が複数機能に影響するなら、cross-cutting と見なして **RFC扱い**に寄せる

#### 典型的なディレクトリ像（例）

* contracts/

  * openapi/*.yaml
  * events/*.schema.json
* db/

  * migrations/*
  * seeds/master/*（必要な場合のみ）
* tests/

  * acceptance/*（AT：Playwright/Cucumber/pytestなど）
  * api-contract/*（OpenAPI準拠/スキーマ検証など）

### Layer C（実装）

* コード

## ワークフロー設計（CLI前提・統合版）

### フロー図（Mermaid）

#### 1) 全体フロー（ヒアリング→REQ→AT/契約→実装→CI→顧客レビュー）

```mermaid
flowchart TB
  %% ====== Layer A (Mutable) ======
  subgraph A[Layer A：揺れてよい（探索・反復）]
    H[顧客ヒアリング / 現場観察]
    M[モック作成]
    C[モックへコメント]
    REQ[要求ID付与（REQ-*）]
    EDGE[Edge Case Backlog（文章）]
    H --> M --> C --> REQ
    C --> EDGE
    EDGE --> REQ
    REQ --> M
  end

  %% ====== Layer B (Source of truth) ======
  subgraph B[Layer B：守る＝正（実行可能な契約）]
    AT[受入テスト（AT-* / GWT）]
    OAS[OpenAPI / Event Schema]
    MIG[DB Migrations + 互換性ルール]
    FM[Docs Frontmatter（id/type/owns/depends_on/acceptance/requirements）]
    IDX[spec-index.json / spec-index.md 生成]
    BUNDLE[bundle（BUNDLE-F-*）生成]
  end

  %% ====== Layer C (Implementation) ======
  subgraph C_LAYER[Layer C：実装]
    CODE[実装コード]
  end

  %% ====== Gates ======
  subgraph G[CIゲート（飛ばしたら落ちる）]
    V1[validate：参照整合（ID/AT実在/index差分）]
    V2[REQ→ATカバレッジ]
    V3[Breaking検出（OpenAPI差分 / Migration policy）]
  end

  %% ====== Flow ======
  REQ -->|A→B変換| AT
  REQ --> FM
  AT --> BUNDLE
  OAS --> BUNDLE
  MIG --> BUNDLE
  FM --> IDX --> BUNDLE

  BUNDLE --> CODE --> V1 --> V2 --> V3 --> PR[PR]
  PR -->|merge| MAIN[main]

  MAIN --> REVIEW[顧客レビュー（経営視点：期待/NGの最終確認）]
  REVIEW -->|差分| H
```

#### 2) 並列開発（Feature並列 + 契約変更はRFCに隔離）

```mermaid
flowchart LR
  subgraph DEV[並列開発（Featureは並列OK）]
    F1[feature/F-1001]
    F2[feature/F-1002]
    F3[feature/F-1003]
  end

  subgraph RFC[契約変更はRFCに集約（衝突源の隔離）]
    R1[rfc/RFC-2001
contracts/db/domain変更]
    STRAT[移行戦略：Expand → Migrate → Contract]
  end

  MAIN[(main)]
  CI[CIゲート
validate / coverage / breaking]

  %% Feature flow
  F1 --> CI
  F2 --> CI
  F3 --> CI
  CI -->|pass| MAIN

  %% RFC flow
  R1 --> STRAT --> CI
  CI -->|pass| MAIN

  %% Rule
  NOTE1[契約を触る必要に気づいたら
featureで無理に触らずRFCを切る]
  NOTE1 -.-> R1

  %% Follow-up
  MAIN --> FOLLOW[各featureが新契約へ追随]
  FOLLOW -.-> F1
  FOLLOW -.-> F2
  FOLLOW -.-> F3
```

#### 3) CIゲート詳細（何をチェックして落とすか）

```mermaid
flowchart TB
  PUSH[push / PR作成] --> CI[CI開始]

  CI --> VREF[validate：参照整合]
  VREF -->|fail| STOP1[FAIL：参照切れ / AT不存在 / index生成漏れ]
  VREF -->|pass| VCOV[REQ→ATカバレッジ]

  VCOV -->|fail| STOP2[FAIL：REQがATに未紐付け
=「言ったことが仕様化されてない」]
  VCOV -->|pass| VBRK[Breaking検出]

  VBRK -->|fail| STOP3[FAIL：OpenAPI breaking / Migration policy違反
→ RFCへ誘導 or 移行策必須]
  VBRK -->|pass| OK[PASS：merge可能]
```

### 補足：モックと本番／厳密な順番／テスト作成タイミング

#### 1) モックと本番の違い（この議論での定義）

* **モック**：要件探索のための“体験の仮説”。目的は *学習*（コメント回収→REQ更新）。

  * 実装形態は何でもよい：Figma/Storybook/スタブAPI/簡易実装/ステージング上のFeature Flag など
  * 重要なのは「フィードバックが Layer A（REQ/コメント/Edge）に戻る」こと

* **本番**：契約（Layer B）を守り、互換性を壊さずに提供するもの。

  * OpenAPI / DB / 共通ルールの破壊的変更は **RFC + 移行策（Expand→Migrate→Contract）** が前提

#### 2) 「ある程度実装して触って帰る」場合もモックを作る？

* **作る（= その触れるものを “モック扱い” にする）** のが安全。
* ただし「別物のモックを必ず作る」のではなく、次の形が現実的：

  * **ステージング + Feature Flag** で“触れるモック”を提供（本番には出さない）
  * フィードバックは **コメント→REQ更新（Layer A）** へ回収
  * その差分を **AT/OpenAPI/Migration（Layer B）** に反映してから merge

#### 3) 並列でも崩れない“厳密な順番”（ゲート）

* **G0：Issue整備**（Scope/Owned/Non-goals/DoD、REQ候補）
* **G1：Layer A更新**（REQ-*確定、モック/コメント/Edge反映）
* **G2：Layer B作成**（AT-*作成、必要ならOpenAPI/Migration案、frontmatter整備→index/bundle生成）
* **G3：契約変更の有無判定**

  * 変更あり → **RFC Issue + rfcブランチ** に分離（featureで契約を触らない）
  * 変更なし → 次へ
* **G4：実装（Layer C）**
* **G5：CIゲート通過**（validate → REQ→ATカバレッジ → breaking）
* **G6：merge / 顧客レビュー / 学習をLayer Aへ戻す**

> 並列化できるのは G0〜G2 と G4（契約を触らない範囲）。
> **契約（contracts/db/domain）の変更だけは RFC で主導権を集約**して、実質“直列化”する。

#### 4) テストはどこで作られる？

* **受入テスト（AT-*）**：原則 **G2（A→B変換）で作る**（実装前に作って“赤”でもOK）。
* 実装中に見つかった差分は Layer A に戻して REQ を更新し、AT を更新する（反復）。
* **ユニット/統合テスト**：G4で実装と並行して増えるが、merge条件は「AT/CIを満たす」。

#### 5) 簡易実装モック（Next.js単体）運用：どう位置づける？

あなたが言う「簡易実装（Next.jsで見た目だけ触れる）」は、このワークフロー上では **“モックの一形態”** として扱うのが最適。

**目的（モックとしてのNext.js）**

* UI/画面遷移/入力体験を早く見せて、コメントを回収して **REQを育てる**
* まだ契約（OpenAPI/DB）を確定させない（＝**偽の約束を作らない**）

**推奨実装パターン（バックエンド無しでも崩れない）**

* データはローカル（fixture JSON）で持つ
* APIが必要に見える箇所は **MSW等でスタブ**（後で実APIに差し替え）
* 画面は Feature Flag で隔離して main に置けるようにする（共有・デモが楽）

**テスト（AT）の作り方：モック段階で何を保証する？**

* モック段階の AT は「画面体験のGiven-When-Then」を **Playwright 等のE2Eでスモーク保証**するのが現実的

  * 例:"Given ログイン済み When 申請フォームに入力して送信 Then 確認画面に遷移しサマリが表示される"
* まだビジネス計算やDB整合が無いなら、ATは **遷移/表示/入力制約**に寄せる
* 後で本実装（API/DB）が入ったら、同じATを本番経路に流して回帰テストにする

**厳密な順番（モックが絡む場合の最短ルート）**

* 先に「触れるもの」を出したいときは、次の“二段ロケット”が安全：

  1. **モックPR（UIだけ）**：REQを仮で立てる → 触ってコメント回収 → REQ更新
  2. **本PR（A→B確定→実装）**：REQ確定 → AT作成 → 必要ならRFC → 実装 → CI

> コツ：モックPRを main に入れるなら **Feature Flag + 最低限のAT（スモーク）** をセットにする。
> 逆に、AT無し・参照無しのモックを main に入れると、後で「何のためのUIか」が消えて負債化しやすい。

### 0. ゴール

* 要件は最初から出し切れない前提で、反復（モック→コメント→更新）しながら育てる
* ただし DB/API/共通ルールの変更で破綻しない（他機能を壊さない）
* 開発者の手を最小化し、AIが並列で進めても崩れない

**核心**：仕様書を“管理”するのではなく、要件を「機械が守る契約」へ変換し続けるパイプラインを作る

---

### 1. 原則（ブレない前提）

1. **要件は揺れてよい、契約は保守的**

* 画面・フロー・文章要件は反復で変わってOK
* ただし contracts / db / domain は雑に変えない

2. **“正の仕様”は文章ではなく実行可能なもの**

* 正（Source of truth）：受入テスト / OpenAPI・event schema / DB migrations
* Markdown：補助（意図・背景・説明）

3. **壊したらマージできない（強制）**

* 手順書ではなく CI/検証で順序を担保する（飛ばしたら落ちる）

---

### 2. 仕様を3層に分ける（情報設計）

* Layer A（揺れてよい）→ Layer B（守る＝正）→ Layer C（実装）

---

### 3. Layer A → B が最重要（価値がここで決まる）

* 経営者が言ったこと（A）がテスト（B）に落ちていないと「言ったのに反映されてない」で終了
* **REQ → AT（Acceptance Test）** のトレーサビリティを作り、未達はCIでfail

**REQ運用（例）**

* REQ-2026-0012 のように要望へID付与
* 受け入れテストへ紐付け（タグ/メタデータ/記述形式は自由だが、機械的に検出できること）

---

### 4. ドキュメント分割の参照漏れ対策（frontmatter＋index＋bundle）

ドキュメントが増えるほど参照漏れが起きるため、タグだけではなく構造化メタデータを必須化する。

#### 4.1 全ドキュメント共通の frontmatter（YAML）

必須要素：

* id / type
* owns（この仕様が責任を持つ契約：API/テーブル/イベント等）
* depends_on（参照している前提：ruleset/glossary等）
* acceptance（AT-*）
* （必要なら requirements（REQ-*））

#### 4.2 index 生成

* 全frontmatterを集計し **spec-index.json**（ID→ファイル→参照関係）を生成
* 人間向けに **spec-index.md** も生成

#### 4.3 bundle（コンテキスト束ね）

* bundle（例：BUNDLE-F-XXXX）で関連ドキュメント・契約・テストを1つに束ねる
* 実装計画・タスク分解・AI入力を bundle に統一し、参照漏れを減らす

---

### 5. エッジケース運用（機能紐づきが基本＋共通のみ昇格）

#### 5.1 基本

* エッジケースは原則 feature に紐づく
* 複数機能に刺さるものは cross-cutting / rule-sets へ昇格

#### 5.2 段階的成熟モデル

* Level 0：基本ケースだけ
* Level 1：Edge Case Backlog（文章で蓄積）
* Level 2：爆発する領域だけディシジョンテーブル化

  * テーブル1行＝受け入れテスト1本が理想

---

### 6. CIゲート（“守るべき順序”を強制する）

#### 6.1 参照整合（validate）

* frontmatter参照切れ（ID不存在）
* acceptance（AT-*）の実在チェック
* index生成の差分チェック（生成し忘れ防止）

#### 6.2 REQ→ATカバレッジ

* REQが受け入れテストに紐づいていない場合はfail
* 「言ったことが仕様化されていない」をマージ前に検知

#### 6.3 破壊的変更の検出

* OpenAPI breaking change 検出（削除/型変更/必須化など）
* migration policy（削除・型変更など禁止 or RFC必須）

---

### 7. 並列開発（Issue / ブランチ / worktree）

#### 7.1 並列化の単位

* Feature（F-*）は多数並列OK
* 契約（contracts/db/domain）は衝突源なのでルールで分離

#### 7.2 Issueは“実行指示書”

Issue必須：

* Scope（対象ID）
* Owned（触っていい契約・ファイル範囲）
* Acceptance（AT-*）
* Requirements（REQ-*）
* Non-goals（触らない領域）
* DoD（CIが通る／validateが通る）

#### 7.3 ブランチ＆worktree

* 1 Issue = 1 branch
* 1 Issue = 1 worktree
* 1 worktree = 1 PR（混ぜない）

### 7.4 Taskの粒度（bundle/AT/REQとの対応）

**結論：Taskは bundle の内側に置き、AT（受入テスト）を最小単位の“完了条件”にする。**

* **bundle = 機能レベルのコンテキスト束**（Feature単位で固定）
* **Task = bundle内の実行単位**（小さく切って並列化できる）
* **完了条件 = 対応するATが通ること**

#### Taskを「文章だけ」にしないためのルール

* Taskには必ず **参照ID（REQ-* / AT-* / owns）** を持たせる
* “終わった”は **対応ATがパス**した時点で判定する
* Task一覧は、**AT一覧をベースに生成**し、追加実装が必要な場合のみ補助Taskを足す

#### Task一覧 → Test一覧 になる？への答え

* **ほぼ Yes**。最終的に「仕様が満たされた」ことはATのパスで証明されるため、
  * Task = 「ATが通る状態にするための作業」
  * Task一覧 = 「AT一覧 + そのATが通るまでの補助作業」
* これにより、**“やったこと”がテストで証明できる**構造になる。

---

### 8. RFC運用（契約変更の集約）

**ルール：contracts / db / domain に触るなら全部RFC**

#### 8.1 RFCを切る条件（強制）

* /contracts/** を変更
* /db/migrations/** を追加/変更
* /specs/domain/**（glossary/invariants）を変更
* 共通ルール（cross-cutting / rule-sets）を変更
  → 必ず RFC Issue + rfcブランチ

#### 8.2 途中でRFCに気づいたときの定石

* feature側で無理に契約を触らない
* RFCを切って契約変更を集約（編集権をRFC側へ）
* RFCで 契約→テスト→移行策 を先に固め main へ
* featureが順次追随

#### 8.3 Breaking変更の移行戦略（推奨）

* Expand → Migrate → Contract

  * Expand：新要素追加（旧は残す）
  * Migrate：利用を移す
  * Contract：最後に旧を削除

---

### 9. “手順書だけでは順序化されない”への答え

* skills / agent.md：方針・判断基準・テンプレを示す「憲法」
* 順序保証：**実行可能なゲート（validate/CI）** で行う
* つまり「飛ばしたら落ちる」までコード化して初めてワークフローが成立する

---

### 10. 最小で作るべき骨格（推奨順）

1. frontmatterスキーマ決定
2. index生成
3. bundle生成
4. validate（参照整合）
5. REQ→ATカバレッジ検証
6. OpenAPI breaking / migration policy 検証
7. RFC/Issue/ブランチ/worktree規約の明文化（運用固定）

## ツール配置方針（叩き台）

* **skills / agent.md**：憲法（判断基準・テンプレ・NG集・レビュー観点）
* **CLI（scripts）**：index/bundle/validate/coverage/breaking-check を実行可能にする
* **GitHub**：Issue=実行指示書、PR=証跡（REQ/AT/owns/depends_on を必須に）
* **CI**：validate/coverage/breaking を必須ゲート化（通らないとマージ不可）

---

## 合意できる“最適案”（暫定）

この節は、現在の議論を「実運用で迷わない設計」に落とすための暫定結論です。曖昧さを残さず、運用と検証が噛み合う点を優先しています。

### 1. 正の仕様の固定場所（機械検出フォーマット）

**結論：frontmatter を正とする。テストは参照に徹する。**

* frontmatter が唯一の Source of truth。
* テスト側は `AT-*` を名寄せするだけにし、参照整合は validate で保証。

**理由**

* index/bundle生成が単純化し、参照漏れの検出が一貫する。
* テストメタと文書メタが二重管理になる事故を防げる。

**標準 frontmatter 仕様（案）**

```
---
id: F-1234

type: feature

owns:
  - api: /contracts/openapi/foo.yaml#/paths/~1foo
  - table: db.public.foo

depends_on:
  - ruleset: R-1001
  - glossary: G-2004

acceptance:
  - AT-1234-001
  - AT-1234-002

requirements:
  - REQ-2026-0012
  - REQ-2026-0013
---
```

### 2. bundle 単位の原則

**結論：bundle は Feature 単位固定とする。複合 bundle は禁止。**

* 例：`BUNDLE-F-1234`。
* cross-cutting の共通ルールは、個別 feature bundle に **参照として入れる**。

**理由**

* 作業単位（Issue/branch/worktree/PR）と bundle を一致させると、運用が崩れない。
* AIの入力単位としても最小で安定する（大きくしすぎると文脈が散る）。

### 3. OpenAPI / DB の breaking 判定の正の定義

**結論：契約ファイル同士の差分比較を正とし、実装生成物は参考扱い。**

* OpenAPI：`contracts/openapi/*.yaml` の差分を正とし、breaking は CI で落とす。
* DB：`db/migrations` のポリシールールを CI で強制。

**理由**

* 「正の仕様」を“生成物”に寄せると差分が揺れる。
* 仕様主導の前提では、契約ファイルが唯一の正であるべき。

### 4. RFC の DoD（最低限合意するべき条件）

**結論：契約変更があるなら、最低限次の4点が揃ってから main に入れる。**

1. **契約差分の明示**（OpenAPI / migration / domainの差分）
2. **AT 追加または改訂**（REQとのトレーサビリティを維持）
3. **移行戦略（Expand → Migrate → Contract）**
4. **validate / coverage / breaking の全ゲート通過**

**理由**

* RFC は「契約の正を更新する場」なので、契約・テスト・移行策が揃わないと merge すべきではない。

### 5. 実運用に落とすときの最小構成

**結論：最初に固定すべき3点**

1. frontmatter schema（機械検出の正）
2. validate（参照整合 + index 差分）
3. REQ→AT coverage gate

**理由**

* この3つだけでも「言ったことが仕様化されない」事故を止められる。
* OpenAPI / DB の breaking は段階的に導入可能。

---

## DSL設計（詳細議論のたたき台）

### 目的（DSLが担う責務）

* **ATの中身を機械可読で表現**し、CIでの検証・生成・可視化に使う
* “正”は frontmatter で固定し、**DSLは「具体的な挙動記述」**に集中させる
* 文章だけのGWTではなく、**データを含めたテスト仕様の再利用**を狙う

### DSLの適用範囲（どこまでをDSLで書くか）

* **対象**：Acceptance Test（AT-*）、ディシジョンテーブル化したEdge Case
* **対象外**：OpenAPI/DBの契約定義（別フォーマットが正）
* **補助**：画面遷移のスモーク（モック段階）にも流用可

### 形式（提案）

* **ファイル構成**：`specs/features/F-XXXX.md` に frontmatter + DSL本文
* **frontmatter**：ID/owns/depends_on/acceptance/requirements を唯一の正とする
* **DSL本文**：AT単位のテスト定義を列挙（GWT + データ）

#### 例（草案）

```
AT-1234-001:
  title: 申請フォームの送信
  given:
    - role: approver
    - page: /apply
  when:
    - fill:
        field: reason
        value: "出張"
    - click: submit
  then:
    - page: /apply/confirm
    - visible: "確認"
  requirements:
    - REQ-2026-0012

AT-1234-002:
  title: 必須項目の未入力
  given:
    - role: approver
    - page: /apply
  when:
    - click: submit
  then:
    - error: "reason is required"
  requirements:
    - REQ-2026-0013
```

### DSLに求める制約（機械検出の前提）

* **ID一意性**：AT IDの重複は禁止（index生成で検出）
* **参照整合**：requirements/depends_on の参照は validate で強制
* **行為語彙の固定**：`fill`, `click`, `visible`, `error` などの語彙を限定して解析容易にする
* **テスト冪等性**：同じATがモック/本番で共通に流せることを理想とする

### DSLとAT/REQの関係（前提の整理）

* frontmatter が “正” であるため、**DSL内のrequirementsは参照補助**（重複でもOK）
* カバレッジ判定は **frontmatterの acceptance/requirements** を基準にする
* DSLは **ATの手順詳細** として使い、CIでは「存在・形式・語彙」の検証を行う

### 次に詰めるべき論点

* DSLの最小語彙（UI/E2E向け or API向けの分離）
* データ表現（JSON/YAML混在の許容範囲、値の型）
* 失敗メッセージの定義（error/invalid/forbidden 等）
* ATのタグ付け（smoke/regression/mock-only など）

---

## 未決事項・論点（次の議論）

* [ ] 本ドキュメントの「最適案」を正式合意として固定するか（frontmatter正・Feature固定bundle・契約差分を正とするbreaking判定・RFCのDoD）
* [ ] frontmatter schema を機械検出用に厳密化する際のバリデーション仕様（必須/任意・型・参照解決）
* [ ] validate / coverage / breaking の最小CLIとCI実装順序

---

※このドキュメントを起点に順次ブラッシュアップする
