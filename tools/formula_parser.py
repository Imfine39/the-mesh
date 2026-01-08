#!/usr/bin/env python3
"""
Formula Parser: 式から依存関係を自動抽出する（v2: derived同士の依存対応）
"""

import re
from typing import Set, Dict, List
from dataclasses import dataclass


@dataclass
class ParsedDependencies:
    """パースした依存関係"""
    state_refs: Set[str]      # entity.field 形式の参照
    derived_refs: Set[str]    # derived関数の呼び出し
    input_refs: Set[str]      # input.xxx 形式の参照


class FormulaParser:
    """式をパースして依存関係を抽出"""

    def __init__(self, known_entities: List[str], known_derived: List[str]):
        self.known_entities = set(known_entities)
        self.known_derived = set(known_derived)

    def parse(self, formula: str) -> ParsedDependencies:
        """式をパースして依存関係を抽出"""
        state_refs = set()
        derived_refs = set()
        input_refs = set()

        # 1. entity.field パターンを抽出
        entity_field_pattern = r'(\w+)\.(\w+)'
        for match in re.finditer(entity_field_pattern, formula):
            entity, field = match.groups()
            if entity in self.known_entities:
                state_refs.add(f"{entity}.{field}")
            elif entity == 'input':
                input_refs.add(f"input.{field}")

        # 2. derived関数呼び出しを抽出
        derived_pattern = r'(\w+)\s*\('
        for match in re.finditer(derived_pattern, formula):
            func_name = match.group(1)
            if func_name in self.known_derived:
                derived_refs.add(func_name)

        return ParsedDependencies(
            state_refs=state_refs,
            derived_refs=derived_refs,
            input_refs=input_refs
        )


def auto_extract_dependencies(spec: dict) -> dict:
    """仕様から依存関係を自動抽出（depends_on 不要）"""

    known_entities = list(spec.get('state', {}).keys())
    known_derived = list(spec.get('derived', {}).keys())
    parser = FormulaParser(known_entities, known_derived)

    result = {
        'derived_deps': {},
        'function_deps': {},
        'invariant_deps': {},
        'constraint_deps': {}
    }

    # derived の依存関係（derived同士の依存も含む）
    for name, definition in spec.get('derived', {}).items():
        formula = definition.get('formula', '') if isinstance(definition, dict) else ''
        if formula:
            parsed = parser.parse(formula)
            result['derived_deps'][name] = {
                'state_refs': sorted(parsed.state_refs),
                'derived_refs': sorted(parsed.derived_refs)  # derived同士の依存
            }

    # functions の依存関係
    for func_name, func_def in spec.get('functions', {}).items():
        all_state_refs = set()
        all_derived_refs = set()

        # pre
        for pre in func_def.get('pre', []):
            expr = pre if isinstance(pre, str) else pre.get('expr', '')
            if expr:
                parsed = parser.parse(expr)
                all_state_refs.update(parsed.state_refs)
                all_derived_refs.update(parsed.derived_refs)

        # post
        for post in func_def.get('post', []):
            if isinstance(post, dict):
                for key in ['when', 'where']:
                    if key in post:
                        parsed = parser.parse(post[key])
                        all_state_refs.update(parsed.state_refs)
                        all_derived_refs.update(parsed.derived_refs)

        # error
        for err in func_def.get('error', []):
            if isinstance(err, dict) and 'when' in err:
                parsed = parser.parse(err['when'])
                all_state_refs.update(parsed.state_refs)
                all_derived_refs.update(parsed.derived_refs)

        result['function_deps'][func_name] = {
            'state_refs': sorted(all_state_refs),
            'derived_refs': sorted(all_derived_refs)
        }

    # invariants の依存関係
    for inv in spec.get('invariants', []):
        inv_id = inv.get('id', 'unknown')
        expr = inv.get('expr', '')
        if expr:
            parsed = parser.parse(expr)
            result['invariant_deps'][inv_id] = {
                'state_refs': sorted(parsed.state_refs),
                'derived_refs': sorted(parsed.derived_refs)
            }

    # constraints の依存関係
    for idx, constraint in enumerate(spec.get('constraints', [])):
        constraint_id = f"CONST-{idx:03d}"
        deps = set()

        if 'from' in constraint:
            deps.add(constraint['from'])
        if 'to' in constraint:
            deps.add(constraint['to'])
        if 'fields' in constraint:
            deps.update(constraint['fields'])

        result['constraint_deps'][constraint_id] = {
            'type': constraint.get('type', 'unknown'),
            'state_refs': sorted(deps),
            'on_delete': constraint.get('on_delete')
        }

    return result


