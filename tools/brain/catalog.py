"""Read a metadata-only catalog; never retain every knowledge body."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from tools.graph import (
    AUTHORITIES,
    IGNORED,
    KNOWLEDGE_ROOTS,
    RELATIONS,
    WIKI,
    graph_metadata,
    is_knowledge,
    resolve_wiki,
    scalar,
)
from tools.validate import (
    parse_top_level_yaml_scalars,
    parse_yaml_list,
    parse_yaml_mapping_lists,
)


class BrainError(ValueError):
    """An actionable error safe for CLI output."""


@dataclass
class Document:
    """Metadata and a source pointer, not a cached document body."""

    path: str
    title: str
    metadata: dict[str, str | list[str]]
    body_offset: int

    @property
    def id(self) -> str:
        """Return the stable knowledge identifier."""
        return str(self.metadata["id"])

    @property
    def kind(self) -> str:
        """Return the original knowledge type."""
        return str(self.metadata["type"])

    @property
    def project(self) -> str:
        """Return explicit project scope or an empty string for shared knowledge."""
        return str(self.metadata.get("project_id", ""))

    @property
    def status(self) -> str:
        """Return the temporal status without inferring currentness."""
        return str(self.metadata.get("status", "unknown"))

    @property
    def is_candidate(self) -> bool:
        """Identify reviewable inbox notes without treating all inbox text as Knowledge."""
        return (
            self.path.startswith("inbox/candidates/") and self.metadata.get("candidate") == "true"
        )

    @property
    def authority(self) -> str:
        """Separate retrieval authority from temporal status and source location."""
        if self.status in {"rejected", "superseded"}:
            return self.status
        explicit = str(self.metadata.get("authority", ""))
        if explicit in AUTHORITIES:
            return explicit
        if self.is_candidate:
            return "candidate"
        if self.status == "needs-verification":
            return "observed"
        if self.status == "active" and self.kind in {
            "decision",
            "principle",
            "project-knowledge",
            "project-rule",
            "protocol",
        }:
            return "canonical"
        return "verified"

    @property
    def evidence_count(self) -> int:
        """Return bounded observation count for candidates; canonical nodes default to one."""
        raw = str(self.metadata.get("evidence_count", "1"))
        return int(raw) if raw.isdigit() and 1 <= int(raw) <= 100000 else 1

    def values(self, key: str) -> list[str]:
        """Return one list property without coercing malformed scalars."""
        value = self.metadata.get(key, [])
        return value if isinstance(value, list) else []


@dataclass
class Project:
    """Project selection policy, kept separate from graph navigation."""

    slug: str
    node: str
    project_type: str
    domains: list[str]
    always_include: list[str]
    task_include: dict[str, list[str]]
    search_include: list[str]

    def required_for(self, task_type: str) -> list[str]:
        """Return deduplicated always and task-specific policy paths."""
        return list(dict.fromkeys([*self.always_include, *self.task_include.get(task_type, [])]))


@dataclass
class Catalog:
    """Metadata, typed adjacency and operation-local I/O counters."""

    root: Path
    documents: dict[str, Document] = field(default_factory=dict)
    projects: dict[str, Project] = field(default_factory=dict)
    adjacency: dict[str, list[tuple[str, str]]] = field(default_factory=dict)
    metrics: dict[str, int] = field(
        default_factory=lambda: {
            "metadata_files_read": 0,
            "body_files_scanned": 0,
            "body_chars_scanned": 0,
        }
    )

    def require_project(self, slug: str | None) -> Project | None:
        """Validate an explicit project filter instead of silently broadening it."""
        if slug is None:
            return None
        if slug not in self.projects:
            raise BrainError("unknown project; use a registered project slug")
        return self.projects[slug]

    def resolve(self, target: str) -> str:
        """Resolve a canonical id, vault path or unambiguous wikilink."""
        if target in {doc.id for doc in self.documents.values()}:
            return next(p for p, doc in self.documents.items() if doc.id == target)
        raw = target[2:-2] if WIKI.fullmatch(target) else target
        path, error = resolve_wiki(raw, "", set(self.documents))
        if error or not path:
            raise BrainError("linked knowledge target is missing or ambiguous")
        return path

    def policy_path(self, path: str) -> str:
        """Map a portable Skill entrypoint to its metadata manifest."""
        if path.endswith("/SKILL.md"):
            parent = Path(path).parent
            path = f"{parent.as_posix()}/{parent.name}.md"
        if path not in self.documents:
            raise BrainError("project policy references missing canonical knowledge")
        return path


def read_header(path: Path, relative: str) -> Document:
    """Read frontmatter and the first title only.

    Args:
        path: Validated local Markdown file.
        relative: Portable source path.

    Returns:
        Metadata-only document.
    """
    with path.open(encoding="utf-8") as stream:
        if stream.readline().strip() != "---":
            raise BrainError(f"missing frontmatter: {relative}")
        lines: list[str] = []
        length = 0
        while True:
            line = stream.readline()
            length += len(line)
            if not line or length > 65536:
                raise BrainError(f"invalid or oversized frontmatter: {relative}")
            if line.strip() == "---":
                break
            lines.append(line)
        offset = stream.tell()
        title = Path(relative).stem
        for _ in range(100):
            line = stream.readline()
            if not line:
                break
            if line.startswith("# "):
                title = line[2:].strip()
                break
    try:
        metadata = graph_metadata("".join(lines))
        # Preserve provenance without interpreting arbitrary historical source paths.
        for key in ("confidence", "source_type"):
            match = re.search(rf"^{key}:\s*(.*)$", "".join(lines), re.MULTILINE)
            if match:
                metadata[key] = scalar(match[1])
    except ValueError as error:
        raise BrainError(f"invalid graph metadata: {relative}") from error
    if not metadata.get("id") or not metadata.get("type") or metadata.get("graph_version") != "1":
        raise BrainError(f"incomplete graph metadata: {relative}")
    return Document(relative, title, metadata, offset)


def load_catalog(root: Path) -> Catalog:
    """Discover canonical metadata plus explicitly marked low-authority candidates."""
    if root.is_symlink() or not root.is_dir():
        raise BrainError("library root must be an existing non-symlink directory; run brain init")
    catalog = Catalog(root.resolve())
    seen: set[str] = set()

    def register(path: Path, relative: str) -> None:
        """Add one validated metadata pointer without retaining its body."""
        document = read_header(path, relative)
        explicit_authority = document.metadata.get("authority")
        if explicit_authority and explicit_authority not in AUTHORITIES:
            raise BrainError("unknown Knowledge authority; run the repository validator")
        if document.id in seen:
            raise BrainError("duplicate knowledge id; run the repository validator")
        seen.add(document.id)
        catalog.documents[relative] = document
        catalog.metrics["metadata_files_read"] += 1

    for directory in sorted(KNOWLEDGE_ROOTS | {"skills"}):
        base = catalog.root / directory
        if not base.is_dir() or base.is_symlink():
            continue
        for current, folders, filenames in os.walk(base, followlinks=False):
            folders[:] = sorted(
                name
                for name in folders
                if name not in IGNORED and not (Path(current) / name).is_symlink()
            )
            for name in sorted(filenames):
                path = Path(current) / name
                relative = path.relative_to(catalog.root).as_posix()
                if path.is_symlink() or not name.endswith(".md") or not is_knowledge(relative):
                    continue
                register(path, relative)
    candidate_root = catalog.root / "inbox/candidates"
    if candidate_root.is_dir() and not candidate_root.is_symlink():
        for path in sorted(candidate_root.glob("*.md")):
            if path.is_symlink() or not path.is_file():
                continue
            relative = path.relative_to(catalog.root).as_posix()
            document = read_header(path, relative)
            if document.metadata.get("candidate") != "true":
                continue
            inactive = document.status in {"rejected", "superseded"}
            if inactive:
                expected_review = "rejected" if document.status == "rejected" else "superseded"
                if document.metadata.get("review_status") != expected_review:
                    raise BrainError("invalid inactive candidate lifecycle metadata")
                if document.metadata.get("authority", document.status) != document.status:
                    raise BrainError("invalid inactive candidate authority")
                continue
            if document.metadata.get("review_status") != "pending" or document.status not in {
                "pending",
                "observed",
            }:
                raise BrainError("invalid candidate lifecycle metadata")
            if document.metadata.get("authority", "candidate") not in {
                "candidate",
                "observed",
            }:
                raise BrainError("invalid candidate authority")
            register(path, relative)
    # A newly initialized library is intentionally empty. Search must be able to
    # return no results before the first Project or shared Knowledge node exists.
    for path in sorted((catalog.root / "projects").glob("*/project.yaml")):
        if path.is_symlink() or path.parent.is_symlink():
            continue
        content = path.read_text(encoding="utf-8")
        values = parse_top_level_yaml_scalars(content)
        slug = values.get("slug", "")
        node = values.get("node", "")
        doc = catalog.documents.get(node)
        if (
            slug != path.parent.name
            or not doc
            or doc.project != slug
            or doc.metadata.get("node_role") != "project"
        ):
            raise BrainError("project registry does not match its canonical node")
        task_include = {
            task_type: [catalog.policy_path(item) for item in items]
            for task_type, items in parse_yaml_mapping_lists(content, "task_include").items()
        }
        catalog.projects[slug] = Project(
            slug=slug,
            node=node,
            project_type=values.get("project_type", values.get("type", "")),
            domains=parse_yaml_list(content, "domains"),
            always_include=[
                catalog.policy_path(item) for item in parse_yaml_list(content, "always_include")
            ],
            task_include=task_include,
            # Search scope is metadata only; it never authorizes blind directory reads.
            search_include=(
                parse_yaml_list(content, "search_include")
                or parse_yaml_mapping_lists(content, "search").get("include", [])
            ),
        )
    for document in catalog.documents.values():
        if document.is_candidate:
            catalog.require_project(document.project or None)
    adjacency: dict[str, set[tuple[str, str]]] = {p: set() for p in catalog.documents}
    for path, doc in catalog.documents.items():
        for relation in sorted(RELATIONS):
            for raw in doc.values(relation):
                target = catalog.resolve(raw)
                adjacency[path].add((relation, target))
                adjacency[target].add((f"inverse:{relation}", path))
    catalog.adjacency = {p: sorted(edges) for p, edges in adjacency.items()}
    return catalog
