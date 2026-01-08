#!/usr/bin/env python3
"""
TypeScript Analyzer: TSコードから依存関係を自動抽出する実験

簡易版: 正規表現ベースでプロパティアクセスと関数呼び出しを抽出
本格版: TypeScript Compiler APIを使うべきだが、まず概念実証
"""

import re
import json
from pathlib import Path
from typing import Dict, List, Set
from dataclasses import dataclass, field


@dataclass
class FunctionAnalysis:
    name: str
    params: List[str] = field(default_factory=list)
    property_accesses: Set[str] = field(default_factory=set)  # obj.prop
    function_calls: Set[str] = field(default_factory=set)      # func()


def extract_functions(code: str) -> Dict[str, str]:
    """関数定義を抽出（簡易版）"""
    functions = {}

    # function name(...) { ... } パターン
    # 簡易的に括弧のネストを追跡
    pattern = r'function\s+(\w+)\s*\(([^)]*)\)\s*(?::\s*\w+[^{]*)?\{'

    for match in re.finditer(pattern, code):
        func_name = match.group(1)
        params_str = match.group(2)
        start = match.end() - 1  # { の位置

        # 括弧のネストを追跡して関数本体を抽出
        depth = 0
        end = start
        for i, char in enumerate(code[start:], start):
            if char == '{':
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break

        func_body = code[start:end]
        functions[func_name] = {
            'params': [p.strip().split(':')[0].strip() for p in params_str.split(',') if p.strip()],
            'body': func_body
        }

    return functions


def analyze_function_body(func_name: str, func_info: dict, known_functions: List[str]) -> FunctionAnalysis:
    """関数本体を解析して依存を抽出"""
    analysis = FunctionAnalysis(name=func_name, params=func_info['params'])
    body = func_info['body']

    # 1. プロパティアクセス (obj.prop) を抽出
    # ただし関数呼び出し (func()) は除外
    prop_pattern = r'(\w+)\.(\w+)(?!\s*\()'
    for match in re.finditer(prop_pattern, body):
        obj, prop = match.groups()
        # パラメータ経由のアクセスを記録
        if obj in func_info['params']:
            analysis.property_accesses.add(f"{obj}.{prop}")
        # ローカル変数経由のアクセスも記録（簡易版では区別しない）
        elif obj not in ['const', 'let', 'var', 'return', 'if', 'else']:
            analysis.property_accesses.add(f"{obj}.{prop}")

    # 2. 関数呼び出しを抽出（既知の関数のみ）
    call_pattern = r'(\w+)\s*\('
    for match in re.finditer(call_pattern, body):
        func_called = match.group(1)
        if func_called in known_functions and func_called != func_name:
            analysis.function_calls.add(func_called)

    return analysis


def analyze_typescript_file(filepath: str) -> dict:
    """TypeScriptファイルを解析"""
    code = Path(filepath).read_text()

    # 1. 型定義を抽出（state相当）
    types = {}
    type_pattern = r'type\s+(\w+)\s*=\s*\{([^}]+)\}'
    for match in re.finditer(type_pattern, code):
        type_name = match.group(1)
        type_body = match.group(2)
        fields = []
        for line in type_body.strip().split('\n'):
            line = line.strip().rstrip(';').rstrip(',')
            if ':' in line:
                field_name = line.split(':')[0].strip()
                if field_name and not field_name.startswith('//'):
                    fields.append(field_name)
        types[type_name] = fields

    # 2. 関数を抽出
    functions = extract_functions(code)
    known_functions = list(functions.keys())

    # 3. 各関数を解析
    analysis_results = {}
    for func_name, func_info in functions.items():
        analysis = analyze_function_body(func_name, func_info, known_functions)
        analysis_results[func_name] = {
            'params': analysis.params,
            'property_accesses': sorted(analysis.property_accesses),
            'function_calls': sorted(analysis.function_calls)
        }

    # 4. 依存グラフを構築
    dependency_graph = {
        'types': types,
        'functions': analysis_results,
        'derived_deps': {},
        'function_deps': {}
    }

    # derived（引数から計算する関数）を特定
    for func_name, info in analysis_results.items():
        # 型名を小文字にしてマッチング
        type_names_lower = {t.lower(): t for t in types.keys()}

        state_refs = []
        for access in info['property_accesses']:
            parts = access.split('.')
            if len(parts) == 2:
                param, field = parts
                # パラメータの型を推測
                for type_name in types.keys():
                    if param.lower() == type_name.lower() or param in info['params']:
                        if field in types.get(type_name, []):
                            state_refs.append(f"{type_name.lower()}.{field}")

        dependency_graph['derived_deps'][func_name] = {
            'state_refs': state_refs,
            'derived_refs': list(info['function_calls'])
        }

    return dependency_graph


def main():
    import argparse

    parser = argparse.ArgumentParser(description='TypeScript Dependency Analyzer')
    parser.add_argument('filepath', help='Path to TypeScript file')
    args = parser.parse_args()

    result = analyze_typescript_file(args.filepath)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
