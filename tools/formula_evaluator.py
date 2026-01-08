#!/usr/bin/env python3
"""
Formula Evaluator: spec YAMLの式をPythonで安全に評価する
PoC版 - 最小実装
"""

import re
import ast
from typing import Any, Dict, List, Optional
from dataclasses import dataclass


@dataclass
class EvalContext:
    """評価コンテキスト: state + input + derived関数"""
    state: Dict[str, Any]       # { invoice: {...}, payment: {...}, allocation: [...] }
    input: Dict[str, Any]       # 関数への入力
    derived: Dict[str, str]     # derived関数名 → formula


class FormulaEvaluator:
    """
    specの式をPythonで評価

    サポートする構文:
    - entity.field → state['entity']['field'] または state['entity'][i]['field']
    - input.field → input['field']
    - remaining(entity) → derived関数呼び出し
    - sum(x.field where x.foreign_key = entity.id) → リスト内包表記
    - ==, >=, <=, >, <, implies, and, or
    """

    def __init__(self, spec: dict):
        self.spec = spec
        self.entities = set(spec.get('state', {}).keys())
        self.derived_formulas = {
            name: defn.get('formula', '')
            for name, defn in spec.get('derived', {}).items()
            if isinstance(defn, dict)
        }

    def _transform_formula(self, formula: str) -> str:
        """式をPython式に変換"""
        result = formula

        # 1. implies → Python論理式 (A implies B = not A or B)
        # "A implies B" → "(not (A) or (B))"
        implies_pattern = r'(.+?)\s+implies\s+(.+)'
        match = re.match(implies_pattern, result, re.IGNORECASE)
        if match:
            a, b = match.groups()
            a_transformed = self._transform_formula(a.strip())
            b_transformed = self._transform_formula(b.strip())
            return f"(not ({a_transformed}) or ({b_transformed}))"

        # 2. sum(x.field where x.foreign = y.id) → Pythonリスト内包
        sum_where_pattern = r'sum\s*\(\s*(\w+)\.(\w+)\s+where\s+(\w+)\.(\w+)\s*=\s*(\w+)\.(\w+)\s*\)'
        def sum_replacer(m):
            item_entity, item_field, filter_entity, filter_field, target_entity, target_field = m.groups()
            return f"sum(item['{item_field}'] for item in state['{item_entity}'] if item['{filter_field}'] == state['{target_entity}']['{target_field}'])"
        result = re.sub(sum_where_pattern, sum_replacer, result)

        # 3. derived関数呼び出し: remaining(invoice) → _eval_derived('remaining', state['invoice'])
        for derived_name in self.derived_formulas.keys():
            pattern = rf'{derived_name}\s*\(\s*(\w+)\s*\)'
            def derived_replacer(m, name=derived_name):
                entity = m.group(1)
                return f"_eval_derived('{name}', '{entity}')"
            result = re.sub(pattern, derived_replacer, result)

        # 4. error(CODE) → _check_error('CODE')
        error_pattern = r'error\s*\(\s*(\w+)\s*\)'
        result = re.sub(error_pattern, r"_check_error('\1')", result)

        # 5. entity.field → state['entity']['field']
        for entity in self.entities:
            pattern = rf'\b{entity}\.(\w+)\b'
            result = re.sub(pattern, rf"state['{entity}']['\1']", result)

        # 6. input.field → input['field']
        result = re.sub(r'\binput\.(\w+)\b', r"input['\1']", result)

        # 7. before_xxx → before['xxx']（シナリオ用）
        result = re.sub(r'\bbefore_(\w+)\b', r"before['\1']", result)

        return result

    def evaluate(self, formula: str, context: EvalContext, error_state: Optional[str] = None) -> Any:
        """式を評価"""
        transformed = self._transform_formula(formula)

        # 評価用の安全な環境を構築
        def _eval_derived(name: str, entity: str) -> Any:
            """derived関数を評価"""
            if name not in self.derived_formulas:
                raise ValueError(f"Unknown derived: {name}")
            derived_formula = self.derived_formulas[name]
            return self.evaluate(derived_formula, context)

        def _check_error(code: str) -> bool:
            """エラー状態をチェック"""
            return error_state == code

        # Python 3のジェネレータ式/リスト内包表記のスコープ問題を回避するため
        # stateをglobalsに配置
        safe_globals = {
            '__builtins__': {},  # 組み込み関数を制限
            'sum': sum,
            'len': len,
            'abs': abs,
            'min': min,
            'max': max,
            'True': True,
            'False': False,
            'state': context.state,  # globalsに配置してジェネレータ内で参照可能に
            'input': context.input,
            'before': {},
        }

        safe_locals = {
            '_eval_derived': _eval_derived,
            '_check_error': _check_error,
        }

        try:
            # ASTで安全性を検証
            tree = ast.parse(transformed, mode='eval')
            # 危険なノードがないか確認
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom, ast.Call)):
                    if isinstance(node, ast.Call):
                        if isinstance(node.func, ast.Name):
                            if node.func.id not in ('sum', 'len', 'abs', 'min', 'max',
                                                     '_eval_derived', '_check_error'):
                                raise ValueError(f"Unsafe function call: {node.func.id}")

            return eval(transformed, safe_globals, safe_locals)
        except Exception as e:
            return {
                'error': str(e),
                'original': formula,
                'transformed': transformed
            }


