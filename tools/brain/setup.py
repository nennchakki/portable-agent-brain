"""Safe, repeatable setup primitives for a portable External Brain."""

from __future__ import annotations

import json
import os
import re
import secrets
import shlex
import shutil
import stat
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, Literal
from urllib.parse import urlsplit

from .config import (
    CONFIG_VERSION,
    MAX_CONFIG_BYTES,
    ConfigError,
    default_config_path,
    normalize_path,
    resolve_library_path,
    save_user_config,
    user_home,
)

GitMode = Literal["none", "local", "existing", "remote"]
CliInstallMethod = Literal["auto", "symlink", "wrapper"]
AgentName = Literal["claude", "codex", "generic"]

KNOWLEDGE_DIRECTORIES: Final = (
    "projects",
    "lessons",
    "decisions",
    "preferences",
    "procedures",
    "concepts",
    "principles",
    "protocols",
    "references",
    "profiles",
    "skills",
    "inbox/candidates",
)
MANAGED_START: Final = "<!-- portable-agent-brain:start -->"
MANAGED_END: Final = "<!-- portable-agent-brain:end -->"
MAX_INSTRUCTION_BYTES: Final = 1024 * 1024


class SetupError(RuntimeError):
    """Raised when setup cannot safely preserve the user's existing state."""


@dataclass(frozen=True)
class LibraryInitResult:
    """Result of creating an empty user-owned Knowledge Library."""

    path: Path
    created: bool
    created_directories: tuple[str, ...]


@dataclass(frozen=True)
class GitSetupResult:
    """Result of configuring optional local Git state."""

    mode: GitMode
    initialized: bool
    remotes: tuple[tuple[str, str], ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class AgentInstallResult:
    """Result of one managed thin-adapter installation."""

    agent: AgentName
    target: Path
    changed: bool
    backup: Path | None
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class CliInstallResult:
    """Result of installing the stable ``brain`` command."""

    target: Path
    changed: bool
    method: Literal["symlink", "wrapper"]


@dataclass(frozen=True)
class HistoryMiningPlan:
    """Explicit, non-executing plan for optional history mining."""

    enabled: bool
    steps: tuple[str, ...]
    privacy_notice: str


@dataclass(frozen=True)
class SetupOptions:
    """Inputs for a non-interactive, caller-driven setup run."""

    library: str | os.PathLike[str] | None = None
    config_path: str | os.PathLike[str] | None = None
    home: str | os.PathLike[str] | None = None
    persist_config: bool = True
    git_mode: GitMode = "none"
    remote_url: str | None = None
    remote_name: str = "origin"
    agents: tuple[AgentName, ...] = ()
    adapter_path: str | os.PathLike[str] | None = None
    agent_targets: Mapping[str, str | os.PathLike[str]] | None = None
    use_codex_override: bool = False
    cli_entrypoint: str | os.PathLike[str] | None = None
    bin_dir: str | os.PathLike[str] | None = None
    cli_method: CliInstallMethod = "auto"
    history_mining: bool = False


@dataclass(frozen=True)
class SetupResult:
    """Complete result of a caller-driven setup run."""

    library: LibraryInitResult
    config_path: Path | None
    git: GitSetupResult
    agents: tuple[AgentInstallResult, ...]
    cli: CliInstallResult | None
    history: HistoryMiningPlan


@dataclass(frozen=True)
class _AgentInstallPlan:
    """Preflighted Agent file update and its exact original state."""

    agent: AgentName
    adapter: Path
    destination: Path
    existing: str
    mode: int | None
    desired: str
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class _CliInstallPlan:
    """Preflighted command target used to verify a scoped rollback."""

    source: Path
    target: Path
    wrapper: bytes
    target_existed: bool
    directory_existed: bool


@dataclass(frozen=True)
class _ConfigWritePlan:
    """Preflighted config update and its exact original state."""

    target: Path
    original: bytes | None
    mode: int
    desired: bytes


def _absolute_path(
    value: str | os.PathLike[str],
    *,
    home: str | os.PathLike[str] | None = None,
    environ: Mapping[str, str] | None = None,
) -> Path:
    """Return an absolute path while preserving a symlink at the final component.

    Args:
        value: Path value to normalize.
        home: Optional home override.
        environ: Optional environment mapping.

    Returns:
        An absolute path.
    """

    effective_home = user_home(home, environ=environ)
    return normalize_path(value, home=effective_home)


def _ensure_directory(path: Path, mode: int = 0o700) -> bool:
    """Create one directory without accepting a symlink in its place.

    Args:
        path: Directory to create.
        mode: Initial permission mode, subject to the process umask.

    Returns:
        ``True`` when the directory was created.

    Raises:
        SetupError: If the path is a symlink or another file type.
    """

    if path.is_symlink():
        raise SetupError(f"Refusing symlink directory: {path}")
    if path.exists():
        if not path.is_dir():
            raise SetupError(f"Expected a directory: {path}")
        return False
    try:
        path.mkdir(mode=mode, parents=True, exist_ok=False)
    except FileExistsError:
        if path.is_symlink() or not path.is_dir():
            raise SetupError(f"Directory path changed during setup: {path}") from None
        return False
    except OSError as error:
        raise SetupError(f"Could not create directory: {path}") from error
    if path.is_symlink():
        raise SetupError(f"Directory became a symlink during setup: {path}")
    return True


def _managed_component_paths(root: Path) -> tuple[Path, ...]:
    """Return every unique managed directory path below ``root``.

    Args:
        root: Knowledge Library root.

    Returns:
        Paths ordered from shallowest to deepest.
    """

    paths: set[Path] = set()
    for relative in KNOWLEDGE_DIRECTORIES:
        current = root
        for part in Path(relative).parts:
            current /= part
            paths.add(current)
    return tuple(sorted(paths, key=lambda item: (len(item.relative_to(root).parts), str(item))))


def _preflight_library(root: Path) -> set[Path]:
    """Validate existing managed components without creating anything.

    Args:
        root: Absolute Knowledge Library root.

    Returns:
        Existing managed directories, used for scoped rollback.

    Raises:
        SetupError: If the root or an existing managed component is redirected or
            has the wrong file type.
    """

    if root.is_symlink():
        raise SetupError("Refusing to initialize a symlink Library root")
    if root.exists() and not root.is_dir():
        raise SetupError(f"Expected a directory: {root}")
    existing: set[Path] = set()
    if not root.exists():
        return existing
    for path in _managed_component_paths(root):
        if path.is_symlink():
            raise SetupError(f"Refusing symlink directory: {path}")
        if path.exists():
            if not path.is_dir():
                raise SetupError(f"Expected a directory: {path}")
            existing.add(path)
    return existing


def _ensure_managed_directory(root: Path, relative: str, mode: int = 0o700) -> bool:
    """Create a managed descendant through no-follow directory descriptors.

    Args:
        root: Existing, non-symlink Library root.
        relative: Managed path below ``root``.
        mode: Initial permission mode, subject to the process umask.

    Returns:
        ``True`` when the final directory was created.

    Raises:
        SetupError: If any component is a symlink, non-directory, or changes
            during creation.
    """

    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptors: list[int] = []
    created_final = False
    try:
        directory = os.open(root, flags)
        descriptors.append(directory)
        parts = Path(relative).parts
        for index, name in enumerate(parts):
            created = False
            try:
                os.mkdir(name, mode=mode, dir_fd=directory)
                created = True
            except FileExistsError:
                pass
            child = os.open(name, flags, dir_fd=directory)
            descriptors.append(child)
            directory = child
            if index == len(parts) - 1:
                created_final = created
    except OSError as error:
        raise SetupError(
            f"Managed Library path is unsafe or unavailable: {root / relative}"
        ) from error
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)
    return created_final


