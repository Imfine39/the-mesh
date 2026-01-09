#!/usr/bin/env python3
"""
要求整合性チェッカー: REQ → AT → 式 の整合性を検証
"""

import yaml
import json
from typing import Dict, List, Set
from dataclasses import dataclass


@dataclass
class IntegrityIssue:
    level: str  # error, warning
    category: str
    message: str
    details: dict = None


def check_req_to_condition_coverage(spec: dict) -> List[IntegrityIssue]:
    """REQの全conditionsがATでカバーされているか"""
    issues = []

    for req_id, req in spec.get('requirements', {}).items():
        conditions = req.get('conditions', [])

        if not conditions:
            issues.append(IntegrityIssue(
                level="warning",
                category="REQ→COND",
                message=f"{req_id} にconditionsが定義されていません",
                details={"req": req_id, "what": req.get('what', '')}
            ))
            continue

        for cond in conditions:
            cond_id = cond.get('id', 'unknown')
            acceptance = cond.get('acceptance', [])

            if not acceptance:
                issues.append(IntegrityIssue(
                    level="error",
                    category="COND→AT",
                    message=f"{cond_id} にacceptance testが紐づいていません",
                    details={"condition": cond_id, "description": cond.get('description', '')}
                ))

    return issues


def check_at_existence(spec: dict) -> List[IntegrityIssue]:
    """参照されているATが実際に存在するか"""
    issues = []
    scenarios = set(spec.get('scenarios', {}).keys())

    for req_id, req in spec.get('requirements', {}).items():
        for cond in req.get('conditions', []):
            for at_id in cond.get('acceptance', []):
                if at_id not in scenarios:
                    issues.append(IntegrityIssue(
                        level="error",
                        category="AT存在",
                        message=f"{at_id} が定義されていません",
                        details={"referenced_by": cond.get('id', ''), "req": req_id}
                    ))

    return issues


def check_at_verifies_condition(spec: dict) -> List[IntegrityIssue]:
    """ATのverifiesがconditionsと整合しているか"""
    issues = []

    # 全conditionのIDを収集
    all_conditions = {}
    for req_id, req in spec.get('requirements', {}).items():
        for cond in req.get('conditions', []):
            all_conditions[cond.get('id', '')] = {
                'req': req_id,
                'description': cond.get('description', ''),
                'acceptance': cond.get('acceptance', [])
            }

    # 各ATのverifiesをチェック
    for at_id, scenario in spec.get('scenarios', {}).items():
        verifies = scenario.get('verifies', [])

        if not verifies:
            issues.append(IntegrityIssue(
                level="warning",
                category="AT→COND",
                message=f"{at_id} がどのconditionも検証していません（verifies未定義）",
                details={"scenario": at_id}
            ))
            continue

        for cond_id in verifies:
            if cond_id not in all_conditions:
                issues.append(IntegrityIssue(
                    level="error",
                    category="AT→COND",
                    message=f"{at_id} が存在しないcondition {cond_id} を参照しています",
                    details={"scenario": at_id, "condition": cond_id}
                ))
            else:
                # 双方向チェック: conditionのacceptanceにこのATが含まれているか
                cond_info = all_conditions[cond_id]
                if at_id not in cond_info['acceptance']:
                    issues.append(IntegrityIssue(
                        level="warning",
                        category="双方向整合",
                        message=f"{at_id} は {cond_id} を検証するが、{cond_id} のacceptanceに {at_id} がない",
                        details={"scenario": at_id, "condition": cond_id}
                    ))

    return issues


def check_derived_traceability(spec: dict) -> List[IntegrityIssue]:
    """derivedがどのREQから導出されたか追跡可能か"""
    issues = []

    for derived_name, derived_def in spec.get('derived', {}).items():
        derived_from = derived_def.get('derived_from', [])

        if not derived_from:
            issues.append(IntegrityIssue(
                level="warning",
                category="derived→REQ",
                message=f"derived '{derived_name}' がどのREQから導出されたか不明です",
                details={"derived": derived_name}
            ))
        else:
            # 参照されているREQが存在するか
            requirements = spec.get('requirements', {})
            for req_id in derived_from:
                if req_id not in requirements:
                    issues.append(IntegrityIssue(
                        level="error",
                        category="derived→REQ",
                        message=f"derived '{derived_name}' が存在しないREQ '{req_id}' を参照",
                        details={"derived": derived_name, "req": req_id}
                    ))

    return issues


