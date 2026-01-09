"""Error types and validation result for The Mesh validator."""

from dataclasses import dataclass, field as dataclass_field
from typing import Any, Literal


@dataclass
class StructuredError:
    """Machine-processable error format for Claude Code integration"""

    # Location info
    path: str  # JSONPath: "state.functions.create_invoice.pre[0].expr"
    line: int | None = None  # Line number in source file (if available)

    # Error classification
    code: str = ""  # Systematic code: "TYP-001", "REF-002"
    category: Literal["schema", "reference", "type", "logic", "constraint"] = "schema"
    severity: Literal["critical", "error", "warning"] = "error"
    message: str = ""  # Human-readable message (for debugging)

    # Machine-processable info
    expected: Any = None  # Expected value/format
    actual: Any = None  # Actual value
    valid_options: list[str] = dataclass_field(default_factory=list)  # Valid choices (for Enum etc.)

    # Auto-fix info
    auto_fixable: bool = False  # Can be auto-fixed
    fix_patch: dict | None = None  # JSON Patch format fix suggestion

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "path": self.path,
            "line": self.line,
            "code": self.code,
            "category": self.category,
            "severity": self.severity,
            "message": self.message,
            "expected": self.expected,
            "actual": self.actual,
            "valid_options": self.valid_options,
            "auto_fixable": self.auto_fixable,
            "fix_patch": self.fix_patch,
        }


@dataclass
class ValidationError:
    """Legacy error format - wraps StructuredError for backward compatibility"""
    path: str
    message: str
    severity: str = "error"

    # Extended fields (optional for backward compatibility)
    code: str = ""
    category: str = "schema"
    expected: Any = None
    actual: Any = None
    valid_options: list[str] = dataclass_field(default_factory=list)
    auto_fixable: bool = False
    fix_patch: dict | None = None

    def to_structured(self) -> StructuredError:
        """Convert to StructuredError"""
        return StructuredError(
            path=self.path,
            message=self.message,
            severity=self.severity if self.severity in ("critical", "error", "warning") else "error",
            code=self.code,
            category=self.category if self.category in ("schema", "reference", "type", "logic", "constraint") else "schema",
            expected=self.expected,
            actual=self.actual,
            valid_options=self.valid_options,
            auto_fixable=self.auto_fixable,
            fix_patch=self.fix_patch,
        )


@dataclass
class ValidationResult:
    """Result of a validation operation."""
    valid: bool
    errors: list[ValidationError]
    warnings: list[ValidationError]

    def to_structured_errors(self) -> list[StructuredError]:
        """Convert all errors to StructuredError format"""
        return [e.to_structured() for e in self.errors]

    def get_fix_patches(self) -> list[dict]:
        """Get all auto-fixable patches from errors"""
        patches = []
        for err in self.errors:
            if err.auto_fixable and err.fix_patch:
                patches.append(err.fix_patch)
        return patches

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "valid": self.valid,
            "errors": [e.to_structured().to_dict() for e in self.errors],
            "warnings": [e.to_structured().to_dict() for e in self.warnings],
            "fix_patches": self.get_fix_patches(),
        }
