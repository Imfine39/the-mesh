"""Tests for OpenAPI Generator"""

import json
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from generators.openapi_gen import OpenAPIGenerator


# Sample spec for testing
SAMPLE_SPEC = {
    "meta": {
        "id": "test-api",
        "title": "Test API",
        "version": "1.0.0",
        "description": "A test API"
    },
    "entities": {
        "invoice": {
            "description": "Invoice entity",
            "fields": {
                "id": {"type": "string", "required": True},
                "customer_id": {"type": {"ref": "customer"}, "required": True},
                "amount": {"type": "int", "required": True},
                "status": {"type": {"enum": ["open", "closed", "cancelled"]}, "required": True},
                "tags": {"type": {"list": "string"}, "required": False}
            }
        },
        "customer": {
            "description": "Customer entity",
            "fields": {
                "id": {"type": "string", "required": True},
                "name": {"type": "string", "required": True}
            }
        }
    },
    "commands": {
        "create_invoice": {
            "description": "Create a new invoice",
            "input": {
                "customer_id": {"type": "string", "required": True},
                "amount": {"type": "int", "required": True}
            },
            "output": {
                "invoice_id": {"type": "string", "required": True},
                "success": {"type": "bool", "required": True}
            },
            "error": [
                {"code": "CUSTOMER_NOT_FOUND", "when": {}, "reason": "Customer not found", "http_status": 404},
                {"code": "INVALID_AMOUNT", "when": {}, "reason": "Amount must be positive", "http_status": 400}
            ],
            "post": [
                {"action": {"create": "invoice"}}
            ]
        },
        "close_invoice": {
            "description": "Close an invoice",
            "input": {
                "invoice_id": {"type": "string", "required": True}
            },
            "error": [
                {"code": "INVOICE_NOT_FOUND", "when": {}, "reason": "Invoice not found", "http_status": 404},
                {"code": "ALREADY_CLOSED", "when": {}, "reason": "Already closed", "http_status": 409}
            ]
        }
    }
}


class TestOpenAPIGenerator:
    """Test OpenAPI schema generation"""

    def test_generate_basic_structure(self):
        """Test that basic OpenAPI structure is generated"""
        gen = OpenAPIGenerator(SAMPLE_SPEC)
        result = gen.generate()

        assert result["openapi"] == "3.1.0"
        assert "info" in result
        assert "paths" in result
        assert "components" in result

    def test_info_from_meta(self):
        """Test info section is populated from spec meta"""
        gen = OpenAPIGenerator(SAMPLE_SPEC)
        result = gen.generate()

        info = result["info"]
        assert info["title"] == "Test API"
        assert info["version"] == "1.0.0"
        assert info["description"] == "A test API"

    def test_paths_from_functions(self):
        """Test paths are generated from functions"""
        gen = OpenAPIGenerator(SAMPLE_SPEC)
        result = gen.generate()

        paths = result["paths"]
        assert "/create-invoice" in paths
        assert "/close-invoice" in paths

    def test_path_operation(self):
        """Test path operation structure"""
        gen = OpenAPIGenerator(SAMPLE_SPEC)
        result = gen.generate()

        path = result["paths"]["/create-invoice"]
        assert "post" in path

        operation = path["post"]
        assert operation["operationId"] == "create_invoice"
        assert operation["summary"] == "Create a new invoice"
        assert "requestBody" in operation
        assert "responses" in operation

    def test_request_body_schema(self):
        """Test request body schema generation"""
        gen = OpenAPIGenerator(SAMPLE_SPEC)
        result = gen.generate()

        path = result["paths"]["/create-invoice"]
        req_body = path["post"]["requestBody"]

        assert req_body["required"] is True

        schema = req_body["content"]["application/json"]["schema"]
        assert schema["type"] == "object"
        assert "customer_id" in schema["properties"]
        assert "amount" in schema["properties"]
        assert "customer_id" in schema["required"]
        assert "amount" in schema["required"]

    def test_response_with_output(self):
        """Test success response with output schema"""
        gen = OpenAPIGenerator(SAMPLE_SPEC)
        result = gen.generate()

        path = result["paths"]["/create-invoice"]
        responses = path["post"]["responses"]

        assert "200" in responses
        success_resp = responses["200"]
        schema = success_resp["content"]["application/json"]["schema"]

        assert "invoice_id" in schema["properties"]
        assert "success" in schema["properties"]

    def test_response_without_output(self):
        """Test success response without output definition"""
        gen = OpenAPIGenerator(SAMPLE_SPEC)
        result = gen.generate()

        path = result["paths"]["/close-invoice"]
        responses = path["post"]["responses"]

        assert "200" in responses
        schema = responses["200"]["content"]["application/json"]["schema"]
        assert schema["properties"]["success"]["const"] is True

    def test_error_responses(self):
        """Test error responses are generated"""
        gen = OpenAPIGenerator(SAMPLE_SPEC)
        result = gen.generate()

        path = result["paths"]["/create-invoice"]
        responses = path["post"]["responses"]

        # Check 404 response (CUSTOMER_NOT_FOUND)
        assert "404" in responses
        error_schema = responses["404"]["content"]["application/json"]["schema"]
        assert "CUSTOMER_NOT_FOUND" in error_schema["properties"]["error"]["enum"]

        # Check 400 response (INVALID_AMOUNT)
        assert "400" in responses

    def test_component_schemas(self):
        """Test component schemas from entities"""
        gen = OpenAPIGenerator(SAMPLE_SPEC)
        result = gen.generate()

        schemas = result["components"]["schemas"]
        assert "Invoice" in schemas
        assert "Customer" in schemas
        assert "ErrorResponse" in schemas

    def test_entity_schema_structure(self):
        """Test entity schema structure"""
        gen = OpenAPIGenerator(SAMPLE_SPEC)
        result = gen.generate()

        invoice_schema = result["components"]["schemas"]["Invoice"]
        assert invoice_schema["type"] == "object"
        assert "id" in invoice_schema["properties"]
        assert "amount" in invoice_schema["properties"]
        assert invoice_schema["description"] == "Invoice entity"

    def test_type_conversions(self):
        """Test TRIR type to OpenAPI type conversions"""
        gen = OpenAPIGenerator(SAMPLE_SPEC)
        result = gen.generate()

        invoice_schema = result["components"]["schemas"]["Invoice"]
        props = invoice_schema["properties"]

        # String
        assert props["id"]["type"] == "string"

        # Integer
        assert props["amount"]["type"] == "integer"

        # Enum
        assert props["status"]["type"] == "string"
        assert props["status"]["enum"] == ["open", "closed", "cancelled"]

        # Reference
        assert props["customer_id"]["type"] == "string"
        assert "Reference to Customer" in props["customer_id"]["description"]

        # List
        assert props["tags"]["type"] == "array"
        assert props["tags"]["items"]["type"] == "string"

    def test_custom_base_url(self):
        """Test custom base URL"""
        gen = OpenAPIGenerator(SAMPLE_SPEC, base_url="/api/v2")
        result = gen.generate()

        assert result["servers"][0]["url"] == "/api/v2"

    def test_tags_from_entity(self):
        """Test operation tags from primary entity"""
        gen = OpenAPIGenerator(SAMPLE_SPEC)
        result = gen.generate()

        # create_invoice has post action creating invoice
        path = result["paths"]["/create-invoice"]
        assert "invoice" in path["post"]["tags"]


