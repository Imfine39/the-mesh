"""TRIR Dependency Graph"""

from dataclasses import dataclass, field
from typing import Any
from enum import Enum


class NodeType(Enum):
    ENTITY = "entity"
    FIELD = "field"
    DERIVED = "derived"
    FUNCTION = "function"
    SCENARIO = "scenario"
    INVARIANT = "invariant"


@dataclass
class Node:
    id: str
    type: NodeType
    name: str
    data: dict = field(default_factory=dict)


@dataclass
class Edge:
    source: str
    target: str
    relation: str  # "references", "uses", "modifies", "tests"


@dataclass
class ImpactAnalysis:
    affected_entities: list[str]
    affected_functions: list[str]
    affected_derived: list[str]
    affected_scenarios: list[str]
    affected_invariants: list[str]
    breaking_changes: list[dict]


class DependencyGraph:
    """Builds and queries dependency graph from TRIR spec"""

    def __init__(self):
        self.nodes: dict[str, Node] = {}
        self.edges: list[Edge] = []
        self._adjacency: dict[str, list[str]] = {}
        self._reverse_adjacency: dict[str, list[str]] = {}

    def build_from_spec(self, spec: dict[str, Any]):
        """Build dependency graph from TRIR specification"""
        self.nodes.clear()
        self.edges.clear()
        self._adjacency.clear()
        self._reverse_adjacency.clear()

        # Add entity nodes
        for name, entity in spec.get("state", {}).items():
            self._add_node(Node(
                id=f"entity:{name}",
                type=NodeType.ENTITY,
                name=name,
                data=entity
            ))

            # Add field nodes and FK edges
            for field_name, field_def in entity.get("fields", {}).items():
                field_id = f"field:{name}.{field_name}"
                self._add_node(Node(
                    id=field_id,
                    type=NodeType.FIELD,
                    name=f"{name}.{field_name}",
                    data=field_def
                ))
                self._add_edge(Edge(field_id, f"entity:{name}", "belongs_to"))

                # FK reference
                field_type = field_def.get("type", {})
                if isinstance(field_type, dict) and "ref" in field_type:
                    ref_target = field_type["ref"]
                    self._add_edge(Edge(field_id, f"entity:{ref_target}", "references"))

        # Add derived nodes
        for name, derived in spec.get("derived", {}).items():
            node_id = f"derived:{name}"
            self._add_node(Node(
                id=node_id,
                type=NodeType.DERIVED,
                name=name,
                data=derived
            ))

            # Link to entity
            if "entity" in derived:
                self._add_edge(Edge(node_id, f"entity:{derived['entity']}", "applies_to"))

            # Extract dependencies from formula
            if "formula" in derived:
                deps = self._extract_expr_deps(derived["formula"])
                for dep in deps["entities"]:
                    self._add_edge(Edge(node_id, f"entity:{dep}", "reads"))
                for dep in deps["derived"]:
                    self._add_edge(Edge(node_id, f"derived:{dep}", "calls"))

        # Add function nodes
        for name, func in spec.get("functions", {}).items():
            node_id = f"function:{name}"
            self._add_node(Node(
                id=node_id,
                type=NodeType.FUNCTION,
                name=name,
                data=func
            ))

            # Extract dependencies from pre/error/post
            all_exprs = []
            for pre in func.get("pre", []):
                if "expr" in pre:
                    all_exprs.append(pre["expr"])
                if "entity" in pre:
                    self._add_edge(Edge(node_id, f"entity:{pre['entity']}", "reads"))

            for err in func.get("error", []):
                if "when" in err:
                    all_exprs.append(err["when"])

            for post in func.get("post", []):
                action = post.get("action", {})
                for action_type in ["create", "update", "delete"]:
                    if action_type in action:
                        self._add_edge(Edge(node_id, f"entity:{action[action_type]}", "modifies"))
                if "condition" in post:
                    all_exprs.append(post["condition"])

            for expr in all_exprs:
                deps = self._extract_expr_deps(expr)
                for dep in deps["entities"]:
                    self._add_edge(Edge(node_id, f"entity:{dep}", "reads"))
                for dep in deps["derived"]:
                    self._add_edge(Edge(node_id, f"derived:{dep}", "calls"))

        # Add scenario nodes
        for name, scenario in spec.get("scenarios", {}).items():
            node_id = f"scenario:{name}"
            self._add_node(Node(
                id=node_id,
                type=NodeType.SCENARIO,
                name=name,
                data=scenario
            ))

            # Link to function being tested
            if "when" in scenario and "call" in scenario["when"]:
                func_name = scenario["when"]["call"]
                self._add_edge(Edge(node_id, f"function:{func_name}", "tests"))

            # Link to entities in given
            for entity_name in scenario.get("given", {}).keys():
                if f"entity:{entity_name}" in self.nodes:
                    self._add_edge(Edge(node_id, f"entity:{entity_name}", "uses"))

        # Add invariant nodes
        for inv in spec.get("invariants", []):
            inv_id = inv.get("id", "")
            node_id = f"invariant:{inv_id}"
            self._add_node(Node(
                id=node_id,
                type=NodeType.INVARIANT,
                name=inv_id,
                data=inv
            ))

            if "entity" in inv:
                self._add_edge(Edge(node_id, f"entity:{inv['entity']}", "constrains"))

            if "expr" in inv:
                deps = self._extract_expr_deps(inv["expr"])
                for dep in deps["derived"]:
                    self._add_edge(Edge(node_id, f"derived:{dep}", "uses"))

    def _add_node(self, node: Node):
        self.nodes[node.id] = node
        if node.id not in self._adjacency:
            self._adjacency[node.id] = []
        if node.id not in self._reverse_adjacency:
            self._reverse_adjacency[node.id] = []

    def _add_edge(self, edge: Edge):
        if edge.target not in self.nodes:
            return  # Skip edges to non-existent nodes

        self.edges.append(edge)
        if edge.source not in self._adjacency:
            self._adjacency[edge.source] = []
        self._adjacency[edge.source].append(edge.target)

        if edge.target not in self._reverse_adjacency:
            self._reverse_adjacency[edge.target] = []
        self._reverse_adjacency[edge.target].append(edge.source)

    def _extract_expr_deps(self, expr: Any) -> dict[str, set[str]]:
        """Extract entity and derived dependencies from an expression (Tagged Union format)"""
        deps = {"entities": set(), "derived": set()}

        def walk(e: Any):
            if not isinstance(e, dict):
                return

            expr_type = e.get("type")

            # Field reference: { "type": "ref", "path": "entity.field" }
            if expr_type == "ref":
                path = e.get("path", "")
                parts = path.split(".")
                if len(parts) >= 1 and parts[0] not in ("item", "self"):
                    deps["entities"].add(parts[0])

            # Aggregation: { "type": "agg", "from": "entity", ... }
            if expr_type == "agg" and "from" in e:
                deps["entities"].add(e["from"])

            # Function call: { "type": "call", "name": "fn", ... }
            if expr_type == "call":
                deps["derived"].add(e.get("name", ""))

            # Recurse
            for v in e.values():
                if isinstance(v, dict):
                    walk(v)
                elif isinstance(v, list):
                    for item in v:
                        walk(item)

        walk(expr)
        return deps

    def analyze_impact(
        self,
        target_type: str,
        target_name: str,
        change_type: str = "modify"
    ) -> ImpactAnalysis:
        """Analyze impact of a change"""
        target_id = f"{target_type}:{target_name}"

        if target_id not in self.nodes:
            return ImpactAnalysis([], [], [], [], [], [
                {"target": target_id, "reason": "Target not found"}
            ])

        # Find all nodes that depend on the target (reverse traversal)
        affected = self._get_affected_nodes(target_id)

        # Categorize affected nodes
        result = ImpactAnalysis(
            affected_entities=[],
            affected_functions=[],
            affected_derived=[],
            affected_scenarios=[],
            affected_invariants=[],
            breaking_changes=[]
        )

        for node_id in affected:
            node = self.nodes.get(node_id)
            if not node:
                continue

            if node.type == NodeType.ENTITY:
                result.affected_entities.append(node.name)
            elif node.type == NodeType.FUNCTION:
                result.affected_functions.append(node.name)
            elif node.type == NodeType.DERIVED:
                result.affected_derived.append(node.name)
            elif node.type == NodeType.SCENARIO:
                result.affected_scenarios.append(node.name)
            elif node.type == NodeType.INVARIANT:
                result.affected_invariants.append(node.name)

        # Detect breaking changes
        if change_type == "delete":
            for node_id in affected:
                node = self.nodes.get(node_id)
                if node and node.type in (NodeType.FUNCTION, NodeType.DERIVED):
                    result.breaking_changes.append({
                        "target": node.name,
                        "reason": f"Depends on deleted {target_type} '{target_name}'"
                    })

        return result

    def _get_affected_nodes(self, start_id: str) -> set[str]:
        """Get all nodes affected by a change (reverse BFS)"""
        affected = set()
        queue = [start_id]

        while queue:
            current = queue.pop(0)
            if current in affected:
                continue
            affected.add(current)

            # Add all nodes that depend on current
            for dep in self._reverse_adjacency.get(current, []):
                if dep not in affected:
                    queue.append(dep)

        return affected

    def get_slice(self, function_name: str) -> dict[str, list[str]]:
        """Get minimal spec slice for implementing a function"""
        func_id = f"function:{function_name}"

        if func_id not in self.nodes:
            return {"error": f"Function '{function_name}' not found"}

        # Forward traversal to get dependencies
        deps = self._get_dependencies(func_id)

        # Find scenarios that test this function
        scenarios = []
        for node_id, node in self.nodes.items():
            if node.type == NodeType.SCENARIO:
                if func_id in self._adjacency.get(node_id, []):
                    scenarios.append(node.name)

        # Find relevant invariants
        invariants = []
        affected_entities = [n.name for nid, n in self.nodes.items()
                           if nid in deps and n.type == NodeType.ENTITY]
        for node_id, node in self.nodes.items():
            if node.type == NodeType.INVARIANT:
                inv_entity = node.data.get("entity")
                if inv_entity in affected_entities:
                    invariants.append(node.name)

        return {
            "function": function_name,
            "entities": [n.name for nid, n in self.nodes.items()
                        if nid in deps and n.type == NodeType.ENTITY],
            "derived": [n.name for nid, n in self.nodes.items()
                       if nid in deps and n.type == NodeType.DERIVED],
            "scenarios": scenarios,
            "invariants": invariants
        }

    def _get_dependencies(self, start_id: str) -> set[str]:
        """Get all dependencies of a node (forward BFS)"""
        deps = set()
        queue = [start_id]

        while queue:
            current = queue.pop(0)
            if current in deps:
                continue
            deps.add(current)

            for dep in self._adjacency.get(current, []):
                if dep not in deps:
                    queue.append(dep)

        return deps

    def to_mermaid(self) -> str:
        """Export graph as Mermaid diagram"""
        lines = ["graph LR"]

        # Style definitions
        lines.append("    classDef entity fill:#e1f5fe")
        lines.append("    classDef derived fill:#fff3e0")
        lines.append("    classDef function fill:#e8f5e9")
        lines.append("    classDef scenario fill:#fce4ec")
        lines.append("    classDef invariant fill:#f3e5f5")

        # Nodes
        for node_id, node in self.nodes.items():
            safe_id = node_id.replace(":", "_").replace(".", "_")
            label = node.name
            lines.append(f"    {safe_id}[{label}]:::{node.type.value}")

        # Edges
        for edge in self.edges:
            src = edge.source.replace(":", "_").replace(".", "_")
            tgt = edge.target.replace(":", "_").replace(".", "_")
            lines.append(f"    {src} -->|{edge.relation}| {tgt}")

        return "\n".join(lines)
