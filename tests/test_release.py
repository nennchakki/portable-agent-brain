"""Release-safety regressions for a synthetic public distribution."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from tests.helpers import BrainTestCase
from tools.brain.release import load_denylist, release_check


class ReleaseSafetyTests(BrainTestCase):
    """Create disposable Git histories; never inspect or alter a user repository."""

    def git(
        self,
        root: Path,
        *arguments: str,
        identity_name: str = "Fixture Maintainer",
        identity_email: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """Run one local-only Git command with synthetic author metadata."""
        environment = os.environ.copy()
        fixture_email = identity_email or ("fixture" + "@" + "example.invalid")
        environment.update(
            {
                "GIT_AUTHOR_NAME": identity_name,
                "GIT_AUTHOR_EMAIL": fixture_email,
                "GIT_COMMITTER_NAME": identity_name,
                "GIT_COMMITTER_EMAIL": fixture_email,
            }
        )
        result = subprocess.run(
            ["git", "-C", str(root), *arguments],
            env=environment,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def write_release(self, root: Path, relative: str, content: str) -> Path:
        """Write one file below a synthetic distribution root."""
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return target

    def create_clean_release(self) -> Path:
        """Create the smallest release-shaped repository accepted by the checker."""
        root = self.sandbox / "demo-distribution"
        root.mkdir()
        self.write_release(root, "README.md", "# Demo distribution\n")
        self.write_release(root, "LICENSE", "MIT License\n")
        entrypoint = self.write_release(root, "brain", "#!/usr/bin/env python3\n")
        entrypoint.chmod(0o755)
        self.write_release(
            root,
            "pyproject.toml",
            '[project]\nname = "demo-distribution"\nversion = "0.1.0"\n',
        )
        self.write_release(
            root,
            "adapters/external-brain.md",
            "# External Brain adapter\n",
        )
        self.write_release(
            root,
            "prompts/connect-agent.md",
            "# Connect an agent\n",
        )
        self.write_release(root, "docs/privacy.md", "# Privacy\nLocal by default.\n")
        self.write_release(
            root,
            "schemas/knowledge-node.schema.json",
            '{"$schema":"https://json-schema.org/draft/2020-12/schema"}\n',
        )
        for relative in (
            "projects",
            "lessons",
            "decisions",
            "preferences",
            "procedures",
            "concepts",
            "inbox/candidates",
        ):
            (root / "templates/library" / relative).mkdir(parents=True, exist_ok=True)
        self.git(root, "init", "-q")
        self.git(root, "add", ".")
        self.git(root, "commit", "-q", "-m", "feat: create demo distribution")
        return root

    def checks(self, root: Path, *, denied_terms: tuple[str, ...] = ()) -> set[str]:
        """Return release finding categories for concise assertions."""
        return {
            item["check"] for item in release_check(root, denied_terms=denied_terms)["findings"]
        }

    def test_clean_fictional_distribution_passes(self) -> None:
        """Verify clean fictional distribution passes."""
        root = self.create_clean_release()
        report = release_check(root)
        self.assertTrue(report["ok"], report["findings"])
        self.assertEqual(report["errors"], 0)

    def test_absolute_home_path_is_rejected_without_echoing_its_contents(self) -> None:
        """Verify absolute home path is rejected without echoing its contents."""
        root = self.create_clean_release()
        exposed = "/" + "Users" + "/example-person/demo.txt"
        self.write_release(root, "docs/example.md", f"Source: {exposed}\n")
        report = release_check(root)
        self.assertFalse(report["ok"])
        self.assertIn("absolute-home-path", self.checks(root))
        self.assertNotIn(exposed, str(report["findings"]))

    def test_candidate_runtime_and_backup_artifacts_are_rejected(self) -> None:
        """Verify candidate runtime and backup artifacts are rejected."""
        root = self.create_clean_release()
        self.write_release(root, "inbox/candidates/pending.md", "candidate fixture\n")
        self.write_release(root, ".cache/brain-capture/events.jsonl", "{}\n")
        self.write_release(root, "backups/old.backup", "archived fixture\n")
        report = release_check(root)
        checks = {item["check"] for item in report["findings"]}
        runtime_paths = {
            item["path"] for item in report["findings"] if item["check"] == "runtime-data"
        }
        self.assertIn("candidate-data", checks)
        self.assertIn("runtime-data", checks)
        self.assertIn(".cache/brain-capture/events.jsonl", runtime_paths)

    def test_live_knowledge_is_rejected_without_a_personal_denylist(self) -> None:
        """Reject live Library folders even when their vocabulary is entirely unknown."""
        root = self.create_clean_release()
        self.write_release(root, "projects/fictional-note.md", "# Fictional local note\n")
        self.git(root, "add", "projects")
        self.git(root, "commit", "-q", "-m", "test: add fictional live folder")
        checks = self.checks(root)
        self.assertTrue({"live-knowledge", "git-history-live-knowledge"}.issubset(checks))

    def test_symlink_oversized_candidate_and_setup_backup_are_rejected(self) -> None:
        """Verify symlink oversized candidate and setup backup are rejected."""
        root = self.create_clean_release()
        (root / "linked-readme").symlink_to(root / "README.md")
        self.write_release(root, "large.txt", "x" * 1_000_001)
        self.write_release(root, "inbox/candidates/pending.json", "{}\n")
        self.write_release(
            root,
            ".AGENTS.md.portable-agent-brain-backup-fixture",
            "# backup\n",
        )
        checks = self.checks(root)
        self.assertTrue(
            {"symlink", "oversized-file", "candidate-data", "runtime-data"}.issubset(checks)
        )

    def test_secret_deleted_from_worktree_is_still_rejected_from_history(self) -> None:
        """Verify secret deleted from worktree is still rejected from history."""
        root = self.create_clean_release()
        secret = "sk-" + "Q" * 24
        leaked = self.write_release(root, "temporary-note.txt", f"api_key = {secret}\n")
        self.git(root, "add", "temporary-note.txt")
        self.git(root, "commit", "-q", "-m", "test: add temporary fixture")
        leaked.unlink()
        self.git(root, "add", "-u")
        self.git(root, "commit", "-q", "-m", "test: remove temporary fixture")
        report = release_check(root)
        self.assertFalse(report["ok"])
        self.assertIn("git-history-secret", self.checks(root))
        self.assertNotIn(secret, str(report["findings"]))

    def test_email_deleted_from_worktree_is_still_rejected_from_history(self) -> None:
        """Verify email deleted from worktree is still rejected from history."""
        root = self.create_clean_release()
        address = "contact" + "@" + "mail.invalid"
        leaked = self.write_release(root, "temporary-contact.txt", f"Contact: {address}\n")
        self.git(root, "add", "temporary-contact.txt")
        self.git(root, "commit", "-q", "-m", "test: add contact fixture")
        leaked.unlink()
        self.git(root, "add", "-u")
        self.git(root, "commit", "-q", "-m", "test: remove contact fixture")
        report = release_check(root)
        self.assertFalse(report["ok"])
        self.assertIn("git-history-email", self.checks(root))
        self.assertNotIn(address, str(report["findings"]))

    def test_private_identity_in_nonbaseline_commit_is_rejected(self) -> None:
        """Verify private identity in nonbaseline commit is rejected."""
        root = self.create_clean_release()
        self.write_release(root, "change.txt", "safe fixture\n")
        self.git(root, "add", "change.txt")
        private_name = "Fictional Confidential Maintainer"
        self.git(
            root,
            "commit",
            "-q",
            "-m",
            "test: add fixture",
            identity_name=private_name,
        )
        report = release_check(root, denied_terms=(private_name,))
        self.assertFalse(report["ok"])
        self.assertIn("git-history-metadata", self.checks(root, denied_terms=(private_name,)))
        self.assertNotIn(private_name, str(report["findings"]))

    def test_unknown_root_metadata_is_not_granted_the_public_baseline_exception(self) -> None:
        """Only the known pre-existing public root receives the legacy identity warning."""
        root = self.create_clean_release()
        private_name = "Fictional Confidential Maintainer"
        self.git(root, "commit", "--amend", "--no-edit", "-q", identity_name=private_name)
        report = release_check(root, denied_terms=(private_name,))
        self.assertFalse(report["ok"])
        self.assertIn("git-history-metadata", self.checks(root, denied_terms=(private_name,)))

    def test_external_markers_scan_worktree_and_deleted_history(self) -> None:
        """Keep a private denylist outside the engine while checking every reachable blob."""
        root = self.create_clean_release()
        marker = "fictional-confidential-project"
        policy = self.sandbox / "private-markers.json"
        policy.write_text(json.dumps([marker]), encoding="utf-8")
        terms = load_denylist(policy, root)
        leaked = self.write_release(root, "temporary.txt", marker)
        self.git(root, "add", "temporary.txt")
        self.git(root, "commit", "-q", "-m", "test: add fictional marker")
        report = release_check(root, denied_terms=terms)
        checks = {item["check"] for item in report["findings"]}
        self.assertTrue({"personal-content", "git-history-content"}.issubset(checks))
        self.assertNotIn(marker, str(report))
        leaked.unlink()
        self.git(root, "add", "-u")
        self.git(root, "commit", "-q", "-m", "test: remove fictional marker")
        cli_result = self.run_brain(
            "release-check", "--root", str(root), "--denylist", str(policy), "--json"
        )
        self.assertEqual(cli_result.returncode, 1, cli_result.stderr)
        report = json.loads(cli_result.stdout)
        self.assertTrue(report["checks"]["external_personal_markers"])
        self.assertIn("git-history-content", {item["check"] for item in report["findings"]})
        self.assertNotIn(marker, cli_result.stdout)

    def test_denylist_rejects_inside_checkout_symlink_and_malformed_data(self) -> None:
        """Refuse marker files that could expose private policy or bypass bounded reads."""
        root = self.create_clean_release()
        policy = self.sandbox / "private-markers.json"
        policy.write_text('["fictional-confidential-project"]', encoding="utf-8")
        linked = self.sandbox / "linked-markers.json"
        linked.symlink_to(policy)
        for path in (root / "private-markers.json", linked, self.sandbox / "missing.json"):
            with self.subTest(path=path.name), self.assertRaises(ValueError):
                load_denylist(path, root)
        for raw in ("{}", "[]", "[3]", '["x"]', "x" * 65_537):
            policy.write_text(raw, encoding="utf-8")
            with self.subTest(length=len(raw)), self.assertRaises(ValueError):
                load_denylist(policy, root)
        self.assertEqual(load_denylist(None, root), ())

    def test_denylist_accepts_short_unicode_markers_and_sanitizes_cli_errors(self) -> None:
        """Support two-character names without exposing invalid file paths or input values."""
        root = self.create_clean_release()
        policy = self.sandbox / "private-markers.json"
        policy.write_text(json.dumps(["架空"]), encoding="utf-8")
        self.assertEqual(load_denylist(policy, root), ("架空",))
        policy.write_text("invalid fictional marker contents", encoding="utf-8")
        result = self.run_brain(
            "release-check", "--root", str(root), "--denylist", str(policy), "--json"
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("error", json.loads(result.stderr))
        self.assertNotIn("Traceback", result.stderr)
        self.assertNotIn(str(policy), result.stderr)
        self.assertNotIn("invalid fictional", result.stderr)

    def test_non_distribution_remote_is_rejected(self) -> None:
        """Verify non distribution remote is rejected."""
        root = self.create_clean_release()
        self.git(
            root,
            "remote",
            "add",
            "origin",
            "https://example.invalid/private-knowledge.git",
        )
        report = release_check(root)
        self.assertFalse(report["ok"])
        self.assertIn("git-remote", self.checks(root))

    def test_broken_template_link_is_rejected(self) -> None:
        """Verify broken template link is rejected."""
        root = self.create_clean_release()
        self.write_release(
            root,
            "templates/library/README.md",
            "[missing example](projects/missing.md)\n",
        )
        report = release_check(root)
        self.assertFalse(report["ok"])
        self.assertTrue({"template", "links"} & self.checks(root))
