"""The Mesh MCP Server - Model Context Protocol interface for specification validation"""

import json
from pathlib import Path
from typing import Any

from the_mesh.core.validator import MeshValidator
from the_mesh.mcp.storage import SpecStorage
from the_mesh.mcp.handlers import HANDLERS

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.server.models import InitializationOptions
    from mcp.types import Tool, TextContent, ServerCapabilities
    HAS_MCP = True
except ImportError:
    HAS_MCP = False


class MeshServer:
    """MCP Server providing The Mesh specification validation tools for Claude Code"""

    def __init__(self, schema_dir: Path | None = None, storage_dir: Path | None = None):
        self.validator = MeshValidator(schema_dir)
        self.storage = SpecStorage(storage_dir)
        self.schema_dir = schema_dir or Path(__file__).parent.parent
        self._spec_cache: dict[str, dict] = {}  # Cache for loaded specs

    def get_tools(self) -> list[dict]:
        """Return list of available MCP tools"""
        return [
            {
                "name": "validate_spec",
                "description": "Validate a complete Mesh specification against schema and semantic rules",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "spec": {
                            "type": "object",
                            "description": "The Mesh specification to validate"
                        },
                        "spec_path": {
                            "type": "string",
                            "description": "Path to Mesh spec file (alternative to spec)"
                        }
                    }
                }
            },
            {
                "name": "validate_expression",
                "description": "Validate a single expression against Mesh expression schema",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "expression": {
                            "type": "object",
                            "description": "The expression to validate"
                        },
                        "context": {
                            "type": "object",
                            "description": "Context for validation (entities, derived, etc.)"
                        }
                    },
                    "required": ["expression"]
                }
            },
            {
                "name": "validate_partial",
                "description": "Validate only changed parts of a spec (incremental validation)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "base_spec": {
                            "type": "object",
                            "description": "The base specification"
                        },
                        "changes": {
                            "type": "array",
                            "items": {"type": "object"},
                            "description": "JSON Patch format changes to validate"
                        }
                    },
                    "required": ["base_spec", "changes"]
                }
            },
            {
                "name": "get_fix_suggestion",
                "description": "Get auto-fix suggestions for validation errors (JSON Patch format)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "errors": {
                            "type": "array",
                            "items": {"type": "object"},
                            "description": "List of validation errors"
                        }
                    },
                    "required": ["errors"]
                }
            },
            {
                "name": "suggest_completion",
                "description": "Suggest completions for missing required fields",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "partial_spec": {
                            "type": "object",
                            "description": "Partial specification needing completion"
                        }
                    },
                    "required": ["partial_spec"]
                }
            },
            {
                "name": "analyze_impact",
                "description": "Analyze impact of a change on the specification",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "spec": {
                            "type": "object",
                            "description": "The current specification"
                        },
                        "change": {
                            "type": "object",
                            "description": "The proposed change"
                        }
                    },
                    "required": ["spec", "change"]
                }
            },
            {
                "name": "check_reference",
                "description": "Check if a reference path is valid in the spec",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "spec": {
                            "type": "object",
                            "description": "The specification"
                        },
                        "reference": {
                            "type": "string",
                            "description": "Reference path to check (e.g., 'invoice.customer.name')"
                        }
                    },
                    "required": ["spec", "reference"]
                }
            },
            {
                "name": "get_entity_schema",
                "description": "Get schema information for an entity",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "spec": {
                            "type": "object",
                            "description": "The specification"
                        },
                        "entity_name": {
                            "type": "string",
                            "description": "Name of the entity"
                        }
                    },
                    "required": ["spec", "entity_name"]
                }
            },
            {
                "name": "list_valid_values",
                "description": "List valid values for a field (enum values, reference targets, etc.)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "spec": {
                            "type": "object",
                            "description": "The specification"
                        },
                        "field_path": {
                            "type": "string",
                            "description": "Path to the field (e.g., 'Invoice.status')"
                        }
                    },
                    "required": ["spec", "field_path"]
                }
            },
            {
                "name": "get_dependencies",
                "description": "Get dependencies for a given element in the spec",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "spec": {
                            "type": "object",
                            "description": "The specification"
                        },
                        "element_path": {
                            "type": "string",
                            "description": "Path to the element (e.g., 'derived.total_amount')"
                        }
                    },
                    "required": ["spec", "element_path"]
                }
            },
            # === Spec File Management Tools ===
            {
                "name": "spec_list",
                "description": "List all spec files in storage (~/.mesh/specs/)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "include_meta": {
                            "type": "boolean",
                            "description": "Include meta info (id, title, version) for each spec",
                            "default": True
                        }
                    }
                }
            },
            {
                "name": "spec_read",
                "description": "Read a spec file from storage",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "spec_id": {
                            "type": "string",
                            "description": "Spec ID or filename"
                        },
                        "sections": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional: only return specific sections"
                        }
                    },
                    "required": ["spec_id"]
                }
            },
            {
                "name": "spec_write",
                "description": "Write/create a spec file (validates before saving, creates backup)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "spec": {
                            "type": "object",
                            "description": "The complete spec to write"
                        },
                        "spec_id": {
                            "type": "string",
                            "description": "Override spec ID (otherwise uses meta.id)"
                        },
                        "validate": {
                            "type": "boolean",
                            "description": "Validate before saving (default: true)",
                            "default": True
                        },
                        "force": {
                            "type": "boolean",
                            "description": "Save even if validation fails (default: false)",
                            "default": False
                        }
                    },
                    "required": ["spec"]
                }
            },
            {
                "name": "spec_delete",
                "description": "Delete a spec file (moves to backup first)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "spec_id": {
                            "type": "string",
                            "description": "Spec ID or filename to delete"
                        },
                        "keep_backup": {
                            "type": "boolean",
                            "description": "Keep a backup copy (default: true)",
                            "default": True
                        }
                    },
                    "required": ["spec_id"]
                }
            },
            {
                "name": "spec_get_section",
                "description": "Get a specific section from a spec",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "spec_id": {"type": "string", "description": "Spec ID"},
                        "section": {
                            "type": "string",
                            "description": "Section name (e.g., 'state', 'functions', 'derived')"
                        },
                        "key": {
                            "type": "string",
                            "description": "Specific key within section (e.g., 'Invoice' in 'state')"
                        }
                    },
                    "required": ["spec_id", "section"]
                }
            },
            {
                "name": "spec_update_section",
                "description": "Update a specific section or item within a spec (creates backup)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "spec_id": {"type": "string", "description": "Spec ID"},
                        "section": {"type": "string", "description": "Section to update"},
                        "key": {
                            "type": "string",
                            "description": "Specific key to update (for object sections)"
                        },
                        "data": {
                            "type": "object",
                            "description": "New data for the section/key"
                        },
                        "merge": {
                            "type": "boolean",
                            "description": "Merge with existing data (default: false = replace)",
                            "default": False
                        },
                        "validate": {
                            "type": "boolean",
                            "description": "Validate after update (default: true)",
                            "default": True
                        }
                    },
                    "required": ["spec_id", "section", "data"]
                }
            },
            {
                "name": "spec_delete_section",
                "description": "Delete a section or item from a spec",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "spec_id": {"type": "string", "description": "Spec ID"},
                        "section": {"type": "string", "description": "Section to delete"},
                        "key": {
                            "type": "string",
                            "description": "Specific key to delete (e.g., delete one entity)"
                        }
                    },
                    "required": ["spec_id", "section"]
                }
            },
            {
                "name": "spec_create_from_template",
                "description": "Create a new spec from a template",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "template": {
                            "type": "string",
                            "enum": ["minimal"],
                            "description": "Template to use"
                        },
                        "meta": {
                            "type": "object",
                            "description": "Override meta fields (id, title, version, domain)",
                            "properties": {
                                "id": {"type": "string"},
                                "title": {"type": "string"},
                                "version": {"type": "string"},
                                "domain": {"type": "string"}
                            },
                            "required": ["id", "title", "version"]
                        }
                    },
                    "required": ["template", "meta"]
                }
            },
            {
                "name": "spec_list_backups",
                "description": "List backup versions of a spec",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "spec_id": {"type": "string", "description": "Spec ID"},
                        "limit": {
                            "type": "integer",
                            "description": "Max backups to return (default: 10)",
                            "default": 10
                        }
                    },
                    "required": ["spec_id"]
                }
            },
            {
                "name": "spec_restore_backup",
                "description": "Restore a spec from a backup version",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "spec_id": {"type": "string", "description": "Spec ID"},
                        "backup_timestamp": {
                            "type": "string",
                            "description": "Timestamp of backup to restore (from spec_list_backups)"
                        },
                        "backup_current": {
                            "type": "boolean",
                            "description": "Backup current before restoring (default: true)",
                            "default": True
                        }
                    },
                    "required": ["spec_id", "backup_timestamp"]
                }
            },
            # === Context Extraction Tools ===
            {
                "name": "get_function_context",
                "description": "Get minimal context needed to implement a function (entities, derived, scenarios, invariants with full definitions)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "spec": {
                            "type": "object",
                            "description": "The specification"
                        },
                        "spec_path": {
                            "type": "string",
                            "description": "Path to spec file (alternative to spec)"
                        },
                        "spec_id": {
                            "type": "string",
                            "description": "Spec ID in storage (alternative to spec/spec_path)"
                        },
                        "function_name": {
                            "type": "string",
                            "description": "Name of the function to get context for"
                        }
                    },
                    "required": ["function_name"]
                }
            },
            # === Test Generation Tools ===
            {
                "name": "generate_tests",
                "description": "Generate test code from TRIR specification scenarios. Supports pytest (Python) and Jest (JavaScript/TypeScript).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "spec": {
                            "type": "object",
                            "description": "The specification"
                        },
                        "spec_path": {
                            "type": "string",
                            "description": "Path to spec file (alternative to spec)"
                        },
                        "spec_id": {
                            "type": "string",
                            "description": "Spec ID in storage (alternative to spec/spec_path)"
                        },
                        "framework": {
                            "type": "string",
                            "enum": ["pytest", "pytest-ut", "jest", "jest-ts", "jest-ut", "jest-ts-ut"],
                            "description": "Test framework: 'pytest'/'jest'/'jest-ts' for AT, add '-ut' suffix for Unit Tests",
                            "default": "pytest"
                        },
                        "function_name": {
                            "type": "string",
                            "description": "Generate tests only for this function (optional, default: all)"
                        }
                    }
                }
            },
            {
                "name": "generate_task_package",
                "description": "Generate a complete implementation task package with tests, context, skeleton, and test runner config. Tests are stored in .mesh/tests/ (no duplication), task files in tasks/{function}/",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "spec": {
                            "type": "object",
                            "description": "The specification"
                        },
                        "spec_path": {
                            "type": "string",
                            "description": "Path to spec file (alternative to spec)"
                        },
                        "spec_id": {
                            "type": "string",
                            "description": "Spec ID in storage (alternative to spec/spec_path)"
                        },
                        "function_name": {
                            "type": "string",
                            "description": "Function to generate task package for. Use 'all' to generate for all functions."
                        },
                        "language": {
                            "type": "string",
                            "enum": ["python", "typescript", "javascript"],
                            "description": "Target language for implementation",
                            "default": "python"
                        },
                        "output_dir": {
                            "type": "string",
                            "description": "Base directory for output (default: current directory)",
                            "default": "."
                        }
                    },
                    "required": ["function_name"]
                }
            },
            {
                "name": "sync_after_change",
                "description": "Sync task packages after spec changes. Analyzes impact and regenerates only affected tests, task packages (TASK.md, context.json, impl skeleton, pytest.ini).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "spec": {
                            "type": "object",
                            "description": "The NEW specification (after changes)"
                        },
                        "spec_path": {
                            "type": "string",
                            "description": "Path to NEW spec file (alternative to spec)"
                        },
                        "spec_id": {
                            "type": "string",
                            "description": "Spec ID in storage (alternative to spec/spec_path)"
                        },
                        "changes": {
                            "type": "array",
                            "items": {"type": "object"},
                            "description": "JSON Patch format changes that were made"
                        },
                        "language": {
                            "type": "string",
                            "enum": ["python", "typescript", "javascript"],
                            "description": "Target language for implementation",
                            "default": "python"
                        },
                        "output_dir": {
                            "type": "string",
                            "description": "Base directory for output (default: current directory)",
                            "default": "."
                        }
                    },
                    "required": ["changes"]
                }
            },
            # === Task Management Tools ===
            {
                "name": "activate_task",
                "description": "Activate a task for implementation. Only active tasks can have their impl files edited.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "function_name": {
                            "type": "string",
                            "description": "Name of the function/task to activate"
                        },
                        "language": {
                            "type": "string",
                            "enum": ["python", "typescript", "javascript"],
                            "description": "Target language for implementation",
                            "default": "python"
                        },
                        "output_dir": {
                            "type": "string",
                            "description": "Base directory containing tasks/ folder",
                            "default": "."
                        }
                    },
                    "required": ["function_name"]
                }
            },
            {
                "name": "deactivate_task",
                "description": "Deactivate a task without completing it. Use this to pause work on a task.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "function_name": {
                            "type": "string",
                            "description": "Name of the function/task to deactivate"
                        },
                        "cleanup_worktree": {
                            "type": "boolean",
                            "description": "If True, remove the worktree (default: False to preserve work)",
                            "default": False
                        },
                        "output_dir": {
                            "type": "string",
                            "description": "Base directory containing tasks/ folder",
                            "default": "."
                        }
                    },
                    "required": ["function_name"]
                }
            },
            {
                "name": "complete_task",
                "description": "Mark a task as completed. If task has worktree, commits changes, pushes, and creates PR (if enabled).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "function_name": {
                            "type": "string",
                            "description": "Name of the function/task to complete"
                        },
                        "test_results": {
                            "type": "object",
                            "description": "Test results from running task tests. Include 'passed' and 'failed' arrays.",
                            "properties": {
                                "passed": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "List of passed test names"
                                },
                                "failed": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "List of failed test names"
                                }
                            }
                        },
                        "commit_message": {
                            "type": "string",
                            "description": "Custom commit message (default: 'Implement {function_name}')"
                        },
                        "pr_title": {
                            "type": "string",
                            "description": "Custom PR title (default: 'Implement {function_name}')"
                        },
                        "pr_body": {
                            "type": "string",
                            "description": "Custom PR body (default: generated from TASK.md)"
                        },
                        "output_dir": {
                            "type": "string",
                            "description": "Base directory containing tasks/ folder",
                            "default": "."
                        }
                    },
                    "required": ["function_name"]
                }
            },
            {
                "name": "get_task_status",
                "description": "Get status of tasks (active, completed, pending). Returns all tasks if no function_name specified.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "function_name": {
                            "type": "string",
                            "description": "Optional: specific task to check status"
                        },
                        "output_dir": {
                            "type": "string",
                            "description": "Base directory containing tasks/ folder",
                            "default": "."
                        }
                    }
                }
            },
            {
                "name": "check_edit_permission",
                "description": "Check if a file can be edited based on active task status. Only impl files of active tasks are editable.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Path to the file to check"
                        },
                        "output_dir": {
                            "type": "string",
                            "description": "Base directory containing tasks/ folder",
                            "default": "."
                        }
                    },
                    "required": ["file_path"]
                }
            },
            {
                "name": "get_test_command",
                "description": "Get the command to run tests for a task",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "function_name": {
                            "type": "string",
                            "description": "Name of the function/task"
                        },
                        "output_dir": {
                            "type": "string",
                            "description": "Base directory containing tasks/ folder",
                            "default": "."
                        }
                    },
                    "required": ["function_name"]
                }
            },
            # === Project Configuration Tools ===
            {
                "name": "init_project",
                "description": "Initialize project configuration. Creates .mesh/config.json with language, paths, and git settings.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "language": {
                            "type": "string",
                            "enum": ["python", "typescript", "javascript"],
                            "description": "Project language",
                            "default": "python"
                        },
                        "src_path": {
                            "type": "string",
                            "description": "Path for implementation files (default: 'src' for Python, 'src/functions' for TypeScript)"
                        },
                        "test_framework": {
                            "type": "string",
                            "enum": ["pytest", "jest", "vitest"],
                            "description": "Test framework (default: based on language)"
                        },
                        "base_branch": {
                            "type": "string",
                            "description": "Base branch for PRs (default: 'main')"
                        },
                        "auto_worktree": {
                            "type": "boolean",
                            "description": "Auto-create worktree on task activation (default: true)"
                        },
                        "auto_pr": {
                            "type": "boolean",
                            "description": "Auto-create PR on task completion (default: true)"
                        },
                        "output_dir": {
                            "type": "string",
                            "description": "Base directory for the project",
                            "default": "."
                        }
                    }
                }
            },
            {
                "name": "get_project_config",
                "description": "Get current project configuration",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "output_dir": {
                            "type": "string",
                            "description": "Base directory for the project",
                            "default": "."
                        }
                    }
                }
            },
            # === Frontend Generation Tools ===
            {
                "name": "generate_typescript_types",
                "description": "Generate TypeScript type definitions from TRIR specification. Generates interfaces for entities and function input/output types.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "spec": {
                            "type": "object",
                            "description": "The specification"
                        },
                        "spec_path": {
                            "type": "string",
                            "description": "Path to spec file (alternative to spec)"
                        },
                        "spec_id": {
                            "type": "string",
                            "description": "Spec ID in storage (alternative to spec/spec_path)"
                        },
                        "entity_name": {
                            "type": "string",
                            "description": "Generate types for specific entity only"
                        },
                        "function_name": {
                            "type": "string",
                            "description": "Generate types for specific function only"
                        },
                        "output_path": {
                            "type": "string",
                            "description": "Write output to file path"
                        }
                    }
                }
            },
            {
                "name": "generate_openapi",
                "description": "Generate OpenAPI 3.1 schema from TRIR specification. Converts functions to paths and entities to component schemas.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "spec": {
                            "type": "object",
                            "description": "The specification"
                        },
                        "spec_path": {
                            "type": "string",
                            "description": "Path to spec file (alternative to spec)"
                        },
                        "spec_id": {
                            "type": "string",
                            "description": "Spec ID in storage (alternative to spec/spec_path)"
                        },
                        "base_url": {
                            "type": "string",
                            "description": "API base URL",
                            "default": "/api/v1"
                        },
                        "output_path": {
                            "type": "string",
                            "description": "Write output to file path"
                        },
                        "format": {
                            "type": "string",
                            "enum": ["json", "yaml"],
                            "description": "Output format",
                            "default": "json"
                        }
                    }
                }
            },
            {
                "name": "generate_zod_schemas",
                "description": "Generate Zod validation schemas from TRIR specification. Includes refinements from pre conditions where possible, marks server-side-only validations as comments.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "spec": {
                            "type": "object",
                            "description": "The specification"
                        },
                        "spec_path": {
                            "type": "string",
                            "description": "Path to spec file (alternative to spec)"
                        },
                        "spec_id": {
                            "type": "string",
                            "description": "Spec ID in storage (alternative to spec/spec_path)"
                        },
                        "entity_name": {
                            "type": "string",
                            "description": "Generate schema for specific entity only"
                        },
                        "function_name": {
                            "type": "string",
                            "description": "Generate schema for specific function only"
                        },
                        "output_path": {
                            "type": "string",
                            "description": "Write output to file path"
                        }
                    }
                }
            },
            {
                "name": "generate_all_frontend",
                "description": "Generate all frontend artifacts (TypeScript types, OpenAPI schema, Zod schemas) in one call.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "spec": {
                            "type": "object",
                            "description": "The specification"
                        },
                        "spec_path": {
                            "type": "string",
                            "description": "Path to spec file (alternative to spec)"
                        },
                        "spec_id": {
                            "type": "string",
                            "description": "Spec ID in storage (alternative to spec/spec_path)"
                        },
                        "output_dir": {
                            "type": "string",
                            "description": "Directory to write output files"
                        },
                        "base_url": {
                            "type": "string",
                            "description": "API base URL for OpenAPI",
                            "default": "/api/v1"
                        }
                    },
                    "required": ["output_dir"]
                }
            }
        ]

    def call_tool(self, name: str, arguments: dict) -> dict:
        """Execute a tool and return results.

        Dispatches to the appropriate handler from the handlers package.
        """
        if name not in HANDLERS:
            return {"error": f"Unknown tool: {name}"}

        try:
            handler = HANDLERS[name]
            return handler(self.validator, self.storage, arguments)
        except Exception as e:
            return {"error": str(e), "error_type": type(e).__name__}

def create_mcp_server():
    """Create and configure MCP server"""
    if not HAS_MCP:
        raise ImportError("mcp package is required: pip install mcp")

    server = Server("the_mesh")
    mesh = MeshServer()

    @server.list_tools()
    async def list_tools():
        return [
            Tool(
                name=tool["name"],
                description=tool["description"],
                inputSchema=tool["inputSchema"]
            )
            for tool in mesh.get_tools()
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict):
        result = mesh.call_tool(name, arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    return server


async def main():
    """Run the MCP server"""
    server = create_mcp_server()
    options = InitializationOptions(
        server_name="the_mesh",
        server_version="0.1.0",
        capabilities=ServerCapabilities(tools={})
    )
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, options)


def main_sync():
    """Synchronous entry point for CLI"""
    import asyncio
    asyncio.run(main())


if __name__ == "__main__":
    main_sync()
