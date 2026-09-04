"""Validate an External Brain library without loading private runtime state."""

from __future__ import annotations

import argparse
import json
import os
import re
from collections.abc import Iterable, Iterator
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import unquote

from tools.graph import IGNORED, inspect_graph, split_frontmatter

TEXT_SUFFIXES = {"", ".json", ".md", ".py", ".toml", ".txt", ".yaml", ".yml"}
REQUIRED_PROJECT_KEYS = {"schema_version", "slug", "node", "project_type", "status"}
TASK_TYPES = {
    "architecture",
    "implementation",
    "ui",
    "debugging",
    "testing",
    "build",
    "documentation",
    "research",
    "analysis",
    "data",
    "security",
}


@dataclass(frozen=True)
class Finding:
    """One diagnostic that never includes source contents or secret values."""

    level: str
    check: str
    path: str
    message: str

    def to_dict(self) -> dict[str, str]:
        """Return a JSON-compatible representation."""
        return asdict(self)


def _relative(path: Path, root: Path) -> str:
    """Return a stable slash-separated relative path."""
    return path.relative_to(root).as_posix()


def iter_files(root: Path, suffixes: set[str] | None = None) -> Iterator[Path]:
    """Yield regular files without following symlinked directories."""
    for current, folders, filenames in os.walk(root, followlinks=False):
        directory = Path(current)
        folders[:] = sorted(
            name for name in folders if name not in IGNORED and not (directory / name).is_symlink()
        )
        for name in sorted(filenames):
            path = directory / name
            if path.is_symlink() or not path.is_file():
                continue
            if suffixes is None or path.suffix.lower() in suffixes:
                yield path


def _read_text(path: Path) -> str:
    """Read bounded UTF-8 text."""
    if path.stat().st_size > 2_000_000:
        raise ValueError("text file exceeds the 2 MB validation limit")
    return path.read_text(encoding="utf-8")


def parse_top_level_yaml_keys(text: str) -> set[str]:
    """Read keys from the deliberately constrained project YAML format."""
    result: set[str] = set()
    for line in text.splitlines():
        if not line or line[0].isspace() or line.lstrip().startswith("#"):
            continue
        match = re.match(r"([A-Za-z0-9_-]+):", line)
        if match:
            result.add(match.group(1))
    return result


def parse_top_level_yaml_scalars(text: str) -> dict[str, str]:
    """Read simple top-level scalar values without a YAML dependency."""
    result: dict[str, str] = {}
    for line in text.splitlines():
        if not line or line[0].isspace() or line.lstrip().startswith("#"):
            continue
        match = re.fullmatch(r"([A-Za-z0-9_-]+):\s*(\S(?:.*\S)?)\s*", line)
        if match:
            result[match.group(1)] = match.group(2).strip("'\"")
    return result


def parse_yaml_list(text: str, key: str) -> list[str]:
    """Read one top-level block list from constrained YAML."""
    result: list[str] = []
    active = False
    for line in text.splitlines():
        if line and not line[0].isspace():
            active = line.startswith(f"{key}:")
            continue
        if not active:
            continue
        match = re.fullmatch(r"\s+-\s+(.+?)\s*", line)
        if match:
            result.append(match.group(1).strip("'\""))
    return result


def parse_yaml_mapping_lists(text: str, key: str) -> dict[str, list[str]]:
    """Read a two-level mapping of block lists from constrained YAML."""
    result: dict[str, list[str]] = {}
    active = False
    current: str | None = None
    for line in text.splitlines():
        if line and not line[0].isspace():
            active = line.strip() == f"{key}:"
            current = None
            continue
        if not active or not line.strip() or line.lstrip().startswith("#"):
            continue
        child = re.fullmatch(r"  ([A-Za-z0-9_-]+):\s*", line)
        if child:
            current = child.group(1)
            result.setdefault(current, [])
            continue
        item = re.fullmatch(r"    -\s+(.+?)\s*", line)
        if item and current is not None:
            result[current].append(item.group(1).strip("'\""))
    return result


