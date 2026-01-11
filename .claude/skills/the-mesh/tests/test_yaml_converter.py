"""Tests for YAML to TRIR converter."""

import json
from pathlib import Path

import pytest
import yaml

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from converter import YAMLToTRIRConverter


class TestYAMLToTRIRConverter:
    """Tests for the YAMLToTRIRConverter class."""

    @pytest.fixture
    def converter(self):
        """Create a converter instance."""
        return YAMLToTRIRConverter()

    def test_convert_meta(self, converter):
        """Test meta section conversion."""
        yaml_spec = {
            "meta": {
                "id": "test-spec",
                "title": "Test Spec",
                "version": "1.0.0"
            },
            "entities": {}
        }
        result = converter.convert(yaml_spec)
        assert result["meta"]["id"] == "test-spec"
        assert result["meta"]["title"] == "Test Spec"
        assert result["meta"]["version"] == "1.0.0"

    def test_convert_entity_basic_types(self, converter):
        """Test entity field type conversion."""
        yaml_spec = {
            "entities": {
                "Product": {
                    "fields": {
                        "id": {"type": "id"},
                        "name": {"type": "string", "required": True},
                        "price": {"type": "money", "min": 0},
                        "stock": {"type": "count"},
                        "active": {"type": "bool"}
                    }
                }
            }
        }
        result = converter.convert(yaml_spec)
        product = result["entities"]["Product"]

        assert product["fields"]["id"]["type"] == "string"
        assert product["fields"]["id"]["preset"] == "id"

        assert product["fields"]["name"]["type"] == "string"
        assert product["fields"]["name"]["required"] is True

        assert product["fields"]["price"]["type"] == "float"
        assert product["fields"]["price"]["preset"] == "money"
        assert product["fields"]["price"]["min"] == 0

        assert product["fields"]["stock"]["type"] == "int"
        assert product["fields"]["stock"]["preset"] == "count"

        assert product["fields"]["active"]["type"] == "bool"

    def test_convert_entity_enum_type(self, converter):
        """Test enum field type conversion."""
        yaml_spec = {
            "entities": {
                "Order": {
                    "fields": {
                        "status": {"type": "enum", "values": ["PENDING", "CONFIRMED", "CANCELLED"]}
                    }
                }
            }
        }
        result = converter.convert(yaml_spec)
        status_field = result["entities"]["Order"]["fields"]["status"]
        assert status_field["type"] == {"enum": ["PENDING", "CONFIRMED", "CANCELLED"]}

    def test_convert_entity_ref_type(self, converter):
        """Test ref field type conversion."""
        yaml_spec = {
            "entities": {
                "OrderItem": {
                    "fields": {
                        "orderId": {"type": "ref", "ref": "Order"}
                    }
                }
            }
        }
        result = converter.convert(yaml_spec)
        order_id_field = result["entities"]["OrderItem"]["fields"]["orderId"]
        assert order_id_field["type"] == {"ref": "Order"}

    def test_convert_entity_aggregate_root(self, converter):
        """Test aggregateRoot flag conversion."""
        yaml_spec = {
            "entities": {
                "Order": {
                    "aggregateRoot": True,
                    "fields": {"id": {"type": "id"}}
                },
                "OrderItem": {
                    "aggregateRoot": False,
                    "parent": "Order",
                    "fields": {"id": {"type": "id"}}
                }
            }
        }
        result = converter.convert(yaml_spec)
        assert result["entities"]["Order"]["aggregateRoot"] is True
        assert "aggregateRoot" not in result["entities"]["OrderItem"]
        assert result["entities"]["OrderItem"]["parent"] == "Order"

    def test_convert_simple_expression(self, converter):
        """Test Level 1 simple expression conversion."""
        yaml_spec = {
            "entities": {"Product": {"fields": {"stock": {"type": "count"}}}},
            "invariants": [{
                "id": "positive_stock",
                "entity": "Product",
                "expr": {
                    "field": "self:stock",
                    "op": ">=",
                    "value": 0
                }
            }]
        }
        result = converter.convert(yaml_spec)
        expr = result["invariants"][0]["expr"]
        assert expr["type"] == "binary"
        assert expr["op"] == "ge"
        assert expr["left"]["type"] == "ref"
        assert expr["left"]["path"] == "stock"
        assert expr["right"]["type"] == "literal"
        assert expr["right"]["value"] == 0

    def test_convert_compound_expression_and(self, converter):
        """Test Level 2 AND expression conversion."""
        yaml_spec = {
            "entities": {"Product": {"fields": {"price": {"type": "money"}, "stock": {"type": "count"}}}},
            "invariants": [{
                "id": "valid_product",
                "entity": "Product",
                "expr": {
                    "and": [
                        {"field": "self:price", "op": ">", "value": 0},
                        {"field": "self:stock", "op": ">=", "value": 0}
                    ]
                }
            }]
        }
        result = converter.convert(yaml_spec)
        expr = result["invariants"][0]["expr"]
        assert expr["type"] == "binary"
        assert expr["op"] == "and"
        assert expr["left"]["type"] == "binary"
        assert expr["left"]["op"] == "gt"
        assert expr["right"]["type"] == "binary"
        assert expr["right"]["op"] == "ge"

    def test_convert_raw_trir_expression(self, converter):
        """Test Level 3 raw TRIR expression passthrough."""
        raw_expr = {
            "type": "agg",
            "op": "sum",
            "from": "OrderItem",
            "select": {"type": "ref", "path": "quantity"}
        }
        yaml_spec = {
            "entities": {"Order": {"fields": {"total": {"type": "money"}}}},
            "invariants": [{
                "id": "total_check",
                "entity": "Order",
                "expr": {"expr": raw_expr}
            }]
        }
        result = converter.convert(yaml_spec)
        expr = result["invariants"][0]["expr"]
        assert expr == raw_expr

    def test_convert_state_machine(self, converter):
        """Test state machine conversion."""
        yaml_spec = {
            "entities": {"Order": {"fields": {"status": {"type": "enum", "values": ["PENDING", "CONFIRMED"]}}}},
            "stateMachines": {
                "OrderFlow": {
                    "entity": "Order",
                    "field": "status",
                    "initial": "PENDING",
                    "states": {
                        "PENDING": {"description": "Pending order"},
                        "CONFIRMED": {"description": "Confirmed", "final": True}
                    },
                    "transitions": [
                        {
                            "id": "confirm",
                            "from": "PENDING",
                            "to": "CONFIRMED",
                            "trigger": "user",
                            "trigger_function": "confirmOrder"
                        }
                    ]
                }
            }
        }
        result = converter.convert(yaml_spec)
        sm = result["stateMachines"]["OrderFlow"]

        assert sm["entity"] == "Order"
        assert sm["field"] == "status"
        assert sm["initial"] == "PENDING"
        assert sm["states"]["PENDING"]["description"] == "Pending order"
        assert sm["states"]["CONFIRMED"]["final"] is True

        transition = sm["transitions"][0]
        assert transition["id"] == "confirm"
        assert transition["from"] == "PENDING"
        assert transition["to"] == "CONFIRMED"
        assert transition["trigger"] == "user"
        assert transition["trigger_function"] == "confirmOrder"

    def test_convert_transition_with_guard(self, converter):
        """Test transition with guard expression."""
        yaml_spec = {
            "entities": {"Order": {"fields": {"status": {"type": "string"}}}},
            "stateMachines": {
                "OrderFlow": {
                    "entity": "Order",
                    "field": "status",
                    "initial": "PENDING",
                    "states": {"PENDING": {}, "PAID": {}},
                    "transitions": [{
                        "from": "PENDING",
                        "to": "PAID",
                        "guard": {"field": "self:totalAmount", "op": ">", "value": 0}
                    }]
                }
            }
        }
        result = converter.convert(yaml_spec)
        guard = result["stateMachines"]["OrderFlow"]["transitions"][0]["guard"]
        assert guard["type"] == "binary"
        assert guard["op"] == "gt"

    def test_convert_transition_from_multiple_states(self, converter):
        """Test transition from multiple source states."""
        yaml_spec = {
            "entities": {"Order": {"fields": {"status": {"type": "string"}}}},
            "stateMachines": {
                "OrderFlow": {
                    "entity": "Order",
                    "field": "status",
                    "initial": "A",
                    "states": {"A": {}, "B": {}, "C": {}},
                    "transitions": [{
                        "from": ["A", "B"],
                        "to": "C",
                        "trigger": "user"
                    }]
                }
            }
        }
        result = converter.convert(yaml_spec)
        transition = result["stateMachines"]["OrderFlow"]["transitions"][0]
        assert transition["from"] == ["A", "B"]

    def test_convert_command(self, converter):
        """Test command conversion."""
        yaml_spec = {
            "entities": {"Cart": {"fields": {"id": {"type": "id"}}}},
            "commands": {
                "addToCart": {
                    "description": "Add item to cart",
                    "entity": "Cart",
                    "input": {
                        "productId": {"type": "id", "required": True},
                        "quantity": {"type": "count", "min": 1}
                    },
                    "pre": [
                        {
                            "expr": {"field": "Product:stock", "op": ">=", "ref": "input:quantity"},
                            "error": "Insufficient stock"
                        }
                    ]
                }
            }
        }
        result = converter.convert(yaml_spec)
        cmd = result["commands"]["addToCart"]

        assert cmd["description"] == "Add item to cart"
        assert cmd["entity"] == "Cart"
        assert cmd["input"]["productId"]["type"] == "string"
        assert cmd["input"]["productId"]["preset"] == "id"
        assert cmd["input"]["quantity"]["type"] == "int"
        assert cmd["input"]["quantity"]["preset"] == "count"

        pre = cmd["pre"][0]
        assert pre["reason"] == "Insufficient stock"
        assert pre["expr"]["type"] == "binary"

    def test_convert_query(self, converter):
        """Test query conversion."""
        yaml_spec = {
            "entities": {"Product": {"fields": {"status": {"type": "string"}}}},
            "queries": {
                "listActiveProducts": {
                    "description": "List active products",
                    "entity": "Product",
                    "filter": {"field": "self:status", "op": "==", "value": "ACTIVE"},
                    "orderBy": {"field": "name", "direction": "asc"},
                    "pagination": {"defaultLimit": 20, "maxLimit": 100}
                }
            }
        }
        result = converter.convert(yaml_spec)
        query = result["queries"]["listActiveProducts"]

        assert query["description"] == "List active products"
        assert query["entity"] == "Product"
        assert query["filter"]["type"] == "binary"
        assert query["filter"]["op"] == "eq"
        assert query["orderBy"]["field"] == "name"
        assert query["pagination"]["defaultLimit"] == 20

    def test_convert_saga(self, converter):
        """Test saga conversion."""
        yaml_spec = {
            "entities": {"Order": {"fields": {"id": {"type": "id"}}}},
            "sagas": {
                "CancelOrderSaga": {
                    "description": "Cancel order with refund",
                    "steps": [
                        {"name": "cancelOrder", "forward": "cancelOrder", "compensate": "revertCancel"},
                        {"name": "refund", "forward": "refund", "compensate": "revertRefund"}
                    ],
                    "onFailure": "compensate_all"
                }
            }
        }
        result = converter.convert(yaml_spec)
        saga = result["sagas"]["CancelOrderSaga"]

        assert saga["description"] == "Cancel order with refund"
        assert len(saga["steps"]) == 2
        assert saga["steps"][0]["name"] == "cancelOrder"
        assert saga["steps"][0]["forward"] == "cancelOrder"
        assert saga["steps"][0]["compensate"] == "revertCancel"
        assert saga["onFailure"] == "compensate_all"

    def test_convert_invariant_with_when(self, converter):
        """Test invariant with when condition."""
        yaml_spec = {
            "entities": {"Payment": {"fields": {"status": {"type": "string"}, "refundAmount": {"type": "money"}}}},
            "invariants": [{
                "id": "refund_limit",
                "entity": "Payment",
                "description": "Refund must not exceed original amount",
                "when": {"field": "self:status", "op": "==", "value": "REFUNDED"},
                "expr": {"field": "self:refundAmount", "op": "<=", "ref": "self:amount"},
                "severity": "critical",
                "violation": "Refund exceeds payment"
            }]
        }
        result = converter.convert(yaml_spec)
        inv = result["invariants"][0]

        assert inv["id"] == "refund_limit"
        assert inv["when"]["type"] == "binary"
        assert inv["when"]["op"] == "eq"
        assert inv["expr"]["type"] == "binary"
        assert inv["severity"] == "critical"
        assert inv["violation"] == "Refund exceeds payment"

    def test_convert_role(self, converter):
        """Test role conversion."""
        yaml_spec = {
            "entities": {"Order": {"fields": {"userId": {"type": "ref", "ref": "User"}}}},
            "roles": {
                "buyer": {
                    "description": "Customer who buys products",
                    "permissions": [
                        {"resource": "Order", "actions": ["create", "read"]},
                        {
                            "resource": "Order",
                            "actions": ["update"],
                            "condition": {"field": "self:userId", "op": "==", "ref": "principal:id"}
                        }
                    ]
                }
            }
        }
        result = converter.convert(yaml_spec)
        role = result["roles"]["buyer"]

        assert role["description"] == "Customer who buys products"
        assert len(role["permissions"]) == 2
        assert role["permissions"][0]["resource"] == "Order"
        assert role["permissions"][0]["actions"] == ["create", "read"]
        assert role["permissions"][1]["condition"]["type"] == "binary"
        assert role["permissions"][1]["condition"]["left"]["type"] == "ref"
        assert role["permissions"][1]["condition"]["right"]["type"] == "principal"

    def test_convert_field_reference_input(self, converter):
        """Test input: field reference parsing."""
        expr = {"field": "input:quantity", "op": ">", "value": 0}
        result = converter._convert_simple_condition(expr)
        assert result["left"]["type"] == "input"
        assert result["left"]["name"] == "quantity"

    def test_convert_field_reference_self(self, converter):
        """Test self: field reference parsing."""
        expr = {"field": "self:price", "op": ">", "value": 0}
        result = converter._convert_simple_condition(expr)
        assert result["left"]["type"] == "ref"
        assert result["left"]["path"] == "price"

    def test_convert_field_reference_entity(self, converter):
        """Test Entity:field reference parsing."""
        expr = {"field": "Product:stock", "op": ">", "value": 0}
        result = converter._convert_simple_condition(expr)
        assert result["left"]["type"] == "ref"
        assert result["left"]["path"] == "Product.stock"

    def test_convert_field_reference_principal(self, converter):
        """Test principal: field reference parsing."""
        expr = {"field": "principal:id", "op": "!=", "value": None}
        result = converter._convert_simple_condition(expr)
        assert result["left"]["type"] == "principal"
        assert result["left"]["field"] == "id"

    def test_convert_in_operator(self, converter):
        """Test 'in' operator with list value."""
        expr = {"field": "self:status", "op": "in", "value": ["ACTIVE", "PENDING"]}
        result = converter._convert_simple_condition(expr)
        assert result["op"] == "in"
        assert result["right"]["type"] == "list"
        assert len(result["right"]["items"]) == 2


