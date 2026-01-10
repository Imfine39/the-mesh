# CLAUDE.md - The Mesh Development Context

## Quick Reference

### Environment
```bash
# Virtual environment (relative to project root)
.venv/

# Activate venv
source .venv/bin/activate

# Python version: 3.10+
```

### Common Commands
```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_validator.py -v

# Run specific test class
python -m pytest tests/test_validator.py::TestBasicValidation -v

# Run with coverage
python -m pytest tests/ --cov=src --cov-report=html

# Lint
python -m ruff check src/
```

### Test Files by Feature
| Feature | Test File |
|---------|-----------|
| Core Validation | `tests/test_validator.py` |
| TypeScript Generation | `tests/test_typescript_gen.py` |
| OpenAPI Generation | `tests/test_openapi_gen.py` |
| Zod Generation | `tests/test_zod_gen.py` |
| Jest Generation | `tests/test_jest_gen.py` |
| Frontend Validation | `tests/test_frontend_validation.py` |
| Task Manager | `tests/test_task_manager.py` |
| Dependency Graph | `tests/test_graph.py` |

---

## Project Overview

The Mesh is a specification-driven development framework integrated with Claude Code via Skills. It uses TRIR (Typed Relational IR) format for specifications.

### Core Concepts
- **TRIR Spec**: JSON format defining entities, functions, scenarios, stateMachines, views, routes, and more
- **Validation**: 21 semantic validation phases with error codes (SCH/REF/TYP/VAL/FSM/CNS/FE)
- **Generation**: TypeScript types, OpenAPI schemas, Zod validators, pytest/Jest tests (AT/UT/PC/ST)
- **Task Management**: Git worktree-based workflow with PR automation

---

## Project Structure

```
src/the_mesh/
├── core/                    # Core functionality
│   ├── validator.py         # Main validator (2500+ lines)
│   ├── errors.py            # Error types
│   ├── storage/             # Spec storage
│   │   └── spec_storage.py
│   ├── task/                # Task management
│   │   └── task_manager.py
│   ├── handlers/            # Tool implementations (38 handlers)
│   │   ├── validation.py    # 10 handlers
│   │   ├── spec_crud.py     # 10 handlers
│   │   ├── generation.py    # 4 handlers
│   │   ├── task.py          # 6 handlers
│   │   ├── project.py       # 2 handlers
│   │   └── frontend.py      # 6 handlers
│   └── domain/              # Domain validation mixins
├── graph/                   # Dependency analysis
│   └── graph.py             # DependencyGraph
├── generators/              # Code generators (15 generators)
│   ├── typescript_gen.py    # TypeScript interfaces
│   ├── openapi_gen.py       # OpenAPI 3.1 schemas
│   ├── zod_gen.py           # Zod validators
│   ├── pytest_gen.py        # Pytest AT (acceptance tests)
│   ├── pytest_unit_gen.py   # Pytest UT (unit tests)
│   ├── postcondition_gen.py # Pytest PC (postcondition tests)
│   ├── state_transition_gen.py # Pytest ST (state transition tests)
│   ├── jest_gen.py          # Jest AT
│   ├── jest_unit_gen.py     # Jest UT
│   ├── jest_postcondition_gen.py # Jest PC
│   ├── jest_state_transition_gen.py # Jest ST
│   ├── human_readable_gen.py # ER diagrams, Mermaid, Markdown
│   ├── yaml_gen.py          # YAML export
│   └── task_package_gen.py  # Implementation packages
├── config/                  # Project configuration
├── hooks/                   # Git integration
└── schemas/                 # JSON Schema definitions
    └── mesh.schema.json     # Main spec schema
```

---

## Key Files

### Validation
- `src/the_mesh/core/validator.py` - Main validation logic
  - `validate()` method runs all validation phases
  - Error codes: SCH-xxx, REF-xxx, TYP-xxx, VAL-xxx, FSM-xxx, CNS-xxx, FE-xxx

### Handlers
- `src/the_mesh/core/handlers/__init__.py` - Handler registry (38 handlers)

### Generators
- TypeScript: `src/the_mesh/generators/typescript_gen.py`
- OpenAPI: `src/the_mesh/generators/openapi_gen.py`
- Zod: `src/the_mesh/generators/zod_gen.py`
- Tests: `pytest_gen.py`, `postcondition_gen.py`, `state_transition_gen.py`, etc.

### Schema
- `src/the_mesh/schemas/mesh.schema.json` - TRIR JSON Schema

---

## Handler Tools Summary (38 total)

### Validation (10 tools)
`validate_spec`, `validate_expression`, `validate_partial`, `get_fix_suggestion`, `suggest_completion`, `analyze_impact`, `check_reference`, `get_entity_schema`, `list_valid_values`, `get_dependencies`

### Generation (4 tools)
`generate_tests`, `generate_task_package`, `get_function_context`, `sync_after_change`

### Frontend (6 tools)
`generate_typescript_types`, `generate_openapi`, `generate_zod_schemas`, `generate_all_frontend`, `export_human_readable`, `export_yaml`

### Spec Storage (10 tools)
`spec_list`, `spec_read`, `spec_write`, `spec_delete`, `spec_get_section`, `spec_update_section`, `spec_delete_section`, `spec_create_from_template`, `spec_list_backups`, `spec_restore_backup`

### Task Management (6 tools)
`activate_task`, `deactivate_task`, `complete_task`, `get_task_status`, `check_edit_permission`, `get_test_command`

### Project (2 tools)
`init_project`, `get_project_config`

---

## Test Generation Frameworks

### Test Types (AT/UT/PC/ST)
| Type | Purpose | Catches |
|------|---------|---------|
| AT (Acceptance) | Scenario-based tests | Logic errors |
| UT (Unit) | Boundaries, error cases | Edge cases |
| PC (PostCondition) | Verify create/update/delete | **Field save issues** |
| ST (State Transition) | State machine behavior | Invalid transitions |

### Framework Options
```
pytest, pytest-ut, pytest-postcondition, pytest-state
jest, jest-ts, jest-ut, jest-ts-ut, jest-postcondition, jest-ts-postcondition, jest-state, jest-ts-state
```

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

## TRIR Spec Sections

Main sections supported by the schema:
- `meta`, `state`, `functions`, `scenarios`, `derived`, `invariants`
- `stateMachines`, `events`, `subscriptions`, `sagas`, `schedules`
- `roles`, `gateways`, `deadlines`, `externalServices`
- `constraints`, `relations`, `dataPolicies`, `auditPolicies`
- `views`, `routes`, `requirements`

---

## TRIR Expression Types

Expressions use tagged union with `type` discriminator:
- `literal`, `ref`, `input`, `binary`, `unary`, `agg`, `call`, `if`, `let`, `match`
- `list`, `range`, `access`, `temporal`, `state`, `principal`, `case`, `switch`, `coalesce`

Binary operators: `add`, `sub`, `mul`, `div`, `eq`, `ne`, `lt`, `le`, `gt`, `ge`, `and`, `or`, `in`, `not_in`, `like`

---

## Development Workflow

1. **Make changes** to source files
2. **Run relevant tests**: `python -m pytest tests/test_<feature>.py -v`
3. **Run all tests**: `python -m pytest tests/ -v`
4. **Check lint**: `python -m ruff check src/`
