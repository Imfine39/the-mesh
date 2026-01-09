#!/usr/bin/env python3
"""
DB Schema Generator: Spec YAML から DB スキーマを生成

SSOT = YAML（仕様）
出力 = SQL (CREATE TABLE) / Prisma schema
"""

import yaml
import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass


@dataclass
class FieldDef:
    """フィールド定義"""
    name: str
    type_str: str
    sql_type: str
    prisma_type: str
    is_primary: bool = False
    is_foreign_key: bool = False
    references: Optional[str] = None  # 参照先テーブル名
    enum_values: Optional[List[str]] = None


@dataclass
class TableDef:
    """テーブル定義"""
    name: str
    fields: List[FieldDef]


def parse_type_to_sql(type_str: str, field_name: str) -> Tuple[str, Optional[List[str]]]:
    """
    spec の型を SQL 型に変換

    Returns:
        (sql_type, enum_values or None)
    """
    if type_str == "int":
        return ("INTEGER", None)
    elif type_str == "string":
        return ("VARCHAR(255)", None)
    elif type_str == "bool":
        return ("BOOLEAN", None)
    elif type_str == "float":
        return ("DECIMAL(10,2)", None)
    elif type_str == "text":
        return ("TEXT", None)
    elif type_str == "datetime":
        return ("TIMESTAMP", None)
    elif type_str.startswith("enum["):
        match = re.match(r'enum\[(.*)\]', type_str)
        if match:
            values = [v.strip() for v in match.group(1).split(',')]
            return ("VARCHAR(50)", values)
    elif type_str.startswith("list["):
        # リストはJSONとして保存
        return ("JSON", None)

    return ("VARCHAR(255)", None)


def parse_type_to_prisma(type_str: str, field_name: str, table_name: str) -> Tuple[str, Optional[List[str]]]:
    """
    spec の型を Prisma 型に変換

    Returns:
        (prisma_type, enum_values or None)
    """
    if type_str == "int":
        return ("Int", None)
    elif type_str == "string":
        return ("String", None)
    elif type_str == "bool":
        return ("Boolean", None)
    elif type_str == "float":
        return ("Float", None)
    elif type_str == "text":
        return ("String", None)
    elif type_str == "datetime":
        return ("DateTime", None)
    elif type_str.startswith("enum["):
        match = re.match(r'enum\[(.*)\]', type_str)
        if match:
            values = [v.strip() for v in match.group(1).split(',')]
            # enum名を生成: TableName_FieldName
            enum_name = f"{table_name.capitalize()}{field_name.capitalize()}"
            return (enum_name, values)
    elif type_str.startswith("list["):
        return ("Json", None)

    return ("String", None)


def detect_foreign_key(field_name: str, all_tables: List[str]) -> Optional[str]:
    """
    フィールド名から外部キー参照先を推測

    xxx_id -> xxx テーブルへの参照
    """
    if field_name.endswith("_id") and field_name != "id":
        referenced_table = field_name[:-3]  # "_id" を除去
        if referenced_table in all_tables:
            return referenced_table
    return None


def parse_state(state: Dict[str, Any]) -> List[TableDef]:
    """
    state 定義からテーブル定義を生成
    """
    all_tables = list(state.keys())
    tables = []

    for table_name, fields in state.items():
        field_defs = []

        # ID フィールドが無ければ追加
        has_id = "id" in fields
        if not has_id:
            field_defs.append(FieldDef(
                name="id",
                type_str="string",
                sql_type="VARCHAR(36)",
                prisma_type="String",
                is_primary=True
            ))

        for field_name, field_type in fields.items():
            sql_type, sql_enum = parse_type_to_sql(field_type, field_name)
            prisma_type, prisma_enum = parse_type_to_prisma(field_type, field_name, table_name)

            # 外部キー検出
            referenced = detect_foreign_key(field_name, all_tables)

            field_def = FieldDef(
                name=field_name,
                type_str=field_type,
                sql_type=sql_type,
                prisma_type=prisma_type,
                is_primary=(field_name == "id"),
                is_foreign_key=(referenced is not None),
                references=referenced,
                enum_values=sql_enum or prisma_enum
            )
            field_defs.append(field_def)

        # created_at, updated_at を追加
        field_defs.append(FieldDef(
            name="created_at",
            type_str="datetime",
            sql_type="TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
            prisma_type="DateTime @default(now())",
            is_primary=False
        ))
        field_defs.append(FieldDef(
            name="updated_at",
            type_str="datetime",
            sql_type="TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP",
            prisma_type="DateTime @updatedAt",
            is_primary=False
        ))

        tables.append(TableDef(name=table_name, fields=field_defs))

    return tables


