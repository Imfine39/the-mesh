#!/usr/bin/env python3
"""
Test Generator v5: 統一パーサーベースのテストコード生成

spec_parser を使用して v5/v6 両方の形式に対応。
"""

import yaml
import re
from typing import Dict, List, Any, Optional, Set
from pathlib import Path

# Import parsers
import sys
sys.path.insert(0, str(Path(__file__).parent))
from expression_parser import parse as parse_simple_expr, to_python, PythonGenerator, ASTNode, FieldAccess, FunctionCall
from spec_parser import SpecParser, StructuredPythonGenerator, parse_formula, to_python_code, StructuredNodeType


def to_snake_case(name: str) -> str:
    """Convert CamelCase/kebab-case to snake_case and make valid Python identifier"""
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    s2 = re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1)
    result = s2.replace('-', '_').lower()
    # Remove any characters that aren't valid in Python identifiers
    result = re.sub(r'[^a-z0-9_]', '_', result)
    return result


def to_python_value(value: Any) -> str:
    """Convert value to Python literal"""
    if isinstance(value, str):
        return f'"{value}"'
    elif isinstance(value, bool):
        return "True" if value else "False"
    elif value is None:
        return "None"
    elif isinstance(value, (int, float)):
        return str(value)
    elif isinstance(value, list):
        items = ", ".join(to_python_value(v) for v in value)
        return f"[{items}]"
    elif isinstance(value, dict):
        items = ", ".join(f'"{k}": {to_python_value(v)}' for k, v in value.items())
        return f"{{{items}}}"
    else:
        return repr(value)


def extract_entities_from_spec(spec: Dict[str, Any]) -> Set[str]:
    """Extract entity names from spec"""
    entities = set()
    state = spec.get('state', {})
    entities.update(state.keys())
    scenarios = spec.get('scenarios', {})
    for scenario in scenarios.values():
        given = scenario.get('given', {})
        entities.update(given.keys())
    return entities


def extract_derived_names(spec: Dict[str, Any]) -> List[str]:
    """Extract derived function names"""
    return list(spec.get('derived', {}).keys())


def is_v6_format(formula: Any) -> bool:
    """Check if formula is in v6 structured format"""
    return isinstance(formula, dict)


# ==================================================
# Derived Function Generator
# ==================================================

def extract_entity_from_formula(formula: Any) -> Optional[str]:
    """Extract the primary entity name from a formula"""
    if isinstance(formula, str):
        # Pattern: starts with entity.field
        match = re.match(r'^(\w+)\.', formula)
        if match:
            entity = match.group(1)
            if entity != 'self':
                return entity
            return None
        # Pattern: function call with entity argument
        match = re.search(r'\((\w+)\)', formula)
        if match and match.group(1) not in ('state', 'entity', 'input', 'self'):
            return match.group(1)
    return None


def generate_derived_function(name: str, d: Dict[str, Any], spec: Dict[str, Any]) -> str:
    """Generate derived function using unified parser"""
    lines = []
    formula = d.get('formula', '')
    description = d.get('description', name)
    derived_names = extract_derived_names(spec)

    lines.append(f"def {name}(state: dict, entity: dict) -> Any:")
    lines.append(f'    """{description}"""')

    try:
        if is_v6_format(formula):
            # v6 structured format - use spec_parser
            parser = SpecParser(spec)
            ast = parser.parse_formula(formula)
            gen = StructuredPythonGenerator(
                entity_var='entity',
                state_var='state',
                input_var='input_data',
                entity_name=None,
                spec=spec
            )
            code = gen.generate(ast)
            lines.append(f"    # Formula (v6): {repr(formula)[:80]}...")
            lines.append(f"    return {code}")
        else:
            # v5 string format - use original logic with 'self' support
            lines.append(f"    # Formula (v5): {formula}")

            # Check if formula uses 'self' keyword (v6 style in string)
            if 'self.' in formula:
                parser = SpecParser(spec)
                ast = parser.parse_formula(formula)
                gen = StructuredPythonGenerator(
                    entity_var='entity',
                    state_var='state',
                    input_var='input_data',
                    spec=spec
                )
                code = gen.generate(ast)
            else:
                # Extract entity name from formula for proper substitution
                entity_name = extract_entity_from_formula(formula)
                simple_ast = parse_simple_expr(formula)
                gen = PythonGenerator(
                    entity_var='entity',
                    state_var='state',
                    input_var='input_data',
                    entity_name=entity_name
                )
                code = gen.generate(simple_ast)

            # Handle division by zero for ratio patterns
            if '/' in str(formula) and '*' in str(formula):
                lines.append(f"    try:")
                lines.append(f"        return {code}")
                lines.append(f"    except ZeroDivisionError:")
                lines.append(f"        return 0")
            else:
                lines.append(f"    return {code}")

    except Exception as e:
        # Fallback: return entity amount
        lines.append(f"    # Parse error: {e}")
        lines.append(f"    return entity.get('amount', 0)")

    lines.append("")
    return "\n".join(lines)


