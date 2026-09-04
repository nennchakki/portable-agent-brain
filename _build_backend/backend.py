"""PEP 517 wrapper that removes local ownership from source archives."""

from __future__ import annotations

import gzip
import os
import tarfile
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any


def _safe_member(member: tarfile.TarInfo) -> None:
    """Reject archive entries that should never appear in this source release.

    Args:
        member: Source archive member to validate.

    Raises:
        RuntimeError: If the path could escape extraction or is a link/special file.
    """
    path = PurePosixPath(member.name)
    if path.is_absolute() or ".." in path.parts:
        raise RuntimeError("source archive contains an unsafe member path")
    if member.issym() or member.islnk() or not (member.isfile() or member.isdir()):
        raise RuntimeError("source archive contains an unsupported member type")


def normalize_sdist_archive(archive: Path) -> None:
    """Rewrite a gzip tarball with deterministic, non-personal ownership.

    Args:
        archive: Source distribution created by Setuptools.

    Raises:
        RuntimeError: If an archive entry is unsafe or cannot be copied.
        OSError: If the normalized archive cannot replace the original.
    """
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".portable-agent-brain-normalized-",
        suffix=".tar.gz",
        dir=archive.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as raw_output:
            descriptor = -1
            with (
                tarfile.open(archive, "r:gz") as source,
                gzip.GzipFile(filename="", mode="wb", fileobj=raw_output, mtime=0) as compressed,
                tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as output,
            ):
                for member in source.getmembers():
                    _safe_member(member)
                    member.uid = 0
                    member.gid = 0
                    member.uname = "root"
                    member.gname = "root"
                    member.mtime = 0
                    member.pax_headers = {}
                    payload = source.extractfile(member) if member.isfile() else None
                    if member.isfile() and payload is None:
                        raise RuntimeError("source archive member could not be read")
                    try:
                        output.addfile(member, payload)
                    finally:
                        if payload is not None:
                            payload.close()
        os.replace(temporary, archive)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def build_sdist(
    sdist_directory: str,
    config_settings: dict[str, Any] | None = None,
) -> str:
    """Build and normalize a Setuptools source distribution.

    Args:
        sdist_directory: PEP 517 output directory.
        config_settings: Optional frontend settings passed through to Setuptools.

    Returns:
        Filename of the normalized source distribution.
    """
    from setuptools import build_meta

    filename = build_meta.build_sdist(sdist_directory, config_settings)
    normalize_sdist_archive(Path(sdist_directory) / filename)
    return filename


def __getattr__(name: str) -> object:
    """Delegate all other PEP 517 hooks to Setuptools.

    Args:
        name: Backend attribute requested by the build frontend.

    Returns:
        Corresponding Setuptools build hook or attribute.
    """
    if name not in {
        "build_wheel",
        "build_editable",
        "get_requires_for_build_sdist",
        "get_requires_for_build_wheel",
        "get_requires_for_build_editable",
        "prepare_metadata_for_build_wheel",
        "prepare_metadata_for_build_editable",
    }:
        raise AttributeError(name)
    from setuptools import build_meta

    return getattr(build_meta, name)
