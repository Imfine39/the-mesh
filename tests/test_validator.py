"""
TRIR Validator Test Suite

Comprehensive tests for the TRIR validator including:
- VAL-001: Custom discriminator validation for expressions
- VAL-003: State machine trigger existence check
- VAL-004: State machine reachability analysis
- VAL-006: Bidirectional reference consistency check

This test suite works with or without pytest.
"""

import json
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from the_mesh.core.validator import MeshValidator, ValidationError, ValidationResult, generate_fix_patches, suggest_fix_for_error, find_closest_match, suggest_completions, validate_changes

# Try to import pytest, but make it optional
try:
    import pytest
    HAS_PYTEST = True

    @pytest.fixture
    def validator():
        """Create a validator instance"""
        return MeshValidator()

    @pytest.fixture
    def minimal_spec():
        """Minimal valid specification"""
        return {
            "meta": {
                "id": "test-spec",
                "title": "Test Specification",
                "version": "1.0.0",
                "schemaVersion": "v1"
            },
            "state": {}
        }

    @pytest.fixture
    def sample_spec():
        """Load the sample specification"""
        sample_path = Path(__file__).parent.parent / "examples" / "ar_clearing_extended.mesh.json"
        with open(sample_path) as f:
            return json.load(f)

except ImportError:
    HAS_PYTEST = False

    # Define simple replacements when pytest is not available
    def validator():
        return MeshValidator()

    def minimal_spec():
        return {
            "meta": {
                "id": "test-spec",
                "title": "Test Specification",
                "version": "1.0.0",
                "schemaVersion": "v1"
            },
            "state": {}
        }

    def sample_spec():
        sample_path = Path(__file__).parent.parent / "examples" / "ar_clearing_extended.mesh.json"
        with open(sample_path) as f:
            return json.load(f)


class TestBasicValidation:
    """Basic validation tests"""

    def test_minimal_spec_valid(self, validator, minimal_spec):
        """Minimal spec should be valid"""
        result = validator.validate(minimal_spec)
        assert result.valid
        assert len(result.errors) == 0

    def test_empty_spec_invalid(self, validator):
        """Empty spec should fail"""
        result = validator.validate({})
        assert not result.valid
        # Should have errors for missing required fields
        error_messages = [e.message for e in result.errors]
        assert any("'meta' is a required property" in m for m in error_messages)
        assert any("'state' is a required property" in m for m in error_messages)

    def test_sample_spec_valid(self, validator, sample_spec):
        """Sample spec should be valid"""
        result = validator.validate(sample_spec)
        assert result.valid, f"Errors: {[e.message for e in result.errors]}"
        assert len(result.errors) == 0


class TestVAL001DiscriminatorValidation:
    """VAL-001: Custom discriminator validation for expressions"""

    def test_missing_type_field(self, validator, minimal_spec):
        """Expression without 'type' field should fail"""
        minimal_spec["derived"] = {
            "broken": {
                "entity": "test",
                "formula": {"op": "add", "left": {"type": "literal", "value": 1}}
            }
        }
        result = validator.validate(minimal_spec)
        assert not result.valid
        error_messages = [e.message for e in result.errors]
        assert any("missing required 'type' discriminator field" in m for m in error_messages)

    def test_unknown_expression_type(self, validator, minimal_spec):
        """Unknown expression type should fail"""
        minimal_spec["derived"] = {
            "broken": {
                "entity": "test",
                "formula": {"type": "invalid_type", "value": 1}
            }
        }
        result = validator.validate(minimal_spec)
        assert not result.valid
        error_messages = [e.message for e in result.errors]
        assert any("Unknown expression type 'invalid_type'" in m for m in error_messages)

    def test_missing_required_field(self, validator, minimal_spec):
        """Expression missing required field should fail"""
        minimal_spec["derived"] = {
            "broken": {
                "entity": "test",
                "formula": {"type": "binary", "op": "add", "left": {"type": "literal", "value": 1}}
            }
        }
        result = validator.validate(minimal_spec)
        assert not result.valid
        error_messages = [e.message for e in result.errors]
        assert any("missing required field 'right'" in m for m in error_messages)

    def test_invalid_operator(self, validator, minimal_spec):
        """Invalid operator should fail"""
        minimal_spec["derived"] = {
            "broken": {
                "entity": "test",
                "formula": {
                    "type": "binary",
                    "op": "invalid_op",
                    "left": {"type": "literal", "value": 1},
                    "right": {"type": "literal", "value": 2}
                }
            }
        }
        result = validator.validate(minimal_spec)
        assert not result.valid
        error_messages = [e.message for e in result.errors]
        assert any("Invalid operator 'invalid_op'" in m for m in error_messages)

    def test_unexpected_field(self, validator, minimal_spec):
        """Unexpected field should fail"""
        minimal_spec["derived"] = {
            "broken": {
                "entity": "test",
                "formula": {"type": "literal", "value": 1, "extra_field": "not allowed"}
            }
        }
        result = validator.validate(minimal_spec)
        assert not result.valid
        error_messages = [e.message for e in result.errors]
        assert any("unexpected field 'extra_field'" in m for m in error_messages)

    def test_nested_expression_validation(self, validator, minimal_spec):
        """Nested expressions should be validated"""
        minimal_spec["derived"] = {
            "broken": {
                "entity": "test",
                "formula": {
                    "type": "binary",
                    "op": "add",
                    "left": {"type": "literal", "value": 1},
                    "right": {"type": "unknown_nested", "value": 2}
                }
            }
        }
        result = validator.validate(minimal_spec)
        assert not result.valid
        error_messages = [e.message for e in result.errors]
        assert any("Unknown expression type 'unknown_nested'" in m for m in error_messages)

    def test_valid_literal_expression(self, validator, minimal_spec):
        """Valid literal expression should pass"""
        minimal_spec["state"] = {"test_entity": {"fields": {}}}
        minimal_spec["derived"] = {
            "test": {
                "entity": "test_entity",
                "formula": {"type": "literal", "value": 42}
            }
        }
        result = validator.validate(minimal_spec)
        # Should only have entity-related errors, not expression errors
        expr_errors = [e for e in result.errors if "Expression" in e.message or "expression" in e.message]
        assert len(expr_errors) == 0

    def test_valid_binary_expression(self, validator, minimal_spec):
        """Valid binary expression should pass"""
        minimal_spec["state"] = {"test_entity": {"fields": {}}}
        minimal_spec["derived"] = {
            "test": {
                "entity": "test_entity",
                "formula": {
                    "type": "binary",
                    "op": "add",
                    "left": {"type": "literal", "value": 1},
                    "right": {"type": "literal", "value": 2}
                }
            }
        }
        result = validator.validate(minimal_spec)
        expr_errors = [e for e in result.errors if "Expression" in e.message or "expression" in e.message]
        assert len(expr_errors) == 0

    def test_valid_aggregation_expression(self, validator, minimal_spec):
        """Valid aggregation expression should pass"""
        minimal_spec["state"] = {"orders": {"fields": {"amount": {"type": "int"}}}}
        minimal_spec["derived"] = {
            "total": {
                "entity": "orders",
                "formula": {
                    "type": "agg",
                    "op": "sum",
                    "from": "orders",
                    "expr": {"type": "ref", "path": "orders.amount"}
                }
            }
        }
        result = validator.validate(minimal_spec)
        discrim_errors = [e for e in result.errors if "discriminator" in e.message.lower() or "expression type" in e.message.lower()]
        assert len(discrim_errors) == 0


class TestVAL003TriggerValidation:
    """VAL-003: State machine trigger existence check"""

    def test_valid_trigger(self, validator, minimal_spec):
        """Valid trigger should pass"""
        minimal_spec["state"] = {"order": {"fields": {}}}
        minimal_spec["functions"] = {
            "submit_order": {
                "description": "Submit an order",
                "input": {},
                "pre": [],
                "post": []
            }
        }
        minimal_spec["stateMachines"] = {
            "order_status": {
                "entity": "order",
                "field": "status",
                "initial": "DRAFT",
                "states": {"DRAFT": {}, "SUBMITTED": {}},
                "transitions": [
                    {"from": "DRAFT", "to": "SUBMITTED", "trigger_function": "submit_order"}
                ]
            }
        }
        result = validator.validate(minimal_spec)
        trigger_errors = [e for e in result.errors if "Trigger" in e.message]
        assert len(trigger_errors) == 0

    def test_missing_trigger_function(self, validator, minimal_spec):
        """Missing trigger function should fail"""
        minimal_spec["state"] = {"order": {"fields": {}}}
        minimal_spec["stateMachines"] = {
            "order_status": {
                "entity": "order",
                "field": "status",
                "initial": "DRAFT",
                "states": {"DRAFT": {}, "SUBMITTED": {}},
                "transitions": [
                    {"from": "DRAFT", "to": "SUBMITTED", "trigger_function": "nonexistent_function"}
                ]
            }
        }
        result = validator.validate(minimal_spec)
        trigger_errors = [e for e in result.errors if "Trigger" in e.message]
        assert len(trigger_errors) > 0
        assert any("nonexistent_function" in e.message for e in trigger_errors)


