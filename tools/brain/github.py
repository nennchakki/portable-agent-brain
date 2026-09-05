"""Explicit private GitHub connections and review-bound, fast-forward pushes.

GitHub CLI owns authentication. This module never creates credentials, commits,
repositories on GitHub, or background jobs. Local search has no dependency on it.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

from tools.validate import secret_path_kind

from .catalog import BrainError
from .learn import reject_sensitive

MAX_TEXT = 1_000_000
MAX_COMMITS = 200
MAX_BLOBS = 2000
MAX_SCAN_BYTES = 20_000_000
SLUG = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9_.-]{1,100}\Z")
REMOTE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")
OID = re.compile(r"[0-9a-f]{40}(?:[0-9a-f]{24})?\Z")
RUNTIME_PARTS = {".cache", ".obsidian", ".venv", "__pycache__", "node_modules"}


class GitHubError(BrainError):
    """A sanitized failure that must prevent connection or transmission."""


@dataclass(frozen=True)
class Repository:
    """The identity and canonical URL verified by GitHub."""

    repository_id: int
    full_name: str

    @property
    def url(self) -> str:
        """Return the sole supported transport endpoint."""
        return f"https://github.com/{self.full_name}.git"


@dataclass(frozen=True)
class Connection:
    """A private repository binding stored only in local Git configuration."""

    library: str
    remote: str
    repository: Repository
    initialized: bool = False


@dataclass(frozen=True)
class PushPlan:
    """All reviewed commits and their exact destination, without saved state."""

    connection: Connection
    branch: str
    head: str
    remote_head: str | None
    commits: tuple[str, ...]
    files: tuple[str, ...]
    patch: str
    approval: str
    pushed: bool = False


def repository_slug(value: str) -> str:
    """Parse an owner/repository or standard GitHub URL without echoing input."""
    slug = value.removeprefix("https://github.com/")
    slug = slug.removesuffix(".git")
    if not SLUG.fullmatch(slug) or slug.split("/")[1] in {".", ".."}:
        raise GitHubError("Use owner/repository or an HTTPS github.com repository URL")
    return slug


def remote_repository_slug(value: str) -> str:
    """Require a real GitHub URL where a configured Git remote is expected."""
    if not value.startswith("https://github.com/"):
        raise GitHubError("Managed remotes must use an HTTPS github.com repository URL")
    return repository_slug(value)


def _executable(name: str) -> str:
    """Resolve an installed command without invoking a shell."""
    path = shutil.which(name)
    if path is None:
        raise GitHubError(f"{name} is required for GitHub operations")
    return os.path.abspath(path)


def _environment() -> dict[str, str]:
    """Keep authentication available while disabling Git redirects and tracing."""
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("GIT_") and key not in {"GH_DEBUG", "GH_HOST", "GH_REPO"}
    }
    environment.update(
        GIT_CONFIG_NOSYSTEM="1",
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_TERMINAL_PROMPT="0",
        GIT_NO_REPLACE_OBJECTS="1",
        GH_PROMPT_DISABLED="1",
    )
    return environment


def _run(arguments: list[str], *, timeout: int = 30) -> subprocess.CompletedProcess[bytes]:
    """Run a command with private captured output and no interactive input."""
    try:
        with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
            result = subprocess.run(
                arguments,
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
                check=False,
                timeout=timeout,
                env=_environment(),
            )
            stdout.seek(0)
            stderr.seek(0)
            return subprocess.CompletedProcess(
                arguments, result.returncode, stdout.read(MAX_TEXT + 1), stderr.read(4096)
            )
    except (OSError, subprocess.TimeoutExpired):
        raise GitHubError(
            "GitHub operation failed or timed out; check remote status before retrying"
        ) from None


def _text(raw: bytes, *, limit: int = MAX_TEXT) -> str:
    """Decode a bounded text result without disclosing malformed content."""
    if len(raw) > limit:
        raise GitHubError("Review limit exceeded; split the change before sending")
    try:
        value = raw.decode("utf-8")
    except UnicodeError:
        raise GitHubError("This version supports UTF-8 text notes only") from None
    if any(ord(char) < 32 and char not in "\n\r\t" or ord(char) == 127 for char in value):
        raise GitHubError("Unsupported control characters in Git content")
    return value


def verify_repository(value: str) -> Repository:
    """Require a private, writable github.com repository using current credentials.

    Args:
        value: Owner/repository or a supported GitHub URL.

    Returns:
        Canonical repository identity, freshly obtained from GitHub.

    Raises:
        GitHubError: If privacy, identity, or write permission cannot be verified.
    """
    slug = repository_slug(value)
    result = _run(
        [
            _executable("gh"),
            "api",
            "--hostname",
            "github.com",
            "--method",
            "GET",
            f"repos/{slug}",
            "--jq",
            "{id,full_name,private,visibility,archived,disabled,push:.permissions.push}",
        ]
    )
    if result.returncode:
        raise GitHubError("Cannot verify repository; check gh authentication, access, and network")
    try:
        data = json.loads(_text(result.stdout, limit=16_384))
    except (ValueError, TypeError):
        raise GitHubError("GitHub returned invalid repository metadata") from None
    if not isinstance(data, dict):
        raise GitHubError("GitHub returned invalid repository metadata")
    if data.get("private") is not True or data.get("visibility") != "private":
        raise GitHubError("Only private GitHub repositories can be connected or sent notes")
    if (
        data.get("push") is not True
        or data.get("archived") is not False
        or data.get("disabled") is not False
    ):
        raise GitHubError("A writable, active private GitHub repository is required")
    identifier, full_name = data.get("id"), data.get("full_name")
    if type(identifier) is not int or identifier <= 0 or not isinstance(full_name, str):
        raise GitHubError("GitHub returned invalid repository identity")
    if repository_slug(full_name).casefold() != slug.casefold():
        raise GitHubError("Repository was renamed or transferred; reconnect using its current name")
    return Repository(identifier, full_name)


def _git(root: Path, *arguments: str, checked: bool = True) -> subprocess.CompletedProcess[bytes]:
    """Run a local Git command in the explicit library, ignoring inherited redirects."""
    result = _run([_executable("git"), "--no-pager", "-C", str(root), *arguments])
    if checked and result.returncode:
        raise GitHubError("Local Git operation failed; existing notes and commits were preserved")
    return result


def _root(library: Path, *, require_git: bool = True) -> Path:
    """Require an external, non-symlink library and an ordinary Git boundary."""
    if library.is_symlink() or not library.is_dir():
        raise GitHubError("Library must be an existing directory, not a symlink")
    root = library.resolve()
    engine = Path(__file__).resolve().parents[2]
    if root.resolve().is_relative_to(engine):
        raise GitHubError("Notes folder must be outside the public engine checkout")
    marker = root / ".git"
    if marker.is_symlink() or marker.exists() and not marker.is_dir():
        raise GitHubError("Managed GitHub sync requires a standalone Git repository")
    top = _git(root, "rev-parse", "--show-toplevel", checked=False)
    if top.returncode:
        if require_git or marker.exists():
            raise GitHubError("Initialize local Git before using this command")
    elif Path(_text(top.stdout).strip()).resolve() != root.resolve():
        raise GitHubError("Library must have its own Git boundary, outside an ancestor repository")
    return root


def _remote_name(remote: str) -> str:
    """Restrict remote names so config keys cannot be injected."""
    if not REMOTE.fullmatch(remote):
        raise GitHubError("Invalid Git remote name")
    return remote


def _config(root: Path, key: str) -> tuple[str, ...]:
    """Read all effective local values; ambiguous bindings are rejected by callers."""
    result = _git(root, "config", "--includes", "--get-all", key, checked=False)
    if result.returncode not in {0, 1}:
        raise GitHubError("Git configuration could not be inspected")
    return tuple(_text(result.stdout).splitlines())


def _check_transport(root: Path, remote: str, repository: Repository, *, new: bool = False) -> None:
    """Reject alternate push URLs, URL rewrites, and ambiguous destinations."""
    rewrites = _git(
        root,
        "config",
        "--includes",
        "--get-regexp",
        r"^url\..*\.(insteadof|pushinsteadof)$",
        checked=False,
    )
    if rewrites.returncode != 1:
        raise GitHubError("Remove local Git URL rewrite rules before using managed GitHub sync")
    overrides = _git(
        root, "config", "--includes", "--get-regexp", r"^(http|credential)\.", checked=False
    )
    if overrides.returncode != 1:
        raise GitHubError(
            "Local HTTP or credential overrides are unsupported; sync uses gh authentication"
        )
    for key in ("url", "pushurl"):
        values = _config(root, f"remote.{remote}.{key}")
        if key == "url" and not values and new:
            continue
        if key == "url" and len(values) != 1 or key == "pushurl" and len(values) > 1:
            raise GitHubError("A single GitHub destination is required")
        for value in values:
            if remote_repository_slug(value).casefold() != repository.full_name.casefold():
                raise GitHubError("Git destination changed; reconnect after reviewing the remote")


def connect(library: Path, value: str, remote: str = "origin") -> Connection:
    """Verify private access before initializing or recording any connection.

    Args:
        library: Existing, external notes directory.
        value: Desired owner/repository or supported GitHub URL.
        remote: Local remote name to bind without replacing an existing target.

    Returns:
        The verified connection. No note content has been sent.
    """
    _remote_name(remote)
    root = _root(library, require_git=False)
    repository = verify_repository(value)
    initialized = not (root / ".git").exists()
    if not initialized:
        _check_transport(root, remote, repository, new=True)
        pinned = _config(root, f"remote.{remote}.brainRepositoryId")
        if pinned and pinned != (str(repository.repository_id),):
            raise GitHubError("Repository identity changed; the existing binding was preserved")
    if initialized:
        _git(root, "init", "--template=", "-b", "main")
    if not _config(root, f"remote.{remote}.url"):
        _git(root, "remote", "add", remote, repository.url)
    _check_transport(root, remote, repository)
    _git(
        root,
        "config",
        "--local",
        f"remote.{remote}.brainRepositoryId",
        str(repository.repository_id),
    )
    return Connection(str(root), remote, repository, initialized)


def connection_status(library: Path, remote: str = "origin") -> Connection:
    """Verify the pinned identity, current privacy, and actual configured target."""
    _remote_name(remote)
    root = _root(library)
    urls = _config(root, f"remote.{remote}.url")
    pinned = _config(root, f"remote.{remote}.brainRepositoryId")
    if len(urls) != 1 or len(pinned) != 1 or not pinned[0].isdigit():
        raise GitHubError("No verified connection; run brain github connect first")
    repository = verify_repository(remote_repository_slug(urls[0]))
    if pinned != (str(repository.repository_id),):
        raise GitHubError("Repository identity changed; sending was refused")
    _check_transport(root, remote, repository)
    return Connection(str(root), remote, repository)


def _network_git(
    root: Path, repository: Repository, *arguments: str
) -> subprocess.CompletedProcess[bytes]:
    """Use canonical HTTPS, gh credentials, TLS, and no redirects or implicit refs."""
    helper = "!" + shlex.quote(_executable("gh")) + " auth git-credential"
    result = _run(
        [
            _executable("git"),
            "--no-pager",
            "-C",
            str(root),
            "-c",
            "credential.helper=",
            "-c",
            "credential.https://github.com.helper=",
            "-c",
            f"credential.https://github.com.helper={helper}",
            "-c",
            "http.followRedirects=false",
            "-c",
            "http.sslVerify=true",
            "-c",
            "push.followTags=false",
            "-c",
            "push.recurseSubmodules=no",
            *arguments,
        ],
        timeout=60,
    )
    if result.returncode:
        raise GitHubError(
            "GitHub Git operation failed; inspect status before retrying, no force push was used"
        )
    return result


def _remote_head(root: Path, repository: Repository, ref: str) -> str | None:
    """Read only the destination branch, without fetching or changing local refs."""
    result = _network_git(root, repository, "ls-remote", "--refs", repository.url, ref)
    lines = _text(result.stdout).splitlines()
    if not lines:
        return None
    if len(lines) != 1:
        raise GitHubError("Ambiguous remote branch")
    parts = lines[0].split("\t")
    if len(parts) != 2 or parts[1] != ref or not OID.fullmatch(parts[0]):
        raise GitHubError("Invalid remote branch metadata")
    return parts[0]


def _scan_commits(root: Path, commits: tuple[str, ...]) -> tuple[tuple[str, ...], str]:
    """Scan every outgoing snapshot and message, including content later deleted."""
    files: set[str] = set()
    scanned: set[str] = set()
    total = 0
    patches: list[str] = []
    for commit in commits:
        reject_sensitive(_text(_git(root, "cat-file", "commit", commit).stdout))
        patch = _text(
            _git(
                root,
                "show",
                "--format=fuller",
                "--root",
                "--first-parent",
                "--no-ext-diff",
                "--no-textconv",
                "--no-renames",
                "--text",
                commit,
                "--",
            ).stdout
        )
        reject_sensitive(patch)
        patches.append(patch)
        if sum(len(item.encode("utf-8")) for item in patches) > MAX_TEXT:
            raise GitHubError("Review limit exceeded; split the change before sending")
        tree = _git(root, "ls-tree", "-r", "-z", commit).stdout
        if len(tree) > MAX_TEXT:
            raise GitHubError("Too many tracked files to review safely")
        for entry in tree.split(b"\0"):
            if not entry:
                continue
            meta, raw_path = entry.split(b"\t", 1)
            mode, kind, raw_oid = meta.split()
            path = _text(raw_path)
            if (
                any(ord(char) < 32 for char in path)
                or path.startswith("/")
                or any(part in {"", ".", ".."} for part in path.split("/"))
            ):
                raise GitHubError("Unsupported filename in outgoing history")
            if mode not in {b"100644", b"100755"} or kind != b"blob":
                raise GitHubError("Symlinks and submodules are not supported by managed sync")
            parts = Path(path).parts
            if (
                secret_path_kind(Path(path))
                or RUNTIME_PARTS.intersection(parts)
                or Path(path).suffix in {".db", ".sqlite", ".sqlite3", ".log"}
            ):
                raise GitHubError(
                    "Secret or runtime file found in outgoing history (path withheld)"
                )
            files.add(path)
            oid = raw_oid.decode("ascii")
            if oid in scanned:
                continue
            scanned.add(oid)
            if len(scanned) > MAX_BLOBS:
                raise GitHubError("Too many note versions to review safely")
            size = int(_git(root, "cat-file", "-s", oid).stdout)
            total += size
            if size > MAX_TEXT or total > MAX_SCAN_BYTES:
                raise GitHubError("Note history exceeds the safe review size limit")
            reject_sensitive(_text(_git(root, "cat-file", "blob", oid).stdout))
    return tuple(sorted(files)), "\n".join(patches)


def prepare_push(library: Path, remote: str = "origin") -> PushPlan:
    """Build a reviewable, deterministic plan without sending note contents."""
    connection = connection_status(library, remote)
    root = Path(connection.library)
    if _git(root, "status", "--porcelain", "--untracked-files=all").stdout:
        raise GitHubError(
            "Review and commit local changes first; this command does not create commits"
        )
    if _text(_git(root, "rev-parse", "--is-shallow-repository").stdout).strip() != "false":
        raise GitHubError("Full Git history is required for the outgoing content check")
    grafts = root / ".git/info/grafts"
    if grafts.exists() or grafts.is_symlink():
        raise GitHubError("Remove legacy Git grafts before reviewing outgoing history")
    branch_result = _git(root, "symbolic-ref", "--quiet", "HEAD", checked=False)
    if branch_result.returncode:
        raise GitHubError("Check out a local branch before preparing a push")
    ref = _text(branch_result.stdout).strip()
    if not ref.startswith("refs/heads/"):
        raise GitHubError("A local branch is required")
    head = _text(_git(root, "rev-parse", "--verify", "HEAD^{commit}").stdout).strip()
    if not OID.fullmatch(head):
        raise GitHubError("Invalid local commit identity")
    remote_head = _remote_head(root, connection.repository, ref)
    revisions = [head]
    if remote_head:
        ancestor = _git(root, "merge-base", "--is-ancestor", remote_head, head, checked=False)
        if ancestor.returncode:
            raise GitHubError(
                "Remote history is missing or diverged; fetch and reconcile it before sending"
            )
        revisions.append("^" + remote_head)
    commits = tuple(
        _text(
            _git(root, "rev-list", "--reverse", f"--max-count={MAX_COMMITS + 1}", *revisions).stdout
        ).splitlines()
    )
    if len(commits) > MAX_COMMITS:
        raise GitHubError("Too many outgoing commits; split the change before sending")
    files, patch = _scan_commits(root, commits)
    identity = {
        "connection": asdict(connection),
        "ref": ref,
        "head": head,
        "remote_head": remote_head,
        "commits": commits,
        "files": files,
        "patch_sha256": hashlib.sha256(patch.encode("utf-8")).hexdigest(),
    }
    approval = hashlib.sha256(json.dumps(identity, sort_keys=True).encode("utf-8")).hexdigest()
    return PushPlan(
        connection,
        ref.removeprefix("refs/heads/"),
        head,
        remote_head,
        commits,
        files,
        patch,
        approval,
    )


def push(library: Path, approval: str, remote: str = "origin") -> PushPlan:
    """Revalidate an approved plan and push only its explicit commit and branch.

    Args:
        library: External library with a verified private GitHub connection.
        approval: Digest returned by the preview the caller reviewed.
        remote: Bound destination remote name.

    Returns:
        The exact plan sent, or an unchanged plan when already up to date.

    Raises:
        GitHubError: On any changed plan, privacy failure, or failed transmission.
    """
    if not re.fullmatch(r"[0-9a-f]{64}", approval):
        raise GitHubError("Supply the approval value from a reviewed push preview")
    plan = prepare_push(library, remote)
    if plan.approval != approval:
        raise GitHubError("Push plan changed; review a new preview before sending")
    if not plan.commits:
        return plan
    current = connection_status(library, remote)
    if current != plan.connection:
        raise GitHubError("Connection changed after review; sending was refused")
    root = Path(plan.connection.library)
    ref = "refs/heads/" + plan.branch
    if _remote_head(root, current.repository, ref) != plan.remote_head:
        raise GitHubError("Remote branch changed after review; prepare a new preview")
    _network_git(
        root,
        current.repository,
        "push",
        "--porcelain",
        "--no-follow-tags",
        "--recurse-submodules=no",
        current.repository.url,
        f"{plan.head}:{ref}",
    )
    return PushPlan(
        plan.connection,
        plan.branch,
        plan.head,
        plan.remote_head,
        plan.commits,
        plan.files,
        plan.patch,
        plan.approval,
        True,
    )