def init_library(
    path: str | os.PathLike[str],
    *,
    home: str | os.PathLike[str] | None = None,
    environ: Mapping[str, str] | None = None,
) -> LibraryInitResult:
    """Create an empty, idempotent Knowledge Library directory structure.

    No Project, Lesson, Decision, candidate, or other Knowledge node is written.
    Templates remain in the public distribution and therefore cannot accidentally
    become canonical user Knowledge.

    Args:
        path: Library root to initialize.
        home: Optional home override used for ``~`` expansion.
        environ: Optional environment mapping.

    Returns:
        Creation details for the root and child directories.

    Raises:
        SetupError: If the root or a managed child is a symlink or non-directory.
    """

    root = _absolute_path(path, home=home, environ=environ)
    _preflight_library(root)
    root_created = _ensure_directory(root)
    created: list[str] = []
    for relative in KNOWLEDGE_DIRECTORIES:
        if _ensure_managed_directory(root, relative):
            created.append(relative)
    return LibraryInitResult(root, root_created, tuple(created))


def _git_executable() -> str:
    """Locate Git without making it a network or hosting dependency.

    Returns:
        Path to the Git executable.

    Raises:
        SetupError: If Git is unavailable for a selected Git setup mode.
    """

    executable = shutil.which("git")
    if executable is None:
        raise SetupError("Git is not installed; rerun setup without Git configuration")
    return executable


def _git_process(root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    """Run a bounded local Git command without allowing credential prompts.

    Args:
        root: Intended repository root.
        *arguments: Git arguments.

    Returns:
        The completed process. Callers decide whether a nonzero code is expected.
    """

    environment = dict(os.environ)
    environment["GIT_TERMINAL_PROMPT"] = "0"
    return subprocess.run(
        [_git_executable(), "-C", os.fspath(root), *arguments],
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
        env=environment,
    )


def _is_repository_root(root: Path) -> bool:
    """Return whether ``root`` itself, rather than an ancestor, is a Git root.

    Args:
        root: Candidate repository root.

    Returns:
        ``True`` only when Git identifies the same top-level directory.
    """

    result = _git_process(root, "rev-parse", "--show-toplevel")
    if result.returncode != 0:
        return False
    try:
        discovered = Path(result.stdout.strip()).resolve(strict=False)
    except (OSError, RuntimeError):
        return False
    return discovered == root.resolve(strict=False)


def _initialize_git(root: Path) -> None:
    """Initialize a local repository without adding or contacting a remote.

    Args:
        root: Library root.

    Raises:
        SetupError: If Git cannot initialize the repository.
    """

    result = _git_process(root, "init", "-b", "main")
    if result.returncode != 0:
        # Older Git versions may not support ``-b``.
        result = _git_process(root, "init")
    if result.returncode != 0 or not _is_repository_root(root):
        raise SetupError("Git could not initialize the local Library repository")


def _validate_remote(name: str, url: str) -> None:
    """Validate remote identifiers without exposing embedded credentials.

    Args:
        name: Git remote name.
        url: Remote URL or local path.

    Raises:
        SetupError: If the name or URL is unsafe or contains URL credentials.
    """

    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name) is None:
        raise SetupError("Git remote name is invalid")
    if not url or url.startswith("-") or any(character in url for character in "\x00\r\n"):
        raise SetupError("Git remote URL is invalid")
    try:
        parsed = urlsplit(url)
        username = parsed.username
        hostname = parsed.hostname
    except ValueError as error:
        raise SetupError("Git remote URL is invalid") from error
    if username is not None or parsed.password is not None:
        raise SetupError("Git remote URL must not contain embedded credentials")
    if parsed.query or parsed.fragment:
        raise SetupError("Git remote URL must not contain query parameters or fragments")
    if parsed.scheme:
        if parsed.scheme not in {"file", "https", "ssh"}:
            raise SetupError("Git remote URL scheme must be file, https, or ssh")
        if parsed.scheme in {"https", "ssh"} and not hostname:
            raise SetupError("Git remote URL must include a host")
        if parsed.scheme == "file" and (parsed.netloc not in {"", "localhost"} or not parsed.path):
            raise SetupError("File Git remote must use a local path")


