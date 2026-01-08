#!/usr/bin/env python3
"""Convert old expression format to tagged union format"""

import json
import sys
from pathlib import Path
from typing import Any


def convert_expr(expr: Any) -> Any:
    """Convert old expression format to tagged union"""
    if not isinstance(expr, dict):
        return expr

    # Already converted (has 'type' field)
    if "type" in expr:
        return expr

    # Literal: { "lit": value } -> { "type": "literal", "value": value }
    if "lit" in expr:
        return {"type": "literal", "value": expr["lit"]}

    # Field reference: { "ref": "path" } -> { "type": "ref", "path": "path" }
    if "ref" in expr and isinstance(expr["ref"], str):
        return {"type": "ref", "path": expr["ref"]}

    # Input reference: { "input": "name" } -> { "type": "input", "name": "name" }
    if "input" in expr and isinstance(expr["input"], str):
        return {"type": "input", "name": expr["input"]}

    # Self reference: { "self": "field" } -> { "type": "self", "field": "field" }
    if "self" in expr and isinstance(expr["self"], str):
        return {"type": "self", "field": expr["self"]}

    # Binary operation: { "op": "add", "left": ..., "right": ... }
    if "op" in expr and "left" in expr and "right" in expr:
        op_map = {
            "subtract": "sub", "multiply": "mul", "divide": "div", "modulo": "mod",
            "add": "add", "sub": "sub", "mul": "mul", "div": "div", "mod": "mod",
            "eq": "eq", "ne": "ne", "lt": "lt", "le": "le", "gt": "gt", "ge": "ge",
            "and": "and", "or": "or", "in": "in", "not_in": "not_in",
            "like": "like", "not_like": "not_like"
        }
        return {
            "type": "binary",
            "op": op_map.get(expr["op"], expr["op"]),
            "left": convert_expr(expr["left"]),
            "right": convert_expr(expr["right"])
        }

    # Unary operation: { "op": "not", "expr": ... }
    if "op" in expr and "expr" in expr and "left" not in expr:
        op_map = {
            "not": "not", "negate": "neg",
            "is_null": "is_null", "is_not_null": "is_not_null"
        }
        return {
            "type": "unary",
            "op": op_map.get(expr["op"], expr["op"]),
            "expr": convert_expr(expr["expr"])
        }

    # Aggregation: { "agg": "sum", "from": ..., ... }
    if "agg" in expr:
        result = {
            "type": "agg",
            "op": expr["agg"],
            "from": expr["from"]
        }
        if "as" in expr:
            result["as"] = expr["as"]
        if "expr" in expr:
            result["expr"] = convert_expr(expr["expr"])
        if "where" in expr:
            result["where"] = convert_expr(expr["where"])
        return result

    # Function call: { "call": "name", "args": [...] }
    if "call" in expr:
        result = {
            "type": "call",
            "name": expr["call"]
        }
        if "args" in expr:
            result["args"] = [convert_expr(a) for a in expr["args"]]
        return result

    # If-then-else: { "if": ..., "then": ..., "else": ... }
    if "if" in expr and "then" in expr:
        return {
            "type": "if",
            "cond": convert_expr(expr["if"]),
            "then": convert_expr(expr["then"]),
            "else": convert_expr(expr.get("else", {"type": "literal", "value": None}))
        }

    # Case expression: { "case": [...], "else": ... }
    if "case" in expr:
        return {
            "type": "case",
            "branches": [
                {"when": convert_expr(c["when"]), "then": convert_expr(c["then"])}
                for c in expr["case"]
            ],
            "else": convert_expr(expr.get("else", {"type": "literal", "value": None}))
        }

    # Date operation: { "date_op": "diff", ... }
    if "date_op" in expr:
        result = {
            "type": "date",
            "op": expr["date_op"]
        }
        if "args" in expr:
            result["args"] = [convert_expr(a) for a in expr["args"]]
        if "unit" in expr:
            result["unit"] = expr["unit"]
        return result

    # List operation: { "list_op": "contains", ... }
    if "list_op" in expr:
        result = {
            "type": "list",
            "op": expr["list_op"],
            "list": convert_expr(expr["list"])
        }
        if "args" in expr:
            result["args"] = [convert_expr(a) for a in expr["args"]]
        return result

    # Unknown format - return as is with warning
    print(f"  Warning: Unknown expression format: {expr}", file=sys.stderr)
    return expr


def convert_spec(spec: dict) -> dict:
    """Convert all expressions in a spec"""
    result = dict(spec)

    # Convert derived formulas
    if "derived" in result:
        for name, derived in result["derived"].items():
            if "formula" in derived:
                derived["formula"] = convert_expr(derived["formula"])

    # Convert functions
    if "functions" in result:
        for name, func in result["functions"].items():
            # Pre conditions
            if "pre" in func:
                for pre in func["pre"]:
                    if "expr" in pre:
                        pre["expr"] = convert_expr(pre["expr"])

            # Error cases
            if "error" in func:
                for err in func["error"]:
                    if "when" in err:
                        err["when"] = convert_expr(err["when"])

            # Post actions
            if "post" in func:
                for post in func["post"]:
                    if "condition" in post:
                        post["condition"] = convert_expr(post["condition"])
                    if "action" in post:
                        action = post["action"]
                        if "with" in action:
                            action["with"] = {
                                k: convert_expr(v) for k, v in action["with"].items()
                            }
                        if "set" in action:
                            action["set"] = {
                                k: convert_expr(v) for k, v in action["set"].items()
                            }
                        if "where" in action:
                            action["where"] = convert_expr(action["where"])

    # Convert scenarios
    if "scenarios" in result:
        for name, scenario in result["scenarios"].items():
            if "then" in scenario and "assert" in scenario["then"]:
                scenario["then"]["assert"] = [
                    convert_expr(a) for a in scenario["then"]["assert"]
                ]

    # Convert invariants
    if "invariants" in result:
        for inv in result["invariants"]:
            if "expr" in inv:
                inv["expr"] = convert_expr(inv["expr"])

    return result


def main():
    if len(sys.argv) < 2:
        print("Usage: convert_to_tagged.py <spec.json> [output.json]")
        print("       If no output specified, writes to stdout")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else None

    with open(input_path) as f:
        spec = json.load(f)

    converted = convert_spec(spec)

    if output_path:
        with open(output_path, "w") as f:
            json.dump(converted, f, indent=2, ensure_ascii=False)
        print(f"Converted: {input_path} -> {output_path}")
    else:
        print(json.dumps(converted, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
