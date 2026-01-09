# Frontend Extension Implementation Plan for The Mesh

## Executive Summary

This plan extends The Mesh to provide the same specification-driven development rigor for frontend as currently exists for backend. The approach focuses on:

1. **Extending the existing schema** rather than creating parallel structures
2. **Building on proven patterns** from the backend task management system
3. **Supporting React + Playwright initially** with framework abstraction for future expansion
4. **Maintaining backward compatibility** throughout all phases

---

## Part 1: Architecture Decisions

### 1.1 Schema Design Decision: Extend vs. Add New Sections

**Decision: Extend existing `views` and `routes`, add minimal new sections**

**Rationale:**
- The current `views` and `routes` already capture 80% of what's needed
- Adding `pages`, `components`, `frontendScenarios` keeps domain separation clear
- Avoids breaking changes to existing specs

**Proposed Schema Extensions:**

```
views (existing) - enhanced with layout hints, component mapping
routes (existing) - enhanced with layout, SSR options
pages (NEW) - compositions of views with data fetching
components (NEW) - reusable UI building blocks
frontendScenarios (NEW) - E2E test scenarios
```

### 1.2 Task Granularity Decision

**Decision: Page-level tasks as primary, component-level as optional**

**Rationale:**
- Pages map naturally to routes and user flows
- Components can be generated inline with page tasks
- Prevents over-fragmentation of development work
- Aligns with how frontend testing is typically organized (by feature/page)

### 1.3 Framework Strategy Decision

**Decision: React + Next.js first, with generator abstraction layer**

**Rationale:**
- React has largest market share and ecosystem
- Next.js provides App Router patterns that map well to TRIR routes
- Playwright for E2E tests is framework-agnostic
- Abstraction layer enables future Vue/Svelte/SvelteKit support

---

## Part 2: Schema Extensions

### 2.1 New Schema Definitions

#### Page Definition

```json
{
  "Page": {
    "type": "object",
    "description": "Frontend page composition",
    "properties": {
      "_kind": { "const": "page" },
      "description": { "type": "string" },
      "route": { "type": "string", "description": "Route path this page implements" },
      "views": {
        "type": "array",
        "items": { "type": "string" },
        "description": "Views composed in this page"
      },
      "layout": {
        "type": "string",
        "description": "Layout component/template to use"
      },
      "dataFetching": {
        "type": "object",
        "properties": {
          "queries": {
            "type": "array",
            "items": { "type": "string" },
            "description": "Functions to call for data loading"
          },
          "mutations": {
            "type": "array",
            "items": { "type": "string" },
            "description": "Functions available for mutations"
          },
          "prefetch": { "type": "boolean", "default": false },
          "ssr": { "type": "boolean", "default": true }
        }
      },
      "components": {
        "type": "array",
        "items": { "type": "string" },
        "description": "Additional components used in this page"
      }
    },
    "required": ["route", "views"],
    "additionalProperties": false
  }
}
```

#### Component Definition

```json
{
  "Component": {
    "type": "object",
    "description": "Reusable UI component definition",
    "properties": {
      "_kind": { "const": "component" },
      "description": { "type": "string" },
      "type": {
        "type": "string",
        "enum": ["display", "input", "form", "container", "layout"],
        "description": "Component category"
      },
      "entity": {
        "type": "string",
        "description": "Primary entity this component displays/edits"
      },
      "fields": {
        "type": "array",
        "items": { "type": "string" },
        "description": "Entity fields this component uses"
      },
      "props": {
        "type": "object",
        "additionalProperties": { "$ref": "#/$defs/Field" },
        "description": "Additional props beyond entity fields"
      },
      "variants": {
        "type": "object",
        "additionalProperties": {
          "type": "object",
          "description": "Variant-specific styling/behavior"
        }
      },
      "actions": {
        "type": "array",
        "items": { "type": "string" },
        "description": "Functions this component can trigger"
      }
    },
    "additionalProperties": false
  }
}
```

#### FrontendScenario Definition

```json
{
  "FrontendScenario": {
    "type": "object",
    "description": "E2E test scenario",
    "properties": {
      "_kind": { "const": "frontend_scenario" },
      "title": { "type": "string" },
      "description": { "type": "string" },
      "page": { "type": "string", "description": "Starting page" },
      "verifies": {
        "type": "array",
        "items": { "type": "string" },
        "description": "Requirement IDs verified by this scenario"
      },
      "given": {
        "type": "object",
        "description": "Initial state/fixtures",
        "properties": {
          "user": {
            "type": "object",
            "properties": {
              "role": { "type": "string" },
              "authenticated": { "type": "boolean", "default": true }
            }
          },
          "fixtures": { "$ref": "#/$defs/ScenarioData" }
        }
      },
      "steps": {
        "type": "array",
        "items": { "$ref": "#/$defs/FrontendStep" }
      }
    },
    "required": ["title", "page", "steps"],
    "additionalProperties": false
  },

  "FrontendStep": {
    "type": "object",
    "properties": {
      "action": {
        "type": "string",
        "enum": ["navigate", "click", "fill", "select", "hover", "wait", "submit", "assert", "screenshot"]
      },
      "target": { "type": "string", "description": "CSS selector, data-testid, or semantic target" },
      "value": { "description": "Value for fill/select actions" },
      "assertion": {
        "type": "object",
        "properties": {
          "type": { "type": "string", "enum": ["visible", "hidden", "text", "value", "count", "url", "toast"] },
          "expected": { }
        }
      },
      "timeout": { "type": "number", "description": "Step timeout in ms" }
    },
    "required": ["action"],
    "additionalProperties": false
  }
}
```

