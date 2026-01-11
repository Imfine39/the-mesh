"""Field definition parser for DSL.

Parses shorthand field notations like:
- "string, required"
- "string, maxLength:100, required"
- "money"
- "int, min:0, max:100"
- { type: string, required: true }  (pass-through)
"""

import re
from .type_aliases import TypeAliases


class FieldParser:
    """Parses DSL field definitions to TRIR format."""

    # Pattern for key:value pairs
    KV_PATTERN = re.compile(r"(\w+)\s*:\s*(.+)")

    # Recognized constraint keys
    CONSTRAINT_KEYS = {
        "min", "max", "minlength", "maxlength",
        "pattern", "precision", "format", "preset"
    }

    # Boolean flags (presence means true)
    FLAG_KEYS = {"required", "unique"}

    @classmethod
    def parse(cls, field_def) -> dict:
        """Parse a field definition to TRIR format.

        Args:
            field_def: Can be:
                - str: "string, required, maxLength:100"
                - dict: {"type": "string", ...} (pass-through with normalization)

        Returns:
            TRIR field definition dict
        """
        if isinstance(field_def, dict):
            return cls._normalize_dict(field_def)
        elif isinstance(field_def, str):
            return cls._parse_string(field_def)
        else:
            raise ValueError(f"Invalid field definition: {field_def}")

    @classmethod
    def _normalize_dict(cls, field_dict: dict) -> dict:
        """Normalize a dict field definition.

        Handles:
        - Type alias resolution
        - constraints block flattening
        - Key case normalization
        """
        result = {}

        # Handle type
        if "type" in field_dict:
            type_val = field_dict["type"]
            if isinstance(type_val, str):
                # Resolve type alias
                resolved = TypeAliases.resolve(type_val)
                result.update(resolved)
            elif isinstance(type_val, dict):
                # Enum or ref type - pass through
                result["type"] = type_val
            else:
                result["type"] = type_val

        # Flatten constraints block if present
        if "constraints" in field_dict:
            constraints = field_dict["constraints"]
            if isinstance(constraints, dict):
                for key, value in constraints.items():
                    norm_key = cls._normalize_key(key)
                    result[norm_key] = value

        # Copy other properties with key normalization
        skip_keys = {"type", "constraints"}
        for key, value in field_dict.items():
            if key not in skip_keys:
                norm_key = cls._normalize_key(key)
                # Don't overwrite type-resolved values
                if norm_key not in result or norm_key not in {"type", "preset", "format"}:
                    result[norm_key] = value

        return result

    @classmethod
    def _parse_string(cls, field_str: str) -> dict:
        """Parse a string field definition.

        Format: "type, key:value, key:value, flag, ..."

        Examples:
            "string" -> {"type": "string"}
            "string, required" -> {"type": "string", "required": true}
            "string, maxLength:100" -> {"type": "string", "maxLength": 100}
            "money" -> {"type": "float", "preset": "money"}
            "int, min:0, max:100" -> {"type": "int", "min": 0, "max": 100}
        """
        parts = [p.strip() for p in field_str.split(",")]
        if not parts:
            raise ValueError(f"Empty field definition: {field_str}")

        # First part is the type
        type_str = parts[0]
        result = TypeAliases.resolve(type_str)

        # Process remaining parts
        for part in parts[1:]:
            part = part.strip()
            if not part:
                continue

            # Check for key:value
            match = cls.KV_PATTERN.match(part)
            if match:
                key = match.group(1)
                value = match.group(2).strip()
                norm_key = cls._normalize_key(key)

                # Parse value
                parsed_value = cls._parse_value(value)
                result[norm_key] = parsed_value
            elif part.lower() in cls.FLAG_KEYS:
                # Boolean flag
                result[part.lower()] = True
            else:
                # Unknown part - could be a constraint name without value
                # Treat as flag if it looks like one
                if part.lower() in {"optional", "nullable"}:
                    result["required"] = False

        return result

    @classmethod
    def _normalize_key(cls, key: str) -> str:
        """Normalize a constraint key to TRIR format."""
        key_lower = key.lower()

        # Handle common variations
        key_map = {
            "minlength": "minLength",
            "min_length": "minLength",
            "maxlength": "maxLength",
            "max_length": "maxLength",
            "min": "min",
            "max": "max",
            "pattern": "pattern",
            "regex": "pattern",
            "precision": "precision",
            "format": "format",
            "preset": "preset",
            "required": "required",
            "unique": "unique",
            "default": "default",
            "description": "description",
        }

        return key_map.get(key_lower, key)

    @classmethod
    def _parse_value(cls, value_str: str):
        """Parse a value string to appropriate Python type."""
        value_str = value_str.strip()

        # Remove quotes if present
        if (value_str.startswith('"') and value_str.endswith('"')) or \
           (value_str.startswith("'") and value_str.endswith("'")):
            return value_str[1:-1]

        # Boolean
        if value_str.lower() == "true":
            return True
        if value_str.lower() == "false":
            return False

        # Number
        try:
            if "." in value_str:
                return float(value_str)
            return int(value_str)
        except ValueError:
            pass

        # String
        return value_str