class TestOpenAPIGeneratorEdgeCases:
    """Test edge cases for OpenAPI generator"""

    def test_empty_spec(self):
        """Test with empty spec"""
        gen = OpenAPIGenerator({})
        result = gen.generate()

        assert result["openapi"] == "3.1.0"
        assert result["paths"] == {}
        assert "ErrorResponse" in result["components"]["schemas"]

    def test_function_no_input(self):
        """Test function without input"""
        spec = {
            "commands": {
                "get_status": {
                    "description": "Get status",
                    "output": {
                        "status": {"type": "string", "required": True}
                    }
                }
            }
        }
        gen = OpenAPIGenerator(spec)
        result = gen.generate()

        path = result["paths"]["/get-status"]
        assert "requestBody" not in path["post"]

    def test_multiple_errors_same_status(self):
        """Test multiple errors with same HTTP status"""
        spec = {
            "commands": {
                "test_func": {
                    "input": {"id": {"type": "string"}},
                    "error": [
                        {"code": "ERROR_A", "http_status": 400},
                        {"code": "ERROR_B", "http_status": 400}
                    ]
                }
            }
        }
        gen = OpenAPIGenerator(spec)
        result = gen.generate()

        path = result["paths"]["/test-func"]
        error_schema = path["post"]["responses"]["400"]["content"]["application/json"]["schema"]

        # Both error codes should be in the enum
        assert "ERROR_A" in error_schema["properties"]["error"]["enum"]
        assert "ERROR_B" in error_schema["properties"]["error"]["enum"]

    def test_datetime_type(self):
        """Test datetime type conversion"""
        spec = {
            "entities": {
                "event": {
                    "fields": {
                        "created_at": {"type": "datetime", "required": True}
                    }
                }
            }
        }
        gen = OpenAPIGenerator(spec)
        result = gen.generate()

        schema = result["components"]["schemas"]["Event"]
        assert schema["properties"]["created_at"]["type"] == "string"
        assert schema["properties"]["created_at"]["format"] == "date-time"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
