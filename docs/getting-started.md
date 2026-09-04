# Getting started

This guide creates an empty, local knowledge library and connects it to an
agent without making a hosted service mandatory.

## 1. Clone the public engine

```sh
git clone https://github.com/nennchakki/portable-agent-brain.git
cd portable-agent-brain
```

The engine checkout is public software. Your knowledge library is a separate
directory and should normally remain private.

## 2. Run the guided setup

```sh
./brain setup
```

Setup covers:

1. A default or custom knowledge-library location.
2. The agents you want to connect.
3. Optional installation of the `brain` command.
4. Thin adapter installation.
5. Local-only use or an optional Git remote.
6. An optional, explicit history-mining plan; setup does not read the source.
7. Verification and a summary of changed files.

Review the prompted paths or pass explicit `--claude-file`, `--codex-file`, and
`--generic-agents-file` targets. When setup changes an existing instruction
file, it preserves unrelated text, creates a backup, and uses a managed,
idempotent block.

Setup checks predictable conflicts before writing and rolls back its own
configuration, adapter, and command changes on failure. Git configuration runs
last. If Git itself fails partway through, setup preserves any partial `.git`
state and reports that it needs manual inspection; it never deletes repository
history to simulate a rollback. A power loss or forced process kill is outside
the in-process rollback boundary.

## 3. Initialize without the wizard

For a non-interactive local-only setup, choose a directory and initialize it:

```sh
export BRAIN_LIBRARY="${HOME}/agent-library"
./brain init --library "$BRAIN_LIBRARY"
```

For a container or sandbox, use a path that is actually visible inside that
environment:

```sh
export BRAIN_LIBRARY="/brain"
./brain init --library "$BRAIN_LIBRARY"
```

Path resolution follows this order:

1. The command's `--library` option.
2. The `BRAIN_LIBRARY` environment variable.
3. A default location saved by setup.
4. The documented setup default, shown before it is created.

Do not rely on `~` when the agent has a different home directory. Do not rely
on a symlink when the sandbox cannot follow the symlink target.

## 4. Confirm the empty library

A new library contains empty folders, not user knowledge. Templates remain in
the public engine checkout so they cannot be mistaken for canonical notes. The
initial library state should be equivalent to:

```text
Projects: 0
Lessons: 0
Decisions: 0
Preferences: 0
Procedures: 0
Candidates: 0
```

If you later copy `TEMPLATE.md`, `.gitkeep`, or the template library README into
the library, validators treat them as documentation rather than knowledge
nodes.

## 5. Register a project

Copy the files in `templates/project/` into a new project directory in your
private library. Replace every `replace-me` value and review all fields before
retrieval:

```text
projects/<slug>/
  <slug>.md
  project.yaml
```

The Markdown file is the canonical project node. `project.yaml` is retrieval
policy: it points to that node and lists any task-specific knowledge that must
be considered.

The isolated [sample-weather-cli fixture](../examples/demo-project/README.md)
shows a complete fictional project. It is for documentation and tests only; it
is not installed into a new library.

## 6. Retrieve bounded context

Use lexical search when you want to inspect possible matches:

```sh
./brain search --library "$BRAIN_LIBRARY" "cache expiry"
```

Use context for a specific project task:

```sh
./brain context --library "$BRAIN_LIBRARY" \
  --project sample-weather-cli \
  "debug stale cached output"
```

Context selection starts from project policy, classifies the task, follows only
useful relations, removes duplicate nodes, and stays within a bounded budget.
It does not load the whole library.

Skip retrieval for tasks where prior knowledge cannot reasonably affect the
result, such as a clear one-character typo or a deterministic rename.

## 7. Capture only reusable knowledge

After completing and verifying a meaningful task, submit a short structured
summary rather than a transcript:

```sh
./brain learn-extract --library "$BRAIN_LIBRARY" \
  --project sample-weather-cli \
  --task-type debugging \
  --stdin < examples/demo-project/task-summary.json
```

The command may return a no-knowledge result. When it saves something, it
writes a pending candidate under `inbox/candidates/`; it does not change a
canonical note. See [Automatic capture](automatic-capture.md).

## 8. Connect agents

Run setup again and select the desired integrations, or follow
[Agent integration](agent-integration.md). Every integration points to the
same small adapter. It must not copy the library into global instructions.

For an agent without a documented integration, use
[`prompts/connect-agent.md`](../prompts/connect-agent.md).

## 9. Choose whether to use Git

Git is optional. These are all valid deployments:

- No repository: the library stays on one machine.
- A local Git repository with no remote.
- A private remote for backup or multi-device synchronization.
- An existing private remote under your control.

Do not put a real knowledge library in the public engine repository. If you add
a remote, confirm that it is private before the first push and inspect the
staged files for secrets.

## 10. Run release safety checks

When changing the public distribution, run:

```sh
./brain release-check
```

The check is for release hygiene, not a substitute for reviewing Git history
or rotating a credential that was ever exposed. See [Privacy](privacy.md).

## Updating

Update the public engine and private library independently. Before updating the
engine, keep local changes separate and review the new release. Before changing
library schemas, back up or commit the private library and run its validator.
