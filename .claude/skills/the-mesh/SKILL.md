---
name: the-mesh
description: "Specification-driven development framework using TRIR (Typed Relational IR). Actions: spec, implement, test, validate, generate. Use for: API development, backend functions, database entities, test generation, type generation. Triggers: implement function, add entity, add field, create test, generate types, validate spec, TDD, spec-driven."
---

# The Mesh - Specification-Driven Development

TRIR (Typed Relational IR) specification framework for test-driven, spec-first development.

## Directory Structure

This skill is self-contained and portable across projects:

```
.claude/skills/the-mesh/
├── SKILL.md              # This file
├── scripts/              # CLI entry points
│   ├── mesh_validate.py
│   ├── mesh_generate.py
│   ├── mesh_spec.py
│   └── mesh_task.py
├── lib/                  # Core library
│   ├── core/             # Validator, handlers, storage
│   ├── generators/       # Test & type generators
│   │   ├── python/       # pytest generators
│   │   └── typescript/   # jest generators
│   ├── graph/            # Dependency analysis
│   ├── config/           # Project config
│   └── schemas/          # JSON Schema definitions
└── tests/                # Unit tests
```

## Quick Commands

CLI scripts are available at `.claude/skills/the-mesh/scripts/`:

### Validate Spec
```bash
python .claude/skills/the-mesh/scripts/mesh_validate.py PROJECT_NAME
```

### Generate Tests
```bash
# Python - Unit tests (constraint-based, executable)
python .claude/skills/the-mesh/scripts/mesh_generate.py PROJECT_NAME --type tests --framework pytest-ut

# Python - Acceptance tests
python .claude/skills/the-mesh/scripts/mesh_generate.py PROJECT_NAME --type tests --framework pytest-at --function create_order

# Python - PostCondition tests
python .claude/skills/the-mesh/scripts/mesh_generate.py PROJECT_NAME --type tests --framework pytest-pc

# Python - State transition tests
python .claude/skills/the-mesh/scripts/mesh_generate.py PROJECT_NAME --type tests --framework pytest-st

# TypeScript - Unit tests
python .claude/skills/the-mesh/scripts/mesh_generate.py PROJECT_NAME --type tests --framework jest-ut

# TypeScript - Acceptance tests
python .claude/skills/the-mesh/scripts/mesh_generate.py PROJECT_NAME --type tests --framework jest-at --function create_order

# TypeScript - PostCondition tests
python .claude/skills/the-mesh/scripts/mesh_generate.py PROJECT_NAME --type tests --framework jest-pc

# TypeScript - State transition tests
python .claude/skills/the-mesh/scripts/mesh_generate.py PROJECT_NAME --type tests --framework jest-st

# Specialized Test Types (Python)
python .claude/skills/the-mesh/scripts/mesh_generate.py PROJECT_NAME --type tests --framework pytest-idem   # Idempotency
python .claude/skills/the-mesh/scripts/mesh_generate.py PROJECT_NAME --type tests --framework pytest-conc   # Concurrency
python .claude/skills/the-mesh/scripts/mesh_generate.py PROJECT_NAME --type tests --framework pytest-authz  # Authorization
python .claude/skills/the-mesh/scripts/mesh_generate.py PROJECT_NAME --type tests --framework pytest-empty  # Empty/Null
python .claude/skills/the-mesh/scripts/mesh_generate.py PROJECT_NAME --type tests --framework pytest-ref    # Reference Integrity
python .claude/skills/the-mesh/scripts/mesh_generate.py PROJECT_NAME --type tests --framework pytest-time   # Temporal

# Specialized Test Types (TypeScript)
python .claude/skills/the-mesh/scripts/mesh_generate.py PROJECT_NAME --type tests --framework jest-idem   # Idempotency
python .claude/skills/the-mesh/scripts/mesh_generate.py PROJECT_NAME --type tests --framework jest-conc   # Concurrency
python .claude/skills/the-mesh/scripts/mesh_generate.py PROJECT_NAME --type tests --framework jest-authz  # Authorization
python .claude/skills/the-mesh/scripts/mesh_generate.py PROJECT_NAME --type tests --framework jest-empty  # Empty/Null
python .claude/skills/the-mesh/scripts/mesh_generate.py PROJECT_NAME --type tests --framework jest-ref    # Reference Integrity
python .claude/skills/the-mesh/scripts/mesh_generate.py PROJECT_NAME --type tests --framework jest-time   # Temporal

# Complete task package (all test types)
python .claude/skills/the-mesh/scripts/mesh_generate.py PROJECT_NAME --type task-package --function create_order
```

### Generate Types
```bash
# TypeScript interfaces
python .claude/skills/the-mesh/scripts/mesh_generate.py PROJECT_NAME --type typescript

# OpenAPI schema
python .claude/skills/the-mesh/scripts/mesh_generate.py PROJECT_NAME --type openapi

# Zod validators
python .claude/skills/the-mesh/scripts/mesh_generate.py PROJECT_NAME --type zod
```

### Spec Management
```bash
# List all specs
python .claude/skills/the-mesh/scripts/mesh_spec.py list

# Read spec
python .claude/skills/the-mesh/scripts/mesh_spec.py read PROJECT_NAME

# Read specific section
python .claude/skills/the-mesh/scripts/mesh_spec.py read PROJECT_NAME --section state.Order

# Update section (from stdin or file)
echo '{"description": "..."}' | python .claude/skills/the-mesh/scripts/mesh_spec.py update PROJECT_NAME --section state.Order
```

### Task Management
```bash
# Activate task for a function
python .claude/skills/the-mesh/scripts/mesh_task.py activate PROJECT_NAME create_order

# Check current task status
python .claude/skills/the-mesh/scripts/mesh_task.py status

# Complete task (creates PR)
python .claude/skills/the-mesh/scripts/mesh_task.py complete
```

