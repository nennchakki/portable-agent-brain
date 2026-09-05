"""Private GitHub policy tests with real disposable Git histories and no network."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.brain import github
from tools.brain.catalog import BrainError


class GitHubTests(unittest.TestCase):
    """Exercise the transport contract without credentials or real repositories."""

    def setUp(self) -> None:
        """Create a private sandbox and a local bare destination."""
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.sandbox = Path(self.temporary.name).resolve()
        self.library = self.sandbox / "notes"
        self.library.mkdir()
        self.bare = self.sandbox / "backup.git"
        self.repository = github.Repository(12345, "fixture-owner/notes")
        self.git(self.sandbox, "init", "--bare", "--template=", str(self.bare))
        self.sent: list[tuple[str, ...]] = []

    def git(self, root: Path, *arguments: str) -> subprocess.CompletedProcess[bytes]:
        """Run real local Git with an isolated identity and configuration."""
        result = subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "-c",
                "user.name=Fixture Author",
                "-c",
                "user.email=fixture" + "@example.invalid",
                "-c",
                "core.hooksPath=/dev/null",
                *arguments,
            ],
            capture_output=True,
            check=False,
            env=github._environment(),
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        return result

    def transport(
        self, root: Path, repository: github.Repository, *arguments: str
    ) -> subprocess.CompletedProcess[bytes]:
        """Substitute only the remote endpoint, retaining real Git push semantics."""
        self.assertEqual(repository, self.repository)
        self.assertIn(repository.url, arguments)
        if arguments[0] == "push":
            self.sent.append(arguments)
        local_arguments = tuple(
            str(self.bare) if item == repository.url else item for item in arguments
        )
        return self.git(root, *local_arguments)

    def connect(self) -> None:
        """Connect against synthetic verified metadata, without contacting GitHub."""
        with patch.object(github, "verify_repository", return_value=self.repository):
            github.connect(self.library, self.repository.full_name)

    def commit(self, content: str = "# A useful note\n", *, path: str = "note.md") -> str:
        """Create a new committed text snapshot."""
        (self.library / path).write_text(content, encoding="utf-8")
        self.git(self.library, "add", "--", path)
        self.git(self.library, "commit", "-m", "docs: update fixture note")
        return self.git(self.library, "rev-parse", "HEAD").stdout.decode().strip()

    def test_private_metadata_is_strict_and_errors_do_not_echo_response(self) -> None:
        """Public, internal, inaccessible, ambiguous, and read-only targets fail closed."""
        valid: dict[str, object] = {
            "id": 12345,
            "full_name": "fixture-owner/notes",
            "private": True,
            "visibility": "private",
            "push": True,
            "archived": False,
            "disabled": False,
        }
        variants = (
            {"private": False},
            {"visibility": "public"},
            {"visibility": "internal"},
            {"push": False},
            {"push": None},
            {"archived": True},
            {"disabled": True},
            {"id": True},
            {"full_name": "different-owner/notes"},
            {"private": 1},
        )
        for variant in variants:
            with self.subTest(variant=variant):
                response = subprocess.CompletedProcess(
                    [], 0, json.dumps({**valid, **variant}).encode(), b""
                )
                with (
                    patch.object(github, "_executable", return_value="gh"),
                    patch.object(github, "_run", return_value=response),
                ):
                    with self.assertRaises(github.GitHubError):
                        github.verify_repository("fixture-owner/notes")
        response = subprocess.CompletedProcess([], 0, json.dumps(valid).encode(), b"")
        with (
            patch.object(github, "_executable", return_value="gh"),
            patch.object(github, "_run", return_value=response),
        ):
            self.assertEqual(github.verify_repository("fixture-owner/notes"), self.repository)
        response = subprocess.CompletedProcess([], 1, b"", b"credential-value-must-not-appear")
        with (
            patch.object(github, "_executable", return_value="gh"),
            patch.object(github, "_run", return_value=response),
        ):
            with self.assertRaises(github.GitHubError) as error:
                github.verify_repository("fixture-owner/notes")
            self.assertNotIn("credential-value", str(error.exception))

    def test_failed_verification_cannot_initialize_git(self) -> None:
        """Privacy must be established before any connection mutation."""
        with patch.object(
            github, "verify_repository", side_effect=github.GitHubError("private required")
        ):
            with self.assertRaises(github.GitHubError):
                github.connect(self.library, "fixture-owner/notes")
        self.assertFalse((self.library / ".git").exists())

    def test_repository_urls_cannot_smuggle_credentials_or_alternate_hosts(self) -> None:
        """Only the canonical HTTPS host and a plain owner/repository are accepted."""
        for value in (
            "https://github.com.example.invalid/fixture-owner/notes",
            "https://user:example-value" + "@" + "github.com/fixture-owner/notes",
            "https://github.com/fixture-owner/notes?extra=value",
            "https://github.com/fixture-owner/notes#branch",
            "https://github.com/fixture-owner/notes/extra",
            "https://github.com/fixture-owner/%2e%2e",
            "https://github.com:443/fixture-owner/notes",
            "fixture-owner/..",
            "--option/notes",
            "fixture-owner/notes\n",
        ):
            with self.subTest(value=value), self.assertRaises(github.GitHubError):
                github.repository_slug(value)
        self.assertEqual(github.repository_slug(self.repository.url), self.repository.full_name)

    def test_network_transport_uses_canonical_https_and_sanitized_environment(self) -> None:
        """Network Git cannot inherit redirecting environment or implicit push behavior."""
        malicious = {
            "GIT_DIR": "/unrelated/repository",
            "GIT_CONFIG_COUNT": "1",
            "GIT_TRACE": "1",
            "GIT_SSL_NO_VERIFY": "1",
            "GH_DEBUG": "api",
        }
        with patch.dict("os.environ", malicious):
            environment = github._environment()
        for key in malicious:
            self.assertNotIn(key, environment)
        self.assertEqual(environment["GIT_CONFIG_GLOBAL"], "/dev/null")
        response = subprocess.CompletedProcess([], 0, b"", b"")
        with patch.object(github, "_run", return_value=response) as run:
            github._network_git(
                self.library,
                self.repository,
                "ls-remote",
                "--refs",
                self.repository.url,
                "refs/heads/main",
            )
        arguments = run.call_args.args[0]
        self.assertIn("http.followRedirects=false", arguments)
        self.assertIn("http.sslVerify=true", arguments)
        self.assertIn("push.followTags=false", arguments)
        self.assertTrue(any("auth git-credential" in item for item in arguments))
        self.assertEqual(arguments[-2], self.repository.url)

    def test_connection_is_idempotent_and_preserves_different_remote(self) -> None:
        """Reconnection cannot silently replace an existing target or repository ID."""
        self.connect()
        before = (self.library / ".git/config").read_bytes()
        self.connect()
        self.assertEqual((self.library / ".git/config").read_bytes(), before)
        self.git(
            self.library, "remote", "set-url", "origin", "https://github.com/other-owner/notes.git"
        )
        changed = (self.library / ".git/config").read_bytes()
        with self.assertRaises(github.GitHubError):
            self.connect()
        self.assertEqual((self.library / ".git/config").read_bytes(), changed)

    def test_review_then_push_sends_only_the_pinned_commit_and_branch(self) -> None:
        """Preview sends nothing; approval pushes the reviewed commit to a local bare repo."""
        self.connect()
        head = self.commit()
        self.git(self.library, "tag", "local-only-tag")
        with (
            patch.object(github, "verify_repository", return_value=self.repository),
            patch.object(github, "_network_git", side_effect=self.transport),
        ):
            plan = github.prepare_push(self.library)
            self.assertFalse(self.sent)
            self.assertIn("A useful note", plan.patch)
            self.assertEqual(plan.commits, (head,))
            self.assertEqual(plan.files, ("note.md",))
            pushed = github.push(self.library, plan.approval)
            self.assertTrue(pushed.pushed)
            empty = github.prepare_push(self.library)
            self.assertEqual(empty.commits, ())
            self.assertFalse(github.push(self.library, empty.approval).pushed)
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(self.sent[0][-1], f"{head}:refs/heads/main")
        self.assertNotIn("--force", self.sent[0])
        self.assertEqual(
            self.git(self.bare, "rev-parse", "refs/heads/main").stdout.decode().strip(), head
        )
        self.assertEqual(self.git(self.bare, "tag").stdout, b"")

    def test_changed_commit_or_destination_invalidates_approval(self) -> None:
        """A preview cannot authorize different content or a different binding."""
        self.connect()
        self.commit()
        with (
            patch.object(github, "verify_repository", return_value=self.repository),
            patch.object(github, "_network_git", side_effect=self.transport),
        ):
            plan = github.prepare_push(self.library)
            self.commit("# Updated note\n")
            with self.assertRaisesRegex(github.GitHubError, "plan changed"):
                github.push(self.library, plan.approval)
            self.git(self.library, "config", "remote.origin.brainRepositoryId", "98765")
            with self.assertRaisesRegex(github.GitHubError, "identity changed"):
                github.prepare_push(self.library)
        self.assertFalse(self.sent)

    def test_privacy_is_checked_again_immediately_before_sending(self) -> None:
        """Revoked private access after a valid preview prevents any content upload."""
        self.connect()
        self.commit()
        with (
            patch.object(github, "verify_repository", return_value=self.repository),
            patch.object(github, "_network_git", side_effect=self.transport),
        ):
            plan = github.prepare_push(self.library)
        with (
            patch.object(
                github,
                "verify_repository",
                side_effect=[self.repository, github.GitHubError("no longer private")],
            ),
            patch.object(github, "_network_git", side_effect=self.transport),
        ):
            with self.assertRaisesRegex(github.GitHubError, "no longer private"):
                github.push(self.library, plan.approval)
        self.assertFalse(self.sent)

    def test_pushurl_and_local_rewrite_cannot_redirect_transmission(self) -> None:
        """Reject effective alternate destinations before invoking Git transport."""
        self.connect()
        self.commit()
        for key, value in (
            ("remote.origin.pushurl", "https://github.com/other-owner/notes.git"),
            ("url.https://example.invalid/.pushInsteadOf", "https://github.com/"),
            ("remote.origin.url", "fixture-owner/notes"),
            ("http.https://github.com/.sslVerify", "false"),
            ("credential.https://github.com/fixture-owner/notes.helper", "unexpected-helper"),
        ):
            with self.subTest(key=key):
                original = (self.library / ".git/config").read_bytes()
                self.git(self.library, "config", key, value)
                with (
                    patch.object(github, "verify_repository", return_value=self.repository),
                    patch.object(github, "_network_git") as transport,
                ):
                    with self.assertRaises(github.GitHubError):
                        github.prepare_push(self.library)
                    transport.assert_not_called()
                (self.library / ".git/config").write_bytes(original)

    def test_deleted_secret_in_outgoing_history_still_blocks_push(self) -> None:
        """Scanning only the final diff would miss a credential added and then removed."""
        self.connect()
        self.commit("# Fixture\n" + "gh" + "p_" + "x" * 32 + "\n")
        self.commit("# Credential removed\n")
        with (
            patch.object(github, "verify_repository", return_value=self.repository),
            patch.object(github, "_network_git", side_effect=self.transport),
        ):
            with self.assertRaises(BrainError):
                github.prepare_push(self.library)
        self.assertFalse(self.sent)

    def test_unsupported_binary_symlink_and_legacy_grafts_cannot_skip_review(self) -> None:
        """History and blob checks fail closed for content they cannot fully inspect."""
        self.connect()
        self.commit()
        with (
            patch.object(github, "verify_repository", return_value=self.repository),
            patch.object(github, "_network_git", side_effect=self.transport),
        ):
            grafts = self.library / ".git/info/grafts"
            grafts.parent.mkdir(exist_ok=True)
            grafts.write_text("", encoding="utf-8")
            with self.assertRaisesRegex(github.GitHubError, "grafts"):
                github.prepare_push(self.library)
            grafts.unlink()
            (self.library / "image.bin").write_bytes(b"\x00\xff")
            self.git(self.library, "add", "image.bin")
            self.git(self.library, "commit", "-m", "docs: binary fixture")
            with self.assertRaises(github.GitHubError):
                github.prepare_push(self.library)
            self.git(self.library, "reset", "--hard", "HEAD~1")
            (self.library / "redirect.md").symlink_to("note.md")
            self.git(self.library, "add", "redirect.md")
            self.git(self.library, "commit", "-m", "docs: symlink fixture")
            with self.assertRaisesRegex(github.GitHubError, "Symlinks"):
                github.prepare_push(self.library)
        self.assertFalse(self.sent)

    def test_dirty_worktree_is_preserved_and_not_reported_as_saved(self) -> None:
        """Uncommitted knowledge is not silently omitted from a successful backup."""
        self.connect()
        self.commit()
        target = self.library / "new-note.md"
        target.write_text("# New knowledge\n", encoding="utf-8")
        with (
            patch.object(github, "verify_repository", return_value=self.repository),
            patch.object(github, "_network_git") as transport,
        ):
            with self.assertRaisesRegex(github.GitHubError, "commit local changes"):
                github.prepare_push(self.library)
            transport.assert_not_called()
        self.assertEqual(target.read_text(), "# New knowledge\n")

    def test_remote_advance_or_divergence_never_gets_overwritten(self) -> None:
        """Changed remote history invalidates review and does not authorize force pushes."""
        self.connect()
        first = self.commit()
        with (
            patch.object(github, "verify_repository", return_value=self.repository),
            patch.object(github, "_network_git", side_effect=self.transport),
        ):
            plan = github.prepare_push(self.library)
            github.push(self.library, plan.approval)
            self.commit("# Next note\n")
            plan = github.prepare_push(self.library)
            self.git(self.bare, "update-ref", "-d", "refs/heads/main")
            with self.assertRaisesRegex(github.GitHubError, "plan changed"):
                github.push(self.library, plan.approval)
            self.git(self.bare, "update-ref", "refs/heads/main", first)
        self.assertEqual(len(self.sent), 1)

    def test_unfetched_remote_changes_require_reconciliation(self) -> None:
        """An independent remote commit is preserved rather than overwritten or auto-merged."""
        self.connect()
        self.commit()
        with (
            patch.object(github, "verify_repository", return_value=self.repository),
            patch.object(github, "_network_git", side_effect=self.transport),
        ):
            plan = github.prepare_push(self.library)
            github.push(self.library, plan.approval)
            other = self.sandbox / "other-device"
            self.git(self.sandbox, "clone", "--branch", "main", str(self.bare), str(other))
            (other / "note.md").write_text("# Change from another device\n", encoding="utf-8")
            self.git(other, "add", "note.md")
            self.git(other, "commit", "-m", "docs: update from another device")
            self.git(other, "push", "origin", "main")
            expected = self.git(self.bare, "rev-parse", "refs/heads/main").stdout
            self.commit("# Different local change\n")
            with self.assertRaisesRegex(github.GitHubError, "history is missing or diverged"):
                github.prepare_push(self.library)
            self.assertEqual(self.git(self.bare, "rev-parse", "refs/heads/main").stdout, expected)
        self.assertEqual(len(self.sent), 1)

    def test_setup_private_failure_leaves_no_library_or_agent_changes(self) -> None:
        """The older setup entry point cannot bypass verification or partially install agents."""
        from tools.brain.setup import SetupError, SetupOptions, run_setup

        destination = self.sandbox / "new-library"
        with patch.object(
            github, "verify_repository", side_effect=github.GitHubError("private required")
        ):
            with self.assertRaisesRegex(SetupError, "private required"):
                run_setup(
                    SetupOptions(
                        library=destination,
                        git_mode="remote",
                        remote_url=self.repository.url,
                        config_path=self.sandbox / "config.json",
                        home=self.sandbox,
                    ),
                    environ={"HOME": str(self.sandbox)},
                )
        self.assertFalse(destination.exists())
        self.assertFalse((self.sandbox / "config.json").exists())


if __name__ == "__main__":
    unittest.main()
