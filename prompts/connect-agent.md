# Connect this agent to Portable Agent Brain

English | [日本語](connect-agent.ja.md)

Use the following prompt once with an agent whose integration is not yet
documented. Replace the placeholders before sending it.

For setup and initial notes from past chats, use the
[setup prompt](setup-and-import.md) instead.

---

Inspect this agent's official, current mechanism for persistent user-level
instructions or rules. Connect Portable Agent Brain without copying any user
knowledge into that mechanism.

Inputs:

- Software directory: `<PORTABLE_AGENT_BRAIN_PATH>`
- Shared agent instruction file:
  `<PORTABLE_AGENT_BRAIN_PATH>/adapters/external-brain.md`
- Notes folder visible to this agent: `<BRAIN_LIBRARY_PATH>`

Requirements:

1. Confirm the effective global instruction mechanism and its precedence before
   editing. Do not assume it is the same as another agent's mechanism.
2. Preserve all existing instructions, hooks, permissions, model settings, and
   project-local rules. Make a recoverable backup before changing a file.
3. Prefer a supported external Markdown import. If imports are unavailable,
   add one clearly marked, minimal managed block that tells the agent when to
   read the shared instruction file. Do not duplicate the adapter body or any
   knowledge note.
4. Configure the library through `BRAIN_LIBRARY` or the CLI's `--library`
   option. Use the path visible inside this agent's runtime, container, or
   sandbox; do not assume the host home directory is visible.
5. Do not preload, index into the prompt, or recursively read the library.
   Retrieval must happen only for tasks where prior knowledge can affect the
   result.
6. If this agent supports a safe task-end hook, propose a hook that checks only
   for the Portable Agent Brain task-end result marker and prompts the same
   agent once when the marker is missing. The hook must not read or store transcripts,
   call another model, or write knowledge directly. Do not install a hook
   without showing the exact change.
7. Running setup again must not add duplicate settings: no second import,
   managed block, or hook.
8. Verify in a fresh session that a knowledge-dependent task can use bounded
   `brain context`, while an obvious typo task skips retrieval. Confirm that no
   knowledge or unrelated global settings changed.
9. Report the exact files changed, backup location, verification result, and
   precise rollback steps. If the official global mechanism cannot be
   established, stop and explain the unresolved point instead of guessing.

Do not alter the Portable Agent Brain engine, the knowledge library, or an
existing project merely to make the connection easier.

---
