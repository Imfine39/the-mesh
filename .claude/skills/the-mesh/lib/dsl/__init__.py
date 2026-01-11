"""DSL to TRIR compiler.

Converts human/LLM-friendly DSL format to strict TRIR JSON.
"""

from .compiler import DSLCompiler
from .field_parser import FieldParser
from .type_aliases import TypeAliases

__all__ = ["DSLCompiler", "FieldParser", "TypeAliases"]
