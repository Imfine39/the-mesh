#!/usr/bin/env python3
"""
Scenario Analyzer: シナリオ（Given-When-Then）から依存関係とトレーサビリティを抽出
"""

import yaml
import json
from typing import Dict, List, Set
from formula_parser import FormulaParser


def analyze_scenarios(spec: dict) -> dict:
    """シナリオを分析して依存関係を抽出"""

    known_entities = list(spec.get('state', {}).keys())
    known_derived = list(spec.get('derived', {}).keys())
    known_functions = list(spec.get('functions', {}).keys())
    parser = FormulaParser(known_entities, known_derived)

    result = {
        "scenarios": {},
        "traceability": {
            "req_to_at": {},
            "at_to_req": {},
            "function_to_at": {},
            "derived_to_at": {}
        }
    }

    # Requirements → AT マッピング
    for req_id, req_def in spec.get('requirements', {}).items():
        acceptance = req_def.get('acceptance', [])
        result["traceability"]["req_to_at"][req_id] = acceptance
        for at_id in acceptance:
            if at_id not in result["traceability"]["at_to_req"]:
                result["traceability"]["at_to_req"][at_id] = []
            result["traceability"]["at_to_req"][at_id].append(req_id)

    # 各シナリオを分析
    for scenario_id, scenario in spec.get('scenarios', {}).items():
        analysis = {
            "title": scenario.get('title', ''),
            "requirements": scenario.get('requirements', []),
            "dependencies": {
                "functions": [],
                "derived": set(),
                "state": set()
            },
            "given_state": {},
            "when": {},
            "assertions": []
        }

        # Given: 使用するstate
        given = scenario.get('given', {})
        if 'state' in given:
            for entity, data in given['state'].items():
                analysis["dependencies"]["state"].add(entity)
                analysis["given_state"][entity] = data

        # When: 呼び出すfunction
        when = scenario.get('when', {})
        if 'call' in when:
            func_name = when['call']
            analysis["dependencies"]["functions"].append(func_name)
            analysis["when"] = {
                "function": func_name,
                "input": when.get('input', {})
            }

            # Function → AT マッピング
            if func_name not in result["traceability"]["function_to_at"]:
                result["traceability"]["function_to_at"][func_name] = []
            result["traceability"]["function_to_at"][func_name].append(scenario_id)

        # Then: 検証する式
        then = scenario.get('then', {})
        for assertion in then.get('assert', []):
            parsed = parser.parse(assertion)
            analysis["assertions"].append({
                "expr": assertion,
                "derived_refs": list(parsed.derived_refs),
                "state_refs": list(parsed.state_refs)
            })
            analysis["dependencies"]["derived"].update(parsed.derived_refs)
            analysis["dependencies"]["state"].update(
                ref.split('.')[0] for ref in parsed.state_refs
            )

            # Derived → AT マッピング
            for derived in parsed.derived_refs:
                if derived not in result["traceability"]["derived_to_at"]:
                    result["traceability"]["derived_to_at"][derived] = []
                if scenario_id not in result["traceability"]["derived_to_at"][derived]:
                    result["traceability"]["derived_to_at"][derived].append(scenario_id)

        # Set に変換
        analysis["dependencies"]["derived"] = list(analysis["dependencies"]["derived"])
        analysis["dependencies"]["state"] = list(analysis["dependencies"]["state"])

        result["scenarios"][scenario_id] = analysis

    return result


def generate_full_bundle(spec: dict, target_function: str) -> dict:
    """
    関数を実装するための完全なbundle（シナリオ含む）を生成
    """
    from bundle_generator import generate_bundle

    # 基本bundle
    bundle = generate_bundle(spec, target_function)

    # シナリオ分析を追加
    scenario_analysis = analyze_scenarios(spec)

    # この関数に関連するシナリオを追加
    related_scenarios = scenario_analysis["traceability"]["function_to_at"].get(target_function, [])

    bundle["scenarios"] = {}
    bundle["requirements"] = {}

    for scenario_id in related_scenarios:
        # シナリオ定義
        bundle["scenarios"][scenario_id] = spec.get('scenarios', {}).get(scenario_id, {})

        # 関連するRequirements
        scenario_reqs = spec.get('scenarios', {}).get(scenario_id, {}).get('requirements', [])
        for req_id in scenario_reqs:
            if req_id not in bundle["requirements"]:
                bundle["requirements"][req_id] = spec.get('requirements', {}).get(req_id, {})

    return bundle


