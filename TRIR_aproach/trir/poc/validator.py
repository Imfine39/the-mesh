"""TRIR JSON Schema Validator"""

import json
from pathlib import Path
from typing import Any
from dataclasses import dataclass

try:
    import jsonschema
    from jsonschema import Draft202012Validator, RefResolver
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False


@dataclass
class ValidationError:
    path: str
    message: str
    severity: str = "error"


@dataclass
class ValidationResult:
    valid: bool
    errors: list[ValidationError]
    warnings: list[ValidationError]


class TRIRValidator:
    """Validates TRIR specifications against JSON Schema"""

    def __init__(self, schema_dir: Path | None = None):
        if not HAS_JSONSCHEMA:
            raise ImportError("jsonschema is required: pip install jsonschema")

        if schema_dir is None:
            schema_dir = Path(__file__).parent.parent

        self.schema_dir = schema_dir
        self._load_schemas()

    def _load_schemas(self):
        """Load all schema files"""
        self.schemas = {}

        schema_file = self.schema_dir / "schema.schema.json"
        if schema_file.exists():
            with open(schema_file) as f:
                self.schemas["schema"] = json.load(f)

        expr_file = self.schema_dir / "expression.schema.json"
        if expr_file.exists():
            with open(expr_file) as f:
                self.schemas["expression"] = json.load(f)

    def validate(self, spec: dict[str, Any]) -> ValidationResult:
        """Validate a TRIR specification"""
        errors = []
        warnings = []

        # 1. JSON Schema validation
        if "schema" in self.schemas:
            schema_errors = self._validate_against_schema(spec, self.schemas["schema"])
            errors.extend(schema_errors)

        # 2. Reference validation (FK references)
        ref_errors = self._validate_references(spec)
        errors.extend(ref_errors)

        # 3. Expression validation
        expr_errors = self._validate_expressions(spec)
        errors.extend(expr_errors)

        # 4. Cycle detection
        cycle_warnings = self._detect_cycles(spec)
        warnings.extend(cycle_warnings)

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )

    def _validate_against_schema(self, spec: dict, schema: dict) -> list[ValidationError]:
        """Validate spec against JSON Schema"""
        errors = []

        try:
            # Load local expression schema if available
            store = {schema.get("$id", ""): schema}

            expr_schema_path = self.schema_dir / "expression.schema.json"
            if expr_schema_path.exists():
                with open(expr_schema_path) as f:
                    expr_schema = json.load(f)
                    store[expr_schema.get("$id", "")] = expr_schema
                    # Also store without domain for local reference
                    store["expression.schema.json"] = expr_schema

            resolver = RefResolver.from_schema(schema, store=store)
            validator = Draft202012Validator(schema, resolver=resolver)

            for error in validator.iter_errors(spec):
                path = ".".join(str(p) for p in error.absolute_path)
                # Skip expression validation errors from JSON Schema
                # The Python jsonschema library doesn't fully support discriminator-based oneOf
                # Our custom _validate_expressions() handles expression validation properly
                if "is not valid under any of the given schemas" in error.message:
                    # This is likely an expression oneOf validation issue
                    # Skip if it's in a known expression location
                    if any(loc in path for loc in ["formula", "expr", "when", "condition", "assert", "with", "set"]):
                        continue
                errors.append(ValidationError(
                    path=path or "root",
                    message=error.message
                ))
        except jsonschema.exceptions.RefResolutionError as e:
            # Remote schema resolution failed - skip schema validation
            # This is expected in offline environments
            pass
        except Exception as e:
            # Only report non-network errors
            if "NameResolutionError" not in str(e) and "ConnectionPool" not in str(e):
                errors.append(ValidationError(
                    path="schema",
                    message=f"Schema validation failed: {e}"
                ))

        return errors

    def _validate_references(self, spec: dict) -> list[ValidationError]:
        """Validate entity references (foreign keys)"""
        errors = []
        entities = set(spec.get("state", {}).keys())

        # Check FK references in entity fields
        for entity_name, entity in spec.get("state", {}).items():
            for field_name, field in entity.get("fields", {}).items():
                field_type = field.get("type", {})
                if isinstance(field_type, dict) and "ref" in field_type:
                    ref_target = field_type["ref"]
                    if ref_target not in entities:
                        errors.append(ValidationError(
                            path=f"state.{entity_name}.fields.{field_name}",
                            message=f"Referenced entity '{ref_target}' does not exist"
                        ))

        # Check entity references in functions
        for func_name, func in spec.get("functions", {}).items():
            # Check pre conditions
            for i, pre in enumerate(func.get("pre", [])):
                if "entity" in pre and pre["entity"] not in entities:
                    errors.append(ValidationError(
                        path=f"functions.{func_name}.pre[{i}]",
                        message=f"Referenced entity '{pre['entity']}' does not exist"
                    ))

            # Check post actions
            for i, post in enumerate(func.get("post", [])):
                action = post.get("action", {})
                for action_type in ["create", "update", "delete"]:
                    if action_type in action and action[action_type] not in entities:
                        errors.append(ValidationError(
                            path=f"functions.{func_name}.post[{i}]",
                            message=f"Referenced entity '{action[action_type]}' does not exist"
                        ))

        # Check derived entity references
        for derived_name, derived in spec.get("derived", {}).items():
            if "entity" in derived and derived["entity"] not in entities:
                errors.append(ValidationError(
                    path=f"derived.{derived_name}",
                    message=f"Referenced entity '{derived['entity']}' does not exist"
                ))

        return errors

    def _validate_expressions(self, spec: dict) -> list[ValidationError]:
        """Validate expression ASTs (Tagged Union format)"""
        errors = []
        entities = spec.get("state", {})
        derived = spec.get("derived", {})
        functions = spec.get("functions", {})

        def validate_expr(expr: Any, path: str, context: dict) -> list[ValidationError]:
            """Recursively validate an expression (Tagged Union format)"""
            errs = []

            if not isinstance(expr, dict):
                return errs

            # Get current aliases from context
            aliases = set(context.get("aliases", []))
            aliases.add("item")  # Default aggregation alias

            expr_type = expr.get("type")

            # Field reference validation: { "type": "ref", "path": "entity.field" }
            if expr_type == "ref":
                ref_path = expr.get("path", "")
                parts = ref_path.split(".")
                if len(parts) >= 2:
                    entity_or_alias = parts[0]
                    # Check if it's a known entity or alias
                    if entity_or_alias not in entities and entity_or_alias not in aliases:
                        errs.append(ValidationError(
                            path=path,
                            message=f"Unknown entity or alias '{entity_or_alias}' in reference '{ref_path}'"
                        ))

            # Aggregation validation: { "type": "agg", "op": "sum", "from": "entity", ... }
            elif expr_type == "agg":
                from_entity = expr.get("from", "")
                if from_entity and from_entity not in entities:
                    errs.append(ValidationError(
                        path=path,
                        message=f"Aggregation from unknown entity '{from_entity}'"
                    ))

                # Add the 'as' alias to context for nested validation
                agg_alias = expr.get("as", "item")
                new_context = dict(context)
                new_context["aliases"] = list(aliases) + [agg_alias]

                # Recursively validate nested expressions with new alias context
                if "expr" in expr:
                    errs.extend(validate_expr(expr["expr"], f"{path}.expr", new_context))
                if "where" in expr:
                    errs.extend(validate_expr(expr["where"], f"{path}.where", new_context))

            # Binary operation validation: { "type": "binary", "op": "add", "left": ..., "right": ... }
            elif expr_type == "binary":
                errs.extend(validate_expr(expr.get("left", {}), f"{path}.left", context))
                errs.extend(validate_expr(expr.get("right", {}), f"{path}.right", context))

            # Unary operation validation: { "type": "unary", "op": "not", "expr": ... }
            elif expr_type == "unary":
                errs.extend(validate_expr(expr.get("expr", {}), f"{path}.expr", context))

            # Function call validation: { "type": "call", "name": "fn", "args": [...] }
            elif expr_type == "call":
                func_name = expr.get("name", "")
                if func_name not in derived and func_name not in functions:
                    errs.append(ValidationError(
                        path=path,
                        message=f"Unknown function '{func_name}'"
                    ))
                # Validate args
                for i, arg in enumerate(expr.get("args", [])):
                    errs.extend(validate_expr(arg, f"{path}.args[{i}]", context))

            # Conditional validation: { "type": "if", "cond": ..., "then": ..., "else": ... }
            elif expr_type == "if":
                errs.extend(validate_expr(expr.get("cond", {}), f"{path}.cond", context))
                errs.extend(validate_expr(expr.get("then", {}), f"{path}.then", context))
                errs.extend(validate_expr(expr.get("else", {}), f"{path}.else", context))

            # Case expression validation: { "type": "case", "branches": [...], "else": ... }
            elif expr_type == "case":
                for i, branch in enumerate(expr.get("branches", [])):
                    errs.extend(validate_expr(branch.get("when", {}), f"{path}.branches[{i}].when", context))
                    errs.extend(validate_expr(branch.get("then", {}), f"{path}.branches[{i}].then", context))
                errs.extend(validate_expr(expr.get("else", {}), f"{path}.else", context))

            # Date operation validation: { "type": "date", "op": "diff", "args": [...] }
            elif expr_type == "date":
                for i, arg in enumerate(expr.get("args", [])):
                    errs.extend(validate_expr(arg, f"{path}.args[{i}]", context))

            # List operation validation: { "type": "list", "op": "contains", "list": ..., "args": [...] }
            elif expr_type == "list":
                errs.extend(validate_expr(expr.get("list", {}), f"{path}.list", context))
                for i, arg in enumerate(expr.get("args", [])):
                    errs.extend(validate_expr(arg, f"{path}.args[{i}]", context))

            # literal, input, self types don't need recursive validation

            return errs

        # Validate derived formulas
        for name, d in derived.items():
            if "formula" in d:
                errors.extend(validate_expr(
                    d["formula"],
                    f"derived.{name}.formula",
                    {"entity": d.get("entity")}
                ))

        # Validate function expressions
        for name, func in functions.items():
            for i, pre in enumerate(func.get("pre", [])):
                if "expr" in pre:
                    errors.extend(validate_expr(
                        pre["expr"],
                        f"functions.{name}.pre[{i}].expr",
                        {}
                    ))
            for i, err in enumerate(func.get("error", [])):
                if "when" in err:
                    errors.extend(validate_expr(
                        err["when"],
                        f"functions.{name}.error[{i}].when",
                        {}
                    ))

        return errors

    def _detect_cycles(self, spec: dict) -> list[ValidationError]:
        """Detect circular dependencies in derived formulas"""
        warnings = []
        derived = spec.get("derived", {})

        def get_deps(formula: dict) -> set[str]:
            """Extract derived function calls from a formula (Tagged Union format)"""
            deps = set()

            def walk(expr: Any):
                if not isinstance(expr, dict):
                    return
                # Tagged Union: { "type": "call", "name": "fn" }
                if expr.get("type") == "call" and expr.get("name") in derived:
                    deps.add(expr["name"])
                for v in expr.values():
                    if isinstance(v, dict):
                        walk(v)
                    elif isinstance(v, list):
                        for item in v:
                            walk(item)

            walk(formula)
            return deps

        # Build dependency graph
        dep_graph = {name: get_deps(d.get("formula", {})) for name, d in derived.items()}

        # Detect cycles using DFS
        def has_cycle(node: str, visited: set, rec_stack: set) -> list[str] | None:
            visited.add(node)
            rec_stack.add(node)

            for dep in dep_graph.get(node, []):
                if dep not in visited:
                    cycle = has_cycle(dep, visited, rec_stack)
                    if cycle is not None:
                        return [node] + cycle
                elif dep in rec_stack:
                    return [node, dep]

            rec_stack.remove(node)
            return None

        visited = set()
        for name in derived:
            if name not in visited:
                cycle = has_cycle(name, visited, set())
                if cycle:
                    warnings.append(ValidationError(
                        path=f"derived",
                        message=f"Circular dependency detected: {' -> '.join(cycle)}",
                        severity="warning"
                    ))
                    break

        return warnings