def generate_sql(tables: List[TableDef], dialect: str = "postgresql") -> str:
    """
    SQL CREATE TABLE 文を生成
    """
    lines = []
    lines.append(f"-- Generated from Spec YAML")
    lines.append(f"-- Dialect: {dialect}")
    lines.append("")

    # ENUMの収集（PostgreSQL用）
    enums_created = set()

    for table in tables:
        # PostgreSQL の ENUM 型を先に定義
        if dialect == "postgresql":
            for field in table.fields:
                if field.enum_values:
                    enum_name = f"{table.name}_{field.name}"
                    if enum_name not in enums_created:
                        values = ", ".join([f"'{v}'" for v in field.enum_values])
                        lines.append(f"CREATE TYPE {enum_name} AS ENUM ({values});")
                        enums_created.add(enum_name)

    if enums_created:
        lines.append("")

    for table in tables:
        lines.append(f"CREATE TABLE {table.name} (")

        field_lines = []
        constraints = []

        for field in table.fields:
            sql_type = field.sql_type

            # PostgreSQL ENUM の場合は型名を使用
            if dialect == "postgresql" and field.enum_values:
                sql_type = f"{table.name}_{field.name}"

            # CHECK 制約（MySQL等の場合）
            if dialect != "postgresql" and field.enum_values:
                check_values = ", ".join([f"'{v}'" for v in field.enum_values])
                constraints.append(f"  CHECK ({field.name} IN ({check_values}))")

            nullable = "" if field.is_primary else ""
            pk = " PRIMARY KEY" if field.is_primary else ""

            field_lines.append(f"  {field.name} {sql_type}{pk}{nullable}")

            # 外部キー制約
            if field.is_foreign_key and field.references:
                constraints.append(
                    f"  FOREIGN KEY ({field.name}) REFERENCES {field.references}(id)"
                )

        lines.append(",\n".join(field_lines))

        if constraints:
            lines.append(",")
            lines.append(",\n".join(constraints))

        lines.append(");")
        lines.append("")

    return "\n".join(lines)


def generate_prisma(tables: List[TableDef]) -> str:
    """
    Prisma schema を生成
    """
    lines = []
    lines.append("// Generated from Spec YAML")
    lines.append("")
    lines.append("generator client {")
    lines.append('  provider = "prisma-client-js"')
    lines.append("}")
    lines.append("")
    lines.append("datasource db {")
    lines.append('  provider = "postgresql"')
    lines.append('  url      = env("DATABASE_URL")')
    lines.append("}")
    lines.append("")

    # ENUM 定義を収集
    enums = {}
    for table in tables:
        for field in table.fields:
            if field.enum_values and field.prisma_type not in ["String", "Int", "Boolean", "Float", "DateTime", "Json"]:
                enums[field.prisma_type] = field.enum_values

    # ENUM 定義
    for enum_name, values in enums.items():
        lines.append(f"enum {enum_name} {{")
        for v in values:
            lines.append(f"  {v}")
        lines.append("}")
        lines.append("")

    # モデル定義
    for table in tables:
        model_name = table.name.capitalize()
        lines.append(f"model {model_name} {{")

        for field in table.fields:
            prisma_type = field.prisma_type

            # 基本型かどうかをチェック
            basic_types = ["String", "Int", "Boolean", "Float", "DateTime", "Json"]
            is_basic_or_enum = prisma_type in basic_types or prisma_type in enums

            # @id アノテーション
            annotations = []
            if field.is_primary:
                annotations.append("@id")
                annotations.append("@default(uuid())")

            # @default(now()) や @updatedAt は prisma_type に含まれている場合がある
            if "@default" in prisma_type or "@updatedAt" in prisma_type:
                # 型とアノテーションを分離
                parts = prisma_type.split(" ", 1)
                prisma_type = parts[0]
                if len(parts) > 1:
                    annotations.append(parts[1])

            # リレーション（外部キー）
            if field.is_foreign_key and field.references:
                ref_model = field.references.capitalize()
                annotations.append(f"@relation(fields: [{field.name}], references: [id])")

                # リレーションフィールドも追加する必要があるが、まずはシンプルに

            annotation_str = " " + " ".join(annotations) if annotations else ""
            lines.append(f"  {field.name} {prisma_type}{annotation_str}")

        # 逆リレーションを追加
        for other_table in tables:
            for field in other_table.fields:
                if field.references == table.name:
                    rel_name = other_table.name + "s"
                    lines.append(f"  {rel_name} {other_table.name.capitalize()}[]")

        lines.append("}")
        lines.append("")

    return "\n".join(lines)


def generate_schema(spec: Dict[str, Any], format: str = "sql", dialect: str = "postgresql") -> str:
    """
    Spec YAML から DB スキーマを生成
    """
    state = spec.get("state", {})

    if not state:
        return "-- No state defined in spec"

    tables = parse_state(state)

    if format == "prisma":
        return generate_prisma(tables)
    else:
        return generate_sql(tables, dialect)


def main():
    import argparse

    parser = argparse.ArgumentParser(description='DB Schema Generator - Spec YAML から DB スキーマを生成')
    parser.add_argument('spec_path', help='Path to spec YAML file')
    parser.add_argument('--output', '-o', help='Output file path (default: stdout)')
    parser.add_argument('--format', '-f', choices=['sql', 'prisma'], default='sql',
                        help='Output format (default: sql)')
    parser.add_argument('--dialect', '-d', choices=['postgresql', 'mysql', 'sqlite'], default='postgresql',
                        help='SQL dialect (default: postgresql)')
    args = parser.parse_args()

    with open(args.spec_path, 'r') as f:
        spec = yaml.safe_load(f)

    output = generate_schema(spec, args.format, args.dialect)

    if args.output:
        with open(args.output, 'w') as f:
            f.write(output)
        print(f"Generated: {args.output}")
    else:
        print(output)


if __name__ == '__main__':
    main()
