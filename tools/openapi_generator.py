#!/usr/bin/env python3
"""
OpenAPI Generator: Spec YAML から OpenAPI 3.0 定義を生成

SSOT = YAML（仕様）
出力 = OpenAPI 3.0 YAML/JSON
"""

import yaml
import json
import re
from typing import Dict, List, Any, Optional
from dataclasses import dataclass


def parse_type(type_str: str) -> Dict[str, Any]:
    """
    spec の型定義を OpenAPI スキーマに変換

    Examples:
        int -> {"type": "integer"}
        string -> {"type": "string"}
        enum[open, closed] -> {"type": "string", "enum": ["open", "closed"]}
    """
    if type_str == "int":
        return {"type": "integer"}
    elif type_str == "string":
        return {"type": "string"}
    elif type_str == "bool":
        return {"type": "boolean"}
    elif type_str == "float":
        return {"type": "number"}
    elif type_str.startswith("enum["):
        # enum[open, closed] をパース
        match = re.match(r'enum\[(.*)\]', type_str)
        if match:
            values = [v.strip() for v in match.group(1).split(',')]
            return {"type": "string", "enum": values}
    elif type_str.startswith("list["):
        # list[string] をパース
        match = re.match(r'list\[(.*)\]', type_str)
        if match:
            inner_type = parse_type(match.group(1).strip())
            return {"type": "array", "items": inner_type}

    # デフォルト: string
    return {"type": "string"}


