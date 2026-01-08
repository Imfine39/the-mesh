#!/usr/bin/env python3
"""
Change Simulator v2: 推移的依存・DB制約対応版
"""

import yaml
import json
from typing import Dict, List, Set
from dataclasses import dataclass
from enum import Enum
from formula_parser import FormulaParser, auto_extract_dependencies, resolve_transitive_deps


class ChangeType(Enum):
    ADD = "add"
    REMOVE = "remove"
    MODIFY = "modify"


@dataclass
class Impact:
    affected_type: str
    affected_id: str
    reason: str
    severity: str
    chain: List[str] = None  # 影響の伝播経路


def build_full_graph(spec: dict) -> dict:
    """完全な依存関係グラフを構築"""

    raw_deps = auto_extract_dependencies(spec)
    resolved = resolve_transitive_deps(raw_deps)

    known_entities = list(spec.get('state', {}).keys())
    known_derived = list(spec.get('derived', {}).keys())
    parser = FormulaParser(known_entities, known_derived)

    graph = {
        "state_to_derived": {},
        "state_to_constraint": {},
        "derived_to_derived": {},
        "derived_to_function": {},
        "derived_to_invariant": {},
        "derived_to_scenario": {},
        "function_to_scenario": {},
        "scenario_to_req": {},
        "constraint_cascade": {},
        "resolved_derived": resolved.get('derived', {}),
        "resolved_function": resolved.get('functions', {})
    }

    # state → derived
    for derived_name, deps in raw_deps.get('derived_deps', {}).items():
        for state_ref in deps.get('state_refs', []):
            if state_ref not in graph["state_to_derived"]:
                graph["state_to_derived"][state_ref] = []
            graph["state_to_derived"][state_ref].append(derived_name)

    # derived → derived
    for derived_name, deps in raw_deps.get('derived_deps', {}).items():
        for parent_derived in deps.get('derived_refs', []):
            if parent_derived not in graph["derived_to_derived"]:
                graph["derived_to_derived"][parent_derived] = []
            graph["derived_to_derived"][parent_derived].append(derived_name)

    # derived → function
    for func_name, deps in raw_deps.get('function_deps', {}).items():
        for derived_ref in deps.get('derived_refs', []):
            if derived_ref not in graph["derived_to_function"]:
                graph["derived_to_function"][derived_ref] = []
            graph["derived_to_function"][derived_ref].append(func_name)

    # derived → invariant
    for inv_id, deps in raw_deps.get('invariant_deps', {}).items():
        for derived_ref in deps.get('derived_refs', []):
            if derived_ref not in graph["derived_to_invariant"]:
                graph["derived_to_invariant"][derived_ref] = []
            graph["derived_to_invariant"][derived_ref].append(inv_id)

    # constraint → cascade
    for const_id, const_def in raw_deps.get('constraint_deps', {}).items():
        if const_def.get('on_delete') == 'cascade':
            from_ref = None
            for ref in const_def.get('state_refs', []):
                if '.' in ref:
                    entity = ref.split('.')[0]
                    if from_ref is None:
                        from_ref = entity
                    else:
                        graph["constraint_cascade"][from_ref] = {
                            "constraint_id": const_id,
                            "cascades_to": entity
                        }

    # state → constraint
    for const_id, const_def in raw_deps.get('constraint_deps', {}).items():
        for ref in const_def.get('state_refs', []):
            if ref not in graph["state_to_constraint"]:
                graph["state_to_constraint"][ref] = []
            graph["state_to_constraint"][ref].append(const_id)

    # function → scenario, derived → scenario, scenario → req
    for scenario_id, scenario in spec.get('scenarios', {}).items():
        # function → scenario
        when = scenario.get('when', {})
        if 'call' in when:
            func_name = when['call']
            if func_name not in graph["function_to_scenario"]:
                graph["function_to_scenario"][func_name] = []
            graph["function_to_scenario"][func_name].append(scenario_id)

        # steps形式のシナリオも対応
        for step in scenario.get('steps', []):
            step_when = step.get('when', {})
            if 'call' in step_when:
                func_name = step_when['call']
                if func_name not in graph["function_to_scenario"]:
                    graph["function_to_scenario"][func_name] = []
                if scenario_id not in graph["function_to_scenario"][func_name]:
                    graph["function_to_scenario"][func_name].append(scenario_id)

        # derived → scenario (then.assert)
        then = scenario.get('then', {})
        for assertion in then.get('assert', []):
            parsed = parser.parse(assertion)
            for derived_ref in parsed.derived_refs:
                if derived_ref not in graph["derived_to_scenario"]:
                    graph["derived_to_scenario"][derived_ref] = []
                if scenario_id not in graph["derived_to_scenario"][derived_ref]:
                    graph["derived_to_scenario"][derived_ref].append(scenario_id)

        # steps形式のassertも対応
        for step in scenario.get('steps', []):
            step_then = step.get('then', {})
            for assertion in step_then.get('assert', []):
                parsed = parser.parse(assertion)
                for derived_ref in parsed.derived_refs:
                    if derived_ref not in graph["derived_to_scenario"]:
                        graph["derived_to_scenario"][derived_ref] = []
                    if scenario_id not in graph["derived_to_scenario"][derived_ref]:
                        graph["derived_to_scenario"][derived_ref].append(scenario_id)

        # scenario → req
        reqs = scenario.get('requirements', [])
        graph["scenario_to_req"][scenario_id] = reqs

    return graph


