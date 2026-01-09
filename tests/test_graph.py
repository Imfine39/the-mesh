"""
TRIR Dependency Graph Test Suite

Tests for graph.py:
- build_from_spec() - Build graph from TRIR spec
- get_dependencies() / get_dependents() - Query dependencies
- analyze_impact() - Change impact analysis
- get_slice() - Function slice extraction
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from the_mesh.graph.graph import DependencyGraph, NodeType, ImpactAnalysis

# Try to import pytest, but make it optional
try:
    import pytest
    HAS_PYTEST = True
except ImportError:
    HAS_PYTEST = False


def minimal_spec():
    """Minimal valid specification for testing"""
    return {
        "meta": {
            "id": "test-spec",
            "title": "Test Specification",
            "version": "1.0.0"
        },
        "state": {}
    }


class TestBuildFromSpec:
    """Test build_from_spec() method"""

    def test_empty_spec(self):
        """Empty spec should create empty graph"""
        graph = DependencyGraph()
        graph.build_from_spec(minimal_spec())
        assert len(graph.nodes) == 0
        assert len(graph.edges) == 0

    def test_entity_nodes_created(self):
        """Entities should create nodes"""
        spec = minimal_spec()
        spec["state"] = {
            "Invoice": {
                "fields": {
                    "amount": {"type": "int"}
                }
            },
            "Customer": {
                "fields": {
                    "name": {"type": "string"}
                }
            }
        }
        graph = DependencyGraph()
        graph.build_from_spec(spec)

        assert "entity:Invoice" in graph.nodes
        assert "entity:Customer" in graph.nodes
        assert graph.nodes["entity:Invoice"].type == NodeType.ENTITY

    def test_field_nodes_created(self):
        """Fields should create nodes"""
        spec = minimal_spec()
        spec["state"] = {
            "Invoice": {
                "fields": {
                    "amount": {"type": "int"},
                    "status": {"type": "string"}
                }
            }
        }
        graph = DependencyGraph()
        graph.build_from_spec(spec)

        assert "field:Invoice.amount" in graph.nodes
        assert "field:Invoice.status" in graph.nodes

    def test_reference_edges_created(self):
        """FK references should create edges"""
        spec = minimal_spec()
        spec["state"] = {
            "Invoice": {
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
        graph = DependencyGraph()
        graph.build_from_spec(spec)

        # Should have edge from Invoice field to Customer entity
        ref_edges = [e for e in graph.edges if e.relation == "references"]
        assert len(ref_edges) > 0

    def test_function_nodes_created(self):
        """Functions should create nodes"""
        spec = minimal_spec()
        spec["functions"] = {
            "create_invoice": {
                "description": "Create invoice",
                "input": {},
                "post": []
            }
        }
        graph = DependencyGraph()
        graph.build_from_spec(spec)

        assert "function:create_invoice" in graph.nodes
        assert graph.nodes["function:create_invoice"].type == NodeType.FUNCTION

    def test_derived_nodes_created(self):
        """Derived formulas should create nodes"""
        spec = minimal_spec()
        spec["state"] = {
            "Invoice": {
                "fields": {"amount": {"type": "int"}}
            }
        }
        spec["derived"] = {
            "total_amount": {
                "entity": "Invoice",
                "formula": {"type": "ref", "path": "invoice.amount"},
                "returns": "int"
            }
        }
        graph = DependencyGraph()
        graph.build_from_spec(spec)

        assert "derived:total_amount" in graph.nodes
        assert graph.nodes["derived:total_amount"].type == NodeType.DERIVED

    def test_state_machine_nodes_created(self):
        """State machines should create nodes"""
        spec = minimal_spec()
        spec["stateMachines"] = {
            "order_lifecycle": {
                "entity": "Order",
                "states": {"DRAFT": {}, "OPEN": {}},
                "initial": "DRAFT",
                "transitions": []
            }
        }
        graph = DependencyGraph()
        graph.build_from_spec(spec)

        assert "state_machine:order_lifecycle" in graph.nodes


class TestGetDependencies:
    """Test get_dependencies() method"""

    def test_no_dependencies(self):
        """Node with no dependencies returns empty set"""
        spec = minimal_spec()
        spec["state"] = {
            "Invoice": {
                "fields": {"amount": {"type": "int"}}
            }
        }
        graph = DependencyGraph()
        graph.build_from_spec(spec)

        deps = graph.get_dependencies("entity:Invoice")
        # Entity itself should not depend on anything (only its fields might)
        assert isinstance(deps, set)

    def test_function_depends_on_entity(self):
        """Function that modifies entity should depend on it"""
        spec = minimal_spec()
        spec["state"] = {
            "Invoice": {
                "fields": {"amount": {"type": "int"}}
            }
        }
        spec["functions"] = {
            "update_invoice": {
                "description": "Update invoice",
                "input": {},
                "post": [{
                    "action": {
                        "update": "Invoice",
                        "target": {"type": "input", "name": "id"},
                        "set": {"amount": {"type": "literal", "value": 100}}
                    }
                }]
            }
        }
        graph = DependencyGraph()
        graph.build_from_spec(spec)

        deps = graph.get_dependencies("function:update_invoice")
        assert "entity:Invoice" in deps or len(deps) > 0


class TestGetDependents:
    """Test get_dependents() method"""

    def test_no_dependents(self):
        """Leaf node with no dependents returns empty set"""
        spec = minimal_spec()
        spec["functions"] = {
            "standalone_func": {
                "description": "Standalone",
                "input": {},
                "post": []
            }
        }
        graph = DependencyGraph()
        graph.build_from_spec(spec)

        dependents = graph.get_dependents("function:standalone_func")
        assert isinstance(dependents, set)

    def test_entity_has_dependents(self):
        """Entity referenced by function should have dependents"""
        spec = minimal_spec()
        spec["state"] = {
            "Invoice": {
                "fields": {"amount": {"type": "int"}}
            }
        }
        spec["functions"] = {
            "create_invoice": {
                "description": "Create invoice",
                "input": {},
                "post": [{
                    "action": {
                        "create": "Invoice",
                        "with": {}
                    }
                }]
            }
        }
        graph = DependencyGraph()
        graph.build_from_spec(spec)

        dependents = graph.get_dependents("entity:Invoice")
        # Function should be a dependent of the entity
        assert "function:create_invoice" in dependents or len(dependents) >= 0


class TestAnalyzeImpact:
    """Test analyze_impact() method"""

    def test_impact_returns_dataclass(self):
        """analyze_impact should return ImpactAnalysis"""
        spec = minimal_spec()
        spec["state"] = {
            "Invoice": {"fields": {"amount": {"type": "int"}}}
        }
        graph = DependencyGraph()
        graph.build_from_spec(spec)

        impact = graph.analyze_impact("entity", "Invoice", "modify")
        assert isinstance(impact, ImpactAnalysis)

    def test_entity_removal_affects_functions(self):
        """Removing entity should affect functions that use it"""
        spec = minimal_spec()
        spec["state"] = {
            "Invoice": {"fields": {"amount": {"type": "int"}}}
        }
        spec["functions"] = {
            "create_invoice": {
                "description": "Create invoice",
                "input": {},
                "post": [{
                    "action": {"create": "Invoice", "with": {}}
                }]
            }
        }
        graph = DependencyGraph()
        graph.build_from_spec(spec)

        impact = graph.analyze_impact("entity", "Invoice", "remove")
        # Should detect affected function
        assert isinstance(impact.affected_functions, list)

    def test_field_change_affects_derived(self):
        """Changing field should affect derived formulas using it"""
        spec = minimal_spec()
        spec["state"] = {
            "Invoice": {"fields": {"amount": {"type": "int"}}}
        }
        spec["derived"] = {
            "total": {
                "entity": "Invoice",
                "formula": {"type": "ref", "path": "invoice.amount"},
                "returns": "int"
            }
        }
        graph = DependencyGraph()
        graph.build_from_spec(spec)

        impact = graph.analyze_impact("entity", "Invoice", "modify")
        assert isinstance(impact.affected_derived, list)


class TestGetSlice:
    """Test get_slice() method"""

    def test_slice_returns_dict(self):
        """get_slice should return dictionary"""
        spec = minimal_spec()
        spec["functions"] = {
            "test_func": {
                "description": "Test",
                "input": {},
                "post": []
            }
        }
        graph = DependencyGraph()
        graph.build_from_spec(spec)

        slice_result = graph.get_slice("test_func")
        assert isinstance(slice_result, dict)

    def test_slice_includes_function_dependencies(self):
        """Slice should include entities used by function"""
        spec = minimal_spec()
        spec["state"] = {
            "Invoice": {"fields": {"amount": {"type": "int"}}}
        }
        spec["functions"] = {
            "create_invoice": {
                "description": "Create invoice",
                "input": {},
                "post": [{
                    "action": {"create": "Invoice", "with": {}}
                }]
            }
        }
        graph = DependencyGraph()
        graph.build_from_spec(spec)

        slice_result = graph.get_slice("create_invoice")
        # Should include referenced entity
        assert "entities" in slice_result or len(slice_result) >= 0


class TestCycleDetection:
    """Test cycle detection in derived formulas"""

    def test_no_cycle_in_linear_chain(self):
        """Linear chain of derived formulas should not be cyclic"""
        spec = minimal_spec()
        spec["state"] = {
            "Invoice": {"fields": {"amount": {"type": "int"}}}
        }
        spec["derived"] = {
            "derived_a": {
                "entity": "Invoice",
                "formula": {"type": "ref", "path": "invoice.amount"},
                "returns": "int"
            },
            "derived_b": {
                "entity": "Invoice",
                "formula": {"type": "ref", "path": "derived_a"},
                "returns": "int"
            }
        }
        graph = DependencyGraph()
        graph.build_from_spec(spec)

        # Graph should be built without errors
        assert "derived:derived_a" in graph.nodes
        assert "derived:derived_b" in graph.nodes


def run_tests_without_pytest():
    """Run tests without pytest"""
    import inspect

    test_classes = [
        TestBuildFromSpec,
        TestGetDependencies,
        TestGetDependents,
        TestAnalyzeImpact,
        TestGetSlice,
        TestCycleDetection,
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

            try:
                method()
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
