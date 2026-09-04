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
git clone https://github.com/nennchakki/portable-agent-brain.git
cd portable-agent-brain
./brain setup
```

Answer the prompts to choose where to keep your knowledge and which agents to
connect. Claude Code and Codex can be set up here. For other agents, see the
[integration guide](docs/agent-integration.md).

You start with an empty library. Short summaries of completed work become
knowledge candidates; later tasks retrieve only the relevant notes.

## A few things worth knowing

- Knowledge stays in a separate local folder. This public repository contains
  none of my personal knowledge or conversation history.
- A Git remote is optional. Use a private repository if you want a backup.
- New knowledge is saved for review, not automatically promoted to permanent rules.
- **Automatic import of past conversations is not implemented.** Even
  `--history-source` only returns guidance; it does not read the history.

When you need the details, see [Getting started](docs/getting-started.md),
[Knowledge capture](docs/automatic-capture.md), and [Privacy](docs/privacy.md).

Questions and bugs can go in [Issues](https://github.com/nennchakki/portable-agent-brain/issues).
Please don't paste secrets or actual conversation logs there.

[MIT License](LICENSE)
