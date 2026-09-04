# Features and commands in detail

English | [日本語](features.ja.md) | [Beginner setup and usage guide](guide.md) | [README](../README.md)

Portable Agent Brain saves useful notes from your work with AI and helps find
the ones you need next time. You still use your usual AI for the conversation
and the work itself.

For your first setup, follow the [beginner guide](guide.md). This page explains
what the tool can do and which commands do it. You do not need to memorize them.

- [Hermes Agent and Portable Agent Brain](#hermes-agent-and-portable-agent-brain)
- [The nine commands](#the-nine-commands)
- [Choosing a notes folder and connecting your AI](#choosing-a-notes-folder-and-connecting-your-ai)
- [Finding notes and selecting what to read](#finding-notes-and-selecting-what-to-read)
- [Projects, note types, and links](#projects-note-types-and-links)
- [Saving notes and checking duplicates or disagreements](#saving-notes-and-checking-duplicates-or-disagreements)
- [Obsidian and structural checks](#obsidian-and-structural-checks)
- [Git, save reminders, and checks before publishing](#git-save-reminders-and-checks-before-publishing)
- [What it does not do yet](#what-it-does-not-do-yet)

## Hermes Agent and Portable Agent Brain

Hermes Agent uses AI models to chat and perform tasks with tools, including
commands and file operations. Portable Agent Brain stores and retrieves notes
for an AI to use. They have different jobs and can be used together.
See the [Hermes tool list](https://hermes-agent.nousresearch.com/docs/user-guide/features/tools/).

Hermes already has memory. This is not a claim that Hermes forgets everything.
Switching models within Hermes is also different from moving to another AI
app: a model change does not itself mean discarding saved knowledge.
See [model configuration](https://hermes-agent.nousresearch.com/docs/user-guide/configuring-models/).

| What you are comparing | Hermes Agent | Portable Agent Brain |
| --- | --- | --- |
| Main job | Chat and perform tasks using tools | Provide a notes folder and retrieval commands for multiple AIs |
| Memory | Built-in `MEMORY.md` and `USER.md`, plus past-session search | Project-based Markdown notes, with search and selected excerpts |
| Carrying information into the next conversation | Loads built-in memory at session start | An AI following the shared instructions calls `brain context` when needed |
| Reusing procedures | Can create, update, and share skills | Saves procedures as notes; does not automatically turn them into executable skills |
| Reviewing saved information | Can require approval for memory and skill writes | Saving commands handle notes awaiting review, without automatic approval |
| External memory | Supports additional memory providers | Uses your Markdown folder; no dedicated Hermes memory plugin is provided |
| Graphs | Offers a learning-history graph | Uses Obsidian to display notes and links; has no graph interface of its own |

For the Hermes details, see [memory, approval, and graphs](https://hermes-agent.nousresearch.com/docs/user-guide/features/memory/),
[skills](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills/),
and [external memory providers](https://hermes-agent.nousresearch.com/docs/user-guide/features/memory-providers/).
This is a comparison of roles, not a feature-count contest.

I made this because, even while using Hermes, I kept trying other AIs. Having
to explain things and rebuild that accumulated knowledge each time was painful.
What I wanted to keep was useful knowledge about my work that the next AI could
read, rather than one particular AI's internal state.

If Hermes alone meets your needs, you do not need to add Portable Agent Brain.
Use it when you move between AI tools and want to manage the same project notes
yourself. Using both does not require deleting Hermes memory or sharing its
entire storage folder with another AI. Check which settings the agent supports,
then use the [connection prompt](../prompts/connect-agent.md) to reference the
shared instructions. This is not a claim that a dedicated Hermes integration
has been tested in a running installation.

This comparison uses the official documentation checked on **2026-09-05** and
Portable Agent Brain `0.1.0`. Hermes features may differ by version and settings.

## The nine commands

A command is an operation you run in Terminal. If an AI is doing this for you,
you can simply ask it to find notes relevant to the task instead of learning
the command names.

| Command | What it does | Does it change files? |
| --- | --- | --- |
| `brain init` | Prepares an empty notes folder | Creates the notes folder and empty subfolders |
| `brain setup` | Sets the notes location, agent connection, and optional command installation or Git settings | Changes the settings you select |
| `brain search` | Lists notes matching a search | No |
| `brain context` | Returns a limited selection of excerpts for a project and task | No |
| `brain learn` | Saves one already structured note for review | Creates a note awaiting review |
| `brain learn-extract` | Makes notes from a short task summary and checks duplicates or additional evidence | May create or update notes awaiting review |
| `brain validate` | Checks note structure, project registration, and links | No |
| `brain release-check` | Checks the public software for accidentally included secrets and other disallowed content | No |
| `brain capture-hook` | Checks a result marker indicating whether the AI considered saving notes | No; may return a reminder for the AI |

Examples here use `./brain` from the downloaded software folder. If you
installed it as a command, you can use `brain` instead. Run `./brain --help`
for the command list, `./brain context --help` for all options for that
operation, or `./brain --version` to check the version.

## Choosing a notes folder and connecting your AI

`init` prepares the folder only. If you select an AI to connect, `setup` also
adds a reference to the shared instructions, `adapters/external-brain.md`, in
the settings that AI reads.
This instruction file is the shared entry point previously called the
“gateway.” It is not a server that relays traffic.

Claude Code and Codex have dedicated settings options. `generic` is for an AI
confirmed to read the `AGENTS.md` file you specify; it does not automatically
connect every AI. Setup preserves existing settings, makes backups, and avoids
adding the same reference twice.

| What you want to configure | Main options |
| --- | --- |
| Notes folder | `--library`, also called `--root` |
| AI and its settings file | `--agent`, `--claude-file`, `--codex-file`, `--generic-agents-file` |
| Shared instructions or a different agent environment | `--adapter`, `--agent-home` |
| Explicitly select Codex's higher-priority settings file | `--codex-override` |
| Where and how to install the command | `--install-command-dir`, `--cli-method auto\|symlink\|wrapper` |
| Run with supplied values instead of asking questions | `--non-interactive`; the AI must confirm the necessary values first |
| Do not save this notes location as the default | `--no-save-default` |

The notes location is selected in this order: `--library`, the `BRAIN_LIBRARY`
environment variable, the settings saved by setup, then `~/agent-library`.
An environment variable passes a value to a running program. `BRAIN_CONFIG`
and `XDG_CONFIG_HOME` can also change where the configuration file lives.
See [configuration details](getting-started.md).

Keep the software and your notes in separate folders. When connecting another
AI, check that it can access the same notes location. Installing the command
does not change `PATH`, the setting that lets programs find commands from
other folders. Normal setup does not change model selection, permissions, or
existing hooks. See [connection and removal](agent-integration.md) and
[isolated environments](sandbox.md).

## Finding notes and selecting what to read

Use `search` when you want a list of possible matches. It returns titles,
locations, status, and the reasons for matches. With `--project`, it searches
only that project's notes. To include shared notes as well, search without a
project filter or use `context`.

Use `context` when you want reading material for the task ahead. It selects
from the project's notes and shared notes, follows links, and removes duplicate
excerpts. It also shows what to prioritize, why each item was selected, and
whether it is awaiting review.

These two commands only read the included fictional project. They do not
touch your history or personal notes. `$PWD` means the software folder you
are currently in.

```sh
./brain search --library "$PWD/examples/demo-project" "cache expiry"
./brain context --library "$PWD/examples/demo-project" --project sample-weather-cli --task-type debugging "stale cached output"
```

| What to adjust | Option and default |
| --- | --- |
| Number of search results | Search's `--limit`: 5 by default, from 1 to 50 |
| Excerpt length and count | Context's `--max-chars`: 12,000 characters; `--max-items`: 12 items. Task-specific budgets may reduce these further |
| How far to follow links | `--hops 1` or `2`; defaults to one step |
| Selection score | `--min-score`: 600 by default. This is not a probability that the note is correct |
| Include the body of topic notes | `--include-concepts`; their bodies are normally omitted |
| Task type | `--task-type`; context infers it from the query and other inputs if omitted |
| Investigate selection and omission | `--trace`; diagnostic information goes to a separate output stream |
| Include replaced or superseded notes | `--include-superseded`; normally excluded |
| Output for an AI or another program | `--json`; returns named fields and values |

There are 11 task types: `architecture` (design), `implementation` (building
changes), `ui` (interfaces), `debugging` (finding faults), `testing`, `build`,
`documentation`, `research`, `analysis`, `data`, and `security`. For a small
task such as fixing a typo, context may return a result indicating that it
should be skipped.

Search uses word matches and a small Japanese–English vocabulary mapping.
It does not use vector search, which represents meaning numerically, or an AI
to reassess the ranking. Context limits the text passed to the AI; it does not
mean that only a few selected files are read from disk. Finding candidates
involves scanning the relevant note bodies.

## Projects, note types, and links

Register a project by creating `projects/<slug>/<slug>.md` and a neighboring
`project.yaml`. A `slug` is a short identifier. There is no dedicated project
registration command, but you can ask an AI to do it as described in the
[beginner guide](guide.md). Examples of the required files are in
`templates/project/`.

The `always_include` setting names candidates for every task, while
`task_include` names candidates for particular task types. Output limits still
apply; the tool reports how many of these items it omitted. **`search_include`
is currently read as configuration but does not restrict the search scope.**
Do not use it to hide private notes from search.

A note's type describes its purpose. The name alone does not establish its
accuracy or priority.

| Purpose | Type names used in files |
| --- | --- |
| Project overview and instructions | `project-knowledge`, `project-rule` |
| General principles and shared procedures | `principle`, `protocol` |
| Lessons from experience and reasons for decisions | `lesson`, `decision` |
| Facts, preferences, constraints, and procedures | `fact`, `preference`, `constraint`, `procedure` |
| Topics, sources, profiles, and skill descriptions | `concept`, `reference`, `profile`, `skill` |

Links can express relationships such as “related to,” “prevents this failure,”
or “replaces this decision.” The field names are `project`, `domains`,
`related`, `uses`, `depends_on`, `implements`, `prevents`, `caused_by`,
`conflicts_with`, `supersedes`, and `superseded_by`. Link only to existing
notes, and only when their contents support the connection. See the
[note format](knowledge-model.md) for meanings and syntax.

When current project files have changed, check those files rather than relying
on an old note. Among notes, reviewed instructions take priority, followed by
verified information, observations, and notes awaiting review. A link does not
approve a note. Rejected notes are excluded from normal work-related searches.

## Saving notes and checking duplicates or disagreements

Use `learn-extract` after normal work. It reads a short JSON summary prepared
by the AI and makes notes in six categories: facts, preferences, constraints,
lessons, procedures, and proposed decisions. The command does not call an AI
itself or summarize conversation files.

The input needs a project and task type, and these must match the command's
arguments. Use `shared` only for knowledge that applies unchanged across
projects, not as a place to put information whose project you cannot identify.

This practice command uses a fictional task summary. `--dry-run` means that it
does not save anything.

```sh
./brain learn-extract --library "$PWD/examples/demo-project" --project sample-weather-cli --task-type debugging --dry-run --json examples/demo-project/task-summary.json
```

To save real notes, use your own notes folder, registered project, and short
summary. The commands refuse to save inside the public software repository.
Do not submit secrets or raw conversations. Check the input without saving
first, then remove `--dry-run`. Supply either a file or `--stdin`; the maximum
input size is 65,536 bytes. See [JSON examples and saving notes](automatic-capture.md).

New notes go into `inbox/candidates/` and await human review. Resubmitting the
same content does not create extra files. If the tool identifies confirmation
from a separate, independent task, it may update evidence counts and related
details. Repeating the same summary is not a way to increase that count.

`learn` is a more direct operation: you supply one note as already structured
JSON. It suggests duplicates and related notes, but does not automatically
suppress duplicates in the same way as `learn-extract`. Use `learn-extract`
for saving findings after everyday work.

If you prepare note JSON yourself, `learn` accepts the six categories above,
plus `protocol` for shared procedures and `none` when nothing needs saving.
Its `--project` option is optional, and `--dry-run` lets you check before saving.

Potentially conflicting decisions produce warnings and links for a person to
review. The tool cannot fully judge natural-language meaning. Repeatedly
confirmed lessons or procedures may produce suggestions to review them as
instructions or skills, but confirmation counts do not automatically adopt
them. Saving zero notes is a valid outcome.

## Obsidian and structural checks

Open your notes folder in Obsidian. It can use the Markdown and links directly;
a Portable Agent Brain plugin is not required. See the
[opening steps and screenshot](guide.md#8-see-the-notes-in-obsidian).

`validate` checks project registration, duplicate IDs, link targets, and cycles
in replacement relationships. It may warn about unconnected notes. Its JSON
output also includes graph counts and relationships. Try it on the included
example:

```sh
./brain validate --library "$PWD/examples/demo-project" --json
```

Notes awaiting review and templates are excluded from validate's main node
count. They may appear in Obsidian, so the counts can differ. There is no
`brain graph` command or dedicated graph interface.

Passing validation does not prove that a note's contents are true. It also
does not visit external web links to check whether they still work. Format
definitions are in `schemas/`, blank templates in `templates/`, and fictional
worked examples in `examples/demo-project/`.

## Git, save reminders, and checks before publishing

### Git setup is not automatic synchronization

| `setup --git-mode` | What it does |
| --- | --- |
| `none` | Leaves Git settings unchanged; does not stop existing synchronization |
| `local` | Initializes local Git tracking if needed; preserves existing remotes |
| `existing` | Checks that the notes folder itself is already a Git repository root |
| `remote` | Initializes Git if needed and registers `--remote-url` as a destination. Its name is `--remote-name`, defaulting to `origin` |

None of these modes automatically commits, pulls, or pushes. They do not
create a GitHub repository or verify that a destination is private. If Git
configuration fails partway through, the tool leaves the partial state for
inspection. It does not delete Git history as a cleanup step.

### Reminders to consider saving notes

`capture-hook` checks for a `brain-capture:v1` result marker in the AI's reply.
If it is missing, the hook may remind the same AI to decide whether there is
anything worth saving. It does not save the conversation or start another AI.

The results are `saved`, `duplicate`, `reinforced` (additional evidence),
`none` (nothing to save), and `error`. Detecting a marker does not verify that
saving actually succeeded. Invalid input or an already active reminder, among
other conditions, is allowed through without blocking the AI from stopping.
Normal setup does not install the hook automatically. See
[integration notes](agent-integration.md).

### Checks for people changing the public software

`release-check` examines working files, reachable Git history, remote
destinations, and other release-related state in the public repository.
For routine structural checks of your personal notes, use `validate`.

```sh
./brain release-check --json
```

Use `--root` to select the public software folder and `--denylist` to supply
additional terms that must not be published. Keep that list outside the public
folder. Unknown binary files, including images, and oversized files are
rejected. The exact README image is allowed with a warning because its image
and metadata were reviewed. This check does not automatically read an image
and judge whether it contains personal information.

Saving and release checks look for secret patterns, but cannot detect every
private detail. Text read by a cloud-based AI may be processed by that service.
“Stored locally” does not mean “never sent anywhere.” See
[privacy and the scope of checks](privacy.md).

## What it does not do yet

There is no dedicated importer that reads history files directly, scheduled
synchronization, built-in chat interface, model training, or automatic note
approval. `--history-source` only checks that a path exists and displays
instructions. With the README prompt, the AI reads history you authorize,
summarizes it, and passes the summary to a saving command.

There are no dedicated CLI commands for project registration, note approval
or deletion, or conversion into executable skills. If you ask an AI to make
those changes, review what it will change first. A prompt cannot give an AI
the ability to edit inaccessible settings or read notes in an environment it
cannot access.

Start with one project and one note you would like to use again. If an
operation fails, see [troubleshooting](guide.md#11-if-something-goes-wrong).
For unfamiliar words, use the [glossary](guide.md#12-a-few-words-you-will-see).
If you still need help, remove private information before posting in
[Issues](https://github.com/nennchakki/portable-agent-brain/issues).

Checked on **2026-09-05**, against Portable Agent Brain `0.1.0` on `main`.
For implementation details, see the [CLI definitions](../tools/brain/cli.py),
[search](../tools/brain/search.py), [excerpt selection](../tools/brain/context.py),
and [saving logic](../tools/brain/extract.py).
