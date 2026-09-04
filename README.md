# Portable Agent Brain

English | [日本語](README.ja.md)

Even while using Hermes-agent, I keep trying different AIs and moving between
them. Losing the knowledge I'd built up each time I switched was frustrating,
so I made this.

I want to try another AI without starting that part over. This keeps knowledge
in Markdown files outside the agent, so the next agent can read it too.

## Just get started

You're probably not going to read a long explanation anyway, so start with this.
You'll need macOS or Linux and Python 3.11 or newer.

```sh
git clone --branch feat/initial-public-release https://github.com/nennchakki/portable-agent-brain.git
cd portable-agent-brain
./brain setup
```

Answer the prompts to choose where to keep your knowledge and which agents to
connect. Claude Code and Codex can be set up here. For other agents, see the
[integration guide](docs/agent-integration.md).

Want an AI to handle setup and make linked notes from selected past chats?
Give it [this setup prompt](prompts/setup-and-import.md).

You start with an empty notes folder. Save short notes about what you learned,
and let the next AI read only the notes relevant to its work.

![Linked notes in Obsidian's graph view](docs/images/obsidian-graph.png)

An example with existing notes in Obsidian. A new library starts empty.

## A few things worth knowing

- Knowledge stays in a separate local folder. This public repository contains
  none of my personal knowledge or conversation history.
- Git synchronization is optional. Use a private repository if you want a backup.
- Saved notes are for reference until a person reviews them. The AI does not
  turn them into rules for future work on its own.
- The CLI does not import past conversations. `--history-source` only returns
  guidance. With the prompt above, the AI reads and summarizes history you approve.

New to terminals or setting up software? Read the [detailed beginner guide](docs/guide.md)
([日本語](docs/guide.ja.md)). For technical details, see [Getting started](docs/getting-started.md),
[Saving notes](docs/automatic-capture.md), and [Privacy](docs/privacy.md).

Questions and bugs can go in [Issues](https://github.com/nennchakki/portable-agent-brain/issues).
Please don't paste secrets or actual conversation logs there.

[MIT License](LICENSE)
