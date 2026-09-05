# Save notes to a private GitHub repository

English | [日本語](github-sync.ja.md) | [Documentation](README.md)

Use your own GitHub account and an existing private repository with any name.
The public software checkout and your notes must remain separate Git repositories.
Local search and note saving still work without GitHub, GitHub CLI, or a network.

## Commands at a glance

| Command | What it does | Sends note contents? |
| --- | --- | --- |
| `brain github connect --repo OWNER/REPO` | Verifies private access and records the destination. | No |
| `brain github status` | Rechecks the destination's privacy, identity, and write access. | No |
| `brain github push` | Displays the outgoing commits and their changes for review. | No |
| `brain github push --approve DIGEST` | Rechecks and sends the exact plan identified by the preview. | Yes, if there are outgoing commits |

Add `--library /absolute/path/to/notes` to select the notes folder explicitly.
All four commands support `--remote NAME` and `--json`. In the final command,
replace `DIGEST` with the approval value from the preview; running the complete
command printed by the preview also selects the same engine and notes folder.

If you run directly from a source checkout, use `./brain` there, or the absolute
path to that checkout's `brain` after changing directories. Use `brain` only when
it resolves to this installation. See [installation and setup](getting-started.md).

## Connect

Install Git and [GitHub CLI](https://cli.github.com/), then authenticate using
`gh auth login --hostname github.com`. Authentication is managed by GitHub CLI;
Brain does not store a token in your notes or print authentication output.
Create a private repository in GitHub first, or choose an existing private
repository to which your account can push. Brain does not create a GitHub repository.
For a new backup, an empty destination avoids unrelated Git histories.

The examples use a fictional `example-owner/my-notes`; replace it with your own.

```sh
brain github connect --library "$HOME/agent-library" --repo example-owner/my-notes
brain github status --library "$HOME/agent-library"
```

The notes directory must already exist (`brain init` can create it). Connection
initializes local Git on branch `main` if needed, adds `origin` if absent, and
records the verified repository ID under `remote.origin.brainRepositoryId` in
local Git configuration. It preserves existing commits and refuses to replace
a different remote or repository identity. `--remote backup` selects another name.
Connection sends no note contents. `status` checks private access again online.

`setup --git-mode remote --remote-url https://github.com/example-owner/my-notes.git`
uses the same private verification. This is a change from the initial 0.1.0
behavior, which only registered a URL. Existing unverified remotes must be bound
with `github connect` before a managed push. Modes `none`, `local`, and `existing`
preserve their local behavior and do not authorize a managed push.

Only `github.com` over HTTPS is supported in this version. Public, internal,
archived, disabled, or non-writable repositories are refused. Authentication,
network, or malformed API responses also stop the operation. A failed check
does not prevent local note saving.

## Review and send

First review your files and make the intended local commits. The tool does not
stage files, commit, pull, merge, or force-push. A dirty worktree, including
untracked notes, stops a preview so uncommitted knowledge is not silently omitted.

```sh
cd "$HOME/agent-library"
git status --short
git diff
# Stage only the intended files, inspect git diff --cached, then commit.
brain github push --library "$HOME/agent-library"
```

The command above is a **preview**, not a push. It reads the remote branch's ID,
checks every outgoing commit and its file snapshots, and displays the commit IDs,
reviewed file list, full textual patch, and a command containing `--approve`.
The file list includes unchanged files inspected in those snapshots; the patch
shows the changes. Review commit metadata and contents, then run the displayed
command to send that exact plan. `--json` returns the complete structured plan.

The approval digest binds the library, remote, repository ID, branch, local and
remote commit IDs, and reviewed content. It is a change-detection receipt, not an
authentication secret or proof that a human read the preview. Callers and agents
must obtain the user's authorization before sending the reviewed contents.

Approval rechecks privacy, access, repository identity, and the plan. Any change
requires a fresh preview. Only the current local branch's pinned commit is sent
to the same branch name on GitHub; unrelated branches and tags are not pushed.
If already up to date, nothing is sent. Push does not set a branch upstream.

## When an operation stops

| Result | Next step |
| --- | --- |
| Private access cannot be verified | Check `gh` login, repository visibility, permissions, and network; local notes remain usable. |
| No verified connection | Use `github connect` to validate and bind the existing destination. |
| Local changes remain | Review and commit the intended files, then preview again. |
| Remote history is missing or diverged | Fetch the chosen remote and reconcile its history deliberately; the tool does not resolve conflicts or overwrite the remote. |
| Plan changed | Read a new preview and use its new approval value. |
| Remote URL or repository ID changed | Inspect your remote configuration and the repository's current identity before reconnecting. |
| Unsupported Git configuration | Local URL rewrites and HTTP/credential overrides are refused. Review their purpose; do not delete settings blindly. |
| A send fails or times out | Check the remote branch and run a new preview. The server may have accepted a push before the response was lost. |

## Scope and limits

- Full ordinary Git repositories only; shallow clones, linked worktrees, legacy
  grafts, symlinks, and submodules are refused.
- UTF-8 text notes only: at most 1,000,000 bytes per blob and displayed review,
  200 outgoing commits, 2,000 distinct blobs, and 20,000,000 scanned blob bytes.
  Oversized histories need a smaller reviewed scope; no content is silently skipped.
- The scan includes intermediate versions later removed from the final snapshot,
  commit metadata, common credential patterns, and credential/runtime filenames.
  It is not a complete personal-information detector; private notes still need review.
- Network Git uses the canonical HTTPS endpoint, GitHub CLI credentials, TLS
  verification, and no HTTP redirects. System/global Git configuration and
  inherited `GIT_*` overrides are excluded from these managed operations.
  This version refuses local URL rewrites and local HTTP/credential overrides.
  It does not modify your global Git settings.
- The private check and Git push are separate requests. Visibility can change
  between them, or the owner can make an existing backup public later. The tool
  cannot guarantee permanent privacy or govern direct Git operations and other
  applications. It does not install a pre-push hook or a background monitor.

An existing public remote is never silently changed to private. Changing visibility
cannot undo an earlier disclosure. See [privacy boundaries](privacy.md).

API and Git behavior: [repository metadata](https://docs.github.com/en/rest/repos/repos#get-a-repository),
[GitHub CLI authentication](https://cli.github.com/manual/gh_auth_login),
[Git push](https://git-scm.com/docs/git-push).
