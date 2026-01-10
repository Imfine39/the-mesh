---
name: the-mosaic
description: "Requirements definition framework with mock-based UI specification. Actions: mock, review, finalize, export. Use for: UI requirements, wireframe creation, screen flow design, mock-to-spec conversion. Triggers: create mock, UI requirements, wireframe, screen design, requirements definition."
---

# The Mosaic - Mock-Based Requirements Definition

モックベースの要件定義フレームワーク。画面モックを通じたやり取りで要件を固め、the-mesh specへ変換する。

## Status: Planning

このスキルは現在設計段階です。

## Concept

```
要件定義フェーズ
    ↓
ユーザー ←→ モック ←→ Claude
    ↓
モック確定（data属性付きHTML）
    ↓
the-mesh spec 自動生成
    ↓
実装・テスト（the-mesh）
```

## Documents

- [IDEAS.md](./docs/IDEAS.md) - 設計アイデア・検討事項
- [MOCK_FORMAT.md](./docs/MOCK_FORMAT.md) - モックHTML形式仕様

## Integration with the-mesh

the-mosaicで確定したモックは、the-meshのviews/routes/componentsセクションに変換される。

```
the-mosaic (要件定義)
    ↓ export
the-mesh (実装・テスト)
```