class TestVAL004ReachabilityAnalysis:
    """VAL-004: State machine reachability analysis"""

    def test_all_states_reachable(self, validator, minimal_spec):
        """All states reachable should not warn"""
        minimal_spec["state"] = {"order": {"fields": {}}}
        minimal_spec["functions"] = {
            "submit": {"description": "Submit", "input": {}, "pre": [], "post": []},
            "complete": {"description": "Complete", "input": {}, "pre": [], "post": []}
        }
        minimal_spec["stateMachines"] = {
            "order_status": {
                "entity": "order",
                "field": "status",
                "initial": "DRAFT",
                "states": {"DRAFT": {}, "SUBMITTED": {}, "COMPLETED": {"final": True}},
                "transitions": [
                    {"from": "DRAFT", "to": "SUBMITTED", "trigger_function": "submit"},
                    {"from": "SUBMITTED", "to": "COMPLETED", "trigger_function": "complete"}
                ]
            }
        }
        result = validator.validate(minimal_spec)
        reachability_warnings = [w for w in result.warnings if "Unreachable" in w.message]
        assert len(reachability_warnings) == 0

    def test_unreachable_state_warning(self, validator, minimal_spec):
        """Unreachable state should generate warning"""
        minimal_spec["state"] = {"order": {"fields": {}}}
        minimal_spec["functions"] = {
            "submit": {"description": "Submit", "input": {}, "pre": [], "post": []}
        }
        minimal_spec["stateMachines"] = {
            "order_status": {
                "entity": "order",
                "field": "status",
                "initial": "DRAFT",
                "states": {"DRAFT": {}, "SUBMITTED": {}, "ORPHAN": {}},
                "transitions": [
                    {"from": "DRAFT", "to": "SUBMITTED", "trigger_function": "submit"}
                ]
            }
        }
        result = validator.validate(minimal_spec)
        unreachable_warnings = [w for w in result.warnings if "Unreachable" in w.message]
        assert len(unreachable_warnings) > 0
        assert any("ORPHAN" in w.message for w in unreachable_warnings)

    def test_dead_end_state_warning(self, validator, minimal_spec):
        """Non-final dead-end state should generate warning"""
        minimal_spec["state"] = {"order": {"fields": {}}}
        minimal_spec["functions"] = {
            "submit": {"description": "Submit", "input": {}, "pre": [], "post": []}
        }
        minimal_spec["stateMachines"] = {
            "order_status": {
                "entity": "order",
                "field": "status",
                "initial": "DRAFT",
                "states": {"DRAFT": {}, "DEAD_END": {}},  # DEAD_END is not final
                "transitions": [
                    {"from": "DRAFT", "to": "DEAD_END", "trigger_function": "submit"}
                ]
            }
        }
        result = validator.validate(minimal_spec)
        dead_end_warnings = [w for w in result.warnings if "Dead-end" in w.message]
        assert len(dead_end_warnings) > 0
        assert any("DEAD_END" in w.message for w in dead_end_warnings)


class TestVAL006BidirectionalReferences:
    """VAL-006: Bidirectional reference consistency check"""

    def test_valid_cascade_options(self, validator, minimal_spec):
        """Valid cascade options should pass"""
        minimal_spec["state"] = {
            "parent": {"fields": {}},
            "child": {"fields": {"parent_id": {"type": {"ref": "parent"}}}}
        }
        minimal_spec["relations"] = {
            "parent_children": {
                "_kind": "relation",
                "from": "parent",
                "to": "child",
                "type": "one_to_many",
                "foreignKey": "parent_id",
                "cascade": {"delete": "restrict", "update": "cascade"}
            }
        }
        result = validator.validate(minimal_spec)
        cascade_errors = [e for e in result.errors if "cascade" in e.message.lower()]
        assert len(cascade_errors) == 0

    def test_invalid_cascade_option(self, validator, minimal_spec):
        """Invalid cascade option should fail"""
        minimal_spec["state"] = {
            "parent": {"fields": {}},
            "child": {"fields": {"parent_id": {"type": {"ref": "parent"}}}}
        }
        minimal_spec["relations"] = {
            "parent_children": {
                "_kind": "relation",
                "from": "parent",
                "to": "child",
                "type": "one_to_many",
                "foreignKey": "parent_id",
                "cascade": {"delete": "invalid_cascade"}
            }
        }
        result = validator.validate(minimal_spec)
        cascade_errors = [e for e in result.errors if "cascade" in e.message.lower()]
        assert len(cascade_errors) > 0

    def test_bidirectional_relation_consistency(self, validator, minimal_spec):
        """Consistent bidirectional relations should pass"""
        minimal_spec["state"] = {
            "a": {"fields": {}},
            "b": {"fields": {}}
        }
        minimal_spec["relations"] = {
            "a_to_b": {
                "_kind": "relation",
                "from": "a",
                "to": "b",
                "type": "one_to_many",
                "inverse": "b_to_a"
            },
            "b_to_a": {
                "_kind": "relation",
                "from": "b",
                "to": "a",
                "type": "one_to_many",  # Note: Schema doesn't have many_to_one
                "inverse": "a_to_b"
            }
        }
        result = validator.validate(minimal_spec)
        bidirectional_errors = [e for e in result.errors if "Bidirectional" in e.message or "Inverse" in e.message]
        assert len(bidirectional_errors) == 0

    def test_bidirectional_relation_mismatch(self, validator, minimal_spec):
        """Mismatched bidirectional relations should fail"""
        minimal_spec["state"] = {
            "a": {"fields": {}},
            "b": {"fields": {}},
            "c": {"fields": {}}
        }
        minimal_spec["relations"] = {
            "a_to_b": {
                "_kind": "relation",
                "from": "a",
                "to": "b",
                "type": "one_to_many",
                "inverse": "b_to_a"
            },
            "b_to_a": {
                "_kind": "relation",
                "from": "b",
                "to": "c",  # Wrong! Should be 'a'
                "type": "one_to_many",
                "inverse": "a_to_b"
            }
        }
        result = validator.validate(minimal_spec)
        bidirectional_errors = [e for e in result.errors if "Bidirectional" in e.message]
        assert len(bidirectional_errors) > 0


class TestReferenceValidation:
    """Reference validation tests"""

    def test_valid_entity_reference(self, validator, minimal_spec):
        """Valid entity reference should pass"""
        minimal_spec["state"] = {
            "customer": {"fields": {}},
            "order": {"fields": {"customer_id": {"type": {"ref": "customer"}}}}
        }
        result = validator.validate(minimal_spec)
        ref_errors = [e for e in result.errors if "does not exist" in e.message]
        assert len(ref_errors) == 0

    def test_invalid_entity_reference(self, validator, minimal_spec):
        """Invalid entity reference should fail"""
        minimal_spec["state"] = {
            "order": {"fields": {"customer_id": {"type": {"ref": "nonexistent"}}}}
        }
        result = validator.validate(minimal_spec)
        ref_errors = [e for e in result.errors if "does not exist" in e.message]
        assert len(ref_errors) > 0


class TestCycleDetection:
    """Cycle detection tests"""

    def test_no_cycles(self, validator, minimal_spec):
        """No cycles should not warn"""
        minimal_spec["state"] = {"entity": {"fields": {}}}
        minimal_spec["derived"] = {
            "a": {
                "entity": "entity",
                "formula": {"type": "literal", "value": 1}
            },
            "b": {
                "entity": "entity",
                "formula": {"type": "call", "name": "a"}
            }
        }
        result = validator.validate(minimal_spec)
        cycle_warnings = [w for w in result.warnings if "Circular" in w.message]
        assert len(cycle_warnings) == 0

    def test_cycle_detected(self, validator, minimal_spec):
        """Cycles should generate warning"""
        minimal_spec["state"] = {"entity": {"fields": {}}}
        minimal_spec["derived"] = {
            "a": {
                "entity": "entity",
                "formula": {"type": "call", "name": "b"}
            },
            "b": {
                "entity": "entity",
                "formula": {"type": "call", "name": "a"}
            }
        }
        result = validator.validate(minimal_spec)
        cycle_warnings = [w for w in result.warnings if "Circular" in w.message]
        assert len(cycle_warnings) > 0