def simulate_state_change(spec: dict, graph: dict, state_ref: str, change_type: ChangeType) -> List[Impact]:
    """state変更の影響をシミュレーション（推移的依存対応）"""
    impacts = []
    seen = set()

    def add_impact(atype, aid, reason, severity, chain=None):
        key = f"{atype}:{aid}"
        if key not in seen:
            seen.add(key)
            impacts.append(Impact(atype, aid, reason, severity, chain or []))

    # 1. 直接依存するderived
    direct_derived = graph.get("state_to_derived", {}).get(state_ref, [])
    for derived in direct_derived:
        chain = [f"state:{state_ref}", f"derived:{derived}"]
        add_impact("derived", derived, f"式が {state_ref} を直接参照",
                   "breaking" if change_type == ChangeType.REMOVE else "warning", chain)

        # 2. derived → derived の連鎖
        child_derived = graph.get("derived_to_derived", {}).get(derived, [])
        for child in child_derived:
            chain2 = chain + [f"derived:{child}"]
            add_impact("derived", child, f"{derived} 経由で {state_ref} に依存",
                       "breaking" if change_type == ChangeType.REMOVE else "warning", chain2)

            # child_derived が依存する function/invariant/scenario も追加
            for func in graph.get("derived_to_function", {}).get(child, []):
                add_impact("function", func, f"{child} 経由で {state_ref} に依存", "warning", chain2 + [f"function:{func}"])
            for inv in graph.get("derived_to_invariant", {}).get(child, []):
                add_impact("invariant", inv, f"{child} 経由で {state_ref} に依存", "breaking", chain2 + [f"invariant:{inv}"])
            for scn in graph.get("derived_to_scenario", {}).get(child, []):
                add_impact("scenario", scn, f"{child} 経由で {state_ref} に依存", "warning", chain2 + [f"scenario:{scn}"])

        # 3. derived → function
        for func in graph.get("derived_to_function", {}).get(derived, []):
            add_impact("function", func, f"{derived} 経由で {state_ref} に依存", "warning", chain + [f"function:{func}"])

        # 4. derived → invariant
        for inv in graph.get("derived_to_invariant", {}).get(derived, []):
            add_impact("invariant", inv, f"{derived} 経由で {state_ref} に依存", "breaking", chain + [f"invariant:{inv}"])

        # 5. derived → scenario
        for scn in graph.get("derived_to_scenario", {}).get(derived, []):
            add_impact("scenario", scn, f"{derived} 経由で {state_ref} に依存", "warning", chain + [f"scenario:{scn}"])

    # 6. constraint への影響
    for const in graph.get("state_to_constraint", {}).get(state_ref, []):
        add_impact("constraint", const, f"制約が {state_ref} を参照", "breaking" if change_type == ChangeType.REMOVE else "warning")

    return impacts


