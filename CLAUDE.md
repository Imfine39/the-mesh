# CLAUDE.md - The Mesh Development Context

## Quick Reference

### Environment
```bash
# Virtual environment location
/home/nick/projects/the-mesh/.venv

# Activate venv
source .venv/bin/activate

# Python version: 3.10+
```

### Common Commands
```bash
# Run all tests
.venv/bin/python -m pytest tests/ -v

# Run specific test file
.venv/bin/python -m pytest tests/test_validator.py -v

# Run specific test class
.venv/bin/python -m pytest tests/test_validator.py::TestBasicValidation -v

# Run with coverage
.venv/bin/python -m pytest tests/ --cov=src --cov-report=html

# Lint
.venv/bin/python -m ruff check src/

# Run MCP server directly
.venv/bin/python -m the_mesh.mcp.server
```

### Test Files by Feature
| Feature | Test File |
|---------|-----------|
| Core Validation | `tests/test_validator.py` |
| TypeScript Generation | `tests/test_typescript_gen.py` |
| OpenAPI Generation | `tests/test_openapi_gen.py` |
| Zod Generation | `tests/test_zod_gen.py` |
| Frontend Validation | `tests/test_frontend_validation.py` |
| Task Manager | `tests/test_task_manager.py` |
| Dependency Graph | `tests/test_graph.py` |

---

## Project Overview

The Mesh is a specification-driven development framework integrated with Claude Code via MCP. It uses TRIR (Typed Relational IR) format for specifications.

### Core Concepts
- **TRIR Spec**: JSON format defining entities, functions, scenarios, views, routes
- **Validation**: 21 semantic validation phases with error codes (SCH/REF/TYP/VAL/FSM/CNS/FE)
- **Generation**: TypeScript types, OpenAPI schemas, Zod validators, pytest/Jest tests
- **Task Management**: Git worktree-based workflow with PR automation

---

## Project Structure

```
src/the_mesh/
├── core/                    # Validation engine
│   ├── validator.py         # Main validator (2500+ lines)
│   ├── errors.py            # Error types
│   ├── engine.py            # High-level engine
│   └── domain/              # Domain validation mixins
├── graph/                   # Dependency analysis
│   └── graph.py             # DependencyGraph
├── generators/              # Code generators
│   ├── typescript_gen.py    # TypeScript interfaces
│   ├── openapi_gen.py       # OpenAPI 3.1 schemas
│   ├── zod_gen.py           # Zod validators
│   ├── pytest_gen.py        # Pytest test generation
│   ├── jest_gen.py          # Jest test generation
│   └── task_package_gen.py  # Implementation packages
├── mcp/                     # MCP server
│   ├── server.py            # Tool definitions (40+ tools)
│   ├── storage.py           # Spec storage
│   ├── task_manager.py      # Task workflow
│   └── handlers/            # Tool implementations
│       ├── validation.py
│       ├── spec_crud.py
│       ├── generation.py
│       ├── task.py
│       ├── project.py
│       └── frontend.py
├── config/                  # Project configuration
├── hooks/                   # Git integration
└── schemas/                 # JSON Schema definitions
    ├── mesh.schema.json     # Main spec schema
    └── expression.schema.json
```

---

## Key Files

### Validation
- `src/the_mesh/core/validator.py` - Main validation logic
  - `validate()` method runs all validation phases
  - Error codes: SCH-xxx, REF-xxx, TYP-xxx, VAL-xxx, FSM-xxx, CNS-xxx, FE-xxx

### MCP Server
- `src/the_mesh/mcp/server.py` - Tool definitions
- `src/the_mesh/mcp/handlers/__init__.py` - Handler registry (36 handlers)

### Generators
- TypeScript: `src/the_mesh/generators/typescript_gen.py`
- OpenAPI: `src/the_mesh/generators/openapi_gen.py`
- Zod: `src/the_mesh/generators/zod_gen.py`

### Schema
- `src/the_mesh/schemas/mesh.schema.json` - TRIR JSON Schema (39 KB)

---

## MCP Tools Summary

### Validation (9 tools)
`validate_spec`, `validate_expression`, `validate_partial`, `get_fix_suggestion`, `analyze_impact`, `check_reference`, `get_entity_schema`, `list_valid_values`, `get_dependencies`

### Generation (7 tools)
`generate_tests`, `generate_typescript_types`, `generate_openapi`, `generate_zod_schemas`, `generate_all_frontend`, `generate_task_package`, `get_function_context`

### Spec Storage (8 tools)
`spec_list`, `spec_read`, `spec_write`, `spec_delete`, `spec_get_section`, `spec_update_section`, `spec_list_backups`, `spec_restore_backup`, `spec_create_from_template`

### Task Management (6 tools)
`activate_task`, `deactivate_task`, `complete_task`, `get_task_status`, `check_edit_permission`, `get_test_command`

### Project (2 tools)
`init_project`, `get_project_config`

---

## Validation Error Codes

| Prefix | Category | Example |
|--------|----------|---------|
| SCH- | Schema | JSON Schema violations |
| REF- | Reference | Invalid entity/function references |
| TYP- | Type | Type mismatches, enum errors |
| VAL- | Validation | Expression/logic errors |
| FSM- | State Machine | Transition/state errors |
| CNS- | Constraint | Constraint violations |
| FE- | Frontend | View/route validation (FE-002~005) |

---

## TRIR Expression Types

Expressions use tagged union with `type` discriminator:
- `literal`, `ref`, `input`, `binary`, `unary`, `agg`, `call`, `if`, `let`, `match`
- `list`, `range`, `access`, `temporal`, `state`, `principal`, `case`, `switch`, `coalesce`

Binary operators: `add`, `sub`, `mul`, `div`, `eq`, `ne`, `lt`, `le`, `gt`, `ge`, `and`, `or`, `in`, `not_in`, `like`

---

## Development Workflow

1. **Make changes** to source files
2. **Run relevant tests**: `.venv/bin/python -m pytest tests/test_<feature>.py -v`
3. **Run all tests**: `.venv/bin/python -m pytest tests/ -v`
4. **Check lint**: `.venv/bin/python -m ruff check src/`

---

## MCP Configuration

Add to `.mcp.json`:
```json
{
  "mcpServers": {
    "the_mesh": {
      "command": "/home/nick/projects/the-mesh/.venv/bin/python",
      "args": ["-m", "the_mesh.mcp.server"],
      "env": {
        "PYTHONPATH": "/home/nick/projects/the-mesh/src"
      }
    }
  }
}
```