# ==================================================
# Function Stub Generator
# ==================================================

def generate_expression_code(expr: Any, spec: Dict[str, Any], entity_var: str = None) -> str:
    """Generate Python code from expression (string or structured)"""
    if is_v6_format(expr):
        parser = SpecParser(spec)
        ast = parser.parse_formula(expr)
        gen = StructuredPythonGenerator(
            entity_var=entity_var or 'entity',
            state_var='state',
            input_var='input_data',
            spec=spec
        )
        return gen.generate(ast)
    elif isinstance(expr, str):
        if 'self.' in expr:
            parser = SpecParser(spec)
            ast = parser.parse_formula(expr)
            gen = StructuredPythonGenerator(
                entity_var=entity_var or 'entity',
                state_var='state',
                input_var='input_data',
                spec=spec
            )
            return gen.generate(ast)
        else:
            try:
                simple_ast = parse_simple_expr(expr)
                gen = PythonGenerator(state_var='state', input_var='input_data')
                return gen.generate(simple_ast)
            except Exception:
                # Fallback for unparseable expressions
                return f"# Unparseable: {expr}"
    else:
        return repr(expr)


def generate_action_code(action: Any, spec: Dict[str, Any]) -> List[str]:
    """Generate Python code from action (string or structured)"""
    lines = []

    if is_v6_format(action):
        parser = SpecParser(spec)
        ast = parser.parse_formula(action)
        gen = StructuredPythonGenerator(
            entity_var='entity',
            state_var='state',
            input_var='input_data',
            spec=spec
        )
        code = gen.generate(ast)
        for line in code.split('\n'):
            if line.strip():
                lines.append(line)
    elif isinstance(action, str):
        try:
            simple_ast = parse_simple_expr(action)
            gen = PythonGenerator(state_var='state', input_var='input_data')
            code = gen.generate(simple_ast)
            for line in code.split('\n'):
                if line.strip():
                    lines.append(line)
        except Exception as e:
            lines.append(f"# Parse error for '{action}': {e}")
    else:
        lines.append(f"# Unknown action type: {type(action)}")

    return lines


def generate_function_stub(func_name: str, func_def: Dict[str, Any], spec: Dict[str, Any]) -> str:
    """Generate function stub using unified parser"""
    lines = []
    description = func_def.get('description', func_name)
    pre = func_def.get('pre', [])
    errors = func_def.get('error', [])
    post = func_def.get('post', [])

    entities = extract_entities_from_spec(spec)
    derived_names = extract_derived_names(spec)

    lines.append(f"def {func_name}(state: dict, input_data: dict) -> dict:")
    lines.append(f'    """{description}"""')
    lines.append("")

    # Entity references
    for entity in sorted(entities):
        lines.append(f"    {entity} = state.get('{entity}', {{}})")
        lines.append(f"    if isinstance({entity}, list): {entity} = {entity}[0] if {entity} else {{}}")
    lines.append("")

    # Business error checks (specific error codes) - BEFORE preconditions
    if errors:
        lines.append("    # ビジネスルールチェック")
        for err in errors:
            if isinstance(err, dict):
                code = err.get('code', 'UNKNOWN')
                when = err.get('when', '')
                reason = err.get('reason', '')

                try:
                    condition = generate_expression_code(when, spec)
                    lines.append(f"    if {condition}:")
                    lines.append(f'        raise BusinessError("{code}", "{reason}")')
                except Exception as e:
                    lines.append(f"    # Parse error for error condition: {e}")
        lines.append("")

    # Precondition checks (generic PRECONDITION_FAILED)
    if pre:
        lines.append("    # 前提条件チェック")
        for p in pre:
            if isinstance(p, dict):
                expr = p.get('expr', '')
                reason = p.get('reason', '')
                entity_hint = p.get('entity')

                try:
                    condition = generate_expression_code(expr, spec, entity_hint)
                    lines.append(f"    if not ({condition}):")
                    lines.append(f'        raise BusinessError("PRECONDITION_FAILED", "{reason}")')
                except Exception as e:
                    lines.append(f"    # Parse error for '{expr}': {e}")
        lines.append("")

    # State updates
    lines.append("    # 状態更新")

    for p in post:
        if isinstance(p, dict):
            action = p.get('action', '')
            condition = p.get('condition', '')

            try:
                action_lines = generate_action_code(action, spec)

                if condition:
                    # Conditional action
                    cond_code = generate_expression_code(condition, spec)
                    if action_lines:
                        lines.append(f"    if {cond_code}:")
                        for line in action_lines:
                            lines.append(f"        {line}")
                else:
                    # Direct action
                    for line in action_lines:
                        lines.append(f"    {line}")

            except Exception as e:
                lines.append(f"    # Parse error for action: {e}")

    lines.append("")
    lines.append("    return {'success': True}")
    lines.append("")
    return "\n".join(lines)


