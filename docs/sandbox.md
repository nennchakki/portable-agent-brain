# Sandbox and read-only deployments

Portable Agent Brain must work when an agent has a different home directory,
runs in a container, or can read only part of the host filesystem.

## Use a path the agent can access

Configure the library from inside the agent environment:

```sh
export BRAIN_LIBRARY="/brain"
brain context --project sample-weather-cli "inspect cache behavior"
```

You can also set a path for one command:

```sh
brain context --library /mnt/agent-library \
  --project sample-weather-cli \
  "inspect cache behavior"
```

An explicit `--library` value takes precedence over `BRAIN_LIBRARY` and a saved
setup default.

Do not assume that the host's `$HOME` matches the agent's `$HOME`. Do not pass a
host path that does not exist in the sandbox.

## Host library to sandbox mount

For read-only retrieval, mount the host library at a stable sandbox path:

```text
host:    <host-library-directory>
            |
            | read-only bind mount
            v
sandbox: /brain
```

A container runtime invocation may look like:

```sh
docker run --rm \
  --mount type=bind,src="${BRAIN_LIBRARY}",dst=/brain,readonly \
  -e BRAIN_LIBRARY=/brain \
  <agent-image>
```

The host variable is expanded by the host shell. The value given to the agent
is `/brain`, which exists inside the container.

With a read-only mount, `search` and `context` can work. Operations that create
or change notes must fail safely without leaving partial writes.

## Avoid inaccessible symlinks

A symlink visible inside a sandbox may point to a host path that is not mounted.
Prefer mounting the real library directory. If symlinks are required, mount
both the link and its target and verify the resolved path inside the agent
environment.

Input files and folders for new notes should not be symlinks. Saving must fail
if the destination is ambiguous or redirected.

## Protect existing notes and allow new drafts

You can keep reviewed notes read-only while allowing writes only to the folder
for notes awaiting review:

```text
/brain/                         read-only reviewed notes
├── projects/
├── lessons/
├── decisions/
├── preferences/
├── procedures/
├── concepts/
└── inbox/
    └── candidates/            separate writable mount
```

Where nested mounts are supported, mount the library read-only and then mount a
private writable directory over `/brain/inbox/candidates`:

```sh
docker run --rm \
  --mount type=bind,src="${BRAIN_LIBRARY}",dst=/brain,readonly \
  --mount type=bind,src="${BRAIN_CANDIDATES_HOST}",dst=/brain/inbox/candidates \
  -e BRAIN_LIBRARY=/brain \
  <agent-image>
```

`BRAIN_CANDIDATES_HOST` in this example is a host-shell variable, not a Portable
Agent Brain configuration variable.

This layout is a supported design target. A release that does not yet expose a
separate candidate-directory setting still requires `inbox/candidates/` to be
writable beneath the configured library root. Verify the exact mount behavior
before allowing automatic note saving. Read-only search remains supported.

## Permissions

- Give the agent read access only to knowledge needed for its work.
- Keep the folder for unreviewed notes private to the user account or container user.
- Do not mount credential stores or unrelated home directories for convenience.
- Keep lock and temporary files on the same protected writable filesystem as
  the folder for unreviewed notes.
- Reject world-writable or redirected paths for new notes when safety cannot be
  established.

## Installing adapters in a sandbox

Host-level agent instructions and sandbox-level instructions are different
surfaces. Run setup in the environment that owns the target instruction file,
and ensure that the adapter path written there is visible in future sessions.

If the public engine checkout is not mounted into the sandbox, install a
reviewed copy of the small adapter in a stable readable location. Do not copy
the knowledge library into global instructions.

## Verification checklist

From inside the final agent environment, verify:

1. `BRAIN_LIBRARY` resolves to the mounted directory.
2. `brain search` and `brain context` cannot escape the library root.
3. Broken or out-of-root wikilinks are rejected.
4. Read-only operations do not create cache or telemetry files in the library.
5. Saving either writes only to the writable review folder or fails safely.
6. The adapter does not instruct the agent to preload the vault.
