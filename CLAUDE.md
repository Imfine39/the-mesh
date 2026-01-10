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
python -m pytest .claude/skills/the-mesh/tests/ -v

# Run specific test file
python -m pytest .claude/skills/the-mesh/tests/test_validator.py -v

# Run specific test class
python -m pytest .claude/skills/the-mesh/tests/test_validator.py::TestBasicValidation -v

# Run with coverage
python -m pytest .claude/skills/the-mesh/tests/ --cov=.claude/skills/the-mesh/lib --cov-report=html

# Lint
python -m ruff check .claude/skills/the-mesh/lib/
```

### CLI Scripts
```bash
# Validate spec
python .claude/skills/the-mesh/scripts/mesh_validate.py PROJECT_NAME

# Generate tests
python .claude/skills/the-mesh/scripts/mesh_generate.py PROJECT_NAME --type tests --framework pytest-ut

# Manage specs
python .claude/skills/the-mesh/scripts/mesh_spec.py list

# Task management
python .claude/skills/the-mesh/scripts/mesh_task.py status
```

### Test Files by Feature
| Feature | Test File |
|---------|-----------|
| Core Validation | `.claude/skills/the-mesh/tests/test_validator.py` |
| TypeScript Generation | `.claude/skills/the-mesh/tests/test_typescript_gen.py` |
| OpenAPI Generation | `.claude/skills/the-mesh/tests/test_openapi_gen.py` |
| Zod Generation | `.claude/skills/the-mesh/tests/test_zod_gen.py` |
| Jest Generation | `.claude/skills/the-mesh/tests/test_jest_gen.py` |
| Frontend Validation | `.claude/skills/the-mesh/tests/test_frontend_validation.py` |
| Task Manager | `.claude/skills/the-mesh/tests/test_task_manager.py` |
| Dependency Graph | `.claude/skills/the-mesh/tests/test_graph.py` |

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
.claude/skills/the-mesh/           # Self-contained skill (portable)
├── SKILL.md                       # Skill definition
├── scripts/                       # CLI entry points
│   ├── mesh_validate.py
│   ├── mesh_generate.py
│   ├── mesh_spec.py
│   └── mesh_task.py
├── lib/                           # Core library
│   ├── core/                      # Core functionality
│   │   ├── validator.py           # Main validator (2500+ lines)
│   │   ├── errors.py              # Error types
│   │   ├── storage/               # Spec storage
│   │   ├── task/                  # Task management
│   │   ├── handlers/              # Tool implementations (38 handlers)
│   │   └── domain/                # Domain validation mixins
│   ├── graph/                     # Dependency analysis
│   │   └── graph.py               # DependencyGraph
│   ├── generators/                # Code generators
│   │   ├── python/                # pytest generators (AT/UT/PC/ST)
│   │   ├── typescript/            # jest generators (AT/UT/PC/ST)
│   │   ├── typescript_gen.py      # TypeScript interfaces
│   │   ├── openapi_gen.py         # OpenAPI 3.1 schemas
│   │   ├── zod_gen.py             # Zod validators
│   │   └── task_package_gen.py    # Implementation packages
│   ├── config/                    # Project configuration
│   └── schemas/                   # JSON Schema definitions
│       └── mesh.schema.json       # Main spec schema
└── tests/                         # Unit tests

.claude/skills/the-mosaic/         # Requirements definition skill (WIP)
├── SKILL.md
└── docs/
    ├── IDEAS.md                   # Design concepts
    └── MOCK_FORMAT.md             # Mock HTML format spec
```

---

## Key Files

### Validation
- `.claude/skills/the-mesh/lib/core/validator.py` - Main validation logic
  - `validate()` method runs all validation phases
  - Error codes: SCH-xxx, REF-xxx, TYP-xxx, VAL-xxx, FSM-xxx, CNS-xxx, FE-xxx

### Handlers
- `.claude/skills/the-mesh/lib/core/handlers/__init__.py` - Handler registry (38 handlers)

### Generators
- TypeScript: `.claude/skills/the-mesh/lib/generators/typescript_gen.py`
- OpenAPI: `.claude/skills/the-mesh/lib/generators/openapi_gen.py`
- Zod: `.claude/skills/the-mesh/lib/generators/zod_gen.py`
- Pytest: `.claude/skills/the-mesh/lib/generators/python/`
- Jest: `.claude/skills/the-mesh/lib/generators/typescript/`

### Schema
- `.claude/skills/the-mesh/lib/schemas/mesh.schema.json` - TRIR JSON Schema

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
pytest-ut, pytest-at, pytest-pc, pytest-st
jest-ut, jest-at, jest-pc, jest-st
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

1. **Make changes** to source files in `.claude/skills/the-mesh/lib/`
2. **Run relevant tests**: `python -m pytest .claude/skills/the-mesh/tests/test_<feature>.py -v`
3. **Run all tests**: `python -m pytest .claude/skills/the-mesh/tests/ -v`
4. **Check lint**: `python -m ruff check .claude/skills/the-mesh/lib/`
