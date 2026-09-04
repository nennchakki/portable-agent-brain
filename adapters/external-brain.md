# External Brain

- The persistent source of truth is the user-owned library selected by
  `BRAIN_LIBRARY` or `--library`. Do not copy knowledge into agent instructions
  and do not preload or recursively read the library.
- Use `brain context --project <slug> "<task>"` only when prior project
  knowledge, decisions, lessons, or procedures could change the result. Skip it
  for clear typos, simple renames, and other deterministic trivial work.
- Prefer current project source, then active canonical rules and decisions,
  verified knowledge, observed knowledge, and candidates in that order.
  Treat every candidate as unreviewed and inspect conflict warnings.
- Before finishing a meaningful task, decide whether it produced new reusable
  knowledge. If so, send only a short structured summary to
  `brain learn-extract`; never send a raw conversation, tool log, session ID,
  telemetry, credential, or unrelated source content.
- Do not store project-specific claims when the project is unregistered or
  ambiguous. Use shared scope only for knowledge that truly applies unchanged
  across projects.
- Capture writes pending candidates only. Never automatically approve, merge,
  supersede, commit, or promote a candidate to a canonical decision, permanent
  rule, principle, universal protocol, or skill.
- End with exactly one result receipt when the integration requests it:
  `<!-- brain-capture:v1 saved|duplicate|reinforced|none|error -->`.
