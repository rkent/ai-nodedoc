#!/usr/bin/env python3
"""
markdown_from_json.py - Generate markdown documentation from node JSON files

Usage:
    python3 markdown_from_json.py <json_file_or_dir> [--output-dir DIR]

If a directory is given, all .json files under Nodes/ within it are processed
(nodes_index.json and tmp/ files are skipped).  Output .md files are placed
alongside the source .json files unless --output-dir is specified.
"""

import argparse
import json
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _interfaces_of_type(interfaces: list, *itypes: str) -> list:
    return [i for i in interfaces if i.get("itype") in itypes]


def _interface_table(items: list, show_role: bool = False) -> str:
    """Return a markdown table for a list of interface items."""
    if show_role:
        header = "| Name | Role | Message Type | Description |"
        sep = "|---|---|---|---|"
        rows = [
            f"| `{i.get('topic', '')}` | {i.get('itype', '')} "
            f"| `{i.get('mtype', '')}` | {i.get('summary', '')} |"
            for i in items
        ]
    else:
        header = "| Name | Message Type | Description |"
        sep = "|---|---|---|"
        rows = [
            f"| `{i.get('topic', '')}` | `{i.get('mtype', '')}` | {i.get('summary', '')} |"
            for i in items
        ]
    return "\n".join([header, sep] + rows)


def _parameters_table(parameters: list) -> str:
    """Return a markdown table for a list of parameter definitions."""
    header = "| Parameter | Type | Default | Description |"
    sep = "|---|---|---|---|"
    rows = [
        f"| `{p.get('name', '')}` | `{p.get('type', '')}` | `{p.get('default', '')}` | {p.get('summary', '')} |"
        for p in parameters
    ]
    return "\n".join([header, sep] + rows)


# ---------------------------------------------------------------------------
# Core conversion
# ---------------------------------------------------------------------------

def json_to_markdown(data: dict) -> str:
    """Convert a node-doc JSON dict to a markdown string."""
    parts: list[str] = []

    # ── Heading ────────────────────────────────────────────────────────────
    name = data.get("name", "Unknown Node")
    package = data.get("package", "")
    parts.append(f"# {name}\n")
    if package:
        parts.append(f"Node Description for node `{name}` in package `{package}`\n")
    else:
        parts.append(f"Node Description for node `{name}`\n")

    # ── Disclaimer ─────────────────────────────────────────────────────────
    parts.append(
        "*This file is ai generated and may contain mistakes. "
        "If you edit this file, remove this notice to prevent rewriting by ai.*\n"
    )

    # ── Description ────────────────────────────────────────────────────────
    overview = data.get("overview") or data.get("summary", "")
    if overview:
        parts.append(f"{overview}\n")

    # ── Interfaces ─────────────────────────────────────────────────────────
    interfaces = data.get("interfaces") or []

    subscribers = _interfaces_of_type(interfaces, "subscriber")
    if subscribers:
        parts.append("## Subscribers\n")
        parts.append(_interface_table(subscribers))
        parts.append("")

    publishers = _interfaces_of_type(interfaces, "publisher")
    if publishers:
        parts.append("## Publishers\n")
        parts.append(_interface_table(publishers))
        parts.append("")

    services = _interfaces_of_type(interfaces, "service", "client", "service client")
    if services:
        parts.append("## Services\n")
        parts.append(_interface_table(services, show_role=True))
        parts.append("")

    actions = _interfaces_of_type(interfaces, "action server", "action client")
    if actions:
        parts.append("## Actions\n")
        parts.append(_interface_table(actions, show_role=True))
        parts.append("")

    # ── Parameters ─────────────────────────────────────────────────────────
    parameters = data.get("parameters") or []
    if parameters:
        parts.append("## Parameters\n")
        parts.append(_parameters_table(parameters))
        parts.append("")

    # ── Running the node ───────────────────────────────────────────────────
    examples = data.get("examples") or []
    if examples:
        parts.append("## Running the Node\n")
        for example in examples:
            parts.append(f"```bash\n{example}\n```")
        parts.append("")
    elif data.get("package"):
        # Construct a minimal example from package + node name
        package = data["package"]
        node_name = name
        parts.append("## Running the Node\n")
        parts.append(f"```bash\nros2 run {package} {node_name}\n```")
        parts.append("")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------

def process_json_file(json_path: Path, output_dir: Path) -> None:
    """Read one JSON file, generate markdown, and write the .md file."""
    with open(json_path, encoding="utf-8") as fh:
        data = json.load(fh)

    markdown = json_to_markdown(data)

    node_name = data.get("name") or json_path.stem
    output_file = output_dir / f"{node_name}.md"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(markdown, encoding="utf-8")
    print(f"Written: {output_file}")


def collect_json_files(root: Path) -> list[Path]:
    """Find all node JSON files under root, skipping index/tmp files."""
    return [
        p for p in root.rglob("*.json")
        if p.name != "nodes_index.json" and "tmp" not in p.parts
    ]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate markdown node docs from JSON files."
    )
    parser.add_argument(
        "input",
        help="Path to a single .json file or an output directory containing Nodes/",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        metavar="DIR",
        help="Root directory for output .md files (default: alongside each .json file)",
    )
    args = parser.parse_args()

    input_path = Path(args.input).resolve()

    if input_path.is_file():
        out_dir = Path(args.output_dir).resolve() if args.output_dir else input_path.parent
        process_json_file(input_path, out_dir)

    elif input_path.is_dir():
        json_files = collect_json_files(input_path)
        if not json_files:
            print(f"No JSON node files found under {input_path}", file=sys.stderr)
            sys.exit(1)

        for json_file in sorted(json_files):
            if args.output_dir:
                rel = json_file.relative_to(input_path)
                out_dir = (Path(args.output_dir).resolve() / rel.parent)
            else:
                out_dir = json_file.parent
            process_json_file(json_file, out_dir)

    else:
        print(f"Error: {input_path} is neither a file nor a directory.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
