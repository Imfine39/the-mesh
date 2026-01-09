"""Tests for Jest Generator"""

import json
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from the_mesh.generators.jest_gen import JestGenerator


# Sample spec for testing
SAMPLE_SPEC = {
    "meta": {
        "id": "test-system",
        "title": "Test System",
        "version": "1.0.0"
    },
    "state": {
        "invoice": {
            "description": "Invoice entity",
            "fields": {
                "invoice_id": {"type": "string", "required": True},
                "customer_code": {"type": {"ref": "customer"}, "required": True},
                "amount": {"type": "int", "required": True},
                "status": {"type": {"enum": ["OPEN", "CLOSED"]}, "required": True}
            }
        },
        "customer": {
            "description": "Customer entity",
            "fields": {
                "customer_code": {"type": "string", "required": True},
                "name": {"type": "string", "required": True}
            }
        }
    },
    "derived": {
        "outstanding_amount": {
            "entity": "invoice",
            "description": "Calculate outstanding amount",
            "formula": {
                "type": "binary",
                "op": "sub",
                "left": {"type": "self", "field": "amount"},
                "right": {"type": "literal", "value": 0}
            }
        }
    },
    "functions": {
        "create_invoice": {
            "description": "Create a new invoice",
            "input": {
                "customer_code": {"type": "string"},
                "amount": {"type": "int"}
            },
            "pre": [],
            "post": [
                {"action": {"create": "invoice"}}
            ]
        },
        "close_invoice": {
            "description": "Close an invoice",
            "input": {
                "invoice_id": {"type": "string"}
            },
            "pre": [
                {"check": {"type": "binary", "op": "eq",
                          "left": {"type": "ref", "path": "invoice.status"},
                          "right": {"type": "literal", "value": "OPEN"}}}
            ],
            "post": [
                {"action": {"update": "invoice"}}
            ]
        }
    },
    "scenarios": {
        "SC-001": {
            "title": "Create invoice for existing customer",
            "given": {
                "customer": {"customer_code": "CUST-001", "name": "Test Customer"}
            },
            "when": {
                "call": "create_invoice",
                "input": {"customer_code": "CUST-001", "amount": 10000}
            },
            "then": {
                "success": True,
                "assert": [
                    {"type": "binary", "op": "eq",
                     "left": {"type": "ref", "path": "result.status"},
                     "right": {"type": "literal", "value": "OPEN"}}
                ]
            }
        },
        "SC-002": {
            "title": "Close an open invoice",
            "given": {
                "invoice": {"invoice_id": "INV-001", "amount": 10000, "status": "OPEN"}
            },
            "when": {
                "call": "close_invoice",
                "input": {"invoice_id": "INV-001"}
            },
            "then": {
                "success": True
            }
        }
    },
    "invariants": [
        {
            "id": "INV-001",
            "entity": "invoice",
            "description": "Invoice amount must be positive",
            "expr": {
                "type": "binary",
                "op": "gt",
                "left": {"type": "self", "field": "amount"},
                "right": {"type": "literal", "value": 0}
            }
        }
    ]
}


def test_jest_generator_basic():
    """Test basic Jest generator instantiation"""
    gen = JestGenerator(SAMPLE_SPEC)
    assert gen.entities == SAMPLE_SPEC["state"]
    assert gen.scenarios == SAMPLE_SPEC["scenarios"]


def test_generate_all_javascript():
    """Test generating all tests in JavaScript"""
    gen = JestGenerator(SAMPLE_SPEC, typescript=False)
    code = gen.generate_all()

    # Should contain JavaScript imports style (not TypeScript)
    assert "// TODO: Import your implementation modules" in code
    assert "import { describe, test, expect" not in code  # No TS imports

    # Should contain describe blocks
    assert "describe('create_invoice'" in code
    assert "describe('close_invoice'" in code

    # Should contain test cases
    assert "test('SC_001:" in code
    assert "test('SC_002:" in code

    # Should contain factory functions
    assert "function createInvoice(overrides" in code
    assert "function createCustomer(overrides" in code

    # Should contain invariant tests
    assert "describe('Invariants'" in code
    assert "test('INVARIANT_INV_001:" in code


def test_generate_all_typescript():
    """Test generating all tests in TypeScript"""
    gen = JestGenerator(SAMPLE_SPEC, typescript=True)
    code = gen.generate_all()

    # Should contain TypeScript imports
    assert "import { describe, test, expect, beforeEach } from '@jest/globals'" in code

    # Should contain type definitions
    assert "interface Invoice {" in code
    assert "interface Customer {" in code

    # Should have typed function signatures
    assert "function createInvoice(overrides: Partial<Invoice>" in code


def test_generate_for_function():
    """Test generating tests for a specific function"""
    gen = JestGenerator(SAMPLE_SPEC, typescript=False)
    code = gen.generate_for_function("close_invoice")

    # Should only contain tests for close_invoice
    assert "SC_002" in code
    assert "SC_001" not in code  # This is for create_invoice

    # Should still have factory functions
    assert "createInvoice" in code


def test_expression_to_js_literal():
    """Test expression conversion - literals"""
    gen = JestGenerator(SAMPLE_SPEC)

    expr = {"type": "literal", "value": 100}
    assert gen._expr_to_js(expr) == "100"

    expr = {"type": "literal", "value": "test"}
    assert gen._expr_to_js(expr) == "'test'"

    expr = {"type": "literal", "value": True}
    assert gen._expr_to_js(expr) == "true"

    expr = {"type": "literal", "value": None}
    assert gen._expr_to_js(expr) == "null"


