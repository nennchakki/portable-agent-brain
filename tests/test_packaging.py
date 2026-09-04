"""Packaging contract tests for the reusable public distribution."""

from __future__ import annotations

import io
import tarfile
import tempfile
import tomllib
import unittest
from pathlib import Path

from _build_backend.backend import normalize_sdist_archive
from tests.helpers import REPOSITORY
from tools.brain.cli import _default_adapter
from tools.graph import is_knowledge


class PackagingTests(unittest.TestCase):
    """Ensure a wheel can carry the public docs and starter resources."""

    def test_data_file_patterns_cover_every_public_resource(self) -> None:
        """Require every non-code distribution resource to match wheel metadata."""
        configuration = tomllib.loads((REPOSITORY / "pyproject.toml").read_text(encoding="utf-8"))
        groups = configuration["tool"]["setuptools"]["data-files"]
        covered: set[Path] = set()
        for patterns in groups.values():
            for pattern in patterns:
                covered.update(path for path in REPOSITORY.glob(pattern) if path.is_file())
        expected = {
            REPOSITORY / "README.md",
            REPOSITORY / "README.ja.md",
            REPOSITORY / "LICENSE",
            REPOSITORY / "brain",
        }
        for directory in ("adapters", "docs", "examples", "prompts", "schemas", "templates"):
            expected.update(path for path in (REPOSITORY / directory).rglob("*") if path.is_file())
        self.assertEqual(expected - covered, set())

    def test_translated_guides_are_data_not_runtime_knowledge(self) -> None:
        """Package translated adapters while keeping the English runtime entry point."""
        configuration = tomllib.loads((REPOSITORY / "pyproject.toml").read_text(encoding="utf-8"))
        groups = configuration["tool"]["setuptools"]["data-files"]
        self.assertEqual(groups["share/portable-agent-brain/adapters"], ["adapters/*.md"])
        self.assertEqual(_default_adapter(), REPOSITORY / "adapters/external-brain.md")
        translated_guides = (
            "adapters/external-brain.ja.md",
            "schemas/README.ja.md",
            "templates/library/README.ja.md",
            "examples/demo-project/README.ja.md",
        )
        self.assertTrue(all(not is_knowledge(path) for path in translated_guides))

    def test_sdist_normalizer_removes_local_archive_ownership(self) -> None:
        """Prevent local account names and numeric IDs from leaking through tar headers."""
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "fixture.tar.gz"
            content = b"public fixture\n"
            member = tarfile.TarInfo("fixture/README.md")
            member.size = len(content)
            member.uid = 501
            member.gid = 20
            member.uname = "Local Builder"
            member.gname = "Local Group"
            with tarfile.open(archive, "w:gz") as output:
                output.addfile(member, io.BytesIO(content))
            normalize_sdist_archive(archive)
            with tarfile.open(archive, "r:gz") as result:
                normalized = result.getmembers()
                self.assertTrue(normalized)
                self.assertTrue(
                    all(
                        item.uid == item.gid == 0
                        and item.uname == item.gname == "root"
                        and item.mtime == 0
                        for item in normalized
                    )
                )

    def test_sdist_normalizer_rejects_escaping_paths_without_replacing_source(self) -> None:
        """An unsafe input archive must remain unchanged and produce no output artifact."""
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "fixture.tar.gz"
            member = tarfile.TarInfo("../../outside.txt")
            with tarfile.open(archive, "w:gz") as output:
                output.addfile(member, io.BytesIO(b""))
            original = archive.read_bytes()
            with self.assertRaises(RuntimeError):
                normalize_sdist_archive(archive)
            self.assertEqual(archive.read_bytes(), original)
            self.assertEqual(list(Path(directory).iterdir()), [archive])


if __name__ == "__main__":
    unittest.main()
