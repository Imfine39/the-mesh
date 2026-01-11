"""Formula DSL Parser

人間が読める式をTRIR Expression ASTに変換する。

Examples:
    "self.quantity * self.unitPrice"
    "sum(items.quantity * items.unitPrice)"
    "if self.total >= 5000 then 0 else 500"
    "count(orders where orders.status = 'COMPLETED')"
"""

import re
from typing import Any
from dataclasses import dataclass


@dataclass
class ParseError(Exception):
    message: str
    position: int


class FormulaParser:
    """シンプルな式言語をTRIR式に変換"""

    # 演算子の優先順位
    PRECEDENCE = {
        'or': 1,
        'and': 2,
        '=': 3, '!=': 3, '<': 3, '<=': 3, '>': 3, '>=': 3, 'in': 3,
        '+': 4, '-': 4,
        '*': 5, '/': 5, '%': 5,
    }

    # TRIR演算子へのマッピング
    OP_MAP = {
        '+': 'add', '-': 'sub', '*': 'mul', '/': 'div', '%': 'mod',
        '=': 'eq', '!=': 'ne', '<': 'lt', '<=': 'le', '>': 'gt', '>=': 'ge',
        'and': 'and', 'or': 'or', 'in': 'in',
    }

    def __init__(self, formula: str):
        self.formula = formula
        self.pos = 0
        self.length = len(formula)

    def parse(self) -> dict[str, Any]:
        """式をパースしてTRIR Expression を返す"""
        self._skip_whitespace()
        result = self._parse_expression()
        self._skip_whitespace()
        if self.pos < self.length:
            raise ParseError(f"Unexpected character: {self.formula[self.pos]}", self.pos)
        return result

    def _parse_expression(self, min_precedence: int = 0) -> dict:
        """演算子優先順位パーサー"""
        left = self._parse_primary()

        while True:
            self._skip_whitespace()
            op = self._peek_operator()
            if op is None or self.PRECEDENCE.get(op, 0) < min_precedence:
                break

            self._consume_operator(op)
            right = self._parse_expression(self.PRECEDENCE[op] + 1)

            left = {
                "type": "binary",
                "op": self.OP_MAP[op],
                "left": left,
                "right": right,
            }

        return left

    def _parse_primary(self) -> dict:
        """プライマリ式（リテラル、参照、関数呼び出し、括弧）"""
        self._skip_whitespace()

        # 括弧
        if self._peek_char() == '(':
            self._consume_char('(')
            expr = self._parse_expression()
            self._skip_whitespace()
            self._consume_char(')')
            return expr

        # 数値リテラル
        if self._peek_char() and (self._peek_char().isdigit() or self._peek_char() == '-'):
            return self._parse_number()

        # 文字列リテラル
        if self._peek_char() in ('"', "'"):
            return self._parse_string()

        # リストリテラル
        if self._peek_char() == '[':
            return self._parse_list()

        # キーワードまたは識別子
        ident = self._parse_identifier()
        if not ident:
            raise ParseError(f"Expected expression at position {self.pos}", self.pos)

        # キーワードチェック
        if ident == 'if':
            return self._parse_if_expression()
        if ident == 'true':
            return {"type": "literal", "value": True}
        if ident == 'false':
            return {"type": "literal", "value": False}
        if ident == 'null':
            return {"type": "literal", "value": None}

        # 集約関数
        if ident in ('sum', 'count', 'avg', 'min', 'max', 'exists'):
            return self._parse_aggregation(ident)

        # 参照（self.field または entity.field）
        self._skip_whitespace()
        if self._peek_char() == '.':
            return self._parse_reference(ident)

        # 関数呼び出し
        if self._peek_char() == '(':
            return self._parse_function_call(ident)

        # 単純な識別子（入力参照として扱う）
        return {"type": "input", "name": ident}

    def _parse_number(self) -> dict:
        """数値リテラル"""
        start = self.pos
        if self._peek_char() == '-':
            self.pos += 1

        while self.pos < self.length and self.formula[self.pos].isdigit():
            self.pos += 1

        # 小数点
        if self.pos < self.length and self.formula[self.pos] == '.':
            self.pos += 1
            while self.pos < self.length and self.formula[self.pos].isdigit():
                self.pos += 1
            value = float(self.formula[start:self.pos])
        else:
            value = int(self.formula[start:self.pos])

        return {"type": "literal", "value": value}

    def _parse_string(self) -> dict:
        """文字列リテラル"""
        quote = self._consume_char()
        start = self.pos
        while self.pos < self.length and self.formula[self.pos] != quote:
            if self.formula[self.pos] == '\\':
                self.pos += 1
            self.pos += 1
        value = self.formula[start:self.pos]
        self._consume_char(quote)
        return {"type": "literal", "value": value}

    def _parse_list(self) -> dict:
        """リストリテラル [a, b, c]"""
        self._consume_char('[')
        items = []

        self._skip_whitespace()
        if self._peek_char() != ']':
            # 最初の要素
            items.append(self._parse_expression())

            # カンマ区切りで続く要素
            while True:
                self._skip_whitespace()
                if self._peek_char() != ',':
                    break
                self._consume_char(',')
                self._skip_whitespace()
                items.append(self._parse_expression())

        self._skip_whitespace()
        self._consume_char(']')
        return {"type": "list", "items": items}

    def _parse_identifier(self) -> str:
        """識別子"""
        start = self.pos
        while self.pos < self.length and (self.formula[self.pos].isalnum() or self.formula[self.pos] == '_'):
            self.pos += 1
        return self.formula[start:self.pos]

    def _parse_reference(self, first_part: str) -> dict:
        """参照 (self.field, entity.field, entity.field.nested)"""
        path_parts = [first_part]

        while self._peek_char() == '.':
            self._consume_char('.')
            part = self._parse_identifier()
            if not part:
                raise ParseError(f"Expected identifier after '.'", self.pos)
            path_parts.append(part)

        if path_parts[0] == 'self':
            # self.field -> SelfRef
            return {"type": "self", "field": ".".join(path_parts[1:])}
        else:
            # entity.field -> FieldRef
            return {"type": "ref", "path": ".".join(path_parts)}

    def _parse_aggregation(self, op: str) -> dict:
        """集約関数 sum(expr), count(entity), count(entity where condition)"""
        self._skip_whitespace()
        self._consume_char('(')
        self._skip_whitespace()

        # count(entity) or count(entity where ...)
        if op in ('count', 'exists'):
            source = self._parse_identifier()
            self._skip_whitespace()

            where_clause = None
            if self._peek_word() == 'where':
                self._consume_word('where')
                where_clause = self._parse_expression()

            self._skip_whitespace()
            self._consume_char(')')

            result = {
                "type": "agg",
                "op": op,
                "from": self._to_entity_name(source),
            }
            if where_clause:
                result["where"] = where_clause
            return result

        # sum/avg/min/max(expr) or sum(entity.field where ...)
        expr = self._parse_expression()
        self._skip_whitespace()

        where_clause = None
        if self._peek_word() == 'where':
            self._consume_word('where')
            where_clause = self._parse_expression()

        self._skip_whitespace()
        self._consume_char(')')

        # exprからsourceを推測
        source = self._infer_source(expr)

        result = {
            "type": "agg",
            "op": op,
            "from": source,
            "expr": expr,
        }
        if where_clause:
            result["where"] = where_clause
        return result

    def _parse_if_expression(self) -> dict:
        """if condition then expr else expr"""
        self._skip_whitespace()
        condition = self._parse_expression()

        self._skip_whitespace()
        self._consume_word('then')

        self._skip_whitespace()
        then_expr = self._parse_expression()

        self._skip_whitespace()
        self._consume_word('else')

        self._skip_whitespace()
        else_expr = self._parse_expression()

        return {
            "type": "if",
            "condition": condition,
            "then": then_expr,
            "else": else_expr,
        }

    def _parse_function_call(self, name: str) -> dict:
        """関数呼び出し func(args...)"""
        self._consume_char('(')
        args = []

        self._skip_whitespace()
        if self._peek_char() != ')':
            args.append(self._parse_expression())
            while self._peek_char() == ',':
                self._consume_char(',')
                self._skip_whitespace()
                args.append(self._parse_expression())

        self._skip_whitespace()
        self._consume_char(')')

        return {
            "type": "call",
            "function": name,
            "args": args,
        }

    def _infer_source(self, expr: dict) -> str:
        """式からソースエンティティを推測"""
        if expr.get("type") == "ref":
            path = expr.get("path", "")
            parts = path.split(".")
            if parts:
                return self._to_entity_name(parts[0])
        if expr.get("type") == "binary":
            left_source = self._infer_source(expr.get("left", {}))
            if left_source:
                return left_source
            return self._infer_source(expr.get("right", {}))
        return "Unknown"

    def _to_entity_name(self, name: str) -> str:
        """識別子をエンティティ名に変換 (items -> Item, orderItems -> OrderItem)"""
        # 複数形を単数形に
        if name.endswith('ies'):
            name = name[:-3] + 'y'
        elif name.endswith('s') and not name.endswith('ss'):
            name = name[:-1]
        # PascalCaseに
        return name[0].upper() + name[1:]

    def _skip_whitespace(self):
        while self.pos < self.length and self.formula[self.pos] in ' \t\n\r':
            self.pos += 1

    def _peek_char(self) -> str | None:
        return self.formula[self.pos] if self.pos < self.length else None

    def _consume_char(self, expected: str = None) -> str:
        if self.pos >= self.length:
            raise ParseError(f"Unexpected end of input", self.pos)
        char = self.formula[self.pos]
        if expected and char != expected:
            raise ParseError(f"Expected '{expected}' but got '{char}'", self.pos)
        self.pos += 1
        return char

    def _peek_word(self) -> str:
        """次の単語を覗く（消費しない）"""
        self._skip_whitespace()
        start = self.pos
        while self.pos < self.length and self.formula[self.pos].isalpha():
            self.pos += 1
        word = self.formula[start:self.pos]
        self.pos = start
        return word

    def _consume_word(self, expected: str):
        """期待する単語を消費"""
        self._skip_whitespace()
        word = self._parse_identifier()
        if word != expected:
            raise ParseError(f"Expected '{expected}' but got '{word}'", self.pos)

    def _peek_operator(self) -> str | None:
        """次の演算子を覗く"""
        self._skip_whitespace()

        # 2文字演算子
        if self.pos + 1 < self.length:
            two_char = self.formula[self.pos:self.pos + 2]
            if two_char in ('<=', '>=', '!='):
                return two_char

        # 1文字演算子
        if self.pos < self.length:
            one_char = self.formula[self.pos]
            if one_char in '+-*/%=<>':
                return one_char

        # キーワード演算子
        word = self._peek_word()
        if word in ('and', 'or', 'in'):
            return word

        return None

    def _consume_operator(self, op: str):
        """演算子を消費"""
        self._skip_whitespace()
        if op in ('and', 'or', 'in'):
            self._consume_word(op)
        else:
            for char in op:
                self._consume_char(char)


def parse_formula(formula: str) -> dict[str, Any]:
    """式をパースしてTRIR Expression を返す"""
    parser = FormulaParser(formula)
    return parser.parse()


# テスト用
if __name__ == "__main__":
    import json

    test_cases = [
        # 単純な算術
        "self.quantity * self.unitPrice",
        "self.price * 1.1",

        # 集約
        "sum(items.quantity * items.unitPrice)",
        "count(orderItems)",
        "avg(products.price)",

        # 条件
        "if self.total >= 5000 then 0 else 500",

        # 複合
        "sum(items.quantity) + 10",

        # where句
        "count(orders where orders.status = 'COMPLETED')",
        "sum(items.amount where items.type = 'SALE')",
    ]

    for formula in test_cases:
        print(f"\n{'='*60}")
        print(f"Formula: {formula}")
        print(f"{'='*60}")
        try:
            result = parse_formula(formula)
            print(json.dumps(result, indent=2))
        except ParseError as e:
            print(f"Error: {e.message} at position {e.position}")
