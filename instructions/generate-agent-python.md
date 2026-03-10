# Instructions: generate a python file 'node_docs.py' to use LLM agents to generate ROS node documentation

## Task Overview.

The main input to `node_docs` will be a directory path whose subdirectories may contain ROS packages. Call this directory path `root_directory`

Using root_directory as input:
- run scripts/find_file_nodes.py on root_directory to identify probable ROS nodes create by each ROS package.
- run scripts/create_node_batches.py on the output of find_file_nodes to generate batch files to be used as inputs to the LLM that will generate documentation.
- for each batch created using create_node_batches, run a LLM on the batch using the instructions in .github/prompts/document-node-batch.prompt.md to generate node documentation.

## Requirements.

- The entire process should be managed by a single python command file.
- Use Langchain to run the LLM ue to generate node documentation.
- The process should be usable as as a standalone program, outside of a vscode, calude, or copilot environment.
- generate a DOCKERFILE using Ubuntu 24.04 that can run the entire process.
