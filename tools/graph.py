"""Validate portable knowledge relations using a deliberately small YAML subset."""

from __future__ import annotations

import json
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote

AUTHORITIES = frozenset(
    {"canonical", "verified", "observed", "candidate", "rejected", "superseded"}
)
RELATIONS = frozenset(
    {
        "project",
        "domains",
        "related",
        "uses",
        "depends_on",
        "supersedes",
        "superseded_by",
        "caused_by",
        "prevents",
        "implements",
        "conflicts_with",
    }
)
LIST_KEYS = RELATIONS | {
    "aliases",
    "domain_ids",
    "evidence_signatures",
}
SCALAR_KEYS = {
    "authority",
    "candidate",
    "confidence",
    "created",
    "evidence_count",
    "fingerprint",
    "id",
    "graph_version",
    "last_observed",
    "node_role",
    "project_id",
    "concept_key",
    "review_status",
    "skill_entrypoint",
    "source_type",
    "task_type",
    "type",
    "status",
}
KNOWLEDGE_ROOTS = {
    "principles",
    "protocols",
    "projects",
    "lessons",
    "decisions",
    "concepts",
    "references",
    "profiles",
    "preferences",
    "procedures",
}
IGNORED = {
    ".git",
    ".obsidian",
    ".cache",
    "cache",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
}
WIKI = re.compile(r"(?<!\\)\[\[([^\]\n]+)\]\]")
MARKDOWN = re.compile(r"(?<!!)\[[^\]\n]+\]\((<[^>\n]+>|[^)\s]+)\)")


@dataclass(frozen=True)
class Issue:
    """A safe graph diagnostic without private source content."""

    level: str
    check: str
    path: str
    message: str


@dataclass
class Node:
    """A canonical Markdown node, independent of the human UI."""

    path: str
    metadata: dict[str, str | list[str]]
    body: str


@dataclass
class Graph:
    """A derived, in-memory graph; never the source of truth."""

    nodes: dict[str, Node]
    edges: set[tuple[str, str, str]]
    issues: list[Issue]
    markdown_files: list[str]
    non_knowledge_orphans: list[str]

    def summary(self) -> dict[str, object]:
        """Return serializable validation coverage and typed adjacency."""
        degree: defaultdict[str, int] = defaultdict(int)
        for source, _, target in self.edges:
            if source != target:
                degree[source] += 1
                degree[target] += 1
        return {
            "knowledge_nodes": len(self.nodes),
            "typed_relations": sum(kind in RELATIONS for _, kind, _ in self.edges),
            "knowledge_edges": len(self.edges),
            "concepts": sum(n.metadata.get("type") == "concept" for n in self.nodes.values()),
            "canonical_projects": sum(
                n.metadata.get("node_role") == "project" for n in self.nodes.values()
            ),
            "orphans": sorted(path for path in self.nodes if not degree[path]),
            "excluded_markdown": sorted(set(self.markdown_files) - self.nodes.keys()),
            "non_knowledge_orphans": self.non_knowledge_orphans,
            "edges": [{"source": a, "relation": b, "target": c} for a, b, c in sorted(self.edges)],
        }


def split_frontmatter(text: str) -> tuple[str, str]:
    """Separate YAML and body without interpreting arbitrary legacy fields."""
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return "", text
    for index, line in enumerate(lines[1:], 1):
        if line.strip() == "---":
            return "".join(lines[1:index]), "".join(lines[index + 1 :])
    raise ValueError("frontmatter closing delimiter is missing")


def scalar(value: str) -> str:
    """Read a YAML string or plain scalar; reject structured YAML."""
    value = value.strip()
    if value.startswith('"'):
        parsed = json.loads(value)
        if not isinstance(parsed, str):
            raise ValueError("expected a string")
        return parsed
    if value.startswith("'"):
        if len(value) < 2 or not value.endswith("'"):
            raise ValueError("unclosed quoted string")
        return value[1:-1].replace("''", "'")
    if any(char in value for char in "[]{}&*!|>") or " #" in value:
        raise ValueError("use a quoted string, without YAML anchors or inline comments")
    return value


