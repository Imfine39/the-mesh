#!/usr/bin/env python3
"""
CLI script to convert Structured YAML to TRIR JSON.

Usage:
    python mesh_convert.py input.yaml -o output.json
    python mesh_convert.py input.yaml  # outputs to stdout
"""

import argparse
import json
import sys
from pathlib import Path

import yaml

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from converter import YAMLToTRIRConverter


def main():
    parser = argparse.ArgumentParser(
        description="Convert Structured YAML to TRIR JSON"
    )
    parser.add_argument("input", help="Input YAML file path")
    parser.add_argument(
        "-o", "--output",
        help="Output JSON file path (default: stdout)"
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        default=True,
        help="Pretty-print JSON output (default: True)"
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Compact JSON output"
    )

    args = parser.parse_args()

    # Load input YAML
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    with open(input_path, "r", encoding="utf-8") as f:
        yaml_spec = yaml.safe_load(f)

    # Convert to TRIR
    converter = YAMLToTRIRConverter()
    trir_spec = converter.convert(yaml_spec)

    # Output
    indent = None if args.compact else 2
    json_output = json.dumps(trir_spec, indent=indent, ensure_ascii=False)

    if args.output:
        output_path = Path(args.output)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(json_output)
        print(f"Converted: {input_path} -> {output_path}")
    else:
        print(json_output)


if __name__ == "__main__":
    main()
