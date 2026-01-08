#!/usr/bin/env python3
"""
Expression Parser: Spec式をASTにパースし、各言語のコードを生成

Spec YAML の式（formula, pre, post, error条件）を統一的に扱う。

パターン:
- フィールドアクセス: entity.field
- 入力アクセス: input.field
- リテラル: 100, 'active', null, true
- 二項演算: a + b, a - b, a * b, a / b
- 比較: a == b, a != b, a < b, a <= b, a > b, a >= b
- 論理演算: a and b, a or b, not a
- 関数呼び出し: sum(...), count(...), exists(...), derived(entity)
- 代入: entity.field = expr
- 条件付き: if condition then action
"""

from dataclasses import dataclass
from typing import Any, List, Optional, Union
from enum import Enum
import re


# ==================================================
# AST Node Definitions
# ==================================================

class NodeType(Enum):
    # Literals
    NUMBER = "number"
    STRING = "string"
    BOOLEAN = "boolean"
    NULL = "null"

    # Access
    FIELD_ACCESS = "field_access"      # entity.field
    INPUT_ACCESS = "input_access"      # input.field
    STATE_ACCESS = "state_access"      # state reference

    # Operations
    BINARY_OP = "binary_op"            # a + b, a == b, etc.
    UNARY_OP = "unary_op"              # not a, -a

    # Functions
    FUNCTION_CALL = "function_call"    # sum(...), count(...), derived(entity)

    # Statements
    ASSIGNMENT = "assignment"          # entity.field = expr
    CONDITIONAL = "conditional"        # if cond then action
    CREATE = "create"                  # create entity with field = value


@dataclass
class ASTNode:
    """Base AST node"""
    node_type: NodeType


@dataclass
class NumberLiteral(ASTNode):
    value: Union[int, float]

    def __init__(self, value):
        super().__init__(NodeType.NUMBER)
        self.value = value


@dataclass
class StringLiteral(ASTNode):
    value: str

    def __init__(self, value):
        super().__init__(NodeType.STRING)
        self.value = value


@dataclass
class BooleanLiteral(ASTNode):
    value: bool

    def __init__(self, value):
        super().__init__(NodeType.BOOLEAN)
        self.value = value


@dataclass
class NullLiteral(ASTNode):
    def __init__(self):
        super().__init__(NodeType.NULL)


@dataclass
class FieldAccess(ASTNode):
    """entity.field アクセス"""
    entity: str
    field: str

    def __init__(self, entity, field):
        super().__init__(NodeType.FIELD_ACCESS)
        self.entity = entity
        self.field = field


@dataclass
class InputAccess(ASTNode):
    """input.field アクセス"""
    field: str

    def __init__(self, field):
        super().__init__(NodeType.INPUT_ACCESS)
        self.field = field


@dataclass
class BinaryOp(ASTNode):
    """二項演算: a op b"""
    operator: str  # +, -, *, /, ==, !=, <, <=, >, >=, and, or
    left: ASTNode
    right: ASTNode

    def __init__(self, operator, left, right):
        super().__init__(NodeType.BINARY_OP)
        self.operator = operator
        self.left = left
        self.right = right


@dataclass
class UnaryOp(ASTNode):
    """単項演算: op a"""
    operator: str  # not, -
    operand: ASTNode

    def __init__(self, operator, operand):
        super().__init__(NodeType.UNARY_OP)
        self.operator = operator
        self.operand = operand


@dataclass
class FunctionCall(ASTNode):
    """関数呼び出し"""
    name: str
    args: List[ASTNode]
    where_clause: Optional[ASTNode] = None  # for sum/count/exists

    def __init__(self, name, args, where_clause=None):
        super().__init__(NodeType.FUNCTION_CALL)
        self.name = name
        self.args = args
        self.where_clause = where_clause


@dataclass
class Assignment(ASTNode):
    """代入文"""
    target: FieldAccess
    value: ASTNode

    def __init__(self, target, value):
        super().__init__(NodeType.ASSIGNMENT)
        self.target = target
        self.value = value


@dataclass
class Conditional(ASTNode):
    """条件付き実行"""
    condition: ASTNode
    then_action: ASTNode
    else_action: Optional[ASTNode] = None

    def __init__(self, condition, then_action, else_action=None):
        super().__init__(NodeType.CONDITIONAL)
        self.condition = condition
        self.then_action = then_action
        self.else_action = else_action