def simulate_derived_change(spec: dict, graph: dict, derived_name: str, change_type: ChangeType) -> List[Impact]:
    """derived変更の影響をシミュレーション（推移的に全て追跡）"""
    impacts = []
    seen = set()

    def add_impact(atype, aid, reason, severity, chain=None):
        key = f"{atype}:{aid}"
        if key not in seen:
            seen.add(key)
            impacts.append(Impact(atype, aid, reason, severity, chain or []))

    def trace_derived(name, current_chain, visited=None):
        """derivedの影響を再帰的に追跡"""
        if visited is None:
            visited = set()
        if name in visited:
            return
        visited.add(name)

        # 1. このderivedに依存する他のderived
        for child in graph.get("derived_to_derived", {}).get(name, []):
            child_chain = current_chain + [f"derived:{child}"]
            add_impact("derived", child, f"{name} に依存",
                       "breaking" if change_type == ChangeType.REMOVE else "warning",
                       child_chain)
            # 再帰的に追跡
            trace_derived(child, child_chain, visited.copy())

        # 2. function
        for func in graph.get("derived_to_function", {}).get(name, []):
            add_impact("function", func, f"{name}() を参照", "warning",
                       current_chain + [f"function:{func}"])

        # 3. invariant
        for inv in graph.get("derived_to_invariant", {}).get(name, []):
            add_impact("invariant", inv, f"{name}() を参照", "breaking",
                       current_chain + [f"invariant:{inv}"])

        # 4. scenario
        for scn in graph.get("derived_to_scenario", {}).get(name, []):
            add_impact("scenario", scn, f"assert で {name}() を検証", "warning",
                       current_chain + [f"scenario:{scn}"])

    # 起点から追跡開始
    trace_derived(derived_name, [f"derived:{derived_name}"])

    return impacts


def simulate_change(spec: dict, element_type: str, element_id: str, change_type: str) -> dict:
    """変更シミュレーションを実行"""
    graph = build_full_graph(spec)
    ct = ChangeType(change_type)

    if element_type == "state":
        impacts = simulate_state_change(spec, graph, element_id, ct)
    elif element_type == "derived":
        impacts = simulate_derived_change(spec, graph, element_id, ct)
    else:
        impacts = []

    result = {
        "change": {
            "type": element_type,
            "id": element_id,
            "action": change_type
        },
        "impact_chain": [],
        "summary": {
            "total": len(impacts),
            "breaking": 0,
            "warning": 0
        }
    }

    for impact in impacts:
        entry = {
            "type": impact.affected_type,
            "id": impact.affected_id,
            "reason": impact.reason,
            "severity": impact.severity,
            "chain": impact.chain
        }
        result["impact_chain"].append(entry)
        result["summary"][impact.severity] += 1

    return result


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Change Simulator v2')
    parser.add_argument('spec_path', help='Path to spec YAML file')
    parser.add_argument('--simulate', help='Simulate change: type:id:action')
    parser.add_argument('--graph', action='store_true', help='Show dependency graph')
    args = parser.parse_args()

    with open(args.spec_path, 'r') as f:
        spec = yaml.safe_load(f)

    if args.graph:
        graph = build_full_graph(spec)
        # グラフの要約を出力
        print(json.dumps({
            "state_to_derived": graph["state_to_derived"],
            "derived_to_derived": graph["derived_to_derived"],
            "derived_to_function": graph["derived_to_function"],
            "derived_to_scenario": graph["derived_to_scenario"],
        }, indent=2))

    elif args.simulate:
        parts = args.simulate.split(':')
        if len(parts) != 3:
            print("Format: type:id:action")
            return
        element_type, element_id, action = parts
        result = simulate_change(spec, element_type, element_id, action)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    else:
        parser.print_help()


if __name__ == '__main__':
    main()
