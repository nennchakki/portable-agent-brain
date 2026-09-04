"""Search, context, task classification, graph, and authority regressions."""

from __future__ import annotations

from tests.helpers import PROJECT, BrainTestCase
from tools.brain.catalog import BrainError, load_catalog
from tools.brain.context import build_context
from tools.brain.search import search


class CoreTests(BrainTestCase):
    """Exercise the engine only against synthetic temporary Knowledge."""

    def setUp(self) -> None:
        """Prepare an isolated fictional library for each test."""
        super().setUp()
        self.create_weather_library()

    def test_empty_catalog_is_a_valid_new_library(self) -> None:
        """Verify empty catalog is a valid new library."""
        empty = self.sandbox / "empty-library"
        empty.mkdir()
        catalog = load_catalog(empty)
        self.assertEqual(catalog.documents, {})
        self.assertEqual(catalog.projects, {})
        self.assertEqual(search(catalog, "anything"), [])

    def test_catalog_rejects_missing_and_redirected_library_roots(self) -> None:
        """Require an explicit existing directory rather than hiding a missing or linked root."""
        missing = self.sandbox / "missing-library"
        with self.assertRaises(BrainError):
            load_catalog(missing)
        redirected = self.sandbox / "redirected-library"
        redirected.symlink_to(self.library, target_is_directory=True)
        with self.assertRaises(BrainError):
            load_catalog(redirected)

    def test_search_finds_fictional_project_knowledge(self) -> None:
        """Verify search finds fictional project knowledge."""
        hits = search(
            load_catalog(self.library),
            "BarometerFrame checksum",
            project=PROJECT,
            limit=10,
        )
        self.assertEqual(hits[0].id, "reference:barometer-format")
        self.assertEqual(hits[0].authority, "verified")

    def test_context_applies_task_type_and_linked_policy(self) -> None:
        """Verify context applies task type and linked policy."""
        bundle = build_context(
            load_catalog(self.library),
            PROJECT,
            "test the BarometerFrame checksum",
            task_type="testing",
        )
        identifiers = {item["id"] for item in bundle["items"]}
        self.assertEqual(bundle["task_type"], "testing")
        self.assertEqual(bundle["task_type_source"], "explicit")
        self.assertIn("protocol:weather-verification", identifiers)

    def test_trivial_task_returns_an_explicit_skip_bundle(self) -> None:
        """Verify trivial task returns an explicit skip bundle."""
        bundle = build_context(
            load_catalog(self.library),
            PROJECT,
            "fix typo",
        )
        self.assertFalse(bundle["context_recommended"])
        self.assertEqual(bundle["context_recommendation"], "skip")
        self.assertEqual(bundle["items"], [])

    def test_authority_order_is_canonical_then_verified_then_observed_candidate(self) -> None:
        """Verify authority order is canonical then verified then observed candidate."""
        self.note(
            "inbox/candidates/weather-cache.md",
            title="Local Weather Cache Alternative",
            kind="decision",
            identifier="candidate:weather-cache",
            body="Try cloud synchronization for the fictional forecast cache.",
            extra=(
                f"project_id: {PROJECT}\n"
                "candidate: true\n"
                "authority: candidate\n"
                "review_status: pending\n"
            ),
            status="pending",
        )
        catalog = load_catalog(self.library)
        self.assertEqual(
            catalog.documents["decisions/local-weather-cache.md"].authority,
            "canonical",
        )
        self.assertEqual(
            catalog.documents["references/barometer-format.md"].authority,
            "verified",
        )
        self.assertEqual(
            catalog.documents["references/experimental-sensor.md"].authority,
            "observed",
        )
        self.assertEqual(
            catalog.documents["inbox/candidates/weather-cache.md"].authority,
            "candidate",
        )
        bundle = build_context(
            catalog,
            PROJECT,
            "Local Weather Cache cloud synchronization",
            task_type="architecture",
            max_items=10,
        )
        identifiers = [item["id"] for item in bundle["items"]]
        self.assertIn("candidate:weather-cache", identifiers)
        self.assertLess(
            identifiers.index("decision:local-weather-cache"),
            identifiers.index("candidate:weather-cache"),
        )
        candidate = next(
            item for item in bundle["items"] if item["id"] == "candidate:weather-cache"
        )
        self.assertTrue(candidate["warning"])
