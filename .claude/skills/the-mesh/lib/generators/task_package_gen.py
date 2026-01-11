"""TRIR Task Package Generator

Generates implementation task packages with:
- Test files in .mesh/tests/ (no duplication)
- Task folders in tasks/{function}/ with references to tests
- TASK.md with requirements
- Implementation skeleton
- pytest.ini / jest.config.json for running related tests
"""

import json
import os
from pathlib import Path
from typing import Any
from dataclasses import dataclass

from generators.python.pytest_gen import PytestGenerator
from generators.python.pytest_unit_gen import PytestUnitGenerator
from generators.python.postcondition_gen import PostConditionGenerator
from generators.python.state_transition_gen import StateTransitionGenerator
from generators.typescript.jest_gen import JestGenerator
from generators.typescript.jest_unit_gen import JestUnitGenerator
from generators.typescript.jest_postcondition_gen import JestPostConditionGenerator
from generators.typescript.jest_state_transition_gen import JestStateTransitionGenerator
from graph.graph import DependencyGraph
from config.project import ProjectConfig


@dataclass
class TaskPackageResult:
    """Result of task package generation"""
    success: bool
    task_dir: str
    tests_dir: str
    impl_path: str  # Path to implementation file in src/
    files_created: list[str]
    related_functions: list[str]
    error: str | None = None


