# External Brain

- The original notes are in the user-owned folder selected by
  `BRAIN_LIBRARY` or `--library`. Do not copy knowledge into agent instructions
  and do not preload or recursively read the library.
- Use `brain context --project <slug> "<task>"` only when prior project
  knowledge, decisions, lessons, or procedures could change the result. Skip it
  for clear typos, simple renames, and other deterministic trivial work.
- Prefer current project source, then reviewed instructions and decisions still
  in use, checked notes, observations, and notes awaiting review, in that order.
  Treat unreviewed notes as reference only and inspect warnings about disagreements.
- Before finishing a meaningful task, decide whether it produced new reusable
  knowledge. If so, send only a short structured summary to
  `brain learn-extract`; never send a raw conversation, tool log, session ID,
  telemetry, credential, or unrelated source content.
- Do not store project-specific claims when the project is unregistered or
  ambiguous. Use shared scope only for knowledge that truly applies unchanged
  across projects.
- Save new notes only as drafts awaiting human review. Never automatically
  approve them, combine them with existing notes, replace existing notes, or
  commit them to Git. Do not turn them into decisions, instructions for future
  work, or agent skills without human review.
- End with exactly one result marker when the integration requests it:
  `<!-- brain-capture:v1 saved|duplicate|reinforced|none|error -->`.
