# Schemas

Portable Agent Brain stores notes in Markdown with a YAML header, called
frontmatter. The files in this directory describe the data after YAML or JSON
has been parsed:

- [`knowledge-node.schema.json`](knowledge-node.schema.json) validates v1 node
  metadata and relation shapes.
- [`project.schema.json`](project.schema.json) validates `project.yaml`
  retrieval policy.
- [`task-summary.schema.json`](task-summary.schema.json) validates bounded input
  for `brain learn-extract`.

The runtime parser intentionally supports a constrained YAML subset. Graph
lists must be `[]` or a two-space-indented block list of quoted strings.
Relations are quoted Obsidian wikilinks.

JSON Schema cannot verify the repository around one document. The repository
validator is also responsible for:

- unique stable IDs and project slugs;
- the required location of each project's main note;
- existing, unambiguous wikilink targets;
- relation target types;
- vault-relative paths without traversal;
- replacement links that point back correctly and do not form a cycle;
- project-policy paths and task types;
- keeping notes awaiting review in their designated folder;
- secret and public-release safety.

Templates named `TEMPLATE.md` and content under `examples/` are documentation,
not the user's own saved notes.