---

## Part 3: Dependency Graph Extension

### 3.1 New Node Types

```python
class NodeType(Enum):
    # Existing types...

    # Frontend types (Phase 3)
    VIEW = "view"
    ROUTE = "route"
    PAGE = "page"
    COMPONENT = "component"
    FRONTEND_SCENARIO = "frontend_scenario"
```

### 3.2 Frontend Dependency Edges

```
page -> route (implements)
page -> view (composes)
page -> component (uses)
page -> function (fetches/mutates)
view -> entity (displays)
view -> function (action)
view -> component (uses - via slots)
component -> entity (binds)
component -> function (triggers)
frontend_scenario -> page (tests)
frontend_scenario -> function (exercises)
```

### 3.3 Impact Analysis Extension

```python
@dataclass
class ImpactAnalysis:
    # Existing fields...

    # Frontend impact
    affected_views: list[str] = field(default_factory=list)
    affected_pages: list[str] = field(default_factory=list)
    affected_components: list[str] = field(default_factory=list)
    affected_frontend_scenarios: list[str] = field(default_factory=list)
```

---

## Part 4: Generator Strategy

### 4.1 New Generators

| Generator | Output | File |
|-----------|--------|------|
| `PageGenerator` | Page component skeletons | `generators/page_gen.py` |
| `ComponentGenerator` | Component skeletons | `generators/component_gen.py` |
| `ApiHooksGenerator` | React Query/SWR hooks | `generators/api_hooks_gen.py` |
| `FormGenerator` | Form components from function inputs | `generators/form_gen.py` |
| `PlaywrightGenerator` | E2E test files | `generators/playwright_gen.py` |
| `ComponentTestGenerator` | Unit tests for components | `generators/component_test_gen.py` |

### 4.2 Key Generator Interfaces

```python
class PageGenerator:
    def __init__(self, spec: dict, framework: str = "react"): ...
    def generate_for_page(self, page_name: str) -> dict[str, str]: ...
    def generate_page_component(self, page_name: str) -> str: ...
    def generate_data_hooks(self, page_name: str) -> str: ...

class ApiHooksGenerator:
    def __init__(self, spec: dict, library: str = "tanstack-query"): ...
    def generate_all(self) -> str: ...
    def generate_query_hook(self, func_name: str) -> str: ...
    def generate_mutation_hook(self, func_name: str) -> str: ...

class PlaywrightGenerator:
    def __init__(self, spec: dict): ...
    def generate_all(self) -> dict[str, str]: ...
    def generate_for_page(self, page_name: str) -> str: ...
    def step_to_playwright(self, step: dict) -> str: ...
```

---

## Part 5: Task Management Extension

### 5.1 Frontend Task Package Structure

```
tasks/frontend/{page_name}/
├── TASK.md                    # Implementation requirements
├── context.json               # Views, entities, functions needed
├── playwright.config.ts       # Test config for this page
└── components/                # Component stubs
    └── {ComponentName}.stub

.mesh/frontend/
├── tests/
│   ├── e2e/
│   │   └── {page_name}.spec.ts  # Playwright tests
│   └── unit/
│       └── {page_name}.test.tsx # Component tests
└── generated/
    ├── hooks/                   # API hooks
    ├── forms/                   # Form components
    └── types/                   # TypeScript types

src/                            # User-editable implementation
├── pages/
│   └── {page_name}/
│       ├── index.tsx           # Page component
│       └── components/         # Page-specific components
└── components/                 # Shared components
```

### 5.2 Edit Permission Rules

```python
FRONTEND_PERMISSION_RULES = {
    # Auto-generated (read-only)
    ".mesh/frontend/tests/**": False,
    ".mesh/frontend/generated/**": False,
    "tasks/frontend/**": False,

    # Editable when task active
    "src/pages/{page_name}/**": "requires_active_task",
    "src/components/**": "requires_active_task",

    # Always editable
    "src/styles/**": True,
    "src/lib/**": True,
}
```

### 5.3 FrontendTaskManager Interface

```python
class FrontendTaskManager:
    def activate_page_task(self, page_name: str, framework: str = "react") -> dict: ...
    def activate_component_task(self, component_name: str) -> dict: ...
    def complete_page_task(self, page_name: str, test_results: dict) -> dict: ...
    def check_frontend_edit_permission(self, file_path: str) -> dict: ...
    def get_e2e_test_command(self, page_name: str) -> dict: ...
```

---

## Part 6: Validation Extension

### 6.1 New Error Codes

