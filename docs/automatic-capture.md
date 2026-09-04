# Saving notes after a task

English | [日本語](automatic-capture.ja.md)

After a task, an agent can save useful findings as notes for human review.
This process, called capture in some command output, does not save every message.

## How saving works

```text
finish and verify a task
  -> decide whether the result is reusable
  -> create a bounded structured summary
  -> reject secrets and transcript-shaped input
  -> check duplicates and active conflicts
  -> save a note awaiting review, or add independent supporting evidence
  -> find it in later searches, marked as not yet reviewed
  -> human review
```

The tool writes only to the folder for notes awaiting review. It does not edit
approved notes.

## What is worth saving

Save only information likely to change a future decision or approach:

- a verified fact about a project;
- a user preference or explicit constraint;
- a failure, its established cause, and a verified correction;
- a repeatable procedure with a verification step;
- a proposed decision, why it was suggested, and when it would apply.

Do not save a note about a task merely because it completed. Normally skip:

- typo fixes;
- simple renames;
- one-line deterministic changes;
- formatting-only work;
- running a build or test without a new finding;
- acknowledgements, progress messages, and lists of changed files.

A failed task may still produce a valuable lesson if the failure and evidence
are clear. An unverified guess should remain an observation or be omitted.

## Structured input

`brain learn-extract` accepts one bounded JSON object. It does not accept a raw
conversation or tool transcript.

```json
{
  "project": "sample-weather-cli",
  "task_type": "debugging",
  "task": "Prevent stale synthetic weather records from being displayed",
  "outcome": "success",
  "new_findings": [
    "Cached records need an explicit capture time before age can be validated."
  ],
  "user_corrections": [],
  "failed_approaches": [
    "Checking only that the cache file existed accepted stale records."
  ],
  "successful_approaches": [
    "Compare captured_at with the configured maximum age and test with a fixed clock."
  ],
  "reusable_knowledge": []
}
```

The project and task type in the JSON must match the CLI scope. Supported
outcomes are `success`, `partial`, `failure`, and `cancelled`. Text lists should
contain findings, not copied terminal output.

`reusable_knowledge` is optional. When present, each item must be one of:

- `fact`
- `preference`
- `constraint`
- `lesson`
- `procedure`
- `decision`

Automatic extraction accepts only the six note types listed above. Other types,
including `project-rule`, `principle`, `protocol`, and `skill`, must be written
and reviewed by a person. Saving a finding does not make it an instruction for
future tasks.

If a task does not map uniquely to a registered project, do not store
project-specific claims under another project. Use the shared scope only for
knowledge that genuinely applies unchanged across projects.

## What gets saved

A newly saved note lives under `inbox/candidates/` and is visibly unapproved:

```yaml
candidate: true
authority: candidate
review_status: pending
status: pending
evidence_count: 1
```

The note records where the finding came from, its project when known, and links
only to existing notes. A link to another note awaiting review does not approve
either note. Notes in the review folder are excluded from the main graph's counts.

The command may instead return a no-knowledge result. That is a normal outcome,
not an error.

## Avoid duplicates and record independent confirmations

Before writing, the tool compares notes of the same type within the same
project, or among notes that apply across projects.

- An equivalent note does not create another file.
- Repeating the same task summary does not increase evidence.
- A genuinely independent task that confirms the same finding may update
  `evidence_count` and `last_observed`.
- Additional evidence does not approve the note. Some output calls this
  update `reinforced`; it still requires human review.

Use a content fingerprint to identify equivalent knowledge and an observation
signature to distinguish independent evidence from a repeated submission.
Neither value is a user identity or session identifier.

## Conflicts

When a new note may contradict a decision that is in use, the tool records a
`conflicts_with` relation and a warning. It must not decide that the natural
language statements are logically incompatible, and it must not combine, replace,
or edit the existing decision.

During search, show the existing decision first and mark the new note as
unverified. Current project source and reviewed instructions take priority
until a person checks the disagreement.

## Suggestions for human review

Repeated independent findings can prompt a person to review whether a note
should become a working instruction. They cannot approve that change. By default:

- any note awaiting review that was independently observed at least four times
  can prompt a review of whether it should become approved working knowledge;
- a procedure independently confirmed at least three times can prompt a review
  of whether it should become a reusable agent skill.

Counts alone never approve a change. A reviewer still checks scope,
evidence, conflicts, and whether the current project source has changed.

## Protect private data before saving

Before saving, inspect both encoded input and decoded strings for
credential-like material, private keys, authorization values, environment-file
paths, raw session identifiers, and telemetry identifiers. Reject the complete
submission without echoing the detected value.

Writes to the review folder should be size-limited, UTF-8, exclusive, and protected
against symlink, hardlink, and overwrite attacks. Runtime counters, if enabled, remain
outside the knowledge graph and never contain task text.

## Task-end result marker

The shared instruction file may ask an agent to end a task with one result marker:

```text
<!-- brain-capture:v1 saved|duplicate|reinforced|none|error -->
```

The marker reports whether a note was saved; it is not part of the saved notes.
A safe stop hook checks only for this marker and prompts the same agent once if it is missing. It never
reads or saves the raw transcript and never saves notes itself.

See [Agent integration](agent-integration.md) for installation boundaries and
[Privacy](privacy.md) for storage and remote considerations.
