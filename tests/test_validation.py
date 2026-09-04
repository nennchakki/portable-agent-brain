"""Library validator tests using only empty and fictional temporary vaults."""

from __future__ import annotations

from tests.helpers import PROJECT, BrainTestCase
from tools.brain.setup import init_library
from tools.validate import run_checks


class ValidationTests(BrainTestCase):
    """Exercise schema and link failures without publishing fixture Knowledge."""

    def errors(self) -> list[object]:
        """Return only validator errors for the current temporary library."""
        findings, _graph = run_checks(self.library)
        return [item for item in findings if item.level == "error"]

    def test_initialized_empty_library_is_valid(self) -> None:
        """Verify initialized empty library is valid."""
        result = init_library(self.library, home=self.agent_home)
        findings, graph = run_checks(result.path)
        self.assertEqual(
            [item for item in findings if item.level == "error"],
            [],
        )
        self.assertEqual(graph["knowledge_nodes"], 0)
        self.assertEqual(graph["canonical_projects"], 0)

    def test_library_root_symlink_is_rejected(self) -> None:
        """Verify library root symlink is rejected."""
        destination = self.sandbox / "real-library"
        destination.mkdir()
        link = self.sandbox / "linked-library"
        link.symlink_to(destination, target_is_directory=True)
        findings, graph = run_checks(link)
        self.assertEqual(graph, {})
        self.assertEqual([item.check for item in findings], ["library-root"])

    def test_fictional_project_matches_the_public_schema(self) -> None:
        """Verify fictional project matches the public schema."""
        self.create_weather_library()
        self.assertEqual(self.errors(), [])

    def test_missing_relation_target_is_reported(self) -> None:
        """Verify missing relation target is reported."""
        self.create_weather_library()
        project = self.library / f"projects/{PROJECT}/{PROJECT}.md"
        content = project.read_text(encoding="utf-8")
        project.write_text(
            content.replace(
                '  - "[[decisions/local-weather-cache]]"',
                '  - "[[decisions/missing-demo-decision]]"',
            ),
            encoding="utf-8",
        )
        checks = {item.check for item in self.errors()}
        self.assertIn("wikilink", checks)

    def test_markdown_link_cannot_escape_the_library(self) -> None:
        """Verify markdown link cannot escape the library."""
        self.create_weather_library()
        outside = self.sandbox / "outside.md"
        outside.write_text("# Not part of the library\n", encoding="utf-8")
        self.write("README.md", "[outside](../../outside.md)\n")
        findings, _graph = run_checks(self.library)
        messages = [item.message for item in findings if item.check == "links"]
        self.assertIn("line 1: local target escapes library root", messages)

    def test_missing_project_schema_version_is_reported(self) -> None:
        """Verify missing project schema version is reported."""
        self.create_weather_library()
        metadata = self.library / f"projects/{PROJECT}/project.yaml"
        metadata.write_text(
            metadata.read_text(encoding="utf-8").replace("schema_version: 1\n", ""),
            encoding="utf-8",
        )
        checks = {item.check for item in self.errors()}
        self.assertIn("project-metadata", checks)