@dataclass
class Create(ASTNode):
    """エンティティ作成"""
    entity: str
    with_values: dict  # field -> ASTNode

    def __init__(self, entity, with_values=None):
        super().__init__(NodeType.CREATE)
        self.entity = entity
        self.with_values = with_values or {}


# ==================================================
# Tokenizer
# ==================================================

TOKEN_PATTERNS = [
    ('NUMBER', r'\d+(\.\d+)?'),
    ('STRING', r"'[^']*'"),
    ('KEYWORD', r'\b(and|or|not|if|then|else|where|with|create|null|true|false|today)\b'),
    ('IDENT', r'[a-zA-Z_][a-zA-Z0-9_]*'),
    ('OP', r'[+\-*/]'),
    ('CMP', r'(==|!=|<=|>=|<|>)'),
    ('ASSIGN', r'='),
    ('DOT', r'\.'),
    ('LPAREN', r'\('),
    ('RPAREN', r'\)'),
    ('COMMA', r','),
    ('WS', r'\s+'),
]

TOKEN_REGEX = '|'.join(f'(?P<{name}>{pattern})' for name, pattern in TOKEN_PATTERNS)


@dataclass
class Token:
    type: str
    value: str
    pos: int


def tokenize(expr: str) -> List[Token]:
    """式をトークン列に分解"""
    tokens = []
    for match in re.finditer(TOKEN_REGEX, expr):
        kind = match.lastgroup
        value = match.group()
        if kind == 'WS':
            continue
        tokens.append(Token(kind, value, match.start()))
    return tokens


# ==================================================
# Parser
# ==================================================