import copy


class OperationSimulator:
    """
    specのfunctions定義に基づいて操作をシミュレートする

    1. pre条件を評価 → 失敗したらエラー
    2. error条件を評価 → 該当したらエラーを返す
    3. post条件を実行 → 状態を変更
    """

    def __init__(self, spec: dict):
        self.spec = spec
        self.evaluator = FormulaEvaluator(spec)
        self.functions = spec.get('functions', {})

    def execute(self, func_name: str, state: dict, input_data: dict) -> dict:
        """
        関数を実行し、新しい状態またはエラーを返す

        Returns:
            {
                'success': bool,
                'state': dict (成功時の新しい状態),
                'error': str (エラー時のエラーコード),
                'pre_check': list (pre条件の評価結果),
                'post_actions': list (実行されたpost action)
            }
        """
        if func_name not in self.functions:
            return {'success': False, 'error': f'UNKNOWN_FUNCTION: {func_name}'}

        func_def = self.functions[func_name]
        context = EvalContext(state=state, input=input_data, derived={})

        result = {
            'success': True,
            'state': copy.deepcopy(state),
            'error': None,
            'pre_check': [],
            'post_actions': []
        }

        # 1. pre条件を評価
        for pre in func_def.get('pre', []):
            expr = pre if isinstance(pre, str) else pre.get('expr', '')
            if expr:
                pre_result = self.evaluator.evaluate(expr, context)
                result['pre_check'].append({'expr': expr, 'result': pre_result})
                if pre_result is not True:
                    result['success'] = False
                    result['error'] = 'PRE_CONDITION_FAILED'
                    return result

        # 2. error条件を評価
        for err in func_def.get('error', []):
            when_expr = err.get('when', '')
            if when_expr:
                err_result = self.evaluator.evaluate(when_expr, context)
                if err_result is True:
                    result['success'] = False
                    result['error'] = err.get('code', 'ERROR')
                    return result

        # 3. post条件を実行（状態を変更）
        new_state = copy.deepcopy(state)

        for post in func_def.get('post', []):
            action = post.get('action', '')
            condition = post.get('condition', '')

            # 条件付きアクション
            if condition:
                cond_result = self.evaluator.evaluate(condition,
                    EvalContext(state=new_state, input=input_data, derived={}))
                if cond_result is not True:
                    continue

            # アクションを実行
            executed = self._execute_action(action, new_state, input_data)
            if executed:
                result['post_actions'].append(action)

        result['state'] = new_state
        return result

    def _execute_action(self, action: str, state: dict, input_data: dict) -> bool:
        """
        アクションを解釈して状態を変更
        サポートするアクション:
        - "create <entity>" → エンティティにレコードを追加
        - "<entity>.<field> = <value>" → フィールドを更新
        """
        # create allocation
        create_match = re.match(r'create\s+(\w+)', action)
        if create_match:
            entity = create_match.group(1)
            if entity not in state:
                state[entity] = []
            if isinstance(state[entity], list):
                # 新しいレコードを作成
                new_record = {'amount': input_data.get('amount', 0)}
                # invoice_id, payment_id を推測
                if 'invoice' in state:
                    new_record['invoice_id'] = state['invoice'].get('id', 'unknown')
                if 'payment' in state:
                    new_record['payment_id'] = state['payment'].get('id', 'unknown')
                state[entity].append(new_record)
                return True
            return False

        # entity.field = value
        assign_match = re.match(r'(\w+)\.(\w+)\s*=\s*(\w+)', action)
        if assign_match:
            entity, field, value = assign_match.groups()
            if entity in state:
                state[entity][field] = value
                return True
            return False

        return False