def graph_metadata(frontmatter: str) -> dict[str, str | list[str]]:
    """Parse version-1 graph fields, rejecting unsupported shapes.

    Other legacy YAML fields are retained in files but not interpreted here.
    Graph lists must be quoted block lists or the empty list [].
    """
    result: dict[str, str | list[str]] = {}
    seen: set[str] = set()
    active: str | None = None
    for line in frontmatter.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line[0].isspace():
            match = re.fullmatch(r"([A-Za-z0-9_-]+):\s*(.*)", line)
            if match is None:
                raise ValueError("unsupported top-level YAML")
            key, value = match.groups()
            if key in seen:
                raise ValueError(f"duplicate YAML key: {key}")
            seen.add(key)
            active = key
            if key in LIST_KEYS:
                if value not in ("", "[]"):
                    raise ValueError(f"{key}: use a quoted block list or []")
                result[key] = []
                if value == "[]":
                    active = None
            elif key in SCALAR_KEYS:
                result[key] = scalar(value)
        elif active in LIST_KEYS:
            match = re.fullmatch(r"  - (.+)", line)
            if match is None or not match[1].startswith(("'", '"')):
                raise ValueError(f"{active}: expected two-space indented quoted list item")
            values = result[active]
            assert isinstance(values, list)
            values.append(scalar(match[1]))
        elif active in SCALAR_KEYS or active is None:
            raise ValueError("unexpected nested graph value")
    return result


def visible_text(text: str) -> str:
    """Remove code and comments so examples cannot create graph edges."""
    text = re.sub(r"<!--.*?-->", lambda m: "\n" * m[0].count("\n"), text, flags=re.DOTALL)
    text = re.sub(r"%%.*?%%", lambda m: "\n" * m[0].count("\n"), text, flags=re.DOTALL)
    result: list[str] = []
    fence: str | None = None
    width = 0
    for line in text.splitlines():
        match = re.match(r"^\s{0,3}(\x60{3,}|~{3,})(.*)$", line)
        if match:
            marker, rest = match.groups()
            if fence is None:
                fence, width = marker[0], len(marker)
            elif marker[0] == fence and len(marker) >= width and not rest.strip():
                fence = None
            result.append("")
        elif fence is None and not line.startswith(("    ", "\t")):
            result.append(line)
        else:
            result.append("")
    joined = "\n".join(result)
    return re.sub(r"(\x60+).*?\1", lambda m: "\n" * m[0].count("\n"), joined, flags=re.DOTALL)


def is_knowledge(path: str) -> bool:
    """Exclude adapters, reports, templates and skill implementation assets."""
    parts = Path(path).parts
    if Path(path).name == "TEMPLATE.md":
        return False
    if parts[0] in KNOWLEDGE_ROOTS:
        return True
    return len(parts) == 3 and parts[0] == "skills" and parts[2] == f"{parts[1]}.md"


def identity(value: str) -> str:
    """Normalize names conservatively for duplicate identity detection."""
    return unicodedata.normalize("NFKC", value).strip().casefold()


def resolve_wiki(raw: str, source: str, files: set[str]) -> tuple[str | None, str | None]:
    """Resolve vault paths or unambiguous basenames; aliases are display-only."""
    target = raw.split("|", 1)[0].split("#", 1)[0].strip()
    if not target:
        return source, None
    path = Path(target)
    if path.is_absolute() or ".." in path.parts or "\\" in target:
        return None, "target must be a vault-relative path"
    candidates = {target, target + ".md"}
    if "/" not in target:
        candidates |= {name for name in files if Path(name).name in {target, target + ".md"}}
    matches = candidates & files
    if not matches:
        return None, f"missing linked target: {target}"
    if len(matches) > 1:
        return None, f"ambiguous linked target: {target}"
    return next(iter(matches)), None


def has_anchor(raw: str, body: str) -> bool:
    """Check literal Obsidian headings and block identifiers when supplied."""
    target = raw.split("|", 1)[0]
    if "#" not in target:
        return True
    anchor = target.split("#", 1)[1]
    if anchor.startswith("^"):
        return re.search(rf"(?:^|\s)\^{re.escape(anchor[1:])}(?:\s|$)", body) is not None
    headings = re.findall(r"^ {0,3}#{1,6}\s+(.+?)\s*#*\s*$", visible_text(body), re.MULTILINE)
    return identity(anchor) in {identity(value) for value in headings}


def cycle_nodes(adjacency: dict[str, set[str]]) -> set[str]:
    """Find every node in a supersession cycle, not unrelated descendants."""
    cyclic: set[str] = set()
    visited: set[str] = set()
    stack: list[str] = []
    active: set[str] = set()

    def visit(node: str) -> None:
        """Perform a bounded graph traversal with an active path."""
        if node in active:
            cyclic.update(stack[stack.index(node) :])
            return
        if node in visited:
            return
        active.add(node)
        stack.append(node)
        for neighbor in sorted(adjacency.get(node, set())):
            visit(neighbor)
        stack.pop()
        active.remove(node)
        visited.add(node)

    for node in sorted(adjacency):
        visit(node)
    return cyclic


