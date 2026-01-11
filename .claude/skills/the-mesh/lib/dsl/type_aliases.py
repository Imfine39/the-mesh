"""Type alias resolution for DSL.

Maps human-friendly type names to strict TRIR types.
"""


class TypeAliases:
    """Resolves type aliases to TRIR field definitions."""

    # Simple type mappings
    TYPE_MAP = {
        # Date/time aliases
        "date": "datetime",
        "time": "datetime",
        "timestamp": "datetime",

        # Boolean aliases
        "boolean": "bool",
        "flag": "bool",

        # Number aliases
        "integer": "int",
        "number": "float",
        "decimal": "float",

        # Text aliases
        "varchar": "string",
        "char": "string",
        "longtext": "text",
    }

    # Preset type shortcuts (type + preset combined)
    PRESET_TYPES = {
        "money": {"type": "float", "preset": "money"},
        "currency": {"type": "float", "preset": "money"},
        "amount": {"type": "float", "preset": "money"},
        "price": {"type": "float", "preset": "money"},
        "cost": {"type": "float", "preset": "money"},

        "email": {"type": "string", "preset": "email"},
        "mail": {"type": "string", "preset": "email"},

        "id": {"type": "string", "preset": "id"},
        "identifier": {"type": "string", "preset": "id"},
        "code": {"type": "string", "preset": "id"},

        "percent": {"type": "float", "preset": "percentage"},
        "percentage": {"type": "float", "preset": "percentage"},
        "rate": {"type": "float", "preset": "percentage"},

        "age": {"type": "int", "preset": "age"},

        "count": {"type": "int", "preset": "count"},
        "quantity": {"type": "int", "preset": "count"},
        "qty": {"type": "int", "preset": "count"},
    }

    # Format shortcuts
    FORMAT_TYPES = {
        "url": {"type": "string", "format": "url"},
        "uri": {"type": "string", "format": "url"},
        "uuid": {"type": "string", "format": "uuid"},
        "phone": {"type": "string", "format": "phone"},
    }

    @classmethod
    def resolve(cls, type_str: str) -> dict:
        """Resolve a type string to TRIR field definition.

        Args:
            type_str: Type name (e.g., "date", "money", "string")

        Returns:
            Dict with at minimum {"type": "..."}, possibly with preset/format
        """
        type_lower = type_str.lower().strip()

        # Check preset types first (they include type + preset)
        if type_lower in cls.PRESET_TYPES:
            return cls.PRESET_TYPES[type_lower].copy()

        # Check format types
        if type_lower in cls.FORMAT_TYPES:
            return cls.FORMAT_TYPES[type_lower].copy()

        # Check simple type aliases
        if type_lower in cls.TYPE_MAP:
            return {"type": cls.TYPE_MAP[type_lower]}

        # Check if it's already a valid TRIR type
        valid_types = {"string", "int", "float", "bool", "datetime", "text"}
        if type_lower in valid_types:
            return {"type": type_lower}

        # Unknown type - return as-is, let validator catch it
        return {"type": type_str}

    @classmethod
    def is_known_type(cls, type_str: str) -> bool:
        """Check if a type string is recognized."""
        type_lower = type_str.lower().strip()
        valid_types = {"string", "int", "float", "bool", "datetime", "text"}
        return (
            type_lower in cls.TYPE_MAP or
            type_lower in cls.PRESET_TYPES or
            type_lower in cls.FORMAT_TYPES or
            type_lower in valid_types
        )
