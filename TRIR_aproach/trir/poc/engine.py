"""TRIR Engine - Core implementation"""

import json
from pathlib import Path
from typing import Any
from dataclasses import dataclass

from .validator import TRIRValidator, ValidationResult
from .graph import DependencyGraph, ImpactAnalysis


@dataclass
class ToolResult:
    success: bool
    id: str | None = None
    error: str | None = None
    warnings: list[str] | None = None
    data: Any = None


class TRIREngine:
    """Main TRIR Engine for managing specifications"""

    def __init__(self, schema_dir: Path | None = None):
        self.spec: dict[str, Any] = self._empty_spec()
        self.validator = TRIRValidator(schema_dir)
        self.graph = DependencyGraph()
        self._dirty = False

    def _empty_spec(self) -> dict[str, Any]:
        return {
            "meta": {"id": "", "title": "", "version": "0.1.0"},
            "state": {},
            "derived": {},
            "functions": {},
            "scenarios": {},
            "invariants": []
        }

    def load(self, path: Path) -> ToolResult:
        """Load spec from file"""
        try:
            with open(path) as f:
                self.spec = json.load(f)
            self._rebuild_graph()
            return ToolResult(success=True, data={"loaded": str(path)})
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def load_json(self, spec: dict[str, Any]) -> ToolResult:
        """Load spec from dict"""
        self.spec = spec
        self._rebuild_graph()
        return ToolResult(success=True)

    def save(self, path: Path) -> ToolResult:
        """Save spec to file"""
        try:
            with open(path, "w") as f:
                json.dump(self.spec, f, indent=2, ensure_ascii=False)
            self._dirty = False
            return ToolResult(success=True, data={"saved": str(path)})
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def validate(self) -> ValidationResult:
        """Validate the current spec"""
        return self.validator.validate(self.spec)

    def _rebuild_graph(self):
        """Rebuild dependency graph from spec"""
        self.graph.build_from_spec(self.spec)

    # ========== Tool Implementations ==========

    def create_entity(
        self,
        name: str,
        fields: dict[str, Any],
        description: str = ""
    ) -> ToolResult:
        """Create a new entity"""
        if name in self.spec["state"]:
            return ToolResult(success=False, error=f"Entity '{name}' already exists")

        entity = {"fields": fields}
        if description:
            entity["description"] = description

        self.spec["state"][name] = entity
        self._dirty = True
        self._rebuild_graph()

        return ToolResult(success=True, id=f"entity:{name}")

    def add_field(
        self,
        entity: str,
        name: str,
        field_type: Any,
        required: bool = True,
        description: str = ""
    ) -> ToolResult:
        """Add a field to an entity"""
        if entity not in self.spec["state"]:
            return ToolResult(success=False, error=f"Entity '{entity}' does not exist")

        field_def = {"type": field_type, "required": required}
        if description:
            field_def["description"] = description

        self.spec["state"][entity]["fields"][name] = field_def
        self._dirty = True
        self._rebuild_graph()

        return ToolResult(success=True, id=f"field:{entity}.{name}")

    def create_function(
        self,
        name: str,
        input_fields: dict[str, Any],
        description: str = "",
        implements: list[str] | None = None
    ) -> ToolResult:
        """Create a new function"""
        if name in self.spec["functions"]:
            return ToolResult(success=False, error=f"Function '{name}' already exists")

        func = {"input": input_fields}
        if description:
            func["description"] = description
        if implements:
            func["implements"] = implements

        self.spec["functions"][name] = func
        self._dirty = True
        self._rebuild_graph()

        return ToolResult(success=True, id=f"function:{name}")

    def add_precondition(
        self,
        function: str,
        expr: dict[str, Any],
        entity: str | None = None,
        reason: str = ""
    ) -> ToolResult:
        """Add a precondition to a function"""
        if function not in self.spec["functions"]:
            return ToolResult(success=False, error=f"Function '{function}' does not exist")

        pre = {"expr": expr}
        if entity:
            pre["entity"] = entity
        if reason:
            pre["reason"] = reason

        if "pre" not in self.spec["functions"][function]:
            self.spec["functions"][function]["pre"] = []

        self.spec["functions"][function]["pre"].append(pre)
        self._dirty = True
        self._rebuild_graph()

        idx = len(self.spec["functions"][function]["pre"]) - 1
        return ToolResult(success=True, id=f"function:{function}.pre[{idx}]")

    def add_error_case(
        self,
        function: str,
        code: str,
        when: dict[str, Any],
        reason: str = "",
        http_status: int = 409
    ) -> ToolResult:
        """Add an error case to a function"""
        if function not in self.spec["functions"]:
            return ToolResult(success=False, error=f"Function '{function}' does not exist")

        error = {"code": code, "when": when, "http_status": http_status}
        if reason:
            error["reason"] = reason

        if "error" not in self.spec["functions"][function]:
            self.spec["functions"][function]["error"] = []

        self.spec["functions"][function]["error"].append(error)
        self._dirty = True
        self._rebuild_graph()

        idx = len(self.spec["functions"][function]["error"]) - 1
        return ToolResult(success=True, id=f"function:{function}.error[{idx}]")

    def add_post_action(
        self,
        function: str,
        action: dict[str, Any],
        condition: dict[str, Any] | None = None,
        reason: str = ""
    ) -> ToolResult:
        """Add a post-action to a function"""
        if function not in self.spec["functions"]:
            return ToolResult(success=False, error=f"Function '{function}' does not exist")

        post = {"action": action}
        if condition:
            post["condition"] = condition
        if reason:
            post["reason"] = reason

        if "post" not in self.spec["functions"][function]:
            self.spec["functions"][function]["post"] = []

        self.spec["functions"][function]["post"].append(post)
        self._dirty = True
        self._rebuild_graph()

        idx = len(self.spec["functions"][function]["post"]) - 1
        return ToolResult(success=True, id=f"function:{function}.post[{idx}]")

    def create_derived(
        self,
        name: str,
        entity: str,
        formula: dict[str, Any],
        description: str = "",
        returns: str | None = None
    ) -> ToolResult:
        """Create a derived formula"""
        if name in self.spec["derived"]:
            return ToolResult(success=False, error=f"Derived '{name}' already exists")

        derived = {"entity": entity, "formula": formula}
        if description:
            derived["description"] = description
        if returns:
            derived["returns"] = returns

        self.spec["derived"][name] = derived
        self._dirty = True
        self._rebuild_graph()

        return ToolResult(success=True, id=f"derived:{name}")

    def create_scenario(
        self,
        id: str,
        title: str,
        given: dict[str, Any],
        when: dict[str, Any],
        then: dict[str, Any],
        verifies: list[str] | None = None
    ) -> ToolResult:
        """Create a test scenario"""
        if id in self.spec["scenarios"]:
            return ToolResult(success=False, error=f"Scenario '{id}' already exists")

        scenario = {"title": title, "given": given, "when": when, "then": then}
        if verifies:
            scenario["verifies"] = verifies

        self.spec["scenarios"][id] = scenario
        self._dirty = True
        self._rebuild_graph()

        return ToolResult(success=True, id=f"scenario:{id}")

    def create_invariant(
        self,
        id: str,
        entity: str,
        expr: dict[str, Any],
        description: str = ""
    ) -> ToolResult:
        """Create an invariant"""
        # Check for duplicate
        for inv in self.spec["invariants"]:
            if inv.get("id") == id:
                return ToolResult(success=False, error=f"Invariant '{id}' already exists")

        invariant = {"id": id, "entity": entity, "expr": expr}
        if description:
            invariant["description"] = description

        self.spec["invariants"].append(invariant)
        self._dirty = True
        self._rebuild_graph()

        return ToolResult(success=True, id=f"invariant:{id}")

    # ========== Analysis Tools ==========

    def analyze_impact(
        self,
        target_type: str,
        target_name: str,
        change_type: str = "modify"
    ) -> ImpactAnalysis:
        """Analyze impact of a change"""
        return self.graph.analyze_impact(target_type, target_name, change_type)

    def get_slice(self, function_name: str) -> dict[str, list[str]]:
        """Get minimal spec slice for implementing a function"""
        return self.graph.get_slice(function_name)

    def get_slice_spec(self, function_name: str) -> dict[str, Any]:
        """Get actual spec data for a function slice"""
        slice_info = self.get_slice(function_name)

        if "error" in slice_info:
            return slice_info

        return {
            "function": self.spec["functions"].get(function_name, {}),
            "entities": {
                name: self.spec["state"][name]
                for name in slice_info["entities"]
                if name in self.spec["state"]
            },
            "derived": {
                name: self.spec["derived"][name]
                for name in slice_info["derived"]
                if name in self.spec["derived"]
            },
            "scenarios": {
                name: self.spec["scenarios"][name]
                for name in slice_info["scenarios"]
                if name in self.spec["scenarios"]
            },
            "invariants": [
                inv for inv in self.spec["invariants"]
                if inv.get("id") in slice_info["invariants"]
            ]
        }

    def export_mermaid(self) -> str:
        """Export dependency graph as Mermaid diagram"""
        return self.graph.to_mermaid()