def _git_remotes(root: Path) -> tuple[tuple[str, str], ...]:
    """Read configured remotes after rejecting credential-bearing URLs.

    Args:
        root: Git repository root.

    Returns:
        Sorted ``(name, url)`` pairs.

    Raises:
        SetupError: If Git cannot inspect the repository or a URL is unsafe.
    """

    listed = _git_process(root, "remote")
    if listed.returncode != 0:
        raise SetupError("Git remotes could not be inspected")
    remotes: list[tuple[str, str]] = []
    for name in sorted(filter(None, listed.stdout.splitlines())):
        result = _git_process(root, "remote", "get-url", name)
        if result.returncode != 0:
            raise SetupError("A Git remote URL could not be inspected")
        url = result.stdout.strip()
        _validate_remote(name, url)
        remotes.append((name, url))
    return tuple(remotes)


def _validate_git_options(mode: GitMode, remote_url: str | None, remote_name: str) -> None:
    """Reject contradictory Git choices before any repository mutation.

    Args:
        mode: Requested Git setup mode.
        remote_url: Optional explicit remote URL.
        remote_name: Requested remote name.

    Raises:
        SetupError: If the selection is incomplete or contradictory.
    """

    if mode not in {"none", "local", "existing", "remote"}:
        raise SetupError("Unknown Git setup mode")
    if mode == "none" and remote_url is not None:
        raise SetupError("No-Git mode does not accept a remote URL")
    if mode == "local" and remote_url is not None:
        raise SetupError("Local Git mode does not accept a remote URL")
    if mode == "existing" and remote_url is not None:
        raise SetupError("Existing Git mode does not accept a new remote URL")
    if mode == "remote":
        if remote_url is None:
            raise SetupError("Remote Git mode requires an explicit remote URL")
        _validate_remote(remote_name, remote_url)


def _preflight_git(root: Path, mode: GitMode, remote_url: str | None, remote_name: str) -> None:
    """Inspect predictable Git conflicts without creating or changing a repository.

    Args:
        root: Intended Library root, which may not exist yet.
        mode: Requested Git mode.
        remote_url: Optional explicit remote URL.
        remote_name: Requested remote name.

    Raises:
        SetupError: If Git is unavailable or existing state conflicts with the plan.
    """

    _validate_git_options(mode, remote_url, remote_name)
    if mode == "none":
        return
    _git_executable()
    if not root.exists():
        if mode == "existing":
            raise SetupError("Existing Git mode requires a repository at the Library root")
        return
    if root.is_symlink() or not root.is_dir():
        raise SetupError("Git setup requires a non-symlink Library directory")
    is_repository = _is_repository_root(root)
    if mode == "existing" and not is_repository:
        raise SetupError("Existing Git mode requires a repository at the Library root")
    if not is_repository:
        return
    remotes = dict(_git_remotes(root))
    if mode == "remote":
        assert remote_url is not None
        current = remotes.get(remote_name)
        if current is not None and current != remote_url:
            raise SetupError("Refusing to overwrite an existing Git remote URL")


def configure_git(
    library: str | os.PathLike[str],
    mode: GitMode,
    *,
    remote_url: str | None = None,
    remote_name: str = "origin",
    home: str | os.PathLike[str] | None = None,
    environ: Mapping[str, str] | None = None,
) -> GitSetupResult:
    """Configure no-Git, local, existing, or explicit-remote Git usage.

    No hosting provider is contacted. Remote mode only records the supplied URL.

    Args:
        library: Initialized Library root.
        mode: ``none``, ``local``, ``existing``, or ``remote``.
        remote_url: Required URL or local path for ``remote`` mode.
        remote_name: Remote name, normally ``origin``.
        home: Optional home override.
        environ: Optional environment mapping.

    Returns:
        Git setup details and non-destructive warnings.

    Raises:
        SetupError: If the mode is invalid or existing state would be overwritten.
    """

    _validate_git_options(mode, remote_url, remote_name)
    root = _absolute_path(library, home=home, environ=environ)
    if not root.is_dir() or root.is_symlink():
        raise SetupError("Git setup requires a non-symlink Library directory")
    if mode == "none":
        return GitSetupResult(mode, False, (), ())
    is_repository = _is_repository_root(root)
    initialized = False
    if mode == "existing":
        if not is_repository:
            raise SetupError("Existing Git mode requires a repository at the Library root")
    else:
        if not is_repository:
            _initialize_git(root)
            initialized = True
            is_repository = True
    assert is_repository
    warnings: list[str] = []
    remotes = _git_remotes(root)
    if mode == "local":
        if remotes:
            warnings.append("Existing Git remotes were preserved; none were contacted")
    elif mode == "remote":
        assert remote_url is not None
        current = dict(remotes).get(remote_name)
        if current is None:
            added = _git_process(root, "remote", "add", remote_name, remote_url)
            if added.returncode != 0:
                raise SetupError("Git remote could not be added")
        elif current != remote_url:
            raise SetupError("Refusing to overwrite an existing Git remote URL")
        remotes = _git_remotes(root)
    return GitSetupResult(mode, initialized, remotes, tuple(warnings))


