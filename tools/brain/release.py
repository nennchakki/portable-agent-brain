"""Run local-only release safety checks for the public engine repository."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

from tools.validate import run_checks, secret_path_kind

MAX_RELEASE_TEXT_BYTES = 1_000_000
REVIEWED_IMAGE_PATH = "docs/images/obsidian-graph.png"
REVIEWED_IMAGE_BYTES = 331_532
REVIEWED_IMAGE_SHA256 = "87e8df83f3c2e905addc134eaa4311f540178e46dd513d94507ca64cfb8504d8"
PUBLIC_BASELINE_COMMIT = "51c6ed3608c1eeb791066b97cba8bbc63c38a878"
HistoryBlobPaths = dict[str, set[tuple[str, str]]]
LIVE_LIBRARY_FOLDERS = frozenset(
    {
        "projects",
        "lessons",
        "decisions",
        "preferences",
        "procedures",
        "concepts",
        "principles",
        "protocols",
        "references",
        "skills",
        "profiles",
        "inbox",
    }
)


@dataclass(frozen=True)
class ReleaseFinding:
    """One sanitized release diagnostic."""

    level: str
    check: str
    path: str
    message: str


def load_denylist(path: Path | None, root: Path) -> tuple[str, ...]:
    """Read optional personal markers from a private file outside the release.

    Args:
        path: External JSON array of denied text markers, or None.
        root: Public checkout that must not contain the private marker file.

    Returns:
        Unique, case-folded markers without publishing them in diagnostics.

    Raises:
        ValueError: If the file is unsafe, unreadable, or malformed.
    """
    if path is None:
        return ()
    selected = path.expanduser()
    if selected.is_symlink() or selected.resolve().is_relative_to(root.resolve()):
        raise ValueError("denylist must be a regular file outside the release checkout")
    descriptor = -1
    try:
        descriptor = os.open(selected, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > 65_536:
            raise ValueError
        with os.fdopen(descriptor, "rb") as source:
            descriptor = -1
            raw = source.read(65_537)
        if len(raw) > 65_536:
            raise ValueError
        value = json.loads(raw)
        if not isinstance(value, list) or not 1 <= len(value) <= 1000:
            raise ValueError
        if any(not isinstance(item, str) or not 2 <= len(item.strip()) <= 256 for item in value):
            raise ValueError
        return tuple(sorted({item.strip().casefold() for item in value}))
    except (OSError, UnicodeError, ValueError) as exc:
        raise ValueError("denylist must be a readable JSON array of bounded text markers") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _owner() -> str:
    """Return the repository owner allowed only in distribution references."""
    return "nenn" + "chakki"


def _run_git(root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    """Run a bounded local Git query without invoking a shell."""
    return subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )


def _run_git_bytes(root: Path, *arguments: str) -> subprocess.CompletedProcess[bytes]:
    """Run a bounded local Git query and preserve arbitrary blob bytes."""
    return subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=False,
        capture_output=True,
        timeout=20,
    )


def _release_bytes(path: Path) -> bytes | None:
    """Read a bounded regular release file without following a final symlink."""
    descriptor = -1
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > MAX_RELEASE_TEXT_BYTES:
            return None
        with os.fdopen(descriptor, "rb") as source:
            descriptor = -1
            content = source.read(MAX_RELEASE_TEXT_BYTES + 1)
        return content if len(content) <= MAX_RELEASE_TEXT_BYTES else None
    except OSError:
        return None
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _reviewed_image_finding(
    path: str, content: bytes, *, history: bool = False, mode: str = "100644"
) -> ReleaseFinding | None:
    """Allow only the exact image reviewed visually and for embedded metadata.

    Args:
        path: Exact release-relative path; aliases receive no exception.
        content: Bounded bytes from a regular file or reachable Git blob.
        history: Whether to label the finding as a Git-history exception.
        mode: Git tree mode; only ordinary non-executable image files qualify.

    Returns:
        An explicit review warning, a mismatch error, or None for other paths.
    """
    if path != REVIEWED_IMAGE_PATH:
        return None
    check = "git-history-reviewed-image" if history else "reviewed-image"
    if (
        mode != "100644"
        or len(content) != REVIEWED_IMAGE_BYTES
        or hashlib.sha256(content).hexdigest() != REVIEWED_IMAGE_SHA256
    ):
        return ReleaseFinding(
            "error",
            check,
            path,
            "image does not match the reviewed path, size, SHA-256, or file mode",
        )
    return ReleaseFinding(
        "warning",
        check,
        path,
        "exact reviewed image allowed; binary contents rely on prior visual and metadata "
        "review, not automated text privacy scanning",
    )


def _release_files(root: Path) -> list[Path]:
    """List regular files and symlinks while retaining unsafe local artifacts."""
    result: list[Path] = []
    ignored = {".git", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache", "dist", "build"}
    for current, folders, filenames in os.walk(root, followlinks=False):
        directory = Path(current)
        for name in sorted(folders):
            path = directory / name
            if path.is_symlink():
                result.append(path)
        folders[:] = sorted(
            name
            for name in folders
            if name not in ignored
            and not name.endswith(".egg-info")
            and not (directory / name).is_symlink()
        )
        for name in sorted(filenames):
            path = directory / name
            if path.is_symlink() or path.is_file():
                result.append(path)
    return result


def _owner_line_allowed(path: str, line: str) -> bool:
    """Allow the public owner only in its repository URL and MIT notice."""
    owner = _owner()
    repository = f"github.com/{owner}/portable-agent-brain"
    return repository in line or (path == "LICENSE" and "Copyright" in line and owner in line)


def _scan_tree(root: Path, denied_terms: tuple[str, ...]) -> list[ReleaseFinding]:
    """Scan paths and text without returning matched private or secret values."""
    findings: list[ReleaseFinding] = []
    home_prefix = "/" + "Users" + "/"
    windows_home = re.compile(r"(?i)\b[A-Z]:\\Users\\[^\\\s]+")
    email = re.compile(r"(?i)(?<![A-Z0-9._%+-])[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}(?![A-Z0-9.-])")
    secrets = (
        ("private key block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
        ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
        ("provider token", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
        ("JWT", re.compile(r"\beyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")),
        (
            "assigned credential literal",
            re.compile(
                r"(?i)\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|passwd|client[_-]?secret|authorization)\b\s*[:=]\s*[\"']?[A-Za-z0-9+/_.=-]{12,}"
            ),
        ),
    )
    terms = tuple(value.casefold() for value in denied_terms)
    owner = _owner().casefold()
    forbidden_parts = {"migration", ".brain-runtime", ".cache", "backups"}
    forbidden_suffixes = {".db", ".sqlite", ".p12", ".pfx", ".pem", ".key"}
    for path in _release_files(root):
        relative = path.relative_to(root).as_posix()
        lowered_path = relative.casefold()
        private_path = any(term in lowered_path for term in terms)
        display_path = "<redacted-path>" if private_path else relative
        if path.is_symlink():
            findings.append(
                ReleaseFinding(
                    "error",
                    "symlink",
                    display_path,
                    "release content must not depend on a filesystem symlink",
                )
            )
            continue
        parts = set(path.relative_to(root).parts)
        if path.relative_to(root).parts[0] in LIVE_LIBRARY_FOLDERS:
            findings.append(
                ReleaseFinding(
                    "error",
                    "live-knowledge",
                    display_path,
                    "live Library data belongs outside the public engine checkout",
                )
            )
        if (
            parts & forbidden_parts
            or path.suffix.casefold() in forbidden_suffixes
            or path.name.endswith((".bak", ".backup", "~"))
            or ".portable-agent-brain-" in path.name
        ):
            findings.append(
                ReleaseFinding(
                    "error",
                    "runtime-data",
                    display_path,
                    "runtime, backup, or private-state artifact is not publishable",
                )
            )
        kind = secret_path_kind(path)
        if kind:
            findings.append(ReleaseFinding("error", "secret-file", display_path, kind))
        if "inbox/candidates/" in relative and relative != (
            "templates/library/inbox/candidates/.gitkeep"
        ):
            findings.append(
                ReleaseFinding(
                    "error",
                    "candidate-data",
                    display_path,
                    "candidate Knowledge must not ship in the engine repository",
                )
            )
        if private_path:
            findings.append(
                ReleaseFinding(
                    "error",
                    "personal-path",
                    display_path,
                    "path contains a denied private identifier",
                )
            )
        try:
            metadata = path.stat()
            size = metadata.st_size
        except OSError:
            size = MAX_RELEASE_TEXT_BYTES + 1
        if size > MAX_RELEASE_TEXT_BYTES:
            findings.append(
                ReleaseFinding(
                    "error",
                    "oversized-file",
                    display_path,
                    "file exceeds the release scanner's 1 MB review limit",
                )
            )
            continue
        raw = _release_bytes(path)
        mode = "100755" if metadata.st_mode & stat.S_IXUSR else "100644"
        image_finding = (
            _reviewed_image_finding(relative, raw, mode=mode) if raw is not None else None
        )
        if image_finding is not None:
            findings.append(image_finding)
            continue
        try:
            content = raw.decode("utf-8") if raw is not None and b"\x00" not in raw else None
        except UnicodeError:
            content = None
        if content is None:
            findings.append(
                ReleaseFinding(
                    "error",
                    "unreadable-file",
                    display_path,
                    "release file is not readable UTF-8 text",
                )
            )
            continue
        for number, line in enumerate(content.splitlines(), 1):
            lowered = line.casefold()
            if any(term in lowered for term in terms):
                findings.append(
                    ReleaseFinding(
                        "error",
                        "personal-content",
                        display_path,
                        f"line {number}: denied private identifier",
                    )
                )
            if owner in lowered and not _owner_line_allowed(relative, line):
                findings.append(
                    ReleaseFinding(
                        "error",
                        "owner-allowlist",
                        display_path,
                        (
                            f"line {number}: repository owner used outside an allowed "
                            "distribution reference"
                        ),
                    )
                )
            if home_prefix in line or windows_home.search(line):
                findings.append(
                    ReleaseFinding(
                        "error",
                        "absolute-home-path",
                        display_path,
                        f"line {number}: private home path",
                    )
                )
            if email.search(line):
                findings.append(
                    ReleaseFinding(
                        "error",
                        "email",
                        display_path,
                        f"line {number}: email address is not required in public source",
                    )
                )
            for label, pattern in secrets:
                if pattern.search(line):
                    findings.append(
                        ReleaseFinding(
                            "error", "secret-content", display_path, f"line {number}: {label}"
                        )
                    )
    return findings


def _scan_repository_shape(root: Path, denied_terms: tuple[str, ...]) -> list[ReleaseFinding]:
    """Check executable mode, templates, schemas, and independent Git ancestry."""
    findings: list[ReleaseFinding] = []
    required = (
        "README.md",
        "LICENSE",
        "brain",
        "pyproject.toml",
        "adapters/external-brain.md",
        "prompts/connect-agent.md",
        "templates/library",
        "schemas/knowledge-node.schema.json",
        "docs/privacy.md",
    )
    for relative in required:
        if not (root / relative).exists():
            findings.append(
                ReleaseFinding(
                    "error", "distribution-shape", relative, "required release artifact is missing"
                )
            )
    executable = root / "brain"
    if executable.is_file() and not executable.stat().st_mode & stat.S_IXUSR:
        findings.append(
            ReleaseFinding("error", "file-mode", "brain", "CLI entrypoint is not executable")
        )
    schemas = root / "schemas"
    if schemas.is_dir():
        for path in sorted(schemas.glob("*.json")):
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(value, dict):
                    raise ValueError
            except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
                findings.append(
                    ReleaseFinding(
                        "error",
                        "schema",
                        path.relative_to(root).as_posix(),
                        "invalid JSON schema document",
                    )
                )
    templates = root / "templates" / "library"
    for relative in (
        "projects",
        "lessons",
        "decisions",
        "preferences",
        "procedures",
        "concepts",
        "inbox/candidates",
    ):
        if not (templates / relative).is_dir():
            findings.append(
                ReleaseFinding(
                    "error",
                    "template",
                    f"templates/library/{relative}",
                    "empty-library directory is missing",
                )
            )
    library_findings, _graph = run_checks(root)
    for item in library_findings:
        if item.check == "links" and item.level == "error":
            findings.append(ReleaseFinding("error", "links", item.path, item.message))
    git_dir = _run_git(root, "rev-parse", "--is-inside-work-tree")
    if git_dir.returncode or git_dir.stdout.strip() != "true":
        return findings + [
            ReleaseFinding(
                "error", "git-history", ".git", "release root is not an independent Git repository"
            )
        ]
    roots = _run_git(root, "rev-list", "--max-parents=0", "--all")
    root_commits = [line for line in roots.stdout.splitlines() if line]
    if roots.returncode or len(root_commits) != 1:
        findings.append(
            ReleaseFinding(
                "error", "git-history", ".git", "repository must have exactly one root history"
            )
        )
    remotes = _run_git(root, "remote", "-v")
    lowered_remotes = remotes.stdout.casefold()
    if any(term.casefold() in lowered_remotes for term in denied_terms):
        findings.append(
            ReleaseFinding(
                "error",
                "git-remote",
                ".git/config",
                "remote refers to denied private infrastructure",
            )
        )
    public_repository = f"github.com/{_owner()}/portable-agent-brain"
    remote_secret = re.compile(
        r"gh[pousr]_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9_-]{20,}|"
        r"https?://[^/\s:@]+:[^/\s@]+@"
    )
    for line in remotes.stdout.splitlines():
        fields = line.split()
        if len(fields) < 2:
            continue
        if remote_secret.search(fields[1]):
            findings.append(
                ReleaseFinding(
                    "error",
                    "git-remote-secret",
                    ".git/config",
                    "remote contains embedded credential-like material",
                )
            )
        if public_repository not in fields[1].casefold():
            findings.append(
                ReleaseFinding(
                    "error",
                    "git-remote",
                    ".git/config",
                    "remote does not identify this public distribution",
                )
            )
    dirty = _run_git(root, "status", "--porcelain")
    if dirty.stdout.strip():
        findings.append(
            ReleaseFinding("warning", "git-state", ".", "working tree is not committed")
        )
    return findings


def _history_path_findings(
    path: str, mode: str, denied_terms: tuple[str, ...]
) -> list[ReleaseFinding]:
    """Reject private-state paths and symlinks from any reachable tree."""
    findings: list[ReleaseFinding] = []
    lowered = path.casefold()
    private_path = any(term.casefold() in lowered for term in denied_terms)
    display_path = "<redacted-path>" if private_path else path
    parts = set(Path(path).parts)
    if Path(path).parts and Path(path).parts[0] in LIVE_LIBRARY_FOLDERS:
        findings.append(
            ReleaseFinding(
                "error",
                "git-history-live-knowledge",
                display_path,
                "reachable history contains live Library data",
            )
        )
    if mode == "120000":
        findings.append(
            ReleaseFinding(
                "error",
                "git-history-symlink",
                display_path,
                "reachable history contains a filesystem symlink",
            )
        )
    kind = secret_path_kind(Path(path))
    if kind:
        findings.append(ReleaseFinding("error", "git-history-secret-file", display_path, kind))
    if private_path:
        findings.append(
            ReleaseFinding(
                "error",
                "git-history-path",
                display_path,
                "reachable history contains a denied private identifier in a path",
            )
        )
    if (
        parts & {"migration", ".brain-runtime", ".cache", "backups"}
        or ".portable-agent-brain-" in Path(path).name
        or Path(path).suffix.casefold() in {".db", ".sqlite", ".p12", ".pfx", ".pem", ".key"}
        or Path(path).name.endswith((".bak", ".backup", "~"))
    ):
        findings.append(
            ReleaseFinding(
                "error",
                "git-history-runtime",
                display_path,
                "reachable history contains runtime, backup, or private-state data",
            )
        )
    if "inbox/candidates/" in lowered and path != ("templates/library/inbox/candidates/.gitkeep"):
        findings.append(
            ReleaseFinding(
                "error",
                "git-history-candidate",
                display_path,
                "reachable history contains candidate Knowledge",
            )
        )
    return findings


def _history_blob_findings(
    root: Path, denied_terms: tuple[str, ...], blob_paths: HistoryBlobPaths
) -> list[ReleaseFinding]:
    """Scan each reachable named blob, including files deleted from later commits."""
    findings: list[ReleaseFinding] = []
    objects = _run_git(root, "rev-list", "--objects", "--all")
    if objects.returncode:
        return [
            ReleaseFinding("error", "git-history", ".git", "unable to enumerate reachable objects")
        ]
    email = re.compile(
        r"(?i)(?<![A-Z0-9._%+-])[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}"
        r"(?![A-Z0-9.-])"
    )
    windows_home = re.compile(r"(?i)\b[A-Z]:\\Users\\[^\\\s]+")
    secret_patterns = (
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
        re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
        re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
        re.compile(r"\beyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
        re.compile(
            r"(?i)\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|"
            r"passwd|client[_-]?secret|authorization)\b\s*[:=]\s*[\"']?"
            r"[A-Za-z0-9+/_.=-]{12,}"
        ),
    )
    terms = tuple(term.casefold() for term in denied_terms)
    owner = _owner().casefold()
    references: set[tuple[str, str, str]] = set()
    for line in objects.stdout.splitlines():
        object_id, _separator, path = line.partition(" ")
        if path:
            continue
        kind = _run_git(root, "cat-file", "-t", object_id)
        if not kind.returncode and kind.stdout.strip() == "tree":
            findings.extend(_history_tree_findings(root, object_id, denied_terms, blob_paths))
    for line in objects.stdout.splitlines():
        object_id, _separator, path = line.partition(" ")
        if object_id in blob_paths:
            references.update((object_id, name, mode) for name, mode in blob_paths[object_id])
        if object_id not in blob_paths or not path:
            references.add((object_id, path or "<unnamed-blob>", ""))
    for object_id, path, mode in sorted(references):
        if not object_id:
            continue
        kind = _run_git(root, "cat-file", "-t", object_id)
        if kind.returncode or kind.stdout.strip() != "blob":
            continue
        private_path = any(term in path.casefold() for term in terms)
        display_path = "<redacted-path>" if private_path else path
        size_result = _run_git(root, "cat-file", "-s", object_id)
        try:
            size = int(size_result.stdout.strip()) if not size_result.returncode else -1
        except ValueError:
            size = -1
        if size < 0 or size > MAX_RELEASE_TEXT_BYTES:
            findings.append(
                ReleaseFinding(
                    "error",
                    "git-history-oversized",
                    display_path,
                    "reachable blob cannot be scanned within the 1 MB review limit",
                )
            )
            continue
        blob = _run_git_bytes(root, "cat-file", "blob", object_id)
        if blob.returncode:
            findings.append(
                ReleaseFinding(
                    "error",
                    "git-history-unreadable",
                    display_path,
                    "reachable blob could not be read",
                )
            )
            continue
        image_finding = _reviewed_image_finding(path, blob.stdout, history=True, mode=mode)
        if image_finding is not None:
            findings.append(image_finding)
            continue
        try:
            content = blob.stdout.decode("utf-8")
        except UnicodeError:
            content = ""
        if (not content and blob.stdout) or b"\x00" in blob.stdout:
            findings.append(
                ReleaseFinding(
                    "error",
                    "git-history-unreadable",
                    display_path,
                    "reachable blob is not UTF-8 text",
                )
            )
            continue
        for number, text in enumerate(content.splitlines(), 1):
            lowered = text.casefold()
            if any(term in lowered for term in terms):
                findings.append(
                    ReleaseFinding(
                        "error",
                        "git-history-content",
                        display_path,
                        f"line {number}: denied private identifier",
                    )
                )
            if owner in lowered and not _owner_line_allowed(path, text):
                findings.append(
                    ReleaseFinding(
                        "error",
                        "git-history-owner",
                        display_path,
                        f"line {number}: repository owner outside the allowlist",
                    )
                )
            home_prefix = "/" + "Users" + "/"
            if home_prefix in text or windows_home.search(text):
                findings.append(
                    ReleaseFinding(
                        "error",
                        "git-history-home-path",
                        display_path,
                        f"line {number}: private home path",
                    )
                )
            if email.search(text):
                findings.append(
                    ReleaseFinding(
                        "error",
                        "git-history-email",
                        display_path,
                        f"line {number}: email address in a reachable blob",
                    )
                )
            if any(pattern.search(text) for pattern in secret_patterns):
                findings.append(
                    ReleaseFinding(
                        "error",
                        "git-history-secret",
                        display_path,
                        f"line {number}: secret-like material",
                    )
                )
    return findings


def _identity_is_private(text: str, denied_terms: tuple[str, ...]) -> bool:
    """Return whether commit identity fields contain non-public metadata."""
    lowered = text.casefold()
    if any(term.casefold() in lowered for term in denied_terms):
        return True
    home_prefix = "/" + "Users" + "/"
    if home_prefix in text or re.search(r"(?i)\b[A-Z]:\\Users\\[^\\\s]+", text):
        return True
    addresses = re.findall(
        r"(?i)(?<![A-Z0-9._%+-])[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}"
        r"(?![A-Z0-9.-])",
        text,
    )
    return any(
        not address.casefold().endswith(("@users.noreply.github.com", "@example.invalid"))
        for address in addresses
    )


def _free_metadata_is_sensitive(text: str, denied_terms: tuple[str, ...]) -> bool:
    """Return whether a commit message or tag annotation contains private data."""
    lowered = text.casefold()
    if any(term.casefold() in lowered for term in denied_terms):
        return True
    home_pattern = r"/" + "Users" + r"/[^/\s]+"
    patterns = (
        home_pattern,
        r"(?i)\b[A-Z]:\\Users\\[^\\\s]+",
        r"(?i)(?<![A-Z0-9._%+-])[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}",
        r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
        r"\bgh[pousr]_[A-Za-z0-9]{20,}\b",
        r"\bsk-[A-Za-z0-9_-]{20,}\b",
        r"\beyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b",
        (
            r"(?i)\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|passwd|"
            r"client[_-]?secret|authorization)\b\s*[:=]\s*[\"']?[A-Za-z0-9+/_.=-]{12,}"
        ),
    )
    return any(re.search(pattern, text) for pattern in patterns)


def _history_tree_findings(
    root: Path, revision: str, denied_terms: tuple[str, ...], blob_paths: HistoryBlobPaths
) -> list[ReleaseFinding]:
    """Check one reachable tree and retain every blob path, including tag-only trees."""
    tree = _run_git_bytes(root, "ls-tree", "-rz", revision)
    if tree.returncode:
        return [
            ReleaseFinding(
                "error", "git-history", revision[:12], "unable to inspect a reachable tree"
            )
        ]
    findings: list[ReleaseFinding] = []
    for entry in tree.stdout.split(b"\x00"):
        if not entry:
            continue
        metadata_fields, separator, raw_path = entry.partition(b"\t")
        try:
            mode, kind, object_id = metadata_fields.decode("ascii").split()
            path = raw_path.decode("utf-8")
            if not separator:
                raise ValueError
        except (UnicodeError, ValueError):
            findings.append(
                ReleaseFinding(
                    "error", "git-history", revision[:12], "malformed reachable tree entry"
                )
            )
            continue
        findings.extend(_history_path_findings(path, mode, denied_terms))
        if kind == "blob":
            blob_paths.setdefault(object_id, set()).add((path, mode))
    return findings


def _scan_history(
    root: Path, denied_terms: tuple[str, ...], blob_paths: HistoryBlobPaths
) -> list[ReleaseFinding]:
    """Scan reachable blobs and disclose immutable baseline metadata exceptions."""
    findings: list[ReleaseFinding] = []
    revisions = _run_git(root, "rev-list", "--all")
    if revisions.returncode:
        return [
            ReleaseFinding("error", "git-history", ".git", "unable to enumerate reachable commits")
        ]
    roots = _run_git(root, "rev-list", "--max-parents=0", "--all")
    baseline = roots.stdout.splitlines()[0] if roots.stdout.splitlines() else ""
    for revision in [line for line in revisions.stdout.splitlines() if line]:
        metadata = _run_git(root, "show", "-s", "--format=%an%n%ae%n%cn%n%ce", revision).stdout
        if _identity_is_private(metadata, denied_terms):
            if revision == baseline == PUBLIC_BASELINE_COMMIT:
                findings.append(
                    ReleaseFinding(
                        "warning",
                        "baseline-metadata",
                        baseline[:12],
                        (
                            "pre-existing public root commit contains legacy author metadata; "
                            "history was preserved as required"
                        ),
                    )
                )
            else:
                findings.append(
                    ReleaseFinding(
                        "error",
                        "git-history-metadata",
                        revision[:12],
                        "reachable non-baseline commit contains a denied private identifier",
                    )
                )
        message = _run_git(root, "show", "-s", "--format=%B", revision).stdout
        if _free_metadata_is_sensitive(message, denied_terms):
            findings.append(
                ReleaseFinding(
                    "error",
                    "git-history-message",
                    revision[:12],
                    "reachable commit message contains private or secret-like metadata",
                )
            )
        findings.extend(_history_tree_findings(root, revision, denied_terms, blob_paths))
    tags = _run_git(root, "tag", "--list")
    for tag in tags.stdout.splitlines():
        annotation = _run_git(
            root, "for-each-ref", "--format=%(contents)", f"refs/tags/{tag}"
        ).stdout
        identity = _run_git(
            root,
            "for-each-ref",
            "--format=%(taggername)%0a%(taggeremail)",
            f"refs/tags/{tag}",
        ).stdout
        if _free_metadata_is_sensitive(
            tag + "\n" + annotation, denied_terms
        ) or _identity_is_private(identity, denied_terms):
            findings.append(
                ReleaseFinding(
                    "error",
                    "git-history-tag",
                    "<redacted-tag>",
                    "reachable tag name or annotation contains private or secret-like metadata",
                )
            )
    return findings


def release_check(root: Path, *, denied_terms: tuple[str, ...] = ()) -> dict[str, object]:
    """Return a deterministic release report; no data leaves the machine."""
    selected = root.expanduser()
    root_findings: list[ReleaseFinding] = []
    if selected.is_symlink():
        root_findings.append(
            ReleaseFinding(
                "error",
                "release-root",
                os.fspath(selected),
                "release root must not be a symlink",
            )
        )
    resolved = selected.resolve()
    blob_paths: HistoryBlobPaths = {}
    history_findings = _scan_history(resolved, denied_terms, blob_paths)
    findings = [
        *root_findings,
        *_scan_tree(resolved, denied_terms),
        *_scan_repository_shape(resolved, denied_terms),
        *history_findings,
        *_history_blob_findings(resolved, denied_terms, blob_paths),
    ]
    for marker in denied_terms:
        if not marker:
            continue
        findings = [
            ReleaseFinding(
                item.level,
                item.check,
                re.sub(re.escape(marker), "<redacted>", item.path, flags=re.IGNORECASE),
                re.sub(re.escape(marker), "<redacted>", item.message, flags=re.IGNORECASE),
            )
            for item in findings
        ]
    unique = sorted(
        set(findings), key=lambda item: (item.level, item.check, item.path, item.message)
    )
    errors = sum(item.level == "error" for item in unique)
    warnings = sum(item.level == "warning" for item in unique)
    return {
        "ok": errors == 0,
        "errors": errors,
        "warnings": warnings,
        "findings": [asdict(item) for item in unique],
        "checks": {
            "working_tree_privacy": True,
            "external_personal_markers": bool(denied_terms),
            "secret_patterns": True,
            "candidate_and_runtime_data": True,
            "distribution_shape": True,
            "single_root_git_history": True,
            "reachable_history_content": True,
            "remote_privacy": True,
        },
    }


def main(argv: list[str] | None = None) -> int:
    """Run the release check as a standalone command."""
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--denylist", type=Path, help="private JSON marker list outside the checkout"
    )
    parser.add_argument("--json", action="store_true")
    arguments = parser.parse_args(argv)
    try:
        denied_terms = load_denylist(arguments.denylist, arguments.root)
    except ValueError as exc:
        parser.error(str(exc))
    report = release_check(arguments.root, denied_terms=denied_terms)
    if arguments.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for item in report["findings"]:
            print(f"{item['level'].upper()} [{item['check']}] {item['path']}: {item['message']}")
        print(f"Release check: {report['errors']} errors, {report['warnings']} warnings.")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
