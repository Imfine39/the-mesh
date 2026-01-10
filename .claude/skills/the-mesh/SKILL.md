---
name: the-mesh
description: "Specification-driven development framework using TRIR (Typed Relational IR). Actions: spec, implement, test, validate, generate. Use for: API development, backend functions, database entities, test generation, type generation. Triggers: implement function, add entity, add field, create test, generate types, validate spec, TDD, spec-driven."
---

# The Mesh - Specification-Driven Development

TRIR (Typed Relational IR) specification framework for test-driven, spec-first development.

## Core Workflow

When implementing features, follow this spec-driven workflow:

### 1. Spec First - Define Before Implement

Before writing any implementation code, ensure the TRIR spec exists and is complete.

**Check if spec exists:**
```bash
ls .mesh/*.mesh.json 2>/dev/null || echo "No spec found"
```

**If no spec exists, create one:**
```bash
python3 -c "
from the_mesh.core.storage import SpecStorage
storage = SpecStorage()
storage.write_spec({
    'meta': {'id': 'PROJECT_NAME', 'title': 'Project Title', 'version': '0.1.0'},
    'state': {},
    'functions': {},
    'scenarios': {}
}, 'PROJECT_NAME')
"
```

### 2. Define Entity (if needed)

Add entity to spec before implementing:

```python
# Use spec_update_section to add entity
spec_update_section(
    spec_id="PROJECT_NAME",
    section="state",
    key="EntityName",
    data={
        "description": "Entity description",
        "fields": {
            "id": {"type": "int", "required": True},
            "name": {"type": "string", "required": True},
            "status": {"type": {"enum": ["active", "inactive"]}}
        }
    }
)
```

### 3. Define Function with Full Contract

**CRITICAL**: Define ALL fields that the function should handle:

```python
spec_update_section(
    spec_id="PROJECT_NAME",
    section="functions",
    key="create_item",
    data={
        "description": "Create a new item",
        "input": {
            "name": {"type": "string", "required": True},
            "price": {"type": "float", "required": True},
            "discount": {"type": "float", "required": False}
        },
        "pre": [
            {"check": {"type": "binary", "op": "gt", "left": {"type": "input", "name": "price"}, "right": {"type": "literal", "value": 0}}}
        ],
        "post": [
            {
                "action": {
                    "create": "Item",
                    "with": {
                        "name": {"type": "input", "name": "name"},
                        "price": {"type": "input", "name": "price"},
                        "discount": {"type": "input", "name": "discount"}
                    }
                }
            }
        ],
        "error_cases": [
            {"code": "INVALID_PRICE", "when": {"type": "binary", "op": "le", "left": {"type": "input", "name": "price"}, "right": {"type": "literal", "value": 0}}}
        ]
    }
)
```

### 4. Validate Spec

Always validate after changes:

```bash
python3 -c "
from the_mesh.core.validator import MeshValidator
from the_mesh.core.storage import SpecStorage
import json

storage = SpecStorage()
spec = storage.read_spec('PROJECT_NAME')
validator = MeshValidator()
result = validator.validate(spec)
print(f'Valid: {result.valid}')
for err in result.errors[:5]:
    print(f'  {err.code}: {err.message}')
"
```

### 5. Generate Tests BEFORE Implementation

**This is the key to catching frontend/backend mismatches!**

```bash
# Generate all test types
python3 -c "
from the_mesh.core.handlers.generation import generate_tests
from the_mesh.core.validator import MeshValidator
from the_mesh.core.storage import SpecStorage

storage = SpecStorage()
validator = MeshValidator()

# Acceptance tests (scenario-based)
result = generate_tests(validator, storage, {'spec_id': 'PROJECT_NAME', 'framework': 'pytest'})
print(result['code'])

# PostCondition tests (verify create/update/delete actually save data!)
result = generate_tests(validator, storage, {'spec_id': 'PROJECT_NAME', 'framework': 'pytest-postcondition'})
print(result['code'])
"
```

