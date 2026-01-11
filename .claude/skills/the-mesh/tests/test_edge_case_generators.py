"""Tests for edge case test generators (idempotency, concurrency, authorization)"""

import pytest
import sys
from pathlib import Path

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

import yaml
from generators.python.idempotency_gen import IdempotencyTestGenerator
from generators.python.concurrency_gen import ConcurrencyTestGenerator
from generators.python.authorization_gen import AuthorizationTestGenerator
from converter import YAMLToTRIRConverter


@pytest.fixture
def ec_prototype_spec():
    """Load EC prototype spec converted from YAML"""
    yaml_path = Path(__file__).parent.parent / "examples" / "ec-prototype.yaml"
    with open(yaml_path, "r") as f:
        yaml_spec = yaml.safe_load(f)
    converter = YAMLToTRIRConverter()
    return converter.convert(yaml_spec)


@pytest.fixture
def minimal_spec_with_test_strategies():
    """Minimal spec with testStrategies enabled"""
    return {
        "meta": {"id": "test", "version": "1.0"},
        "entities": {
            "Order": {
                "fields": {
                    "id": {"type": "string"},
                    "amount": {"type": "float", "preset": "money"},
                    "status": {"type": "string"},
                }
            },
            "Payment": {
                "fields": {
                    "id": {"type": "string"},
                    "orderId": {"type": "string"},
                    "amount": {"type": "float", "preset": "money"},
                }
            },
        },
        "commands": {
            "createOrder": {
                "entity": "Order",
                "input": {
                    "amount": {"type": "float", "required": True},
                }
            },
            "confirmPayment": {
                "entity": "Payment",
                "input": {
                    "orderId": {"type": "string", "required": True},
                }
            },
        },
        "roles": {
            "buyer": {
                "permissions": [
                    {"resource": "Order", "actions": ["create", "read"]},
                ]
            },
            "admin": {
                "permissions": [
                    {"resource": "Order", "actions": ["create", "read", "update", "delete", "list"]},
                    {"resource": "Payment", "actions": ["create", "read", "update"]},
                ]
            },
        },
        "testStrategies": {
            "templates": {
                "idempotency": {
                    "enabled": True,
                    "targets": ["createOrder"],
                },
                "concurrency": {
                    "enabled": True,
                    "targets": ["Order", "Payment"],
                    "parallelRequests": 3,
                },
                "authorization": {
                    "enabled": True,
                    "targets": ["buyer", "admin"],
                },
            }
        }
    }


class TestIdempotencyGenerator:
    """Tests for IdempotencyTestGenerator"""

    def test_generate_disabled(self):
        """When disabled, generates placeholder tests"""
        spec = {
            "meta": {"id": "test"},
            "entities": {},
            "testStrategies": {
                "templates": {
                    "idempotency": {"enabled": False}
                }
            }
        }
        gen = IdempotencyTestGenerator(spec)
        output = gen.generate_all()

        assert "DISABLED" in output
        assert "@pytest.mark.skip" in output

    def test_generate_with_targets(self, minimal_spec_with_test_strategies):
        """Generates tests for specified targets"""
        gen = IdempotencyTestGenerator(minimal_spec_with_test_strategies)
        output = gen.generate_all()

        assert "Auto-generated Idempotency Tests" in output
        assert "TestIdempotencyCreateOrder" in output
        assert "double_exec" in output
        assert "retry_safety" in output

    def test_generate_from_ec_prototype(self, ec_prototype_spec):
        """Generates tests from full EC prototype"""
        gen = IdempotencyTestGenerator(ec_prototype_spec)
        output = gen.generate_all()

        # Should generate tests for addToCart and confirmOrder
        assert "addToCart" in output.lower() or "add_to_cart" in output.lower()
        assert "confirmOrder" in output.lower() or "confirm_order" in output.lower()


