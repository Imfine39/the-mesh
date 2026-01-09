#!/usr/bin/env python3
"""
Spec Analyzer: 計算可能な仕様書から依存関係を抽出し、bundleを生成する
"""

import yaml
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional
from collections import defaultdict


@dataclass
class DependencyGraph:
    """依存関係グラフ"""
    # function -> 依存するderived/state
    function_deps: Dict[str, Set[str]] = field(default_factory=lambda: defaultdict(set))
    # derived -> 依存するstate
    derived_deps: Dict[str, Set[str]] = field(default_factory=lambda: defaultdict(set))
    # invariant -> 依存するderived
    invariant_deps: Dict[str, Set[str]] = field(default_factory=lambda: defaultdict(set))
    # 逆引き: derived/state -> それに依存するfunction
    reverse_deps: Dict[str, Set[str]] = field(default_factory=lambda: defaultdict(set))


def load_spec(path: str) -> dict:
    """仕様YAMLを読み込む"""
    with open(path, 'r') as f:
        return yaml.safe_load(f)


def extract_dependencies(spec: dict) -> DependencyGraph:
    """仕様から依存関係を抽出"""
    graph = DependencyGraph()

    # derived の依存関係を抽出
    for derived_name, derived_def in spec.get('derived', {}).items():
        deps = derived_def.get('depends_on', [])
        for dep in deps:
            if 'state' in dep:
                graph.derived_deps[derived_name].add(f"state:{dep['state']}")

    # function の依存関係を抽出
    for func_name, func_def in spec.get('functions', {}).items():
        # pre conditions
        for pre in func_def.get('pre', []):
            for dep in pre.get('depends_on', []):
                if 'state' in dep:
                    graph.function_deps[func_name].add(f"state:{dep['state']}")
                    graph.reverse_deps[f"state:{dep['state']}"].add(func_name)
                if 'derived' in dep:
                    graph.function_deps[func_name].add(f"derived:{dep['derived']}")
                    graph.reverse_deps[f"derived:{dep['derived']}"].add(func_name)

        # post conditions
        for post in func_def.get('post', []):
            for dep in post.get('depends_on', []):
                if 'state' in dep:
                    graph.function_deps[func_name].add(f"state:{dep['state']}")
                    graph.reverse_deps[f"state:{dep['state']}"].add(func_name)
                if 'derived' in dep:
                    graph.function_deps[func_name].add(f"derived:{dep['derived']}")
                    graph.reverse_deps[f"derived:{dep['derived']}"].add(func_name)

        # error conditions
        for err in func_def.get('error', []):
            for dep in err.get('depends_on', []):
                if 'derived' in dep:
                    graph.function_deps[func_name].add(f"derived:{dep['derived']}")
                    graph.reverse_deps[f"derived:{dep['derived']}"].add(func_name)

    # invariants の依存関係を抽出
    for inv in spec.get('invariants', []):
        inv_id = inv.get('id', 'unknown')
        for dep in inv.get('depends_on', []):
            if 'derived' in dep:
                graph.invariant_deps[inv_id].add(f"derived:{dep['derived']}")

    return graph


