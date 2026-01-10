---
name: the-mesh
description: "Specification-driven development framework using TRIR (Typed Relational IR). Actions: spec, implement, test, validate, generate. Use for: API development, backend functions, database entities, test generation, type generation. Triggers: implement function, add entity, add field, create test, generate types, validate spec, TDD, spec-driven."
---

# The Mesh - Specification-Driven Development

TRIR (Typed Relational IR) specification framework for test-driven, spec-first development.

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
  "state": {
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

### 3. Define Function
```json
{
  "functions": {
    "create_order": {
      "description": "Create a new order",
      "input": {
        "amount": {"type": "float", "required": true},
        "customer_id": {"type": "string", "required": true}
      },
      "pre": [{"check": {"type": "binary", "op": "gt", "left": {"type": "input", "name": "amount"}, "right": {"type": "literal", "value": 0}}}],
      "post": [{"action": {"create": "Order", "with": {"amount": {"type": "input", "name": "amount"}}}}],
      "error": [{"code": "INVALID_AMOUNT", "reason": "Amount must be positive"}]
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

| Type | Python | TypeScript | Purpose |
|------|--------|------------|---------|
| **UT** | `pytest-ut` | `jest-ut` | Unit tests with constraint-based edge cases |
| **AT** | `pytest-at` | `jest-at` | Acceptance tests (Given/When/Then scenarios) |
| **PC** | `pytest-pc` | `jest-pc` | PostCondition tests (verify data is saved) |
| **ST** | `pytest-st` | `jest-st` | State transition tests |

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

| Task | Command |
|------|---------|
| Validate | `mesh_validate.py PROJECT_NAME` |
| Generate UT (Python) | `mesh_generate.py PROJECT_NAME --type tests --framework pytest-ut` |
| Generate AT (Python) | `mesh_generate.py PROJECT_NAME --type tests --framework pytest-at` |
| Generate PC (Python) | `mesh_generate.py PROJECT_NAME --type tests --framework pytest-pc` |
| Generate ST (Python) | `mesh_generate.py PROJECT_NAME --type tests --framework pytest-st` |
| Generate UT (TypeScript) | `mesh_generate.py PROJECT_NAME --type tests --framework jest-ut` |
| Generate AT (TypeScript) | `mesh_generate.py PROJECT_NAME --type tests --framework jest-at` |
| Generate PC (TypeScript) | `mesh_generate.py PROJECT_NAME --type tests --framework jest-pc` |
| Generate ST (TypeScript) | `mesh_generate.py PROJECT_NAME --type tests --framework jest-st` |
| Generate TypeScript Types | `mesh_generate.py PROJECT_NAME --type typescript` |
| Generate OpenAPI | `mesh_generate.py PROJECT_NAME --type openapi` |
| Generate Zod | `mesh_generate.py PROJECT_NAME --type zod` |
| List specs | `mesh_spec.py list` |
| Read spec | `mesh_spec.py read PROJECT_NAME` |
| Activate task | `mesh_task.py activate PROJECT_NAME function_name` |