def _read_instruction_file(path: Path) -> tuple[str, int | None]:
    """Read an optional bounded UTF-8 instruction file without following symlinks.

    Args:
        path: Instruction file path.

    Returns:
        Existing text and permission mode, or empty text and ``None`` when absent.

    Raises:
        SetupError: If the path is unsafe, oversized, or not UTF-8 text.
    """

    if path.is_symlink():
        raise SetupError(f"Refusing symlink instruction file: {path}")
    if not path.exists():
        return "", None
    if not path.is_file():
        raise SetupError(f"Instruction target is not a regular file: {path}")
    try:
        info = path.stat()
        if info.st_size > MAX_INSTRUCTION_BYTES:
            raise SetupError(f"Instruction file is too large: {path}")
        raw = path.read_bytes()
        return raw.decode("utf-8"), stat.S_IMODE(info.st_mode)
    except UnicodeError as error:
        raise SetupError(f"Instruction file must be UTF-8: {path}") from error
    except OSError as error:
        raise SetupError(f"Instruction file could not be read: {path}") from error


def _managed_block(agent: AgentName, adapter: Path) -> str:
    """Build a tiny managed reference without copying adapter content.

    Args:
        agent: Target Agent integration.
        adapter: Absolute canonical adapter path.

    Returns:
        Managed Markdown block.
    """

    reference = (
        f"@{adapter.as_posix()}"
        if agent == "claude"
        else f"Read and follow `{adapter.as_posix()}`."
    )
    return f"{MANAGED_START}\n{reference}\n{MANAGED_END}"


def _merge_managed_block(existing: str, block: str) -> str:
    """Insert or replace exactly one managed block while preserving other text.

    Args:
        existing: Current instruction text.
        block: Desired managed block.

    Returns:
        Updated instruction text.

    Raises:
        SetupError: If incomplete or duplicate markers make ownership ambiguous.
    """

    starts = existing.count(MANAGED_START)
    ends = existing.count(MANAGED_END)
    if starts != ends or starts > 1:
        raise SetupError("Instruction file has incomplete or duplicate managed markers")
    if starts == 1:
        pattern = re.compile(
            re.escape(MANAGED_START) + r".*?" + re.escape(MANAGED_END),
            re.DOTALL,
        )
        return pattern.sub(lambda _match: block, existing, count=1)
    if not existing:
        return block + "\n"
    separator = "\n" if existing.endswith("\n") else "\n\n"
    return existing + separator + block + "\n"


def _sync_directory(path: Path) -> None:
    """Best-effort fsync a directory after a replacement.

    Args:
        path: Directory to synchronize.
    """

    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


def _exclusive_write(path: Path, content: bytes, mode: int) -> None:
    """Create and fsync one new regular file.

    Args:
        path: New file path.
        content: Exact file bytes.
        mode: Initial file mode.

    Raises:
        OSError: If exclusive creation or writing fails.
    """

    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = -1
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _unique_sibling(path: Path, label: str) -> Path:
    """Return an unpredictable sibling name for a backup or temporary file.

    Args:
        path: Destination file.
        label: Human-readable name component.

    Returns:
        A sibling path that is overwhelmingly unlikely to exist.
    """

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return path.with_name(
        f".{path.name}.portable-agent-brain-{label}-{timestamp}-{secrets.token_hex(4)}"
    )


def _restore_file(path: Path, original: bytes | None, mode: int) -> None:
    """Best-effort restore the pre-update file state.

    Args:
        path: Updated target path.
        original: Original bytes, or ``None`` when the target did not exist.
        mode: File permission mode for a restored file.

    Raises:
        OSError: If restoration fails.
    """

    if original is None:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        _sync_directory(path.parent)
        return
    temporary = _unique_sibling(path, "rollback")
    try:
        _exclusive_write(temporary, original, mode)
        os.replace(temporary, path)
        _sync_directory(path.parent)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _transactional_update(path: Path, content: bytes, mode: int | None) -> Path | None:
    """Atomically update one file with backup and failure rollback.

    Args:
        path: Destination file.
        content: Desired exact bytes.
        mode: Existing mode, or ``None`` for a new private file.

    Returns:
        Backup path for an existing file, otherwise ``None``.

    Raises:
        SetupError: If backup, replacement, or rollback fails.
    """

    if path.is_symlink():
        raise SetupError(f"Refusing symlink target: {path}")
    try:
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    except OSError as error:
        raise SetupError(f"Could not create instruction directory: {path.parent}") from error
    original = path.read_bytes() if path.exists() else None
    file_mode = mode if mode is not None else 0o600
    backup: Path | None = None
    if original is not None:
        backup = _unique_sibling(path, "backup")
        try:
            _exclusive_write(backup, original, file_mode)
            _sync_directory(path.parent)
        except OSError as error:
            raise SetupError("Could not create an instruction backup") from error
    temporary = _unique_sibling(path, "tmp")
    try:
        _exclusive_write(temporary, content, file_mode)
        os.replace(temporary, path)
        _sync_directory(path.parent)
    except OSError as error:
        try:
            _restore_file(path, original, file_mode)
        except OSError as rollback_error:
            location = os.fspath(backup) if backup is not None else "no backup"
            raise SetupError(
                f"Instruction update and rollback failed; recovery source: {location}"
            ) from rollback_error
        raise SetupError("Instruction update failed and the original was restored") from error
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
    return backup