def generate_bundle_for_function(spec: dict, graph: DependencyGraph, func_name: str) -> dict:
    """
    特定の関数を実装するために必要なbundleを生成

    bundleには以下を含む:
    - 対象関数の定義
    - 依存するderived（式）の定義
    - 依存するstateの定義
    - 関連するinvariantsの定義
    - 影響を受ける他の関数（参考情報）
    """
    bundle = {
        "meta": {
            "bundle_id": f"BUNDLE-{func_name}",
            "target_function": func_name,
            "generated_from": spec.get('meta', {}).get('id', 'unknown')
        },
        "target": {},
        "dependencies": {
            "derived": {},
            "state": {},
            "invariants": []
        },
        "impact": {
            "functions_sharing_deps": []
        }
    }

    # 対象関数の定義
    bundle["target"] = spec.get('functions', {}).get(func_name, {})

    # 依存関係を収集
    deps = graph.function_deps.get(func_name, set())

    derived_needed = set()
    state_needed = set()

    for dep in deps:
        if dep.startswith("derived:"):
            derived_name = dep.split(":")[1]
            derived_needed.add(derived_name)
        elif dep.startswith("state:"):
            state_path = dep.split(":")[1]
            state_needed.add(state_path)

    # derived の定義を追加（+ derived が依存する state も追加）
    for derived_name in derived_needed:
        derived_def = spec.get('derived', {}).get(derived_name, {})
        bundle["dependencies"]["derived"][derived_name] = {
            "formula": derived_def.get('formula', ''),
            "params": derived_def.get('params', [])
        }
        # derived が依存する state も追加
        for dep in graph.derived_deps.get(derived_name, set()):
            if dep.startswith("state:"):
                state_needed.add(dep.split(":")[1])

    # state の定義を追加
    for state_path in state_needed:
        parts = state_path.split(".")
        entity = parts[0]
        entity_def = spec.get('state', {}).get(entity, {})
        if entity not in bundle["dependencies"]["state"]:
            bundle["dependencies"]["state"][entity] = entity_def

    # 関連する invariants を追加
    for inv in spec.get('invariants', []):
        inv_id = inv.get('id', 'unknown')
        inv_deps = graph.invariant_deps.get(inv_id, set())
        # この関数が依存する derived に関連する invariant を追加
        for dep in inv_deps:
            if dep.startswith("derived:"):
                derived_name = dep.split(":")[1]
                if derived_name in derived_needed:
                    bundle["dependencies"]["invariants"].append({
                        "id": inv_id,
                        "expr": inv.get('expr', ''),
                        "description": inv.get('description', '')
                    })
                    break

    # 同じ依存を持つ他の関数（影響範囲）
    for dep in deps:
        for other_func in graph.reverse_deps.get(dep, set()):
            if other_func != func_name:
                if other_func not in bundle["impact"]["functions_sharing_deps"]:
                    bundle["impact"]["functions_sharing_deps"].append(other_func)

    return bundle


def analyze_change_impact(spec: dict, graph: DependencyGraph, changed_derived: str) -> dict:
    """
    derived の定義が変更された場合の影響範囲を分析
    """
    impact = {
        "changed": f"derived:{changed_derived}",
        "affected_functions": [],
        "affected_invariants": []
    }

    # この derived に依存する関数を収集
    for func_name, deps in graph.function_deps.items():
        if f"derived:{changed_derived}" in deps:
            impact["affected_functions"].append(func_name)

    # この derived に依存する invariant を収集
    for inv_id, deps in graph.invariant_deps.items():
        if f"derived:{changed_derived}" in deps:
            impact["affected_invariants"].append(inv_id)

    return impact


def generate_index(spec: dict, graph: DependencyGraph) -> dict:
    """
    仕様全体のindex情報を生成
    """
    index = {
        "meta": spec.get('meta', {}),
        "entities": list(spec.get('state', {}).keys()),
        "functions": list(spec.get('functions', {}).keys()),
        "derived": list(spec.get('derived', {}).keys()),
        "invariants": [inv.get('id') for inv in spec.get('invariants', [])],
        "dependency_summary": {}
    }

    # 各関数の依存サマリ
    for func_name in spec.get('functions', {}).keys():
        deps = graph.function_deps.get(func_name, set())
        index["dependency_summary"][func_name] = {
            "depends_on": list(deps),
            "dep_count": len(deps)
        }

    return index


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Spec Analyzer')
    parser.add_argument('spec_path', help='Path to spec YAML file')
    parser.add_argument('--bundle', help='Generate bundle for specific function')
    parser.add_argument('--impact', help='Analyze impact of changing a derived')
    parser.add_argument('--index', action='store_true', help='Generate index')
    parser.add_argument('--graph', action='store_true', help='Show dependency graph')
    args = parser.parse_args()

    spec = load_spec(args.spec_path)
    graph = extract_dependencies(spec)

    if args.bundle:
        bundle = generate_bundle_for_function(spec, graph, args.bundle)
        print(json.dumps(bundle, indent=2, ensure_ascii=False))

    elif args.impact:
        impact = analyze_change_impact(spec, graph, args.impact)
        print(json.dumps(impact, indent=2, ensure_ascii=False))

    elif args.index:
        index = generate_index(spec, graph)
        print(json.dumps(index, indent=2, ensure_ascii=False))

    elif args.graph:
        print("=== Function Dependencies ===")
        for func, deps in graph.function_deps.items():
            print(f"{func}:")
            for dep in sorted(deps):
                print(f"  -> {dep}")

        print("\n=== Derived Dependencies ===")
        for derived, deps in graph.derived_deps.items():
            print(f"{derived}:")
            for dep in sorted(deps):
                print(f"  -> {dep}")

        print("\n=== Reverse Dependencies (who depends on what) ===")
        for target, funcs in graph.reverse_deps.items():
            print(f"{target}:")
            for func in sorted(funcs):
                print(f"  <- {func}")

    else:
        parser.print_help()


if __name__ == '__main__':
    main()