def secret_path_kind(path: Path) -> str | None:
    """Classify filenames commonly used for credentials."""
    name = path.name.casefold()
    if name == ".env.example":
        return None
    if name == ".env" or name.startswith(".env."):
        return "environment secret file"
    if name in {"auth.json", "credentials.json", "id_rsa", "id_ed25519"}:
        return "credential file"
    if path.suffix.casefold() in {".key", ".p12", ".pfx", ".pem"}:
        return "private credential material"
    return None


def _check_projects(root: Path) -> list[Finding]:
    """Validate registered Projects; zero Projects is a valid empty library."""
    findings: list[Finding] = []
    for path in sorted((root / "projects").glob("*/project.yaml")):
        relative = _relative(path, root)
        try:
            text = _read_text(path)
        except (OSError, UnicodeError, ValueError):
            findings.append(
                Finding("error", "project-metadata", relative, "unreadable project metadata")
            )
            continue
        keys = parse_top_level_yaml_keys(text)
        scalars = parse_top_level_yaml_scalars(text)
        missing = sorted(REQUIRED_PROJECT_KEYS - keys)
        if missing:
            findings.append(
                Finding(
                    "error", "project-metadata", relative, "missing keys: " + ", ".join(missing)
                )
            )
        if scalars.get("slug") != path.parent.name:
            findings.append(
                Finding("error", "project-metadata", relative, "slug does not match its directory")
            )
        node = scalars.get("node", "")
        if (
            not node
            or Path(node).is_absolute()
            or ".." in Path(node).parts
            or not (root / node).is_file()
        ):
            findings.append(
                Finding(
                    "error",
                    "project-metadata",
                    relative,
                    "node must name an existing library-relative file",
                )
            )
        task_include = parse_yaml_mapping_lists(text, "task_include")
        unknown = sorted(set(task_include) - TASK_TYPES)
        if unknown:
            findings.append(
                Finding(
                    "error",
                    "project-metadata",
                    relative,
                    "unknown task types: " + ", ".join(unknown),
                )
            )
        for target in [
            *parse_yaml_list(text, "always_include"),
            *(item for values in task_include.values() for item in values),
        ]:
            if (
                Path(target).is_absolute()
                or ".." in Path(target).parts
                or not (root / target).is_file()
            ):
                findings.append(
                    Finding(
                        "error", "project-metadata", relative, f"missing policy target: {target}"
                    )
                )
    return findings


def _check_candidate_files(root: Path) -> list[Finding]:
    """Validate lifecycle metadata for candidate inbox Markdown."""
    findings: list[Finding] = []
    directory = root / "inbox" / "candidates"
    if not directory.exists():
        return findings
    if directory.is_symlink() or not directory.is_dir():
        return [
            Finding(
                "error",
                "candidate-store",
                "inbox/candidates",
                "candidate store must be a real directory",
            )
        ]
    for path in sorted(directory.glob("*.md")):
        relative = _relative(path, root)
        try:
            frontmatter, _ = split_frontmatter(_read_text(path))
            scalars = parse_top_level_yaml_scalars(frontmatter)
        except (OSError, UnicodeError, ValueError):
            findings.append(
                Finding(
                    "error",
                    "candidate-store",
                    relative,
                    "candidate is not readable Markdown with frontmatter",
                )
            )
            continue
        if scalars.get("candidate") != "true" or scalars.get("review_status") not in {
            "pending",
            "rejected",
            "superseded",
        }:
            findings.append(
                Finding(
                    "error", "candidate-store", relative, "invalid candidate lifecycle metadata"
                )
            )
    return findings


