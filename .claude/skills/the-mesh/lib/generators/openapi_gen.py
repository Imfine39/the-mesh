"""OpenAPI 3.1 schema generator for The Mesh."""

from typing import Any


class OpenAPIGenerator:
    """Generate OpenAPI 3.1 schema from TRIR specification.

    Generates:
    - Paths from functions
    - Component schemas from entities
    - Error responses from error definitions
    """

    def __init__(self, spec: dict, base_url: str = "/api/v1"):
        self.spec = spec
        self.base_url = base_url.rstrip("/")
        self.meta = spec.get("meta", {})
        self.entities = spec.get("entities", {})
        self.functions = spec.get("commands", {})

    def generate(self) -> dict:
        """Generate complete OpenAPI 3.1 schema."""
        return {
            "openapi": "3.1.0",
            "info": self._generate_info(),
            "servers": [{"url": self.base_url}],
            "paths": self._generate_paths(),
            "components": self._generate_components()
        }

    def _generate_info(self) -> dict:
        """Generate info section from spec meta."""
        return {
            "title": self.meta.get("title", "API"),
            "version": self.meta.get("version", "1.0.0"),
            "description": self.meta.get("description", "Generated from TRIR specification")
        }

    def _generate_paths(self) -> dict:
        """Generate paths from functions."""
        paths = {}

        for func_name, func_def in self.functions.items():
            path = f"/{self._to_kebab_case(func_name)}"
            paths[path] = self._generate_path_item(func_name, func_def)

        return paths

    def _generate_path_item(self, func_name: str, func_def: dict) -> dict:
        """Generate a single path item."""
        operation = {
            "operationId": func_name,
            "summary": func_def.get("description", f"Execute {func_name}"),
            "tags": [self._get_primary_entity(func_def) or "operations"]
        }

        # Request body from input
        input_def = func_def.get("input", {})
        if input_def:
            operation["requestBody"] = {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": self._generate_input_schema(func_name, input_def)
                    }
                }
            }

        # Responses
        operation["responses"] = self._generate_responses(func_name, func_def)

        return {"post": operation}

    def _generate_input_schema(self, func_name: str, input_def: dict) -> dict:
        """Generate schema for function input."""
        properties = {}
        required = []

        for param_name, param_def in input_def.items():
            properties[param_name] = self._trir_type_to_openapi(param_def.get("type"))

            # Add description if present
            if "description" in param_def:
                properties[param_name]["description"] = param_def["description"]

            if param_def.get("required", True):
                required.append(param_name)

        schema = {
            "type": "object",
            "properties": properties
        }

        if required:
            schema["required"] = required

        return schema

    def _generate_responses(self, func_name: str, func_def: dict) -> dict:
        """Generate response definitions."""
        responses = {}

        # Success response
        output_def = func_def.get("output", {})
        if output_def:
            responses["200"] = {
                "description": "Successful operation",
                "content": {
                    "application/json": {
                        "schema": self._generate_output_schema(func_name, output_def)
                    }
                }
            }
        else:
            responses["200"] = {
                "description": "Successful operation",
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "success": {"type": "boolean", "const": True}
                            },
                            "required": ["success"]
                        }
                    }
                }
            }

        # Error responses from error definitions
        errors = func_def.get("error", [])
        error_responses = {}

        for error in errors:
            code = error.get("code", "ERROR")
            http_status = str(error.get("http_status", 409))
            reason = error.get("reason", "")

            if http_status not in error_responses:
                error_responses[http_status] = {
                    "codes": [],
                    "reasons": []
                }

            error_responses[http_status]["codes"].append(code)
            error_responses[http_status]["reasons"].append(reason)

        for status, info in error_responses.items():
            codes_enum = info["codes"]
            description = "; ".join(f"{c}: {r}" for c, r in zip(info["codes"], info["reasons"]))

            responses[status] = {
                "description": description or f"Error: {', '.join(codes_enum)}",
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "success": {"type": "boolean", "const": False},
                                "error": {
                                    "type": "string",
                                    "enum": codes_enum
                                },
                                "message": {"type": "string"}
                            },
                            "required": ["success", "error"]
                        }
                    }
                }
            }

        return responses

    def _generate_output_schema(self, func_name: str, output_def: dict) -> dict:
        """Generate schema for function output."""
        properties = {}
        required = []

        for field_name, field_def in output_def.items():
            properties[field_name] = self._trir_type_to_openapi(field_def.get("type"))

            if field_def.get("required", True):
                required.append(field_name)

        schema = {
            "type": "object",
            "properties": properties
        }

        if required:
            schema["required"] = required

        return schema

    def _generate_components(self) -> dict:
        """Generate components section."""
        components = {
            "schemas": {}
        }

        # Entity schemas
        for entity_name, entity_def in self.entities.items():
            schema_name = self._to_pascal_case(entity_name)
            components["schemas"][schema_name] = self._generate_entity_schema(entity_def)

        # Common error response schema
        components["schemas"]["ErrorResponse"] = {
            "type": "object",
            "properties": {
                "success": {"type": "boolean", "const": False},
                "error": {"type": "string"},
                "message": {"type": "string"}
            },
            "required": ["success", "error"]
        }

        return components

    def _generate_entity_schema(self, entity_def: dict) -> dict:
        """Generate schema for an entity."""
        properties = {}
        required = []

        fields = entity_def.get("fields", {})
        for field_name, field_def in fields.items():
            properties[field_name] = self._trir_type_to_openapi(field_def.get("type"))

            # Add description
            if "description" in field_def:
                properties[field_name]["description"] = field_def["description"]

            if field_def.get("required", True):
                required.append(field_name)

        schema = {
            "type": "object",
            "properties": properties
        }

        if required:
            schema["required"] = required

        # Add entity description
        if "description" in entity_def:
            schema["description"] = entity_def["description"]

        return schema

    def _trir_type_to_openapi(self, trir_type: Any) -> dict:
        """Convert TRIR type to OpenAPI schema type."""
        if trir_type is None:
            return {"type": "string"}

        if isinstance(trir_type, str):
            type_map = {
                "string": {"type": "string"},
                "int": {"type": "integer"},
                "float": {"type": "number"},
                "bool": {"type": "boolean"},
                "datetime": {"type": "string", "format": "date-time"},
                "text": {"type": "string"}
            }
            return type_map.get(trir_type, {"type": "string"})

        if isinstance(trir_type, dict):
            if "enum" in trir_type:
                return {
                    "type": "string",
                    "enum": trir_type["enum"]
                }
            if "ref" in trir_type:
                # Reference to another entity - just use string for ID
                ref_entity = trir_type["ref"]
                return {
                    "type": "string",
                    "description": f"Reference to {self._to_pascal_case(ref_entity)}"
                }
            if "list" in trir_type:
                inner_schema = self._trir_type_to_openapi(trir_type["list"])
                return {
                    "type": "array",
                    "items": inner_schema
                }

        return {"type": "string"}

    def _get_primary_entity(self, func_def: dict) -> str | None:
        """Get primary entity from function's post actions."""
        for post in func_def.get("post", []):
            action = post.get("action", {})
            for action_type in ["create", "update", "delete"]:
                if action_type in action:
                    return action[action_type]
        return None

    def _to_pascal_case(self, name: str) -> str:
        """Convert snake_case to PascalCase."""
        return "".join(word.capitalize() for word in name.split("_"))

    def _to_kebab_case(self, name: str) -> str:
        """Convert snake_case to kebab-case."""
        return name.replace("_", "-")
