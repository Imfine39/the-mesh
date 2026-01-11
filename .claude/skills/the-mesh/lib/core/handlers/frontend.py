"""Frontend generation handlers for The Mesh."""

import json
from pathlib import Path
from typing import Any

from core.validator import MeshValidator
from core.storage import SpecStorage
from generators.typescript_gen import TypeScriptGenerator
from generators.openapi_gen import OpenAPIGenerator
from generators.zod_gen import ZodGenerator


def _load_spec_from_args(storage: SpecStorage, args: dict) -> dict | None:
    """Helper to load spec from various sources in args"""
    spec = args.get("spec")
    spec_path = args.get("spec_path")
    spec_id = args.get("spec_id")

    if spec is not None:
        return spec
    if spec_path:
        path = Path(spec_path)
        if path.exists():
            with open(path) as f:
                return json.load(f)
        return None
    if spec_id:
        return storage.read_spec(spec_id)
    return None


def generate_typescript_types(validator: MeshValidator, storage: SpecStorage, args: dict) -> dict:
    """Generate TypeScript type definitions from specification.

    Args:
        spec, spec_path, or spec_id: Specification source
        entity_name: Optional - generate types for specific entity only
        function_name: Optional - generate types for specific function only
        output_path: Optional - write output to file

    Returns:
        Generated TypeScript code and metadata
    """
    # Load spec
    spec = _load_spec_from_args(storage, args)
    if spec is None:
        if args.get("spec_id"):
            return {"error": f"Spec not found: {args['spec_id']}"}
        return {"error": "One of spec, spec_path, or spec_id is required"}

    entity_name = args.get("entity_name")
    function_name = args.get("function_name")
    output_path = args.get("output_path")

    # Create generator
    generator = TypeScriptGenerator(spec)

    # Generate code
    if entity_name:
        code = generator.generate_for_entity(entity_name)
        suggested_filename = f"{entity_name}.types.ts"
    elif function_name:
        code = generator.generate_for_function(function_name)
        suggested_filename = f"{function_name}.types.ts"
    else:
        code = generator.generate_all()
        suggested_filename = "types.ts"

    # Optionally write to file
    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(code)

    # Count generated types
    entities = spec.get("entities", {})
    functions = spec.get("commands", {})

    return {
        "success": True,
        "code": code,
        "suggested_filename": suggested_filename,
        "stats": {
            "entity_types": len(entities) if not entity_name else (1 if entity_name in entities else 0),
            "function_input_types": len([f for f in functions.values() if f.get("input")]),
            "function_output_types": len([f for f in functions.values() if f.get("output")])
        },
        "output_path": str(output_path) if output_path else None
    }


def generate_openapi(validator: MeshValidator, storage: SpecStorage, args: dict) -> dict:
    """Generate OpenAPI 3.1 schema from specification.

    Args:
        spec, spec_path, or spec_id: Specification source
        base_url: Optional - API base URL (default: /api/v1)
        output_path: Optional - write output to file
        format: Optional - 'json' or 'yaml' (default: json)

    Returns:
        Generated OpenAPI schema and metadata
    """
    # Load spec
    spec = _load_spec_from_args(storage, args)
    if spec is None:
        if args.get("spec_id"):
            return {"error": f"Spec not found: {args['spec_id']}"}
        return {"error": "One of spec, spec_path, or spec_id is required"}

    base_url = args.get("base_url", "/api/v1")
    output_path = args.get("output_path")
    output_format = args.get("format", "json")

    # Create generator
    generator = OpenAPIGenerator(spec, base_url=base_url)

    # Generate schema
    schema = generator.generate()

    # Format output
    if output_format == "yaml":
        try:
            import yaml
            code = yaml.dump(schema, default_flow_style=False, sort_keys=False, allow_unicode=True)
            suggested_filename = "openapi.yaml"
        except ImportError:
            return {"error": "PyYAML is required for YAML output: pip install pyyaml"}
    else:
        code = json.dumps(schema, indent=2)
        suggested_filename = "openapi.json"

    # Optionally write to file
    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(code)

    # Count paths and schemas
    paths = schema.get("paths", {})
    components = schema.get("components", {}).get("schemas", {})

    return {
        "success": True,
        "schema": schema,
        "code": code,
        "suggested_filename": suggested_filename,
        "stats": {
            "paths_count": len(paths),
            "component_schemas_count": len(components),
            "operations_count": sum(len(p) for p in paths.values())
        },
        "output_path": str(output_path) if output_path else None
    }