def _check_secrets(root: Path) -> list[Finding]:
    """Detect common secret material without returning matched values."""
    patterns = (
        ("private key block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
        ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
        ("provider token", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
        ("JWT", re.compile(r"\beyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")),
        (
            "assigned credential literal",
            re.compile(
                r"(?i)\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|passwd|client[_-]?secret)\b\s*[:=]\s*[\"']?[A-Za-z0-9+/_.=-]{12,}"
            ),
        ),
    )
    findings: list[Finding] = []
    for path in iter_files(root):
        relative = _relative(path, root)
        kind = secret_path_kind(path)
        if kind:
            findings.append(Finding("error", "secrets", relative, kind))
        if path.suffix.casefold() not in TEXT_SUFFIXES or path.stat().st_size > 1_000_000:
            continue
        try:
            lines = _read_text(path).splitlines()
        except (OSError, UnicodeError, ValueError):
            continue
        for line_number, line in enumerate(lines, 1):
            for label, pattern in patterns:
                if pattern.search(line):
                    findings.append(
                        Finding("error", "secrets", relative, f"line {line_number}: {label}")
                    )
    return findings


def _check_links(root: Path) -> list[Finding]:
    """Validate local Markdown links while leaving external URLs offline."""
    findings: list[Finding] = []
    pattern = re.compile(r"(?<!!)\[[^\]]+\]\(([^)\s]+)(?:\s+['\"][^)]*['\"])?\)")
    for path in iter_files(root, {".md"}):
        try:
            lines = _read_text(path).splitlines()
        except (OSError, UnicodeError, ValueError):
            continue
        for line_number, line in enumerate(lines, 1):
            for match in pattern.finditer(line):
                raw = match.group(1).strip("<>")
                if raw.startswith("#") or re.match(r"[A-Za-z][A-Za-z0-9+.-]*:", raw):
                    continue
                target = unquote(raw.split("#", 1)[0])
                if not target:
                    continue
                resolved_target = (path.parent / target).resolve(strict=False)
                if not resolved_target.is_relative_to(root):
                    findings.append(
                        Finding(
                            "error",
                            "links",
                            _relative(path, root),
                            f"line {line_number}: local target escapes library root",
                        )
                    )
                elif not resolved_target.is_file():
                    findings.append(
                        Finding(
                            "error",
                            "links",
                            _relative(path, root),
                            f"line {line_number}: missing local target",
                        )
                    )
    return findings


def run_checks(root: Path) -> tuple[list[Finding], dict[str, object]]:
    """Run library validation and return findings plus graph coverage."""
    selected = root.expanduser()
    if selected.is_symlink():
        return [
            Finding("error", "library-root", str(root), "library root must not be a symlink")
        ], {}
    resolved = selected.resolve()
    if not resolved.is_dir():
        return [
            Finding("error", "library-root", str(root), "library root must be a real directory")
        ], {}
    graph = inspect_graph(resolved)
    findings = [
        *_check_projects(resolved),
        *_check_candidate_files(resolved),
        *_check_secrets(resolved),
        *_check_links(resolved),
        *(Finding(item.level, item.check, item.path, item.message) for item in graph.issues),
    ]
    return sorted(
        findings, key=lambda item: (item.level, item.check, item.path, item.message)
    ), graph.summary()


def print_text(findings: Iterable[Finding], graph: dict[str, object]) -> None:
    """Print diagnostics and a compact coverage summary."""
    items = list(findings)
    for item in items:
        print(f"{item.level.upper()} [{item.check}] {item.path}: {item.message}")
    errors = sum(item.level == "error" for item in items)
    warnings = sum(item.level == "warning" for item in items)
    print(f"Validation finished: {errors} errors, {warnings} warnings.")
    if graph:
        summary = (
            f"Graph: {graph['knowledge_nodes']} nodes, "
            f"{graph['typed_relations']} typed relations, "
            f"{graph['canonical_projects']} projects."
        )
        print(summary)


def main(argv: list[str] | None = None) -> int:
    """Run the standalone library validator."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", "--library", dest="root", type=Path, required=True)
    parser.add_argument("--json", action="store_true")
    arguments = parser.parse_args(argv)
    findings, graph = run_checks(arguments.root)
    errors = sum(item.level == "error" for item in findings)
    if arguments.json:
        print(
            json.dumps(
                {
                    "root": str(arguments.root.expanduser().resolve()),
                    "errors": errors,
                    "warnings": sum(item.level == "warning" for item in findings),
                    "findings": [item.to_dict() for item in findings],
                    "graph": graph,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print_text(findings, graph)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
