"""Public CLI tests for initialization, path selection, search, and context."""

from __future__ import annotations

import json

from tests.helpers import PROJECT, REPOSITORY, BrainTestCase
from tools.brain.catalog import load_catalog


class CliTests(BrainTestCase):
    """Treat the command line as the stable distribution interface."""

    def assert_json_success(self, result: object) -> dict[str, object]:
        """Assert a subprocess result succeeded and decode its JSON object."""
        self.assertEqual(result.returncode, 0, result.stderr)
        value = json.loads(result.stdout)
        self.assertIsInstance(value, dict)
        return value

    def test_init_creates_a_valid_empty_library_and_is_idempotent(self) -> None:
        """Verify init creates a valid empty library and is idempotent."""
        first = self.run_brain("init", "--library", str(self.library), "--json")
        self.assert_json_success(first)
        self.assertTrue(self.library.is_dir())
        catalog = load_catalog(self.library)
        self.assertEqual(catalog.documents, {})
        self.assertEqual(catalog.projects, {})
        self.assertEqual(list(self.library.rglob("*.md")), [])

        before = sorted(
            path.relative_to(self.library).as_posix() for path in self.library.rglob("*")
        )
        second = self.run_brain("init", "--library", str(self.library), "--json")
        self.assert_json_success(second)
        after = sorted(
            path.relative_to(self.library).as_posix() for path in self.library.rglob("*")
        )
        self.assertEqual(after, before)

    def test_init_honors_brain_library_environment_override(self) -> None:
        """Verify init honors brain library environment override."""
        target = self.sandbox / "workspace" / ".brain"
        result = self.run_brain("init", "--json", library_env=target)
        self.assert_json_success(result)
        self.assertTrue(target.is_dir())
        self.assertEqual(load_catalog(target).documents, {})

    def test_bootstrap_saves_linked_notes_without_approving_them(self) -> None:
        """Exercise the setup prompt's flow using only synthetic, isolated data."""
        self.assert_json_success(self.run_brain("init", "--library", str(self.library), "--json"))
        for source, destination in (
            ("project.md", f"{PROJECT}.md"),
            ("project.yaml", "project.yaml"),
        ):
            template = (REPOSITORY / "templates/project" / source).read_text(encoding="utf-8")
            content = (
                template.replace("replace-me", PROJECT)
                .replace("YYYY-MM-DD", "2026-01-01")
                .replace("human-reviewed", "synthetic-test")
            )
            self.write(f"projects/{PROJECT}/{destination}", content)

        command = (
            "learn-extract",
            "--library",
            str(self.library),
            "--project",
            PROJECT,
            "--task-type",
            "testing",
            "--stdin",
            "--json",
        )
        summary = self.summary(
            reusable=[
                {
                    "type": "fact",
                    "title": "BarometerFrame checksum verification",
                    "statement": (
                        "Verify the BarometerFrame checksum before displaying measurements."
                    ),
                    "evidence": "Synthetic history summary; verified in a fictional checksum test.",
                }
            ]
        )
        self.assert_json_success(self.run_brain(*command, "--dry-run", input_text=summary))
        self.assertEqual(list((self.library / "inbox/candidates").glob("*.md")), [])
        first = self.assert_json_success(self.run_brain(*command, input_text=summary))
        first_path = first["candidates_created"][0]["path"]
        original = (self.library / first_path).read_bytes()

        followup = self.summary(
            reusable=[
                {
                    "type": "preference",
                    "title": "BarometerFrame output layout",
                    "statement": (
                        "Keep the BarometerFrame checksum result beside the displayed measurement."
                    ),
                    "evidence": "Synthetic user preference from a separate fictional review.",
                    "related": [first_path],
                }
            ]
        )
        second = self.assert_json_success(self.run_brain(*command, input_text=followup))
        second_path = second["candidates_created"][0]["path"]
        saved = (self.library / second_path).read_text(encoding="utf-8")
        self.assertIn(f"[[{first_path.removesuffix('.md')}]]", saved)
        self.assertIn(f"[[projects/{PROJECT}/{PROJECT}]]", saved)
        self.assertEqual((self.library / first_path).read_bytes(), original)
        catalog = load_catalog(self.library)
        for path in (first_path, second_path):
            self.assertEqual(catalog.documents[path].status, "pending")
            self.assertEqual(catalog.documents[path].authority, "candidate")

        results = self.assert_json_success(
            self.run_brain(
                "search",
                "--library",
                str(self.library),
                "--project",
                PROJECT,
                "BarometerFrame",
                "--json",
            )
        )
        self.assertTrue(
            {first_path, second_path}.issubset({item["path"] for item in results["results"]})
        )
        validation = self.assert_json_success(
            self.run_brain("validate", "--library", str(self.library), "--json")
        )
        self.assertEqual(validation["graph"]["knowledge_nodes"], 1)
        self.assertEqual(validation["graph"]["canonical_projects"], 1)

    def test_setup_supports_an_absolute_sandbox_mount_without_agents(self) -> None:
        """Verify setup supports an absolute sandbox mount without agents."""
        target = self.sandbox / "brain"
        self.assertTrue(target.is_absolute())
        result = self.run_brain(
            "setup",
            "--library",
            str(target),
            "--install-command-dir",
            str(self.command_dir),
            "--agent-home",
            str(self.agent_home),
            "--git-mode",
            "local",
            "--json",
        )
        self.assert_json_success(result)
        self.assertEqual(load_catalog(target).documents, {})
        self.assertTrue((self.command_dir / "brain").exists())
        self.assertFalse(any(self.agent_home.rglob("AGENTS.md")))
        self.assertFalse(any(self.agent_home.rglob("CLAUDE.md")))

    def test_setup_accepts_explicit_claude_and_codex_targets(self) -> None:
        """Verify setup accepts explicit claude and codex targets."""
        claude_file = self.agent_home / "claude-global.md"
        codex_file = self.agent_home / "codex-global.md"
        result = self.run_brain(
            "setup",
            "--library",
            str(self.library),
            "--agent",
            "claude",
            "--agent",
            "codex",
            "--claude-file",
            str(claude_file),
            "--codex-file",
            str(codex_file),
            "--agent-home",
            str(self.agent_home),
            "--json",
        )
        self.assert_json_success(result)
        self.assertIn("@", claude_file.read_text(encoding="utf-8"))
        self.assertIn("portable-agent-brain:start", codex_file.read_text(encoding="utf-8"))

    def test_init_refuses_to_mix_a_writable_library_into_the_engine(self) -> None:
        """Verify init refuses to mix a writable library into the engine."""
        target = REPOSITORY / ".test-library-must-not-be-created"
        self.assertFalse(target.exists())
        result = self.run_brain("init", "--library", str(target), "--json")
        self.assertEqual(result.returncode, 2)
        self.assertFalse(target.exists())

    def test_search_uses_custom_library_argument_and_environment(self) -> None:
        """Verify search uses custom library argument and environment."""
        self.create_weather_library()
        explicit = self.run_brain(
            "search",
            "--library",
            str(self.library),
            "--project",
            PROJECT,
            "BarometerFrame checksum",
            "--json",
        )
        explicit_json = self.assert_json_success(explicit)
        self.assertEqual(explicit_json["results"][0]["id"], "reference:barometer-format")

        environment = self.run_brain(
            "search",
            "BarometerFrame checksum",
            "--project",
            PROJECT,
            "--json",
            library_env=self.library,
        )
        environment_json = self.assert_json_success(environment)
        self.assertEqual(environment_json["results"][0]["id"], "reference:barometer-format")

    def test_context_reports_explicit_type_and_automatic_trivial_skip(self) -> None:
        """Verify context reports explicit type and automatic trivial skip."""
        self.create_weather_library()
        typed = self.run_brain(
            "context",
            "--library",
            str(self.library),
            "--project",
            PROJECT,
            "test the BarometerFrame checksum",
            "--task-type",
            "testing",
            "--json",
        )
        typed_json = self.assert_json_success(typed)
        self.assertEqual(typed_json["task_type"], "testing")
        self.assertEqual(typed_json["task_type_source"], "explicit")

        skipped = self.run_brain(
            "context",
            "--library",
            str(self.library),
            "--project",
            PROJECT,
            "fix typo",
            "--json",
        )
        skipped_json = self.assert_json_success(skipped)
        self.assertEqual(skipped_json["context_recommendation"], "skip")
        self.assertEqual(skipped_json["items"], [])

    def test_learn_extract_cli_writes_only_to_the_selected_library(self) -> None:
        """Verify learn extract cli writes only to the selected library."""
        self.create_weather_library()
        result = self.run_brain(
            "learn-extract",
            "--library",
            str(self.library),
            "--project",
            PROJECT,
            "--task-type",
            "testing",
            "--stdin",
            "--json",
            input_text=self.summary(
                new_findings=[
                    "A BarometerFrame checksum stays stable across repeated demo exports."
                ]
            ),
        )
        value = self.assert_json_success(result)
        self.assertTrue(value["knowledge_created"])
        self.assertEqual(len(list((self.library / "inbox/candidates").glob("*.md"))), 1)
