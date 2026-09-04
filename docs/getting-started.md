# Getting started

English | [日本語](getting-started.ja.md)

This guide creates a local folder for your notes, called a library, and connects
it to an AI agent. You do not need a hosted service.

If you are new to terminals, folders, or Git, start with the
[beginner guide](guide.md) ([日本語](guide.ja.md)).
For the complete command overview, current limits, and a comparison with Hermes Agent,
see [Features and commands](features.md) ([日本語](features.ja.md)).

## 1. Clone the public engine

```sh
git clone https://github.com/nennchakki/portable-agent-brain.git
cd portable-agent-brain
```

The engine checkout is public software. Your knowledge library is a separate
directory and should normally remain private.

This downloads the implementation from `main`. For AI-assisted setup and notes
from selected past chats, use the [setup prompt](../prompts/setup-and-import.md).

## 2. Run the guided setup

```sh
./brain setup
```

Setup covers:

1. A default or custom knowledge-library location.
2. The agents you want to connect.
3. Optional installation of the `brain` command.
4. Installation of a short instruction file that tells the agent how to use this tool.
5. Local-only use or an optional Git remote.
6. Optional guidance for reviewing past conversations; setup does not read them.
7. Verification and a summary of changed files.

Review the prompted paths or pass explicit `--claude-file`, `--codex-file`, and
`--generic-agents-file` targets. When setup changes an existing instruction
file, it preserves unrelated text, creates a backup, and marks the added section.
Running setup again does not add the same section twice.

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
the public engine checkout so they cannot be mistaken for actual user notes. The
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
the library, validators treat them as documentation rather than saved notes.

## 5. Register a project

Copy the files in `templates/project/` into a new project directory in your
private library. Replace every `replace-me` value and review all fields before using the project in a search:

```text
projects/<slug>/
  <slug>.md
  project.yaml
```

The Markdown file is the project's main reference note. `project.yaml`
contains search settings: it points to that note and lists other notes that
must be considered for particular tasks.

The isolated [sample-weather-cli fixture](../examples/demo-project/README.md)
shows a complete fictional project. It is for documentation and tests only; it
is not installed into a new library.

## 6. Find notes for a task

Use keyword search when you want to inspect possible matches:

```sh
./brain search --library "$BRAIN_LIBRARY" "cache expiry"
```

Use context for a specific project task:

```sh
./brain context --library "$BRAIN_LIBRARY" \
  --project sample-weather-cli \
  "debug stale cached output"
```

The `context` command uses the project settings and task type to select notes,
follows relevant links, removes duplicate results, and limits the output size.
It does not load the whole library.

Skip retrieval for tasks where prior knowledge cannot reasonably affect the
result, such as a clear one-character typo or a deterministic rename.

## 7. Save useful findings

After completing and verifying a meaningful task, submit a short structured
summary rather than a transcript:

```sh
./brain learn-extract --library "$BRAIN_LIBRARY" \
  --project sample-weather-cli \
  --task-type debugging \
  --stdin < examples/demo-project/task-summary.json
```

The command may return a no-knowledge result. When it saves something, it
writes a note awaiting review under `inbox/candidates/`; it does not change
existing notes. See [Saving notes](automatic-capture.md).

## 8. Connect agents

Run setup again and select the desired integrations, or follow
[Agent integration](agent-integration.md). Every integration points to the
same short instruction file, called an adapter. It must not copy your notes
into the agent's global instructions.

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

The check helps prevent accidental publication of private data, not a substitute for reviewing Git history
or rotating a credential that was ever exposed. See [Privacy](privacy.md).

## Updating

Update the public engine and private library independently. Before updating the
engine, keep local changes separate and review the new release. Before changing
library schemas, back up or commit the private library and run its validator.
