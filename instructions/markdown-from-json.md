# Generate a markdown file from a json file

Previous programs generate json files that contain information about nodes. Those json files follow the schema `instructions/node-doc.schema.json`.

Write a python script to generate node documentation, as a markdown file, from the json file as follows:

## Markdown file (`<node_name>.md`)

Include:
- "Node Description for node <node name> in package <package name>" as the top level heading
- after the node name, in italics: *This file is ai generated and may contain mistakes. If you edit this file, remove this notice to prevent rewriting by ai.*
- node description
- subscriptions, publishers, services, and actions for the node with interface (e.g. message) type, in a table.
- **IMPORTANT: ONLY include sections (## Publishers, ## Subscribers, ## Services, ## Actions) if the node actually has items of that type. DO NOT include empty sections or sections with "None". Omit the entire section if there are no items.**
- documentation of any parameters defined for the node, in a table with parameter name, type, default value, and description
- **IMPORTANT: ONLY include the Parameters section if the node actually has parameters. DO NOT include an empty Parameters section or a section with "None". Omit the entire section if there are no parameters.**
- example of how to run the node using the `ros2 run` command
