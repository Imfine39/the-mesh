# The Mesh

Specification validation MCP server for AI-driven development.

## Overview

The Mesh provides a structured approach to specification-driven development with Claude Code. It validates `.mesh.json` specification files and generates test code, documentation, and more.

## Features

- **Specification Validation**: Validate entities, functions, state machines, and more
- **Expression Engine**: Type-safe expression validation with reference resolution
- **Dependency Graph**: Analyze impact of changes across specifications
- **Code Generation**: Generate pytest/Jest tests from specifications
- **MCP Integration**: Works seamlessly with Claude Code

## Installation

```bash
# Clone the repository
git clone https://github.com/the-mesh/the-mesh.git
cd the-mesh

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install in development mode
pip install -e ".[dev]"
```

## Usage

### As MCP Server

Add to your `.mcp.json`:

```json
{
  "mcpServers": {
    "the_mesh": {
      "command": "the_mesh"
    }
  }
}
```

### Available Tools

- `validate_spec` - Validate a complete specification
- `validate_expression` - Validate a single expression
- `analyze_impact` - Analyze impact of changes
- `generate_tests` - Generate test code
- `spec_read` / `spec_write` - CRUD operations for specs
- And more...

## Project Structure

```
the-mesh/
├── src/the_mesh/           # Main package
│   ├── core/               # Validator, engine
│   ├── graph/              # Dependency graph
│   ├── generators/         # Code generators
│   ├── mcp/                # MCP server
│   ├── config/             # Configuration
│   ├── hooks/              # Claude Code hooks
│   └── schemas/            # JSON schemas
├── tests/                  # Test suite
├── examples/               # Example specifications
└── docs/                   # Documentation
```

## Specification Format

Specifications use the `.mesh.json` format:

```json
{
  "$schema": "https://the-mesh.dev/schemas/mesh.schema.json",
  "meta": {
    "name": "my-spec",
    "version": "1.0.0"
  },
  "state": {
    "entities": {
      "User": {
        "fields": {
          "id": {"type": "string"},
          "name": {"type": "string"}
        }
      }
    }
  },
  "functions": {}
}
```

See `examples/` for more complete examples.

## Development

```bash
# Run tests
pytest tests/ -v

# Run a specific test file
pytest tests/test_validator.py -v
```

## License

MIT