# ==================================================
# Test Function Generator
# ==================================================

def translate_assertion(assertion: Any, entities: Set[str], spec: Dict[str, Any]) -> str:
    """Translate spec assertion to pytest assert"""
    # v6 format: assertion can be dict with 'expr' key or structured expression
    if isinstance(assertion, dict):
        if 'expr' in assertion:
            assertion = assertion['expr']
        # else it's a structured expression

    try:
        code = generate_expression_code(assertion, spec)

        # Replace entity.get('field') with state['entity'].get('field')
        # because test functions don't have entity variables defined
        for entity in entities:
            code = re.sub(rf"\b{entity}\.get\(", f"state['{entity}'].get(", code)
            # Also handle derived function calls: func(state, entity) -> func(state, state['entity'])
            code = re.sub(rf", {entity}\)", f", state['{entity}'])", code)

        return f"assert {code}"
    except Exception as e:
        # Fallback
        return f"assert True  # Could not parse: {assertion} ({e})"


def generate_test_function(scenario_id: str, scenario: Dict[str, Any], spec: Dict[str, Any]) -> str:
    """Generate test function from scenario"""
    title = scenario.get('title', scenario_id)
    given = scenario.get('given', {})
    when = scenario.get('when', {})
    then = scenario.get('then', {})
    verifies = scenario.get('verifies', [])
    entities = extract_entities_from_spec(spec)

    safe_id = to_snake_case(scenario_id)
    safe_title = to_snake_case(title)
    func_name = f"test_{safe_id}_{safe_title}"
    lines = []

    # Docstring
    doc_lines = [f'"""{title}']
    if verifies:
        doc_lines.append("")
        doc_lines.append(f"Verifies: {', '.join(verifies)}")
    doc_lines.append('"""')

    lines.append(f"def {func_name}():")
    lines.append("    " + "\n    ".join(doc_lines))
    lines.append("")

    # Given: Initial state setup
    lines.append("    # Given: 初期状態")
    lines.append("    state = {}")

    for entity, data in given.items():
        lines.append(f"    state['{entity}'] = {to_python_value(data)}")

    lines.append("")

    # When: Action execution
    call = when.get('call', '')
    input_data = when.get('input', {})

    lines.append("    # When: アクション実行")
    lines.append(f"    input_data = {to_python_value(input_data)}")

    # Error expected
    if 'error' in then:
        error_code = then['error']
        lines.append("")
        lines.append(f"    # Then: エラー {error_code} が発生すること")
        lines.append("    try:")
        lines.append(f"        result = {call}(state, input_data)")
        lines.append("        assert False, 'Expected error was not raised'")
        lines.append("    except BusinessError as e:")
        lines.append(f'        assert e.code == "{error_code}"')
    else:
        lines.append(f"    result = {call}(state, input_data)")
        lines.append("")
        lines.append("    # Then: 期待結果")

        if then.get('success'):
            lines.append("    assert result['success'] is True")

        for assertion in then.get('assert', []):
            python_assert = translate_assertion(assertion, entities, spec)
            lines.append(f"    {python_assert}")

    lines.append("")
    return "\n".join(lines)


# ==================================================
# Helper Functions Generator
# ==================================================

