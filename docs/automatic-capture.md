# Automatic capture

Automatic capture preserves useful task knowledge without turning every agent
message into permanent memory.

## The loop

```text
finish and verify a task
  -> decide whether the result is reusable
  -> create a bounded structured summary
  -> reject secrets and transcript-shaped input
  -> check duplicates and active conflicts
  -> save or reinforce a pending candidate
  -> retrieve later with candidate authority
  -> human review
```

Capture is a review-queue writer. It is not a canonical knowledge editor.

## What is worth capturing

Capture only information likely to change a future decision or approach:

- a verified fact about a project;
- a user preference or explicit constraint;
- a failure, its established cause, and a verified correction;
- a repeatable procedure with a verification step;
- the context and rationale of a decision candidate.

Do not capture a task merely because it completed. Normally skip:

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

Automatic extraction must reject permanent rules, principles, universal
protocols, and skills. Those require deliberate human authorship and review.

If a task does not map uniquely to a registered project, do not store
project-specific claims under another project. Use the shared scope only for
knowledge that genuinely applies unchanged across projects.

## Output contract

A newly saved note lives under `inbox/candidates/` and is visibly unapproved:

```yaml
candidate: true
authority: candidate
review_status: pending
status: pending
evidence_count: 1
```

The note records provenance, the relevant project when known, and typed links
only to existing canonical nodes. It is excluded from canonical graph counts.

The command may instead return a no-knowledge result. That is a normal outcome,
not an error.

## Duplicate suppression and reinforcement

Before writing, capture compares candidates within the same project or shared
scope and type.

- An equivalent candidate does not create another file.
- Repeating the same task summary does not increase evidence.
- A genuinely independent task that confirms the same finding may update
  `evidence_count` and `last_observed`.
- Reinforcement does not make the candidate canonical.

Use a content fingerprint to identify equivalent knowledge and an observation
signature to distinguish independent evidence from a repeated submission.
Neither value is a user identity or session identifier.

## Conflicts

When a candidate may contradict an active decision, capture records a
`conflicts_with` relation and a warning. It must not decide that the natural
language statements are logically incompatible, and it must not merge,
supersede, or edit the active decision.

During retrieval, show the conflicting active knowledge first and identify the
candidate as unverified. Current project source and active reviewed knowledge
win until human review.

## Promotion proposals

Repetition can justify review, not automatic promotion. Conservative defaults
include:

- a lesson independently observed at least four times can receive a rule-review
  proposal;
- a procedure independently confirmed at least three times can receive a
  skill-distillation review proposal.

Counts alone never approve the proposal. A reviewer still checks scope,
evidence, conflicts, and whether the current project source has changed.

## Secret and privacy boundary

Before persistence, inspect both encoded input and decoded strings for
credential-like material, private keys, authorization values, environment-file
paths, raw session identifiers, and telemetry identifiers. Reject the complete
submission without echoing the detected value.

Candidate writes should be bounded, UTF-8, exclusive, and protected against
symlink, hardlink, and overwrite attacks. Runtime counters, if enabled, remain
outside the knowledge graph and never contain task text.

## Agent completion receipt

An adapter may ask an agent to end a completed task with one receipt:

```text
<!-- brain-capture:v1 saved|duplicate|reinforced|none|error -->
```

The receipt reports the decision; it is not knowledge. A safe stop hook checks
only for this marker and prompts the same agent once if it is missing. It never
reads or saves the raw transcript and never performs capture itself.

See [Agent integration](agent-integration.md) for installation boundaries and
[Privacy](privacy.md) for storage and remote considerations.
