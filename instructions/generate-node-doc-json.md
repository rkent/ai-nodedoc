---
name: Document Node Batch
description: Document a batch of ROS2 nodes by reading source files and writing .md and .json files.
agent: 'agent'
---

## Input

A batch JSON array. Each element has:

- `package` — the ROS package name
- `package_dir` — absolute path to the directory that contains `package.xml`
- `node_files` — list of source file paths (relative to `package_dir`) in which node definitions were detected

## Step 1 — Read source files and identify nodes

For each entry in the batch, read the files listed in `node_files` (as absolute paths constructed from `package_dir` + the relative path). The working directory for all file reads is the `package_dir` of the current batch entry.

If those files alone do not provide enough information to fully document a node (e.g. the class body is in a separate `.cpp` implementation file, parameters are declared in a utility header, or entry point names are in `setup.py` / `CMakeLists.txt`), read the additional files needed. Limit supplementary reads to files that are directly referenced (e.g. `#include` directives, Python imports) or that have standard names in the package (`setup.py`, `CMakeLists.txt`, `package.xml`).

Identify all nodes defined across the listed files. A single source file may define more than one node class.

## Step 2 — Write documentation files

For each node, write a `.json` file into `Nodes/<package name>/` relative to the directory from which this prompt is invoked — NOT relative to the package directory or any subdirectory of it. The file names must match the node name. Use `mkdir -p` to create the directory if it does not exist.

### JSON file (`<node_name>.json`)

The file must validate against `ai-instructions/node-doc.schema.json`. Include all required fields and only the allowed fields.

Key constraints (enforced by `ai-instructions/node-doc.schema.json`):
- `summary` and `overview` are plain string values (30-100 and 110-300 chars respectively)
- Each `parameters` item uses **only** these keys: `name`, `type`, `default`, `summary`
- Each `interfaces` item uses **only** these keys: `itype`, `topic`, `mtype`, `summary`
- `itype` must be one of: `publisher`, `subscriber`, `service`, `client`, `action server`, `action client`
- No extra keys are allowed anywhere in the document
- If a `.json` file already exists for a node and the `donotmodify` field is `true`, do not modify it.

After writing each `.json` file, immediately validate it against the schema:

```bash
check-jsonschema --schemafile ai-instructions/node-doc.schema.json <path-to-json-file>
```

If validation fails, examine the errors, correct the JSON file, and re-validate. Repeat until the file passes validation before moving on to the next node.

## Return

Your **entire** response must be exactly one line and nothing else:

`PACKAGE_COMPLETE: X nodes documented in package <package_name>`

Do not include any other text, summaries, lists, confirmations, or explanations. Only that single line.