class TestPhase1ExpressionTypes:
    """Tests for Phase 1 extension expression types"""

    def test_temporal_expression(self, validator, minimal_spec):
        """Valid temporal expression should pass discriminator validation"""
        minimal_spec["state"] = {"order": {"fields": {}}}
        minimal_spec["derived"] = {
            "order_at_time": {
                "entity": "order",
                "formula": {
                    "type": "temporal",
                    "op": "at",
                    "entity": "order",
                    "field": "status"
                }
            }
        }
        result = validator.validate(minimal_spec)
        discrim_errors = [e for e in result.errors if "expression type" in e.message.lower()]
        assert len(discrim_errors) == 0

    def test_window_expression(self, validator, minimal_spec):
        """Valid window expression should pass discriminator validation"""
        minimal_spec["state"] = {"sales": {"fields": {"amount": {"type": "int"}}}}
        minimal_spec["derived"] = {
            "running_total": {
                "entity": "sales",
                "formula": {
                    "type": "window",
                    "op": "sum",
                    "from": "sales",
                    "expr": {"type": "ref", "path": "sales.amount"}
                }
            }
        }
        result = validator.validate(minimal_spec)
        discrim_errors = [e for e in result.errors if "expression type" in e.message.lower()]
        assert len(discrim_errors) == 0

    def test_state_expression(self, validator, minimal_spec):
        """Valid state expression should pass validation"""
        minimal_spec["state"] = {"order": {"fields": {}}}
        minimal_spec["stateMachines"] = {
            "order_status": {
                "entity": "order",
                "field": "status",
                "initial": "DRAFT",
                "states": {"DRAFT": {}, "SUBMITTED": {}},
                "transitions": []
            }
        }
        minimal_spec["derived"] = {
            "is_draft": {
                "entity": "order",
                "formula": {
                    "type": "state",
                    "op": "is_in",
                    "machine": "order_status",
                    "state": "DRAFT"
                }
            }
        }
        result = validator.validate(minimal_spec)
        state_errors = [e for e in result.errors if "state" in e.message.lower() and "expression" in e.path.lower()]
        assert len(state_errors) == 0

    def test_state_expression_invalid_state(self, validator, minimal_spec):
        """State expression with invalid state should fail semantic validation"""
        minimal_spec["state"] = {"order": {"fields": {}}}
        minimal_spec["stateMachines"] = {
            "order_status": {
                "entity": "order",
                "field": "status",
                "initial": "DRAFT",
                "states": {"DRAFT": {}},
                "transitions": []
            }
        }
        minimal_spec["derived"] = {
            "is_nonexistent": {
                "entity": "order",
                "formula": {
                    "type": "state",
                    "op": "is_in",
                    "machine": "order_status",
                    "state": "NONEXISTENT"
                }
            }
        }
        result = validator.validate(minimal_spec)
        state_errors = [e for e in result.errors if "'NONEXISTENT'" in e.message]
        assert len(state_errors) > 0

    def test_principal_expression(self, validator, minimal_spec):
        """Valid principal expression should pass"""
        minimal_spec["roles"] = {
            "admin": {"permissions": ["manage_users"]}
        }
        minimal_spec["derived"] = {
            "can_manage": {
                "entity": "test",
                "formula": {
                    "type": "principal",
                    "op": "has_role",
                    "role": "admin"
                }
            }
        }
        result = validator.validate(minimal_spec)
        discrim_errors = [e for e in result.errors if "expression type" in e.message.lower()]
        assert len(discrim_errors) == 0


class TestPhase2Gateways:
    """Test Phase 2 gateway validation"""

    def test_valid_exclusive_gateway(self, validator, minimal_spec):
        """Test valid exclusive gateway"""
        minimal_spec["gateways"] = {
            "test_gateway": {
                "_kind": "gateway",
                "type": "exclusive",
                "description": "Test gateway",
                "outgoingFlows": [
                    {"target": "test_func", "condition": {"type": "literal", "value": True}},
                    {"target": "test_func", "default": True}
                ]
            }
        }
        minimal_spec["functions"] = {
            "test_func": {"description": "Test", "input": {}, "post": []}
        }
        result = validator.validate(minimal_spec)
        gateway_errors = [e for e in result.errors if "gateway" in e.path.lower()]
        assert len(gateway_errors) == 0

    def test_invalid_gateway_type(self, validator, minimal_spec):
        """Test invalid gateway type validation"""
        minimal_spec["gateways"] = {
            "test_gateway": {
                "_kind": "gateway",
                "type": "invalid_type",
                "outgoingFlows": [
                    {"target": "test_func"}
                ]
            }
        }
        minimal_spec["functions"] = {
            "test_func": {"description": "Test", "input": {}, "post": []}
        }
        result = validator.validate(minimal_spec)
        type_errors = [e for e in result.errors if "gateway type" in e.message.lower()]
        assert len(type_errors) > 0

    def test_gateway_unknown_target(self, validator, minimal_spec):
        """Test gateway with unknown target"""
        minimal_spec["gateways"] = {
            "test_gateway": {
                "_kind": "gateway",
                "type": "exclusive",
                "outgoingFlows": [
                    {"target": "unknown_function"}
                ]
            }
        }
        result = validator.validate(minimal_spec)
        target_errors = [e for e in result.errors if "not found" in e.message.lower()]
        assert len(target_errors) > 0

    def test_parallel_gateway_no_conditions(self, validator, minimal_spec):
        """Test parallel gateway should not have conditions"""
        minimal_spec["gateways"] = {
            "test_gateway": {
                "_kind": "gateway",
                "type": "parallel",
                "outgoingFlows": [
                    {"target": "test_func", "condition": {"type": "literal", "value": True}}
                ]
            }
        }
        minimal_spec["functions"] = {
            "test_func": {"description": "Test", "input": {}, "post": []}
        }
        result = validator.validate(minimal_spec)
        parallel_errors = [e for e in result.errors if "parallel" in e.message.lower()]
        assert len(parallel_errors) > 0


class TestPhase2Deadlines:
    """Test Phase 2 deadline validation"""

    def test_valid_deadline(self, validator, minimal_spec):
        """Test valid deadline definition"""
        minimal_spec["state"] = {
            "test_entity": {
                "fields": {
                    "test_field": {"type": "datetime", "required": True}
                }
            }
        }
        minimal_spec["deadlines"] = {
            "test_deadline": {
                "_kind": "deadline",
                "entity": "test_entity",
                "description": "Test deadline",
                "duration": "24h",
                "startWhen": {"field": "test_field", "condition": "created"},
                "action": "test_func"
            }
        }
        minimal_spec["functions"] = {
            "test_func": {"description": "Test", "input": {}, "post": []}
        }
        result = validator.validate(minimal_spec)
        deadline_errors = [e for e in result.errors if "deadline" in e.path.lower()]
        assert len(deadline_errors) == 0

    def test_deadline_unknown_entity(self, validator, minimal_spec):
        """Test deadline with unknown entity"""
        minimal_spec["deadlines"] = {
            "test_deadline": {
                "_kind": "deadline",
                "entity": "unknown_entity",
                "duration": "P1D",
                "startWhen": {"field": "created_at"}
            }
        }
        result = validator.validate(minimal_spec)
        entity_errors = [e for e in result.errors if "unknown entity" in e.message.lower()]
        assert len(entity_errors) > 0

    def test_deadline_unknown_action(self, validator, minimal_spec):
        """Test deadline with unknown action function"""
        minimal_spec["state"] = {
            "test_entity": {
                "fields": {
                    "test_field": {"type": "datetime", "required": True}
                }
            }
        }
        minimal_spec["deadlines"] = {
            "test_deadline": {
                "_kind": "deadline",
                "entity": "test_entity",
                "duration": "7d",
                "startWhen": {"field": "test_field"},
                "action": "unknown_function"
            }
        }
        result = validator.validate(minimal_spec)
        action_errors = [e for e in result.errors if "unknown function" in e.message.lower()]
        assert len(action_errors) > 0

    def test_deadline_invalid_duration(self, validator, minimal_spec):
        """Test deadline with invalid duration format"""
        minimal_spec["state"] = {
            "test_entity": {
                "fields": {
                    "test_field": {"type": "datetime", "required": True}
                }
            }
        }
        minimal_spec["deadlines"] = {
            "test_deadline": {
                "_kind": "deadline",
                "entity": "test_entity",
                "duration": "invalid-format",
                "startWhen": {"field": "test_field"}
            }
        }
        result = validator.validate(minimal_spec)
        duration_errors = [e for e in result.errors if "duration" in e.message.lower()]
        assert len(duration_errors) > 0

    def test_deadline_valid_iso_duration(self, validator, minimal_spec):
        """Test deadline with valid ISO 8601 duration"""
        minimal_spec["state"] = {
            "test_entity": {
                "fields": {
                    "test_field": {"type": "datetime", "required": True}
                }
            }
        }
        minimal_spec["deadlines"] = {
            "test_deadline": {
                "_kind": "deadline",
                "entity": "test_entity",
                "duration": "P1DT2H30M",
                "startWhen": {"field": "test_field"}
            }
        }
        result = validator.validate(minimal_spec)
        duration_errors = [e for e in result.errors if "duration" in e.path.lower()]
        assert len(duration_errors) == 0

    def test_deadline_escalation_unknown_event(self, validator, minimal_spec):
        """Test deadline escalation with unknown event"""
        minimal_spec["state"] = {
            "test_entity": {
                "fields": {
                    "test_field": {"type": "datetime", "required": True}
                }
            }
        }
        minimal_spec["deadlines"] = {
            "test_deadline": {
                "_kind": "deadline",
                "entity": "test_entity",
                "duration": "24h",
                "startWhen": {"field": "test_field"},
                "escalations": [
                    {"after": "1h", "event": "unknown_event"}
                ]
            }
        }
        result = validator.validate(minimal_spec)
        event_errors = [e for e in result.errors if "unknown event" in e.message.lower()]
        assert len(event_errors) > 0


