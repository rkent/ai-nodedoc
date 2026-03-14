#!/usr/bin/env python3
"""
node_docs.py - AI-assisted ROS 2 node documentation generator

Orchestrates the full pipeline:
  1. scripts/find_file_nodes.py   - identify ROS 2 packages with nodes
  2. scripts/create_node_batches.py - split packages into LLM-sized batches
  3. LangChain agent              - read source files, write .md + .json docs

Usage:
    python3 node_docs.py <root_directory> [options]

Options:
    --output-dir DIR     Directory under which Nodes/ is written (default: CWD)
    --batch-dir DIR      Directory for intermediate batch JSON files
                         (default: <output-dir>/tmp)
    --provider PROV      LLM provider: anthropic (default) or openai
    --model MODEL        Model name (default: provider's default)
    --max-packages N     Stop scanning after N packages with nodes
    --max-per-batch N    Max node files per batch (default: 20)
    --batch N            Only process batch number N (1-based); skip others
    --skip-scan          Skip scanning; reuse existing nodes_index.json
    --skip-batch         Skip batch creation; reuse existing batch files

Environment variables:
    ANTHROPIC_API_KEY    Required when --provider anthropic (default)
    OPENAI_API_KEY       Required when --provider openai
    OPENROUTER_API_KEY   Required when --provider openrouter
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths relative to this script
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).parent.resolve()
_CWD = Path().resolve()
_FIND_SCRIPT = _SCRIPT_DIR / "find_file_nodes.py"
_BATCH_SCRIPT = _SCRIPT_DIR / "create_node_batches.py"
_PROMPT_FILE = _CWD / "instructions" / "document-node-batch.prompt.md"
_SCHEMA_FILE = _CWD / "instructions" / "node-doc.schema.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _check_imports() -> None:
    """Exit early with a helpful message if LangChain is not installed."""
    try:
        import langchain          # noqa: F401
        import langchain_core     # noqa: F401
    except ImportError as exc:
        sys.exit(
            f"Missing dependency: {exc}\n"
            "Install dependencies with:\n"
            "    pip install -r requirements.txt\n"
            "or:\n"
            "    pip install langchain langchain-core langchain-anthropic langchain-openai"
        )


def _strip_frontmatter(text: str) -> str:
    """Remove YAML frontmatter (--- ... ---) from markdown content."""
    if not text.startswith("---"):
        return text
    end = text.find("\n---", 3)
    if end == -1:
        return text
    return text[end + 4:].lstrip("\n")


def _load_prompt() -> str:
    """Load and return the document-node-batch prompt, stripped of frontmatter."""
    with open(_PROMPT_FILE, "r", encoding="utf-8") as fh:
        raw = fh.read()
    text = _strip_frontmatter(raw)
    # Replace the relative schema path with the absolute path so check-jsonschema
    # works regardless of the agent's working directory.
    text = text.replace(
        "ai-instructions/node-doc.schema.json",
        str(_SCHEMA_FILE),
    )
    # Remove the VS-Code-specific note about using `run_in_terminal` for file reads;
    # in this standalone context the agent has direct file read access via tools.
    vscode_note = (
        "**IMPORTANT: To avoid permission dialog requests when reading files outside "
        "the workspace, use terminal commands (e.g. `cat`, `grep`) via `run_in_terminal` "
        "instead of file read tools. This prevents VS Code from requesting file access "
        "permissions.**\n\n"
    )
    text = text.replace(vscode_note, "")
    return text


def _get_llm(provider: str, model: str | None):
    """Instantiate and return the requested LangChain chat model."""
    print(f"Initializing LLM provider: {provider}" + (f" with model {model}" if model else ""))
    if provider == "anthropic":
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError:
            sys.exit("langchain-anthropic is not installed. Run: pip install langchain-anthropic")
        kwargs = {"max_tokens": 8192}
        if model:
            kwargs["model"] = model
        return ChatAnthropic(**kwargs)

    if provider == "openai":
        try:
            from langchain_openai import ChatOpenAI
        except ImportError:
            sys.exit("langchain-openai is not installed. Run: pip install langchain-openai")
        kwargs = {}
        if model:
            kwargs["model"] = model
        else:
            kwargs["model"] = "gpt-4o"
        return ChatOpenAI(**kwargs)

    if provider == "openrouter":
        try:
            from langchain_openai import ChatOpenAI
        except ImportError:
            sys.exit("langchain-openai is not installed. Run: pip install langchain-openai")
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            sys.exit("OPENROUTER_API_KEY environment variable is not set.")
        kwargs = {
            "openai_api_base": "https://openrouter.ai/api/v1",
            "openai_api_key": api_key,
            "model": model or "anthropic/claude-3.5-sonnet",
        }
        return ChatOpenAI(**kwargs)

    sys.exit(f"Unknown provider: {provider!r}. Choose 'anthropic', 'openai', or 'openrouter'.")


def _make_tools(working_dir: str):
    """Return LangChain tools for the documentation agent."""
    from langchain_core.tools import tool

    @tool
    def read_file(path: str) -> str:
        """Read and return the full text content of a file.

        Args:
            path: Absolute path, or path relative to the working directory.
        """
        print(f"Reading file: {path}")
        p = Path(path) if Path(path).is_absolute() else Path(working_dir) / path
        try:
            return p.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return f"ERROR reading {path}: {exc}"

    @tool
    def write_file(path: str, content: str) -> str:
        """Write text content to a file, creating parent directories as needed.

        Args:
            path: Absolute path, or path relative to the working directory.
            content: The text to write.
        """
        p = Path(path) if Path(path).is_absolute() else Path(working_dir) / path
        print(f"Writing file: {p}")
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            return f"OK: wrote {len(content)} chars to {p}"
        except OSError as exc:
            return f"ERROR writing {path}: {exc}"

    @tool
    def run_shell(command: str) -> str:
        """Run a shell command in the working directory and return its combined output.

        Useful for: mkdir -p, check-jsonschema, cat, ls, pipx install, etc.

        Args:
            command: The shell command string to execute.
        """
        print(f"Running shell command: {command}")
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=working_dir,
                timeout=120,
            )
            output = result.stdout
            if result.stderr:
                output += "\nSTDERR:\n" + result.stderr
            if result.returncode != 0:
                output = f"(exit code {result.returncode})\n" + output
            # Limit output to avoid excessive context usage
            return output[:10000]
        except subprocess.TimeoutExpired:
            return "ERROR: command timed out after 120s"
        except Exception as exc:
            return f"ERROR running command: {exc}"

    @tool
    def list_dir(path: str) -> str:
        """List the names of files and subdirectories inside a directory.

        Args:
            path: Absolute path, or path relative to the working directory.
        """
        p = Path(path) if Path(path).is_absolute() else Path(working_dir) / path
        try:
            entries = sorted(p.iterdir())
            lines = [e.name + ("/" if e.is_dir() else "") for e in entries]
            return "\n".join(lines) if lines else "(empty)"
        except OSError as exc:
            return f"ERROR listing {path}: {exc}"

    return [read_file, write_file, run_shell, list_dir]


def _run_batch(
    batch_file: str,
    prompt_text: str,
    llm,
    working_dir: str,
    batch_index: int,
    total_batches: int,
) -> str:
    """Run the LangChain documentation agent on one batch file."""
    from langchain.agents import create_agent

    with open(batch_file, "r", encoding="utf-8") as fh:
        batch_data = fh.read()

    tools = _make_tools(working_dir)

    system_prompt = prompt_text + f"\n\nWorking directory (write Nodes/ here): {working_dir}"

    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=system_prompt,
    )

    human_input = (
        f"Batch {batch_index} of {total_batches}.\n\n"
        f"Here is the batch JSON to process:\n"
        f"```json\n{batch_data}\n```"
    )

    result = agent.invoke(
        {"messages": [("human", human_input)]},
        config={"recursion_limit": 400},
    )
    return result["messages"][-1].content


def _run_subprocess(script: Path, args: list[str]) -> int:
    """Run a Python script as a subprocess. Returns the exit code."""
    cmd = [sys.executable, str(script)] + args
    print(f"  $ {' '.join(cmd)}")
    result = subprocess.run(cmd, text=True)
    return result.returncode


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate AI documentation for ROS 2 nodes found in a workspace."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("Environment variables:")[1].strip()
        if "Environment variables:" in __doc__
        else None,
    )
    parser.add_argument(
        "root_directory",
        help="Root directory containing ROS 2 packages to scan",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        metavar="DIR",
        help=(
            "Directory under which Nodes/ documentation is written "
            "(default: current working directory)"
        ),
    )
    parser.add_argument(
        "--batch-dir",
        default=None,
        metavar="DIR",
        help=(
            "Directory for intermediate batch JSON files "
            "(default: <output-dir>/tmp)"
        ),
    )
    parser.add_argument(
        "--provider",
        default="anthropic",
        choices=["anthropic", "openai", "openrouter"],
        help="LLM provider (default: anthropic)",
    )
    parser.add_argument(
        "--model",
        default=None,
        metavar="MODEL",
        help=(
            "Model name override. Defaults: claude-3-5-sonnet (anthropic), "
            "gpt-4o (openai), anthropic/claude-3.5-sonnet (openrouter)"
        ),
    )
    parser.add_argument(
        "--max-packages",
        type=int,
        default=None,
        metavar="N",
        help="Stop scanning after finding N packages with nodes",
    )
    parser.add_argument(
        "--max-per-batch",
        type=int,
        default=20,
        metavar="N",
        help="Maximum number of node files per batch (default: 20)",
    )
    parser.add_argument(
        "--batch",
        type=int,
        default=None,
        metavar="N",
        help="Process only batch number N (1-based); skip all others",
    )
    parser.add_argument(
        "--skip-scan",
        action="store_true",
        help=(
            "Skip scanning; reuse <output-dir>/nodes_index.json if it already exists"
        ),
    )
    parser.add_argument(
        "--skip-batch",
        action="store_true",
        help="Skip batch creation; reuse batch files already in <batch-dir>",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    _check_imports()

    # Resolve paths
    root_dir = os.path.abspath(args.root_directory)
    if not os.path.isdir(root_dir):
        sys.exit(f"Error: root_directory does not exist: {root_dir}")

    output_dir = os.path.abspath(args.output_dir) if args.output_dir else os.getcwd()
    os.makedirs(output_dir, exist_ok=True)

    batch_dir = (
        os.path.abspath(args.batch_dir)
        if args.batch_dir
        else os.path.join(output_dir, "tmp")
    )
    os.makedirs(batch_dir, exist_ok=True)

    nodes_json = os.path.join(output_dir, "nodes_index.json")

    print(f"root_directory : {root_dir}")
    print(f"output_dir     : {output_dir}")
    print(f"batch_dir      : {batch_dir}")
    print(f"LLM provider   : {args.provider}" + (f"  model: {args.model}" if args.model else ""))
    if args.provider == "openrouter" and not os.environ.get("OPENROUTER_API_KEY"):
        sys.exit("Error: OPENROUTER_API_KEY environment variable is not set.")

    # -----------------------------------------------------------------------
    # Step 1: find_file_nodes.py
    # -----------------------------------------------------------------------
    if args.skip_scan and os.path.exists(nodes_json):
        print(f"\n=== Step 1: Skipping scan (reusing {nodes_json}) ===")
    else:
        print("\n=== Step 1: Scanning for ROS 2 nodes ===")
        find_args = [root_dir, nodes_json]
        if args.max_packages:
            find_args += ["--max", str(args.max_packages)]
        rc = _run_subprocess(_FIND_SCRIPT, find_args)
        if rc != 0:
            sys.exit(f"find_file_nodes.py failed (exit {rc})")
        print(f"  -> node index written to {nodes_json}")

    # -----------------------------------------------------------------------
    # Step 2: create_node_batches.py
    # -----------------------------------------------------------------------
    if args.skip_batch and any(
        f.startswith("batch") and f.endswith(".json")
        for f in os.listdir(batch_dir)
    ):
        print(f"\n=== Step 2: Skipping batch creation (reusing files in {batch_dir}) ===")
    else:
        print("\n=== Step 2: Creating batch files ===")
        batch_args = [nodes_json, batch_dir, "--max", str(args.max_per_batch)]
        rc = _run_subprocess(_BATCH_SCRIPT, batch_args)
        if rc != 0:
            sys.exit(f"create_node_batches.py failed (exit {rc})")

    batch_files = sorted(
        os.path.join(batch_dir, f)
        for f in os.listdir(batch_dir)
        if f.startswith("batch") and f.endswith(".json")
    )
    print(f"  -> {len(batch_files)} batch file(s) in {batch_dir}")

    if not batch_files:
        print("No batches to process. Exiting.")
        return

    # -----------------------------------------------------------------------
    # Step 3: LLM agent
    # -----------------------------------------------------------------------
    print("\n=== Step 3: Running LLM agent to generate documentation ===")
    prompt_text = _load_prompt()
    llm = _get_llm(args.provider, args.model)

    errors: list[str] = []
    for i, batch_file in enumerate(batch_files, start=1):
        if args.batch is not None and i != args.batch:
            continue

        print(f"\n--- Batch {i}/{len(batch_files)}: {os.path.basename(batch_file)} ---")
        try:
            output = _run_batch(
                batch_file,
                prompt_text,
                llm,
                output_dir,
                batch_index=i,
                total_batches=len(batch_files),
            )
            print(f"Agent result: {output}")
        except Exception as exc:
            msg = f"Batch {i} ({os.path.basename(batch_file)}) failed: {exc}"
            print(f"ERROR: {msg}", file=sys.stderr)
            errors.append(msg)

    print("\n=== Documentation generation complete ===")
    if errors:
        print(f"\n{len(errors)} batch(es) encountered errors:")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)


if __name__ == "__main__":
    main()
