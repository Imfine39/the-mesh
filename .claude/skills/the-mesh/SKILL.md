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

Use `generate_task_package` to generate all 4 test types at once:

```bash
python3 -c "
from the_mesh.core.handlers.generation import generate_task_package
from the_mesh.core.validator import MeshValidator
from the_mesh.core.storage import SpecStorage

storage = SpecStorage()
validator = MeshValidator()

# Generate complete task package with all tests
result = generate_task_package(validator, storage, {
    'spec_id': 'PROJECT_NAME',
    'function_name': 'create_item',
    'language': 'python'
})
print(result)
"
```

Or generate individual test types:

```bash
python3 -c "
from the_mesh.core.handlers.generation import generate_tests
from the_mesh.core.validator import MeshValidator
from the_mesh.core.storage import SpecStorage

storage = SpecStorage()
validator = MeshValidator()

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
pytest .mesh/tests/ -v
```

---

## Test Types (AT/UT/PC/ST)

All test types are generated for both Python (pytest) and JavaScript/TypeScript (Jest):

| Type | Directory | Purpose | Catches |
|------|-----------|---------|---------|
| **AT** | `at/` | Acceptance Tests (scenario-based) | Logic errors |
| **UT** | `ut/` | Unit Tests (boundaries, errors) | Edge cases |
| **PC** | `pc/` | PostCondition Tests | **Missing field saves!** |
| **ST** | `st/` | State Transition Tests | Invalid state changes |

### Framework Options

**Python:**
- `pytest` - AT (acceptance)
- `pytest-ut` - UT (unit)
- `pytest-postcondition` - PC (postcondition)
- `pytest-state` - ST (state transition)

**JavaScript/TypeScript:**
- `jest` / `jest-ts` - AT
- `jest-ut` / `jest-ts-ut` - UT
- `jest-postcondition` / `jest-ts-postcondition` - PC
- `jest-state` / `jest-ts-state` - ST

**Note on State Transition Tests:**
State transition tests are organized by state machine, not by function. When filtering:
- For AT/UT/PC: Use `function_name` parameter to filter by function
- For ST: Use `function_name` parameter to filter by **state_machine name**

```python
# Filter state transition tests by state machine name
generate_tests(validator, storage, {
    'spec_id': 'PROJECT_NAME',
    'framework': 'pytest-state',
    'function_name': 'OrderStateMachine'  # State machine name, not function
})
```

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
import json

storage = SpecStorage()
validator = MeshValidator()
result = generate_openapi(validator, storage, {'spec_id': 'PROJECT_NAME'})
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

### Human-Readable Export (ER Diagrams, Tables)
```bash
python3 -c "
from the_mesh.core.handlers.frontend import export_human_readable
from the_mesh.core.validator import MeshValidator
from the_mesh.core.storage import SpecStorage

storage = SpecStorage()
validator = MeshValidator()
result = export_human_readable(validator, storage, {'spec_id': 'PROJECT_NAME', 'format': 'er'})
print(result['content']['er_diagram'])
"
```

---

## Preventing Common Issues

### Issue: Frontend sends fields that backend ignores

**Solution**: PostCondition tests verify that ALL input fields defined in `post.action.with` are actually saved.

1. Add field to function's `input`
2. Add field to `post.action.with`
3. Generate postcondition tests: `generate_tests(..., framework="pytest-postcondition")`
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
| Generate all tests | `generate_task_package(..., function_name="all")` |
| Generate specific test | `generate_tests(..., framework="pytest-postcondition")` |
| Generate types | `generate_typescript_types(...)` |
| Generate OpenAPI | `generate_openapi(...)` |
| Export ER diagram | `export_human_readable(..., format="er")` |
| Export YAML | `export_yaml(...)` |
