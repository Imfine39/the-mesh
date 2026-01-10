"""Project Configuration for The Mesh

Manages .mesh/config.json settings for language, paths, and git options.
"""

import json
from pathlib import Path
from typing import Any


class ProjectConfig:
    """Manages project configuration for The Mesh"""

    DEFAULT_CONFIG = {
        "language": "python",
        "src_path": "src",
        "test_framework": "pytest",
        "naming": "snake_case",
        "git": {
            "base_branch": "main",
            "branch_prefix": "task",
            "auto_worktree": True,
            "auto_pr": True,
            "cleanup_worktree": False
        },
        "implementation": {
            # Default import pattern: {src_path}.{function}
            # Can use {function}, {Function}, {src_path}
            "python_module": "{src_path}.{function}",
            "typescript_module": "./{src_path}/{function}",
            # Per-function overrides
            "functions": {}
        }
    }

    def __init__(self, base_dir: Path | None = None):
        self.base_dir = base_dir or Path.cwd()
        self.mesh_dir = self.base_dir / ".mesh"
        self.config_file = self.mesh_dir / "config.json"

    def exists(self) -> bool:
        """Check if config file exists"""
        return self.config_file.exists()

    def load(self) -> dict:
        """Load config, returning defaults if not exists"""
        if not self.config_file.exists():
            return self.DEFAULT_CONFIG.copy()

        with open(self.config_file) as f:
            config = json.load(f)

        # Merge with defaults for missing keys
        merged = self.DEFAULT_CONFIG.copy()
        merged.update(config)
        if "git" in config:
            merged["git"] = {**self.DEFAULT_CONFIG["git"], **config["git"]}

        return merged

    def save(self, config: dict) -> None:
        """Save config to file"""
        self.mesh_dir.mkdir(parents=True, exist_ok=True)
        with open(self.config_file, 'w') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

    def init(self, language: str = "python", src_path: str | None = None,
             test_framework: str | None = None, git_config: dict | None = None) -> dict:
        """Initialize project config"""
        config = self.DEFAULT_CONFIG.copy()
        config["language"] = language

        # Set defaults based on language
        if language == "typescript":
            config["src_path"] = src_path or "src/functions"
            config["test_framework"] = test_framework or "jest"
            config["naming"] = "camelCase"
        elif language == "javascript":
            config["src_path"] = src_path or "src"
            config["test_framework"] = test_framework or "jest"
            config["naming"] = "camelCase"
        else:  # python
            config["src_path"] = src_path or "src"
            config["test_framework"] = test_framework or "pytest"
            config["naming"] = "snake_case"

        # Merge git config
        if git_config:
            config["git"] = {**config["git"], **git_config}

        self.save(config)
        return config

    def get_impl_path(self, function_name: str) -> Path:
        """Get the implementation file path for a function"""
        config = self.load()
        src_path = Path(config["src_path"])

        # Apply naming convention
        if config["naming"] == "camelCase":
            # snake_case → camelCase
            parts = function_name.split("_")
            name = parts[0] + "".join(p.capitalize() for p in parts[1:])
        else:
            name = function_name

        # Determine extension
        if config["language"] == "typescript":
            ext = "ts"
        elif config["language"] == "javascript":
            ext = "js"
        else:
            ext = "py"

        return self.base_dir / src_path / f"{name}.{ext}"

    def get_test_config_name(self) -> str:
        """Get the test config file name based on framework"""
        config = self.load()
        if config["test_framework"] in ("jest", "vitest"):
            return "jest.config.json"
        return "pytest.ini"

    def get_import_module(self, function_name: str) -> str:
        """Get the import module path for a function.

        Returns a module path like 'src.orders.create_order' (Python)
        or './src/orders/createOrder' (TypeScript).
        """
        config = self.load()
        impl_config = config.get("implementation", {})

        # Check for per-function override
        func_overrides = impl_config.get("functions", {})
        if function_name in func_overrides:
            return func_overrides[function_name].get("module", function_name)

        # Use pattern-based default
        language = config.get("language", "python")
        src_path = config.get("src_path", "src")

        if language in ("typescript", "javascript"):
            pattern = impl_config.get("typescript_module", "./{src_path}/{function}")
            # Convert to camelCase for TypeScript
            parts = function_name.split("_")
            func_camel = parts[0] + "".join(p.capitalize() for p in parts[1:])
            func_pascal = "".join(p.capitalize() for p in parts)
            return pattern.format(
                src_path=src_path,
                function=func_camel,
                Function=func_pascal
            )
        else:
            pattern = impl_config.get("python_module", "{src_path}.{function}")
            parts = function_name.split("_")
            func_pascal = "".join(p.capitalize() for p in parts)
            return pattern.format(
                src_path=src_path,
                function=function_name,
                Function=func_pascal
            )

    def set_function_module(self, function_name: str, module: str) -> None:
        """Set the import module for a specific function."""
        config = self.load()
        if "implementation" not in config:
            config["implementation"] = {"functions": {}}
        if "functions" not in config["implementation"]:
            config["implementation"]["functions"] = {}

        config["implementation"]["functions"][function_name] = {"module": module}
        self.save(config)

    def get_all_import_modules(self, function_names: list[str]) -> dict[str, str]:
        """Get import modules for multiple functions at once."""
        return {fn: self.get_import_module(fn) for fn in function_names}
