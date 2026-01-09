# The Mesh

**Specification-driven development framework for AI-assisted coding with Claude Code**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Version](https://img.shields.io/badge/version-0.2.0-green.svg)](https://github.com/the-mesh/the-mesh)

The Mesh provides a **single source of truth** for specification-driven development using the **TRIR (Typed Relational IR)** format. It validates specifications, generates test code, creates API schemas, and manages implementation workflows—all integrated with Claude Code via MCP (Model Context Protocol).

## Features

| Feature | Description |
|---------|-------------|
| **Specification Validation** | Validates `.mesh.json` specs against JSON Schema with 21 semantic validation phases |
| **Test Generation** | Generates pytest/Jest tests from scenario definitions |
| **Type Generation** | Creates TypeScript types, OpenAPI 3.1 schemas, Zod validators |
| **Task Management** | Manages implementation workflows with git worktrees and PR automation |
| **Dependency Analysis** | Analyzes entity relationships and change impact |
| **Frontend Validation** | Validates View/Route definitions against backend spec |

## Quick Start

```bash
# Clone and setup
git clone https://github.com/the-mesh/the-mesh.git
cd the-mesh
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# Verify installation
pytest tests/ -v
```

## TRIR Specification Format

Specifications are written in `.mesh.json` files:

```json
{
  "meta": {
    "id": "invoice-system",
    "title": "Invoice Processing System",
    "version": "1.0.0"
  },
  "state": {
    "invoice": {
      "description": "Invoice entity",
      "fields": {
        "id": { "type": "string", "required": true },
        "customer_id": { "type": { "ref": "customer" }, "required": true },
        "amount": { "type": "int", "required": true },
        "status": { "type": { "enum": ["draft", "open", "closed"] }, "required": true }
      }
    },
    "customer": {
      "fields": {
        "id": { "type": "string", "required": true },
        "name": { "type": "string", "required": true }
      }
    }
  },
  "functions": {
    "create_invoice": {
      "description": "Create a new invoice",
      "input": {
        "customer_id": { "type": "string", "required": true },
        "amount": { "type": "int", "required": true }
      },
      "pre": [
        {
          "expr": {
            "type": "binary", "op": "gt",
            "left": { "type": "input", "name": "amount" },
            "right": { "type": "literal", "value": 0 }
          },
          "reason": "Amount must be positive"
        }
      ],
      "post": [
        {
          "action": {
            "create": "invoice",
            "with": {
              "id": { "type": "call", "name": "uuid" },
              "customer_id": { "type": "input", "name": "customer_id" },
              "amount": { "type": "input", "name": "amount" },
              "status": { "type": "literal", "value": "draft" }
            }
          }
        }
      ],
      "error": [
        { "code": "CUSTOMER_NOT_FOUND", "when": { "type": "ref", "path": "..." }, "reason": "Customer not found", "http_status": 404 }
      ]
    }
  },
  "scenarios": {
    "valid_invoice_creation": {
      "title": "Create valid invoice",
      "given": {
        "customer": [{ "id": "cust1", "name": "ACME Corp" }]
      },
      "when": {
        "call": "create_invoice",
        "input": { "customer_id": "cust1", "amount": 1000 }
      },
      "then": {
        "success": true,
        "assert": [
          {
            "type": "binary", "op": "eq",
            "left": { "type": "ref", "path": "result.status" },
            "right": { "type": "literal", "value": "draft" }
          }
        ]
      }
    }
  }
}
```

## MCP Tools (40+)

### Validation Tools
| Tool | Description |
|------|-------------|
| `validate_spec` | Validate complete specification with structured errors |
| `validate_expression` | Validate single expression with context |
| `validate_partial` | Incremental validation (JSON Patch format) |
| `get_fix_suggestion` | Auto-fix suggestions for validation errors |
| `analyze_impact` | Change impact analysis |
| `check_reference` | Verify reference path validity |
| `get_entity_schema` | Get entity schema information |
| `list_valid_values` | List valid enum/reference values |
| `get_dependencies` | Get element dependencies |

### Code Generation Tools
| Tool | Description |
|------|-------------|
| `generate_tests` | Generate pytest/Jest tests (6 variants) |
| `generate_typescript_types` | TypeScript interface generation |
| `generate_openapi` | OpenAPI 3.1 schema (JSON/YAML) |
| `generate_zod_schemas` | Zod validation with refinements |
| `generate_all_frontend` | All frontend artifacts in one call |
| `generate_task_package` | Complete implementation package |
| `get_function_context` | Minimal implementation context |

### Task Management Tools
| Tool | Description |
|------|-------------|
| `activate_task` | Start task (creates git worktree) |
| `deactivate_task` | Pause task |
| `complete_task` | Finish task (commit, push, PR) |
| `get_task_status` | Check task status |
| `check_edit_permission` | Verify file edit permissions |
| `get_test_command` | Get test run command |

### Spec Storage Tools
| Tool | Description |
|------|-------------|
| `spec_list` | List stored specs |
| `spec_read` / `spec_write` | Read/write specs |
| `spec_get_section` / `spec_update_section` | Section operations |
| `spec_list_backups` / `spec_restore_backup` | Backup management |
| `spec_create_from_template` | Create from template |

### Project Tools
| Tool | Description |
|------|-------------|
| `init_project` | Initialize project config |
| `get_project_config` | Get project configuration |

## Claude Code Integration

Add to your project's `.mcp.json`:

```json
{
  "mcpServers": {
    "the_mesh": {
      "command": "/path/to/the-mesh/.venv/bin/python",
      "args": ["-m", "the_mesh.mcp.server"],
      "env": {
        "PYTHONPATH": "/path/to/the-mesh/src"
      }
    }
  }
}
```

## Specification Sections

| Section | Purpose |
|---------|---------|
| `meta` | **Required**. Project metadata (id, title, version) |
| `state` | **Required**. Entity definitions (database schema) |
| `derived` | Computed fields with formulas |
| `functions` | Business logic with pre/post conditions |
| `scenarios` | Test cases (given/when/then) |
| `invariants` | Always-true conditions |
| `stateMachines` | State transition definitions |
| `events` | Domain events |
| `subscriptions` | Event handlers |
| `roles` | RBAC definitions |
| `sagas` | Long-running transactions |
| `schedules` | Scheduled jobs |
| `views` | UI view definitions |
| `routes` | Frontend routing |

## Field Types

```json
// Primitives
"type": "string"      // Text
"type": "int"         // Integer
"type": "float"       // Decimal
"type": "bool"        // Boolean
"type": "datetime"    // ISO datetime
"type": "text"        // Long text

// Reference (Foreign Key)
"type": { "ref": "customer", "on_delete": "cascade" }

// Enum
"type": { "enum": ["draft", "open", "closed"] }

// List
"type": { "list": "string" }
```

## Expression Types (18+)

| Type | Purpose | Example |
|------|---------|---------|
| `literal` | Constant value | `{ "type": "literal", "value": 100 }` |
| `ref` | Field reference | `{ "type": "ref", "path": "invoice.amount" }` |
| `input` | Function input | `{ "type": "input", "name": "amount" }` |
| `binary` | Operations | `{ "type": "binary", "op": "gt", "left": ..., "right": ... }` |
| `agg` | Aggregation | `{ "type": "agg", "op": "sum", "from": "invoice", "expr": ... }` |
| `call` | Function call | `{ "type": "call", "name": "uuid" }` |
| `if` | Conditional | `{ "type": "if", "cond": ..., "then": ..., "else": ... }` |
| `temporal` | Time queries | `{ "type": "temporal", "op": "at", ... }` |
| `state` | State machine | `{ "type": "state", "op": "is_in", "machine": "invoice_status" }` |
| `principal` | Access control | `{ "type": "principal", "op": "has_role", "role": "admin" }` |

Binary operators: `add`, `sub`, `mul`, `div`, `eq`, `ne`, `lt`, `le`, `gt`, `ge`, `and`, `or`, `in`, `not_in`, `like`

## Project Structure

```
the-mesh/
├── src/the_mesh/
│   ├── core/               # Validation engine
│   │   ├── validator.py    # Main validator (2500+ lines)
│   │   ├── errors.py       # Error types
│   │   ├── engine.py       # High-level engine
│   │   └── domain/         # Domain validation mixins
│   ├── graph/              # Dependency analysis
│   │   └── graph.py        # DependencyGraph (800+ lines)
│   ├── generators/         # Code generators
│   │   ├── pytest_gen.py
│   │   ├── jest_gen.py
│   │   ├── typescript_gen.py
│   │   ├── openapi_gen.py
│   │   ├── zod_gen.py
│   │   └── task_package_gen.py
│   ├── mcp/                # MCP server
│   │   ├── server.py       # Tool definitions (950+ lines)
│   │   ├── storage.py      # Spec storage
│   │   ├── task_manager.py # Task workflow
│   │   └── handlers/       # Tool implementations
│   ├── config/             # Project configuration
│   ├── hooks/              # Git integration
│   └── schemas/            # JSON Schema definitions
│       ├── mesh.schema.json      # (39 KB)
│       └── expression.schema.json # (21 KB)
├── tests/                  # Test suite
├── examples/               # Example specifications
└── pyproject.toml
```

## Validation Error Codes

| Code | Category | Description |
|------|----------|-------------|
| SCH-xxx | Schema | JSON Schema violations |
| REF-xxx | Reference | Invalid entity/function references |
| TYP-xxx | Type | Type mismatches, enum errors |
| VAL-xxx | Validation | Expression/logic errors |
| FSM-xxx | State Machine | Transition/state errors |
| CNS-xxx | Constraint | Constraint violations |
| FE-xxx | Frontend | View/route validation errors |

## Development

```bash
# Run all tests
pytest tests/ -v

# Run specific test
pytest tests/test_validator.py::TestBasicValidation -v

# With coverage
pytest tests/ --cov=src --cov-report=html

# Lint
ruff check src/
```

## Examples

See the `examples/` directory:
- `accounting.mesh.json` - Invoice/payment system with Japanese labels
- `reservation.mesh.json` - Room reservation system
- `ar_clearing_real.mesh.json` - Complex AR clearing with state machines

## License

MIT License
