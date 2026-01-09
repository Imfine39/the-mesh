#!/usr/bin/env python3
"""
Formula Evaluator v2: spec YAMLの式をPythonで安全に評価する
v5/v6 両方の形式に対応（spec_parser使用）
"""

import re
import ast
import copy
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from pathlib import Path
import sys

# Import spec_parser
sys.path.insert(0, str(Path(__file__).parent))
from spec_parser import SpecParser, StructuredPythonGenerator, parse_formula, StructuredNodeType


@dataclass
class EvalContext:
    """評価コンテキスト: state + input + derived関数"""
    state: Dict[str, Any]       # { invoice: {...}, payment: {...}, allocation: [...] }
    input: Dict[str, Any]       # 関数への入力
    derived: Dict[str, str]     # derived関数名 → formula


def is_v6_format(formula: Any) -> bool:
    """Check if formula is in v6 structured format"""
    return isinstance(formula, dict)


class FormulaEvaluator:
    """
    specの式をPythonで評価
    v5/v6 両方の形式に対応

    サポートする構文:
    - entity.field → state['entity']['field'] または state['entity'][i]['field']
    - self.field → 対象エンティティのフィールド
    - input.field → input['field']
    - remaining(entity) → derived関数呼び出し
    - sum/count/exists with from/where
    - case/when/then/else
    - ==, >=, <=, >, <, implies, and, or, in, not
    """

    def __init__(self, spec: dict):
        self.spec = spec
        self.entities = set(spec.get('state', {}).keys())
        self.derived_formulas = {}
        for name, defn in spec.get('derived', {}).items():
            if isinstance(defn, dict):
                self.derived_formulas[name] = defn.get('formula', '')
        self.parser = SpecParser(spec)

    def _get_entity_name(self, entity_arg: Any, state: dict) -> str:
        """Get entity name from argument (can be string name or dict entity)"""
        if isinstance(entity_arg, str):
            return entity_arg
        elif isinstance(entity_arg, dict):
            # If it's an entity dict, try to find it in state
            for name, value in state.items():
                if value is entity_arg:
                    return name
                if isinstance(value, list) and entity_arg in value:
                    return name
                if isinstance(value, dict) and value == entity_arg:
                    return name
            return 'unknown'
        return str(entity_arg)

    def _transform_formula_v5(self, formula: str) -> str:
        """v5形式の式をPython式に変換"""
        result = formula

        # 1. implies → Python論理式 (A implies B = not A or B)
        implies_pattern = r'(.+?)\s+implies\s+(.+)'
        match = re.match(implies_pattern, result, re.IGNORECASE)
        if match:
            a, b = match.groups()
            a_transformed = self._transform_formula_v5(a.strip())
            b_transformed = self._transform_formula_v5(b.strip())
            return f"(not ({a_transformed}) or ({b_transformed}))"

        # 2. sum(x.field where x.foreign = y.id) → Pythonリスト内包
        sum_where_pattern = r'sum\s*\(\s*(\w+)\.(\w+)\s+where\s+(.+?)\)'
        def sum_replacer(m):
            item_entity, item_field, where_clause = m.groups()
            # Transform where clause
            where_transformed = self._transform_where_clause(where_clause, item_entity)
            return f"sum(item['{item_field}'] for item in state.get('{item_entity}', []) if {where_transformed})"
        result = re.sub(sum_where_pattern, sum_replacer, result)

        # 3. count pattern
        count_where_pattern = r'count\s*\(\s*(\w+)\s+where\s+(.+?)\)'
        def count_replacer(m):
            item_entity, where_clause = m.groups()
            where_transformed = self._transform_where_clause(where_clause, item_entity)
            return f"len([item for item in state.get('{item_entity}', []) if {where_transformed}])"
        result = re.sub(count_where_pattern, count_replacer, result)

        # 4. derived関数呼び出し: remaining(invoice) → _eval_derived('remaining', 'invoice')
        for derived_name in self.derived_formulas.keys():
            pattern = rf'{derived_name}\s*\(\s*(\w+)\s*\)'
            def derived_replacer(m, name=derived_name):
                entity = m.group(1)
                return f"_eval_derived('{name}', '{entity}')"
            result = re.sub(pattern, derived_replacer, result)

        # 5. error(CODE) → _check_error('CODE')
        error_pattern = r'error\s*\(\s*(\w+)\s*\)'
        result = re.sub(error_pattern, r"_check_error('\1')", result)

        # 6. entity.field → state['entity']['field']
        for entity in self.entities:
            pattern = rf'\b{entity}\.(\w+)\b'
            result = re.sub(pattern, rf"state['{entity}']['\1']", result)

        # 7. self.field → entity['field']
        result = re.sub(r'\bself\.(\w+)\b', r"entity['\1']", result)

        # 8. input.field → input['\1']
        result = re.sub(r'\binput\.(\w+)\b', r"input['\1']", result)

        # 9. before_xxx → before['xxx']（シナリオ用）
        result = re.sub(r'\bbefore_(\w+)\b', r"before['\1']", result)

        return result

    def _transform_where_clause(self, where_clause: str, item_entity: str) -> str:
        """Transform where clause for aggregation"""
        result = where_clause

        # Replace item_entity.field with item['field']
        result = re.sub(rf'\b{item_entity}\.(\w+)\b', r"item['\1']", result)

        # Replace other entity.field with state['entity']['field']
        for entity in self.entities:
            if entity != item_entity:
                result = re.sub(rf'\b{entity}\.(\w+)\b', rf"state['{entity}']['\1']", result)

        # Replace 'and' with Python 'and', '==' stays same
        result = result.replace(' and ', ' and ')

        return result

    def _transform_formula_v6(self, formula: Any, entity_context: str = None) -> str:
        """v6形式の式をPython式に変換"""
        ast_node = self.parser.parse_formula(formula)
        gen = StructuredPythonGenerator(
            entity_var='entity',
            state_var='state',
            input_var='input',
            entity_name=entity_context,
            spec=self.spec
        )
        return gen.generate(ast_node)

    def evaluate(self, formula: Any, context: EvalContext,
                 error_state: Optional[str] = None,
                 entity_context: str = None) -> Any:
        """式を評価"""
        if is_v6_format(formula):
            transformed = self._transform_formula_v6(formula, entity_context)
        else:
            transformed = self._transform_formula_v5(str(formula))

        # 評価用の安全な環境を構築
        def _eval_derived(name: str, entity_name: str) -> Any:
            """derived関数を評価"""
            if name not in self.derived_formulas:
                raise ValueError(f"Unknown derived: {name}")
            derived_formula = self.derived_formulas[name]
            entity_data = context.state.get(entity_name, {})
            if isinstance(entity_data, list):
                entity_data = entity_data[0] if entity_data else {}
            # Create new context with entity set
            new_context = EvalContext(
                state=context.state,
                input=context.input,
                derived={}
            )
            return self.evaluate(derived_formula, new_context, entity_context=entity_name)

        def _check_error(code: str) -> bool:
            """エラー状態をチェック"""
            return error_state == code

        # Get entity data for v6 self references
        entity = {}
        if entity_context:
            entity = context.state.get(entity_context, {})
            if isinstance(entity, list):
                entity = entity[0] if entity else {}

        # Python 3のジェネレータ式/リスト内包表記のスコープ問題を回避するため
        safe_globals = {
            '__builtins__': {},
            'sum': sum,
            'len': len,
            'abs': abs,
            'min': min,
            'max': max,
            'any': any,
            'all': all,
            'True': True,
            'False': False,
            'None': None,
            'state': context.state,
            'input': context.input,
            'entity': entity,
            'before': {},
        }

        # Add each entity from state to globals (for derived function calls)
        for entity_name, entity_value in context.state.items():
            entity_data = entity_value
            if isinstance(entity_value, list):
                entity_data = entity_value[0] if entity_value else {}
            safe_globals[entity_name] = entity_data

        safe_locals = {
            '_eval_derived': _eval_derived,
            '_check_error': _check_error,
        }

        # Add derived function names to safe_locals for direct calls
        for derived_name in self.derived_formulas.keys():
            def make_derived_caller(name):
                def caller(state_arg, entity_arg):
                    return _eval_derived(name, self._get_entity_name(entity_arg, context.state))
                return caller
            safe_locals[derived_name] = make_derived_caller(derived_name)

        try:
            tree = ast.parse(transformed, mode='eval')
            # 安全性チェック
            allowed = {'sum', 'len', 'abs', 'min', 'max', 'any', 'all',
                      '_eval_derived', '_check_error'}
            allowed.update(self.derived_formulas.keys())  # Add derived function names

            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    raise ValueError("Import not allowed")
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        if node.func.id not in allowed:
                            raise ValueError(f"Unsafe function call: {node.func.id}")

            return eval(transformed, safe_globals, safe_locals)
        except Exception as e:
            return {
                'error': str(e),
                'original': formula,
                'transformed': transformed
            }


