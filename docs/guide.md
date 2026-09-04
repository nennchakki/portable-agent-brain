# A beginner's guide to Portable Agent Brain

English | [日本語](guide.ja.md) | [Back to README](../README.md)

You do not need to know how to program to follow this guide. If an AI sent you
here, that is fine too. The short version is: this tool keeps useful notes in a
folder you own, so another AI can read them when you switch tools.

If you would rather have an AI handle setup, start with
[the setup prompt](../prompts/setup-and-import.md). The sections below explain
what it will do, which choices are yours, and how to check the result.

## 1. What you are setting up

Imagine you and an AI spend an afternoon fixing a document. You discover that
one particular export setting breaks the layout, find a setting that works,
and agree not to rename the original files. Next week you try a different AI.
You should not have to explain those findings from scratch.

Portable Agent Brain saves short notes about things like that. The next AI can
look up the notes relevant to its task. The files use Markdown, a plain-text
format that you can read in a text editor or in Obsidian.

It is not a copy of an AI's entire memory, personality, or chat account. It
does not automatically collect every conversation. It also does not make an
old or incorrect note true: new notes wait for review, and current project
files take priority over conflicting old information.

The tool runs on your computer. Its core commands do not require a separate
server or an API key. The AI you use alongside it is separate: its account,
subscription, usage limits, and any API charges still apply.

### Two folders, with different jobs

| Folder | What goes in it | Usual location |
| --- | --- | --- |
| Software folder | The program, instructions, examples, and templates from this public repository | `~/portable-agent-brain` |
| Notes folder, also called the library | Your projects, useful findings, and notes awaiting review | `~/agent-library` |

Keep these separate. Your personal notes do not belong in the public software
folder. The `~` character means your home folder, not the root of your computer.
An AI running in another environment may have a different home folder, so it
must check the actual path it can access.

## 2. What you need

- A Mac or Linux computer. Native Windows is not currently supported. This
  guide does not provide a tested Windows or WSL installation procedure.
- Python 3.11 or newer. Python runs the program; you do not need to learn the
  language to use it.
- Git to download the software using the instructions below. Keeping your
  personal notes in Git is a separate, optional choice.
- An AI agent that can read files and run commands in the environment where
  the tool is installed, if you want it to do the work for you.
- Obsidian only if you want a convenient note editor and graph view. The tool
  works without it.

Downloading the software needs an internet connection. An online AI may also
need one. Storing files locally does not make that AI work offline.

## 3. The easiest route: ask your AI

Open the [English setup prompt](../prompts/setup-and-import.md), copy the short
text at the top, and send it to the agent you want to use. You can add:

> I am new to this. Explain any choice before asking me to make it. Start with
> this AI and a local notes folder. Ask which past conversations you may use
> before reading them, and do not publish or synchronize anything.

This is a message for your AI's chat, not a command to paste into Terminal.

The prompt asks the AI to find the settings it actually reads, connect the
shared instruction file, and make initial notes from history you approve. It
also asks it to check the notes and help you open them in Obsidian.

You still choose where notes go, which AI settings may change, and which
history may be read. An AI that can only chat in a browser cannot necessarily
edit files on your computer. Likewise, an agent does not automatically have
access to your other chats, apps, or accounts. It should explain what it can
access and ask for a limited export or give you manual steps when needed.

Do not grant access to your whole computer just to get past a setup error.
If the AI says it is finished, ask it to show the notes folder, the settings
file it changed, and the checks it actually ran.

## 4. Manual setup on a Mac