def _nonempty_override(path: Path) -> bool:
    """Return whether a safe Codex override contains active content.

    Args:
        path: ``AGENTS.override.md`` path.

    Returns:
        ``True`` when a regular UTF-8 file contains non-whitespace text.
    """

    text, _mode = _read_instruction_file(path)
    return bool(text.strip())


def _plan_agent_adapter(
    agent: AgentName,
    adapter_path: str | os.PathLike[str],
    *,
    target: str | os.PathLike[str] | None = None,
    home: str | os.PathLike[str] | None = None,
    environ: Mapping[str, str] | None = None,
    use_codex_override: bool = False,
) -> _AgentInstallPlan:
    """Validate and stage one Agent instruction update without writing it.

    Args:
        agent: ``claude``, ``codex``, or ``generic``.
        adapter_path: Canonical adapter Markdown file.
        target: Explicit instruction target. Required for ``generic``.
        home: Optional home override.
        environ: Optional environment mapping.
        use_codex_override: Explicitly select a non-empty Codex override.

    Returns:
        An immutable update plan containing the exact original state.

    Raises:
        SetupError: If the adapter or destination cannot be selected safely.
    """

    if agent not in {"claude", "codex", "generic"}:
        raise SetupError("Unsupported Agent adapter")
    environment = os.environ if environ is None else environ
    effective_home = user_home(home, environ=environment)
    adapter_candidate = _absolute_path(adapter_path, home=effective_home, environ=environment)
    try:
        adapter = adapter_candidate.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise SetupError("Adapter path does not exist") from error
    if not adapter.is_file():
        raise SetupError("Adapter path is not a regular file")
    explicit_target = target is not None
    warnings: list[str] = []
    if target is not None:
        destination = _absolute_path(target, home=effective_home, environ=environment)
    elif agent == "claude":
        destination = effective_home / ".claude" / "CLAUDE.md"
    elif agent == "codex":
        configured_codex_home = environment.get("CODEX_HOME")
        codex_home = (
            _absolute_path(configured_codex_home, home=effective_home, environ=environment)
            if configured_codex_home
            else effective_home / ".codex"
        )
        default_target = codex_home / "AGENTS.md"
        override = codex_home / "AGENTS.override.md"
        if _nonempty_override(override):
            if not use_codex_override:
                raise SetupError(
                    "A non-empty Codex AGENTS.override.md is active; explicitly choose "
                    "use_codex_override=True or pass a target after reviewing precedence"
                )
            destination = override
            warnings.append("Installed into the explicitly selected Codex override")
        else:
            destination = default_target
    else:
        raise SetupError("Generic Agent installation requires an explicit target")
    if agent == "codex" and explicit_target:
        warnings.append("Used the explicitly selected Codex instruction target")
    if destination.resolve(strict=False) == adapter:
        raise SetupError("Instruction target must differ from the canonical adapter")
    existing, mode = _read_instruction_file(destination)
    desired = _merge_managed_block(existing, _managed_block(agent, adapter))
    return _AgentInstallPlan(
        agent,
        adapter,
        destination,
        existing,
        mode,
        desired,
        tuple(warnings),
    )


def _apply_agent_plan(plan: _AgentInstallPlan) -> AgentInstallResult:
    """Apply one preflighted Agent update if its source state is unchanged.

    Args:
        plan: Preflighted Agent installation.

    Returns:
        Installation result with a recovery backup when an existing file changed.

    Raises:
        SetupError: If the target changed after preflight or the atomic update fails.
    """

    existing, mode = _read_instruction_file(plan.destination)
    if existing != plan.existing or mode != plan.mode:
        raise SetupError("Instruction target changed after setup preflight")
    if plan.desired == plan.existing:
        return AgentInstallResult(plan.agent, plan.destination, False, None, plan.warnings)
    backup = _transactional_update(
        plan.destination,
        plan.desired.encode("utf-8"),
        plan.mode,
    )
    return AgentInstallResult(plan.agent, plan.destination, True, backup, plan.warnings)


def install_agent_adapter(
    agent: AgentName,
    adapter_path: str | os.PathLike[str],
    *,
    target: str | os.PathLike[str] | None = None,
    home: str | os.PathLike[str] | None = None,
    environ: Mapping[str, str] | None = None,
    use_codex_override: bool = False,
) -> AgentInstallResult:
    """Install one managed thin reference while preserving existing instructions.

    Args:
        agent: ``claude``, ``codex``, or ``generic``.
        adapter_path: Canonical adapter Markdown file. The written reference is absolute.
        target: Explicit instruction target. Required for ``generic``.
        home: Optional home override.
        environ: Optional environment mapping; ``CODEX_HOME`` is honored.
        use_codex_override: Explicitly install into a non-empty Codex override.

    Returns:
        Installation result, including backup and warnings.

    Raises:
        SetupError: If the target is ambiguous or cannot be updated safely.
    """

    plan = _plan_agent_adapter(
        agent,
        adapter_path,
        target=target,
        home=home,
        environ=environ,
        use_codex_override=use_codex_override,
    )
    return _apply_agent_plan(plan)