class TaskPackageGenerator:
    """Generates complete task packages for implementation"""

    def __init__(self, spec: dict[str, Any], base_dir: str = "."):
        self.spec = spec
        self.base_dir = Path(base_dir)
        self.mesh_dir = self.base_dir / ".mesh"
        self.tests_dir = self.mesh_dir / "tests"
        self.tasks_dir = self.base_dir / "tasks"

        # Load project config
        self.project_config = ProjectConfig(self.base_dir)
        self.config = self.project_config.load()

        # Build dependency graph for impact analysis
        self.graph = DependencyGraph()
        self.graph.build_from_spec(spec)

        self.entities = spec.get("entities", {})
        self.functions = spec.get("commands", {})
        self.scenarios = spec.get("scenarios", {})
        self.derived = spec.get("derived", {})
        self.invariants = spec.get("invariants", [])

    def generate_all_tests(self, language: str = "python") -> dict[str, str]:
        """Generate all test files to .mesh/tests/"""
        files = {}

        # Get import modules from config for all functions
        function_names = list(self.functions.keys())
        import_modules = self.project_config.get_all_import_modules(function_names)

        if language == "python":
            # AT tests (Acceptance Tests - scenario-based)
            at_gen = PytestGenerator(self.spec, import_modules=import_modules)
            for func_name in self.functions:
                code = at_gen.generate_for_function(func_name)
                files[f"at/test_{func_name}_at.py"] = code

            # UT tests (Unit Tests - boundaries, error cases)
            ut_gen = PytestUnitGenerator(self.spec)
            files["ut/test_unit.py"] = ut_gen.generate_all()

            # PC tests (PostCondition - verify create/update/delete)
            pc_gen = PostConditionGenerator(self.spec, import_modules=import_modules)
            files["pc/test_postcondition.py"] = pc_gen.generate_all()

            # ST tests (State Transition - state machine behavior)
            if self.spec.get("stateMachines"):
                st_gen = StateTransitionGenerator(self.spec, import_modules=import_modules)
                files["st/test_state_transition.py"] = st_gen.generate_all()

        elif language in ("javascript", "typescript"):
            is_ts = language == "typescript"
            ext = "ts" if is_ts else "js"

            # AT tests (Acceptance Tests)
            at_gen = JestGenerator(self.spec, typescript=is_ts, import_modules=import_modules)
            for func_name in self.functions:
                code = at_gen.generate_for_function(func_name)
                files[f"at/{func_name}.at.test.{ext}"] = code

            # UT tests (Unit Tests)
            ut_gen = JestUnitGenerator(self.spec, typescript=is_ts)
            files[f"ut/unit.test.{ext}"] = ut_gen.generate_all()

            # PC tests (PostCondition)
            pc_gen = JestPostConditionGenerator(self.spec, typescript=is_ts, import_modules=import_modules)
            files[f"pc/postcondition.test.{ext}"] = pc_gen.generate_all()

            # ST tests (State Transition)
            if self.spec.get("stateMachines"):
                st_gen = JestStateTransitionGenerator(self.spec, typescript=is_ts, import_modules=import_modules)
                files[f"st/state_transition.test.{ext}"] = st_gen.generate_all()

        return files

    def get_related_functions(self, function_name: str) -> list[str]:
        """Get functions that might be affected by changes to this function"""
        related = set()

        func_def = self.functions.get(function_name, {})

        # Get entities modified by this function
        modified_entities = set()
        for post in func_def.get("post", []):
            action = post.get("action", {})
            for action_type in ["create", "update", "delete"]:
                if action_type in action:
                    target = self._get_action_target(action[action_type])
                    if target:
                        modified_entities.add(target)

        # Find other functions that read these entities
        for other_func, other_def in self.functions.items():
            if other_func == function_name:
                continue

            # Check preconditions for entity references
            for pre in other_def.get("pre", []):
                refs = self._extract_entity_refs(pre.get("check", {}))
                if refs & modified_entities:
                    related.add(other_func)

            # Check post-actions
            for post in other_def.get("post", []):
                action = post.get("action", {})
                for action_type in ["create", "update", "delete"]:
                    target = self._get_action_target(action.get(action_type))
                    if target in modified_entities:
                        related.add(other_func)

        return sorted(related)

    def _get_action_target(self, action_value) -> str | None:
        """Extract target entity name from action value.

        Supports both formats:
        - Legacy: "Invoice" (string directly)
        - New: {"target": "Invoice", "data": {...}} (dict with target)
        """
        if action_value is None:
            return None
        if isinstance(action_value, str):
            return action_value
        if isinstance(action_value, dict):
            return action_value.get("target")
        return None

    def _extract_entity_refs(self, expr: dict) -> set[str]:
        """Extract entity references from expression"""
        refs = set()
        if not isinstance(expr, dict):
            return refs

        expr_type = expr.get("type")

        if expr_type == "ref":
            path = expr.get("path", "")
            if "." in path:
                refs.add(path.split(".")[0])

        # Recurse into sub-expressions
        for key in ["left", "right", "expr", "cond", "then", "else"]:
            if key in expr:
                refs |= self._extract_entity_refs(expr[key])

        for branch in expr.get("branches", []):
            refs |= self._extract_entity_refs(branch.get("when", {}))
            refs |= self._extract_entity_refs(branch.get("then", {}))

        return refs

    def generate_task_md(self, function_name: str, related_functions: list[str]) -> str:
        """Generate TASK.md content"""
        func_def = self.functions.get(function_name, {})

        lines = [
            f"# Task: {function_name}",
            "",
            f"## 概要",
            f"{func_def.get('description', 'No description')}",
            "",
            "## 入力パラメータ",
            "",
        ]

        # Input parameters
        for param_name, param_def in func_def.get("input", {}).items():
            param_type = param_def.get("type", "any")
            required = "必須" if param_def.get("required", True) else "任意"
            lines.append(f"- `{param_name}`: {param_type} ({required})")

        lines.extend(["", "## 前提条件 (Preconditions)", ""])

        # Preconditions
        for i, pre in enumerate(func_def.get("pre", []), 1):
            check = pre.get("check", {})
            lines.append(f"{i}. {self._expr_to_human(check)}")

        if not func_def.get("pre"):
            lines.append("- なし")

        lines.extend(["", "## 事後処理 (Post-actions)", ""])

        # Post-actions
        for post in func_def.get("post", []):
            action = post.get("action", {})
            for action_type, entity in action.items():
                lines.append(f"- {action_type.upper()}: {entity}")

        lines.extend(["", "## エラーケース", ""])

        # Error cases
        for err in func_def.get("error_cases", []):
            code = err.get("code", "")
            msg = err.get("message", "")
            lines.append(f"- `{code}`: {msg}")

        if not func_def.get("error_cases"):
            lines.append("- なし")

        lines.extend(["", "## 関連テスト", ""])
        lines.append("このタスク完了後、以下のテストがGREENであることを確認:")
        lines.append("")
        lines.append(f"- `test_{function_name}_at.py` (このタスクのAT)")
        lines.append(f"- `test_unit.py` (UT)")

        if related_functions:
            lines.append("")
            lines.append("### 影響を受ける可能性のある関連テスト")
            for rel in related_functions:
                lines.append(f"- `test_{rel}_at.py`")

        lines.extend([
            "",
            "## テスト実行",
            "",
            "```bash",
            "# このタスクフォルダで実行",
            "pytest  # Python",
            "# または",
            "npx jest  # Node.js",
            "```",
        ])

        return "\n".join(lines)

    def generate_context_json(self, function_name: str) -> dict:
        """Generate context.json with necessary type definitions"""
        func_def = self.functions.get(function_name, {})

        # Get slice from dependency graph
        slice_info = self.graph.get_slice(function_name)

        context = {
            "function": function_name,
            "function_def": func_def,
            "entities": {},
            "derived": {},
            "scenarios": {},
            "invariants": []
        }

        # Extract relevant entities
        for entity_name in slice_info.get("entities", []):
            if entity_name in self.entities:
                context["entities"][entity_name] = self.entities[entity_name]

        # Extract relevant derived
        for derived_name in slice_info.get("derived", []):
            if derived_name in self.derived:
                context["derived"][derived_name] = self.derived[derived_name]

        # Extract relevant scenarios
        for scenario_id in slice_info.get("scenarios", []):
            if scenario_id in self.scenarios:
                context["scenarios"][scenario_id] = self.scenarios[scenario_id]

        # Extract relevant invariants
        invariant_ids = set(slice_info.get("invariants", []))
        for inv in self.invariants:
            if inv.get("id") in invariant_ids:
                context["invariants"].append(inv)

        return context

    def generate_skeleton_python(self, function_name: str) -> str:
        """Generate Python implementation skeleton"""
        func_def = self.functions.get(function_name, {})

        lines = [
            '"""',
            f'Implementation: {function_name}',
            '',
            'Auto-generated skeleton from TRIR specification',
            '"""',
            '',
            'from dataclasses import dataclass',
            'from typing import Any, Optional',
            'from datetime import datetime',
            '',
            '',
        ]

        # Input dataclass
        pascal_name = self._to_pascal(function_name)
        lines.append(f"@dataclass")
        lines.append(f"class {pascal_name}Input:")
        lines.append(f'    """Input parameters for {function_name}"""')

        inputs = func_def.get("input", {})
        if inputs:
            for param_name, param_def in inputs.items():
                py_type = self._trir_type_to_python(param_def.get("type", "any"))
                lines.append(f"    {param_name}: {py_type}")
        else:
            lines.append("    pass")

        lines.extend(["", ""])

        # Result dataclass
        lines.append(f"@dataclass")
        lines.append(f"class {pascal_name}Result:")
        lines.append(f'    """Result of {function_name}"""')
        lines.append(f"    success: bool")
        lines.append(f"    error: Optional[str] = None")
        lines.append(f"    error_code: Optional[str] = None")
        lines.append(f"    data: Optional[dict] = None")

        lines.extend(["", ""])

        # Function implementation
        lines.append(f"def {function_name}(input: {pascal_name}Input) -> {pascal_name}Result:")
        lines.append(f'    """')
        lines.append(f'    {func_def.get("description", function_name)}')
        lines.append(f'    ')
        lines.append(f'    Preconditions:')
        for pre in func_def.get("pre", []):
            lines.append(f'    - {self._expr_to_human(pre.get("check", {}))}')
        lines.append(f'    ')
        lines.append(f'    Post-actions:')
        for post in func_def.get("post", []):
            action = post.get("action", {})
            for action_type, entity in action.items():
                lines.append(f'    - {action_type}: {entity}')
        lines.append(f'    """')
        lines.append(f'    ')

        # Precondition checks
        lines.append(f'    # ========== Precondition Checks ==========')
        for i, pre in enumerate(func_def.get("pre", []), 1):
            lines.append(f'    # TODO: Check precondition {i}')
            lines.append(f'    # {self._expr_to_human(pre.get("check", {}))}')
            lines.append(f'    # if not _check_precondition_{i}(input):')
            lines.append(f'    #     return {pascal_name}Result(success=False, error="Precondition {i} failed")')
        lines.append(f'    ')

        # Error case checks
        if func_def.get("error_cases"):
            lines.append(f'    # ========== Error Case Checks ==========')
            for err in func_def.get("error_cases", []):
                code = err.get("code", "")
                msg = err.get("message", "")
                lines.append(f'    # TODO: Check {code}')
                lines.append(f'    # {msg}')
                lines.append(f'    # if _should_error_{code.lower().replace("-", "_")}(input):')
                lines.append(f'    #     return {pascal_name}Result(success=False, error="{msg}", error_code="{code}")')
            lines.append(f'    ')

        # Main logic
        lines.append(f'    # ========== Main Logic ==========')
        lines.append(f'    # TODO: Implement main logic')
        lines.append(f'    ')

        # Post-actions
        lines.append(f'    # ========== Post-actions ==========')
        for post in func_def.get("post", []):
            action = post.get("action", {})
            for action_type, entity in action.items():
                lines.append(f'    # TODO: {action_type} {entity}')
        lines.append(f'    ')

        lines.append(f'    raise NotImplementedError("TODO: implement {function_name}")')

        return "\n".join(lines)

    def generate_skeleton_typescript(self, function_name: str) -> str:
        """Generate TypeScript implementation skeleton"""
        func_def = self.functions.get(function_name, {})
        pascal_name = self._to_pascal(function_name)
        camel_name = self._to_camel(function_name)

        lines = [
            '/**',
            f' * Implementation: {function_name}',
            ' * ',
            ' * Auto-generated skeleton from TRIR specification',
            ' */',
            '',
        ]

        # Input interface
        lines.append(f"export interface {pascal_name}Input {{")
        for param_name, param_def in func_def.get("input", {}).items():
            ts_type = self._trir_type_to_typescript(param_def.get("type", "any"))
            optional = "?" if not param_def.get("required", True) else ""
            lines.append(f"  {param_name}{optional}: {ts_type};")
        lines.append("}")
        lines.append("")

        # Result interface
        lines.append(f"export interface {pascal_name}Result {{")
        lines.append("  success: boolean;")
        lines.append("  error?: string;")
        lines.append("  errorCode?: string;")
        lines.append("  data?: Record<string, unknown>;")
        lines.append("}")
        lines.append("")

        # Function implementation
        lines.append(f"export async function {camel_name}(input: {pascal_name}Input): Promise<{pascal_name}Result> {{")
        lines.append(f"  /**")
        lines.append(f"   * {func_def.get('description', function_name)}")
        lines.append(f"   */")
        lines.append(f"  ")

        # Preconditions
        lines.append(f"  // ========== Precondition Checks ==========")
        for i, pre in enumerate(func_def.get("pre", []), 1):
            lines.append(f"  // TODO: Check precondition {i}")
            lines.append(f"  // {self._expr_to_human(pre.get('check', {}))}")
        lines.append(f"  ")

        # Error cases
        if func_def.get("error_cases"):
            lines.append(f"  // ========== Error Case Checks ==========")
            for err in func_def.get("error_cases", []):
                code = err.get("code", "")
                msg = err.get("message", "")
                lines.append(f"  // TODO: Check {code}: {msg}")
        lines.append(f"  ")

        # Main logic
        lines.append(f"  // ========== Main Logic ==========")
        lines.append(f"  // TODO: Implement main logic")
        lines.append(f"  ")

        # Post-actions
        lines.append(f"  // ========== Post-actions ==========")
        for post in func_def.get("post", []):
            action = post.get("action", {})
            for action_type, entity in action.items():
                lines.append(f"  // TODO: {action_type} {entity}")
        lines.append(f"  ")

        lines.append(f"  throw new Error('TODO: implement {function_name}');")
        lines.append("}")

        return "\n".join(lines)

    def generate_pytest_ini(self, function_name: str, related_functions: list[str]) -> str:
        """Generate pytest.ini for this task"""
        lines = [
            "[pytest]",
            "testpaths = ../../.mesh/tests",
            "python_files = ",
            f"    test_{function_name}_at.py",
            "    test_unit.py",
        ]

        for rel in related_functions:
            lines.append(f"    test_{rel}_at.py")

        return "\n".join(lines)

    def generate_jest_config(self, function_name: str, related_functions: list[str], typescript: bool = False) -> str:
        """Generate jest.config.json for this task"""
        ext = "ts" if typescript else "js"

        test_match = [
            f"**/{function_name}.at.test.{ext}",
            f"**/unit.test.{ext}",
        ]

        for rel in related_functions:
            test_match.append(f"**/{rel}.at.test.{ext}")

        config = {
            "rootDir": "../../.mesh/tests",
            "testMatch": test_match,
        }

        if typescript:
            config["preset"] = "ts-jest"
            config["testEnvironment"] = "node"

        return json.dumps(config, indent=2)

    def generate_task_package(
        self,
        function_name: str,
        language: str | None = None,
        write_files: bool = True
    ) -> TaskPackageResult:
        """Generate complete task package for a function

        Implementation file goes to src/ (configurable via .mesh/config.json)
        Task folder contains only TASK.md, context.json, and test config
        """

        if function_name not in self.functions:
            return TaskPackageResult(
                success=False,
                task_dir="",
                tests_dir="",
                impl_path="",
                files_created=[],
                related_functions=[],
                error=f"Function not found: {function_name}"
            )

        # Use config language if not specified
        if language is None:
            language = self.config.get("language", "python")

        files_created = []
        related_functions = self.get_related_functions(function_name)

        # Get implementation file path from config
        impl_path = self.project_config.get_impl_path(function_name)
        src_dir = impl_path.parent

        # Determine file extension and naming
        is_ts = language == "typescript"
        is_js = language == "javascript"

        # Generate test files (to .mesh/tests/)
        test_files = self.generate_all_tests(language)

        # Generate task-specific files (NO impl file in task folder)
        task_name = self._apply_naming(function_name)
        task_dir = self.tasks_dir / task_name

        task_files = {
            "TASK.md": self.generate_task_md(function_name, related_functions),
            "context.json": json.dumps(self.generate_context_json(function_name), indent=2, ensure_ascii=False),
        }

        # Test config (references src/ and .mesh/tests/)
        if language == "python":
            task_files["pytest.ini"] = self.generate_pytest_ini_v2(function_name, related_functions, impl_path)
        else:
            task_files["jest.config.json"] = self.generate_jest_config_v2(function_name, related_functions, impl_path, is_ts)

        # Implementation skeleton (goes to src/)
        if language == "python":
            impl_content = self.generate_skeleton_python(function_name)
        else:
            impl_content = self.generate_skeleton_typescript(function_name)

        if write_files:
            # Create directories
            self.tests_dir.mkdir(parents=True, exist_ok=True)
            (self.tests_dir / "at").mkdir(exist_ok=True)
            (self.tests_dir / "ut").mkdir(exist_ok=True)
            task_dir.mkdir(parents=True, exist_ok=True)
            src_dir.mkdir(parents=True, exist_ok=True)

            # Write test files
            for rel_path, content in test_files.items():
                file_path = self.tests_dir / rel_path
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(content)
                files_created.append(str(file_path))

            # Write task files
            for filename, content in task_files.items():
                file_path = task_dir / filename
                file_path.write_text(content)
                files_created.append(str(file_path))

            # Write implementation skeleton to src/ (only if not exists)
            if not impl_path.exists():
                impl_path.write_text(impl_content)
                files_created.append(str(impl_path))
            # Existing implementation files are protected from overwrite

        return TaskPackageResult(
            success=True,
            task_dir=str(task_dir),
            tests_dir=str(self.tests_dir),
            impl_path=str(impl_path),
            files_created=files_created,
            related_functions=related_functions
        )

    def _apply_naming(self, name: str) -> str:
        """Apply naming convention from config"""
        if self.config.get("naming") == "camelCase":
            parts = name.split("_")
            return parts[0] + "".join(p.capitalize() for p in parts[1:])
        return name

    def generate_pytest_ini_v2(self, function_name: str, related_functions: list[str], impl_path: Path) -> str:
        """Generate pytest.ini that references src/ and .mesh/tests/"""
        # Calculate relative paths from task folder
        task_dir = self.tasks_dir / function_name
        tests_rel = os.path.relpath(self.tests_dir, task_dir)
        src_rel = os.path.relpath(impl_path.parent, task_dir)

        lines = [
            "[pytest]",
            f"testpaths = {tests_rel}",
            f"pythonpath = {src_rel}",
            "python_files = ",
            f"    test_{function_name}_at.py",
            "    test_unit.py",
        ]

        for rel in related_functions:
            lines.append(f"    test_{rel}_at.py")

        return "\n".join(lines)

    def generate_jest_config_v2(self, function_name: str, related_functions: list[str],
                                 impl_path: Path, typescript: bool = False) -> str:
        """Generate jest.config.json that references src/ and .mesh/tests/"""
        # Calculate relative paths from task folder
        func_name = self._apply_naming(function_name)
        task_dir = self.tasks_dir / func_name
        tests_rel = os.path.relpath(self.tests_dir, task_dir)
        src_rel = os.path.relpath(impl_path.parent, task_dir)

        ext = "ts" if typescript else "js"

        test_match = [
            f"<rootDir>/{tests_rel}/at/{func_name}.at.test.{ext}",
            f"<rootDir>/{tests_rel}/ut/unit.test.{ext}",
        ]

        for rel in related_functions:
            rel_name = self._apply_naming(rel)
            test_match.append(f"<rootDir>/{tests_rel}/at/{rel_name}.at.test.{ext}")

        config = {
            "rootDir": ".",
            "testMatch": test_match,
            "moduleDirectories": ["node_modules", src_rel],
        }

        if typescript:
            config["preset"] = "ts-jest"
            config["testEnvironment"] = "node"

        return json.dumps(config, indent=2)

    def generate_all_task_packages(self, language: str = "python") -> list[TaskPackageResult]:
        """Generate task packages for all functions"""
        results = []

        # First, generate all tests once
        test_files = self.generate_all_tests(language)

        # Create test directories and write files
        self.tests_dir.mkdir(parents=True, exist_ok=True)
        (self.tests_dir / "at").mkdir(exist_ok=True)
        (self.tests_dir / "ut").mkdir(exist_ok=True)

        for rel_path, content in test_files.items():
            file_path = self.tests_dir / rel_path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content)

        # Generate task packages (without re-generating tests)
        for function_name in self.functions:
            result = self.generate_task_package(function_name, language, write_files=True)
            results.append(result)

        return results

    # Helper methods
    def _to_pascal(self, name: str) -> str:
        return "".join(word.capitalize() for word in name.split("_"))

    def _to_camel(self, name: str) -> str:
        parts = name.split("_")
        return parts[0] + "".join(word.capitalize() for word in parts[1:])

    def _trir_type_to_python(self, trir_type: Any) -> str:
        if isinstance(trir_type, str):
            mapping = {
                "string": "str",
                "int": "int",
                "float": "float",
                "bool": "bool",
                "datetime": "datetime",
                "text": "str"
            }
            return mapping.get(trir_type, "Any")
        if isinstance(trir_type, dict):
            if "enum" in trir_type:
                return "str"
            if "ref" in trir_type:
                return "str"
            if "list" in trir_type:
                inner = self._trir_type_to_python(trir_type["list"])
                return f"list[{inner}]"
        return "Any"

    def _trir_type_to_typescript(self, trir_type: Any) -> str:
        if isinstance(trir_type, str):
            mapping = {
                "string": "string",
                "int": "number",
                "float": "number",
                "bool": "boolean",
                "datetime": "string",
                "text": "string"
            }
            return mapping.get(trir_type, "unknown")
        if isinstance(trir_type, dict):
            if "enum" in trir_type:
                return " | ".join(f'"{v}"' for v in trir_type["enum"])
            if "ref" in trir_type:
                return "string"
            if "list" in trir_type:
                inner = self._trir_type_to_typescript(trir_type["list"])
                return f"{inner}[]"
        return "unknown"

    def _expr_to_human(self, expr: dict) -> str:
        """Convert expression to human-readable string"""
        if not isinstance(expr, dict):
            return str(expr)

        expr_type = expr.get("type")

        if expr_type == "literal":
            return str(expr.get("value"))
        if expr_type == "ref":
            return expr.get("path", "")
        if expr_type == "self":
            field = expr.get("field", "")
            return f"self.{field}" if field else "self"
        if expr_type == "input":
            return f"input.{expr.get('name', '')}"
        if expr_type == "binary":
            op_map = {
                "eq": "==", "ne": "!=", "lt": "<", "le": "<=", "gt": ">", "ge": ">=",
                "add": "+", "sub": "-", "mul": "*", "div": "/",
                "and": "AND", "or": "OR", "in": "IN"
            }
            op = op_map.get(expr.get("op", ""), expr.get("op", ""))
            left = self._expr_to_human(expr.get("left", {}))
            right = self._expr_to_human(expr.get("right", {}))
            return f"{left} {op} {right}"
        if expr_type == "unary":
            op = expr.get("op", "")
            inner = self._expr_to_human(expr.get("expr", {}))
            return f"{op}({inner})"
        if expr_type == "agg":
            return f"{expr.get('op', '')}({expr.get('from', '')})"

        return str(expr)