class TestPhase3Security:
    """Test Phase 3 security/role/permission validation"""

    def test_valid_role_with_entity_permissions(self, validator, minimal_spec):
        """Test valid role with entity permissions"""
        minimal_spec["state"] = {
            "test_entity": {
                "fields": {
                    "id": {"type": "string", "required": True}
                }
            }
        }
        minimal_spec["roles"] = {
            "test_role": {
                "_kind": "role",
                "description": "Test role",
                "permissions": ["view_test"],
                "entityPermissions": [
                    {"entity": "test_entity", "operations": ["read", "create"]}
                ]
            }
        }
        result = validator.validate(minimal_spec)
        role_errors = [e for e in result.errors if "role" in e.path.lower()]
        assert len(role_errors) == 0

    def test_role_circular_inheritance(self, validator, minimal_spec):
        """Test circular role inheritance detection"""
        minimal_spec["roles"] = {
            "role_a": {
                "_kind": "role",
                "inherits": ["role_b"]
            },
            "role_b": {
                "_kind": "role",
                "inherits": ["role_c"]
            },
            "role_c": {
                "_kind": "role",
                "inherits": ["role_a"]
            }
        }
        result = validator.validate(minimal_spec)
        cycle_errors = [e for e in result.errors if "circular" in e.message.lower()]
        assert len(cycle_errors) > 0

    def test_entity_permission_unknown_entity(self, validator, minimal_spec):
        """Test entity permission with unknown entity"""
        minimal_spec["roles"] = {
            "test_role": {
                "_kind": "role",
                "entityPermissions": [
                    {"entity": "unknown_entity", "operations": ["read"]}
                ]
            }
        }
        result = validator.validate(minimal_spec)
        entity_errors = [e for e in result.errors if "unknown entity" in e.message.lower()]
        assert len(entity_errors) > 0

    def test_entity_permission_invalid_operation(self, validator, minimal_spec):
        """Test entity permission with invalid operation"""
        minimal_spec["state"] = {
            "test_entity": {
                "fields": {
                    "id": {"type": "string", "required": True}
                }
            }
        }
        minimal_spec["roles"] = {
            "test_role": {
                "_kind": "role",
                "entityPermissions": [
                    {"entity": "test_entity", "operations": ["read", "invalid_op"]}
                ]
            }
        }
        result = validator.validate(minimal_spec)
        op_errors = [e for e in result.errors if "invalid operation" in e.message.lower()]
        assert len(op_errors) > 0


class TestPhase3Audit:
    """Test Phase 3 audit policy validation"""

    def test_valid_audit_policy(self, validator, minimal_spec):
        """Test valid audit policy"""
        minimal_spec["state"] = {
            "test_entity": {
                "fields": {
                    "id": {"type": "string", "required": True},
                    "status": {"type": "string", "required": True}
                }
            }
        }
        minimal_spec["auditPolicies"] = {
            "test_audit": {
                "_kind": "audit_policy",
                "entity": "test_entity",
                "operations": ["create", "update"],
                "fields": ["status"]
            }
        }
        result = validator.validate(minimal_spec)
        audit_errors = [e for e in result.errors if "audit" in e.path.lower()]
        assert len(audit_errors) == 0

    def test_audit_policy_all_fields(self, validator, minimal_spec):
        """Test audit policy with 'all' fields"""
        minimal_spec["state"] = {
            "test_entity": {
                "fields": {
                    "id": {"type": "string", "required": True}
                }
            }
        }
        minimal_spec["auditPolicies"] = {
            "test_audit": {
                "_kind": "audit_policy",
                "entity": "test_entity",
                "operations": ["create", "update", "delete"],
                "fields": ["all"]
            }
        }
        result = validator.validate(minimal_spec)
        audit_errors = [e for e in result.errors if "audit" in e.path.lower()]
        assert len(audit_errors) == 0

    def test_audit_policy_unknown_field(self, validator, minimal_spec):
        """Test audit policy with unknown field"""
        minimal_spec["state"] = {
            "test_entity": {
                "fields": {
                    "id": {"type": "string", "required": True}
                }
            }
        }
        minimal_spec["auditPolicies"] = {
            "test_audit": {
                "_kind": "audit_policy",
                "entity": "test_entity",
                "operations": ["update"],
                "fields": ["unknown_field"]
            }
        }
        result = validator.validate(minimal_spec)
        field_errors = [e for e in result.errors if "unknown field" in e.message.lower()]
        assert len(field_errors) > 0

    def test_audit_policy_invalid_operation(self, validator, minimal_spec):
        """Test audit policy with invalid operation"""
        minimal_spec["state"] = {
            "test_entity": {
                "fields": {
                    "id": {"type": "string", "required": True}
                }
            }
        }
        minimal_spec["auditPolicies"] = {
            "test_audit": {
                "_kind": "audit_policy",
                "entity": "test_entity",
                "operations": ["invalid_operation"],
                "fields": ["all"]
            }
        }
        result = validator.validate(minimal_spec)
        op_errors = [e for e in result.errors if "invalid audit operation" in e.message.lower()]
        assert len(op_errors) > 0


class TestPhase4ExternalServices:
    """Test Phase 4 external service validation"""

    def test_valid_external_service(self, validator, minimal_spec):
        """Test valid external service"""
        minimal_spec["externalServices"] = {
            "test_api": {
                "_kind": "external_service",
                "baseUrl": "https://api.example.com/v1",
                "type": "rest",
                "auth": {"type": "bearer"},
                "operations": {
                    "getData": {"method": "GET", "path": "/data"}
                }
            }
        }
        result = validator.validate(minimal_spec)
        svc_errors = [e for e in result.errors if "externalServices" in e.path]
        assert len(svc_errors) == 0

    def test_invalid_base_url(self, validator, minimal_spec):
        """Test invalid base URL format"""
        minimal_spec["externalServices"] = {
            "test_api": {
                "_kind": "external_service",
                "baseUrl": "not-a-valid-url"
            }
        }
        result = validator.validate(minimal_spec)
        url_errors = [e for e in result.errors if "url" in e.message.lower()]
        assert len(url_errors) > 0

    def test_invalid_auth_type(self, validator, minimal_spec):
        """Test invalid authentication type"""
        minimal_spec["externalServices"] = {
            "test_api": {
                "_kind": "external_service",
                "baseUrl": "https://api.example.com",
                "auth": {"type": "invalid_auth"}
            }
        }
        result = validator.validate(minimal_spec)
        auth_errors = [e for e in result.errors if "auth type" in e.message.lower()]
        assert len(auth_errors) > 0

    def test_invalid_http_method(self, validator, minimal_spec):
        """Test invalid HTTP method"""
        minimal_spec["externalServices"] = {
            "test_api": {
                "_kind": "external_service",
                "baseUrl": "https://api.example.com",
                "operations": {
                    "invalid": {"method": "INVALID"}
                }
            }
        }
        result = validator.validate(minimal_spec)
        method_errors = [e for e in result.errors if "http method" in e.message.lower()]
        assert len(method_errors) > 0


class TestPhase4DataPolicy:
    """Test Phase 4 data policy validation"""

    def test_valid_data_policy(self, validator, minimal_spec):
        """Test valid data policy"""
        minimal_spec["state"] = {
            "user": {
                "fields": {
                    "name": {"type": "string", "required": True},
                    "email": {"type": "string", "required": True}
                }
            }
        }
        minimal_spec["dataPolicies"] = {
            "user_pii": {
                "_kind": "data_policy",
                "entity": "user",
                "piiFields": ["name", "email"],
                "retention": {"period": "7 years"}
            }
        }
        result = validator.validate(minimal_spec)
        dp_errors = [e for e in result.errors if "dataPolicies" in e.path]
        assert len(dp_errors) == 0

    def test_pii_field_unknown(self, validator, minimal_spec):
        """Test PII field not found"""
        minimal_spec["state"] = {
            "user": {
                "fields": {
                    "id": {"type": "string", "required": True}
                }
            }
        }
        minimal_spec["dataPolicies"] = {
            "user_pii": {
                "_kind": "data_policy",
                "entity": "user",
                "piiFields": ["unknown_field"]
            }
        }
        result = validator.validate(minimal_spec)
        pii_errors = [e for e in result.errors if "pii field" in e.message.lower()]
        assert len(pii_errors) > 0

    def test_invalid_masking_strategy(self, validator, minimal_spec):
        """Test invalid masking strategy"""
        minimal_spec["state"] = {
            "user": {
                "fields": {
                    "ssn": {"type": "string", "required": True}
                }
            }
        }
        minimal_spec["dataPolicies"] = {
            "user_pii": {
                "_kind": "data_policy",
                "entity": "user",
                "masking": {"fields": ["ssn"], "strategy": "invalid_strategy"}
            }
        }
        result = validator.validate(minimal_spec)
        mask_errors = [e for e in result.errors if "masking strategy" in e.message.lower()]
        assert len(mask_errors) > 0

    def test_invalid_retention_format(self, validator, minimal_spec):
        """Test invalid retention period format"""
        minimal_spec["state"] = {
            "log": {
                "fields": {
                    "message": {"type": "string", "required": True}
                }
            }
        }
        minimal_spec["dataPolicies"] = {
            "log_retention": {
                "_kind": "data_policy",
                "entity": "log",
                "retention": {"period": "invalid-format"}
            }
        }
        result = validator.validate(minimal_spec)
        retention_errors = [e for e in result.errors if "retention period" in e.message.lower()]
        assert len(retention_errors) > 0


class TestPhase5Schedules:
    """Test Phase 5 schedule validation"""

    def test_valid_schedule(self, validator, minimal_spec):
        """Test valid schedule definition"""
        minimal_spec["functions"] = {
            "daily_task": {"description": "Daily task", "input": {}, "post": []}
        }
        minimal_spec["schedules"] = {
            "daily_check": {
                "_kind": "schedule",
                "cron": "0 9 * * *",
                "action": "daily_task",
                "timezone": "Asia/Tokyo"
            }
        }
        result = validator.validate(minimal_spec)
        sched_errors = [e for e in result.errors if "schedule" in e.path.lower()]
        assert len(sched_errors) == 0

    def test_invalid_cron_expression(self, validator, minimal_spec):
        """Test invalid cron expression"""
        minimal_spec["schedules"] = {
            "bad_schedule": {
                "_kind": "schedule",
                "cron": "invalid cron",
                "action": "some_func"
            }
        }
        result = validator.validate(minimal_spec)
        cron_errors = [e for e in result.errors if "cron" in e.message.lower()]
        assert len(cron_errors) > 0

    def test_schedule_unknown_action(self, validator, minimal_spec):
        """Test schedule with unknown action function"""
        minimal_spec["schedules"] = {
            "orphan_schedule": {
                "_kind": "schedule",
                "cron": "0 0 * * *",
                "action": "unknown_function"
            }
        }
        result = validator.validate(minimal_spec)
        action_errors = [e for e in result.errors if "unknown function" in e.message.lower()]
        assert len(action_errors) > 0

    def test_invalid_overlap_policy(self, validator, minimal_spec):
        """Test invalid overlap policy"""
        minimal_spec["functions"] = {
            "test_func": {"description": "Test", "input": {}, "post": []}
        }
        minimal_spec["schedules"] = {
            "bad_policy": {
                "_kind": "schedule",
                "cron": "0 0 * * *",
                "action": "test_func",
                "overlapPolicy": "invalid_policy"
            }
        }
        result = validator.validate(minimal_spec)
        policy_errors = [e for e in result.errors if "overlap policy" in e.message.lower()]
        assert len(policy_errors) > 0