def generate_zod_schemas(validator: MeshValidator, storage: SpecStorage, args: dict) -> dict:
    """Generate Zod validation schemas from specification.

    Args:
        spec, spec_path, or spec_id: Specification source
        entity_name: Optional - generate schema for specific entity only
        function_name: Optional - generate schema for specific function only
        output_path: Optional - write output to file

    Returns:
        Generated Zod schema code and metadata
    """
    # Load spec
    spec = _load_spec_from_args(storage, args)
    if spec is None:
        if args.get("spec_id"):
            return {"error": f"Spec not found: {args['spec_id']}"}
        return {"error": "One of spec, spec_path, or spec_id is required"}

    entity_name = args.get("entity_name")
    function_name = args.get("function_name")
    output_path = args.get("output_path")

    # Create generator
    generator = ZodGenerator(spec)

    # Generate code
    if entity_name:
        code = generator.generate_for_entity(entity_name)
        suggested_filename = f"{entity_name}.schema.ts"
    elif function_name:
        code = generator.generate_for_function(function_name)
        suggested_filename = f"{function_name}.schema.ts"
    else:
        code = generator.generate_all()
        suggested_filename = "schemas.ts"

    # Optionally write to file
    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(code)

    # Count generated schemas
    entities = spec.get("entities", {})
    functions = spec.get("commands", {})

    # Count refinements (pre conditions that can be converted to Zod refinements)
    refinement_count = 0
    server_only_count = 0
    for func in functions.values():
        for pre in func.get("pre", []):
            expr = pre.get("expr", pre.get("check", {}))
            if isinstance(expr, dict):
                if expr.get("type") == "binary":
                    # Binary expressions with input fields can be refinements
                    left = expr.get("left", {})
                    right = expr.get("right", {})
                    if left.get("type") == "input" or right.get("type") == "input":
                        refinement_count += 1
                elif expr.get("type") in ["ref", "agg", "call", "state"]:
                    server_only_count += 1

    return {
        "success": True,
        "code": code,
        "suggested_filename": suggested_filename,
        "stats": {
            "entity_schemas": len(entities) if not entity_name else (1 if entity_name in entities else 0),
            "function_input_schemas": len([f for f in functions.values() if f.get("input")]),
            "refinements_generated": refinement_count,
            "server_only_validations": server_only_count
        },
        "output_path": str(output_path) if output_path else None
    }


def generate_all_frontend(validator: MeshValidator, storage: SpecStorage, args: dict) -> dict:
    """Generate all frontend artifacts (TypeScript types, OpenAPI, Zod schemas).

    Args:
        spec, spec_path, or spec_id: Specification source
        output_dir: Directory to write output files
        base_url: Optional - API base URL for OpenAPI (default: /api/v1)

    Returns:
        Summary of all generated files
    """
    # Load spec
    spec = _load_spec_from_args(storage, args)
    if spec is None:
        if args.get("spec_id"):
            return {"error": f"Spec not found: {args['spec_id']}"}
        return {"error": "One of spec, spec_path, or spec_id is required"}

    output_dir = args.get("output_dir")
    if not output_dir:
        return {"error": "output_dir is required"}

    base_url = args.get("base_url", "/api/v1")
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    generated_files = []
    errors = []

    # Generate TypeScript types
    try:
        ts_generator = TypeScriptGenerator(spec)
        ts_code = ts_generator.generate_all()
        ts_path = output_path / "types.ts"
        ts_path.write_text(ts_code)
        generated_files.append(str(ts_path))
    except Exception as e:
        errors.append(f"TypeScript generation failed: {e}")

    # Generate OpenAPI schema
    try:
        openapi_generator = OpenAPIGenerator(spec, base_url=base_url)
        openapi_schema = openapi_generator.generate()
        openapi_path = output_path / "openapi.json"
        openapi_path.write_text(json.dumps(openapi_schema, indent=2))
        generated_files.append(str(openapi_path))
    except Exception as e:
        errors.append(f"OpenAPI generation failed: {e}")

    # Generate Zod schemas
    try:
        zod_generator = ZodGenerator(spec)
        zod_code = zod_generator.generate_all()
        zod_path = output_path / "schemas.ts"
        zod_path.write_text(zod_code)
        generated_files.append(str(zod_path))
    except Exception as e:
        errors.append(f"Zod generation failed: {e}")

    return {
        "success": len(errors) == 0,
        "output_dir": str(output_path),
        "generated_files": generated_files,
        "errors": errors if errors else None,
        "stats": {
            "files_generated": len(generated_files),
            "entities": len(spec.get("entities", {})),
            "functions": len(spec.get("commands", {}))
        }
    }


