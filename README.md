# Portable Agent Brain

> Your agents are replaceable. Your knowledge should not be.

Portable Agent Brain is a local-first, provider-independent knowledge layer for
AI coding agents. It keeps project decisions, lessons, procedures, and
preferences in a user-owned Markdown library, then retrieves only the small
amount of knowledge relevant to the current task.

The public repository contains the engine, schemas, adapters, templates, and
documentation. It contains no user knowledge.

## Why it exists

Agent-native memory is useful, but it is usually tied to one product, account,
or runtime. Portable Agent Brain keeps the durable source of truth outside any
single agent:

```text
Claude Code ─┐
Codex ───────┼─> bounded context ─> user-owned knowledge library
Other agents ┘
```

Agents may change. The library remains ordinary Markdown and YAML that you can
inspect, edit, version, or open as an Obsidian vault.

Portable Agent Brain is a knowledge layer, not an agent runtime. It does not
replace an agent's planning, tool use, permissions, or model.

## What it provides

- A lightweight `brain` CLI for setup, retrieval, and reviewable capture.
- Task-aware lexical retrieval with project filters and bounded context.
- A Markdown and YAML knowledge graph with typed `[[wikilink]]` relations.
- Low-authority candidate capture with secret checks, duplicate suppression,
  reinforcement, and conflict warnings.
- Thin adapters for Claude Code, Codex, and agents that use `AGENTS.md`.
- Portable templates, schemas, validation, and release-safety checks.
- Local-only operation. A private Git remote is optional.

It deliberately does not require a vector database, embeddings, a hosted
service, or Obsidian.

## Quick start

Requires Python 3.11 or newer on macOS or Linux. Git is needed to clone the
engine, but is optional for operating a knowledge library. No external Python
package is required at runtime.

```sh
git clone https://github.com/nennchakki/portable-agent-brain.git
cd portable-agent-brain
./brain setup
```

The setup flow asks where to create the knowledge library, which agents to
connect, whether to install the `brain` command, and whether to configure a Git
remote. It preserves unrelated agent configuration, reports its changes, and
verifies the result.

For a local-only, explicit initialization:

```sh
export BRAIN_LIBRARY="${HOME}/agent-library"
./brain init --library "$BRAIN_LIBRARY"
```

`--library` takes precedence for a single command. `BRAIN_LIBRARY` provides an
environment-level override. Setup can also save a default location. The
library does not have to live under your home directory.

After registering a project in the library, retrieve relevant knowledge:

```sh
./brain search --library "$BRAIN_LIBRARY" "cache expiry"
./brain context --library "$BRAIN_LIBRARY" \
  --project sample-weather-cli \
  "debug stale cached output"
```

At the end of a meaningful task, an agent can submit a bounded structured
summary. The command writes only reviewable candidates and may decide that
nothing should be saved:

```sh
./brain learn-extract --library "$BRAIN_LIBRARY" \
  --project sample-weather-cli \
  --task-type debugging \
  --stdin < examples/demo-project/task-summary.json
```

Before publishing or packaging this repository, run:

```sh
./brain release-check
```

See [Getting started](docs/getting-started.md) for the complete first-run path.

## Public engine, private knowledge

Portable Agent Brain keeps the distribution and user data separate:

```text
portable-agent-brain/        public engine checkout
  brain
  tools/
  adapters/
  schemas/
  templates/

agent-library/               private user-owned library
  projects/
  lessons/
  decisions/
  preferences/
  procedures/
  concepts/
  inbox/candidates/
```

Running `brain init` creates an empty library. Documentation fixtures remain
under `examples/` in the engine repository and are never copied into a new
library unless you explicitly do so.

## Knowledge lifecycle

```text
task
  -> retrieve only relevant knowledge
  -> complete and verify the work
  -> decide whether anything is reusable
  -> validate a short structured summary
  -> save a pending candidate
  -> retrieve it later with a warning
  -> human review
```

Retrieval preserves this authority order:

```text
current project source
  > active rules and decisions
  > verified knowledge
  > observed knowledge
  > pending candidates
  > rejected or superseded records
```

Candidates never automatically become permanent rules, canonical decisions,
universal protocols, or skills. Repeated evidence can create a review proposal,
but promotion remains a human decision.

Read [Knowledge model](docs/knowledge-model.md) and
[Automatic capture](docs/automatic-capture.md) for the full contract.

## Supported agents

| Integration | Connection model |
|---|---|
| Claude Code | A thin import of the canonical adapter from user-level instructions. |
| Codex | An idempotent managed block in the appropriate global `AGENTS.md`. |
| Generic `AGENTS.md` agents | A managed block that points to the same adapter. |
| Other agents | A vendor-neutral one-time connection prompt. |

The adapter does not copy the knowledge library into agent instructions and
does not preload the vault. See [Agent integration](docs/agent-integration.md)
and [the generic connection prompt](prompts/connect-agent.md).

## Privacy model

- Knowledge stays local by default.
- Core use does not require a Git remote or a hosted database.
- A private Git repository is optional and recommended only when you want
  backup or multi-device synchronization.
- This public repository contains no personal knowledge, candidate inbox,
  runtime metrics, credentials, or private history.
- Capture accepts structured summaries, not raw conversations or tool logs.
- Secret-like input is rejected before candidate persistence.

Local storage does not by itself prevent an agent provider from receiving the
specific snippets you give to that agent. Review your agent's data controls and
retrieve only what the task needs. See [Privacy](docs/privacy.md).

## Portability

The library path is configurable and may be a host directory, a container
mount such as `/brain`, or a workspace mount such as `/workspace/.brain`.
Retrieval can operate against a read-only library. A deployment may mount only
`inbox/candidates/` as writable for capture. See
[Sandbox and read-only deployments](docs/sandbox.md).

## Documentation

- [Getting started](docs/getting-started.md)
- [Agent integration](docs/agent-integration.md)
- [Knowledge model](docs/knowledge-model.md)
- [Automatic capture](docs/automatic-capture.md)
- [Sandbox and read-only deployments](docs/sandbox.md)
- [Privacy and release safety](docs/privacy.md)
- [Schemas](schemas/README.md)
- [Fictional demo library](examples/demo-project/README.md)

## License

Portable Agent Brain is available under the [MIT License](LICENSE). Dependency
licenses remain subject to their respective terms.