class Parser:
    """再帰下降パーサー"""

    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0

    def current(self) -> Optional[Token]:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None

    def peek(self, offset=0) -> Optional[Token]:
        pos = self.pos + offset
        if pos < len(self.tokens):
            return self.tokens[pos]
        return None

    def consume(self, expected_type=None, expected_value=None) -> Token:
        token = self.current()
        if token is None:
            raise SyntaxError(f"Unexpected end of expression")
        if expected_type and token.type != expected_type:
            raise SyntaxError(f"Expected {expected_type}, got {token.type} at pos {token.pos}")
        if expected_value and token.value != expected_value:
            raise SyntaxError(f"Expected '{expected_value}', got '{token.value}' at pos {token.pos}")
        self.pos += 1
        return token

    def match(self, *types) -> bool:
        token = self.current()
        return token and token.type in types

    def match_value(self, value) -> bool:
        token = self.current()
        return token and token.value == value

    # Grammar rules

    def parse(self) -> ASTNode:
        """Entry point"""
        return self.parse_statement()

    def parse_statement(self) -> ASTNode:
        """statement := create | assignment | conditional | expression"""

        # create entity ...
        if self.match_value('create'):
            return self.parse_create()

        # if ... then ...
        if self.match_value('if'):
            return self.parse_conditional()

        # assignment or expression
        expr = self.parse_expression()

        # Check for assignment
        if self.match('ASSIGN'):
            if not isinstance(expr, FieldAccess):
                raise SyntaxError("Left side of assignment must be field access")
            self.consume('ASSIGN')
            value = self.parse_expression()
            return Assignment(expr, value)

        return expr

    def parse_create(self) -> Create:
        """create := 'create' IDENT ('with' field '=' expr (',' field '=' expr)*)?"""
        self.consume('KEYWORD', 'create')
        entity = self.consume('IDENT').value

        with_values = {}
        if self.match_value('with'):
            self.consume('KEYWORD', 'with')
            # Parse field = value pairs
            field = self.consume('IDENT').value
            self.consume('ASSIGN')
            value = self.parse_expression()
            with_values[field] = value

            while self.match('COMMA'):
                self.consume('COMMA')
                field = self.consume('IDENT').value
                self.consume('ASSIGN')
                value = self.parse_expression()
                with_values[field] = value

        return Create(entity, with_values)

    def parse_conditional(self) -> Conditional:
        """conditional := 'if' expression 'then' statement ('else' statement)?"""
        self.consume('KEYWORD', 'if')
        condition = self.parse_expression()
        self.consume('KEYWORD', 'then')
        then_action = self.parse_statement()

        else_action = None
        if self.match_value('else'):
            self.consume('KEYWORD', 'else')
            else_action = self.parse_statement()

        return Conditional(condition, then_action, else_action)

    def parse_expression(self) -> ASTNode:
        """expression := or_expr"""
        return self.parse_or_expr()

    def parse_or_expr(self) -> ASTNode:
        """or_expr := and_expr ('or' and_expr)*"""
        left = self.parse_and_expr()
        while self.match_value('or'):
            self.consume('KEYWORD', 'or')
            right = self.parse_and_expr()
            left = BinaryOp('or', left, right)
        return left

    def parse_and_expr(self) -> ASTNode:
        """and_expr := not_expr ('and' not_expr)*"""
        left = self.parse_not_expr()
        while self.match_value('and'):
            self.consume('KEYWORD', 'and')
            right = self.parse_not_expr()
            left = BinaryOp('and', left, right)
        return left

    def parse_not_expr(self) -> ASTNode:
        """not_expr := 'not' not_expr | comparison"""
        if self.match_value('not'):
            self.consume('KEYWORD', 'not')
            operand = self.parse_not_expr()
            return UnaryOp('not', operand)
        return self.parse_comparison()

    def parse_comparison(self) -> ASTNode:
        """comparison := additive (CMP additive)?"""
        left = self.parse_additive()
        if self.match('CMP'):
            op = self.consume('CMP').value
            right = self.parse_additive()
            left = BinaryOp(op, left, right)
        return left

    def parse_additive(self) -> ASTNode:
        """additive := multiplicative (('+' | '-') multiplicative)*"""
        left = self.parse_multiplicative()
        while self.current() and self.current().value in ('+', '-'):
            op = self.consume('OP').value
            right = self.parse_multiplicative()
            left = BinaryOp(op, left, right)
        return left

    def parse_multiplicative(self) -> ASTNode:
        """multiplicative := unary (('*' | '/') unary)*"""
        left = self.parse_unary()
        while self.current() and self.current().value in ('*', '/'):
            op = self.consume('OP').value
            right = self.parse_unary()
            left = BinaryOp(op, left, right)
        return left

    def parse_unary(self) -> ASTNode:
        """unary := '-' unary | primary"""
        if self.current() and self.current().value == '-':
            self.consume('OP')
            operand = self.parse_unary()
            return UnaryOp('-', operand)
        return self.parse_primary()

    def parse_primary(self) -> ASTNode:
        """primary := literal | function_call | field_access | '(' expression ')'"""
        token = self.current()

        if token is None:
            raise SyntaxError("Unexpected end of expression")

        # Parenthesized expression
        if token.type == 'LPAREN':
            self.consume('LPAREN')
            expr = self.parse_expression()
            self.consume('RPAREN')
            return expr

        # Number literal
        if token.type == 'NUMBER':
            self.consume('NUMBER')
            if '.' in token.value:
                return NumberLiteral(float(token.value))
            return NumberLiteral(int(token.value))

        # String literal
        if token.type == 'STRING':
            self.consume('STRING')
            return StringLiteral(token.value[1:-1])  # Remove quotes

        # Keywords: null, true, false, today
        if token.type == 'KEYWORD':
            if token.value == 'null':
                self.consume('KEYWORD')
                return NullLiteral()
            elif token.value == 'true':
                self.consume('KEYWORD')
                return BooleanLiteral(True)
            elif token.value == 'false':
                self.consume('KEYWORD')
                return BooleanLiteral(False)
            elif token.value == 'today':
                self.consume('KEYWORD')
                return FunctionCall('today', [])

        # Identifier: could be function call or field access
        if token.type == 'IDENT':
            name = self.consume('IDENT').value

            # Function call: name(...)
            if self.match('LPAREN'):
                return self.parse_function_call(name)

            # Field access: entity.field or input.field
            if self.match('DOT'):
                self.consume('DOT')
                field = self.consume('IDENT').value

                if name == 'input':
                    return InputAccess(field)
                else:
                    return FieldAccess(name, field)

            # Just an identifier (variable reference)
            return FieldAccess(name, None)

        raise SyntaxError(f"Unexpected token: {token.type} '{token.value}' at pos {token.pos}")

    def parse_function_call(self, name: str) -> FunctionCall:
        """function_call := IDENT '(' args ')' ('where' condition)?"""
        self.consume('LPAREN')

        args = []
        where_clause = None

        # Parse arguments
        if not self.match('RPAREN'):
            # Check for aggregation pattern: sum(entity.field where condition)
            first_arg = self.parse_expression()
            args.append(first_arg)

            # Check for 'where' clause
            if self.match_value('where'):
                self.consume('KEYWORD', 'where')
                where_clause = self.parse_expression()
            else:
                # More arguments
                while self.match('COMMA'):
                    self.consume('COMMA')
                    args.append(self.parse_expression())

        self.consume('RPAREN')

        return FunctionCall(name, args, where_clause)