def _wrapper_content(entrypoint: Path) -> bytes:
    """Return a minimal POSIX wrapper for one absolute executable.

    Args:
        entrypoint: Absolute executable path.

    Returns:
        UTF-8 shell script bytes.
    """

    return ("#!/bin/sh\nexec " + shlex.quote(os.fspath(entrypoint)) + ' "$@"\n').encode("utf-8")


def _install_symlink(entrypoint: Path, target: Path) -> None:
    """Atomically create a command symlink without overwriting another command.

    Args:
        entrypoint: Absolute executable target.
        target: Command path to create.

    Raises:
        OSError: If symlink creation or replacement fails.
    """

    os.symlink(entrypoint, target)
    _sync_directory(target.parent)


def _plan_cli_install(
    entrypoint: str | os.PathLike[str],
    bin_dir: str | os.PathLike[str],
    *,
    name: str = "brain",
    method: CliInstallMethod = "auto",
    home: str | os.PathLike[str] | None = None,
    environ: Mapping[str, str] | None = None,
) -> _CliInstallPlan:
    """Validate a command installation without creating its destination directory.

    Args:
        entrypoint: Existing executable to expose.
        bin_dir: Destination command directory.
        name: Command filename.
        method: ``auto``, ``symlink``, or ``wrapper``.
        home: Optional home override.
        environ: Optional environment mapping.

    Returns:
        A preflight plan containing exact source and desired wrapper bytes.

    Raises:
        SetupError: If input or existing destination state is unsafe.
    """

    if method not in {"auto", "symlink", "wrapper"}:
        raise SetupError("Unknown CLI installation method")
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name) is None:
        raise SetupError("CLI command name is invalid")
    entry_candidate = _absolute_path(entrypoint, home=home, environ=environ)
    try:
        source = entry_candidate.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise SetupError("CLI entrypoint does not exist") from error
    if not source.is_file() or not os.access(source, os.X_OK):
        raise SetupError("CLI entrypoint must be an executable regular file")
    directory = _absolute_path(bin_dir, home=home, environ=environ)
    if directory.is_symlink():
        raise SetupError("Refusing a symlink CLI installation directory")
    if directory.exists() and not directory.is_dir():
        raise SetupError("CLI installation directory is not a directory")
    target = directory / name
    wrapper = _wrapper_content(source)
    if target.is_symlink():
        try:
            if target.resolve(strict=True) == source:
                return _CliInstallPlan(source, target, wrapper, True, True)
        except (OSError, RuntimeError):
            pass
        raise SetupError("Refusing to replace an existing command symlink")
    if target.exists():
        if not target.is_file():
            raise SetupError("Refusing to replace a non-file command")
        try:
            existing = target.read_bytes()
        except OSError as error:
            raise SetupError("Existing command could not be inspected") from error
        if existing != wrapper:
            raise SetupError("Refusing to overwrite an existing command")
    return _CliInstallPlan(source, target, wrapper, target.exists(), directory.exists())


def install_cli(
    entrypoint: str | os.PathLike[str],
    bin_dir: str | os.PathLike[str],
    *,
    name: str = "brain",
    method: CliInstallMethod = "auto",
    home: str | os.PathLike[str] | None = None,
    environ: Mapping[str, str] | None = None,
) -> CliInstallResult:
    """Install a stable command by safe symlink or minimal wrapper.

    Existing unrelated commands are never overwritten.

    Args:
        entrypoint: Existing executable to expose.
        bin_dir: Destination command directory.
        name: Command filename.
        method: ``auto``, ``symlink``, or ``wrapper``.
        home: Optional home override.
        environ: Optional environment mapping.

    Returns:
        Command installation result.

    Raises:
        SetupError: If input or existing destination state is unsafe.
    """

    plan = _plan_cli_install(
        entrypoint,
        bin_dir,
        name=name,
        method=method,
        home=home,
        environ=environ,
    )
    source = plan.source
    target = plan.target
    wrapper = plan.wrapper
    directory = target.parent
    _ensure_directory(directory)
    if target.is_symlink():
        try:
            if target.resolve(strict=True) == source:
                return CliInstallResult(target, False, "symlink")
        except (OSError, RuntimeError):
            pass
        raise SetupError("Refusing to replace an existing command symlink")
    if target.exists():
        if not target.is_file():
            raise SetupError("Refusing to replace a non-file command")
        try:
            existing = target.read_bytes()
        except OSError as error:
            raise SetupError("Existing command could not be inspected") from error
        if existing == wrapper:
            return CliInstallResult(target, False, "wrapper")
        raise SetupError("Refusing to overwrite an existing command")
    if method in {"auto", "symlink"}:
        try:
            _install_symlink(source, target)
            return CliInstallResult(target, True, "symlink")
        except OSError as error:
            if method == "symlink":
                raise SetupError("CLI symlink could not be installed") from error
    try:
        _transactional_update(target, wrapper, 0o755)
        target.chmod(0o755)
    except (OSError, SetupError) as error:
        raise SetupError("CLI wrapper could not be installed") from error
    return CliInstallResult(target, True, "wrapper")