class TestPhase5Constraints:
    """Test Phase 5 constraint validation"""

    def test_valid_unique_constraint(self, validator, minimal_spec):
        """Test valid unique constraint"""
        minimal_spec["state"] = {
            "user": {
                "fields": {
                    "email": {"type": "string", "required": True},
                    "tenant_id": {"type": "string", "required": True}
                }
            }
        }
        minimal_spec["constraints"] = {
            "unique_email_per_tenant": {
                "_kind": "constraint",
                "type": "unique",
                "entity": "user",
                "fields": ["email", "tenant_id"]
            }
        }
        result = validator.validate(minimal_spec)
        const_errors = [e for e in result.errors if "constraint" in e.path.lower()]
        assert len(const_errors) == 0

    def test_unique_constraint_unknown_field(self, validator, minimal_spec):
        """Test unique constraint with unknown field"""
        minimal_spec["state"] = {
            "user": {
                "fields": {
                    "email": {"type": "string", "required": True}
                }
            }
        }
        minimal_spec["constraints"] = {
            "bad_unique": {
                "_kind": "constraint",
                "type": "unique",
                "entity": "user",
                "fields": ["unknown_field"]
            }
        }
        result = validator.validate(minimal_spec)
        field_errors = [e for e in result.errors if "not found" in e.message.lower()]
        assert len(field_errors) > 0

    def test_invalid_constraint_type(self, validator, minimal_spec):
        """Test invalid constraint type"""
        minimal_spec["state"] = {
            "test_entity": {
                "fields": {"id": {"type": "string", "required": True}}
            }
        }
        minimal_spec["constraints"] = {
            "bad_type": {
                "_kind": "constraint",
                "type": "invalid_type",
                "entity": "test_entity"
            }
        }
        result = validator.validate(minimal_spec)
        type_errors = [e for e in result.errors if "constraint type" in e.message.lower()]
        assert len(type_errors) > 0


class TestPhase2_1EnumValidation:
    """Test Phase 2-1 Enum usage validation (TYP-001)"""

    def test_valid_enum_value(self, validator, minimal_spec):
        """Valid enum value should pass"""
        minimal_spec["state"] = {
            "Invoice": {
                "fields": {
                    "status": {"type": {"enum": ["draft", "open", "closed"]}}
                }
            }
        }
        minimal_spec["functions"] = {
            "test_func": {
                "description": "Test",
                "input": {},
                "pre": [{
                    "expr": {
                        "type": "binary",
                        "op": "eq",
                        "left": {"type": "ref", "path": "invoice.status"},
                        "right": {"type": "literal", "value": "open"}
                    }
                }],
                "post": []
            }
        }
        result = validator.validate(minimal_spec)
        enum_errors = [e for e in result.errors if e.code == "TYP-001"]
        assert len(enum_errors) == 0

    def test_invalid_enum_value_case_mismatch(self, validator, minimal_spec):
        """Case mismatch enum value should fail with auto-fix"""
        minimal_spec["state"] = {
            "Invoice": {
                "fields": {
                    "status": {"type": {"enum": ["draft", "open", "closed"]}}
                }
            }
        }
        minimal_spec["functions"] = {
            "test_func": {
                "description": "Test",
                "input": {},
                "pre": [{
                    "expr": {
                        "type": "binary",
                        "op": "eq",
                        "left": {"type": "ref", "path": "invoice.status"},
                        "right": {"type": "literal", "value": "OPEN"}
                    }
                }],
                "post": []
            }
        }
        result = validator.validate(minimal_spec)
        enum_errors = [e for e in result.errors if e.code == "TYP-001"]
        assert len(enum_errors) > 0
        # Should be auto-fixable
        assert enum_errors[0].auto_fixable
        assert enum_errors[0].fix_patch is not None
        assert enum_errors[0].expected == "open"
        assert enum_errors[0].actual == "OPEN"
        assert "open" in enum_errors[0].valid_options

    def test_invalid_enum_value_no_match(self, validator, minimal_spec):
        """Completely invalid enum value should fail without auto-fix"""
        minimal_spec["state"] = {
            "Invoice": {
                "fields": {
                    "status": {"type": {"enum": ["draft", "open", "closed"]}}
                }
            }
        }
        minimal_spec["functions"] = {
            "test_func": {
                "description": "Test",
                "input": {},
                "pre": [{
                    "expr": {
                        "type": "binary",
                        "op": "eq",
                        "left": {"type": "ref", "path": "invoice.status"},
                        "right": {"type": "literal", "value": "invalid_status"}
                    }
                }],
                "post": []
            }
        }
        result = validator.validate(minimal_spec)
        enum_errors = [e for e in result.errors if e.code == "TYP-001"]
        assert len(enum_errors) > 0
        # Should NOT be auto-fixable
        assert not enum_errors[0].auto_fixable
        assert enum_errors[0].fix_patch is None

    def test_enum_validation_in_invariant(self, validator, minimal_spec):
        """Enum validation should work in invariants"""
        minimal_spec["state"] = {
            "Order": {
                "fields": {
                    "priority": {"type": {"enum": ["low", "medium", "high"]}}
                }
            }
        }
        minimal_spec["invariants"] = [{
            "id": "priority_check",
            "description": "Check priority",
            "assert": {
                "type": "binary",
                "op": "ne",
                "left": {"type": "ref", "path": "order.priority"},
                "right": {"type": "literal", "value": "HIGH"}
            }
        }]
        result = validator.validate(minimal_spec)
        enum_errors = [e for e in result.errors if e.code == "TYP-001"]
        assert len(enum_errors) > 0
        assert enum_errors[0].auto_fixable
        assert enum_errors[0].expected == "high"

    def test_enum_validation_reversed_comparison(self, validator, minimal_spec):
        """Enum validation should work when literal is on left side"""
        minimal_spec["state"] = {
            "Task": {
                "fields": {
                    "state": {"type": {"enum": ["pending", "active", "done"]}}
                }
            }
        }
        minimal_spec["derived"] = {
            "is_active": {
                "entity": "Task",
                "formula": {
                    "type": "binary",
                    "op": "eq",
                    "left": {"type": "literal", "value": "ACTIVE"},
                    "right": {"type": "ref", "path": "task.state"}
                }
            }
        }
        result = validator.validate(minimal_spec)
        enum_errors = [e for e in result.errors if e.code == "TYP-001"]
        assert len(enum_errors) > 0
        assert "left.value" in enum_errors[0].path

    def test_enum_validation_in_state_machine_guard(self, validator, minimal_spec):
        """Enum validation should work in state machine guards"""
        minimal_spec["state"] = {
            "Document": {
                "fields": {
                    "approval_status": {"type": {"enum": ["pending", "approved", "rejected"]}}
                }
            }
        }
        minimal_spec["functions"] = {
            "approve": {"description": "Approve", "input": {}, "post": []}
        }
        minimal_spec["stateMachines"] = {
            "doc_flow": {
                "entity": "Document",
                "field": "status",
                "initial": "draft",
                "states": {"draft": {}, "submitted": {}},
                "transitions": [{
                    "from": "draft",
                    "to": "submitted",
                    "trigger_function": "approve",
                    "guard": {
                        "type": "binary",
                        "op": "eq",
                        "left": {"type": "ref", "path": "document.approval_status"},
                        "right": {"type": "literal", "value": "APPROVED"}
                    }
                }]
            }
        }
        result = validator.validate(minimal_spec)
        enum_errors = [e for e in result.errors if e.code == "TYP-001"]
        assert len(enum_errors) > 0

    def test_no_enum_validation_for_non_enum_field(self, validator, minimal_spec):
        """Non-enum fields should not trigger enum validation"""
        minimal_spec["state"] = {
            "User": {
                "fields": {
                    "name": {"type": "string"}
                }
            }
        }
        minimal_spec["functions"] = {
            "check_name": {
                "description": "Check",
                "input": {},
                "pre": [{
                    "expr": {
                        "type": "binary",
                        "op": "eq",
                        "left": {"type": "ref", "path": "user.name"},
                        "right": {"type": "literal", "value": "AnyValue"}
                    }
                }],
                "post": []
            }
        }
        result = validator.validate(minimal_spec)
        enum_errors = [e for e in result.errors if e.code == "TYP-001"]
        assert len(enum_errors) == 0

    def test_multiple_enum_errors(self, validator, minimal_spec):
        """Multiple enum errors should all be reported"""
        minimal_spec["state"] = {
            "Item": {
                "fields": {
                    "status": {"type": {"enum": ["active", "inactive"]}}
                }
            }
        }
        minimal_spec["functions"] = {
            "check": {
                "description": "Check",
                "input": {},
                "pre": [
                    {
                        "expr": {
                            "type": "binary",
                            "op": "eq",
                            "left": {"type": "ref", "path": "item.status"},
                            "right": {"type": "literal", "value": "ACTIVE"}
                        }
                    },
                    {
                        "expr": {
                            "type": "binary",
                            "op": "eq",
                            "left": {"type": "ref", "path": "item.status"},
                            "right": {"type": "literal", "value": "INACTIVE"}
                        }
                    }
                ],
                "post": []
            }
        }
        result = validator.validate(minimal_spec)
        enum_errors = [e for e in result.errors if e.code == "TYP-001"]
        assert len(enum_errors) == 2