def check_coverage(spec: dict) -> dict:
    """REQ → AT カバレッジをチェック"""

    result = {
        "covered": [],
        "uncovered": [],
        "coverage_rate": 0.0
    }

    requirements = spec.get('requirements', {})
    scenarios = spec.get('scenarios', {})

    for req_id, req_def in requirements.items():
        acceptance = req_def.get('acceptance', [])
        # ATが存在するかチェック
        existing_ats = [at for at in acceptance if at in scenarios]

        if existing_ats:
            result["covered"].append({
                "req_id": req_id,
                "what": req_def.get('what', ''),
                "ats": existing_ats
            })
        else:
            result["uncovered"].append({
                "req_id": req_id,
                "what": req_def.get('what', ''),
                "missing_ats": acceptance
            })

    total = len(requirements)
    covered = len(result["covered"])
    result["coverage_rate"] = (covered / total * 100) if total > 0 else 0.0

    return result


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Scenario Analyzer')
    parser.add_argument('spec_path', help='Path to spec YAML file')
    parser.add_argument('--analyze', action='store_true', help='Analyze all scenarios')
    parser.add_argument('--bundle', help='Generate full bundle for function')
    parser.add_argument('--coverage', action='store_true', help='Check REQ→AT coverage')
    parser.add_argument('--trace', help='Trace from REQ/AT/function (e.g., REQ-001, AT-001, allocate_payment)')
    args = parser.parse_args()

    with open(args.spec_path, 'r') as f:
        spec = yaml.safe_load(f)

    if args.analyze:
        result = analyze_scenarios(spec)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif args.bundle:
        bundle = generate_full_bundle(spec, args.bundle)
        print(json.dumps(bundle, indent=2, ensure_ascii=False))

    elif args.coverage:
        result = check_coverage(spec)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif args.trace:
        analysis = analyze_scenarios(spec)
        trace_id = args.trace

        print(f"=== Trace: {trace_id} ===\n")

        # REQ からトレース
        if trace_id.startswith("REQ"):
            ats = analysis["traceability"]["req_to_at"].get(trace_id, [])
            req_def = spec.get('requirements', {}).get(trace_id, {})
            print(f"Who: {req_def.get('who', 'N/A')}")
            print(f"Why: {req_def.get('why', 'N/A')}")
            print(f"What: {req_def.get('what', 'N/A')}")
            print(f"Acceptance Tests: {ats}")
            for at_id in ats:
                scenario = spec.get('scenarios', {}).get(at_id, {})
                print(f"\n  {at_id}: {scenario.get('title', '')}")
                print(f"    Calls: {scenario.get('when', {}).get('call', 'N/A')}")

        # AT からトレース
        elif trace_id.startswith("AT"):
            reqs = analysis["traceability"]["at_to_req"].get(trace_id, [])
            scenario = analysis["scenarios"].get(trace_id, {})
            print(f"Title: {scenario.get('title', 'N/A')}")
            print(f"Requirements: {reqs}")
            print(f"Calls function: {scenario.get('when', {}).get('function', 'N/A')}")
            print(f"Dependencies:")
            print(f"  - Functions: {scenario.get('dependencies', {}).get('functions', [])}")
            print(f"  - Derived: {scenario.get('dependencies', {}).get('derived', [])}")
            print(f"  - State: {scenario.get('dependencies', {}).get('state', [])}")

        # Function からトレース
        else:
            ats = analysis["traceability"]["function_to_at"].get(trace_id, [])
            print(f"Function: {trace_id}")
            print(f"Tested by: {ats}")
            for at_id in ats:
                reqs = analysis["traceability"]["at_to_req"].get(at_id, [])
                print(f"\n  {at_id}:")
                print(f"    Requirements: {reqs}")
                for req_id in reqs:
                    req_def = spec.get('requirements', {}).get(req_id, {})
                    print(f"      {req_id}: {req_def.get('what', '')}")

    else:
        parser.print_help()


if __name__ == '__main__':
    main()