def _plan_config_write(
    library: Path,
    config_path: str | os.PathLike[str] | None,
    *,
    home: str | os.PathLike[str] | None,
    environ: Mapping[str, str],
) -> _ConfigWritePlan:
    """Stage a bounded user-config update without changing the filesystem.

    Args:
        library: Selected absolute Library path.
        config_path: Optional explicit config path.
        home: Optional home override.
        environ: Effective environment mapping.

    Returns:
        Exact before and desired states for rollback verification.

    Raises:
        ConfigError: If an existing target cannot be preserved safely.
    """

    effective_home = user_home(home, environ=environ)
    target = (
        normalize_path(config_path, home=effective_home)
        if config_path is not None
        else default_config_path(home=effective_home, environ=environ)
    )
    if target.is_symlink():
        raise ConfigError("User configuration must not be a symlink")
    original: bytes | None = None
    mode = 0o600
    if target.exists():
        if not target.is_file():
            raise ConfigError("User configuration target is not a regular file")
        try:
            info = target.stat()
            if info.st_size > MAX_CONFIG_BYTES:
                raise ConfigError("User configuration is too large to preserve safely")
            original = target.read_bytes()
            mode = stat.S_IMODE(info.st_mode)
        except OSError as error:
            raise ConfigError("User configuration could not be inspected") from error
    desired = (
        json.dumps(
            {"version": CONFIG_VERSION, "library": library.as_posix()},
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    ).encode("utf-8")
    return _ConfigWritePlan(target, original, mode, desired)


def _rollback_agent_install(plan: _AgentInstallPlan, result: AgentInstallResult) -> None:
    """Undo one changed Agent target only while it still matches this run.

    Args:
        plan: Exact preflight state and desired content.
        result: Completed installation result.

    Raises:
        SetupError: If another process changed the target or restoration fails.
    """

    if not result.changed:
        return
    current, _mode = _read_instruction_file(plan.destination)
    if current != plan.desired:
        raise SetupError("Agent target changed after installation; recovery backup was retained")
    original = plan.existing.encode("utf-8") if plan.mode is not None else None
    restore_mode = plan.mode if plan.mode is not None else 0o600
    try:
        _restore_file(plan.destination, original, restore_mode)
        if result.backup is not None:
            result.backup.unlink()
            _sync_directory(result.backup.parent)
    except OSError as error:
        raise SetupError("Agent target rollback failed; recovery backup was retained") from error


def _rollback_cli_install(plan: _CliInstallPlan, result: CliInstallResult) -> None:
    """Remove a command created by this run after verifying exact ownership.

    Args:
        plan: Preflighted command paths and wrapper content.
        result: Completed command installation.

    Raises:
        SetupError: If the command no longer matches this run's artifact.
    """

    if not result.changed:
        return
    owned = False
    if result.method == "symlink" and result.target.is_symlink():
        try:
            owned = result.target.resolve(strict=True) == plan.source
        except (OSError, RuntimeError):
            owned = False
    elif result.method == "wrapper" and result.target.is_file() and not result.target.is_symlink():
        try:
            owned = result.target.read_bytes() == plan.wrapper
        except OSError:
            owned = False
    if not owned:
        raise SetupError("Installed command changed before rollback and was preserved")
    try:
        result.target.unlink()
        _sync_directory(result.target.parent)
        if not plan.directory_existed:
            try:
                result.target.parent.rmdir()
            except OSError:
                pass
    except OSError as error:
        raise SetupError("Installed command could not be rolled back") from error


def _rollback_config(plan: _ConfigWritePlan) -> None:
    """Restore a config written by this run only if its desired bytes remain.

    Args:
        plan: Exact original and desired config states.

    Raises:
        SetupError: If the config changed after setup or restoration fails.
    """

    try:
        if plan.target.is_symlink() or not plan.target.is_file():
            raise SetupError("User config changed before rollback and was preserved")
        if plan.target.read_bytes() != plan.desired:
            raise SetupError("User config changed before rollback and was preserved")
        _restore_file(plan.target, plan.original, plan.mode)
    except OSError as error:
        raise SetupError("User config rollback failed") from error


def _rollback_library(
    root: Path,
    *,
    root_existed: bool,
    existing_components: set[Path],
) -> None:
    """Remove only empty directories that this setup run created.

    Args:
        root: Library root.
        root_existed: Whether the root existed at preflight.
        existing_components: Managed directories present at preflight.

    Notes:
        Non-empty or concurrently changed directories are deliberately retained.
    """

    for path in reversed(_managed_component_paths(root)):
        if path in existing_components or path.is_symlink():
            continue
        try:
            path.rmdir()
        except (FileNotFoundError, OSError):
            pass
    if not root_existed and not root.is_symlink():
        try:
            root.rmdir()
        except (FileNotFoundError, OSError):
            pass


def history_mining_plan(enabled: bool) -> HistoryMiningPlan:
    """Return guidance for explicit opt-in history mining without reading history.

    Args:
        enabled: Whether the user explicitly opted in.

    Returns:
        A plan. This function never opens an Agent history or writes raw content.
    """

    notice = (
        "Raw conversations, session identifiers, tool logs, credentials, and runtime "
        "telemetry must never be copied into the Knowledge Library."
    )
    if not enabled:
        return HistoryMiningPlan(False, (), notice)
    return HistoryMiningPlan(
        True,
        (
            "Inventory selected history sources read-only and exclude the active session.",
            "Review bounded task summaries; do not persist a raw-history index.",
            "Verify reusable facts against current Project sources and active Decisions.",
            "Submit only short structured candidates through brain learn-extract.",
        ),
        notice,
    )


def run_setup(
    options: SetupOptions,
    *,
    environ: Mapping[str, str] | None = None,
) -> SetupResult:
    """Run setup from explicit options without requiring an interactive framework.

    Args:
        options: Caller-selected setup options.
        environ: Optional environment mapping for isolated HOME and tests.

    Returns:
        Structured results for verification and UI reporting.

    Raises:
        ConfigError: If Library configuration is invalid.
        SetupError: If a setup operation cannot preserve existing state.
    """

    environment = os.environ if environ is None else environ
    library_path = resolve_library_path(
        options.library,
        config_path=options.config_path,
        home=options.home,
        environ=environment,
    )

    # Preflight every predictable failure before creating the Library or touching
    # any user-level integration file.
    root_existed = library_path.exists()
    existing_components = _preflight_library(library_path)
    _preflight_git(
        library_path,
        options.git_mode,
        options.remote_url,
        options.remote_name,
    )
    if options.agents and options.adapter_path is None:
        raise SetupError("Agent installation requires an adapter path")
    if len(set(options.agents)) != len(options.agents):
        raise SetupError("Each Agent may be selected only once")
    if (options.cli_entrypoint is None) != (options.bin_dir is None):
        raise SetupError("CLI installation requires both entrypoint and bin directory")

    targets = options.agent_targets or {}
    agent_plans: list[_AgentInstallPlan] = []
    for agent in options.agents:
        assert options.adapter_path is not None
        agent_plans.append(
            _plan_agent_adapter(
                agent,
                options.adapter_path,
                target=targets.get(agent),
                home=options.home,
                environ=environment,
                use_codex_override=options.use_codex_override,
            )
        )
    destinations = [plan.destination for plan in agent_plans]
    if len(set(destinations)) != len(destinations):
        raise SetupError("Selected Agent integrations resolve to the same instruction file")

    cli_plan = (
        _plan_cli_install(
            options.cli_entrypoint,
            options.bin_dir,
            method=options.cli_method,
            home=options.home,
            environ=environment,
        )
        if options.cli_entrypoint is not None and options.bin_dir is not None
        else None
    )
    config_plan = (
        _plan_config_write(
            library_path,
            options.config_path,
            home=options.home,
            environ=environment,
        )
        if options.persist_config
        else None
    )
    write_targets = [*destinations]
    if cli_plan is not None:
        write_targets.append(cli_plan.target)
    if config_plan is not None:
        write_targets.append(config_plan.target)
    if len(set(write_targets)) != len(write_targets):
        raise SetupError("Setup write targets must not overlap")

    git_marker_existed = os.path.lexists(library_path / ".git")
    agent_results: list[AgentInstallResult] = []
    cli: CliInstallResult | None = None
    config_written = False
    git_apply_started = False
    try:
        library = init_library(library_path, home=options.home, environ=environment)
        for plan in agent_plans:
            agent_results.append(_apply_agent_plan(plan))
        if cli_plan is not None:
            cli = install_cli(
                cli_plan.source,
                cli_plan.target.parent,
                method=options.cli_method,
                home=options.home,
                environ=environment,
            )
        written_config: Path | None = None
        if config_plan is not None:
            written_config = save_user_config(
                library.path,
                options.config_path,
                home=options.home,
                environ=environment,
            )
            config_written = True
        git_apply_started = options.git_mode != "none"
        git = configure_git(
            library.path,
            options.git_mode,
            remote_url=options.remote_url,
            remote_name=options.remote_name,
            home=options.home,
            environ=environment,
        )
    except Exception as error:
        rollback_errors: list[str] = []
        if config_plan is not None:
            config_matches = config_written
            if (
                not config_matches
                and config_plan.target.is_file()
                and not config_plan.target.is_symlink()
            ):
                try:
                    config_matches = config_plan.target.read_bytes() == config_plan.desired
                except OSError:
                    config_matches = False
            if config_matches:
                try:
                    _rollback_config(config_plan)
                except SetupError as rollback_error:
                    rollback_errors.append(str(rollback_error))
        if cli_plan is not None:
            rollback_cli = cli
            if rollback_cli is None and not cli_plan.target_existed:
                if cli_plan.target.is_symlink():
                    rollback_cli = CliInstallResult(cli_plan.target, True, "symlink")
                elif cli_plan.target.is_file():
                    rollback_cli = CliInstallResult(cli_plan.target, True, "wrapper")
            if rollback_cli is not None:
                try:
                    _rollback_cli_install(cli_plan, rollback_cli)
                except SetupError as rollback_error:
                    rollback_errors.append(str(rollback_error))
            elif not cli_plan.directory_existed:
                try:
                    cli_plan.target.parent.rmdir()
                except OSError:
                    pass
        for index in range(len(agent_results) - 1, -1, -1):
            plan = agent_plans[index]
            result = agent_results[index]
            try:
                _rollback_agent_install(plan, result)
            except SetupError as rollback_error:
                rollback_errors.append(str(rollback_error))
        new_git_state = not git_marker_existed and os.path.lexists(library_path / ".git")
        if not new_git_state:
            _rollback_library(
                library_path,
                root_existed=root_existed,
                existing_components=existing_components,
            )
        if git_apply_started:
            rollback_errors.append("Git state was not rolled back; inspect the Library repository")
        if rollback_errors:
            detail = "; ".join(dict.fromkeys(rollback_errors))
            raise SetupError(f"{error}; rollback incomplete: {detail}") from error
        raise
    return SetupResult(
        library,
        written_config,
        git,
        tuple(agent_results),
        cli,
        history_mining_plan(options.history_mining),
    )


__all__ = [
    "AgentInstallResult",
    "CliInstallResult",
    "ConfigError",
    "GitSetupResult",
    "HistoryMiningPlan",
    "LibraryInitResult",
    "SetupError",
    "SetupOptions",
    "SetupResult",
    "configure_git",
    "history_mining_plan",
    "init_library",
    "install_agent_adapter",
    "install_cli",
    "run_setup",
]
