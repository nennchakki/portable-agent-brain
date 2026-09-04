# Note formats and search priority

English | [日本語](knowledge-model.ja.md)

Portable Agent Brain separates the reusable engine from each user's data:

```text
public software                       private notes folder
brain CLI --------------------------> Markdown + YAML
schemas and validators ------------> project notes
agent instruction files -----------> findings and decisions
templates --------------------------> notes awaiting review
```

The private library is the folder containing your original notes. Search
results, text selected for an agent, HTML pages, and link diagrams are views of
those notes, not replacements for them.

## Library layout

A library uses this portable layout. `brain init` creates the directories; the
README and templates remain available in the public engine checkout for
optional copying.

```text
agent-library/
├── README.md
├── principles/
├── protocols/
├── projects/
│   └── <slug>/
│       ├── <slug>.md
│       └── project.yaml
├── lessons/
├── decisions/
├── preferences/
├── procedures/
├── concepts/
├── references/
├── profiles/
├── skills/
└── inbox/
    └── candidates/
```

Empty directories may contain `.gitkeep`. Files named `TEMPLATE.md` explain
formats but are not saved notes.

## Write notes in Markdown

Each note is a Markdown file with a YAML header, also called frontmatter.
A note and its links form one entry in the graph. This fictional example shows
the fields the parser accepts:

```yaml
---
graph_version: 1
id: lesson:sample-weather-cli/cache-expiry
type: lesson
project_id: sample-weather-cli
status: active
authority: verified
confidence: high
source_type: demo-fixture
created: 2026-01-01
project:
  - "[[projects/sample-weather-cli/sample-weather-cli|Sample Weather CLI]]"
domains:
  - "[[concepts/cache-expiry|Cache Expiry]]"
related: []
---
```

Use a stable `namespace:key` ID that survives file moves. Use lowercase project
slugs. Keep graph fields at the top level. Relation lists use two-space-indented,
quoted wikilinks; use `[]` for an empty list.

The v1 parser intentionally accepts a small YAML subset. Avoid YAML anchors,
nested graph maps, inline non-empty graph lists, and multiline graph scalars.
Type-specific prose belongs in the Markdown body.

## Note types

The core model supports:

- `project-knowledge` and `project-rule`
- `principle` and `protocol`
- `lesson` and `decision`
- `fact`, `preference`, `constraint`, and `procedure`
- `concept`, `reference`, `profile`, and `skill`

A type describes what a note is for. It does not make the note verified or give
it priority over other sources.

## Keep one main note for each project

Each project has exactly one main reference note at
`projects/<slug>/<slug>.md`. Give that note `node_role: project` and a stable
project ID. Do not create separate overview copies.

The neighboring `project.yaml` controls which notes are searched and selected:

```yaml
schema_version: 1
slug: sample-weather-cli
node: projects/sample-weather-cli/sample-weather-cli.md
project_type: software
domains:
  - command-line-tools
status: active
always_include: []
task_include:
  debugging:
    - lessons/sample-weather-cli/cache-expiry.md
search_include:
  - projects/sample-weather-cli/
  - lessons/sample-weather-cli/
```

- `node` points to the project's main Markdown file.
- `always_include` is only for notes that apply to every task in the project.
- `task_include` maps a supported task type to required note paths.
- `search_include` is currently loaded as metadata only; it does not restrict search.
  Do not use it as an exclusion or privacy boundary.
- `domains` provides keyword hints; it does not indicate whether a note has been verified.

Unknown task types, missing paths, or mismatched project slugs are validation
errors. Repeated entries are deduplicated during note selection; the validator
does not reject them as duplicates.

## Relations

Links have a type and a direction. These are the exact field names:

| Relation | Meaning |
|---|---|
| `project` | Note to its project's main reference note. |
| `domains` | Note to an existing topic note. |
| `related` | A connection to another relevant note. |
| `uses` | Project or procedure to a resource it uses. |
| `depends_on` | Note to an explicit prerequisite. |
| `implements` | Rule, procedure, or decision to what it implements. |
| `prevents` | Rule or procedure to the failure it prevents. |
| `caused_by` | Lesson to a verified cause. |
| `conflicts_with` | Unreviewed observation to a possible conflicting decision. |
| `supersedes` | New note to the older note it replaces. |
| `superseded_by` | Older note to its replacement. |

Links help readers and search find related notes. A link does not prove that a
note is correct, make it apply to other projects, or approve it. Use paths
relative to the notes folder in wikilinks; do not use absolute paths or `..` segments.

## Which source takes priority

The `authority` field records how a note should be used when sources disagree.
It is separate from `status` and the file's location. The order is:

1. Current project source is checked outside the library and wins when it has
   changed.
2. `canonical` means reviewed project references, decisions, and instructions
   that are currently in use.
3. `verified` means notes that have been checked against evidence.
4. `observed` means findings that have not yet been fully checked.
5. `candidate` means notes awaiting human review.
6. `rejected` and `superseded` records do not guide normal work.

Each search result should retain its ID, source path, `authority`, `status`, and
an explanation of why it was selected. The agent must be able to tell a note
awaiting review from a decision that is already in use.

## New notes need human review

`inbox/candidates/` holds notes awaiting review. They are not approved
instructions. Such a note has `candidate: true`, `review_status: pending`,
`status: pending`, and `authority: candidate`. It may be retrieved with a warning,
but reviewed instructions and decisions take priority if they disagree.

A person may reject the note, keep it as an observation, add its evidence to an
existing note, or approve it for future use. The tool does not make that
decision automatically.

## Obsidian compatibility

Open the library root as a vault. No plugin is required for Markdown,
frontmatter, or wikilinks. Personal `.obsidian/` settings are local UI state and
do not define the note format.

Obsidian's graph may display templates or support files that validators exclude
from the knowledge graph. Use the validator's counts to check which notes were
included; the diagram may show additional files.

HTML may be generated as an optional view, but the Markdown files remain the
original records.

## Schemas and validation

Machine-readable format definitions are in [`schemas/`](../schemas/README.md). A
validator should reject duplicate IDs, malformed relation lists, broken or
ambiguous links, invalid project manifests, replacement links that form a cycle,
and unsafe vault paths. It can warn about isolated nodes without inventing relations.
