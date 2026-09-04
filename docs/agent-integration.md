# Agent integration

English | [日本語](agent-integration.ja.md)

All integrations use the same short instruction file, called an adapter:

```text
portable-agent-brain/adapters/external-brain.md
```

This file tells the agent when to find relevant notes and when to save a new
note for review. It contains no user notes. Each agent's global instructions
should contain only a short reference to this file.

## Install through setup

```sh
./brain setup
```

Select one or more agents and review the selected paths. The installer:

- uses the documented defaults or an explicit target supplied by the user;
- preserves existing instructions, hooks, permissions, and model settings;
- records one backup before the first change;
- inserts one clearly marked block or import;
- produces the same result when run again;
- verifies both the adapter path and the `brain` command;
- reports how to roll back only its own changes.

Do not install the same global block in multiple ancestor files. Doing so can
make an agent load duplicate instructions.

## Claude Code

When the installed Claude Code version supports external Markdown imports, add
one user-level import to its official global instruction file:

```markdown
@/absolute/path/to/portable-agent-brain/adapters/external-brain.md
```

The installer resolves the adapter path at installation time. It does not copy
the adapter text or knowledge notes into `CLAUDE.md`. The default user-level
target is `~/.claude/CLAUDE.md`; use `--claude-file` when the active installation
uses another documented target.

Reference: [Claude Code documentation for `CLAUDE.md` imports and
scope](https://code.claude.com/docs/en/memory).

Start a new session after installation and ask the agent to explain when it
would skip `brain context`. The answer should mention trivial tasks and should
not claim that the whole library is preloaded.

## Codex

Codex uses the appropriate global `AGENTS.md`. Setup adds a small managed block
like this, with the placeholder resolved to the real adapter path:

```markdown
<!-- portable-agent-brain:start -->
## External Brain

For non-trivial work where prior project knowledge could change the result,
read `<ADAPTER_PATH>` and follow it. Do not preload the knowledge library.
<!-- portable-agent-brain:end -->
```

The installer retains all text outside these markers. It checks for a non-empty
`AGENTS.override.md` and refuses an ambiguous install unless the override is
explicitly selected. Use `--codex-file` for another reviewed global target.
Project-local `AGENTS.md` files are not modified by default.

Reference: [Codex documentation for global `AGENTS.md` discovery and override
precedence](https://learn.chatgpt.com/docs/agent-configuration/agents-md).

Start a new Codex task to verify the managed block. Test one knowledge-dependent
request and one obvious typo request; only the first should need retrieval.

## Generic `AGENTS.md`

For Kimi or another agent that honors `AGENTS.md`, first determine its official
search order and global scope. Then add the same managed block to one effective
user-level file. Do not guess a filename merely because another product uses
it.

If an agent has no global `AGENTS.md`, use its documented rule mechanism or the
generic connection prompt instead.

## Other agents

[`prompts/connect-agent.md`](../prompts/connect-agent.md) is a one-time prompt
for an unfamiliar agent. It asks the agent to inspect its official persistent
instruction mechanism, connect only the adapter, preserve existing content,
and verify the result.

The prompt is intentionally vendor-neutral. It does not grant broader file or
network permissions and does not ask the agent to copy the library.

For setup plus initial notes from selected history, use the
[setup prompt](../prompts/setup-and-import.md).

## Saving notes when a task ends

An integration may use a supported stop hook to check whether the agent has
decided if anything is worth saving.
The hook should only look for the task-end result marker and ask the
same agent to perform the decision once. It must not:

- save or parse the raw transcript;
- call a second model or remote service;
- write knowledge directly;
- repeat when the hook is already active;
- approve a new note, combine it with other notes, replace an existing note,
  or make a Git commit.

The agent that has the task context creates a short structured summary and
calls `brain learn-extract` only when it found reusable knowledge. Valid result
marker values are `saved`, `duplicate`, `reinforced`, `none`, and `error`.

Stop integration is optional for agents that do not expose a safe hook. The agent
or user can still submit a task summary without a hook.

## Finding the notes folder

Agent instruction files use the same path selection order as the CLI:

1. An explicit `--library` option for the command being run.
2. `BRAIN_LIBRARY` inside the agent's environment.
3. A setup-managed default.
4. `~/agent-library` when none of the above is set.

An environment variable set on the host may not exist inside a sandbox. Verify
the value from the agent's runtime and use the sandbox-visible mount path.

## Rollback

To undo setup, remove only files and settings that Portable Agent Brain installed:

1. Remove the managed block between its exact markers.
2. Remove only the adapter import added by setup.
3. Remove only a stop-hook entry whose command matches this installation.
4. Remove a command link only after confirming its target.
5. Restore the setup backup only when a precise managed rollback is impossible.

Never replace an entire global instruction or hook file just to remove one
integration.
