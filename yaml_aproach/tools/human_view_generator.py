#!/usr/bin/env python3
"""
Human View Generator: 機械式を人間が読みやすい形式に変換

SSOT = YAML（機械式）
出力 = Markdown（人間用ビュー）
"""

import yaml
import re
from typing import Dict, List, Optional
from dataclasses import dataclass


# 用語集: 機械的な名前 → 人間が読める名前
GLOSSARY = {
    # エンティティ
    "invoice": "請求",
    "payment": "入金",
    "allocation": "消込",
    "customer": "顧客",

    # フィールド
    "amount": "金額",
    "status": "ステータス",
    "remaining": "残額",
    "net_amount": "税引後金額",
    "discount_rate": "割引率",
    "tax_amount": "税額",

    # ステータス
    "open": "未完了",
    "closed": "完了",

    # エラー
    "OVER_ALLOCATION": "過剰消込エラー",
    "CUSTOMER_MISMATCH": "顧客不一致エラー",
}


def translate_term(term: str) -> str:
    """用語を翻訳"""
    return GLOSSARY.get(term, term)


def translate_expr(expr: str) -> str:
    """式を自然言語に変換"""
    result = expr

    # パターンマッチングで変換
    patterns = [
        # remaining(invoice) >= input.amount
        (r'remaining\(invoice\)\s*>=\s*input\.amount',
         '請求の残額 ≧ 消込金額'),

        # remaining(invoice) == 0
        (r'remaining\(invoice\)\s*==\s*0',
         '請求の残額 = 0（全額消込済み）'),

        # remaining(invoice) < input.amount
        (r'remaining\(invoice\)\s*<\s*input\.amount',
         '請求の残額 < 消込金額（残額超過）'),

        # invoice.status == 'open'
        (r"invoice\.status\s*==\s*'open'",
         '請求ステータス = 未完了'),

        # invoice.status == 'closed'
        (r"invoice\.status\s*==\s*'closed'",
         '請求ステータス = 完了'),

        # invoice.customer_id == payment.customer_id
        (r'invoice\.customer_id\s*==\s*payment\.customer_id',
         '請求と入金が同一顧客'),

        # invoice.customer_id != payment.customer_id
        (r'invoice\.customer_id\s*!=\s*payment\.customer_id',
         '請求と入金が異なる顧客'),

        # 汎用: xxx.yyy == zzz
        (r'(\w+)\.(\w+)\s*==\s*(\d+)',
         lambda m: f'{translate_term(m.group(1))}の{translate_term(m.group(2))} = {m.group(3)}'),

        # 汎用: xxx(yyy) == zzz
        (r'(\w+)\((\w+)\)\s*==\s*(\d+)',
         lambda m: f'{translate_term(m.group(2))}の{translate_term(m.group(1))} = {m.group(3)}'),
    ]

    for pattern, replacement in patterns:
        if callable(replacement):
            result = re.sub(pattern, replacement, result)
        else:
            result = re.sub(pattern, replacement, result)

    return result


def translate_formula(formula: str) -> str:
    """計算式を自然言語に変換"""
    # invoice.amount - sum(allocation.amount where allocation.invoice_id = invoice.id)
    if 'sum(allocation.amount' in formula and 'invoice.amount' in formula:
        return "請求金額 − その請求への消込合計額"

    if 'net_amount(invoice)' in formula:
        return "税引後請求額 − その請求への消込合計額"

    if 'invoice.amount * (1 - invoice.discount_rate)' in formula:
        return "請求金額 × (1 − 割引率) + 税額"

    return formula


def generate_requirement_view(req_id: str, req: dict) -> str:
    """要求を人間用ビューに変換"""
    lines = []
    lines.append(f"### {req_id}: {req.get('what', '')}")
    lines.append("")
    lines.append(f"**誰が**: {req.get('who', '未定義')}")
    lines.append(f"**なぜ**: {req.get('why', '未定義')}")
    lines.append("")

    conditions = req.get('conditions', [])
    if conditions:
        lines.append("**満たすべき条件:**")
        lines.append("")
        for cond in conditions:
            cond_id = cond.get('id', '')
            desc = cond.get('description', '')
            ats = cond.get('acceptance', [])
            lines.append(f"- [{cond_id}] {desc}")
            if ats:
                lines.append(f"  - 検証: {', '.join(ats)}")

            verifies = cond.get('verifies', [])
            for v in verifies:
                expr = v.get('expr', '')
                human_expr = translate_expr(expr)
                lines.append(f"  - 式: {human_expr}")
        lines.append("")

    return "\n".join(lines)


def generate_derived_view(name: str, derived: dict) -> str:
    """導出式を人間用ビューに変換"""
    lines = []
    human_name = translate_term(name)
    lines.append(f"### {human_name} (`{name}`)")
    lines.append("")

    desc = derived.get('description', '')
    if desc:
        lines.append(f"{desc}")
        lines.append("")

    formula = derived.get('formula', '')
    if formula:
        human_formula = translate_formula(formula)
        lines.append(f"**計算方法**: {human_formula}")
        lines.append("")
        lines.append(f"```")
        lines.append(f"{formula}")
        lines.append(f"```")
        lines.append("")

    derived_from = derived.get('derived_from', [])
    if derived_from:
        lines.append(f"**関連する要求**: {', '.join(derived_from)}")
        lines.append("")

    return "\n".join(lines)