class OperationSimulator:
    """
    specのfunctions定義に基づいて操作をシミュレートする
    v5/v6 両方の形式に対応
    """

    def __init__(self, spec: dict):
        self.spec = spec
        self.evaluator = FormulaEvaluator(spec)
        self.functions = spec.get('functions', {})
        self.parser = SpecParser(spec)

    def execute(self, func_name: str, state: dict, input_data: dict) -> dict:
        """関数を実行し、新しい状態またはエラーを返す"""
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
            if isinstance(pre, str):
                expr = pre
                entity_hint = None
            else:
                expr = pre.get('expr', '')
                entity_hint = pre.get('entity')

            if expr:
                pre_result = self.evaluator.evaluate(expr, context, entity_context=entity_hint)
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
                result['post_actions'].append(str(action))

        result['state'] = new_state
        return result

    def _execute_action(self, action: Any, state: dict, input_data: dict) -> bool:
        """アクションを解釈して状態を変更"""

        # v6 structured action
        if is_v6_format(action):
            return self._execute_structured_action(action, state, input_data)

        # v5 string action
        if isinstance(action, str):
            return self._execute_string_action(action, state, input_data)

        return False

    def _execute_structured_action(self, action: dict, state: dict, input_data: dict) -> bool:
        """v6構造化アクションを実行"""

        # create entity
        if 'create' in action:
            entity = action['create']
            with_values = action.get('with', {})

            if entity not in state:
                state[entity] = []

            if isinstance(state[entity], list):
                new_record = {'id': f'{entity.upper()}-{len(state[entity]) + 1:03d}'}
                new_record.update(input_data)

                for field, value_expr in with_values.items():
                    if isinstance(value_expr, str):
                        # Evaluate expression
                        if value_expr.startswith("'") and value_expr.endswith("'"):
                            new_record[field] = value_expr[1:-1]
                        elif value_expr.startswith('input.'):
                            field_name = value_expr.split('.')[1]
                            new_record[field] = input_data.get(field_name)
                        else:
                            new_record[field] = value_expr
                    else:
                        new_record[field] = value_expr

                state[entity].append(new_record)
                return True

        # update entity
        if 'update' in action:
            entity = action['update']
            set_values = action.get('set', {})

            if entity in state:
                entity_data = state[entity]
                if isinstance(entity_data, list):
                    entity_data = entity_data[0] if entity_data else {}
                    if not entity_data:
                        return False

                for field, value_expr in set_values.items():
                    if isinstance(value_expr, str):
                        if value_expr.startswith("'") and value_expr.endswith("'"):
                            entity_data[field] = value_expr[1:-1]
                        else:
                            entity_data[field] = value_expr
                    else:
                        entity_data[field] = value_expr

                return True

        # delete entity
        if 'delete' in action:
            entity = action['delete']
            where = action.get('where')

            if entity in state and isinstance(state[entity], list):
                if where:
                    # TODO: Implement filtered delete
                    pass
                else:
                    state[entity] = []
                return True

        return False

    def _execute_string_action(self, action: str, state: dict, input_data: dict) -> bool:
        """v5文字列アクションを実行"""

        # create entity
        create_match = re.match(r'create\s+(\w+)', action)
        if create_match:
            entity = create_match.group(1)
            if entity not in state:
                state[entity] = []
            if isinstance(state[entity], list):
                new_record = {'amount': input_data.get('amount', 0)}
                if 'invoice' in state:
                    new_record['invoice_id'] = state['invoice'].get('id', 'unknown')
                if 'payment' in state:
                    new_record['payment_id'] = state['payment'].get('id', 'unknown')
                state[entity].append(new_record)
                return True
            return False

        # entity.field = value
        assign_match = re.match(r"(\w+)\.(\w+)\s*=\s*'?(\w+)'?", action)
        if assign_match:
            entity, field, value = assign_match.groups()
            if entity in state:
                entity_data = state[entity]
                if isinstance(entity_data, list):
                    entity_data = entity_data[0] if entity_data else {}
                entity_data[field] = value
                return True
            return False

        return False