def parse(expr: str) -> ASTNode:
    """式をパースしてASTを返す"""
    tokens = tokenize(expr)
    if not tokens:
        raise SyntaxError("Empty expression")
    parser = Parser(tokens)
    ast = parser.parse()

    # Check for leftover tokens
    if parser.current() is not None:
        remaining = parser.current()
        raise SyntaxError(f"Unexpected token after expression: {remaining.value} at pos {remaining.pos}")

    return ast


# ==================================================
# Code Generators
# ==================================================

class PythonGenerator:
    """ASTからPythonコードを生成"""

    def __init__(self, entity_var='entity', state_var='state', input_var='input_data',
                 entity_name=None):
        self.entity_var = entity_var
        self.state_var = state_var
        self.input_var = input_var
        self.entity_name = entity_name  # Entity name to replace with entity_var
        self.entities = set()  # Track referenced entities

    def generate(self, node: ASTNode) -> str:
        """Generate Python code from AST"""
        method_name = f'gen_{node.node_type.value}'
        method = getattr(self, method_name, None)
        if method is None:
            raise NotImplementedError(f"No generator for {node.node_type}")
        return method(node)

    def gen_number(self, node: NumberLiteral) -> str:
        return str(node.value)

    def gen_string(self, node: StringLiteral) -> str:
        return f"'{node.value}'"

    def gen_boolean(self, node: BooleanLiteral) -> str:
        return 'True' if node.value else 'False'

    def gen_null(self, node: NullLiteral) -> str:
        return 'None'

    def gen_field_access(self, node: FieldAccess) -> str:
        self.entities.add(node.entity)
        # Replace entity name with entity_var if it matches
        entity_ref = node.entity
        if self.entity_name and node.entity == self.entity_name:
            entity_ref = self.entity_var
        if node.field is None:
            return entity_ref
        return f"{entity_ref}.get('{node.field}')"

    def gen_input_access(self, node: InputAccess) -> str:
        return f"{self.input_var}.get('{node.field}')"

    def gen_binary_op(self, node: BinaryOp) -> str:
        left = self.generate(node.left)
        right = self.generate(node.right)

        op_map = {
            '==': '==',
            '!=': '!=',
            '<': '<',
            '<=': '<=',
            '>': '>',
            '>=': '>=',
            '+': '+',
            '-': '-',
            '*': '*',
            '/': '/',
            'and': 'and',
            'or': 'or',
        }

        py_op = op_map.get(node.operator, node.operator)

        # Handle null comparisons
        if isinstance(node.right, NullLiteral):
            if node.operator == '==':
                return f"({left} is None)"
            elif node.operator == '!=':
                return f"({left} is not None)"

        return f"({left} {py_op} {right})"

    def gen_unary_op(self, node: UnaryOp) -> str:
        operand = self.generate(node.operand)
        if node.operator == 'not':
            return f"(not {operand})"
        elif node.operator == '-':
            return f"(-{operand})"
        return f"({node.operator}{operand})"

    def gen_function_call(self, node: FunctionCall) -> str:
        name = node.name

        # Built-in functions
        if name == 'today':
            return 'today()'

        # Aggregation functions with where clause
        if name in ('sum', 'count', 'exists') and node.where_clause:
            return self._gen_aggregation(name, node.args, node.where_clause)

        # Derived function call: derived(entity)
        if node.args and isinstance(node.args[0], FieldAccess):
            entity = node.args[0].entity
            self.entities.add(entity)
            # Replace entity name with entity_var if it matches
            entity_ref = entity
            if self.entity_name and entity == self.entity_name:
                entity_ref = self.entity_var
            return f"{name}({self.state_var}, {entity_ref})"

        # Generic function call
        args_str = ', '.join(self.generate(arg) for arg in node.args)
        return f"{name}({args_str})"

    def _gen_aggregation(self, func: str, args: List[ASTNode], where: ASTNode) -> str:
        """Generate aggregation like sum(x.field where condition)"""
        if not args or not isinstance(args[0], FieldAccess):
            raise ValueError(f"Invalid aggregation: {func}")

        target = args[0]
        agg_entity_name = target.entity
        field_name = target.field

        # Generate where condition
        # We need to replace entity references with loop variable for the aggregated entity
        # and with entity_var for the parent entity (self.entity_name)
        where_gen = PythonGenerator(
            entity_var=self.entity_var,
            state_var=self.state_var,
            input_var=self.input_var,
            entity_name=self.entity_name
        )
        where_code = where_gen.generate(where)
        # Replace aggregated entity.get('field') with item.get('field')
        where_code = re.sub(rf"\b{agg_entity_name}\.get\('(\w+)'\)", r"item.get('\1')", where_code)

        if func == 'sum':
            return f"sum(item.get('{field_name}', 0) for item in {self.state_var}.get('{agg_entity_name}', []) if {where_code})"
        elif func == 'count':
            return f"len([item for item in {self.state_var}.get('{agg_entity_name}', []) if {where_code}])"
        elif func == 'exists':
            return f"any(item for item in {self.state_var}.get('{agg_entity_name}', []) if {where_code})"

        raise ValueError(f"Unknown aggregation: {func}")

    def gen_assignment(self, node: Assignment) -> str:
        target = node.target
        value = self.generate(node.value)
        self.entities.add(target.entity)
        return f"{target.entity}['{target.field}'] = {value}"

    def gen_conditional(self, node: Conditional) -> str:
        condition = self.generate(node.condition)
        then_action = self.generate(node.then_action)

        if node.else_action:
            else_action = self.generate(node.else_action)
            return f"if {condition}:\n    {then_action}\nelse:\n    {else_action}"

        return f"if {condition}:\n    {then_action}"

    def gen_create(self, node: Create) -> str:
        entity = node.entity
        lines = []

        # Generate ID and copy input_data
        lines.append(f"new_{entity} = {{'id': f'{entity.upper()}-{{len({self.state_var}.get(\"{entity}\", [])) + 1:03d}}', **{self.input_var}}}")

        # Add with values (override input_data if specified)
        for field, value_node in node.with_values.items():
            value = self.generate(value_node)
            lines.append(f"new_{entity}['{field}'] = {value}")

        # Add to state
        lines.append(f"if '{entity}' not in {self.state_var}: {self.state_var}['{entity}'] = []")
        lines.append(f"{self.state_var}['{entity}'].append(new_{entity})")

        # Return with newline separator (no extra indentation)
        return '\n'.join(lines)


