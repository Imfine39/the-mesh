#!/usr/bin/env python3
"""
Test Generator v4: AST-based test code generation from Spec YAML

Uses expression_parser for unified expression handling.
"""

import yaml
import re
from typing import Dict, List, Any, Optional, Set
from pathlib import Path

# Import expression parser
import sys
sys.path.insert(0, str(Path(__file__).parent))
from expression_parser import parse, to_python, PythonGenerator, ASTNode, FieldAccess, FunctionCall


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


# ==================================================
# Derived Function Generator
# ==================================================

def extract_entity_from_formula(formula: str) -> Optional[str]:
    """Extract the primary entity name from a formula (e.g., 'payment' from 'payment.amount - ...')"""
    # Pattern: starts with entity.field
    match = re.match(r'^(\w+)\.', formula)
    if match:
        return match.group(1)
    # Pattern: function call with entity argument
    match = re.search(r'\((\w+)\)', formula)
    if match and match.group(1) not in ('state', 'entity', 'input'):
        return match.group(1)
    return None


def generate_derived_function(name: str, d: Dict[str, Any], spec: Dict[str, Any]) -> str:
    """Generate derived function using AST parser"""
    lines = []
    formula = d.get('formula', '')
    description = d.get('description', name)
    derived_names = extract_derived_names(spec)

    # Extract entity name from formula for proper substitution
    entity_name = extract_entity_from_formula(formula)

    lines.append(f"def {name}(state: dict, entity: dict) -> Any:")
    lines.append(f'    """{description}"""')
    lines.append(f"    # Formula: {formula}")

    try:
        ast = parse(formula)
        gen = PythonGenerator(entity_var='entity', state_var='state', input_var='input_data',
                             entity_name=entity_name)

        # Handle different AST patterns
        code = gen.generate(ast)

        # For simple field access subtraction patterns, handle specially
        if 'sum(' in formula or 'count(' in formula:
            # Aggregation - already handled by generator
            lines.append(f"    return {code}")
        elif ' - ' in formula and any(dn in formula for dn in derived_names):
            # Pattern: entity.field - other_derived(entity)
            lines.append(f"    return {code}")
        elif '/' in formula and '*' in formula:
            # Ratio pattern: (a / b) * 100
            # Handle division by zero
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

def generate_function_stub(func_name: str, func_def: Dict[str, Any], spec: Dict[str, Any]) -> str:
    """Generate function stub using AST parser"""
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
                    ast = parse(when)
                    gen = PythonGenerator(state_var='state', input_var='input_data')
                    condition = gen.generate(ast)
                    lines.append(f"    if {condition}:")
                    lines.append(f'        raise BusinessError("{code}", "{reason}")')
                except Exception as e:
                    lines.append(f"    # Parse error for '{when}': {e}")
        lines.append("")

    # Precondition checks (generic PRECONDITION_FAILED)
    if pre:
        lines.append("    # 前提条件チェック")
        for p in pre:
            if isinstance(p, dict):
                expr = p.get('expr', '')
                reason = p.get('reason', '')

                try:
                    ast = parse(expr)
                    gen = PythonGenerator(state_var='state', input_var='input_data')
                    condition = gen.generate(ast)
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
                # Parse the action
                ast = parse(action)
                gen = PythonGenerator(state_var='state', input_var='input_data')
                code = gen.generate(ast)

                if condition:
                    # Conditional action
                    cond_ast = parse(condition)
                    cond_code = gen.generate(cond_ast)
                    code_lines = [l for l in code.split('\n') if l.strip()]
                    if code_lines:
                        lines.append(f"    if {cond_code}:")
                        for line in code_lines:
                            lines.append(f"        {line}")
                else:
                    # Direct action - each line gets proper indentation
                    for line in code.split('\n'):
                        if line.strip():
                            lines.append(f"    {line}")

            except Exception as e:
                lines.append(f"    # Parse error for '{action}': {e}")

    lines.append("")
    lines.append("    return {'success': True}")
    lines.append("")
    return "\n".join(lines)


# ==================================================
# Test Function Generator
# ==================================================

def translate_assertion(expr: str, entities: Set[str]) -> str:
    """Translate spec assertion to pytest assert using AST"""
    try:
        ast = parse(expr)
        gen = PythonGenerator(state_var='state', input_var='input_data')
        code = gen.generate(ast)

        # Replace entity.get('field') with state['entity'].get('field')
        # because test functions don't have entity variables defined
        for entity in entities:
            code = re.sub(rf"\b{entity}\.get\(", f"state['{entity}'].get(", code)
            # Also handle derived function calls: func(state, entity) -> func(state, state['entity'])
            code = re.sub(rf", {entity}\)", f", state['{entity}'])", code)

        return f"assert {code}"
    except Exception as e:
        # Fallback: simple regex replacement
        result = expr
        for entity in entities:
            result = re.sub(rf"\b{entity}\.(\w+)", rf"state['{entity}']['\1']", result)
        result = re.sub(r'(\w+)\((\w+)\)', r"\1(state, state['\2'])", result)
        return f"assert {result}  # Fallback: {e}"


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
            python_assert = translate_assertion(assertion, entities)
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
    lines.append("from datetime import date, datetime")
    lines.append("")
    lines.append("# Date helper")
    lines.append("def today() -> str:")
    lines.append("    return date.today().isoformat()")
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

    parser = argparse.ArgumentParser(description='Test Generator v4 - AST-based test generation')
    parser.add_argument('spec_path', help='Path to spec YAML file')
    parser.add_argument('-o', '--output', help='Output file path')

    args = parser.parse_args()

    # Load spec
    with open(args.spec_path, 'r') as f:
        spec = yaml.safe_load(f)

    # Generate test file
    test_code = generate_test_file(spec)

    # Output
    if args.output:
        with open(args.output, 'w') as f:
            f.write(test_code)
        print(f"Generated: {args.output}")
    else:
        print(test_code)


if __name__ == '__main__':
    main()