If the AI has already completed setup, you can skip to
[checking the result](#6-check-that-setup-worked). Do not download a second copy
or delete an existing folder just to repeat these steps.

### Open Terminal

In Finder, open **Applications**, then **Utilities**, and double-click
**Terminal**. This is an app where you give the computer written commands.
See [Apple's Terminal instructions](https://support.apple.com/en-lamr/guide/terminal/apd5265185d-f365-44cb-8b09-71a064a42125/mac).

For each command below, copy the line inside the box into Terminal and press
Return or Enter. Wait for it to finish before entering the next one. A line
ending in `%` or `$` is usually Terminal saying it is ready; do not copy that
part. Do not copy the three backticks that surround code in raw Markdown.
On a Mac, Command-V pastes the copied text. If a command fails, stop and check
the error before continuing with the remaining lines.

### Check Git and Python

First run:

```sh
git --version
```

A response starting with `git version` means Git is available. If it is
missing, use the options on the [official Git installation page for Mac](https://git-scm.com/install/mac).
If macOS asks to install its command-line tools, read the prompt before
proceeding. Return here after installation and run the check again.

Next run:

```sh
python3 --version
```

The response must be Python **3.11 or newer**, such as `Python 3.12.10`.
Python 3.9 and 3.10 are too old for this tool. If Python is missing or too old,
use a suitable current stable installer from the
[official Python downloads for Mac](https://www.python.org/downloads/macos/).
After installation, open a new Terminal window and check again. If the old
version still appears, ask for help selecting the installed version; do not
delete the Python supplied with your system.

On Linux, open your distribution's terminal app and run the same version
checks. Follow that distribution's official instructions to install Git and
Python if necessary. Package names and commands differ, so do not copy an
administrator command intended for a different distribution.

### Download the software

Run these lines one at a time:

```sh
cd ~
```

This moves Terminal to your home folder. It does not move or delete files.

```sh
git clone --branch feat/initial-public-release https://github.com/nennchakki/portable-agent-brain.git
```

This downloads the public software into a new `portable-agent-brain` folder.
The command names the preview branch because that is where the implementation
is currently published. A branch is a particular line of development; you do
not need to create one yourself.

If Git says the destination already exists, stop here and check that folder.
It may be an earlier installation or contain your changes. Do not delete it
or overwrite it. Ask your AI to check its repository and branch.

```sh
cd portable-agent-brain
```

Terminal is now working inside the software folder. Finally, run:

```sh
./brain setup
```

The `./` means “run the program in this folder.” This starts a short series of
questions, explained below. It does not open an app window.

## 5. How to answer the setup questions

An answer in square brackets is the default. Pressing Enter without typing
accepts it. These are the prompts in the current command-line version.

### `Notes folder`

For a new installation, the usual default is `~/agent-library`, displayed as
its full path. An existing saved setting or `BRAIN_LIBRARY` environment
variable may change that default. Read the path before accepting it.

Choose a folder for your own notes, outside `portable-agent-brain`. If you are
unsure, use a new local folder. Avoid an existing shared or cloud-synchronized
folder unless you deliberately want its contents sent to that service. Setup
does not turn off synchronization managed by another app.

### `Agents (comma separated: claude,codex; blank for none)`

Type `claude` for Claude Code, `codex` for Codex, or `claude,codex` for both.
Choose only agents you actually use and whose settings you intend to change.
Press Enter without typing if you want to create the notes folder without
connecting an agent yet.

For Hermes or another agent, use the AI-assisted prompt to check that
product's actual settings mechanism. Do not assume every AI reads `AGENTS.md`.
The command also has a `generic` option, but it requires an explicit settings
file through `--generic-agents-file`; typing `generic` alone in this wizard
does not supply that file.

Setup adds a short reference to the shared file
`adapters/external-brain.md`. This is the common entry point, sometimes called
an adapter or gateway. It is an instruction file, not a network server. It
tells the AI when to look up notes and when to save useful findings.

Existing unrelated instructions are preserved, and setup makes a backup when
it changes an existing instruction file. Its added section is marked so it
can be recognized later. If setup stops because settings conflict, have the AI
inspect the exact files instead of bypassing the check. See
[Agent integration](agent-integration.md) for file selection and rollback.

### `Install brain command? (y/N)`

For this walkthrough, press Enter to choose `N`. You can use `./brain` from
the software folder without adding a command to the rest of your system.

If you choose `y`, setup installs a command link or wrapper in
`~/.local/bin`; your terminal and AI still need to be able to find that
directory. Saying yes is not proof that typing `brain` will work everywhere.

With `N`, tell your AI to use the full path to the program for future tasks,
or to run `./brain` from the software folder. Ask it to verify that choice
from its own environment. The shared settings reference alone does not make
the command available in every folder.

### `Git mode (none/local/existing/remote)`

Press Enter to choose `none` for now. Your notes stay as ordinary local files;
setup does not add Git tracking to the notes folder.

`local` creates a local Git repository without a remote destination. `existing`
uses an existing Git repository, and `remote` connects an existing remote
address you supply. None of these choices creates a GitHub repository for
you. If the notes folder already has Git or synchronization configured,
choosing `none` does not erase that configuration.

You can arrange a private backup later. There is no need to understand Git
synchronization before making your first note.

## 6. Check that setup worked

Setup prints a report, including paths and verification results. Keep the
notes folder path handy. A newly created library starts empty: setup does not
invent projects or silently import conversations.

From the software folder, run:

```sh
./brain validate --library "$HOME/agent-library"
```

Here `$HOME` means your home folder. Copy it as shown, including the dollar
sign and the quotes. If you chose a different notes folder, replace
`$HOME/agent-library` with that folder's full path, keeping the quotes.

Look for `errors: 0`. This checks supported note formats and links, not whether
every statement is true. Read any warnings rather than ignoring them. Empty
graph counts are normal before you add notes; notes awaiting review also do
not count toward the main graph totals reported by this command.

Next, begin a fresh task or session in the connected AI and ask:

> Show the Portable Agent Brain instruction file and notes folder you can
> actually read. Check that you can run the program. Do not read every note.
> Explain when you would look up past notes and when you would skip that step.

If it cannot access the folder or run the command, the connection is not yet
verified. An AI running remotely may not share your computer's files.

## 7. Make your first notes

### Start with one project

A project is a group of work that belongs together: a website, a manuscript,
or a particular research task. Registering one gives its notes a clear home
and prevents findings for unrelated work from getting mixed together.

You can ask your AI:

> Help me register this project in my notes folder. Confirm its name, what it
> covers, and which current files are the source before saving anything. Use
> the repository's project template and check the result.

The AI should create a project overview and its neighboring `project.yaml`
configuration in `projects/<slug>/`. A slug is a short identifier such as
`my-website`; it is not your account name or a password. The AI should replace
all template examples with confirmed values, and should not recreate a
project that is already registered. You do not need to write YAML or JSON
yourself. The format is described in [Getting started](getting-started.md).

### Use selected history, not every conversation

Try a small request first:

> Use only the exported conversations I select, from the past month, about
> this project. Save useful findings and working procedures as short notes
> awaiting review. Check old claims against the current files. Do not save
> transcripts, passwords, or unrelated personal details. Stop after this
> project and tell me what you saved.

The AI needs a readable export or a history source it can actually access.
You decide the files, dates, and project before it reads their contents. It
should not search your whole home folder or assume permission to read other
accounts. Review exports for secrets and other people's private information
before sharing them with an AI.

The AI does the reading and summarizing. The command
`setup --history-source` only returns guidance: it does **not** read or import
history. The setup prompt continues beyond that guidance by asking the AI to
prepare summaries and save them through `learn-extract`.

Saved notes go into `inbox/candidates/`, meaning “awaiting human review.” They
can be found in searches, with their review status, but they do not become
instructions the AI must follow. Review the content and its evidence before
deciding to adopt it. A note can also be wrong or no longer applicable. The
AI should not silently approve it, replace an existing decision, or make a
Git commit on your behalf.

## 8. See the notes in Obsidian

Obsidian is optional. If you use it, open **the notes folder**, not the public
software folder. Obsidian calls a folder of notes a *vault*.

1. Open Obsidian's vault selection screen.
2. Choose **Open folder as vault**.
3. Select your notes folder, normally `agent-library` in your home folder.
4. Open **Graph view** using the graph icon in the left sidebar.

See the official instructions for [opening a vault](https://obsidian.md/help/manage-vaults)
and [Graph view](https://obsidian.md/help/plugins/graph) if your screen differs.
The built-in graph feature is enough; you do not need a community plugin or
cloud synchronization for this. Keep any existing Obsidian settings rather
than replacing them with a new configuration.

![An existing collection of notes displayed as connected dots in Obsidian](images/obsidian-graph.png)

An example from an existing notes collection. A new installation is empty and
will not immediately look like this.

Dots represent notes and lines represent links between them. Notes with no
links may appear separately; that is not a setup failure. Ask the AI to link
notes to their project and to other notes only when there is a real,
explainable connection. Adding links just to fill the graph makes it less
useful.

A line does not prove agreement or correctness. Obsidian may show notes that
are still awaiting review, even though `brain validate` excludes them from
its main node count. Do not mark a note as reviewed just to change the graph.

## 9. Use it during normal work

At the start of a task, you can say:

> Check the relevant notes for this project before starting. Tell me if they
> disagree with the current files. Do not load the entire library.

At the end, you can say:

> If we learned anything useful for next time, save a short note for review.
> Separate what we verified from what remains uncertain. If there is nothing
> worth keeping, do not save a note just for the sake of it.

The connection instructions also ask an agent to make this judgment during
work. They are not an always-running background recorder, and an obvious
typo fix usually does not need a search or a saved note.

When you try another AI, use the setup prompt to connect it to the **same**
notes folder. Do not make a separate copy of the notes inside every agent's
settings. Verify that the new AI can access the folder; a remote agent may
need a different arrangement, which you should approve explicitly.

Avoid renaming or moving the software or notes folder casually. The settings
and command may refer to their current paths. If you do move them, ask the AI
to update only those references and verify the connection again.

## 10. Privacy, backups, updates, and removal

### Local storage is not the same as an offline AI

The notes are ordinary local files, but when an online AI reads them their
contents may become part of that service's input. Check your AI service's
data handling and your organization's rules before giving it work material.
The same applies to synced folders and backup services you already use.

Do not save passwords, API keys, access tokens, raw chat archives, or complete
tool logs. Do not include another person's private information merely because
it appeared in a conversation. Automated checks help, but cannot guarantee
that every sensitive detail will be detected. See [Privacy](privacy.md).

### Back up the notes, not just the program

Keep a private backup of your notes folder using a method you understand.
Downloading the public software again will not restore your personal notes.
Never upload the notes folder to this public repository.

If you use Git, a **commit** records a version locally. A **push** sends
commits to a remote repository. These are different operations. The ordinary
note-saving workflow does not automatically commit or push notes. A private
remote still needs a review of its access and of what you are sending.

### Updating or stopping use

Update the software separately from your notes. Before updating, run
`git status` in the software folder and check whether you have local changes.
If you do, ask the AI to preserve them before proceeding. Do not use a forced
reset or delete the folder to make an update work.

To stop using the integration, remove only its marked settings section or
its added import. Do not replace your entire AI settings file or delete your
notes. Backups and precise removal steps are described in
[Agent integration: Rollback](agent-integration.md#rollback).

## 11. If something goes wrong

| What you see | What to check next |
| --- | --- |
| `git: command not found` | Install Git using the official instructions above, then reopen Terminal and check its version. |
| Python is missing, too old, or gives an error before setup starts | Run `python3 --version`. Confirm that the command actually selects Python 3.11 or newer. |
| `destination path ... already exists` | Inspect the existing folder. Do not delete it or clone over it. |
| `brain: command not found` | If you chose `N`, use `./brain` from the software folder. For the AI, verify the program's full path. |
| `./brain: no such file or directory` | Check which folder Terminal is in. The `brain` file belongs in the downloaded software folder. |
| Setup reports conflicting instructions or an active override | Have the AI inspect the named settings files and which one is effective. Preserve existing content. |
| Unknown or unregistered project | Check that the project overview and `project.yaml` exist together, and that their slug matches the request. |
| Search finds nothing | Check the notes folder and project. An empty library or an unrelated query can legitimately return no results. |
| The graph is empty or notes are isolated | Check that Obsidian opened the notes folder, that notes exist, and that meaningful links were saved. |
| Permission denied or a folder is invisible to the AI | Check the exact path and the agent's environment. Do not bypass this with `sudo`, broad access, or `chmod 777`. |

It is fine to ask an AI for help with an error. Share the relevant error text
after removing names, private paths, account details, tokens, and confidential
content. Do not paste your whole configuration, chat history, or terminal log.
If a command failed, ask what caused it before trying a suggested repair.

If you lose track of your location, `pwd` shows Terminal's current folder and
`ls` lists its contents. Those names may be private; check before sharing
their output. To interrupt a running command, usually press Control-C. This
does not guarantee that any files already written will be restored, so check
what changed before trying again.

For a reproducible problem with the tool, open a
[GitHub issue](https://github.com/nennchakki/portable-agent-brain/issues).
Include your operating system, Python version, tool version, steps taken, and
a sanitized error. GitHub issues here are public; do not attach your library.

## 12. A few words you will see

| Word | Meaning here |
| --- | --- |
| Repository, or repo | A folder of project files with Git history; this public one contains the software. |
| Terminal | The app where you enter written commands. |
| Command | A line asking the computer to perform an operation, such as `./brain setup`. |
| Markdown | A readable text format for notes, usually saved in `.md` files. |
| Library / vault | Your notes folder. “Library” is this tool's term; “vault” is Obsidian's. |
| Path | A file or folder's location. A full path identifies it without depending on the current folder. |
| Home folder / `~` | Your user folder. `~` is a short way to refer to it in a terminal. |
| Project / slug | A group of related work / its short identifier, such as `my-website`. |
| Adapter / gateway | The shared instruction file that connects an AI to this workflow, not a server. |
| JSON | A structured text format the AI uses to submit summaries. You do not need to write it by hand. |
| Candidate / pending | A saved note that is waiting for human review. |
| Commit / push | Record a version in local Git history / send commits to a remote destination. |

This guide was checked against command-line version `0.1.0` and the
`feat/initial-public-release` preview on **2026-09-05**. For command options
and file formats, continue with [Getting started](getting-started.md),
[Agent integration](agent-integration.md), and [Saving notes](automatic-capture.md).