def test_expression_to_js_binary():
    """Test expression conversion - binary operations"""
    gen = JestGenerator(SAMPLE_SPEC)

    # Equality
    expr = {
        "type": "binary", "op": "eq",
        "left": {"type": "ref", "path": "invoice.amount"},
        "right": {"type": "literal", "value": 100}
    }
    result = gen._expr_to_js(expr)
    assert "===" in result
    assert "100" in result

    # Addition
    expr = {
        "type": "binary", "op": "add",
        "left": {"type": "literal", "value": 10},
        "right": {"type": "literal", "value": 20}
    }
    result = gen._expr_to_js(expr)
    assert "(10 + 20)" in result

    # Logical and
    expr = {
        "type": "binary", "op": "and",
        "left": {"type": "literal", "value": True},
        "right": {"type": "literal", "value": False}
    }
    result = gen._expr_to_js(expr)
    assert "&&" in result


def test_expression_to_js_unary():
    """Test expression conversion - unary operations"""
    gen = JestGenerator(SAMPLE_SPEC)

    # Not
    expr = {"type": "unary", "op": "not", "expr": {"type": "literal", "value": True}}
    assert "!" in gen._expr_to_js(expr)

    # is_null
    expr = {"type": "unary", "op": "is_null", "expr": {"type": "ref", "path": "x"}}
    assert "== null" in gen._expr_to_js(expr)


def test_expression_to_js_aggregation():
    """Test expression conversion - aggregation"""
    gen = JestGenerator(SAMPLE_SPEC)

    # Sum
    expr = {
        "type": "agg", "op": "sum", "from": "items",
        "expr": {"type": "ref", "path": "item.amount"}
    }
    result = gen._expr_to_js(expr)
    assert ".reduce(" in result
    assert "amount" in result

    # Count
    expr = {"type": "agg", "op": "count", "from": "items"}
    result = gen._expr_to_js(expr)
    assert ".length" in result


def test_expression_to_js_conditional():
    """Test expression conversion - if/case"""
    gen = JestGenerator(SAMPLE_SPEC)

    # If-then-else
    expr = {
        "type": "if",
        "cond": {"type": "literal", "value": True},
        "then": {"type": "literal", "value": "yes"},
        "else": {"type": "literal", "value": "no"}
    }
    result = gen._expr_to_js(expr)
    assert "?" in result
    assert ":" in result
    assert "'yes'" in result
    assert "'no'" in result


def test_type_conversions():
    """Test TypeScript type conversions"""
    gen = JestGenerator(SAMPLE_SPEC, typescript=True)

    assert gen._get_ts_type({"type": "string"}) == "string"
    assert gen._get_ts_type({"type": "int"}) == "number"
    assert gen._get_ts_type({"type": "float"}) == "number"
    assert gen._get_ts_type({"type": "bool"}) == "boolean"

    # Enum
    assert "'OPEN' | 'CLOSED'" in gen._get_ts_type({"type": {"enum": ["OPEN", "CLOSED"]}})

    # List
    assert "number[]" in gen._get_ts_type({"type": {"list": "int"}})


def test_case_conversions():
    """Test case conversion utilities"""
    gen = JestGenerator(SAMPLE_SPEC)

    assert gen._to_pascal_case("invoice_item") == "InvoiceItem"
    assert gen._to_camel_case("invoice_item") == "invoiceItem"
    assert gen._to_camel_case("close_invoice") == "closeInvoice"


def test_default_values():
    """Test default value generation"""
    gen = JestGenerator(SAMPLE_SPEC)

    assert "'STRING-001'" in gen._get_default_value("string", {"type": "string"})
    assert "0" == gen._get_default_value("amount", {"type": "int"})
    assert "false" == gen._get_default_value("active", {"type": "bool"})
    assert "'OPEN'" in gen._get_default_value("status", {"type": {"enum": ["OPEN", "CLOSED"]}})


def test_with_real_spec():
    """Test with real AR clearing spec if available"""
    spec_path = Path(__file__).parent.parent / "examples" / "ar_clearing_extended.mesh.json"
    if not spec_path.exists():
        return  # Skip if file doesn't exist

    with open(spec_path) as f:
        spec = json.load(f)

    # Test JavaScript generation
    gen_js = JestGenerator(spec, typescript=False)
    code_js = gen_js.generate_all()
    assert len(code_js) > 1000  # Should generate substantial code
    assert "describe(" in code_js
    assert "test(" in code_js

    # Test TypeScript generation
    gen_ts = JestGenerator(spec, typescript=True)
    code_ts = gen_ts.generate_all()
    assert "interface" in code_ts
    assert len(code_ts) > len(code_js)  # TS should be longer due to types


# Run tests if executed directly
if __name__ == "__main__":
    import traceback

    tests = [
        test_jest_generator_basic,
        test_generate_all_javascript,
        test_generate_all_typescript,
        test_generate_for_function,
        test_expression_to_js_literal,
        test_expression_to_js_binary,
        test_expression_to_js_unary,
        test_expression_to_js_aggregation,
        test_expression_to_js_conditional,
        test_type_conversions,
        test_case_conversions,
        test_default_values,
        test_with_real_spec,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            print(f"PASSED: {test.__name__}")
            passed += 1
        except Exception as e:
            print(f"FAILED: {test.__name__}")
            traceback.print_exc()
            failed += 1

    print(f"\nResults: {passed} passed, {failed} failed")