def to_python(node: ASTNode, **kwargs) -> str:
    """ASTをPythonコードに変換"""
    gen = PythonGenerator(**kwargs)
    return gen.generate(node)


# ==================================================
# High-level API
# ==================================================

def parse_and_generate(expr: str, target='python', **kwargs) -> str:
    """式をパースしてコードを生成"""
    ast = parse(expr)

    if target == 'python':
        return to_python(ast, **kwargs)
    else:
        raise ValueError(f"Unknown target: {target}")


# ==================================================
# Tests
# ==================================================

def test_parser():
    """Basic parser tests"""

    test_cases = [
        # Literals
        ("100", "100"),
        ("'active'", "'active'"),
        ("true", "True"),
        ("null", "None"),

        # Field access
        ("entity.field", "entity.get('field')"),
        ("input.amount", "input_data.get('amount')"),

        # Binary operations
        ("a.x + b.y", "(a.get('x') + b.get('y'))"),
        ("entity.amount - input.value", "(entity.get('amount') - input_data.get('value'))"),

        # Comparisons
        ("entity.status == 'active'", "(entity.get('status') == 'active')"),
        ("entity.field != null", "(entity.get('field') is not None)"),
        ("value.x > 100", "(value.get('x') > 100)"),

        # Logical
        ("a.x == 1 and b.y == 2", "((a.get('x') == 1) and (b.get('y') == 2))"),
        ("not entity.deleted", "(not entity.get('deleted'))"),

        # Function calls
        ("today", "today()"),
        ("remaining(invoice)", "remaining(state, invoice)"),

        # Assignment
        ("entity.status = 'closed'", "entity['status'] = 'closed'"),
        ("task.status = input.new_status", "task['status'] = input_data.get('new_status')"),

        # Arithmetic assignment
        ("product.stock = product.stock - input.quantity",
         "product['stock'] = (product.get('stock') - input_data.get('quantity'))"),
    ]

    print("Testing expression parser...")
    passed = 0
    failed = 0

    for expr, expected in test_cases:
        try:
            result = parse_and_generate(expr)
            if result == expected:
                print(f"  PASS: {expr}")
                passed += 1
            else:
                print(f"  FAIL: {expr}")
                print(f"    Expected: {expected}")
                print(f"    Got:      {result}")
                failed += 1
        except Exception as e:
            print(f"  ERROR: {expr}")
            print(f"    {type(e).__name__}: {e}")
            failed += 1

    print(f"\nResults: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == '__main__':
    test_parser()