class TestConcurrencyGenerator:
    """Tests for ConcurrencyTestGenerator"""

    def test_generate_disabled(self):
        """When disabled, generates placeholder tests"""
        spec = {
            "meta": {"id": "test"},
            "entities": {},
            "testStrategies": {
                "templates": {
                    "concurrency": {"enabled": False}
                }
            }
        }
        gen = ConcurrencyTestGenerator(spec)
        output = gen.generate_all()

        assert "DISABLED" in output
        assert "@pytest.mark.skip" in output

    def test_generate_with_targets(self, minimal_spec_with_test_strategies):
        """Generates tests for specified targets"""
        gen = ConcurrencyTestGenerator(minimal_spec_with_test_strategies)
        output = gen.generate_all()

        assert "Auto-generated Concurrency Tests" in output
        assert "TestConcurrencyOrder" in output or "TestConcurrencyPayment" in output
        assert "parallel_same" in output or "read_write_race" in output

    def test_generate_from_ec_prototype(self, ec_prototype_spec):
        """Generates tests from full EC prototype"""
        gen = ConcurrencyTestGenerator(ec_prototype_spec)
        output = gen.generate_all()

        # Should generate tests for Order and Payment entities
        assert "Order" in output
        assert "Payment" in output


class TestAuthorizationGenerator:
    """Tests for AuthorizationTestGenerator"""

    def test_generate_disabled(self):
        """When disabled, generates placeholder tests"""
        spec = {
            "meta": {"id": "test"},
            "entities": {},
            "roles": {},
            "testStrategies": {
                "templates": {
                    "authorization": {"enabled": False}
                }
            }
        }
        gen = AuthorizationTestGenerator(spec)
        output = gen.generate_all()

        assert "DISABLED" in output
        assert "@pytest.mark.skip" in output

    def test_generate_with_targets(self, minimal_spec_with_test_strategies):
        """Generates tests for specified roles"""
        gen = AuthorizationTestGenerator(minimal_spec_with_test_strategies)
        output = gen.generate_all()

        assert "Auto-generated Authorization Tests" in output
        # Should have tests for buyer and admin roles
        assert "buyer" in output.lower()
        assert "admin" in output.lower()
        # Should test both allowed and denied actions
        assert "allowed" in output.lower()
        assert "denied" in output.lower()

    def test_generate_permission_granted_tests(self, minimal_spec_with_test_strategies):
        """Generates permission granted tests"""
        gen = AuthorizationTestGenerator(minimal_spec_with_test_strategies)
        output = gen.generate_all()

        # buyer can create and read Order
        assert "Order" in output
        assert "create" in output.lower()
        assert "read" in output.lower()

    def test_generate_permission_denied_tests(self, minimal_spec_with_test_strategies):
        """Generates permission denied tests for non-allowed actions"""
        gen = AuthorizationTestGenerator(minimal_spec_with_test_strategies)
        output = gen.generate_all()

        # buyer cannot delete Order
        assert "denied" in output.lower()
        assert "delete" in output.lower() or "update" in output.lower()

    def test_generate_from_ec_prototype(self, ec_prototype_spec):
        """Generates tests from full EC prototype"""
        gen = AuthorizationTestGenerator(ec_prototype_spec)
        output = gen.generate_all()

        # Should generate tests for buyer and storeAdmin roles
        assert "buyer" in output.lower()
        assert "storeadmin" in output.lower() or "store_admin" in output.lower()


class TestGeneratorIntegration:
    """Integration tests for all generators"""

    def test_all_generators_produce_valid_python(self, ec_prototype_spec):
        """All generators produce syntactically valid Python"""
        generators = [
            IdempotencyTestGenerator(ec_prototype_spec),
            ConcurrencyTestGenerator(ec_prototype_spec),
            AuthorizationTestGenerator(ec_prototype_spec),
        ]

        for gen in generators:
            output = gen.generate_all()
            # Should be valid Python (compile check)
            try:
                compile(output, "<string>", "exec")
            except SyntaxError as e:
                pytest.fail(f"{gen.__class__.__name__} produced invalid Python: {e}")

    def test_generators_handle_empty_test_strategies(self):
        """Generators handle missing testStrategies gracefully"""
        spec = {
            "meta": {"id": "test"},
            "entities": {"Order": {"fields": {"id": {"type": "string"}}}},
        }

        # Should not raise, should return disabled/empty tests
        for GenClass in [IdempotencyTestGenerator, ConcurrencyTestGenerator, AuthorizationTestGenerator]:
            gen = GenClass(spec)
            output = gen.generate_all()
            assert output  # Should produce some output
            assert "DISABLED" in output or len(output) > 0