| Code | Description |
|------|-------------|
| FE-006 | Page references unknown route |
| FE-007 | Page references unknown view |
| FE-008 | Page dataFetching references unknown function |
| FE-009 | Component references unknown entity |
| FE-010 | Component action references unknown function |
| FE-011 | FrontendScenario references unknown page |
| FE-012 | FrontendScenario step target invalid |
| FE-013 | Component variant references unknown field |
| FE-014 | Page layout references unknown component |

---

## Part 7: MCP Handler Extensions

### 7.1 New Tools

```python
FRONTEND_HANDLERS = {
    # Generation
    "generate_frontend_task_package": ...,
    "generate_page_skeleton": ...,
    "generate_component_skeleton": ...,
    "generate_api_hooks": ...,
    "generate_form_component": ...,
    "generate_e2e_tests": ...,

    # Task management
    "activate_frontend_task": ...,
    "complete_frontend_task": ...,
    "get_frontend_task_status": ...,
    "check_frontend_edit_permission": ...,
    "get_e2e_test_command": ...,

    # Context
    "get_page_context": ...,
    "get_frontend_dependencies": ...,
    "analyze_frontend_impact": ...,
}
```

---

## Part 8: Implementation Phases

### Phase 1: Schema Foundation (Week 1-2)
**Priority: Critical**

1. Add `pages`, `components`, `frontendScenarios` to `mesh.schema.json`
2. Add validation methods (FE-006 through FE-014)
3. Write tests for new schema validations

**Files:**
- `src/the_mesh/schemas/mesh.schema.json`
- `src/the_mesh/core/validator.py`
- `tests/test_frontend_validation.py`

### Phase 2: Dependency Graph Extension (Week 2-3)
**Priority: High**

1. Add frontend NodeTypes to graph.py
2. Implement frontend dependency edge building
3. Extend ImpactAnalysis with frontend fields
4. Add `get_frontend_slice()` methods

**Files:**
- `src/the_mesh/graph/graph.py`
- `tests/test_graph.py`

### Phase 3: Core Generators (Week 3-5)
**Priority: High**

1. Create `PageGenerator` for React
2. Create `ApiHooksGenerator` for TanStack Query
3. Create `FormGenerator` for Shadcn UI
4. Create `PlaywrightGenerator` for E2E tests

**Files:**
- `src/the_mesh/generators/page_gen.py`
- `src/the_mesh/generators/api_hooks_gen.py`
- `src/the_mesh/generators/form_gen.py`
- `src/the_mesh/generators/playwright_gen.py`

### Phase 4: Frontend Task Management (Week 5-6)
**Priority: High**

1. Create `FrontendTaskManager`
2. Implement `FrontendTaskPackageGenerator`
3. Add edit permission rules
4. Integrate with git worktree workflow

**Files:**
- `src/the_mesh/mcp/frontend_task_manager.py`
- `src/the_mesh/generators/frontend_task_package_gen.py`

### Phase 5: MCP Integration (Week 6-7)
**Priority: Medium**

1. Create extended frontend handlers
2. Add tools to MCP server
3. Update handler registry

**Files:**
- `src/the_mesh/mcp/handlers/frontend_extended.py`
- `src/the_mesh/mcp/server.py`

### Phase 6: Component Generator Enhancement (Week 7-8)
**Priority: Medium**

1. Create `ComponentGenerator`
2. Create `ComponentTestGenerator`
3. Add component-level task support

### Phase 7: Framework Abstraction (Week 8-9)
**Priority: Low**

1. Create framework adapter interface
2. Implement Vue adapter
3. Implement Svelte adapter

---

## Part 9: Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Schema Complexity | Keep pages/components minimal initially; validate against real examples |
| Generator Maintenance | Start with React only; use adapter pattern from the start |
| E2E Test Flakiness | Use data-testid selectors; include explicit waits |
| Task Scope Creep | Support component-level subtasks; allow partial completion |
| Backward Compatibility | All new sections optional; existing views/routes remain valid |

---

## Part 10: Configuration Extension

```python
DEFAULT_CONFIG = {
    # Existing...

    "frontend": {
        "framework": "react",              # react, vue, svelte
        "ui_library": "shadcn",            # shadcn, chakra, mantine, mui
        "state_library": "tanstack-query", # tanstack-query, swr, rtk-query
        "e2e_framework": "playwright",     # playwright, cypress
        "pages_path": "src/pages",
        "components_path": "src/components",
        "hooks_path": "src/hooks"
    }
}
```

---

## Critical Files Summary

| File | Purpose |
|------|---------|
| `src/the_mesh/schemas/mesh.schema.json` | Schema extensions |
| `src/the_mesh/core/validator.py` | Frontend validation (FE-006~014) |
| `src/the_mesh/graph/graph.py` | Frontend dependency tracking |
| `src/the_mesh/generators/page_gen.py` | Page skeleton generation |
| `src/the_mesh/generators/playwright_gen.py` | E2E test generation |
| `src/the_mesh/mcp/frontend_task_manager.py` | Task management |
| `src/the_mesh/mcp/handlers/frontend_extended.py` | MCP tools |
