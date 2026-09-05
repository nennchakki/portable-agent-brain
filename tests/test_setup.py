"""Setup, configuration, Git, and thin-adapter safety tests."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.brain.config import resolve_library_path, save_user_config
from tools.brain.github import Repository
from tools.brain.setup import (
    KNOWLEDGE_DIRECTORIES,
    SetupError,
    SetupOptions,
    configure_git,
    history_mining_plan,
    init_library,
    install_agent_adapter,
    install_cli,
    run_setup,
)


class SetupTests(unittest.TestCase):
    """Keep every setup mutation inside an isolated HOME."""

    def setUp(self) -> None:
        """Create an isolated filesystem layout."""

        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.sandbox = Path(self.temporary.name)
        self.home = self.sandbox / "home"
        self.home.mkdir()
        self.environment = {"HOME": os.fspath(self.home)}
        self.adapter = self.sandbox / "distribution" / "adapters" / "external-brain.md"
        self.adapter.parent.mkdir(parents=True)
        self.adapter.write_text("# Fictional External Brain adapter\n", encoding="utf-8")

    def test_library_resolution_precedence(self) -> None:
        """Explicit path wins, then environment, saved config, and default."""

        configured = self.sandbox / "configured-library"
        config = self.sandbox / "config.json"
        save_user_config(configured, config, home=self.home, environ=self.environment)
        environment = {
            **self.environment,
            "BRAIN_LIBRARY": os.fspath(self.sandbox / "environment-library"),
        }
        explicit = self.sandbox / "explicit-library"
        self.assertEqual(
            resolve_library_path(explicit, config_path=config, home=self.home, environ=environment),
            explicit,
        )
        self.assertEqual(
            resolve_library_path(config_path=config, home=self.home, environ=environment),
            self.sandbox / "environment-library",
        )
        self.assertEqual(
            resolve_library_path(config_path=config, home=self.home, environ=self.environment),
            configured,
        )
        self.assertEqual(
            resolve_library_path(
                config_path=self.sandbox / "missing.json",
                home=self.home,
                environ=self.environment,
            ),
            self.home / "agent-library",
        )

    def test_saved_config_is_small_versioned_json(self) -> None:
        """Persist only the selected Library path."""

        config = self.sandbox / "settings" / "config.json"
        library = self.sandbox / "library"
        save_user_config(library, config, home=self.home, environ=self.environment)
        value = json.loads(config.read_text(encoding="utf-8"))
        self.assertEqual(value, {"version": 1, "library": library.as_posix()})

    def test_init_library_is_empty_and_idempotent(self) -> None:
        """Initialization creates directories but no Knowledge or candidate files."""

        library = self.sandbox / "library"
        first = init_library(library, home=self.home, environ=self.environment)
        self.assertTrue(first.created)
        self.assertEqual(set(first.created_directories), set(KNOWLEDGE_DIRECTORIES))
        self.assertEqual(list(library.rglob("*.md")), [])
        self.assertEqual(list((library / "inbox/candidates").iterdir()), [])
        second = init_library(library, home=self.home, environ=self.environment)
        self.assertFalse(second.created)
        self.assertEqual(second.created_directories, ())

    def test_init_library_rejects_symlink_root(self) -> None:
        """A symlink cannot redirect initialization outside the selected Library."""

        destination = self.sandbox / "destination"
        destination.mkdir()
        link = self.sandbox / "library"
        link.symlink_to(destination, target_is_directory=True)
        with self.assertRaises(SetupError):
            init_library(link, home=self.home, environ=self.environment)
        self.assertEqual(list(destination.iterdir()), [])

    def test_init_library_rejects_intermediate_symlink(self) -> None:
        """A managed child cannot redirect nested directory creation."""

        library = self.sandbox / "library"
        outside = self.sandbox / "outside"
        library.mkdir()
        outside.mkdir()
        (library / "inbox").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(SetupError):
            init_library(library, home=self.home, environ=self.environment)
        self.assertEqual(list(outside.iterdir()), [])

    def test_predictable_setup_errors_have_no_side_effects(self) -> None:
        """Remote, CLI, and Agent ambiguity is rejected before initialization."""

        library = self.sandbox / "library"
        config = self.sandbox / "config.json"
        with self.assertRaises(SetupError):
            run_setup(
                SetupOptions(
                    library=library,
                    config_path=config,
                    home=self.home,
                    git_mode="remote",
                ),
                environ=self.environment,
            )
        self.assertFalse(library.exists())
        self.assertFalse(config.exists())

        with self.assertRaises(SetupError):
            run_setup(
                SetupOptions(
                    library=library,
                    config_path=config,
                    home=self.home,
                    cli_entrypoint=self.adapter,
                ),
                environ=self.environment,
            )
        self.assertFalse(library.exists())
        self.assertFalse(config.exists())

    def test_all_agent_targets_are_preflighted_before_any_write(self) -> None:
        """A later Codex ambiguity cannot leave an earlier managed block."""

        generic = self.home / "generic" / "AGENTS.md"
        generic.parent.mkdir()
        original = "# Existing generic instructions\n"
        generic.write_text(original, encoding="utf-8")
        codex_home = self.home / "codex"
        codex_home.mkdir()
        (codex_home / "AGENTS.override.md").write_text("# Active override\n", encoding="utf-8")
        environment = {**self.environment, "CODEX_HOME": os.fspath(codex_home)}
        library = self.sandbox / "library"
        config = self.sandbox / "config.json"
        with self.assertRaises(SetupError):
            run_setup(
                SetupOptions(
                    library=library,
                    config_path=config,
                    home=self.home,
                    agents=("generic", "codex"),
                    adapter_path=self.adapter,
                    agent_targets={"generic": generic},
                ),
                environ=environment,
            )
        self.assertEqual(generic.read_text(encoding="utf-8"), original)
        self.assertEqual(list(generic.parent.glob(".*portable-agent-brain-backup-*")), [])
        self.assertFalse(library.exists())
        self.assertFalse(config.exists())

    def test_git_none_needs_no_git_and_local_is_idempotent(self) -> None:
        """No-Git mode is dependency-free; local mode creates no remote."""

        library = init_library(
            self.sandbox / "library", home=self.home, environ=self.environment
        ).path
        with patch("tools.brain.setup.shutil.which", return_value=None):
            result = configure_git(library, "none", home=self.home, environ=self.environment)
        self.assertEqual(result.remotes, ())
        if shutil.which("git") is None:
            self.skipTest("Git is not installed")
        first = configure_git(library, "local", home=self.home, environ=self.environment)
        second = configure_git(library, "local", home=self.home, environ=self.environment)
        self.assertTrue(first.initialized)
        self.assertFalse(second.initialized)
        self.assertEqual(second.remotes, ())

    def test_git_option_errors_do_not_initialize_and_credentials_are_rejected(self) -> None:
        """Predictable remote errors cannot create Git state or expose credentials."""

        library = self.sandbox / "library"
        library.mkdir()
        credential_remote = (
            "https://" + "user" + ":" + "password" + "@" + "example.invalid/library.git"
        )
        query_remote = "https://example.invalid/library.git?" + "token" + "=" + "not-a-secret"
        for remote in (
            None,
            credential_remote,
            "http://example.invalid/library.git",
            "ftp://example.invalid/library.git",
            "https://[invalid/library.git",
            "--upload-pack=unexpected-command",
            query_remote,
        ):
            with self.assertRaises(SetupError):
                configure_git(
                    library,
                    "remote",
                    remote_url=remote,
                    home=self.home,
                    environ=self.environment,
                )
            self.assertFalse((library / ".git").exists())

    def test_git_existing_and_remote_preserve_existing_configuration(self) -> None:
        """Private GitHub remote setup is repeatable and never overwrites another URL."""

        if shutil.which("git") is None:
            self.skipTest("Git is not installed")
        library = init_library(
            self.sandbox / "library", home=self.home, environ=self.environment
        ).path
        remote = "https://github.com/fixture-owner/fictional-library.git"
        repository = Repository(12345, "fixture-owner/fictional-library")
        with patch("tools.brain.github.verify_repository", return_value=repository):
            added = configure_git(
                library,
                "remote",
                remote_url=remote,
                home=self.home,
                environ=self.environment,
            )
            self.assertIn(("origin", remote), added.remotes)
            self.assertEqual(
                (library / ".git/config")
                .read_text(encoding="utf-8")
                .count("brainRepositoryId = 12345"),
                1,
            )
            existing = configure_git(library, "existing", home=self.home, environ=self.environment)
            self.assertFalse(existing.initialized)
            repeated = configure_git(
                library,
                "remote",
                remote_url=remote,
                home=self.home,
                environ=self.environment,
            )
            self.assertFalse(repeated.initialized)
            with (
                patch(
                    "tools.brain.github.verify_repository",
                    return_value=Repository(98765, "fixture-owner/different"),
                ),
                self.assertRaises(SetupError),
            ):
                configure_git(
                    library,
                    "remote",
                    remote_url="https://github.com/fixture-owner/different.git",
                    home=self.home,
                    environ=self.environment,
                )

    def test_adapter_install_preserves_content_backs_up_and_is_idempotent(self) -> None:
        """Only one managed absolute reference is added to an existing file."""

        target = self.home / "rules" / "AGENTS.md"
        target.parent.mkdir(parents=True)
        original = "# Existing instructions\n\nKeep this line.\n"
        target.write_text(original, encoding="utf-8")
        first = install_agent_adapter(
            "generic",
            self.adapter,
            target=target,
            home=self.home,
            environ=self.environment,
        )
        self.assertTrue(first.changed)
        self.assertIsNotNone(first.backup)
        assert first.backup is not None
        self.assertEqual(first.backup.read_text(encoding="utf-8"), original)
        installed = target.read_text(encoding="utf-8")
        self.assertTrue(installed.startswith(original))
        self.assertIn(self.adapter.resolve().as_posix(), installed)
        self.assertNotIn("Fictional External Brain adapter", installed)
        second = install_agent_adapter(
            "generic",
            self.adapter,
            target=target,
            home=self.home,
            environ=self.environment,
        )
        self.assertFalse(second.changed)
        self.assertIsNone(second.backup)

    def test_adapter_failure_restores_existing_file(self) -> None:
        """A replacement failure retains the original and a recovery backup."""

        target = self.home / "rules" / "AGENTS.md"
        target.parent.mkdir(parents=True)
        original = b"# Existing instructions\n"
        target.write_bytes(original)
        real_replace = os.replace
        calls = 0

        def fail_once(source: object, destination: object) -> None:
            """Fail the update replacement, then allow rollback."""

            nonlocal calls
            calls += 1
            if calls == 1:
                raise OSError("synthetic replacement failure")
            real_replace(source, destination)

        with patch("tools.brain.setup.os.replace", side_effect=fail_once):
            with self.assertRaises(SetupError):
                install_agent_adapter(
                    "generic",
                    self.adapter,
                    target=target,
                    home=self.home,
                    environ=self.environment,
                )
        self.assertEqual(target.read_bytes(), original)

    def test_late_setup_failure_rolls_back_reversible_changes(self) -> None:
        """Config, Agent, CLI, and empty Library changes roll back together."""

        library = self.sandbox / "library"
        config = self.sandbox / "config.json"
        original_config = b'{"version": 1, "library": "/fictional/original"}\n'
        config.write_bytes(original_config)
        config.chmod(0o640)
        target = self.home / "rules" / "AGENTS.md"
        target.parent.mkdir(parents=True)
        original_instructions = "# Existing instructions\n"
        target.write_text(original_instructions, encoding="utf-8")
        entrypoint = self.sandbox / "distribution" / "brain"
        entrypoint.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        entrypoint.chmod(0o755)
        command_dir = self.sandbox / "bin"

        with patch("tools.brain.setup.configure_git", side_effect=SetupError("late failure")):
            with self.assertRaises(SetupError):
                run_setup(
                    SetupOptions(
                        library=library,
                        config_path=config,
                        home=self.home,
                        agents=("generic",),
                        adapter_path=self.adapter,
                        agent_targets={"generic": target},
                        cli_entrypoint=entrypoint,
                        bin_dir=command_dir,
                    ),
                    environ=self.environment,
                )

        self.assertEqual(config.read_bytes(), original_config)
        self.assertEqual(config.stat().st_mode & 0o777, 0o640)
        self.assertEqual(target.read_text(encoding="utf-8"), original_instructions)
        self.assertEqual(list(target.parent.glob(".*portable-agent-brain-backup-*")), [])
        self.assertFalse((command_dir / "brain").exists())
        self.assertFalse(library.exists())

    def test_partial_git_failure_preserves_git_for_manual_recovery(self) -> None:
        """A partial Git mutation is retained while reversible files roll back."""

        if shutil.which("git") is None:
            self.skipTest("Git is not installed")
        library = self.sandbox / "library"
        config = self.sandbox / "config.json"
        target = self.home / "rules" / "AGENTS.md"
        target.parent.mkdir(parents=True)
        original = "# Existing instructions\n"
        target.write_text(original, encoding="utf-8")

        def fail_after_git_creation(root: Path, *_arguments: object, **_keywords: object) -> object:
            """Create a synthetic Git marker, then model an unverified partial failure."""

            (root / ".git").mkdir()
            raise SetupError("synthetic partial Git failure")

        with patch("tools.brain.setup.configure_git", side_effect=fail_after_git_creation):
            with self.assertRaisesRegex(SetupError, "Git state was not rolled back"):
                run_setup(
                    SetupOptions(
                        library=library,
                        config_path=config,
                        home=self.home,
                        git_mode="local",
                        agents=("generic",),
                        adapter_path=self.adapter,
                        agent_targets={"generic": target},
                    ),
                    environ=self.environment,
                )

        self.assertTrue((library / ".git").is_dir())
        self.assertFalse(config.exists())
        self.assertEqual(target.read_text(encoding="utf-8"), original)
        self.assertEqual(list(target.parent.glob(".*portable-agent-brain-backup-*")), [])

    def test_codex_override_requires_explicit_selection(self) -> None:
        """A non-empty override is never silently shadowed by AGENTS.md."""

        codex_home = self.home / "custom-codex"
        codex_home.mkdir()
        override = codex_home / "AGENTS.override.md"
        override.write_text("# Existing override\n", encoding="utf-8")
        environment = {**self.environment, "CODEX_HOME": os.fspath(codex_home)}
        with self.assertRaises(SetupError):
            install_agent_adapter("codex", self.adapter, home=self.home, environ=environment)
        result = install_agent_adapter(
            "codex",
            self.adapter,
            home=self.home,
            environ=environment,
            use_codex_override=True,
        )
        self.assertEqual(result.target, override)
        self.assertTrue(result.warnings)

    def test_claude_install_uses_only_an_absolute_import(self) -> None:
        """Claude receives a thin import rather than copied Knowledge."""

        result = install_agent_adapter(
            "claude", self.adapter, home=self.home, environ=self.environment
        )
        content = result.target.read_text(encoding="utf-8")
        self.assertIn("@" + self.adapter.resolve().as_posix(), content)
        self.assertNotIn("Fictional External Brain adapter", content)

    def test_cli_install_is_safe_and_idempotent(self) -> None:
        """Command installation does not overwrite an unrelated executable."""

        entrypoint = self.sandbox / "distribution" / "brain"
        entrypoint.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        entrypoint.chmod(0o755)
        command_dir = self.sandbox / "bin"
        first = install_cli(
            entrypoint,
            command_dir,
            method="symlink",
            home=self.home,
            environ=self.environment,
        )
        self.assertTrue(first.changed)
        self.assertEqual(first.target.resolve(), entrypoint.resolve())
        second = install_cli(
            entrypoint,
            command_dir,
            method="symlink",
            home=self.home,
            environ=self.environment,
        )
        self.assertFalse(second.changed)
        first.target.unlink()
        first.target.write_text("#!/bin/sh\nexit 9\n", encoding="utf-8")
        first.target.chmod(0o755)
        with self.assertRaises(SetupError):
            install_cli(
                entrypoint,
                command_dir,
                home=self.home,
                environ=self.environment,
            )

    def test_history_mining_requires_opt_in_and_never_reads_history(self) -> None:
        """History mining is guidance-only and states the raw-data boundary."""

        disabled = history_mining_plan(False)
        self.assertFalse(disabled.enabled)
        self.assertEqual(disabled.steps, ())
        enabled = history_mining_plan(True)
        self.assertTrue(enabled.enabled)
        self.assertTrue(enabled.steps)
        self.assertIn("Raw conversations", enabled.privacy_notice)


if __name__ == "__main__":
    unittest.main()
