"""Resolve and persist the user-owned Knowledge Library location."""

from __future__ import annotations

import json
import os
import secrets
from collections.abc import Mapping
from pathlib import Path
from typing import Final

ENV_LIBRARY: Final = "BRAIN_LIBRARY"
ENV_CONFIG: Final = "BRAIN_CONFIG"
CONFIG_VERSION: Final = 1
CONFIG_DIRECTORY: Final = "portable-agent-brain"
CONFIG_FILENAME: Final = "config.json"
DEFAULT_LIBRARY_DIRECTORY: Final = "agent-library"
MAX_CONFIG_BYTES: Final = 64 * 1024


class ConfigError(ValueError):
    """Raised when a Library path or user configuration is unsafe or invalid."""


def _environment(environ: Mapping[str, str] | None) -> Mapping[str, str]:
    """Return the supplied environment or the current process environment.

    Args:
        environ: Optional environment mapping, primarily for isolated setups and tests.

    Returns:
        The effective environment mapping.
    """

    return os.environ if environ is None else environ


def user_home(
    home: str | os.PathLike[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> Path:
    """Resolve HOME without assuming the host and sandbox share one account.

    Args:
        home: Explicit home directory override.
        environ: Optional environment mapping. ``HOME`` is honored when present.

    Returns:
        An absolute home directory path without resolving symlinks.

    Raises:
        ConfigError: If the selected path is empty or contains a NUL byte.
    """

    environment = _environment(environ)
    selected: str | os.PathLike[str] = (
        home if home is not None else environment.get("HOME") or Path.home()
    )
    return normalize_path(selected, home=Path.home())


def normalize_path(
    value: str | os.PathLike[str],
    *,
    home: str | os.PathLike[str],
    base: str | os.PathLike[str] | None = None,
) -> Path:
    """Convert a configured path to an absolute path without following symlinks.

    Args:
        value: Configured path value.
        home: Home used to expand ``~`` and ``~/``.
        base: Base for a relative value. The process working directory is the default.

    Returns:
        A normalized absolute path.

    Raises:
        ConfigError: If the value is empty or contains unsafe control characters.
    """

    text = os.fspath(value)
    if not text or not text.strip():
        raise ConfigError("Library path must not be empty")
    if "\x00" in text or "\n" in text or "\r" in text:
        raise ConfigError("Library path contains an unsafe control character")
    home_path = Path(home)
    if text == "~":
        candidate = home_path
    elif text.startswith("~/"):
        candidate = home_path / text[2:]
    elif text.startswith("~"):
        try:
            candidate = Path(text).expanduser()
        except RuntimeError as error:
            raise ConfigError("Library path contains an unknown home directory") from error
    else:
        candidate = Path(text)
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate if base is None else Path(base) / candidate
    return Path(os.path.abspath(candidate))


def default_config_path(
    *,
    home: str | os.PathLike[str] | None = None,
    environ: Mapping[str, str] | None = None,
) -> Path:
    """Return the per-user configuration path.

    Args:
        home: Optional home directory override.
        environ: Optional environment mapping. ``BRAIN_CONFIG`` and
            ``XDG_CONFIG_HOME`` are honored.

    Returns:
        An absolute JSON configuration path.
    """

    environment = _environment(environ)
    effective_home = user_home(home, environ=environment)
    configured = environment.get(ENV_CONFIG)
    if configured is not None:
        return normalize_path(configured, home=effective_home)
    xdg = environment.get("XDG_CONFIG_HOME")
    if xdg is None:
        base = effective_home / ".config"
    else:
        base = normalize_path(xdg, home=effective_home)
    return base / CONFIG_DIRECTORY / CONFIG_FILENAME


def _selected_config_path(
    config_path: str | os.PathLike[str] | None,
    *,
    home: Path,
    environ: Mapping[str, str],
) -> Path:
    """Resolve an explicit or default user configuration path.

    Args:
        config_path: Explicit configuration path.
        home: Effective user home.
        environ: Effective environment mapping.

    Returns:
        The absolute configuration path.
    """

    if config_path is not None:
        return normalize_path(config_path, home=home)
    return default_config_path(home=home, environ=environ)


def load_user_config(
    config_path: str | os.PathLike[str] | None = None,
    *,
    home: str | os.PathLike[str] | None = None,
    environ: Mapping[str, str] | None = None,
) -> Path | None:
    """Load the optional Library path from the user configuration.

    Args:
        config_path: Explicit configuration path.
        home: Optional home directory override.
        environ: Optional environment mapping.

    Returns:
        The configured absolute Library path, or ``None`` when no config exists.

    Raises:
        ConfigError: If the configuration is unsafe, oversized, or malformed.
    """

    environment = _environment(environ)
    effective_home = user_home(home, environ=environment)
    path = _selected_config_path(config_path, home=effective_home, environ=environment)
    if path.is_symlink():
        raise ConfigError("User configuration must not be a symlink")
    if not path.exists():
        return None
    if not path.is_file():
        raise ConfigError("User configuration is not a regular file")
    try:
        with path.open("rb") as stream:
            raw = stream.read(MAX_CONFIG_BYTES + 1)
    except OSError as error:
        raise ConfigError("User configuration could not be read") from error
    if len(raw) > MAX_CONFIG_BYTES:
        raise ConfigError("User configuration is too large")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError, RecursionError) as error:
        raise ConfigError("User configuration must be valid UTF-8 JSON") from error
    if not isinstance(value, dict):
        raise ConfigError("User configuration must be a JSON object")
    version = value.get("version", CONFIG_VERSION)
    if version != CONFIG_VERSION:
        raise ConfigError("Unsupported user configuration version")
    library = value.get("library")
    if not isinstance(library, str):
        raise ConfigError("User configuration must contain a string library path")
    return normalize_path(library, home=effective_home, base=path.parent)


def resolve_library_path(
    explicit_library: str | os.PathLike[str] | None = None,
    *,
    config_path: str | os.PathLike[str] | None = None,
    home: str | os.PathLike[str] | None = None,
    environ: Mapping[str, str] | None = None,
) -> Path:
    """Resolve the Library using the documented precedence.

    Precedence is explicit ``--library`` value > ``BRAIN_LIBRARY`` > user config
    > ``~/agent-library``.

    Args:
        explicit_library: Path supplied explicitly by a caller or CLI option.
        config_path: Optional user configuration path.
        home: Optional home directory override.
        environ: Optional environment mapping.

    Returns:
        The selected absolute Library path.

    Raises:
        ConfigError: If a selected value or user configuration is invalid.
    """

    environment = _environment(environ)
    effective_home = user_home(home, environ=environment)
    if explicit_library is not None:
        return normalize_path(explicit_library, home=effective_home)
    if ENV_LIBRARY in environment:
        return normalize_path(environment[ENV_LIBRARY], home=effective_home)
    configured = load_user_config(config_path, home=effective_home, environ=environment)
    return configured if configured is not None else effective_home / DEFAULT_LIBRARY_DIRECTORY


def _sync_directory(path: Path) -> None:
    """Best-effort fsync a directory after an atomic configuration update.

    Args:
        path: Directory to synchronize.
    """

    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    descriptor = os.open(path, flags)
    try:
        os.fsync(descriptor)
    except OSError:
        # Some filesystems do not support directory fsync; the file itself is synced.
        pass
    finally:
        os.close(descriptor)


def save_user_config(
    library: str | os.PathLike[str],
    config_path: str | os.PathLike[str] | None = None,
    *,
    home: str | os.PathLike[str] | None = None,
    environ: Mapping[str, str] | None = None,
) -> Path:
    """Atomically persist the selected Library path in the user config.

    Args:
        library: Library path to persist.
        config_path: Explicit configuration path.
        home: Optional home directory override.
        environ: Optional environment mapping.

    Returns:
        The absolute configuration path written.

    Raises:
        ConfigError: If the target is unsafe or cannot be written atomically.
    """

    environment = _environment(environ)
    effective_home = user_home(home, environ=environment)
    target = _selected_config_path(config_path, home=effective_home, environ=environment)
    if target.is_symlink():
        raise ConfigError("User configuration must not be a symlink")
    if target.exists() and not target.is_file():
        raise ConfigError("User configuration target is not a regular file")
    normalized_library = normalize_path(library, home=effective_home)
    payload = (
        json.dumps(
            {"version": CONFIG_VERSION, "library": normalized_library.as_posix()},
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    ).encode("utf-8")
    try:
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        temporary = target.parent / (f".{target.name}.tmp-{os.getpid()}-{secrets.token_hex(6)}")
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                descriptor = -1
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
            _sync_directory(target.parent)
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass
    except OSError as error:
        raise ConfigError("User configuration could not be written safely") from error
    return target
