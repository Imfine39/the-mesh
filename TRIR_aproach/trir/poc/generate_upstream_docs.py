"""
Generate upstream-style documents from TRIR specification
Outputs documents comparable to the original 上流工程 folder structure
"""

import json
import os
from pathlib import Path
from generators.human_readable_gen import HumanReadableGenerator


def generate_upstream_docs(spec_path: str, output_dir: str):
    """Generate multiple documents mimicking upstream folder structure"""

    with open(spec_path) as f:
        spec = json.load(f)

    gen = HumanReadableGenerator(spec)
    output = gen.generate_all()

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # =========================================================================
    # 01_企画・立上げ相当
    # =========================================================================

    with open(output_path / "01_システム概要.md", "w") as f:
        meta = spec.get("meta", {})
        f.write(f"# {meta.get('title', 'システム概要')}\n\n")
        f.write("*このドキュメントはTRIR仕様から自動生成されました*\n\n")
        f.write("## 概要\n\n")
        if meta.get("description"):
            f.write(f"{meta['description']}\n\n")
        f.write(f"- **バージョン**: {meta.get('version', '-')}\n")
        f.write(f"- **エンティティ数**: {len(spec.get('state', {}))}\n")
        f.write(f"- **機能数**: {len(spec.get('functions', {}))}\n")
        f.write(f"- **テストシナリオ数**: {len(spec.get('scenarios', {}))}\n")

    print(f"  Generated: 01_システム概要.md")

    # =========================================================================
    # 02_要件定義相当
    # =========================================================================

    with open(output_path / "02_ビジネス要件定義書.md", "w") as f:
        f.write(output.requirements_text)
        f.write("\n\n---\n\n")
        f.write("## KPI・受入条件\n\n")

        reqs = spec.get("requirements", {})
        for req_id, req in reqs.items():
            if "acceptance" in req:
                f.write(f"### {req_id}\n\n")
                for ac_id, ac in req["acceptance"].items():
                    f.write(f"- **{ac_id}**: {ac.get('description', '-')}\n")
                f.write("\n")

    print(f"  Generated: 02_ビジネス要件定義書.md")

    # =========================================================================
    # 03_基本設計相当
    # =========================================================================

    # データモデル
    with open(output_path / "03_データモデル_論理ER.md", "w") as f:
        f.write("# データモデル（論理ER図）\n\n")
        f.write("*このドキュメントはTRIR仕様から自動生成されました*\n\n")
        f.write("## ER図\n\n")
        f.write("```mermaid\n")
        f.write(output.er_diagram)
        f.write("\n```\n\n")
        f.write("---\n\n")
        f.write(output.entity_tables)
        f.write("\n\n---\n\n")
        f.write("# フィールド定義\n\n")
        for entity_name, table in output.field_tables.items():
            f.write(table)
            f.write("\n\n")

    print(f"  Generated: 03_データモデル_論理ER.md")

    # 状態遷移
    with open(output_path / "03_状態遷移定義.md", "w") as f:
        f.write("# 状態遷移定義\n\n")
        f.write("*このドキュメントはTRIR仕様から自動生成されました*\n\n")

        if output.state_diagrams:
            for key, diagram in output.state_diagrams.items():
                f.write(f"## {key}\n\n")
                f.write("```mermaid\n")
                f.write(diagram)
                f.write("\n```\n\n")
        else:
            f.write("状態遷移は定義されていません。\n")

    print(f"  Generated: 03_状態遷移定義.md")

    # =========================================================================
    # 04_詳細設計相当
    # =========================================================================

    # 消込ロジック設計
    with open(output_path / "04_消込ロジック設計.md", "w") as f:
        f.write("# 消込ロジック設計\n\n")
        f.write("*このドキュメントはTRIR仕様から自動生成されました*\n\n")
        f.write(output.function_explanations)
        f.write("\n\n---\n\n")
        f.write("# フローチャート\n\n")
        for func_name, flowchart in output.flowcharts.items():
            f.write(f"## {func_name}\n\n")
            f.write("```mermaid\n")
            f.write(flowchart)
            f.write("\n```\n\n")

    print(f"  Generated: 04_消込ロジック設計.md")

    # 計算フィールド
    with open(output_path / "04_計算フィールド定義.md", "w") as f:
        f.write("# 計算フィールド定義\n\n")
        f.write("*このドキュメントはTRIR仕様から自動生成されました*\n\n")
        f.write(output.derived_explanations)

    print(f"  Generated: 04_計算フィールド定義.md")

    # =========================================================================
    # 05_テスト相当
    # =========================================================================

    with open(output_path / "05_テストシナリオ.md", "w") as f:
        f.write("# テストシナリオ\n\n")
        f.write("*このドキュメントはTRIR仕様から自動生成されました*\n\n")
        f.write(output.scenario_table)
        f.write("\n\n---\n\n")
        f.write("## シナリオ詳細\n\n")

        scenarios = spec.get("scenarios", {})
        for scenario_id, scenario in scenarios.items():
            f.write(f"### {scenario_id}: {scenario.get('title', '-')}\n\n")

            # Given
            f.write("**初期状態**:\n\n")
            for entity, data in scenario.get("given", {}).items():
                if isinstance(data, list):
                    f.write(f"- {entity}: {len(data)}件\n")
                else:
                    f.write(f"- {entity}: 1件\n")

            # When
            when = scenario.get("when", {})
            f.write(f"\n**実行**: `{when.get('call', '-')}`\n\n")
            if "input" in when:
                f.write("入力:\n")
                for k, v in when["input"].items():
                    f.write(f"- {k}: `{v}`\n")

            # Then
            then = scenario.get("then", {})
            f.write(f"\n**期待結果**:\n\n")
            if then.get("success"):
                f.write("- 成功\n")
            if then.get("error"):
                f.write(f"- エラー: `{then['error']}`\n")

            f.write("\n")

    print(f"  Generated: 05_テストシナリオ.md")

    # =========================================================================
    # 06_不変条件
    # =========================================================================

    with open(output_path / "06_不変条件・整合性ルール.md", "w") as f:
        f.write("# 不変条件・整合性ルール\n\n")
        f.write("*このドキュメントはTRIR仕様から自動生成されました*\n\n")
        f.write(output.invariant_list)

    print(f"  Generated: 06_不変条件・整合性ルール.md")

    print(f"\n完了: {output_path}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python generate_upstream_docs.py <spec.trir.json> <output_dir>")
        sys.exit(1)

    generate_upstream_docs(sys.argv[1], sys.argv[2])