def check_function_implements(spec: dict) -> List[IntegrityIssue]:
    """functionのimplementsがREQと整合しているか"""
    issues = []
    requirements = set(spec.get('requirements', {}).keys())

    for func_name, func_def in spec.get('functions', {}).items():
        implements = func_def.get('implements', [])

        if not implements:
            issues.append(IntegrityIssue(
                level="warning",
                category="function→REQ",
                message=f"function '{func_name}' がどのREQを実現するか不明です",
                details={"function": func_name}
            ))
        else:
            for req_id in implements:
                if req_id not in requirements:
                    issues.append(IntegrityIssue(
                        level="error",
                        category="function→REQ",
                        message=f"function '{func_name}' が存在しないREQ '{req_id}' を参照",
                        details={"function": func_name, "req": req_id}
                    ))

    return issues


def check_condition_verifies_expr(spec: dict) -> List[IntegrityIssue]:
    """conditionsのverifies式が妥当か"""
    issues = []
    known_derived = set(spec.get('derived', {}).keys())

    for req_id, req in spec.get('requirements', {}).items():
        for cond in req.get('conditions', []):
            cond_id = cond.get('id', '')
            verifies = cond.get('verifies', [])

            for v in verifies:
                expr = v.get('expr', '')
                # 式中のderivedが存在するか簡易チェック
                for derived_name in known_derived:
                    if f"{derived_name}(" in expr:
                        break
                else:
                    # derivedを使っていない式は警告（必須ではない）
                    pass

    return issues


def generate_traceability_matrix(spec: dict) -> dict:
    """REQ → COND → AT → 式 のトレーサビリティマトリクス"""
    matrix = {
        "requirements": {},
        "coverage_summary": {
            "total_reqs": 0,
            "total_conditions": 0,
            "covered_conditions": 0,
            "coverage_rate": 0.0
        }
    }

    total_conditions = 0
    covered_conditions = 0

    for req_id, req in spec.get('requirements', {}).items():
        req_entry = {
            "what": req.get('what', ''),
            "conditions": []
        }

        for cond in req.get('conditions', []):
            cond_id = cond.get('id', '')
            acceptance = cond.get('acceptance', [])
            verifies = cond.get('verifies', [])

            total_conditions += 1
            if acceptance:
                covered_conditions += 1

            cond_entry = {
                "id": cond_id,
                "description": cond.get('description', ''),
                "acceptance_tests": acceptance,
                "verifies_exprs": [v.get('expr', '') for v in verifies],
                "covered": len(acceptance) > 0
            }
            req_entry["conditions"].append(cond_entry)

        matrix["requirements"][req_id] = req_entry

    matrix["coverage_summary"]["total_reqs"] = len(spec.get('requirements', {}))
    matrix["coverage_summary"]["total_conditions"] = total_conditions
    matrix["coverage_summary"]["covered_conditions"] = covered_conditions
    matrix["coverage_summary"]["coverage_rate"] = (
        covered_conditions / total_conditions * 100 if total_conditions > 0 else 0
    )

    return matrix


def check_all(spec: dict) -> dict:
    """全ての整合性チェックを実行"""
    all_issues = []

    all_issues.extend(check_req_to_condition_coverage(spec))
    all_issues.extend(check_at_existence(spec))
    all_issues.extend(check_at_verifies_condition(spec))
    all_issues.extend(check_derived_traceability(spec))
    all_issues.extend(check_function_implements(spec))

    errors = [i for i in all_issues if i.level == "error"]
    warnings = [i for i in all_issues if i.level == "warning"]

    return {
        "summary": {
            "total_issues": len(all_issues),
            "errors": len(errors),
            "warnings": len(warnings),
            "passed": len(errors) == 0
        },
        "errors": [{"category": i.category, "message": i.message, "details": i.details} for i in errors],
        "warnings": [{"category": i.category, "message": i.message, "details": i.details} for i in warnings]
    }


def main():
    import argparse

    parser = argparse.ArgumentParser(description='要求整合性チェッカー')
    parser.add_argument('spec_path', help='Path to spec YAML file')
    parser.add_argument('--check', action='store_true', help='Run all integrity checks')
    parser.add_argument('--matrix', action='store_true', help='Generate traceability matrix')
    args = parser.parse_args()

    with open(args.spec_path, 'r') as f:
        spec = yaml.safe_load(f)

    if args.check:
        result = check_all(spec)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif args.matrix:
        matrix = generate_traceability_matrix(spec)
        print(json.dumps(matrix, indent=2, ensure_ascii=False))

    else:
        parser.print_help()


if __name__ == '__main__':
    main()
