"""Tests for Jest Generator - Repository Pattern"""

import json
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from the_mesh.generators.typescript.jest_gen import JestGenerator


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
    """Test generating all tests in JavaScript (Repository pattern)"""
    gen = JestGenerator(SAMPLE_SPEC, typescript=False)
    code = gen.generate_all()

    # Should contain describe blocks
    assert "describe('create_invoice'" in code
    assert "describe('close_invoice'" in code

    # Should contain mock factories (Repository pattern)
    assert "createMock" in code
    assert "Repository" in code
    assert "jest.fn()" in code

    # Should contain entity factories
    assert "createinvoice" in code.lower() or "createInvoice" in code

    # Should contain invariant tests
    assert "describe('Invariants'" in code


def test_generate_all_typescript():
    """Test generating all tests in TypeScript (Repository pattern)"""
    gen = JestGenerator(SAMPLE_SPEC, typescript=True)
    code = gen.generate_all()

    # Should contain TypeScript imports
    assert "import { describe, it, expect" in code

    # Should contain repository interfaces
    assert "interface" in code
    assert "Repository" in code

    # Should have typed function signatures
    assert ": string" in code or ": Partial<" in code


def test_generate_for_function():
    """Test generating tests for a specific function"""
    gen = JestGenerator(SAMPLE_SPEC, typescript=False)
    code = gen.generate_for_function("close_invoice")

    # Should only contain tests for close_invoice scenarios
    assert "close_invoice" in code

    # Should have mock repository
    assert "createMock" in code


def test_mock_repository_structure():
    """Test that mock repositories have correct structure"""
    gen = JestGenerator(SAMPLE_SPEC, typescript=True)
    code = gen.generate_all()

    # Repository should have CRUD methods
    assert "create: jest.fn()" in code
    assert "get: jest.fn()" in code
    assert "update: jest.fn()" in code
    assert "delete: jest.fn()" in code

    # Should have _setData helper for test setup
    assert "_setData" in code


def test_scenario_test_structure():
    """Test that scenario tests follow Given/When/Then structure"""
    gen = JestGenerator(SAMPLE_SPEC, typescript=False)
    code = gen.generate_all()

    # Should have Given section
    assert "// Given" in code

    # Should have When section
    assert "// When" in code

    # Should have Then section
    assert "// Then" in code


def test_typescript_repository_interfaces():
    """Test TypeScript repository interface generation"""
    gen = JestGenerator(SAMPLE_SPEC, typescript=True)
    code = gen.generate_all()

    # Should have interface definitions
    assert "interface" in code

    # Should have Promise return types
    assert "Promise<" in code


def test_expression_to_pseudo():
    """Test expression to pseudo code conversion for comments"""
    gen = JestGenerator(SAMPLE_SPEC)

    # Test literal
    expr = {"type": "literal", "value": 100}
    result = gen._expr_to_pseudo(expr)
    assert "100" in result

    # Test ref
    expr = {"type": "ref", "path": "invoice.amount"}
    result = gen._expr_to_pseudo(expr)
    assert "invoice.amount" in result

    # Test binary
    expr = {
        "type": "binary", "op": "eq",
        "left": {"type": "ref", "path": "x"},
        "right": {"type": "literal", "value": 100}
    }
    result = gen._expr_to_pseudo(expr)
    assert "eq" in result


def test_to_js_value():
    """Test Python to JavaScript value conversion"""
    gen = JestGenerator(SAMPLE_SPEC)

    # Test primitives
    assert gen._to_js_value(100) == "100"
    assert gen._to_js_value("test") == '"test"'
    assert gen._to_js_value(True) == "true"
    assert gen._to_js_value(False) == "false"
    assert gen._to_js_value(None) == "null"

    # Test dict
    result = gen._to_js_value({"key": "value"})
    assert "key:" in result
    assert '"value"' in result

    # Test list
    result = gen._to_js_value([1, 2, 3])
    assert "[1, 2, 3]" == result


def test_case_conversions():
    """Test case conversion utilities"""
    gen = JestGenerator(SAMPLE_SPEC)

    # _to_pascal
    assert gen._to_pascal("invoice_item") == "InvoiceItem"
    assert gen._to_pascal("customer") == "Customer"

    # _to_camel
    assert gen._to_camel("invoice_item") == "invoiceItem"
    assert gen._to_camel("close_invoice") == "closeInvoice"


def test_default_values():
    """Test default value generation for entity factories"""
    gen = JestGenerator(SAMPLE_SPEC)

    # These should be present in generated entity factory
    code = gen.generate_all()

    # String fields should have placeholder values
    assert "001" in code  # Default ID pattern


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
    assert "it(" in code_js  # Uses it() for tests

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
        test_mock_repository_structure,
        test_scenario_test_structure,
        test_typescript_repository_interfaces,
        test_expression_to_pseudo,
        test_to_js_value,
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