class TestECPrototypeConversion:
    """Integration tests using the EC prototype YAML."""

    @pytest.fixture
    def converter(self):
        return YAMLToTRIRConverter()

    @pytest.fixture
    def ec_yaml_path(self):
        return Path(__file__).parent.parent / "examples" / "ec-prototype.yaml"

    @pytest.fixture
    def ec_yaml(self, ec_yaml_path):
        if not ec_yaml_path.exists():
            pytest.skip(f"EC prototype file not found: {ec_yaml_path}")
        with open(ec_yaml_path) as f:
            return yaml.safe_load(f)

    def test_ec_prototype_converts(self, converter, ec_yaml):
        """EC prototype should convert without errors."""
        result = converter.convert(ec_yaml)
        assert "meta" in result
        assert "entities" in result
        assert "stateMachines" in result

    def test_ec_prototype_has_all_entities(self, converter, ec_yaml):
        """All EC entities should be converted."""
        result = converter.convert(ec_yaml)
        expected_entities = ["Product", "Cart", "CartItem", "Order", "Payment", "Shipment"]
        for entity in expected_entities:
            assert entity in result["entities"], f"Missing entity: {entity}"

    def test_ec_prototype_has_all_state_machines(self, converter, ec_yaml):
        """All EC state machines should be converted."""
        result = converter.convert(ec_yaml)
        expected_sms = ["OrderFlow", "PaymentFlow", "ShipmentFlow"]
        for sm in expected_sms:
            assert sm in result["stateMachines"], f"Missing state machine: {sm}"

    def test_ec_prototype_has_all_commands(self, converter, ec_yaml):
        """All EC commands should be converted."""
        result = converter.convert(ec_yaml)
        expected_cmds = ["addToCart", "confirmOrder", "startPayment", "cancelWithRefund"]
        for cmd in expected_cmds:
            assert cmd in result["commands"], f"Missing command: {cmd}"

    def test_ec_prototype_has_all_queries(self, converter, ec_yaml):
        """All EC queries should be converted."""
        result = converter.convert(ec_yaml)
        expected_queries = ["listProducts", "getOrderHistory"]
        for query in expected_queries:
            assert query in result["queries"], f"Missing query: {query}"

    def test_ec_prototype_has_invariants(self, converter, ec_yaml):
        """EC invariants should be converted."""
        result = converter.convert(ec_yaml)
        assert len(result["invariants"]) == 5
        inv_ids = [inv["id"] for inv in result["invariants"]]
        assert "positive_price" in inv_ids
        assert "refund_within_payment" in inv_ids

    def test_ec_prototype_has_roles(self, converter, ec_yaml):
        """EC roles should be converted."""
        result = converter.convert(ec_yaml)
        assert "buyer" in result["roles"]
        assert "storeAdmin" in result["roles"]

    def test_ec_prototype_has_saga(self, converter, ec_yaml):
        """EC saga should be converted."""
        result = converter.convert(ec_yaml)
        assert "CancelRefundSaga" in result["sagas"]
        saga = result["sagas"]["CancelRefundSaga"]
        assert len(saga["steps"]) == 3

    def test_ec_prototype_has_test_strategies(self, converter, ec_yaml):
        """EC test strategies should be converted."""
        result = converter.convert(ec_yaml)
        assert "testStrategies" in result
        assert result["testStrategies"]["coverage"]["mode"] == "risk_based"