def generate_schemas(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    state 定義から OpenAPI schemas を生成
    """
    schemas = {}

    for entity_name, fields in state.items():
        properties = {}
        required = []

        for field_name, field_type in fields.items():
            properties[field_name] = parse_type(field_type)
            required.append(field_name)

        # ID フィールドを追加（なければ）
        if "id" not in properties:
            properties["id"] = {"type": "string", "description": f"{entity_name} の一意識別子"}
            required.insert(0, "id")

        schemas[entity_name.capitalize()] = {
            "type": "object",
            "properties": properties,
            "required": required
        }

    # 共通エラースキーマ
    schemas["Error"] = {
        "type": "object",
        "properties": {
            "code": {"type": "string", "description": "エラーコード"},
            "message": {"type": "string", "description": "エラーメッセージ"}
        },
        "required": ["code", "message"]
    }

    return schemas


def generate_request_schema(func_name: str, func_def: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
    """
    関数の input から request body スキーマを生成
    """
    input_def = func_def.get("input", {})

    if not input_def:
        # input が未定義の場合、when の input を参考にする
        return None

    properties = {}
    required = []

    for field_name, field_type in input_def.items():
        properties[field_name] = parse_type(field_type)
        required.append(field_name)

    return {
        "type": "object",
        "properties": properties,
        "required": required
    }


def extract_input_from_scenarios(func_name: str, scenarios: Dict[str, Any]) -> Dict[str, Any]:
    """
    シナリオから関数の入力形式を推測
    """
    properties = {}

    for scenario_id, scenario in scenarios.items():
        when = scenario.get("when", {})
        if when.get("call") == func_name:
            input_data = when.get("input", {})
            for key, value in input_data.items():
                if key not in properties:
                    # 値から型を推測
                    if isinstance(value, int):
                        properties[key] = {"type": "integer"}
                    elif isinstance(value, float):
                        properties[key] = {"type": "number"}
                    elif isinstance(value, bool):
                        properties[key] = {"type": "boolean"}
                    else:
                        properties[key] = {"type": "string"}

    if properties:
        return {
            "type": "object",
            "properties": properties,
            "required": list(properties.keys())
        }
    return None


def generate_error_responses(func_def: Dict[str, Any]) -> Dict[str, Any]:
    """
    関数の error 定義から OpenAPI responses を生成
    """
    responses = {}

    errors = func_def.get("error", [])
    for error in errors:
        if isinstance(error, dict):
            code = error.get("code", "UNKNOWN_ERROR")
            when = error.get("when", "")
            reason = error.get("reason", "")

            # エラーコードから適切な HTTP ステータスを決定
            # ビジネスルール違反は 422 Unprocessable Entity
            responses["422"] = {
                "description": f"Business Rule Violation: {code}",
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/Error"},
                        "example": {
                            "code": code,
                            "message": reason or when
                        }
                    }
                }
            }

    return responses


def generate_paths(functions: Dict[str, Any], state: Dict[str, Any], scenarios: Dict[str, Any]) -> Dict[str, Any]:
    """
    functions 定義から OpenAPI paths を生成
    """
    paths = {}

    for func_name, func_def in functions.items():
        path = f"/api/{func_name}"

        # 説明文の生成
        description_parts = []
        if func_def.get("description"):
            description_parts.append(func_def["description"])

        implements = func_def.get("implements", [])
        if implements:
            description_parts.append(f"\n\n実現する要求: {', '.join(implements)}")

        # 前提条件をドキュメント化
        pre_conditions = func_def.get("pre", [])
        if pre_conditions:
            description_parts.append("\n\n**前提条件:**")
            for pre in pre_conditions:
                if isinstance(pre, dict):
                    expr = pre.get("expr", "")
                    reason = pre.get("reason", "")
                    description_parts.append(f"\n- `{expr}`: {reason}")
                else:
                    description_parts.append(f"\n- `{pre}`")

        # リクエストボディスキーマ
        request_schema = None
        if "input" in func_def:
            request_schema = generate_request_schema(func_name, func_def, state)
        else:
            # シナリオから推測
            request_schema = extract_input_from_scenarios(func_name, scenarios)

        # レスポンス定義
        responses = {
            "200": {
                "description": "成功",
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "success": {"type": "boolean", "example": True}
                            }
                        }
                    }
                }
            },
            "400": {
                "description": "Bad Request - 前提条件違反",
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/Error"}
                    }
                }
            }
        }

        # エラーレスポンスを追加
        error_responses = generate_error_responses(func_def)
        responses.update(error_responses)

        # パス定義
        operation = {
            "summary": func_def.get("description", func_name),
            "description": "\n".join(description_parts),
            "operationId": func_name,
            "tags": [func_def.get("implements", ["default"])[0] if func_def.get("implements") else "default"],
            "responses": responses
        }

        if request_schema:
            operation["requestBody"] = {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": request_schema
                    }
                }
            }

        paths[path] = {"post": operation}

    return paths


def generate_openapi(spec: Dict[str, Any]) -> Dict[str, Any]:
    """
    Spec YAML から OpenAPI 3.0 定義を生成
    """
    meta = spec.get("meta", {})
    state = spec.get("state", {})
    functions = spec.get("functions", {})
    scenarios = spec.get("scenarios", {})

    openapi = {
        "openapi": "3.0.3",
        "info": {
            "title": meta.get("title", "Generated API"),
            "version": meta.get("version", "1.0.0"),
            "description": f"Spec ID: {meta.get('id', 'N/A')}\n\nこの API は仕様書から自動生成されました。"
        },
        "servers": [
            {"url": "http://localhost:8080", "description": "Development server"}
        ],
        "paths": generate_paths(functions, state, scenarios),
        "components": {
            "schemas": generate_schemas(state)
        }
    }

    # タグ定義（要求IDベース）
    requirements = spec.get("requirements", {})
    if requirements:
        tags = []
        for req_id, req in requirements.items():
            tags.append({
                "name": req_id,
                "description": req.get("what", "")
            })
        openapi["tags"] = tags

    return openapi


def main():
    import argparse

    parser = argparse.ArgumentParser(description='OpenAPI Generator - Spec YAML から OpenAPI 定義を生成')
    parser.add_argument('spec_path', help='Path to spec YAML file')
    parser.add_argument('--output', '-o', help='Output file path (default: stdout)')
    parser.add_argument('--format', '-f', choices=['yaml', 'json'], default='yaml',
                        help='Output format (default: yaml)')
    args = parser.parse_args()

    with open(args.spec_path, 'r') as f:
        spec = yaml.safe_load(f)

    openapi = generate_openapi(spec)

    if args.format == 'json':
        output = json.dumps(openapi, indent=2, ensure_ascii=False)
    else:
        output = yaml.dump(openapi, allow_unicode=True, default_flow_style=False, sort_keys=False)

    if args.output:
        with open(args.output, 'w') as f:
            f.write(output)
        print(f"Generated: {args.output}")
    else:
        print(output)


if __name__ == '__main__':
    main()