class TestPhase2_2FunctionTypeConsistency:
    """Test Phase 2-2 Function input/output type consistency (TYP-002)"""

    def test_valid_input_reference(self, validator, minimal_spec):
        """Valid input reference should pass"""
        minimal_spec["functions"] = {
            "create_invoice": {
                "description": "Create invoice",
                "input": {
                    "amount": {"type": "int"},
                    "customer_id": {"type": "string"}
                },
                "pre": [{
                    "expr": {
                        "type": "binary",
                        "op": "gt",
                        "left": {"type": "input", "name": "amount"},
                        "right": {"type": "literal", "value": 0}
                    }
                }],
                "post": []
            }
        }
        result = validator.validate(minimal_spec)
        type_errors = [e for e in result.errors if e.code == "TYP-002"]
        assert len(type_errors) == 0

    def test_invalid_input_reference(self, validator, minimal_spec):
        """Reference to undeclared input should fail"""
        minimal_spec["functions"] = {
            "create_invoice": {
                "description": "Create invoice",
                "input": {
                    "amount": {"type": "int"}
                },
                "pre": [{
                    "expr": {
                        "type": "binary",
                        "op": "gt",
                        "left": {"type": "input", "name": "nonexistent_input"},
                        "right": {"type": "literal", "value": 0}
                    }
                }],
                "post": []
            }
        }
        result = validator.validate(minimal_spec)
        type_errors = [e for e in result.errors if e.code == "TYP-002"]
        assert len(type_errors) > 0
        assert "nonexistent_input" in type_errors[0].message

    def test_type_mismatch_in_action(self, validator, minimal_spec):
        """Type mismatch between input and entity field should fail"""
        minimal_spec["state"] = {
            "Invoice": {
                "fields": {
                    "amount": {"type": "int"},
                    "status": {"type": "string"}
                }
            }
        }
        minimal_spec["functions"] = {
            "create_invoice": {
                "description": "Create invoice",
                "input": {
                    "id": {"type": "string"},
                    "amount": {"type": "string"}  # Wrong type - should be int
                },
                "post": [{
                    "action": {
                        "create": "Invoice",
                        "target": {"type": "input", "name": "id"},
                        "with": {
                            "amount": {"type": "input", "name": "amount"}
                        }
                    }
                }]
            }
        }
        result = validator.validate(minimal_spec)
        type_errors = [e for e in result.errors if e.code == "TYP-002"]
        assert len(type_errors) > 0
        assert "Type mismatch" in type_errors[0].message

    def test_valid_input_in_post_action(self, validator, minimal_spec):
        """Valid input reference in post action should pass"""
        minimal_spec["state"] = {
            "Invoice": {
                "fields": {
                    "amount": {"type": "int"}
                }
            }
        }
        minimal_spec["functions"] = {
            "update_invoice": {
                "description": "Update invoice",
                "input": {
                    "id": {"type": "string"},
                    "new_amount": {"type": "int"}
                },
                "post": [{
                    "action": {
                        "update": "Invoice",
                        "target": {"type": "input", "name": "id"},
                        "set": {
                            "amount": {"type": "input", "name": "new_amount"}
                        }
                    }
                }]
            }
        }
        result = validator.validate(minimal_spec)
        type_errors = [e for e in result.errors if e.code == "TYP-002"]
        assert len(type_errors) == 0


class TestPhase2_3TransitionConflicts:
    """Test Phase 2-3 Transition conflict detection (TRANS-001)"""

    def test_no_conflict_single_transition(self, validator, minimal_spec):
        """Single transition per state+trigger should pass"""
        minimal_spec["functions"] = {
            "submit": {"description": "Submit", "input": {}, "post": []}
        }
        minimal_spec["stateMachines"] = {
            "order_sm": {
                "entity": "Order",
                "field": "status",
                "initial": "DRAFT",
                "states": {"DRAFT": {}, "SUBMITTED": {}},
                "transitions": [
                    {"from": "DRAFT", "to": "SUBMITTED", "trigger_function": "submit"}
                ]
            }
        }
        result = validator.validate(minimal_spec)
        conflict_errors = [e for e in result.errors if e.code == "TRANS-001"]
        assert len(conflict_errors) == 0

    def test_conflict_unguarded_transitions(self, validator, minimal_spec):
        """Multiple unguarded transitions from same state+trigger should fail"""
        minimal_spec["functions"] = {
            "process": {"description": "Process", "input": {}, "post": []}
        }
        minimal_spec["stateMachines"] = {
            "item_sm": {
                "entity": "Item",
                "field": "status",
                "initial": "NEW",
                "states": {"NEW": {}, "ACTIVE": {}, "CLOSED": {}},
                "transitions": [
                    {"from": "NEW", "to": "ACTIVE", "trigger_function": "process"},
                    {"from": "NEW", "to": "CLOSED", "trigger_function": "process"}
                ]
            }
        }
        result = validator.validate(minimal_spec)
        conflict_errors = [e for e in result.errors if e.code == "TRANS-001"]
        assert len(conflict_errors) > 0
        assert "conflict" in conflict_errors[0].message.lower()

    def test_no_conflict_with_guards(self, validator, minimal_spec):
        """Guarded transitions should not trigger conflict"""
        minimal_spec["functions"] = {
            "process": {"description": "Process", "input": {}, "post": []}
        }
        minimal_spec["stateMachines"] = {
            "item_sm": {
                "entity": "Item",
                "field": "status",
                "initial": "NEW",
                "states": {"NEW": {}, "ACTIVE": {}, "CLOSED": {}},
                "transitions": [
                    {
                        "from": "NEW",
                        "to": "ACTIVE",
                        "trigger_function": "process",
                        "guard": {"type": "literal", "value": True}
                    },
                    {
                        "from": "NEW",
                        "to": "CLOSED",
                        "trigger_function": "process",
                        "guard": {"type": "literal", "value": False}
                    }
                ]
            }
        }
        result = validator.validate(minimal_spec)
        conflict_errors = [e for e in result.errors if e.code == "TRANS-001"]
        assert len(conflict_errors) == 0


class TestPhase2_4ReferencePaths:
    """Test Phase 2-4 Reference path validation (REF-002)"""

    def test_valid_simple_path(self, validator, minimal_spec):
        """Simple entity.field path should pass"""
        minimal_spec["state"] = {
            "Invoice": {
                "fields": {
                    "amount": {"type": "int"}
                }
            }
        }
        minimal_spec["functions"] = {
            "check": {
                "description": "Check",
                "input": {},
                "pre": [{
                    "expr": {
                        "type": "binary",
                        "op": "gt",
                        "left": {"type": "ref", "path": "invoice.amount"},
                        "right": {"type": "literal", "value": 0}
                    }
                }],
                "post": []
            }
        }
        result = validator.validate(minimal_spec)
        ref_errors = [e for e in result.errors if e.code == "REF-002"]
        assert len(ref_errors) == 0

    def test_invalid_field_in_path(self, validator, minimal_spec):
        """Reference to non-existent field should fail"""
        minimal_spec["state"] = {
            "Invoice": {
                "fields": {
                    "amount": {"type": "int"}
                }
            }
        }
        minimal_spec["functions"] = {
            "check": {
                "description": "Check",
                "input": {},
                "pre": [{
                    "expr": {
                        "type": "binary",
                        "op": "gt",
                        "left": {"type": "ref", "path": "invoice.nonexistent_field"},
                        "right": {"type": "literal", "value": 0}
                    }
                }],
                "post": []
            }
        }
        result = validator.validate(minimal_spec)
        ref_errors = [e for e in result.errors if e.code == "REF-002"]
        assert len(ref_errors) > 0
        assert "nonexistent_field" in ref_errors[0].message

    def test_valid_nested_path(self, validator, minimal_spec):
        """Valid nested path through relations should pass"""
        minimal_spec["state"] = {
            "Order": {
                "fields": {
                    "customer_id": {"type": {"ref": "Customer"}}
                }
            },
            "Customer": {
                "fields": {
                    "name": {"type": "string"}
                }
            }
        }
        minimal_spec["derived"] = {
            "customer_name": {
                "entity": "Order",
                "returns": "string",
                "formula": {"type": "ref", "path": "order.customer_id"}
            }
        }
        result = validator.validate(minimal_spec)
        ref_errors = [e for e in result.errors if e.code == "REF-002"]
        assert len(ref_errors) == 0


