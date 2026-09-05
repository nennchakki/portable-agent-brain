"""Human and JSON output tests for the explicit GitHub CLI workflow."""

from __future__ import annotations

import io
import json
import shlex
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from tools.brain import cli
from tools.brain.github import Connection, PushPlan, Repository


class GitHubCliTests(unittest.TestCase):
    """Keep the review boundary visible without contacting GitHub."""

    def setUp(self) -> None:
        """Create an external temporary library and HOME."""
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.sandbox = Path(self.temporary.name)
        self.library = self.sandbox / "notes"
        self.library.mkdir()
        self.home = self.sandbox / "home"
        self.home.mkdir()
        self.repository = Repository(12345, "fixture-owner/fictional-notes")
        self.connection = Connection(
            self.library.as_posix(), "origin", self.repository, initialized=True
        )

    def run_cli(self, *arguments: str) -> tuple[int, str, str]:
        """Run ``brain`` in-process and capture its terminal output."""
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch.dict("os.environ", {"HOME": self.home.as_posix()}, clear=False):
            with redirect_stdout(stdout), redirect_stderr(stderr):
                result = cli.main([*arguments, "--library", self.library.as_posix()])
        return result, stdout.getvalue(), stderr.getvalue()

    def test_connect_human_output_confirms_private_target(self) -> None:
        """Connection output states the verified private destination."""
        with patch("tools.brain.github.connect", return_value=self.connection):
            result, output, error = self.run_cli(
                "github", "connect", "--repo", self.repository.full_name
            )
        self.assertEqual(result, 0, error)
        self.assertIn("github.com/fixture-owner/fictional-notes", output)
        self.assertIn("private: 確認済み", output)
        self.assertIn("内容は送信していません", output)

    def test_preview_shows_patch_and_exact_approval_command(self) -> None:
        """Preview output exposes outgoing content and a manual approval command."""
        plan = PushPlan(
            self.connection,
            "main",
            "a" * 40,
            None,
            ("a" * 40,),
            ("notes.md",),
            "diff --git a/notes.md b/notes.md\n+synthetic note\n",
            "b" * 64,
        )
        with patch("tools.brain.github.prepare_push", return_value=plan):
            result, output, error = self.run_cli("github", "push")
        self.assertEqual(result, 0, error)
        self.assertIn("GitHub push preview（未送信）", output)
        self.assertIn("outgoing commits (1)", output)
        self.assertIn("notes.md", output)
        self.assertIn("+synthetic note", output)
        self.assertIn("approval SHA-256: " + "b" * 64, output)
        self.assertIn(
            shlex.quote(str(cli.ENGINE_ROOT / "brain"))
            + " github push --library "
            + shlex.quote(self.library.as_posix())
            + " --remote origin --approve "
            + "b" * 64,
            output,
        )
        self.assertIn("未送信", output)

    def test_successful_approval_does_not_repeat_patch(self) -> None:
        """A completed push reports counts without printing the reviewed patch again."""
        plan = PushPlan(
            self.connection,
            "main",
            "a" * 40,
            None,
            ("a" * 40,),
            ("notes.md",),
            "SECRET-SYNTHETIC-PATCH-CONTENT",
            "b" * 64,
            True,
        )
        with patch("tools.brain.github.push", return_value=plan):
            result, output, error = self.run_cli("github", "push", "--approve", "b" * 64)
        self.assertEqual(result, 0, error)
        self.assertIn("送信済み", output)
        self.assertIn("outgoing commits: 1", output)
        self.assertNotIn("SECRET-SYNTHETIC-PATCH-CONTENT", output)

    def test_json_output_remains_dataclass_shaped(self) -> None:
        """JSON output keeps the complete structured push plan."""
        plan = PushPlan(
            self.connection,
            "main",
            "a" * 40,
            None,
            (),
            (),
            "",
            "b" * 64,
        )
        with patch("tools.brain.github.prepare_push", return_value=plan):
            result, output, error = self.run_cli("github", "push", "--json")
        self.assertEqual(result, 0, error)
        value = json.loads(output)
        self.assertEqual(value["approval"], "b" * 64)
        self.assertIn("connection", value)
        self.assertEqual(value["connection"]["repository"]["repository_id"], 12345)

    def test_up_to_date_human_output_does_not_request_another_approval(self) -> None:
        """Already synchronized branches should finish without a redundant next command."""
        plan = PushPlan(self.connection, "main", "a" * 40, "a" * 40, (), (), "", "b" * 64)
        with patch("tools.brain.github.prepare_push", return_value=plan):
            result, output, error = self.run_cli("github", "push")
        self.assertEqual(result, 0, error)
        self.assertIn("送信するコミットはありません", output)
        self.assertNotIn("--approve", output)


if __name__ == "__main__":
    unittest.main()