def inspect_graph(root: Path) -> Graph:
    """Build and validate the graph entirely from Markdown and project YAML."""
    root = root.resolve()
    files = {
        p.relative_to(root).as_posix()
        for p in root.rglob("*")
        if p.is_file() and not p.is_symlink() and not (set(p.relative_to(root).parts) & IGNORED)
    }
    markdown = sorted(path for path in files if path.endswith(".md"))
    nodes: dict[str, Node] = {}
    bodies: dict[str, str] = {}
    issues: list[Issue] = []
    edges: set[tuple[str, str, str]] = set()
    all_edges: set[tuple[str, str]] = set()

    def issue(level: str, check: str, path: str, message: str) -> None:
        """Append one graph finding."""
        issues.append(Issue(level, check, path, message))

    for path in markdown:
        text = (root / path).read_text(encoding="utf-8")
        try:
            frontmatter, body = split_frontmatter(text)
            bodies[path] = body
            if is_knowledge(path):
                metadata = graph_metadata(frontmatter)
                nodes[path] = Node(path, metadata, body)
                for key in ("id", "type", "graph_version"):
                    if not metadata.get(key):
                        issue("error", "graph-metadata", path, f"missing {key}")
                if metadata.get("graph_version") != "1":
                    issue("error", "graph-metadata", path, "unsupported graph_version")
        except ValueError as error:
            issue("error", "graph-metadata", path, str(error))
            bodies.setdefault(path, text)

    ids: defaultdict[str, list[str]] = defaultdict(list)
    concept_names: defaultdict[str, set[str]] = defaultdict(set)
    projects: defaultdict[str, list[str]] = defaultdict(list)
    for path, node in nodes.items():
        meta = node.metadata
        node_id = meta.get("id")
        authority = meta.get("authority")
        if authority is not None and authority not in AUTHORITIES:
            issue(
                "error",
                "knowledge-authority",
                path,
                "authority must use the documented lifecycle vocabulary",
            )
        if isinstance(node_id, str):
            ids[node_id].append(path)
            if not re.fullmatch(r"[a-z][a-z0-9-]*:[a-z0-9][a-z0-9/._-]*", node_id):
                issue(
                    "error",
                    "graph-id",
                    path,
                    "id must be a namespaced stable identifier",
                )
        if meta.get("type") == "concept":
            key = meta.get("concept_key")
            if not isinstance(key, str) or not key:
                issue("error", "duplicate-concept", path, "concept_key is required")
            else:
                if node_id != f"concept:{key}":
                    issue("error", "graph-id", path, "concept id and concept_key disagree")
                for name in [key, Path(path).stem, *meta.get("aliases", [])]:
                    concept_names[identity(name)].add(path)
        if meta.get("node_role") == "project":
            slug = meta.get("project_id")
            if not isinstance(slug, str) or not slug:
                issue("error", "canonical-project", path, "project_id is required")
            else:
                projects[slug].append(path)
                if path != f"projects/{slug}/{slug}.md" or node_id != f"project:{slug}":
                    issue(
                        "error",
                        "canonical-project",
                        path,
                        "canonical path or id disagrees with project_id",
                    )
        elif isinstance(node_id, str) and node_id.startswith("project:"):
            issue(
                "error",
                "canonical-project",
                path,
                "project id requires node_role: project",
            )
        entrypoint = meta.get("skill_entrypoint")
        if meta.get("type") == "skill" and not entrypoint:
            issue(
                "error",
                "skill-entrypoint",
                path,
                "skill graph node requires skill_entrypoint",
            )
        if isinstance(entrypoint, str):
            expected = f"{Path(path).parent.as_posix()}/SKILL.md"
            if entrypoint != expected or entrypoint not in files:
                issue(
                    "error",
                    "skill-entrypoint",
                    path,
                    "skill entrypoint must be the existing sibling SKILL.md",
                )

    for node_id, paths in ids.items():
        if len(paths) > 1:
            issue("error", "duplicate-id", ", ".join(paths), f"duplicate id: {node_id}")
    for name, paths in concept_names.items():
        if len(paths) > 1:
            issue(
                "error",
                "duplicate-concept",
                ", ".join(sorted(paths)),
                f"colliding concept key or alias: {name}",
            )

    project_files = sorted(
        path for path in files if re.fullmatch(r"projects/[^/]+/project.yaml", path)
    )
    known_slugs = {Path(path).parent.name for path in project_files}
    for slug in sorted(known_slugs | projects.keys()):
        candidates = projects.get(slug, [])
        if len(candidates) != 1:
            issue(
                "error",
                "canonical-project",
                f"projects/{slug}",
                f"expected one canonical project node, found {len(candidates)}",
            )
        config = f"projects/{slug}/project.yaml"
        if config not in files:
            issue("error", "canonical-project", config, "project.yaml is missing")
        else:
            match = re.search(r"^node:\s*(.+)$", (root / config).read_text(), re.MULTILINE)
            try:
                target = scalar(match[1]) if match else ""
            except ValueError:
                target = ""
            if not target or target not in candidates:
                issue(
                    "error",
                    "canonical-project",
                    config,
                    "node must point to the canonical project note",
                )
    for path, node in nodes.items():
        slug = node.metadata.get("project_id")
        if isinstance(slug, str) and slug and slug not in known_slugs:
            issue(
                "error",
                "canonical-project",
                path,
                "project_id has no registered project",
            )

    supersession: defaultdict[str, set[str]] = defaultdict(set)
    for path in markdown:
        node = nodes.get(path)
        links = [("body", match[1]) for match in WIKI.finditer(visible_text(bodies[path]))]
        if node:
            for relation in sorted(RELATIONS):
                values = node.metadata.get(relation, [])
                assert isinstance(values, list)
                for value in values:
                    match = WIKI.fullmatch(value)
                    if not match:
                        issue(
                            "error",
                            "graph-relation",
                            path,
                            f"{relation}: expected a single wikilink",
                        )
                    elif "#" in match[1]:
                        issue(
                            "error",
                            "graph-relation",
                            path,
                            f"{relation}: link to a whole node, not a heading",
                        )
                    else:
                        links.append((relation, match[1]))
        for relation, raw in links:
            target, error = resolve_wiki(raw, path, files)
            if error:
                issue("error", "wikilink", path, error)
                continue
            assert target is not None
            if not has_anchor(raw, bodies.get(target, "")):
                issue("error", "wikilink", path, f"missing heading or block in {target}")
                continue
            if relation in RELATIONS and target not in nodes:
                issue(
                    "error",
                    "graph-relation",
                    path,
                    f"{relation}: target is not canonical Knowledge: {target}",
                )
                continue
            if relation in {"domains", "project"}:
                target_meta = nodes[target].metadata
                if relation == "domains" and target_meta.get("type") != "concept":
                    issue("error", "graph-relation", path, "domains must target concepts")
                if relation == "project" and target_meta.get("node_role") != "project":
                    issue(
                        "error",
                        "graph-relation",
                        path,
                        "project must target a canonical project",
                    )
                elif (
                    relation == "project"
                    and node
                    and node.metadata.get("project_id")
                    and node.metadata["project_id"] != target_meta.get("project_id")
                ):
                    issue(
                        "error",
                        "graph-relation",
                        path,
                        "project link disagrees with project_id",
                    )
            if relation == "conflicts_with" and nodes[target].metadata.get("type") != "decision":
                issue(
                    "error",
                    "graph-relation",
                    path,
                    "conflicts_with must target a Decision",
                )
            if relation in {"supersedes", "superseded_by"}:
                if node and node.metadata.get("type") != nodes[target].metadata.get("type"):
                    issue(
                        "error",
                        "supersedes",
                        path,
                        "supersession must keep the knowledge type",
                    )
                newer, older = (path, target) if relation == "supersedes" else (target, path)
                supersession[newer].add(older)
                if nodes[older].metadata.get("status") != "superseded":
                    issue(
                        "error",
                        "supersedes",
                        older,
                        "superseded target must have status: superseded",
                    )
            all_edges.add((path, target))
            if path in nodes and target in nodes:
                edges.add((path, relation, target))
        for match in MARKDOWN.finditer(visible_text(bodies[path])):
            raw = unquote(match[1].strip("<>").split("#", 1)[0])
            if not raw or re.match(r"[a-zA-Z][a-zA-Z0-9+.-]*:", raw):
                continue
            resolved = (root / path).parent.joinpath(raw).resolve()
            if not resolved.is_relative_to(root):
                continue
            target = resolved.relative_to(root).as_posix()
            if target in files:
                all_edges.add((path, target))
                if path in nodes and target in nodes:
                    edges.add((path, "body", target))

    for path in cycle_nodes(supersession):
        issue("error", "circular-supersedes", path, "supersession cycle detected")
    linked = {p for a, b in all_edges if a != b for p in (a, b)}
    graph = Graph(nodes, edges, issues, markdown, sorted(set(markdown) - nodes.keys() - linked))
    for path in graph.summary()["orphans"]:
        issue(
            "warning",
            "orphan-knowledge",
            path,
            "no incoming or outgoing link to other Knowledge",
        )
    return graph