class TestPhase3_1DepthLimit:
    """Test Phase 3-1 Depth limit validation (VAL-DEPTH)"""

    def _make_deep_expr(self, depth: int) -> dict:
        """Create a deeply nested expression"""
        if depth == 0:
            return {"type": "literal", "value": 1}
        return {
            "type": "binary",
            "op": "add",
            "left": self._make_deep_expr(depth - 1),
            "right": {"type": "literal", "value": 1}
        }

    def test_shallow_expression_valid(self, validator, minimal_spec):
        """Shallow expression (depth 5) should pass"""
        minimal_spec["derived"] = {
            "shallow": {
                "entity": "Test",
                "returns": "int",
                "formula": self._make_deep_expr(5)
            }
        }
        result = validator.validate(minimal_spec)
        depth_errors = [e for e in result.errors if e.code == "VAL-DEPTH"]
        assert len(depth_errors) == 0

    def test_deep_expression_fails(self, validator, minimal_spec):
        """Very deep expression (depth 60) should fail with VAL-DEPTH"""
        minimal_spec["derived"] = {
            "deep": {
                "entity": "Test",
                "returns": "int",
                "formula": self._make_deep_expr(60)
            }
        }
        result = validator.validate(minimal_spec)
        depth_errors = [e for e in result.errors if e.code == "VAL-DEPTH"]
        assert len(depth_errors) > 0
        assert "depth" in depth_errors[0].message.lower()

    def test_boundary_depth(self, validator, minimal_spec):
        """Expression at exactly max depth (50) should pass"""
        minimal_spec["derived"] = {
            "boundary": {
                "entity": "Test",
                "returns": "int",
                "formula": self._make_deep_expr(50)
            }
        }
        result = validator.validate(minimal_spec)
        depth_errors = [e for e in result.errors if e.code == "VAL-DEPTH"]
        assert len(depth_errors) == 0

    def test_over_boundary_depth(self, validator, minimal_spec):
        """Expression at max depth + 1 (51) should fail"""
        minimal_spec["derived"] = {
            "over_boundary": {
                "entity": "Test",
                "returns": "int",
                "formula": self._make_deep_expr(51)
            }
        }
        result = validator.validate(minimal_spec)
        depth_errors = [e for e in result.errors if e.code == "VAL-DEPTH"]
        assert len(depth_errors) > 0


class TestPhase3_2Performance:
    """Test Phase 3-2 Performance optimization (caching)"""

    def test_cache_enabled_by_default(self, validator):
        """Validator should have cache enabled by default"""
        assert validator._cache is not None

    def test_cache_can_be_disabled(self):
        """Validator should allow disabling cache"""
        from the_mesh.core.validator import MeshValidator
        v = MeshValidator(enable_cache=False)
        assert v._cache is None

    def test_entity_cache_populated(self, validator, minimal_spec):
        """Entity cache should be populated during validation"""
        minimal_spec["state"] = {
            "Invoice": {
                "fields": {
                    "amount": {"type": "int"},
                    "status": {"type": {"enum": ["draft", "open", "closed"]}}
                }
            }
        }
        validator.validate(minimal_spec)
        assert "Invoice" in validator._cache.entity_fields_cache
        assert "amount" in validator._cache.entity_fields_cache["Invoice"]

    def test_reference_cache_used(self, validator, minimal_spec):
        """Reference cache should be used for repeated paths"""
        minimal_spec["state"] = {
            "Invoice": {
                "fields": {
                    "amount": {"type": "int"}
                }
            }
        }
        # Add multiple refs to the same path
        minimal_spec["functions"] = {
            "check1": {
                "description": "Check 1",
                "input": {},
                "pre": [{"expr": {"type": "ref", "path": "invoice.amount"}}],
                "post": []
            },
            "check2": {
                "description": "Check 2",
                "input": {},
                "pre": [{"expr": {"type": "ref", "path": "invoice.amount"}}],
                "post": []
            }
        }
        validator.validate(minimal_spec)
        # Cache should have been used
        assert validator._cache.hits > 0

    def test_large_spec_performance(self, validator, minimal_spec):
        """Large spec should validate in reasonable time"""
        import time

        # Create a spec with many entities and fields
        entities = {}
        for i in range(50):
            entities[f"Entity{i}"] = {
                "fields": {
                    f"field{j}": {"type": "string"} for j in range(10)
                }
            }
        minimal_spec["state"] = entities

        # Add functions that reference fields
        minimal_spec["functions"] = {}
        for i in range(20):
            minimal_spec["functions"][f"func{i}"] = {
                "description": f"Function {i}",
                "input": {},
                "pre": [{"expr": {"type": "ref", "path": f"entity{i % 50}.field{i % 10}"}}],
                "post": []
            }

        start = time.time()
        result = validator.validate(minimal_spec)
        elapsed = time.time() - start

        # Should complete in under 5 seconds even for larger specs
        assert elapsed < 5.0, f"Validation took too long: {elapsed:.2f}s"


class TestPhase0_3AutoFix:
    """Test Phase 0-3 Auto-fix suggestion functionality"""

    def test_find_closest_match_exact(self):
        """Exact case-insensitive match should be found"""
        result = find_closest_match("OPEN", ["draft", "open", "closed"])
        assert result == "open"

    def test_find_closest_match_prefix(self):
        """Prefix match should be found"""
        result = find_closest_match("dra", ["draft", "open", "closed"])
        assert result == "draft"

    def test_find_closest_match_substring(self):
        """Substring match should be found"""
        result = find_closest_match("aft", ["draft", "open", "closed"])
        assert result == "draft"

    def test_find_closest_match_fallback(self):
        """Should return first option as fallback"""
        result = find_closest_match("xyz", ["draft", "open", "closed"])
        assert result == "draft"

    def test_suggest_fix_for_enum_error(self):
        """Should suggest fix for enum value error"""
        error = ValidationError(
            path="functions.check.pre[0].expr.right",
            message="Invalid enum value",
            code="TYP-001",
            actual="OPEN",
            valid_options=["draft", "open", "closed"]
        )
        fix = suggest_fix_for_error(error)
        assert fix is not None
        assert fix["op"] == "replace"
        assert fix["value"] == "open"
        assert "OPEN" in fix["reason"]

    def test_suggest_fix_for_reference_error(self):
        """Should suggest fix for invalid reference"""
        error = ValidationError(
            path="functions.check.pre[0].expr",
            message="Invalid reference path",
            code="REF-002",
            actual="amnt",
            valid_options=["amount", "status", "created_at"]
        )
        fix = suggest_fix_for_error(error)
        assert fix is not None
        assert fix["op"] == "replace"
        assert "amount" in fix["reason"]

    def test_generate_fix_patches_integration(self, validator, minimal_spec):
        """Integration test: generate_fix_patches should work with validation result"""
        minimal_spec["state"] = {
            "Invoice": {
                "fields": {
                    "status": {"type": {"enum": ["draft", "open", "closed"]}}
                }
            }
        }
        minimal_spec["functions"] = {
            "check": {
                "description": "Check",
                "input": {},
                "pre": [{
                    "expr": {
                        "type": "binary",
                        "op": "eq",
                        "left": {"type": "ref", "path": "invoice.status"},
                        "right": {"type": "literal", "value": "OPEN"}  # Wrong case
                    }
                }],
                "post": []
            }
        }
        result = validator.validate(minimal_spec)
        enum_errors = [e for e in result.errors if e.code == "TYP-001"]
        if enum_errors:
            patches = generate_fix_patches(enum_errors)
            assert len(patches) > 0


class TestPhase0_4Completions:
    """Test Phase 0-4 Completion suggestion functionality"""

    def test_suggest_missing_meta_fields(self):
        """Should suggest missing meta fields"""
        partial_spec = {}
        suggestions = suggest_completions(partial_spec)
        meta_suggestions = [s for s in suggestions if s["path"].startswith("/meta")]
        assert len(meta_suggestions) >= 3  # id, version, title

    def test_suggest_missing_saga_forward(self):
        """Should suggest missing forward field in saga step"""
        partial_spec = {
            "meta": {"id": "test", "version": "1.0", "title": "Test"},
            "sagas": {
                "payment": {
                    "steps": [
                        {"name": "step1"}  # Missing forward
                    ]
                }
            }
        }
        suggestions = suggest_completions(partial_spec)
        forward_suggestions = [s for s in suggestions if "forward" in s["path"]]
        assert len(forward_suggestions) > 0
        assert forward_suggestions[0]["suggestion"] == "step1_action"

    def test_suggest_missing_function_description(self):
        """Should suggest missing function description"""
        partial_spec = {
            "meta": {"id": "test", "version": "1.0", "title": "Test"},
            "functions": {
                "create_invoice": {}  # Missing description and input
            }
        }
        suggestions = suggest_completions(partial_spec)
        desc_suggestions = [s for s in suggestions if "description" in s["path"]]
        assert len(desc_suggestions) > 0

    def test_suggest_missing_state_machine_initial(self):
        """Should suggest missing initial state"""
        partial_spec = {
            "meta": {"id": "test", "version": "1.0", "title": "Test"},
            "stateMachines": {
                "order_lifecycle": {
                    "states": {"DRAFT": {}, "OPEN": {}, "CLOSED": {}}
                    # Missing initial
                }
            }
        }
        suggestions = suggest_completions(partial_spec)
        initial_suggestions = [s for s in suggestions if "initial" in s["path"]]
        assert len(initial_suggestions) > 0
        assert initial_suggestions[0]["suggestion"] == "DRAFT"  # First state

    def test_suggest_missing_derived_returns(self):
        """Should suggest missing returns field in derived formula"""
        partial_spec = {
            "meta": {"id": "test", "version": "1.0", "title": "Test"},
            "derived": {
                "total": {
                    "formula": {"type": "literal", "value": 0}
                    # Missing entity and returns
                }
            }
        }
        suggestions = suggest_completions(partial_spec)
        returns_suggestions = [s for s in suggestions if "returns" in s["path"]]
        assert len(returns_suggestions) > 0

    def test_no_suggestions_for_complete_spec(self, sample_spec):
        """Complete spec should have minimal suggestions"""
        suggestions = suggest_completions(sample_spec)
        # A complete spec may still have some optional suggestions
        # but should not have critical missing field suggestions
        critical_fields = ["forward", "initial", "description"]
        critical_suggestions = [s for s in suggestions
                               if any(f in s["reason"] for f in critical_fields)]
        # Should be minimal or none
        assert len(critical_suggestions) < 5


