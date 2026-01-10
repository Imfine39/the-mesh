"""Tests for Frontend Validation (FE-002 through FE-005)"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.validator import MeshValidator


class TestFrontendViewValidation:
    """Test FE-002 and FE-003: View validation"""

    def setup_method(self):
        self.validator = MeshValidator()

    def test_valid_view(self):
        """Test that valid view passes validation"""
        spec = {
            "meta": {"id": "test", "title": "Test", "version": "1.0.0"},
            "state": {
                "invoice": {
                    "fields": {
                        "id": {"type": "string"},
                        "amount": {"type": "int"},
                        "status": {"type": {"enum": ["open", "closed"]}}
                    }
                }
            },
            "functions": {
                "close_invoice": {
                    "input": {"invoice_id": {"type": "string"}}
                }
            },
            "views": {
                "InvoiceList": {
                    "entity": "invoice",
                    "type": "list",
                    "fields": [
                        {"name": "id", "label": "ID"},
                        {"name": "amount", "format": "currency"}
                    ],
                    "actions": [
                        {"name": "close", "function": "close_invoice"}
                    ]
                }
            }
        }
        result = self.validator.validate(spec)
        # Filter for FE-002 and FE-003 errors
        fe_errors = [e for e in result.errors if e.code and e.code.startswith("FE-")]
        assert len(fe_errors) == 0

    def test_fe002_invalid_entity_reference(self):
        """Test FE-002: View references unknown entity"""
        spec = {
            "meta": {"id": "test", "title": "Test", "version": "1.0.0"},
            "state": {
                "invoice": {"fields": {"id": {"type": "string"}}}
            },
            "views": {
                "CustomerList": {
                    "entity": "customer",  # Does not exist
                    "type": "list"
                }
            }
        }
        result = self.validator.validate(spec)
        fe002_errors = [e for e in result.errors if e.code == "FE-002"]
        assert len(fe002_errors) >= 1
        assert "customer" in fe002_errors[0].message

    def test_fe002_invalid_field_reference(self):
        """Test FE-002: View field references unknown entity field"""
        spec = {
            "meta": {"id": "test", "title": "Test", "version": "1.0.0"},
            "state": {
                "invoice": {
                    "fields": {
                        "id": {"type": "string"},
                        "amount": {"type": "int"}
                    }
                }
            },
            "views": {
                "InvoiceList": {
                    "entity": "invoice",
                    "type": "list",
                    "fields": [
                        {"name": "id"},
                        {"name": "nonexistent_field"}  # Does not exist
                    ]
                }
            }
        }
        result = self.validator.validate(spec)
        fe002_errors = [e for e in result.errors if e.code == "FE-002"]
        assert len(fe002_errors) >= 1
        assert "nonexistent_field" in fe002_errors[0].message

    def test_fe002_invalid_filter_field(self):
        """Test FE-002: View filter references unknown field"""
        spec = {
            "meta": {"id": "test", "title": "Test", "version": "1.0.0"},
            "state": {
                "invoice": {"fields": {"id": {"type": "string"}}}
            },
            "views": {
                "InvoiceList": {
                    "entity": "invoice",
                    "type": "list",
                    "filters": [
                        {"field": "unknown_filter_field", "type": "text"}
                    ]
                }
            }
        }
        result = self.validator.validate(spec)
        fe002_errors = [e for e in result.errors if e.code == "FE-002"]
        assert len(fe002_errors) >= 1
        assert "unknown_filter_field" in fe002_errors[0].message

    def test_fe002_invalid_sort_field(self):
        """Test FE-002: View defaultSort references unknown field"""
        spec = {
            "meta": {"id": "test", "title": "Test", "version": "1.0.0"},
            "state": {
                "invoice": {"fields": {"id": {"type": "string"}}}
            },
            "views": {
                "InvoiceList": {
                    "entity": "invoice",
                    "type": "list",
                    "defaultSort": {"field": "unknown_sort", "direction": "asc"}
                }
            }
        }
        result = self.validator.validate(spec)
        fe002_errors = [e for e in result.errors if e.code == "FE-002"]
        assert len(fe002_errors) >= 1
        assert "unknown_sort" in fe002_errors[0].message

    def test_fe003_invalid_function_reference(self):
        """Test FE-003: View action references unknown function"""
        spec = {
            "meta": {"id": "test", "title": "Test", "version": "1.0.0"},
            "state": {
                "invoice": {"fields": {"id": {"type": "string"}}}
            },
            "functions": {
                "close_invoice": {"input": {"id": {"type": "string"}}}
            },
            "views": {
                "InvoiceList": {
                    "entity": "invoice",
                    "type": "list",
                    "actions": [
                        {"name": "delete", "function": "delete_invoice"}  # Does not exist
                    ]
                }
            }
        }
        result = self.validator.validate(spec)
        fe003_errors = [e for e in result.errors if e.code == "FE-003"]
        assert len(fe003_errors) >= 1
        assert "delete_invoice" in fe003_errors[0].message


class TestFrontendRouteValidation:
    """Test FE-004: Route validation"""

    def setup_method(self):
        self.validator = MeshValidator()

    def test_valid_route(self):
        """Test that valid route passes validation"""
        spec = {
            "meta": {"id": "test", "title": "Test", "version": "1.0.0"},
            "state": {
                "invoice": {"fields": {"id": {"type": "string"}}}
            },
            "views": {
                "InvoiceList": {"entity": "invoice", "type": "list"}
            },
            "roles": {
                "admin": {"permissions": ["invoice:read"]}
            },
            "routes": {
                "/invoices": {
                    "view": "InvoiceList",
                    "guards": [
                        {"type": "role", "role": "admin"}
                    ]
                }
            }
        }
        result = self.validator.validate(spec)
        fe004_errors = [e for e in result.errors if e.code == "FE-004"]
        assert len(fe004_errors) == 0

    def test_fe004_invalid_view_reference(self):
        """Test FE-004: Route references unknown view"""
        spec = {
            "meta": {"id": "test", "title": "Test", "version": "1.0.0"},
            "state": {
                "invoice": {"fields": {"id": {"type": "string"}}}
            },
            "views": {
                "InvoiceList": {"entity": "invoice", "type": "list"}
            },
            "routes": {
                "/customers": {
                    "view": "CustomerList"  # Does not exist
                }
            }
        }
        result = self.validator.validate(spec)
        fe004_errors = [e for e in result.errors if e.code == "FE-004"]
        assert len(fe004_errors) >= 1
        assert "CustomerList" in fe004_errors[0].message

    def test_fe004_invalid_role_in_guard(self):
        """Test FE-004: Route guard references unknown role"""
        spec = {
            "meta": {"id": "test", "title": "Test", "version": "1.0.0"},
            "state": {
                "invoice": {"fields": {"id": {"type": "string"}}}
            },
            "views": {
                "InvoiceList": {"entity": "invoice", "type": "list"}
            },
            "roles": {
                "admin": {"permissions": []}
            },
            "routes": {
                "/invoices": {
                    "view": "InvoiceList",
                    "guards": [
                        {"type": "role", "role": "super_admin"}  # Does not exist
                    ]
                }
            }
        }
        result = self.validator.validate(spec)
        fe004_errors = [e for e in result.errors if e.code == "FE-004"]
        assert len(fe004_errors) >= 1
        assert "super_admin" in fe004_errors[0].message

    def test_fe004_invalid_permission_in_guard(self):
        """Test FE-004: Route guard references unknown permission"""
        spec = {
            "meta": {"id": "test", "title": "Test", "version": "1.0.0"},
            "state": {
                "invoice": {"fields": {"id": {"type": "string"}}}
            },
            "views": {
                "InvoiceList": {"entity": "invoice", "type": "list"}
            },
            "roles": {
                "admin": {"permissions": ["invoice:read", "invoice:write"]}
            },
            "routes": {
                "/invoices": {
                    "view": "InvoiceList",
                    "guards": [
                        {"type": "permission", "permission": "invoice:delete"}  # Not defined
                    ]
                }
            }
        }
        result = self.validator.validate(spec)
        fe004_errors = [e for e in result.errors if e.code == "FE-004"]
        assert len(fe004_errors) >= 1
        assert "invoice:delete" in fe004_errors[0].message


class TestUnusedFunctionWarning:
    """Test FE-005: Unused function detection"""

    def setup_method(self):
        self.validator = MeshValidator()

    def test_no_warning_when_function_used_in_view(self):
        """Test that used functions don't generate warning"""
        spec = {
            "meta": {"id": "test", "title": "Test", "version": "1.0.0"},
            "state": {
                "invoice": {"fields": {"id": {"type": "string"}}}
            },
            "functions": {
                "close_invoice": {"input": {"id": {"type": "string"}}}
            },
            "views": {
                "InvoiceList": {
                    "entity": "invoice",
                    "type": "list",
                    "actions": [
                        {"name": "close", "function": "close_invoice"}
                    ]
                }
            }
        }
        result = self.validator.validate(spec)
        fe005_warnings = [w for w in result.warnings if w.code == "FE-005"]
        assert len(fe005_warnings) == 0

    def test_warning_for_unused_function(self):
        """Test FE-005: Warning for function not used in any view"""
        spec = {
            "meta": {"id": "test", "title": "Test", "version": "1.0.0"},
            "state": {
                "invoice": {"fields": {"id": {"type": "string"}}}
            },
            "functions": {
                "close_invoice": {"input": {"id": {"type": "string"}}},
                "delete_invoice": {"input": {"id": {"type": "string"}}}  # Not used
            },
            "views": {
                "InvoiceList": {
                    "entity": "invoice",
                    "type": "list",
                    "actions": [
                        {"name": "close", "function": "close_invoice"}
                    ]
                }
            }
        }
        result = self.validator.validate(spec)
        fe005_warnings = [w for w in result.warnings if w.code == "FE-005"]
        assert len(fe005_warnings) >= 1
        assert "delete_invoice" in fe005_warnings[0].message

    def test_no_warning_when_function_used_in_subscription(self):
        """Test that functions used in subscriptions don't generate warning"""
        spec = {
            "meta": {"id": "test", "title": "Test", "version": "1.0.0"},
            "state": {
                "invoice": {"fields": {"id": {"type": "string"}}}
            },
            "functions": {
                "handle_invoice_created": {"input": {"id": {"type": "string"}}}
            },
            "events": {
                "invoice_created": {"payload": {"invoice_id": {"type": "string"}}}
            },
            "subscriptions": {
                "on_invoice_created": {
                    "event": "invoice_created",
                    "handler": "handle_invoice_created"
                }
            },
            "views": {
                "InvoiceList": {"entity": "invoice", "type": "list"}
            }
        }
        result = self.validator.validate(spec)
        fe005_warnings = [w for w in result.warnings if w.code == "FE-005"]
        # handle_invoice_created should not be in warnings
        unused_names = [w.path.split(".")[-1] for w in fe005_warnings]
        assert "handle_invoice_created" not in unused_names

    def test_no_warning_when_function_used_in_saga(self):
        """Test that functions used in sagas don't generate warning"""
        spec = {
            "meta": {"id": "test", "title": "Test", "version": "1.0.0"},
            "state": {
                "order": {"fields": {"id": {"type": "string"}}}
            },
            "functions": {
                "create_order": {"input": {"id": {"type": "string"}}},
                "rollback_order": {"input": {"id": {"type": "string"}}}
            },
            "sagas": {
                "order_saga": {
                    "steps": [
                        {"name": "create", "forward": "create_order", "compensate": "rollback_order"}
                    ]
                }
            },
            "views": {
                "OrderList": {"entity": "order", "type": "list"}
            }
        }
        result = self.validator.validate(spec)
        fe005_warnings = [w for w in result.warnings if w.code == "FE-005"]
        unused_names = [w.path.split(".")[-1] for w in fe005_warnings]
        assert "create_order" not in unused_names
        assert "rollback_order" not in unused_names

    def test_no_warning_when_function_used_in_schedule(self):
        """Test that functions used in schedules don't generate warning"""
        spec = {
            "meta": {"id": "test", "title": "Test", "version": "1.0.0"},
            "state": {
                "report": {"fields": {"id": {"type": "string"}}}
            },
            "functions": {
                "generate_report": {"input": {}}
            },
            "schedules": {
                "daily_report": {
                    "cron": "0 0 * * *",
                    "action": "generate_report"
                }
            },
            "views": {
                "ReportList": {"entity": "report", "type": "list"}
            }
        }
        result = self.validator.validate(spec)
        fe005_warnings = [w for w in result.warnings if w.code == "FE-005"]
        unused_names = [w.path.split(".")[-1] for w in fe005_warnings]
        assert "generate_report" not in unused_names

    def test_no_warning_when_no_views_defined(self):
        """Test that no warning when views section is empty"""
        spec = {
            "meta": {"id": "test", "title": "Test", "version": "1.0.0"},
            "state": {
                "invoice": {"fields": {"id": {"type": "string"}}}
            },
            "functions": {
                "some_function": {"input": {}}
            }
            # No views defined
        }
        result = self.validator.validate(spec)
        fe005_warnings = [w for w in result.warnings if w.code == "FE-005"]
        # No warning because there are no views to check against
        assert len(fe005_warnings) == 0

    def test_private_functions_not_warned(self):
        """Test that private functions (starting with _) are not warned"""
        spec = {
            "meta": {"id": "test", "title": "Test", "version": "1.0.0"},
            "state": {
                "invoice": {"fields": {"id": {"type": "string"}}}
            },
            "functions": {
                "_internal_helper": {"input": {}},  # Private function
                "public_unused": {"input": {}}  # Should warn
            },
            "views": {
                "InvoiceList": {"entity": "invoice", "type": "list"}
            }
        }
        result = self.validator.validate(spec)
        fe005_warnings = [w for w in result.warnings if w.code == "FE-005"]
        unused_names = [w.path.split(".")[-1] for w in fe005_warnings]
        assert "_internal_helper" not in unused_names
        assert "public_unused" in unused_names


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