---

## Core Workflow

### 1. Spec First
Before implementing, ensure the TRIR spec exists and is complete.

### 2. Define Entity
```json
{
  "entities": {
    "Order": {
      "description": "Customer order",
      "fields": {
        "id": {"type": "string", "required": true},
        "amount": {"type": "float", "required": true},
        "status": {"type": {"enum": ["OPEN", "PAID", "SHIPPED"]}}
      }
    }
  }
}
```

### 3. Define Command
```json
{
  "commands": {
    "create_order": {
      "description": "Create a new order",
      "input": {
        "amount": {"type": "float", "required": true},
        "customer_id": {"type": "string", "required": true}
      },
      "pre": [{"expr": {"type": "binary", "op": "gt", "left": {"type": "input", "field": "amount"}, "right": {"type": "literal", "value": 0}}, "error": "Amount must be positive"}],
      "post": [{"action": {"create": {"target": "Order", "data": {"amount": {"type": "input", "field": "amount"}}}}}],
      "errors": [{"code": "INVALID_AMOUNT", "status": 400, "message": "Amount must be positive"}]
    }
  }
}
```

### 4. Validate & Generate Tests
```bash
python .claude/skills/the-mesh/scripts/mesh_validate.py PROJECT_NAME
python .claude/skills/the-mesh/scripts/mesh_generate.py PROJECT_NAME --type task-package --function create_order
```

### 5. Implement to Pass Tests
Tests use **Repository pattern** with mocks. Implementation should accept a repository parameter:

```python
def create_order(data: dict, repository: OrderRepository) -> dict:
    # Validate
    if data["amount"] <= 0:
        return {"success": False, "error": {"code": "INVALID_AMOUNT"}}

    # Create
    order = repository.create({
        "amount": data["amount"],
        "customer_id": data["customer_id"],
        "status": "OPEN"
    })

    return {"success": True, "order": order}
```

---

## Test Types

### Core Tests (4 types)
| Type | Python | TypeScript | Purpose |
|------|--------|------------|---------|
| **UT** | `pytest-ut` | `jest-ut` | Unit tests with constraint-based edge cases |
| **AT** | `pytest-at` | `jest-at` | Acceptance tests (Given/When/Then scenarios) |
| **PC** | `pytest-pc` | `jest-pc` | PostCondition tests (verify data is saved) |
| **ST** | `pytest-st` | `jest-st` | State transition tests |

### Specialized Tests (6 types)
| Type | Python | TypeScript | Purpose |
|------|--------|------------|---------|
| **Idempotency** | `pytest-idem` | `jest-idem` | Same request produces same result |
| **Concurrency** | `pytest-conc` | `jest-conc` | Parallel execution safety |
| **Authorization** | `pytest-authz` | `jest-authz` | Role-based access control |
| **Empty/Null** | `pytest-empty` | `jest-empty` | Null/empty boundary handling |
| **Reference** | `pytest-ref` | `jest-ref` | FK integrity, orphan detection |
| **Temporal** | `pytest-time` | `jest-time` | Time-based logic, deadlines |

All tests are **executable** using mock repositories with Repository pattern.

---

## Constraint Inference

Field constraints are automatically inferred from field names:

| Field Name Pattern | Preset | Constraints |
|-------------------|--------|-------------|
| `*amount*`, `*price*`, `*cost*` | money | min: 0, precision: 2 |
| `*email*` | email | format: email, maxLength: 254 |
| `*_id`, `id` | id | pattern: `^[A-Z0-9_-]+$` |
| `*percent*`, `*rate*` | percentage | min: 0, max: 100 |
| `*age*` | age | min: 0, max: 150 |
| `*count*`, `*quantity*` | count | min: 0 |

**CNS-006 Warning**: When constraints are inferred, validator shows a warning. Add explicit `preset` to confirm or disable:

```json
{
  "amount": {"type": "float", "preset": "money"},      // Confirm inference
  "score": {"type": "int", "preset": "none"}           // Disable inference
}
```

---

## Quick Reference

### Test Frameworks (20 total)

| Framework | Description |
|-----------|-------------|
| `pytest-ut` / `jest-ut` | Unit tests (edge cases) |
| `pytest-at` / `jest-at` | Acceptance tests (scenarios) |
| `pytest-pc` / `jest-pc` | PostCondition tests |
| `pytest-st` / `jest-st` | State transition tests |
| `pytest-idem` / `jest-idem` | Idempotency tests |
| `pytest-conc` / `jest-conc` | Concurrency tests |
| `pytest-authz` / `jest-authz` | Authorization tests |
| `pytest-empty` / `jest-empty` | Empty/Null tests |
| `pytest-ref` / `jest-ref` | Reference integrity tests |
| `pytest-time` / `jest-time` | Temporal tests |

### Common Commands

| Task | Command |
|------|---------|
| Validate | `mesh_validate.py PROJECT_NAME` |
| Generate Tests | `mesh_generate.py PROJECT_NAME --type tests --framework <framework>` |
| Generate Task Package | `mesh_generate.py PROJECT_NAME --type task-package --function <func>` |
| Generate TypeScript Types | `mesh_generate.py PROJECT_NAME --type typescript` |
| Generate OpenAPI | `mesh_generate.py PROJECT_NAME --type openapi` |
| Generate Zod | `mesh_generate.py PROJECT_NAME --type zod` |
| List specs | `mesh_spec.py list` |
| Read spec | `mesh_spec.py read PROJECT_NAME` |
| Activate task | `mesh_task.py activate PROJECT_NAME function_name` |
