#!/usr/bin/env python3
"""
Spec Parser: 統一spec式パーサー

全ジェネレーターで共有する式解析エンジン。
構造化YAML形式と文字列式の両方に対応。

対応パターン:
- 文字列式: "self.amount", "self.status == 'open'"
- 構造化式: sum/count/exists with from/where
- 条件分岐: case/when/then/else
- 比較演算: in, between, is_null
- 日付関数: date_diff, today, overlaps
- 論理演算: implies, and, or, not
- アクション: create, update, delete
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union, Set
from enum import Enum
import re
import sys
from pathlib import Path

# Import expression_parser for simple string expressions
sys.path.insert(0, str(Path(__file__).parent))
from expression_parser import (
    parse as parse_simple_expr,
    to_python,
    PythonGenerator,
    ASTNode,
    FieldAccess,
    InputAccess,
    FunctionCall,
    BinaryOp,
    UnaryOp,
    NumberLiteral,
    StringLiteral,
    BooleanLiteral,
    NullLiteral,
    NodeType,
)


# ==================================================
# Structured AST Node Definitions
# ==================================================

class StructuredNodeType(Enum):
    """構造化式のノード種別"""
    # Aggregations
    SUM = "sum"
    COUNT = "count"
    EXISTS = "exists"
    NOT_EXISTS = "not_exists"
    AVG = "avg"
    MIN = "min_agg"
    MAX = "max_agg"

    # Conditionals
    CASE = "case"
    IF_THEN_ELSE = "if_then_else"

    # Comparisons
    IN = "in"
    NOT_IN = "not_in"
    BETWEEN = "between"
    IS_NULL = "is_null"
    IS_NOT_NULL = "is_not_null"

    # Logical
    AND = "and"
    OR = "or"
    NOT = "not"
    IMPLIES = "implies"

    # Date/Time
    DATE_DIFF = "date_diff"
    TODAY = "today"
    NOW = "now"
    OVERLAPS = "overlaps"
    ADD_DAYS = "add_days"

    # Arithmetic
    ADD = "add"
    SUBTRACT = "subtract"
    MULTIPLY = "multiply"
    DIVIDE = "divide"

    # Actions
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"

    # Function call
    CALL = "call"

    # Comparison operators
    EQ = "eq"
    NE = "ne"
    LT = "lt"
    LE = "le"
    GT = "gt"
    GE = "ge"

    # Simple expression (delegated to expression_parser)
    SIMPLE = "simple"


@dataclass
class StructuredAST:
    """構造化ASTノード"""
    node_type: StructuredNodeType
    data: Dict[str, Any] = field(default_factory=dict)
    children: List['StructuredAST'] = field(default_factory=list)
    simple_ast: Optional[ASTNode] = None  # For delegated simple expressions
    raw_expr: Optional[str] = None  # Original expression string


# ==================================================
# Spec Parser
# ==================================================

class SpecParser:
    """統一spec式パーサー"""

    def __init__(self, spec: Optional[Dict[str, Any]] = None):
        """
        Args:
            spec: Spec YAML dictionary (for entity/derived name resolution)
        """
        self.spec = spec or {}
        self.entities = set(self.spec.get('state', {}).keys())
        self.derived_names = set(self.spec.get('derived', {}).keys())

    def parse_formula(self, formula: Any) -> StructuredAST:
        """
        文字列 or YAML構造を解析してASTを返す

        Args:
            formula: 文字列式 or 構造化YAML (dict/list)

        Returns:
            StructuredAST
        """
        if isinstance(formula, str):
            return self._parse_string_expr(formula)
        elif isinstance(formula, dict):
            return self._parse_structured(formula)
        elif isinstance(formula, (int, float)):
            return StructuredAST(
                node_type=StructuredNodeType.SIMPLE,
                simple_ast=NumberLiteral(formula),
                raw_expr=str(formula)
            )
        elif isinstance(formula, bool):
            return StructuredAST(
                node_type=StructuredNodeType.SIMPLE,
                simple_ast=BooleanLiteral(formula),
                raw_expr=str(formula)
            )
        elif formula is None:
            return StructuredAST(
                node_type=StructuredNodeType.SIMPLE,
                simple_ast=NullLiteral(),
                raw_expr="null"
            )
        else:
            raise ValueError(f"Unsupported formula type: {type(formula)}")

    def _parse_string_expr(self, expr: str) -> StructuredAST:
        """文字列式をパース（expression_parserに委譲）"""
        # Handle 'self' keyword - replace with placeholder for parsing
        normalized_expr = expr

        try:
            simple_ast = parse_simple_expr(normalized_expr)
            return StructuredAST(
                node_type=StructuredNodeType.SIMPLE,
                simple_ast=simple_ast,
                raw_expr=expr
            )
        except Exception as e:
            # If parsing fails, store as raw expression
            return StructuredAST(
                node_type=StructuredNodeType.SIMPLE,
                raw_expr=expr,
                data={'parse_error': str(e)}
            )

    def _parse_structured(self, data: Dict[str, Any]) -> StructuredAST:
        """構造化YAML式をパース"""

        # Aggregation functions: sum, count, exists, etc.
        for agg_type in ['sum', 'count', 'exists', 'not_exists', 'avg', 'min_agg', 'max_agg']:
            if agg_type in data:
                return self._parse_aggregation(agg_type, data[agg_type])

        # Conditionals
        if 'case' in data:
            return self._parse_case(data['case'])

        if 'if' in data:
            return self._parse_if_then_else(data)

        # Comparison operators
        if 'eq' in data:
            return self._parse_comparison('eq', data['eq'])
        if 'ne' in data:
            return self._parse_comparison('ne', data['ne'])
        if 'lt' in data:
            return self._parse_comparison('lt', data['lt'])
        if 'le' in data:
            return self._parse_comparison('le', data['le'])
        if 'gt' in data:
            return self._parse_comparison('gt', data['gt'])
        if 'ge' in data:
            return self._parse_comparison('ge', data['ge'])

        # In/between
        if 'in' in data:
            return self._parse_in(data)
        if 'not_in' in data:
            return self._parse_not_in(data)
        if 'between' in data:
            return self._parse_between(data)

        # Null checks
        if 'is_null' in data:
            return StructuredAST(
                node_type=StructuredNodeType.IS_NULL,
                data={'field': data['is_null']}
            )
        if 'is_not_null' in data:
            return StructuredAST(
                node_type=StructuredNodeType.IS_NOT_NULL,
                data={'field': data['is_not_null']}
            )

        # Logical operators
        if 'and' in data:
            return self._parse_logical('and', data['and'])
        if 'or' in data:
            return self._parse_logical('or', data['or'])
        if 'not' in data:
            return StructuredAST(
                node_type=StructuredNodeType.NOT,
                children=[self.parse_formula(data['not'])]
            )
        if 'implies' in data:
            return self._parse_implies(data['implies'])

        # Arithmetic
        if 'add' in data:
            return self._parse_arithmetic('add', data['add'])
        if 'subtract' in data:
            return self._parse_arithmetic('subtract', data['subtract'])
        if 'multiply' in data:
            return self._parse_arithmetic('multiply', data['multiply'])
        if 'divide' in data:
            return self._parse_arithmetic('divide', data['divide'])

        # Date functions
        if 'date_diff' in data:
            return self._parse_date_diff(data['date_diff'])
        if 'today' in data:
            return StructuredAST(node_type=StructuredNodeType.TODAY)
        if 'now' in data:
            return StructuredAST(node_type=StructuredNodeType.NOW)
        if 'overlaps' in data:
            return self._parse_overlaps(data['overlaps'])
        if 'add_days' in data:
            return self._parse_add_days(data['add_days'])

        # Function call
        if 'call' in data:
            return self._parse_function_call(data)

        # Actions
        if 'create' in data:
            return self._parse_create(data)
        if 'update' in data:
            return self._parse_update(data)
        if 'delete' in data:
            return self._parse_delete(data)

        # Unknown structure - return as-is
        return StructuredAST(
            node_type=StructuredNodeType.SIMPLE,
            data=data,
            raw_expr=str(data)
        )

    def _parse_aggregation(self, agg_type: str, agg_data: Any) -> StructuredAST:
        """集約関数をパース (sum, count, exists, etc.)"""
        node_type_map = {
            'sum': StructuredNodeType.SUM,
            'count': StructuredNodeType.COUNT,
            'exists': StructuredNodeType.EXISTS,
            'not_exists': StructuredNodeType.NOT_EXISTS,
            'avg': StructuredNodeType.AVG,
            'min_agg': StructuredNodeType.MIN,
            'max_agg': StructuredNodeType.MAX,
        }

        if isinstance(agg_data, dict):
            return StructuredAST(
                node_type=node_type_map[agg_type],
                data={
                    'expr': agg_data.get('expr'),
                    'from': agg_data.get('from'),
                    'join': agg_data.get('join'),
                    'where': agg_data.get('where'),
                }
            )
        else:
            # Simple aggregation: sum: "field"
            return StructuredAST(
                node_type=node_type_map[agg_type],
                data={'expr': agg_data}
            )

    def _parse_case(self, case_data: List[Dict]) -> StructuredAST:
        """case/when/then/else をパース"""
        branches = []
        else_branch = None

        for branch in case_data:
            if 'else' in branch:
                else_branch = self.parse_formula(branch['else'])
            elif 'when' in branch:
                branches.append({
                    'when': self.parse_formula(branch['when']),
                    'then': self.parse_formula(branch['then'])
                })

        return StructuredAST(
            node_type=StructuredNodeType.CASE,
            data={
                'branches': branches,
                'else': else_branch
            }
        )

    def _parse_if_then_else(self, data: Dict) -> StructuredAST:
        """if/then/else をパース"""
        return StructuredAST(
            node_type=StructuredNodeType.IF_THEN_ELSE,
            data={
                'if': self.parse_formula(data['if']),
                'then': self.parse_formula(data['then']),
                'else': self.parse_formula(data.get('else')) if 'else' in data else None
            }
        )

    def _parse_comparison(self, op: str, operands: List) -> StructuredAST:
        """比較演算子をパース"""
        op_map = {
            'eq': StructuredNodeType.EQ,
            'ne': StructuredNodeType.NE,
            'lt': StructuredNodeType.LT,
            'le': StructuredNodeType.LE,
            'gt': StructuredNodeType.GT,
            'ge': StructuredNodeType.GE,
        }

        return StructuredAST(
            node_type=op_map[op],
            children=[self.parse_formula(operands[0]), self.parse_formula(operands[1])]
        )

    def _parse_in(self, data: Dict) -> StructuredAST:
        """in演算子をパース"""
        in_data = data['in']
        if isinstance(in_data, dict):
            return StructuredAST(
                node_type=StructuredNodeType.IN,
                data={
                    'field': in_data.get('field'),
                    'values': in_data.get('values', [])
                }
            )
        else:
            # in: [values] format
            return StructuredAST(
                node_type=StructuredNodeType.IN,
                data={'values': in_data}
            )

    def _parse_not_in(self, data: Dict) -> StructuredAST:
        """not_in演算子をパース"""
        return StructuredAST(
            node_type=StructuredNodeType.NOT_IN,
            data=data['not_in']
        )

    def _parse_between(self, data: Dict) -> StructuredAST:
        """between演算子をパース"""
        between_data = data['between']
        return StructuredAST(
            node_type=StructuredNodeType.BETWEEN,
            data={
                'field': between_data.get('field'),
                'min': between_data.get('min'),
                'max': between_data.get('max'),
            }
        )

    def _parse_logical(self, op: str, operands: List) -> StructuredAST:
        """論理演算子をパース"""
        op_map = {
            'and': StructuredNodeType.AND,
            'or': StructuredNodeType.OR,
        }

        return StructuredAST(
            node_type=op_map[op],
            children=[self.parse_formula(operand) for operand in operands]
        )

    def _parse_implies(self, data: Dict) -> StructuredAST:
        """implies演算子をパース"""
        return StructuredAST(
            node_type=StructuredNodeType.IMPLIES,
            data={
                'if': self.parse_formula(data.get('if')),
                'then': self.parse_formula(data.get('then'))
            }
        )

    def _parse_arithmetic(self, op: str, operands: List) -> StructuredAST:
        """算術演算子をパース"""
        op_map = {
            'add': StructuredNodeType.ADD,
            'subtract': StructuredNodeType.SUBTRACT,
            'multiply': StructuredNodeType.MULTIPLY,
            'divide': StructuredNodeType.DIVIDE,
        }

        return StructuredAST(
            node_type=op_map[op],
            children=[self.parse_formula(operand) for operand in operands]
        )

    def _parse_date_diff(self, data: Dict) -> StructuredAST:
        """date_diff関数をパース"""
        return StructuredAST(
            node_type=StructuredNodeType.DATE_DIFF,
            data={
                'from': data.get('from'),
                'to': data.get('to'),
                'unit': data.get('unit', 'days')
            }
        )

    def _parse_overlaps(self, data: Dict) -> StructuredAST:
        """overlaps関数をパース"""
        return StructuredAST(
            node_type=StructuredNodeType.OVERLAPS,
            data={
                'range1': data.get('range1'),
                'range2': data.get('range2')
            }
        )

    def _parse_add_days(self, data: Dict) -> StructuredAST:
        """add_days関数をパース"""
        return StructuredAST(
            node_type=StructuredNodeType.ADD_DAYS,
            data={
                'date': data.get('date'),
                'days': data.get('days')
            }
        )

    def _parse_function_call(self, data: Dict) -> StructuredAST:
        """関数呼び出しをパース"""
        return StructuredAST(
            node_type=StructuredNodeType.CALL,
            data={
                'name': data.get('call'),
                'args': data.get('args', [])
            }
        )

    def _parse_create(self, data: Dict) -> StructuredAST:
        """createアクションをパース"""
        return StructuredAST(
            node_type=StructuredNodeType.CREATE,
            data={
                'entity': data.get('create'),
                'with': data.get('with', {})
            }
        )

    def _parse_update(self, data: Dict) -> StructuredAST:
        """updateアクションをパース"""
        return StructuredAST(
            node_type=StructuredNodeType.UPDATE,
            data={
                'entity': data.get('update'),
                'set': data.get('set', {})
            }
        )

    def _parse_delete(self, data: Dict) -> StructuredAST:
        """deleteアクションをパース"""
        return StructuredAST(
            node_type=StructuredNodeType.DELETE,
            data={
                'entity': data.get('delete'),
                'where': data.get('where')
            }
        )


# ==================================================
# Python Code Generator
# ==================================================

class StructuredPythonGenerator:
    """構造化ASTからPythonコードを生成"""

    def __init__(self, entity_var: str = 'entity', state_var: str = 'state',
                 input_var: str = 'input_data', entity_name: Optional[str] = None,
                 spec: Optional[Dict[str, Any]] = None):
        self.entity_var = entity_var
        self.state_var = state_var
        self.input_var = input_var
        self.entity_name = entity_name
        self.spec = spec or {}
        self.entities = set(self.spec.get('state', {}).keys())
        self.derived_names = set(self.spec.get('derived', {}).keys())
        # For aggregation where clauses
        self._from_alias = None
        self._from_entity = None
        self._parent_entity_var = None

    def generate(self, ast: StructuredAST) -> str:
        """ASTからPythonコードを生成"""
        method_name = f'_gen_{ast.node_type.value}'
        method = getattr(self, method_name, None)
        if method is None:
            if ast.node_type == StructuredNodeType.SIMPLE:
                return self._gen_simple(ast)
            raise NotImplementedError(f"No generator for {ast.node_type}")
        return method(ast)

    def _gen_simple(self, ast: StructuredAST) -> str:
        """単純式を生成（expression_parserに委譲）"""
        if ast.simple_ast:
            gen = PythonGenerator(
                entity_var=self.entity_var,
                state_var=self.state_var,
                input_var=self.input_var,
                entity_name=self.entity_name
            )
            code = gen.generate(ast.simple_ast)
            # Replace 'self' references with entity_var
            code = re.sub(r'\bself\.get\(', f'{self.entity_var}.get(', code)
            code = re.sub(r'\bself\[', f'{self.entity_var}[', code)
            return code
        elif ast.raw_expr:
            # Fallback: transform raw expression
            return self._transform_raw_expr(ast.raw_expr)
        return "None"

    def _transform_raw_expr(self, expr: str) -> str:
        """生の式をPython式に変換（フォールバック）"""
        result = expr

        # Handle entity.field patterns
        def replace_field_access(match):
            entity = match.group(1)
            field = match.group(2)
            if entity == 'self':
                return f"{self.entity_var}.get('{field}')"
            elif entity == 'input':
                return f"{self.input_var}.get('{field}')"
            else:
                return f"{entity}.get('{field}')"

        # Match entity.field pattern
        result = re.sub(r'\b(\w+)\.(\w+)\b', replace_field_access, result)
        return result

    def _gen_sum(self, ast: StructuredAST) -> str:
        """sum集約を生成"""
        return self._gen_aggregation('sum', ast)

    def _gen_count(self, ast: StructuredAST) -> str:
        """count集約を生成"""
        return self._gen_aggregation('count', ast)

    def _gen_exists(self, ast: StructuredAST) -> str:
        """exists集約を生成"""
        return self._gen_aggregation('exists', ast)

    def _gen_not_exists(self, ast: StructuredAST) -> str:
        """not_exists集約を生成"""
        return f"(not {self._gen_aggregation('exists', ast)})"

    def _gen_aggregation(self, func: str, ast: StructuredAST) -> str:
        """汎用集約生成"""
        data = ast.data
        expr = data.get('expr', '')
        from_clause = data.get('from', '')
        where_clause = data.get('where', '')
        join_clause = data.get('join')

        # Extract entity name from 'from' clause
        from_match = re.match(r'(\w+)(?:\s+as\s+(\w+))?', from_clause) if from_clause else None
        if from_match:
            from_entity = from_match.group(1)
            from_alias = from_match.group(2) or 'item'
        else:
            from_entity = from_clause or ''
            from_alias = 'item'

        # Generate expression for item
        if isinstance(expr, str):
            item_expr = self._transform_item_expr(expr, from_alias)
        else:
            item_expr = self.generate(self.parse_formula(expr) if hasattr(self, 'parse_formula') else expr)

        # Generate where condition
        where_code = "True"
        if where_clause:
            if isinstance(where_clause, str):
                where_code = self._transform_where_expr(where_clause, from_alias, from_entity)
            elif isinstance(where_clause, dict):
                where_parser = SpecParser(self.spec)
                where_ast = where_parser.parse_formula(where_clause)
                # Create a custom generator for where clause that:
                # - Uses from_alias for the from_entity (item for allocation)
                # - Uses original entity_var for self references
                where_gen = AggregationWhereGenerator(
                    from_alias=from_alias,
                    from_entity=from_entity,
                    parent_entity_var=self.entity_var,
                    state_var=self.state_var,
                    input_var=self.input_var,
                    spec=self.spec
                )
                where_code = where_gen.generate(where_ast)

        # Generate the aggregation
        if func == 'sum':
            return f"sum({item_expr} for {from_alias} in {self.state_var}.get('{from_entity}', []) if {where_code})"
        elif func == 'count':
            return f"len([{from_alias} for {from_alias} in {self.state_var}.get('{from_entity}', []) if {where_code}])"
        elif func == 'exists':
            return f"any(True for {from_alias} in {self.state_var}.get('{from_entity}', []) if {where_code})"
        else:
            return f"{func}({item_expr} for {from_alias} in {self.state_var}.get('{from_entity}', []) if {where_code})"

    def _transform_item_expr(self, expr: str, alias: str) -> str:
        """集約内の項目式を変換"""
        result = expr

        # Handle entity.field patterns
        def replace_field_access(match):
            entity = match.group(1)
            field = match.group(2)
            if entity == alias:
                return f"{alias}.get('{field}', 0)"
            elif entity == 'self':
                return f"{self.entity_var}.get('{field}')"
            else:
                return f"{entity}.get('{field}')"

        # Match entity.field pattern
        result = re.sub(r'\b(\w+)\.(\w+)\b', replace_field_access, result)
        return result

    def _transform_where_expr(self, expr: str, alias: str, from_entity: str) -> str:
        """where条件式を変換"""
        result = expr

        # Handle entity.field patterns
        # Use word boundary but exclude .get( pattern that's already transformed
        def replace_field_access(match):
            entity = match.group(1)
            field = match.group(2)
            # Don't process if it's already get('field') or get("field")
            if field in ('get',):
                return match.group(0)
            if entity == alias or entity == from_entity:
                return f"{alias}.get('{field}')"
            elif entity == 'self':
                return f"{self.entity_var}.get('{field}')"
            else:
                return f"{entity}.get('{field}')"

        # Match entity.field pattern (not .get patterns)
        result = re.sub(r'\b(\w+)\.(\w+)\b(?!\()', replace_field_access, result)
        return result

    def _gen_case(self, ast: StructuredAST) -> str:
        """case/when/then/else を生成"""
        branches = ast.data.get('branches', [])
        else_branch = ast.data.get('else')

        if not branches:
            return self.generate(else_branch) if else_branch else "None"

        # Generate nested ternary expression
        result = ""
        for branch in branches:
            when_code = self.generate(branch['when'])
            then_code = self.generate(branch['then'])
            result += f"({then_code} if {when_code} else "

        if else_branch:
            result += self.generate(else_branch)
        else:
            result += "None"

        result += ")" * len(branches)
        return result

    def _gen_if_then_else(self, ast: StructuredAST) -> str:
        """if/then/else を生成"""
        if_code = self.generate(ast.data['if'])
        then_code = self.generate(ast.data['then'])
        else_data = ast.data.get('else')

        if else_data:
            else_code = self.generate(else_data)
            return f"({then_code} if {if_code} else {else_code})"
        else:
            return f"({then_code} if {if_code} else None)"

    def _gen_eq(self, ast: StructuredAST) -> str:
        return self._gen_binary_op('==', ast)

    def _gen_ne(self, ast: StructuredAST) -> str:
        return self._gen_binary_op('!=', ast)

    def _gen_lt(self, ast: StructuredAST) -> str:
        return self._gen_binary_op('<', ast)

    def _gen_le(self, ast: StructuredAST) -> str:
        return self._gen_binary_op('<=', ast)

    def _gen_gt(self, ast: StructuredAST) -> str:
        return self._gen_binary_op('>', ast)

    def _gen_ge(self, ast: StructuredAST) -> str:
        return self._gen_binary_op('>=', ast)

    def _gen_binary_op(self, op: str, ast: StructuredAST) -> str:
        left = self.generate(ast.children[0])
        right = self.generate(ast.children[1])
        return f"({left} {op} {right})"

    def _gen_in(self, ast: StructuredAST) -> str:
        """in演算子を生成"""
        field = ast.data.get('field', '')
        values = ast.data.get('values', [])

        if field:
            field_code = self._transform_raw_expr(field)
        else:
            field_code = self.entity_var

        values_str = repr(values)
        return f"({field_code} in {values_str})"

    def _gen_not_in(self, ast: StructuredAST) -> str:
        """not_in演算子を生成"""
        field = ast.data.get('field', '')
        values = ast.data.get('values', [])

        if field:
            field_code = self._transform_raw_expr(field)
        else:
            field_code = self.entity_var

        values_str = repr(values)
        return f"({field_code} not in {values_str})"

    def _gen_between(self, ast: StructuredAST) -> str:
        """between演算子を生成"""
        field = ast.data.get('field', '')
        min_val = ast.data.get('min')
        max_val = ast.data.get('max')

        field_code = self._transform_raw_expr(field)
        return f"({min_val} <= {field_code} <= {max_val})"

    def _gen_is_null(self, ast: StructuredAST) -> str:
        field = self._transform_raw_expr(ast.data.get('field', ''))
        return f"({field} is None)"

    def _gen_is_not_null(self, ast: StructuredAST) -> str:
        field = self._transform_raw_expr(ast.data.get('field', ''))
        return f"({field} is not None)"

    def _gen_and(self, ast: StructuredAST) -> str:
        parts = [self.generate(child) for child in ast.children]
        return f"({' and '.join(parts)})"

    def _gen_or(self, ast: StructuredAST) -> str:
        parts = [self.generate(child) for child in ast.children]
        return f"({' or '.join(parts)})"

    def _gen_not(self, ast: StructuredAST) -> str:
        inner = self.generate(ast.children[0])
        return f"(not {inner})"

    def _gen_implies(self, ast: StructuredAST) -> str:
        """implies演算子を生成: A implies B = not A or B"""
        if_code = self.generate(ast.data['if'])
        then_code = self.generate(ast.data['then'])
        return f"(not ({if_code}) or ({then_code}))"

    def _gen_add(self, ast: StructuredAST) -> str:
        return self._gen_arithmetic_op('+', ast)

    def _gen_subtract(self, ast: StructuredAST) -> str:
        return self._gen_arithmetic_op('-', ast)

    def _gen_multiply(self, ast: StructuredAST) -> str:
        return self._gen_arithmetic_op('*', ast)

    def _gen_divide(self, ast: StructuredAST) -> str:
        return self._gen_arithmetic_op('/', ast)

    def _gen_arithmetic_op(self, op: str, ast: StructuredAST) -> str:
        left = self.generate(ast.children[0])
        right = self.generate(ast.children[1])
        return f"({left} {op} {right})"

    def _gen_date_diff(self, ast: StructuredAST) -> str:
        """date_diff関数を生成"""
        from_date = self._transform_raw_expr(ast.data.get('from', ''))
        to_date = self._transform_raw_expr(ast.data.get('to', ''))
        unit = ast.data.get('unit', 'days')

        return f"date_diff({from_date}, {to_date}, '{unit}')"

    def _gen_today(self, ast: StructuredAST) -> str:
        return "today()"

    def _gen_now(self, ast: StructuredAST) -> str:
        return "now()"

    def _gen_overlaps(self, ast: StructuredAST) -> str:
        """overlaps関数を生成"""
        range1 = ast.data.get('range1', [])
        range2 = ast.data.get('range2', [])

        if len(range1) >= 2 and len(range2) >= 2:
            r1_start = self._transform_raw_expr(range1[0])
            r1_end = self._transform_raw_expr(range1[1])
            r2_start = self._transform_raw_expr(range2[0])
            r2_end = self._transform_raw_expr(range2[1])
            return f"overlaps({r1_start}, {r1_end}, {r2_start}, {r2_end})"

        return "False"

    def _gen_add_days(self, ast: StructuredAST) -> str:
        """add_days関数を生成"""
        date = self._transform_raw_expr(ast.data.get('date', ''))
        days = ast.data.get('days', 0)
        return f"add_days({date}, {days})"

    def _gen_call(self, ast: StructuredAST) -> str:
        """関数呼び出しを生成"""
        name = ast.data.get('name', '')
        args = ast.data.get('args', [])

        args_code = []
        for arg in args:
            if isinstance(arg, str):
                # Check if arg is 'self' - replace with entity_var
                if arg == 'self':
                    args_code.append(self.entity_var)
                else:
                    # Check if it's a known entity name or field access
                    transformed = self._transform_raw_expr(arg)
                    # If it's just an entity name (no .get), keep it as-is
                    if arg in self.entities and '.get' not in transformed:
                        args_code.append(arg)
                    else:
                        args_code.append(transformed)
            else:
                args_code.append(repr(arg))

        # If it's a derived function, add state parameter
        if name in self.derived_names:
            # Use the first arg as entity if provided, otherwise use entity_var
            if args_code:
                entity_arg = args_code[0]
                return f"{name}({self.state_var}, {entity_arg})"
            else:
                return f"{name}({self.state_var}, {self.entity_var})"

        return f"{name}({', '.join(args_code)})"

    def _gen_create(self, ast: StructuredAST) -> str:
        """createアクションを生成"""
        entity = ast.data.get('entity', '')
        with_values = ast.data.get('with', {})

        lines = []
        lines.append(f"new_{entity} = {{'id': f'{entity.upper()}-{{len({self.state_var}.get(\"{entity}\", [])) + 1:03d}}', **{self.input_var}}}")

        for field, value in with_values.items():
            if isinstance(value, str):
                value_code = self._transform_raw_expr(value)
            else:
                value_code = repr(value)
            lines.append(f"new_{entity}['{field}'] = {value_code}")

        lines.append(f"if '{entity}' not in {self.state_var}: {self.state_var}['{entity}'] = []")
        lines.append(f"{self.state_var}['{entity}'].append(new_{entity})")

        return '\n'.join(lines)

    def _gen_update(self, ast: StructuredAST) -> str:
        """updateアクションを生成"""
        entity = ast.data.get('entity', '')
        set_values = ast.data.get('set', {})

        lines = []
        for field, value in set_values.items():
            if isinstance(value, str):
                value_code = self._transform_raw_expr(value)
            else:
                value_code = repr(value)
            lines.append(f"{entity}['{field}'] = {value_code}")

        return '\n'.join(lines)

    def _gen_delete(self, ast: StructuredAST) -> str:
        """deleteアクションを生成"""
        entity = ast.data.get('entity', '')
        where = ast.data.get('where')

        if where:
            where_code = self._transform_raw_expr(where)
            return f"{self.state_var}['{entity}'] = [e for e in {self.state_var}.get('{entity}', []) if not ({where_code})]"
        else:
            return f"{self.state_var}['{entity}'] = []"


class AggregationWhereGenerator(StructuredPythonGenerator):
    """
    集約のwhere句用の特殊ジェネレーター

    - from_alias (e.g., 'item') はfrom_entityのフィールドに使用
    - parent_entity_var (e.g., 'entity') はself参照に使用
    """

    def __init__(self, from_alias: str, from_entity: str, parent_entity_var: str,
                 state_var: str = 'state', input_var: str = 'input_data',
                 spec: Optional[Dict[str, Any]] = None):
        super().__init__(
            entity_var=parent_entity_var,  # self -> parent_entity_var
            state_var=state_var,
            input_var=input_var,
            entity_name=None,
            spec=spec
        )
        self._from_alias = from_alias
        self._from_entity = from_entity
        self._parent_entity_var = parent_entity_var

    def _gen_simple(self, ast: StructuredAST) -> str:
        """単純式を生成 - 集約のwhere句用"""
        if ast.simple_ast:
            gen = PythonGenerator(
                entity_var=self._parent_entity_var,
                state_var=self.state_var,
                input_var=self.input_var,
                entity_name=None
            )
            code = gen.generate(ast.simple_ast)
            # Replace 'self' with parent_entity_var
            code = re.sub(r'\bself\.get\(', f'{self._parent_entity_var}.get(', code)
            code = re.sub(r'\bself\[', f'{self._parent_entity_var}[', code)
            # Replace from_entity with from_alias
            code = re.sub(rf'\b{self._from_entity}\.get\(', f'{self._from_alias}.get(', code)
            return code
        elif ast.raw_expr:
            return self._transform_where_raw_expr(ast.raw_expr)
        return "None"

    def _transform_where_raw_expr(self, expr: str) -> str:
        """where句の式をPython式に変換"""
        result = expr

        def replace_field_access(match):
            entity = match.group(1)
            field = match.group(2)
            if field in ('get',):
                return match.group(0)
            if entity == 'self':
                return f"{self._parent_entity_var}.get('{field}')"
            elif entity == self._from_entity or entity == self._from_alias:
                return f"{self._from_alias}.get('{field}')"
            elif entity == 'input':
                return f"{self.input_var}.get('{field}')"
            else:
                return f"{entity}.get('{field}')"

        result = re.sub(r'\b(\w+)\.(\w+)\b(?!\()', replace_field_access, result)
        return result


# ==================================================
# High-level API
# ==================================================

def parse_formula(formula: Any, spec: Optional[Dict[str, Any]] = None) -> StructuredAST:
    """式をパースしてASTを返す"""
    parser = SpecParser(spec)
    return parser.parse_formula(formula)


def to_python_code(ast: StructuredAST, spec: Optional[Dict[str, Any]] = None, **kwargs) -> str:
    """ASTからPythonコードを生成"""
    gen = StructuredPythonGenerator(spec=spec, **kwargs)
    return gen.generate(ast)


def parse_and_generate(formula: Any, spec: Optional[Dict[str, Any]] = None, **kwargs) -> str:
    """式をパースしてPythonコードを生成"""
    ast = parse_formula(formula, spec)
    return to_python_code(ast, spec, **kwargs)


# ==================================================
# Tests
# ==================================================

def test_spec_parser():
    """Spec parser tests"""
    print("Testing spec_parser...")

    test_cases = [
        # Simple string expressions
        ("self.amount", "entity.get('amount')"),
        ("self.status == 'open'", "(entity.get('status') == 'open')"),

        # Structured sum
        (
            {
                "sum": {
                    "expr": "item.amount",
                    "from": "allocation",
                    "where": "item.invoice_id == self.id"
                }
            },
            None  # Complex output, just check it runs
        ),

        # Case/when
        (
            {
                "case": [
                    {"when": "self.days >= 7", "then": 0},
                    {"when": "self.days >= 3", "then": 0.3},
                    {"else": 1.0}
                ]
            },
            None
        ),

        # In operator
        (
            {
                "in": {
                    "field": "self.status",
                    "values": ["open", "pending"]
                }
            },
            "(entity.get('status') in ['open', 'pending'])"
        ),

        # Implies
        (
            {
                "implies": {
                    "if": "self.remaining == 0",
                    "then": "self.status == 'closed'"
                }
            },
            None
        ),
    ]

    passed = 0
    failed = 0

    for formula, expected in test_cases:
        try:
            result = parse_and_generate(formula)
            if expected is None:
                print(f"  PASS: {formula} -> {result[:50]}...")
                passed += 1
            elif result == expected:
                print(f"  PASS: {formula}")
                passed += 1
            else:
                print(f"  FAIL: {formula}")
                print(f"    Expected: {expected}")
                print(f"    Got:      {result}")
                failed += 1
        except Exception as e:
            print(f"  ERROR: {formula}")
            print(f"    {type(e).__name__}: {e}")
            failed += 1

    print(f"\nResults: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == '__main__':
    test_spec_parser()
