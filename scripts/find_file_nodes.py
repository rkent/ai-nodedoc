#!/usr/bin/env python3
"""
Find ROS package directories that contain ROS 2 node definitions and write a
JSON file listing each package together with all source files in which a node
definition was detected.

Usage:
    find_file_nodes.py <search_dir> <output_json> [--max N]

Arguments:
    search_dir   : Root directory to search for ROS packages
    output_json  : Path of the JSON file to write (parent dirs created if needed)
    --max N      : Stop after finding N packages with nodes
"""

import argparse
import json
import os
import re
import sys

# ---------------------------------------------------------------------------
# Patterns that indicate a ROS2 node definition in Python source files
# ---------------------------------------------------------------------------
_PY_NODE_CLASS_RE = re.compile(
    r"class\s+\w+\s*\(\s*"
    r"(?:\w+\.)*"
    r"(?:Node|LifecycleNode)\s*[,)]",
    re.MULTILINE,
)

_PY_CREATE_NODE_RE = re.compile(
    r"\brclpy\s*\.\s*create_node\s*\(",
    re.MULTILINE,
)

_PYTHON_NODE_PATTERNS = [_PY_NODE_CLASS_RE, _PY_CREATE_NODE_RE]

# ---------------------------------------------------------------------------
# Patterns that indicate a ROS2 node definition in C/C++ source files
# ---------------------------------------------------------------------------
_CPP_NODE_INHERIT_RE = re.compile(
    r":\s*public\s+"
    r"(?:rclcpp(?:_lifecycle)?\s*::\s*)"
    r"(?:Node|LifecycleNode)\b",
    re.MULTILINE,
)

_CPP_NODE_CONSTRUCT_RE = re.compile(
    r"(?:std\s*::\s*make_shared\s*<\s*rclcpp\s*::\s*(?:Node|LifecycleNode)\s*>"
    r"|rclcpp\s*::\s*(?:Node|LifecycleNode)\s*::\s*make_shared\s*\("
    r"|new\s+rclcpp\s*::\s*(?:Node|LifecycleNode)\s*\()",
    re.MULTILINE,
)

_CPP_NODE_PATTERNS = [_CPP_NODE_INHERIT_RE, _CPP_NODE_CONSTRUCT_RE]

_PYTHON_EXTENSIONS = {".py"}
_CPP_EXTENSIONS = {".cpp", ".hpp", ".h", ".cc", ".cxx"}


def _is_node_file(filepath: str) -> bool:
    """Return True if *filepath* contains a ROS 2 node definition."""
    ext = os.path.splitext(filepath)[1].lower()
    if ext in _PYTHON_EXTENSIONS:
        patterns = _PYTHON_NODE_PATTERNS
    elif ext in _CPP_EXTENSIONS:
        patterns = _CPP_NODE_PATTERNS
    else:
        return False

    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as fh:
            content = fh.read()
    except OSError:
        return False

    return any(pat.search(content) for pat in patterns)


def find_node_files(package_dir: str) -> list[str]:
    """
    Walk *package_dir* and return relative paths of all files that contain
    a ROS 2 node definition.  Subdirectories named 'test' or 'tests' are
    pruned to avoid false positives from test code.
    """
    node_files: list[str] = []
    print(f"Scanning package: {package_dir}")
    seen_real: set[str] = set()
    for dirpath, dirnames, filenames in os.walk(package_dir, followlinks=True):
        real = os.path.realpath(dirpath)
        if real in seen_real:
            dirnames.clear()
            continue
        seen_real.add(real)
        # Prune test directories in-place
        dirnames[:] = [d for d in dirnames if d.lower() not in ("test", "tests")]
        for filename in sorted(filenames):
            filepath = os.path.join(dirpath, filename)
            if _is_node_file(filepath):
                node_files.append(os.path.relpath(filepath, package_dir))
    return node_files


def _path_components(path: str) -> list[str]:
    """Return all directory components of *path* as a list."""
    parts: list[str] = []
    while True:
        head, tail = os.path.split(path)
        if tail:
            parts.append(tail)
        elif head:
            parts.append(head)
            break
        else:
            break
        path = head
    return parts


def _has_test_component(package_dir: str, search_dir: str) -> bool:
    """
    Return True if any path component of *package_dir* relative to
    *search_dir* is named 'test' or 'tests' (case-insensitive).
    """
    try:
        rel = os.path.relpath(package_dir, search_dir)
    except ValueError:
        return False
    for part in _path_components(rel):
        if part.lower() in ("test", "tests"):
            return True
    return False


def find_node_packages(search_dir: str, max_packages: int | None = None):
    """
    Yield dicts with keys 'package', 'package_dir', 'node_files' for every
    ROS package under *search_dir* that contains at least one node definition.
    """
    search_dir = os.path.abspath(search_dir)
    count = 0

    seen_real: set[str] = set()
    for dirpath, dirnames, filenames in os.walk(search_dir, followlinks=True):
        real = os.path.realpath(dirpath)
        if real in seen_real:
            dirnames.clear()
            continue
        seen_real.add(real)
        if "package.xml" not in filenames:
            continue

        package_dir = dirpath

        # Exclude packages inside test/tests path components
        if _has_test_component(package_dir, search_dir):
            continue

        node_files = find_node_files(package_dir)
        if not node_files:
            continue

        yield {
            "package": os.path.basename(package_dir),
            "package_dir": package_dir,
            "node_files": node_files,
        }

        count += 1
        if max_packages is not None and count >= max_packages:
            return


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Find ROS 2 packages with node definitions and write a JSON index."
    )
    parser.add_argument("search_dir", help="Root directory to search for ROS packages.")
    parser.add_argument(
        "output_json",
        help="Path of the JSON file to write. Parent directories are created if needed.",
    )
    parser.add_argument(
        "--max",
        metavar="N",
        type=int,
        default=None,
        dest="max_packages",
        help="Stop after finding N packages.",
    )
    args = parser.parse_args()

    results: list[dict] = []
    reached_max = False

    for entry in find_node_packages(args.search_dir, args.max_packages):
        for node_file in entry["node_files"]:
            print(f"{entry['package']}  [{node_file}]")
        results.append(entry)
        if args.max_packages is not None and len(results) >= args.max_packages:
            reached_max = True
            break

    if reached_max:
        print(f"Reached maximum of {args.max_packages} package(s); stopping search.")

    if not results:
        print("No ROS packages containing a node were found.")
        return

    # Write JSON output
    output_path = os.path.abspath(args.output_json)
    if not output_path.endswith(".json"):
        output_path += ".json"
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2)
        fh.write("\n")

    print(f"Total: {len(results)} package(s) written to {output_path}")


if __name__ == "__main__":
    main()