def export_human_readable(validator: MeshValidator, storage: SpecStorage, args: dict) -> dict:
    """Export specification to human-readable formats (Mermaid diagrams, Markdown tables).

    Args:
        spec, spec_path, or spec_id: Specification source
        format: Output format - 'all', 'er', 'state', 'flow', 'entities', 'functions', 'scenarios'
        output_path: Optional - write output to file

    Returns:
        Generated human-readable content
    """
    from generators.human_readable_gen import HumanReadableGenerator

    # Load spec
    spec = _load_spec_from_args(storage, args)
    if spec is None:
        if args.get("spec_id"):
            return {"error": f"Spec not found: {args['spec_id']}"}
        return {"error": "One of spec, spec_path, or spec_id is required"}

    output_format = args.get("format", "all")
    output_path = args.get("output_path")

    generator = HumanReadableGenerator(spec)

    if output_format == "all":
        result = generator.generate_all()
        content = {
            "er_diagram": result.er_diagram,
            "state_diagrams": result.state_diagrams,
            "flowcharts": result.flowcharts,
            "entity_tables": result.entity_tables,
            "field_tables": result.field_tables,
            "requirements_text": result.requirements_text,
            "derived_explanations": result.derived_explanations,
            "function_explanations": result.function_explanations,
            "scenario_table": result.scenario_table,
            "invariant_list": result.invariant_list,
            "state_machine_diagrams": result.state_machine_diagrams,
            "saga_diagrams": result.saga_diagrams,
            "permission_matrix": result.permission_matrix,
            "event_flow_diagram": result.event_flow_diagram,
            "role_hierarchy_diagram": result.role_hierarchy_diagram,
        }
    elif output_format == "er":
        content = {"er_diagram": generator.generate_er_diagram()}
    elif output_format == "state":
        content = {"state_diagrams": generator.generate_state_diagrams()}
    elif output_format == "flow":
        content = {"flowcharts": generator.generate_flowcharts()}
    elif output_format == "entities":
        content = {
            "entity_tables": generator.generate_entity_tables(),
            "field_tables": generator.generate_field_tables(),
        }
    elif output_format == "functions":
        content = {"function_explanations": generator.generate_function_explanations()}
    elif output_format == "scenarios":
        content = {"scenario_table": generator.generate_scenario_table()}
    else:
        return {
            "error": f"Unknown format: {output_format}",
            "supported_formats": ["all", "er", "state", "flow", "entities", "functions", "scenarios"]
        }

    # Optionally write to file
    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(content, indent=2, ensure_ascii=False))

    return {
        "success": True,
        "format": output_format,
        "content": content,
        "output_path": str(output_path) if output_path else None
    }


def export_yaml(validator: MeshValidator, storage: SpecStorage, args: dict) -> dict:
    """Export specification to YAML format (human-readable view).

    Args:
        spec, spec_path, or spec_id: Specification source
        section: Optional - export only specific section
        output_path: Optional - write output to file

    Returns:
        Generated YAML content
    """
    from generators.yaml_gen import YAMLGenerator

    # Load spec
    spec = _load_spec_from_args(storage, args)
    if spec is None:
        if args.get("spec_id"):
            return {"error": f"Spec not found: {args['spec_id']}"}
        return {"error": "One of spec, spec_path, or spec_id is required"}

    section = args.get("section")
    output_path = args.get("output_path")

    try:
        generator = YAMLGenerator(spec)
    except ImportError as e:
        return {"error": str(e)}

    if section:
        code = generator.generate_section(section)
        suggested_filename = f"{section}.yaml"
    else:
        code = generator.generate()
        suggested_filename = "spec.yaml"

    # Optionally write to file
    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(code)

    return {
        "success": True,
        "code": code,
        "suggested_filename": suggested_filename,
        "output_path": str(output_path) if output_path else None
    }


# Handler registry
HANDLERS = {
    "generate_typescript_types": generate_typescript_types,
    "generate_openapi": generate_openapi,
    "generate_zod_schemas": generate_zod_schemas,
    "generate_all_frontend": generate_all_frontend,
    "export_human_readable": export_human_readable,
    "export_yaml": export_yaml,
}
