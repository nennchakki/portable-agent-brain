"""Automatic capture, deduplication, conflict, secret, and Stop-hook tests."""

from __future__ import annotations

import json
import os

from tests.helpers import PROJECT, BrainTestCase
from tools.brain.catalog import BrainError, load_catalog
from tools.brain.extract import learn_extract
from tools.brain.hook import capture_hook_decision


class CaptureTests(BrainTestCase):
    """Keep every write inside a disposable fictional library."""

    def setUp(self) -> None:
        """Prepare an isolated fictional library for each test."""
        super().setUp()
        self.create_weather_library()

    @staticmethod
    def fact() -> dict[str, object]:
        """Return one reusable fictional observation."""
        return {
            "type": "fact",
            "title": "BarometerFrame cache lifetime",
            "statement": ("A BarometerFrame cache must be cleared before checksum verification."),
        }

    def extract(self, raw: str) -> dict[str, object]:
        """Run learn-extract against a freshly loaded catalog."""
        return learn_extract(
            load_catalog(self.library),
            raw,
            project=PROJECT,
            task_type="testing",
        )

    def candidate_files(self) -> list[object]:
        """List generated candidate files without assuming random names."""
        return sorted((self.library / "inbox/candidates").glob("*.md"))

    def test_candidate_is_saved_with_low_authority(self) -> None:
        """Verify candidate is saved with low authority."""
        result = self.extract(self.summary(reusable=[self.fact()]))
        self.assertTrue(result["knowledge_created"])
        self.assertEqual(result["candidates_created"][0]["authority"], "candidate")
        self.assertEqual(len(self.candidate_files()), 1)
        content = self.candidate_files()[0].read_text(encoding="utf-8")
        self.assertIn('authority: "candidate"', content)
        self.assertIn("review_status: pending", content)
        self.assertIn("evidence_count: 1", content)

    def test_duplicate_same_task_does_not_increment_evidence(self) -> None:
        """Verify duplicate same task does not increment evidence."""
        raw = self.summary(reusable=[self.fact()])
        self.extract(raw)
        replay = self.extract(raw)
        self.assertEqual(len(replay["duplicates_suppressed"]), 1)
        self.assertEqual(replay["reinforcements"], [])
        self.assertEqual(len(self.candidate_files()), 1)
        self.assertIn(
            "evidence_count: 1",
            self.candidate_files()[0].read_text(encoding="utf-8"),
        )

    def test_independent_task_reinforces_without_creating_another_file(self) -> None:
        """Verify independent task reinforces without creating another file."""
        self.extract(self.summary(reusable=[self.fact()]))
        result = self.extract(
            self.summary(
                task="Verify BarometerFrame behavior in a second export path",
                reusable=[self.fact()],
            )
        )
        self.assertEqual(result["reinforcements"][0]["evidence_count"], 2)
        self.assertEqual(len(self.candidate_files()), 1)
        self.assertIn(
            "evidence_count: 2",
            self.candidate_files()[0].read_text(encoding="utf-8"),
        )

    def test_conflict_is_flagged_without_changing_the_active_decision(self) -> None:
        """Verify conflict is flagged without changing the active decision."""
        decision = self.library / "decisions/local-weather-cache.md"
        before = decision.read_bytes()
        raw = self.summary(
            reusable=[
                {
                    "type": "decision",
                    "title": "Cloud Weather Cache",
                    "context": "A fictional synchronization experiment.",
                    "decision": "Use cloud synchronization for forecast storage.",
                    "why": "The demo client requested remote access.",
                }
            ]
        )
        result = self.extract(raw)
        self.assertIn("decisions/local-weather-cache.md", result["conflicts"])
        self.assertEqual(decision.read_bytes(), before)
        candidate = self.candidate_files()[0].read_text(encoding="utf-8")
        self.assertIn("conflicts_with:", candidate)

    def test_secret_rejection_saves_nothing_and_does_not_echo_the_value(self) -> None:
        """Verify secret rejection saves nothing and does not echo the value."""
        secret = "sk-" + "Z" * 24
        raw = self.summary(
            new_findings=[f"A demo process unexpectedly exposed {secret} in output."]
        )
        with self.assertRaises(BrainError) as raised:
            self.extract(raw)
        self.assertNotIn(secret, str(raised.exception))
        self.assertFalse((self.library / "inbox").exists())

    def test_trivial_summary_does_not_create_a_candidate(self) -> None:
        """Verify trivial summary does not create a candidate."""
        result = self.extract(self.summary(task="fix typo", reusable=[self.fact()]))
        self.assertFalse(result["knowledge_created"])
        self.assertEqual(result["reason"], "trivial task")
        self.assertFalse((self.library / "inbox").exists())

    def test_world_writable_candidate_directory_is_rejected(self) -> None:
        """Verify world writable candidate directory is rejected."""
        candidate_directory = self.library / "inbox" / "candidates"
        candidate_directory.mkdir(parents=True)
        candidate_directory.chmod(0o777)
        self.addCleanup(os.chmod, candidate_directory, 0o700)
        with self.assertRaises(BrainError):
            self.extract(self.summary(reusable=[self.fact()]))
        self.assertEqual(list(candidate_directory.iterdir()), [])

    def test_capture_hook_blocks_once_then_prevents_recursion(self) -> None:
        """Verify capture hook blocks once then prevents recursion."""
        payload = {
            "hook_event_name": "Stop",
            "stop_hook_active": False,
            "last_assistant_message": "The fictional task is complete.",
        }
        first = capture_hook_decision(json.dumps(payload).encode("utf-8"))
        self.assertEqual(first["decision"], "block")
        payload["stop_hook_active"] = True
        self.assertEqual(
            capture_hook_decision(json.dumps(payload).encode("utf-8")),
            {"continue": True},
        )
        payload["stop_hook_active"] = False
        payload["last_assistant_message"] += "\n<!-- brain-capture:v1 none -->"
        self.assertEqual(
            capture_hook_decision(json.dumps(payload).encode("utf-8")),
            {"continue": True},
        )
