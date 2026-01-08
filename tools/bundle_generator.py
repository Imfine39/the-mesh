#!/usr/bin/env python3
"""
Bundle Generator: 式から自動抽出した依存関係を元にbundleを生成
"""

import yaml
import json
from pathlib import Path
from formula_parser import FormulaParser, auto_extract_dependencies, resolve_transitive_deps


def generate_bundle(spec: dict, target_function: str) -> dict:
    """
    特定の関数を実装するために必要なbundleを自動生成
    depends_on 不要 - 式から全て抽出
    """
    # 依存関係を自動抽出
    raw_deps = auto_extract_dependencies(spec)
    resolved = resolve_transitive_deps(raw_deps)

    func_deps = resolved.get(target_function, {})
    func_def = spec.get('functions', {}).get(target_function, {})

    if not func_def:
        raise ValueError(f"Function '{target_function}' not found in spec")

    bundle = {
        "meta": {
            "bundle_id": f"BUNDLE-{target_function}",
            "spec_id": spec.get('meta', {}).get('id', 'unknown'),
            "target": target_function
        },
        "context": {
            "function": {
                "name": target_function,
                "definition": func_def
            },
            "derived": {},
            "state": {},
            "invariants": []
        },
        "dependencies": {
            "direct": {
                "state": func_deps.get('direct_state_refs', []),
                "derived": func_deps.get('direct_derived_refs', [])
            },
            "transitive": {
                "state": func_deps.get('all_state_refs', []),
                "derived": func_deps.get('all_derived_refs', [])
            }
        }
    }

    # derived の定義を追加
    for derived_name in func_deps.get('all_derived_refs', []):
        derived_def = spec.get('derived', {}).get(derived_name, {})
        bundle["context"]["derived"][derived_name] = derived_def

    # 必要な state の定義を追加
    needed_entities = set()
    for state_ref in func_deps.get('all_state_refs', []):
        entity = state_ref.split('.')[0]
        needed_entities.add(entity)

    for entity in needed_entities:
        entity_def = spec.get('state', {}).get(entity, {})
        bundle["context"]["state"][entity] = entity_def

    # 関連する invariants を追加
    for inv in spec.get('invariants', []):
        inv_id = inv.get('id', 'unknown')
        inv_deps = raw_deps['invariant_deps'].get(inv_id, {})
        # この関数が依存する derived に関連する invariant を追加
        for derived_name in inv_deps.get('derived_refs', []):
            if derived_name in func_deps.get('all_derived_refs', []):
                bundle["context"]["invariants"].append(inv)
                break

    return bundle


def generate_impact_analysis(spec: dict, changed_element: str, element_type: str = 'derived') -> dict:
    """
    要素が変更された場合の影響分析
    """
    raw_deps = auto_extract_dependencies(spec)
    resolved = resolve_transitive_deps(raw_deps)

    impact = {
        "changed": f"{element_type}:{changed_element}",
        "affected": {
            "functions": [],
            "invariants": []
        }
    }

    if element_type == 'derived':
        # この derived に依存する関数
        for func_name, deps in resolved.items():
            if changed_element in deps.get('all_derived_refs', []):
                impact["affected"]["functions"].append({
                    "name": func_name,
                    "dependency_type": "direct" if changed_element in deps.get('direct_derived_refs', []) else "transitive"
                })

        # この derived に依存する invariant
        for inv_id, inv_deps in raw_deps['invariant_deps'].items():
            if changed_element in inv_deps.get('derived_refs', []):
                impact["affected"]["invariants"].append(inv_id)

    elif element_type == 'state':
        # この state に依存する関数
        for func_name, deps in resolved.items():
            if changed_element in deps.get('all_state_refs', []):
                impact["affected"]["functions"].append({
                    "name": func_name,
                    "dependency_type": "direct" if changed_element in deps.get('direct_state_refs', []) else "transitive"
                })

        # この state に依存する derived
        impact["affected"]["derived"] = []
        for derived_name, derived_deps in raw_deps['derived_deps'].items():
            if changed_element in derived_deps.get('state_refs', []):
                impact["affected"]["derived"].append(derived_name)

    return impact


def generate_index(spec: dict) -> dict:
    """仕様全体のindex情報を生成"""
    raw_deps = auto_extract_dependencies(spec)
    resolved = resolve_transitive_deps(raw_deps)

    index = {
        "meta": spec.get('meta', {}),
        "summary": {
            "entities": list(spec.get('state', {}).keys()),
            "functions": list(spec.get('functions', {}).keys()),
            "derived": list(spec.get('derived', {}).keys()),
            "invariants": [inv.get('id') for inv in spec.get('invariants', [])]
        },
        "dependency_graph": {
            "derived": raw_deps['derived_deps'],
            "functions": {
                name: {
                    "direct_deps": {
                        "state": deps['direct_state_refs'],
                        "derived": deps['direct_derived_refs']
                    },
                    "all_deps": {
                        "state": deps['all_state_refs'],
                        "derived": deps['all_derived_refs']
                    }
                }
                for name, deps in resolved.items()
            },
            "invariants": raw_deps['invariant_deps']
        }
    }

    return index


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Bundle Generator')
    parser.add_argument('spec_path', help='Path to spec YAML file')
    parser.add_argument('--bundle', help='Generate bundle for specific function')
    parser.add_argument('--impact', help='Analyze impact of changing an element (format: type:name, e.g., derived:remaining)')
    parser.add_argument('--index', action='store_true', help='Generate index')
    args = parser.parse_args()

    with open(args.spec_path, 'r') as f:
        spec = yaml.safe_load(f)

    if args.bundle:
        bundle = generate_bundle(spec, args.bundle)
        print(json.dumps(bundle, indent=2, ensure_ascii=False))

    elif args.impact:
        parts = args.impact.split(':')
        if len(parts) != 2:
            print("Impact format: type:name (e.g., derived:remaining, state:invoice.amount)")
            return
        element_type, element_name = parts
        impact = generate_impact_analysis(spec, element_name, element_type)
        print(json.dumps(impact, indent=2, ensure_ascii=False))

    elif args.index:
        index = generate_index(spec)
        print(json.dumps(index, indent=2, ensure_ascii=False))

    else:
        parser.print_help()


if __name__ == '__main__':
    main()