def run_scenario(spec: dict, scenario: dict) -> dict:
    """シナリオを実行して結果を返す"""
    evaluator = FormulaEvaluator(spec)
    simulator = OperationSimulator(spec)

    # given → state構築
    state = {}
    given = scenario.get('given', {})
    for entity_name, entity_data in given.items():
        if isinstance(entity_data, list):
            state[entity_name] = entity_data
        else:
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
            context = EvalContext(state=new_state, input=input_data, derived={})
            results['state_after'] = new_state

            for assertion in then.get('assert', []):
                # v6 format: assertion can be dict with 'expr' key
                if isinstance(assertion, dict) and 'expr' in assertion:
                    assertion = assertion['expr']

                result = evaluator.evaluate(assertion, context)
                passed = result is True
                results['assertions'].append({
                    'expr': str(assertion),
                    'result': result,
                    'passed': passed
                })
                if not passed:
                    results['all_passed'] = False
        else:
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

    parser = argparse.ArgumentParser(description='Formula Evaluator v2')
    parser.add_argument('spec_path', help='Path to spec YAML file')
    parser.add_argument('--eval', help='Evaluate a single formula')
    parser.add_argument('--scenario', help='Run a specific scenario by ID')
    parser.add_argument('--all-scenarios', action='store_true', help='Run all scenarios')
    args = parser.parse_args()

    with open(args.spec_path, 'r') as f:
        spec = yaml.safe_load(f)

    if args.eval:
        evaluator = FormulaEvaluator(spec)
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
        passed = 0
        failed = 0
        for scenario_id, scenario_def in scenarios.items():
            result = run_scenario(spec, scenario_def)
            result['id'] = scenario_id
            all_results.append(result)
            if result['all_passed']:
                passed += 1
                print(f"  PASS: {scenario_id} - {result['scenario']}")
            else:
                failed += 1
                print(f"  FAIL: {scenario_id} - {result['scenario']}")
                for a in result['assertions']:
                    if not a.get('passed'):
                        print(f"    -> {a}")

        print(f"\nTotal: {passed} passed, {failed} failed")

    else:
        parser.print_help()


if __name__ == '__main__':
    main()