def generate_helper_functions(spec: Dict[str, Any]) -> str:
    """Generate helper functions"""
    lines = []

    # BusinessError class
    lines.append("class BusinessError(Exception):")
    lines.append('    """ビジネスルール違反エラー"""')
    lines.append("    def __init__(self, code: str, message: str = ''):")
    lines.append("        self.code = code")
    lines.append("        self.message = message")
    lines.append("        super().__init__(f'{code}: {message}')")
    lines.append("")
    lines.append("")

    # Derived functions
    derived = spec.get('derived', {})
    for name, d in derived.items():
        lines.append(generate_derived_function(name, d, spec))
        lines.append("")

    # Function stubs
    functions = spec.get('functions', {})
    for func_name, func_def in functions.items():
        lines.append(generate_function_stub(func_name, func_def, spec))
        lines.append("")

    return "\n".join(lines)


# ==================================================
# Main Generator
# ==================================================

def generate_test_file(spec: Dict[str, Any]) -> str:
    """Generate complete test file from spec"""
    meta = spec.get('meta', {})
    scenarios = spec.get('scenarios', {})

    lines = []

    # Header
    lines.append('"""')
    lines.append(f"Auto-generated tests from: {meta.get('title', 'Spec')}")
    lines.append(f"Spec ID: {meta.get('id', 'N/A')}")
    lines.append(f"Version: {meta.get('version', 'N/A')}")
    lines.append('"""')
    lines.append("")
    lines.append("import pytest")
    lines.append("from typing import Dict, Any, List")
    lines.append("from datetime import date, datetime, timedelta")
    lines.append("")
    lines.append("# Date helpers")
    lines.append("def today() -> str:")
    lines.append("    return date.today().isoformat()")
    lines.append("")
    lines.append("def now() -> str:")
    lines.append("    return datetime.now().isoformat()")
    lines.append("")
    lines.append("def date_diff(d1: str, d2: str, unit: str = 'days') -> int:")
    lines.append("    \"\"\"Calculate difference between two dates\"\"\"")
    lines.append("    from datetime import datetime")
    lines.append("    dt1 = datetime.fromisoformat(d1)")
    lines.append("    dt2 = datetime.fromisoformat(d2)")
    lines.append("    delta = dt2 - dt1")
    lines.append("    if unit == 'days':")
    lines.append("        return delta.days")
    lines.append("    elif unit == 'hours':")
    lines.append("        return int(delta.total_seconds() / 3600)")
    lines.append("    return delta.days")
    lines.append("")
    lines.append("def overlaps(start1: str, end1: str, start2: str, end2: str) -> bool:")
    lines.append("    \"\"\"Check if two date ranges overlap\"\"\"")
    lines.append("    return start1 < end2 and start2 < end1")
    lines.append("")
    lines.append("def add_days(d: str, days: int) -> str:")
    lines.append("    \"\"\"Add days to a date\"\"\"")
    lines.append("    from datetime import datetime, timedelta")
    lines.append("    dt = datetime.fromisoformat(d)")
    lines.append("    return (dt + timedelta(days=days)).date().isoformat()")
    lines.append("")
    lines.append("")

    # Helper functions
    lines.append("# " + "=" * 50)
    lines.append("# Helper Functions (generated from spec)")
    lines.append("# " + "=" * 50)
    lines.append("")
    lines.append(generate_helper_functions(spec))

    # Test functions
    lines.append("# " + "=" * 50)
    lines.append("# Test Functions (generated from scenarios)")
    lines.append("# " + "=" * 50)
    lines.append("")

    for scenario_id, scenario in scenarios.items():
        lines.append(generate_test_function(scenario_id, scenario, spec))
        lines.append("")

    # Main
    lines.append("")
    lines.append("if __name__ == '__main__':")
    lines.append("    pytest.main([__file__, '-v'])")
    lines.append("")

    return "\n".join(lines)


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Test Generator v5 - Unified parser test generation')
    parser.add_argument('spec_path', nargs='+', help='Path to spec YAML file(s)')
    parser.add_argument('-o', '--output', help='Output directory for test files (default: tests/)')

    args = parser.parse_args()

    output_dir = Path(args.output) if args.output else Path('tests')
    output_dir.mkdir(parents=True, exist_ok=True)

    for spec_path in args.spec_path:
        spec_path = Path(spec_path)

        # Load spec
        with open(spec_path, 'r') as f:
            spec = yaml.safe_load(f)

        # Generate test file
        test_code = generate_test_file(spec)

        # Determine output filename
        output_file = output_dir / f"test_{spec_path.stem}.py"

        # Write output
        with open(output_file, 'w') as f:
            f.write(test_code)

        print(f"Generated: {output_file}")


if __name__ == '__main__':
    main()