def run_scenario(spec: dict, scenario: dict) -> dict:
    """シナリオを実行して結果を返す（操作シミュレーション付き）"""
    evaluator = FormulaEvaluator(spec)
    simulator = OperationSimulator(spec)

    # given → state構築
    state = {}
    given = scenario.get('given', {})
    for entity_name, entity_data in given.items():
        if isinstance(entity_data, list):
            state[entity_name] = entity_data
        else:
            # 単一エンティティにはIDを付与
            if isinstance(entity_data, dict) and 'id' not in entity_data:
                entity_data = dict(entity_data)
                entity_data['id'] = f'{entity_name.upper()}-001'
            state[entity_name] = entity_data

    # when → 操作を実行
    when = scenario.get('when', {})
    func_name = when.get('call')
    input_data = when.get('input', {})

    # then の期待値
    then = scenario.get('then', {})
    expected_error = then.get('error')
    expected_success = then.get('success', True)

    results = {
        'scenario': scenario.get('title', 'unknown'),
        'given': state,
        'when': {'call': func_name, 'input': input_data},
        'execution': None,
        'assertions': [],
        'all_passed': True
    }

    # 操作を実行
    if func_name:
        exec_result = simulator.execute(func_name, state, input_data)
        results['execution'] = {
            'success': exec_result['success'],
            'error': exec_result['error'],
            'pre_check': exec_result['pre_check'],
            'post_actions': exec_result['post_actions']
        }

        # エラー期待のケース
        if expected_error:
            if exec_result['error'] == expected_error:
                results['assertions'].append({
                    'type': 'error_check',
                    'expected': expected_error,
                    'actual': exec_result['error'],
                    'passed': True
                })
            else:
                results['assertions'].append({
                    'type': 'error_check',
                    'expected': expected_error,
                    'actual': exec_result['error'],
                    'passed': False
                })
                results['all_passed'] = False
            return results

        # 成功期待のケース → 新しい状態でassertを評価
        if exec_result['success']:
            new_state = exec_result['state']
            context = EvalContext(
                state=new_state,
                input=input_data,
                derived={}
            )
            results['state_after'] = new_state

            for assertion in then.get('assert', []):
                result = evaluator.evaluate(assertion, context)
                passed = result is True
                results['assertions'].append({
                    'expr': assertion,
                    'result': result,
                    'passed': passed
                })
                if not passed:
                    results['all_passed'] = False
        else:
            # 成功を期待していたが失敗した
            results['all_passed'] = False
            results['assertions'].append({
                'type': 'success_check',
                'expected': True,
                'actual': False,
                'error': exec_result['error'],
                'passed': False
            })

    return results


def main():
    import yaml
    import json
    import argparse

    parser = argparse.ArgumentParser(description='Formula Evaluator')
    parser.add_argument('spec_path', help='Path to spec YAML file')
    parser.add_argument('--eval', help='Evaluate a single formula')
    parser.add_argument('--scenario', help='Run a specific scenario by ID')
    parser.add_argument('--all-scenarios', action='store_true', help='Run all scenarios')
    args = parser.parse_args()

    with open(args.spec_path, 'r') as f:
        spec = yaml.safe_load(f)

    if args.eval:
        evaluator = FormulaEvaluator(spec)
        # 簡易テスト用のダミーコンテキスト
        context = EvalContext(
            state={
                'invoice': {'amount': 100000, 'status': 'open', 'id': 'INV-001'},
                'payment': {'amount': 80000, 'id': 'PAY-001'},
                'allocation': []
            },
            input={'amount': 80000},
            derived={}
        )
        result = evaluator.evaluate(args.eval, context)
        print(f"Formula: {args.eval}")
        print(f"Result: {result}")

    elif args.scenario:
        scenarios = spec.get('scenarios', {})
        if args.scenario in scenarios:
            result = run_scenario(spec, scenarios[args.scenario])
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print(f"Scenario not found: {args.scenario}")

    elif args.all_scenarios:
        scenarios = spec.get('scenarios', {})
        all_results = []
        for scenario_id, scenario_def in scenarios.items():
            result = run_scenario(spec, scenario_def)
            result['id'] = scenario_id
            all_results.append(result)
        print(json.dumps(all_results, indent=2, ensure_ascii=False))

    else:
        parser.print_help()


if __name__ == '__main__':
    main()
