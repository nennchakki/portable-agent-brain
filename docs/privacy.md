# Privacy and release safety

Portable Agent Brain is local-first. A new library is empty, core operation does
not require a hosted service, and a Git remote is optional.

Local-first is a storage property, not a promise about every connected agent.
When an agent receives retrieved knowledge, that agent's provider may process
the selected text under its own terms and account settings. Retrieve only what
the task needs and review the provider's data controls.

## Data boundaries

The public engine repository may contain:

- CLI and validation code;
- schemas and empty library templates;
- thin agent adapters;
- documentation;
- clearly isolated, wholly fictional examples and test fixtures.

It must not contain:

- a user's real projects, lessons, decisions, preferences, or candidates;
- conversations, session histories, work logs, or migration reports;
- runtime metrics, caches, backups, or local state;
- private repository addresses or private infrastructure details;
- personal absolute paths, identity data, or email addresses;
- credentials, authentication material, environment files, or certificates.

The public distribution is built by copying reviewed generic source files into
an independent public repository. Never publish a sanitized clone of a private
knowledge repository, and never import its Git history.

## Local storage

By default, keep the knowledge library in a separate local directory with
permissions appropriate for personal data. The public engine checkout and the
private library should have different Git boundaries.

Templates and `.gitignore` reduce accidental additions but are not a security
boundary. Review staged files and repository status before every commit.

## Optional Git remote

Portable Agent Brain supports local-only use. If you want backup or multi-device
synchronization, initialize the knowledge library as its own repository and use
a private remote under your control.

Before the first push:

1. Confirm the remote is private.
2. Inspect the remote URL and staged file list.
3. Run secret scanning against the working tree and history.
4. Check that cache, candidate-export, backup, and environment files are ignored.
5. Understand the host's retention and collaborator policies.

Changing a remote from public to private does not undo prior disclosure.

## Capture privacy

Capture accepts a short structured task summary, not a transcript. Store only
new findings, user corrections, verified failed approaches, verified successful
approaches, and explicit reusable candidates.

Input is rejected when it resembles a credential, authorization value, private
key, raw session identifier, or telemetry record. Diagnostics must identify the
class of problem without printing the value.

Candidate files remain private user data. They are low-authority for retrieval,
but low authority does not mean low sensitivity.

## Optional history-mining plan

In version 0.1, `--history-source` only enables a local review plan. Setup
validates the explicitly selected path but does not open, parse, copy, or import
its contents. A future miner must remain opt-in and produce minimal structured
candidates rather than copied messages.

Do not place source exports, raw chat archives, migration reports, or mining
work files in either the public distribution or canonical knowledge graph.

## Release safety check

Before committing a public release, `brain release-check` or an equivalent
validator should fail on:

- personal project or identity markers from an explicitly provided external denylist;
- private absolute paths and private remote addresses;
- a non-empty live candidate inbox;
- runtime metrics, caches, backups, or local configuration;
- secret-like values and credential files;
- broken templates, schemas, or documentation links;
- Git remotes or history that connect the public project to a private source.

The check should scan tracked and untracked release files. Before the initial
release, also inspect every commit and reachable object in the public history.
Any necessary public owner or repository identifier must be narrowly allowlisted
and reported as an explicit exception.

Never embed real personal names in the scanner or its test fixtures, including
split strings or encoded copies. Keep an optional JSON array of private markers
outside the public checkout and pass its path explicitly:

```sh
brain release-check --denylist /private/release-markers.json
```

The file is read locally and is never copied into the distribution. Diagnostics
do not print matched markers. Without `--denylist`, generic secret, path,
candidate, runtime, remote, and history checks still run, but organization-
specific markers are not checked. The JSON report records whether the external
marker check ran. Pattern scans are not a semantic personal-data detector.

Automated pattern matching produces false positives and cannot identify every
semantic leak. Pair it with manual review of examples, comments, tests, and Git
history. A renamed real project is still personal data and is not a valid
fixture.

`brain release-check` scans the current directory, or the explicit `--root`
checkout. It rejects symlinks, opaque files, and text larger than its 1 MB review
limit rather than silently skipping them. It is a source-repository check;
packaged archives require a separate inspection of their members and metadata.

`uv build` uses a small local backend wrapper to normalize source-archive
UID/GID, owner/group names, timestamps, and extended metadata. This avoids
shipping the local builder's account identity in tar headers. The wrapper does
not change Setuptools licensing or add a runtime dependency.

## If a secret is detected

1. Stop publication and do not print or paste the value into an issue.
2. Revoke or rotate the credential at its provider.
3. Remove it from the working tree and reachable Git history.
4. Re-run the safety checks from a clean clone.
5. Review logs, artifacts, and mirrors for additional copies.

Deleting the current file is not enough after a value has entered Git history.

## Telemetry and derived views

The public distribution contains no user runtime metrics. If a future optional
local metric is enabled, keep it outside the graph, exclude task text and
identifiers, and never treat it as evidence for automatic promotion.

Markdown is the source of truth. Optional HTML, indexes, caches, and graph views
are derived data and should be reproducible, disposable, and excluded from
commits unless they are intentionally reviewed public documentation.