def generate_function_view(name: str, func: dict) -> str:
    """関数を人間用ビューに変換"""
    lines = []
    lines.append(f"### {name}")
    lines.append("")

    desc = func.get('description', '')
    if desc:
        lines.append(f"{desc}")
        lines.append("")

    implements = func.get('implements', [])
    if implements:
        lines.append(f"**実現する要求**: {', '.join(implements)}")
        lines.append("")

    # 前提条件
    pre = func.get('pre', [])
    if pre:
        lines.append("**前提条件** (これを満たさないと実行できない):")
        lines.append("")
        for p in pre:
            if isinstance(p, dict):
                expr = p.get('expr', '')
                reason = p.get('reason', '')
                required_by = p.get('required_by', '')
                human_expr = translate_expr(expr)
                line = f"- {human_expr}"
                if reason:
                    line += f" — {reason}"
                if required_by:
                    line += f" [{required_by}]"
                lines.append(line)
            else:
                lines.append(f"- {translate_expr(p)}")
        lines.append("")

    # 実行結果
    post = func.get('post', [])
    if post:
        lines.append("**実行結果** (成功時に起きること):")
        lines.append("")
        for p in post:
            if isinstance(p, dict):
                action = p.get('action', '')
                reason = p.get('reason', '')
                condition = p.get('condition', '')
                required_by = p.get('required_by', '')

                if condition:
                    human_cond = translate_expr(condition)
                    line = f"- {human_cond} の場合: {action}"
                else:
                    line = f"- {action}"

                if reason:
                    line += f" — {reason}"
                if required_by:
                    line += f" [{required_by}]"
                lines.append(line)
        lines.append("")

    # エラー
    error = func.get('error', [])
    if error:
        lines.append("**エラー** (これらの場合は失敗する):")
        lines.append("")
        for e in error:
            if isinstance(e, dict):
                code = e.get('code', '')
                when = e.get('when', '')
                required_by = e.get('required_by', '')
                human_code = translate_term(code)
                human_when = translate_expr(when)
                line = f"- **{human_code}**: {human_when}"
                if required_by:
                    line += f" [{required_by}]"
                lines.append(line)
        lines.append("")

    return "\n".join(lines)


def generate_scenario_view(at_id: str, scenario: dict) -> str:
    """シナリオを人間用ビューに変換"""
    lines = []
    title = scenario.get('title', '')
    lines.append(f"### {at_id}: {title}")
    lines.append("")

    verifies = scenario.get('verifies', [])
    if verifies:
        lines.append(f"**検証する条件**: {', '.join(verifies)}")
        lines.append("")

    # Given
    given = scenario.get('given', {})
    if given:
        lines.append("**前提状態** (Given):")
        lines.append("")
        for entity, data in given.items():
            human_entity = translate_term(entity)
            if isinstance(data, dict):
                for key, value in data.items():
                    human_key = translate_term(key)
                    if isinstance(value, str) and value in GLOSSARY:
                        value = translate_term(value)
                    lines.append(f"- {human_entity}の{human_key}: {value}")
            elif isinstance(data, list):
                lines.append(f"- {human_entity}: {len(data)}件")
        lines.append("")

    # When
    when = scenario.get('when', {})
    if when:
        call = when.get('call', '')
        input_data = when.get('input', {})
        lines.append("**操作** (When):")
        lines.append("")
        lines.append(f"- `{call}` を実行")
        if input_data:
            for key, value in input_data.items():
                human_key = translate_term(key)
                lines.append(f"  - {human_key}: {value}")
        lines.append("")

    # Then
    then = scenario.get('then', {})
    if then:
        lines.append("**期待結果** (Then):")
        lines.append("")

        if 'success' in then:
            lines.append(f"- 成功: {then['success']}")

        if 'error' in then:
            human_error = translate_term(then['error'])
            lines.append(f"- エラー: {human_error}")

        for assertion in then.get('assert', []):
            human_assert = translate_expr(assertion)
            lines.append(f"- {human_assert}")
        lines.append("")

    return "\n".join(lines)


def generate_full_document(spec: dict) -> str:
    """仕様全体を人間用ドキュメントに変換"""
    lines = []

    meta = spec.get('meta', {})
    lines.append(f"# {meta.get('title', '仕様書')}")
    lines.append("")
    lines.append(f"バージョン: {meta.get('version', '未定義')}")
    lines.append("")

    # 要求
    requirements = spec.get('requirements', {})
    if requirements:
        lines.append("---")
        lines.append("## 要求一覧")
        lines.append("")
        for req_id, req in requirements.items():
            lines.append(generate_requirement_view(req_id, req))

    # 計算式
    derived = spec.get('derived', {})
    if derived:
        lines.append("---")
        lines.append("## 計算式")
        lines.append("")
        for name, d in derived.items():
            lines.append(generate_derived_view(name, d))

    # 機能
    functions = spec.get('functions', {})
    if functions:
        lines.append("---")
        lines.append("## 機能（API）")
        lines.append("")
        for name, f in functions.items():
            lines.append(generate_function_view(name, f))

    # シナリオ
    scenarios = spec.get('scenarios', {})
    if scenarios:
        lines.append("---")
        lines.append("## テストシナリオ")
        lines.append("")
        for at_id, s in scenarios.items():
            lines.append(generate_scenario_view(at_id, s))

    return "\n".join(lines)


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Human View Generator')
    parser.add_argument('spec_path', help='Path to spec YAML file')
    parser.add_argument('--output', '-o', help='Output file path (default: stdout)')
    args = parser.parse_args()

    with open(args.spec_path, 'r') as f:
        spec = yaml.safe_load(f)

    doc = generate_full_document(spec)

    if args.output:
        with open(args.output, 'w') as f:
            f.write(doc)
        print(f"Generated: {args.output}")
    else:
        print(doc)


if __name__ == '__main__':
    main()