def resolve_transitive_deps(deps: dict) -> dict:
    """
    推移的依存関係を解決（derived → derived → state も追跡）
    """
    derived_deps = deps['derived_deps']
    function_deps = deps['function_deps']

    # まずderivedの推移的依存を解決
    def resolve_derived(name, visited=None):
        if visited is None:
            visited = set()
        if name in visited:
            return set(), set()
        visited.add(name)

        dep = derived_deps.get(name, {})
        all_state = set(dep.get('state_refs', []))
        all_derived = set(dep.get('derived_refs', []))

        # 依存するderivedの依存も追加
        for child_derived in list(all_derived):
            child_state, child_derived_deps = resolve_derived(child_derived, visited)
            all_state.update(child_state)
            all_derived.update(child_derived_deps)

        return all_state, all_derived

    resolved_derived = {}
    for name in derived_deps:
        all_state, all_derived = resolve_derived(name)
        resolved_derived[name] = {
            'direct_state_refs': sorted(derived_deps[name].get('state_refs', [])),
            'direct_derived_refs': sorted(derived_deps[name].get('derived_refs', [])),
            'all_state_refs': sorted(all_state),
            'all_derived_refs': sorted(all_derived)
        }

    # 次にfunctionの推移的依存を解決
    resolved_function = {}
    for func_name, func_dep in function_deps.items():
        all_state = set(func_dep.get('state_refs', []))
        all_derived = set(func_dep.get('derived_refs', []))

        for derived_name in func_dep.get('derived_refs', []):
            if derived_name in resolved_derived:
                all_state.update(resolved_derived[derived_name]['all_state_refs'])
                all_derived.update(resolved_derived[derived_name]['all_derived_refs'])

        resolved_function[func_name] = {
            'direct_state_refs': sorted(func_dep.get('state_refs', [])),
            'direct_derived_refs': sorted(func_dep.get('derived_refs', [])),
            'all_state_refs': sorted(all_state),
            'all_derived_refs': sorted(all_derived)
        }

    return {
        'derived': resolved_derived,
        'functions': resolved_function
    }


def main():
    import yaml
    import json
    import argparse

    parser = argparse.ArgumentParser(description='Formula Parser')
    parser.add_argument('spec_path', help='Path to spec YAML file')
    parser.add_argument('--formula', help='Parse a single formula')
    parser.add_argument('--resolve', action='store_true', help='Resolve transitive dependencies')
    args = parser.parse_args()

    with open(args.spec_path, 'r') as f:
        spec = yaml.safe_load(f)

    if args.formula:
        known_entities = list(spec.get('state', {}).keys())
        known_derived = list(spec.get('derived', {}).keys())
        fp = FormulaParser(known_entities, known_derived)
        result = fp.parse(args.formula)
        print(f"State refs: {sorted(result.state_refs)}")
        print(f"Derived refs: {sorted(result.derived_refs)}")
        print(f"Input refs: {sorted(result.input_refs)}")
    else:
        deps = auto_extract_dependencies(spec)

        if args.resolve:
            resolved = resolve_transitive_deps(deps)
            output = {
                'raw_deps': deps,
                'resolved': resolved
            }
            print(json.dumps(output, indent=2, ensure_ascii=False))
        else:
            print(json.dumps(deps, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