### 6. Implement to Pass Tests

Now implement the backend code. The tests will fail if:
- Input fields are not properly received
- Post-actions don't actually save data
- Error cases aren't handled

### 7. Run Tests

```bash
pytest tests/test_postcondition_*.py -v
```

---

## Available Test Frameworks

| Framework | Purpose | Catches |
|-----------|---------|---------|
| `pytest` | Scenario acceptance tests | Logic errors |
| `pytest-ut` | Unit tests (boundaries, errors) | Edge cases |
| `pytest-postcondition` | **Post-action verification** | **Missing field saves!** |
| `pytest-state` | State machine transitions | Invalid transitions |
| `jest`, `jest-ts` | JS/TS acceptance tests | Frontend logic |
| `jest-postcondition`, `jest-ts-postcondition` | JS post-action tests | Frontend saves |

---

## Impact Analysis

When modifying existing spec, check impact:

```bash
python3 -c "
from the_mesh.graph.graph import DependencyGraph
from the_mesh.core.storage import SpecStorage
import json

storage = SpecStorage()
spec = storage.read_spec('PROJECT_NAME')

graph = DependencyGraph()
graph.build_from_spec(spec)

# Check what depends on an entity
deps = graph.get_dependents('EntityName')
print(json.dumps(deps, indent=2))
"
```

---

## Code Generation

### TypeScript Types
```bash
python3 -c "
from the_mesh.core.handlers.frontend import generate_typescript_types
from the_mesh.core.validator import MeshValidator
from the_mesh.core.storage import SpecStorage

storage = SpecStorage()
validator = MeshValidator()
result = generate_typescript_types(validator, storage, {'spec_id': 'PROJECT_NAME'})
print(result['code'])
"
```

### OpenAPI Schema
```bash
python3 -c "
from the_mesh.core.handlers.frontend import generate_openapi
from the_mesh.core.validator import MeshValidator
from the_mesh.core.storage import SpecStorage

storage = SpecStorage()
validator = MeshValidator()
result = generate_openapi(validator, storage, {'spec_id': 'PROJECT_NAME'})
import json
print(json.dumps(result['schema'], indent=2))
"
```

### Zod Schemas
```bash
python3 -c "
from the_mesh.core.handlers.frontend import generate_zod_schemas
from the_mesh.core.validator import MeshValidator
from the_mesh.core.storage import SpecStorage

storage = SpecStorage()
validator = MeshValidator()
result = generate_zod_schemas(validator, storage, {'spec_id': 'PROJECT_NAME'})
print(result['code'])
"
```

---

## Preventing Common Issues

### Issue: Frontend sends fields that backend ignores

**Solution**: PostCondition tests verify that ALL input fields defined in `post.action.with` are actually saved.

1. Add field to function's `input`
2. Add field to `post.action.with`
3. Generate postcondition tests
4. Tests will fail until backend properly handles the field

### Issue: API schema drift

**Solution**: Generate OpenAPI from spec, use it as contract.

```bash
# Generate and compare
python3 -c "..." > openapi.json
diff openapi.json backend/openapi.json
```

### Issue: Type mismatches between frontend/backend

**Solution**: Generate TypeScript types and Zod from same spec.

---

## Quick Reference

| Task | Handler |
|------|---------|
| Add entity | `spec_update_section(section="state", key="Name", data={...})` |
| Add function | `spec_update_section(section="functions", key="name", data={...})` |
| Add scenario | `spec_update_section(section="scenarios", key="AT-001", data={...})` |
| Validate | `validator.validate(spec)` |
| Generate tests | `generate_tests(..., framework="pytest-postcondition")` |
| Generate types | `generate_typescript_types(...)` |
| Generate OpenAPI | `generate_openapi(...)` |
| Export readable | `export_human_readable(..., format="er")` |