class TestPhase0_5IncrementalValidation:
    """Test Phase 0-5 Incremental validation functionality"""

    def test_validate_changes_replace_operation(self, minimal_spec):
        """Should validate after applying replace operation"""
        minimal_spec["functions"] = {
            "test_func": {
                "description": "Test function",
                "input": {},
                "post": []
            }
        }
        changes = [
            {"op": "replace", "path": "/functions/test_func/description", "value": "Updated description"}
        ]
        result = validate_changes(minimal_spec, changes)
        # Should be valid after change
        func_errors = [e for e in result.errors if "test_func" in e.path]
        assert len(func_errors) == 0

    def test_validate_changes_add_operation(self, minimal_spec):
        """Should validate after applying add operation"""
        changes = [
            {"op": "add", "path": "/functions", "value": {
                "new_func": {
                    "description": "New function",
                    "input": {},
                    "post": []
                }
            }}
        ]
        result = validate_changes(minimal_spec, changes)
        # Should be valid after adding function
        assert isinstance(result, ValidationResult)

    def test_validate_changes_remove_operation(self, minimal_spec):
        """Should validate after applying remove operation"""
        minimal_spec["functions"] = {
            "func1": {"description": "Func 1", "input": {}, "post": []},
            "func2": {"description": "Func 2", "input": {}, "post": []}
        }
        changes = [
            {"op": "remove", "path": "/functions/func2"}
        ]
        result = validate_changes(minimal_spec, changes)
        # Should be valid after removal
        assert isinstance(result, ValidationResult)

    def test_validate_changes_invalid_patch_ignored(self, minimal_spec):
        """Invalid patch paths should be ignored"""
        changes = [
            {"op": "replace", "path": "/nonexistent/path/deep", "value": "ignored"}
        ]
        result = validate_changes(minimal_spec, changes)
        # Should not crash, returns validation result
        assert isinstance(result, ValidationResult)

    def test_validate_changes_detects_new_errors(self, minimal_spec):
        """Should detect errors introduced by changes"""
        minimal_spec["state"] = {
            "Invoice": {
                "fields": {
                    "status": {"type": {"enum": ["draft", "open", "closed"]}}
                }
            }
        }
        minimal_spec["functions"] = {
            "check": {
                "description": "Check",
                "input": {},
                "pre": [{
                    "expr": {
                        "type": "binary",
                        "op": "eq",
                        "left": {"type": "ref", "path": "invoice.status"},
                        "right": {"type": "literal", "value": "open"}  # Valid
                    }
                }],
                "post": []
            }
        }
        # First validate - should be valid
        result1 = validate_changes(minimal_spec, [])
        enum_errors1 = [e for e in result1.errors if e.code == "TYP-001"]

        # Now change to invalid enum value
        changes = [
            {"op": "replace", "path": "/functions/check/pre/0/expr/right/value", "value": "INVALID"}
        ]
        result2 = validate_changes(minimal_spec, changes)
        enum_errors2 = [e for e in result2.errors if e.code == "TYP-001"]
        assert len(enum_errors2) > len(enum_errors1)

    def test_validate_changes_with_provided_validator(self, validator, minimal_spec):
        """Should use provided validator instance"""
        changes = []
        result = validate_changes(minimal_spec, changes, validator=validator)
        assert isinstance(result, ValidationResult)


class TestPhase5Sagas:
    """Test Phase 5 saga validation"""

    def test_valid_saga(self, validator, minimal_spec):
        """Test valid saga definition"""
        minimal_spec["functions"] = {
            "step1_action": {"description": "Step 1", "input": {}, "post": []},
            "step1_compensate": {"description": "Compensate 1", "input": {}, "post": []}
        }
        minimal_spec["sagas"] = {
            "test_saga": {
                "_kind": "saga",
                "steps": [
                    {"name": "step1", "forward": "step1_action", "compensate": "step1_compensate"}
                ],
                "onFailure": "compensate_all"
            }
        }
        result = validator.validate(minimal_spec)
        saga_errors = [e for e in result.errors if "saga" in e.path.lower()]
        assert len(saga_errors) == 0

    def test_saga_duplicate_step_name(self, validator, minimal_spec):
        """Test saga with duplicate step names"""
        minimal_spec["functions"] = {
            "action1": {"description": "Action", "input": {}, "post": []}
        }
        minimal_spec["sagas"] = {
            "dup_saga": {
                "_kind": "saga",
                "steps": [
                    {"name": "step1", "forward": "action1"},
                    {"name": "step1", "forward": "action1"}
                ]
            }
        }
        result = validator.validate(minimal_spec)
        dup_errors = [e for e in result.errors if "duplicate" in e.message.lower()]
        assert len(dup_errors) > 0

    def test_saga_unknown_compensation(self, validator, minimal_spec):
        """Test saga with unknown compensation function"""
        minimal_spec["functions"] = {
            "action1": {"description": "Action", "input": {}, "post": []}
        }
        minimal_spec["sagas"] = {
            "bad_comp_saga": {
                "_kind": "saga",
                "steps": [
                    {"name": "step1", "forward": "action1", "compensate": "unknown_compensate"}
                ]
            }
        }
        result = validator.validate(minimal_spec)
        comp_errors = [e for e in result.errors if "compensate" in e.message.lower()]
        assert len(comp_errors) > 0

    def test_saga_invalid_failure_policy(self, validator, minimal_spec):
        """Test saga with invalid failure policy"""
        minimal_spec["functions"] = {
            "action1": {"description": "Action", "input": {}, "post": []}
        }
        minimal_spec["sagas"] = {
            "bad_policy_saga": {
                "_kind": "saga",
                "steps": [
                    {"name": "step1", "forward": "action1"}
                ],
                "onFailure": "invalid_policy"
            }
        }
        result = validator.validate(minimal_spec)
        policy_errors = [e for e in result.errors if "failure policy" in e.message.lower()]
        assert len(policy_errors) > 0


def run_tests_without_pytest():
    """Run tests without pytest"""
    import inspect

    test_classes = [
        TestBasicValidation,
        TestVAL001DiscriminatorValidation,
        TestVAL003TriggerValidation,
        TestVAL004ReachabilityAnalysis,
        TestVAL006BidirectionalReferences,
        TestReferenceValidation,
        TestCycleDetection,
        TestPhase1ExpressionTypes,
        TestPhase2Gateways,
        TestPhase2Deadlines,
        TestPhase2_1EnumValidation,
        TestPhase2_2FunctionTypeConsistency,
        TestPhase2_3TransitionConflicts,
        TestPhase2_4ReferencePaths,
        TestPhase3_1DepthLimit,
        TestPhase3_2Performance,
        TestPhase0_3AutoFix,
        TestPhase0_4Completions,
        TestPhase0_5IncrementalValidation,
        TestPhase3Security,
        TestPhase3Audit,
        TestPhase4ExternalServices,
        TestPhase4DataPolicy,
        TestPhase5Schedules,
        TestPhase5Constraints,
        TestPhase5Sagas
    ]

    passed = 0
    failed = 0
    errors = []

    for test_class in test_classes:
        print(f'\n=== {test_class.__name__} ===')
        instance = test_class()

        for method_name in dir(test_class):
            if not method_name.startswith('test_'):
                continue

            method = getattr(instance, method_name)
            sig = inspect.signature(method)
            params = list(sig.parameters.keys())

            kwargs = {}
            if 'validator' in params:
                kwargs['validator'] = validator()
            if 'minimal_spec' in params:
                kwargs['minimal_spec'] = minimal_spec()
            if 'sample_spec' in params:
                kwargs['sample_spec'] = sample_spec()

            try:
                method(**kwargs)
                print(f'  PASS: {method_name}')
                passed += 1
            except AssertionError as e:
                print(f'  FAIL: {method_name}')
                print(f'        AssertionError: {e}')
                failed += 1
                errors.append((test_class.__name__, method_name, str(e)))
            except Exception as e:
                print(f'  ERROR: {method_name}')
                print(f'         {type(e).__name__}: {e}')
                failed += 1
                errors.append((test_class.__name__, method_name, f'{type(e).__name__}: {e}'))

    print(f'\n\n=== SUMMARY ===')
    print(f'Passed: {passed}')
    print(f'Failed: {failed}')
    print(f'Total:  {passed + failed}')

    if failed > 0:
        print('\nFailed tests:')
        for cls, name, err in errors:
            print(f'  {cls}.{name}: {err}')
        return False
    return True


if __name__ == "__main__":
    if HAS_PYTEST:
        import pytest
        pytest.main([__file__, "-v"])
    else:
        print("pytest not available, running with simple test runner")
        success = run_tests_without_pytest()
        sys.exit(0 if success else 1)
