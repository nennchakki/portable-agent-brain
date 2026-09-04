# Knowledge model

Portable Agent Brain separates the reusable engine from each user's data:

```text
public engine                         private library
brain CLI --------------------------> Markdown + YAML
schemas and validators ------------> project knowledge
agent adapters --------------------> lessons and decisions
templates --------------------------> pending candidate inbox
```

The private library is the source of truth. Search results, context bundles,
HTML pages, and graph visualizations are derived views.

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
formats but are not knowledge nodes.

## Markdown nodes

Knowledge is Markdown with YAML frontmatter. This fictional lesson illustrates
the constrained graph fields:

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

## Node types

The core model supports:

- `project-knowledge` and `project-rule`
- `principle` and `protocol`
- `lesson` and `decision`
- `fact`, `preference`, `constraint`, and `procedure`
- `concept`, `reference`, `profile`, and `skill`

A type describes the note's role. It does not grant authority by itself.

## Canonical projects

Each project has exactly one canonical node at
`projects/<slug>/<slug>.md`. Give that node `node_role: project` and a stable
project ID. Do not create separate overview copies.

The neighboring `project.yaml` controls retrieval:

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

- `node` points to the one canonical project Markdown file.
- `always_include` is only for invariants relevant to every project task.
- `task_include` maps a supported task type to required knowledge paths.
- `search_include` limits project-aware discovery without forcing inclusion.
- `domains` provides conservative lexical hints; it is not an authority signal.

Unknown task types, missing paths, duplicate targets, or mismatched project
slugs are validation errors.

## Relations

Typed relations are explicit and directional:

| Relation | Meaning |
|---|---|
| `project` | Note to its canonical project node. |
| `domains` | Note to a canonical concept. |
| `related` | A useful semantic connection. |
| `uses` | Project or procedure to a resource it uses. |
| `depends_on` | Note to an explicit prerequisite. |
| `implements` | Rule, procedure, or decision to what it implements. |
| `prevents` | Rule or procedure to the failure it prevents. |
| `caused_by` | Lesson to a verified cause. |
| `conflicts_with` | Unreviewed observation to a possible conflicting decision. |
| `supersedes` | New note to the older note it replaces. |
| `superseded_by` | Older note to its replacement. |

Relations improve navigation and bounded retrieval. They do not prove a fact,
expand project scope, or promote a note. Prefer vault-root-relative paths in
wikilinks; do not use absolute paths or `..` segments.

## Authority and lifecycle

Authority is separate from status and source location:

1. Current project source is checked outside the library and wins when it has
   changed.
2. `canonical` covers reviewed active rules, decisions, principles, protocols,
   and project sources.
3. `verified` covers curated knowledge supported by evidence.
4. `observed` covers useful but incompletely verified observations.
5. `candidate` covers pending inbox notes.
6. `rejected` and `superseded` records do not guide normal work.

Every context item should retain its ID, source path, authority, status, and a
reason for inclusion. An agent must be able to distinguish a candidate from an
active decision.

## Candidate boundary

`inbox/candidates/` is a review queue, not canonical knowledge. A pending
candidate has `candidate: true`, `review_status: pending`, `status: pending`,
and `authority: candidate`. It may be retrieved with a warning, but active
knowledge wins on conflict.

Human review may reject it, keep it as an observation, merge its evidence into
an existing note, or create a reviewed canonical note. Automation never
performs that promotion.

## Obsidian compatibility

Open the library root as a vault. No plugin is required for Markdown,
frontmatter, or wikilinks. Personal `.obsidian/` settings are local UI state and
should not be the canonical schema.

Obsidian's graph may display templates or support files that validators exclude
from the knowledge graph. Validator counts, not the visual node count, define
the canonical scope.

HTML may be generated as an optional view, but Markdown remains the source of
truth.

## Schemas and validation

Machine-readable contracts are in [`schemas/`](../schemas/README.md). A
validator should reject duplicate IDs, malformed relation lists, broken or
ambiguous links, invalid project manifests, circular supersession, and unsafe
vault paths. It can warn about isolated nodes without inventing relations.
