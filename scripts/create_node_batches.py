#!/usr/bin/env python3
"""
Split the output of find_file_nodes.py into batches for parallel processing.

Each batch contains whole packages (packages are never split across batches).
The number of node_files per batch is kept at or below MAX_NODES, except when
a single package has more than MAX_NODES node_files, in which case that
package forms its own batch.

Usage:
    create_node_batches.py <input_json> <output_dir> [--max N]

Arguments:
    input_json   : JSON file produced by find_file_nodes.py
    output_dir   : Directory to write batchNNN.json files (created if needed)
    --max N      : Maximum number of node_files per batch (default: 20)
"""

import argparse
import json
import os
import sys


MAX_NODES_DEFAULT = 20


def parse_args():
    parser = argparse.ArgumentParser(
        description="Split find_file_nodes.py output into batches.",
    )
    parser.add_argument(
        "input_json",
        help="JSON file produced by find_file_nodes.py",
    )
    parser.add_argument(
        "output_dir",
        help="Directory to write batchNNN.json files",
    )
    parser.add_argument(
        "--max",
        type=int,
        default=MAX_NODES_DEFAULT,
        dest="max_nodes",
        metavar="N",
        help=f"Maximum node_files per batch (default: {MAX_NODES_DEFAULT})",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # Read input
    try:
        with open(args.input_json, "r", encoding="utf-8") as fh:
            packages = json.load(fh)
    except FileNotFoundError:
        print(f"Error: input file not found: {args.input_json}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as exc:
        print(f"Error: failed to parse JSON: {exc}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(packages, list):
        print("Error: expected a JSON array at the top level", file=sys.stderr)
        sys.exit(1)

    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)

    # Build batches: iterate over packages and fill batches greedily
    batches = []
    current_batch = []
    current_count = 0

    for pkg in packages:
        node_files = pkg.get("node_files", [])
        n = len(node_files)

        # Start a new batch if adding this package would exceed the limit,
        # unless the current batch is empty (single oversized package).
        if current_count > 0 and current_count + n > args.max_nodes:
            batches.append(current_batch)
            current_batch = []
            current_count = 0

        current_batch.append(pkg)
        current_count += n

    if current_batch:
        batches.append(current_batch)

    # Write batch files
    for i, batch in enumerate(batches):
        batch_file = os.path.join(args.output_dir, f"batch{i + 1:03d}.json")
        with open(batch_file, "w", encoding="utf-8") as fh:
            json.dump(batch, fh, indent=2)

    total_packages = sum(len(b) for b in batches)
    total_nodes = sum(
        len(pkg.get("node_files", []))
        for batch in batches
        for pkg in batch
    )
    print(
        f"Wrote {len(batches)} batch file(s) to '{args.output_dir}' "
        f"({total_packages} packages, {total_nodes} node files, "
        f"max {args.max_nodes} per batch)."
    )


if __name__ == "__main__":
    main()
