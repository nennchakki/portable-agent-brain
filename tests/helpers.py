"""Small, fictional fixtures shared by the public test suite."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]
BRAIN = REPOSITORY / "brain"
PROJECT = "sample-weather-cli"


class BrainTestCase(unittest.TestCase):
    """Create an isolated library and HOME for every test."""

    def setUp(self) -> None:
        """Allocate paths that cannot touch the real user environment."""
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.sandbox = Path(self.temporary.name)
        self.library = self.sandbox / "mnt" / "agent-library"
        self.agent_home = self.sandbox / "agent-home"
        self.command_dir = self.sandbox / "bin"
        self.agent_home.mkdir(parents=True)
        self.command_dir.mkdir()

    def write(self, relative: str, content: str) -> Path:
        """Write a runtime fixture below the isolated library."""
        target = self.library / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return target

    def note(
        self,
        relative: str,
        *,
        title: str,
        kind: str,
        identifier: str,
        body: str,
        extra: str = "",
        status: str = "active",
    ) -> Path:
        """Create one fictional version-1 Knowledge note."""
        return self.write(
            relative,
            "---\n"
            f"type: {kind}\n"
            f"id: {identifier}\n"
            "graph_version: 1\n"
            f"status: {status}\n"
            "confidence: high\n"
            "source_type: synthetic-test\n"
            f"{extra}"
            "---\n\n"
            f"# {title}\n\n"
            f"{body}\n",
        )

    def create_weather_library(self) -> None:
        """Create a complete fictional Project with linked policy Knowledge."""
        self.note(
            f"projects/{PROJECT}/{PROJECT}.md",
            title="Sample Weather CLI",
            kind="project-knowledge",
            identifier=f"project:{PROJECT}",
            body="A fictional command-line weather report used only by tests.",
            extra=(
                f"project_id: {PROJECT}\n"
                "node_role: project\n"
                "domains:\n"
                '  - "[[concepts/weather-data]]"\n'
                "uses:\n"
                '  - "[[protocols/weather-verification]]"\n'
                '  - "[[decisions/local-weather-cache]]"\n'
            ),
        )
        self.write(
            f"projects/{PROJECT}/project.yaml",
            f"name: Sample Weather CLI\n"
            "schema_version: 1\n"
            f"slug: {PROJECT}\n"
            f"node: projects/{PROJECT}/{PROJECT}.md\n"
            "project_type: software\n"
            "status: active\n"
            "domains:\n"
            "  - weather-data\n"
            "always_include: []\n"
            "task_include:\n"
            "  testing:\n"
            "    - protocols/weather-verification.md\n"
            "search:\n"
            "  include:\n"
            f"    - projects/{PROJECT}\n",
        )
        self.note(
            "concepts/weather-data.md",
            title="Weather Data",
            kind="concept",
            identifier="concept:weather-data",
            body="Navigation for fictional temperature and pressure records.",
            extra="concept_key: weather-data\n",
        )
        self.note(
            "protocols/weather-verification.md",
            title="Weather Verification",
            kind="protocol",
            identifier="protocol:weather-verification",
            body="Verify the barometer checksum before publishing a demo forecast.",
        )
        self.note(
            "decisions/local-weather-cache.md",
            title="Local Weather Cache",
            kind="decision",
            identifier="decision:local-weather-cache",
            body=(
                "The active decision requires local-only forecast storage and "
                "forbids cloud synchronization."
            ),
            extra=f"project_id: {PROJECT}\n",
        )
        self.note(
            "references/barometer-format.md",
            title="Barometer Record Format",
            kind="reference",
            identifier="reference:barometer-format",
            body="Every BarometerFrame record carries a checksum and unit label.",
            extra=f"project_id: {PROJECT}\n",
        )
        self.note(
            "references/experimental-sensor.md",
            title="Experimental Sensor Note",
            kind="fact",
            identifier="fact:experimental-sensor",
            body="One fictional sensor may need another calibration run.",
            extra=f"project_id: {PROJECT}\nauthority: observed\n",
            status="needs-verification",
        )

    def summary(
        self,
        *,
        task: str = "Verify repeated BarometerFrame exports",
        reusable: list[dict[str, object]] | None = None,
        new_findings: list[str] | None = None,
    ) -> str:
        """Return a bounded, fictional learn-extract task summary."""
        value: dict[str, object] = {
            "project": PROJECT,
            "task_type": "testing",
            "task": task,
            "outcome": "success",
            "new_findings": new_findings or [],
            "user_corrections": [],
            "failed_approaches": [],
            "successful_approaches": [],
        }
        if reusable is not None:
            value["reusable_knowledge"] = reusable
        return json.dumps(value, ensure_ascii=False)

    def run_brain(
        self,
        *arguments: str,
        input_text: str | None = None,
        library_env: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """Run the public CLI with an isolated HOME and deterministic environment."""
        environment = os.environ.copy()
        environment.update(
            {
                "HOME": str(self.agent_home),
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONPATH": str(REPOSITORY),
            }
        )
        if library_env is not None:
            environment["BRAIN_LIBRARY"] = str(library_env)
        else:
            environment.pop("BRAIN_LIBRARY", None)
        return subprocess.run(
            [sys.executable, str(BRAIN), *arguments],
            cwd=REPOSITORY,
            env=environment,
            input=input_text,
            text=True,
            capture_output=True,
            check=False,
        )
