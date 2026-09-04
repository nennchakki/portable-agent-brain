"""Relation-aware candidate selection; graph adjacency is not applicability."""

from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass, field

from .catalog import Catalog, Document, Project
from .search import Hit, contains, eligible, normalize, search
from .tasking import TASK_HINTS, TaskProfile

MIN_CONTEXT_SCORE = 600
DIRECT_TASK_CUTOFF = 1500
RELATION_WEIGHTS = {
    "project": 1200,
    "inverse:project": 1200,
    "depends_on": 1200,
    "uses": 1000,
    "prevents": 1000,
    "implements": 900,
    "caused_by": 800,
    "conflicts_with": 1600,
    "related": 200,
    "domains": 50,
    "inverse:depends_on": 150,
    "inverse:uses": 100,
    "inverse:implements": 150,
    "inverse:prevents": 300,
    "inverse:caused_by": 150,
    "inverse:conflicts_with": 50,
    "inverse:related": 100,
    "inverse:domains": 25,
    "supersedes": 200,
    "superseded_by": 200,
    "inverse:supersedes": 100,
    "inverse:superseded_by": 100,
}


@dataclass
class Candidate:
    """One candidate with a complete winning edge path and numeric evidence."""

    path: str
    score: int
    search_score: int
    task_score: int = 0
    graph_score: int = 0
    hop: int = 0
    reasons: list[str] = field(default_factory=list)
    reason_codes: list[str] = field(default_factory=list)
    route: list[dict[str, object]] = field(default_factory=list)


def task_affinity(document: Document, task_type: str) -> int:
    """Score declared metadata against the small task taxonomy."""
    text = normalize(
        " ".join(
            [
                document.path,
                document.id,
                document.title,
                *document.values("domain_ids"),
                *document.values("domains"),
            ]
        )
    )
    matches = sum(contains(text, normalize(hint)) for hint in TASK_HINTS.get(task_type, ()))
    score = min(2400, 450 * matches)
    if task_type == "architecture" and (
        "architecture" in document.path or document.kind == "decision"
    ):
        score += 800
    return score


def context_search_score(hit: Hit | None) -> int:
    """Remove the search command's Project identity boost from context ranking."""
    if hit is None:
        return 0
    signals = hit.signals
    return int(
        (100000 if signals["exact_title"] else 0)
        + signals["lexical_score"]
        + signals["domain_score"]
        + signals["relation_score"]
        + signals["coverage_score"]
        + signals["authority_score"]
    )


def hit_reason_codes(hit: Hit | None) -> list[str]:
    """Convert detailed search signals to stable categorical reason codes."""
    if hit is None:
        return []
    signals = hit.signals
    codes: list[str] = []
    for condition, code in (
        (signals["exact_title"], "query_exact_title"),
        (signals["direct_title_terms"], "query_title"),
        (signals["rare_body_terms"], "query_body_rare"),
        (signals["coverage_score"], "query_multi_intent"),
    ):
        if condition:
            codes.append(code)
    terms = [*signals["direct_title_terms"], *signals["rare_body_terms"]]
    for term in terms:
        safe = re.sub(r"[^a-z0-9]+", "_", str(term).casefold()).strip("_")
        if safe and len(safe) <= 32:
            codes.append("query_term_" + safe)
        if len(codes) >= 6:
            break
    return codes or ["query_direct"]


def relation_weight(relation: str, task_type: str) -> int:
    """Adjust relation evidence only where the task gives it operational meaning."""
    weight = RELATION_WEIGHTS.get(relation, 0)
    base = relation.removeprefix("inverse:")
    if base == "prevents":
        if task_type in {"ui", "debugging", "build", "testing", "security"}:
            weight += 300
        elif task_type == "writing":
            weight = min(weight, 500)
    elif (base == "depends_on" and task_type in {"architecture", "build", "testing"}) or (
        base == "implements" and task_type in {"architecture", "implementation"}
    ):
        weight += 200
    return weight


def qualified(hit: Hit | None) -> bool:
    """Require direct task evidence; a domain or generic body word is insufficient."""
    if hit is None:
        return False
    evidence = hit.signals
    return bool(
        evidence["exact_title"]
        or (
            evidence["lexical_score"] >= MIN_CONTEXT_SCORE
            and (
                evidence["direct_title_terms"]
                or evidence["expanded_title_terms"]
                or evidence["rare_body_terms"]
            )
        )
    )


def candidates(
    catalog: Catalog,
    policy: Project,
    query: str,
    *,
    hops: int,
    min_score: int,
    include_superseded: bool,
    include_concepts: bool,
    task: TaskProfile,
    trace: dict[str, object] | None,
) -> dict[str, Candidate]:
    """Generate bounded candidates and reject unqualified weak traversal.

    Args:
        catalog: Metadata-only Knowledge catalog.
        policy: Registered Project and its task-aware context policy.
        query: Actual task query.
        hops: Maximum edges from a qualifying seed.
        min_score: Minimum optional-item score, not a Knowledge confidence value.
        include_superseded: Explicit historical opt-in.
        include_concepts: Explicit request for Concept bodies.
        task: Explicit or inferred task profile.
        trace: Optional diagnostics sink, never part of the Agent bundle.

    Returns:
        At most 48 candidates, including required policy entries.
    """
    scope = {
        path
        for path, doc in catalog.documents.items()
        if doc.project in ("", policy.slug) and eligible(doc, include_superseded)
    }
    hits = search(
        catalog,
        query,
        paths=scope,
        preferred_project=policy.slug,
        limit=50,
        include_superseded=include_superseded,
    )
    indexed = {hit.path: hit for hit in hits}
    task_required = set(policy.task_include.get(task.task_type, []))
    required = {policy.node, *policy.required_for(task.task_type)}
    result: dict[str, Candidate] = {}
    rejected: dict[str, str] = {}

    def add(
        path: str,
        reason: str,
        reason_code: str,
        route: list[dict[str, object]],
    ) -> bool:
        """Retain the strongest explainable route, without filling an item quota."""
        if path not in scope:
            return False
        hit = indexed.get(path)
        lexical = context_search_score(hit)
        affinity = task_affinity(catalog.documents[path], task.task_type)
        graph_score = min((edge["weight"] for edge in route), default=0) // max(1, len(route))
        score = lexical + affinity + graph_score
        if catalog.documents[path].project == policy.slug:
            score += 400
        if path not in required and score < min_score:
            rejected[path] = "below relevance threshold"
            return False
        if (
            catalog.documents[path].kind == "concept"
            and not include_concepts
            and path not in required
        ):
            rejected[path] = "navigation only: Concept body omitted"
            return False
        if path not in result and len(result) >= 48:
            rejected[path] = "candidate bound"
            return False
        previous = result.get(path)
        if previous and previous.score >= score:
            return False
        reasons = [
            *(
                item
                for item in (previous.reasons if previous else [])
                if not item.startswith("graph(")
            ),
            reason,
        ]
        reason_codes = [
            *(
                item
                for item in (previous.reason_codes if previous else [])
                if not item.startswith("relation_")
            ),
            reason_code,
        ]
        if hit and qualified(hit):
            reasons.append(f"context lexical score={lexical}")
            reason_codes.extend(hit_reason_codes(hit))
        result[path] = Candidate(
            path=path,
            score=score,
            search_score=lexical,
            task_score=affinity,
            graph_score=graph_score,
            hop=len(route),
            reasons=list(dict.fromkeys(reasons))[:2],
            reason_codes=list(dict.fromkeys(reason_codes))[:8],
            route=route,
        )
        rejected.pop(path, None)
        return True

    add(policy.node, "project canonical node", "project_exact", [])
    for path in sorted(required - {policy.node}):
        if path in task_required:
            reason = f"project.yaml task_include.{task.task_type}"
            code = f"task_type_{task.task_type}"
        else:
            reason = "project.yaml always_include"
            code = "project_policy_always"
        add(
            path,
            reason,
            code,
            [],
        )
    for hit in hits:
        if qualified(hit):
            lexical = context_search_score(hit)
            if (
                hit.path not in required
                and task.source != "project_metadata"
                and not hit.signals["exact_title"]
                and lexical < DIRECT_TASK_CUTOFF
            ):
                rejected[hit.path] = "below direct task evidence cutoff"
                continue
            add(hit.path, "direct task evidence", "query_direct", [])
        elif hit.path not in result:
            rejected[hit.path] = "no direct task evidence (domain/generic terms only)"
    queue = deque((path, [], {path}) for path in list(result))
    while queue:
        source, route, visited = queue.popleft()
        if len(route) >= hops:
            continue
        source_doc = catalog.documents[source]
        for relation, target in catalog.adjacency.get(source, []):
            if target not in scope or target in visited:
                continue
            if not include_superseded and relation.removeprefix("inverse:") in {
                "supersedes",
                "superseded_by",
            }:
                continue
            weight = relation_weight(relation, task.task_type)
            target_doc = catalog.documents[target]
            project_link = source_doc.project == policy.slug and target_doc.project == policy.slug
            if project_link:
                weight = max(weight, 1200)
            target_hit = indexed.get(target)
            target_lexical = context_search_score(target_hit)
            target_affinity = task_affinity(target_doc, task.task_type)
            if (
                task.source != "project_metadata"
                and target not in required
                and target_affinity < 900
                and not (
                    qualified(target_hit)
                    and (
                        task.source == "project_metadata"
                        or target_hit.signals["exact_title"]
                        or target_lexical >= DIRECT_TASK_CUTOFF
                    )
                )
            ):
                rejected.setdefault(target, "relation is not task-aligned")
                continue
            # Reverse links to a broad Principle or Concept are not instructions
            # to apply all workflows referencing that node.
            strong = weight >= 800 and source_doc.kind != "concept"
            if not strong and not qualified(indexed.get(target)):
                rejected.setdefault(target, "weak relation without direct task evidence")
                continue
            next_route = [
                *route,
                {
                    "source": source,
                    "relation": relation,
                    "target": target,
                    "weight": weight,
                },
            ]
            if add(
                target,
                f"graph({len(next_route)}): {source} [{relation}]",
                "relation_" + relation.replace(":", "_"),
                next_route,
            ):
                queue.append((target, next_route, visited | {target}))
    if trace is not None:
        trace.update(
            {
                "min_score": min_score,
                "direct_task_cutoff": DIRECT_TASK_CUTOFF,
                "task_type": task.task_type,
                "relation_weights": RELATION_WEIGHTS,
                "search": [
                    {
                        "id": hit.id,
                        "path": hit.path,
                        "score": hit.score,
                        "signals": hit.signals,
                    }
                    for hit in hits
                ],
                "candidates": [
                    {
                        "id": catalog.documents[path].id,
                        "score": item.score,
                        "search_score": item.search_score,
                        "task_score": item.task_score,
                        "graph_score": item.graph_score,
                        "reason_codes": item.reason_codes,
                        "route": item.route,
                    }
                    for path, item in result.items()
                ],
                "rejected": [
                    {"id": catalog.documents[path].id, "reason": reason}
                    for path, reason in sorted(rejected.items())
                    if path not in result
                ],
            }
        )
    return result


def anchors(catalog: Catalog, document: Document) -> set[str]:
    """Resolve canonical topic/rule anchors instead of comparing display aliases."""
    result = {"project:" + document.project} if document.project else set()
    for relation in ("domains", "implements"):
        result.update(catalog.resolve(value) for value in document.values(relation))
    return result


def content_lines(text: str) -> set[str]:
    """Ignore display titles/list numbering, keeping each line's section conditions."""
    result: set[str] = set()
    headings: dict[int, str] = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        heading = re.match(r"^(#{1,6}) (.+)", line)
        if heading:
            level = len(heading[1])
            headings = {key: value for key, value in headings.items() if key < level}
            if level > 1:
                headings[level] = line.strip()
            continue
        content = re.sub(r"^(?:[-*]|\d+[.)])\s+", "", line.strip())
        result.add("\n".join([*headings.values(), content]))
    return result


def redundant(
    catalog: Catalog,
    document: Document,
    text: str,
    selected: list[tuple[Document, str]],
) -> str | None:
    """Suppress a covered explanation only when its canonical anchors also match.

    Decisions, Rules and Lessons remain separate evidence even when their advice
    overlaps. New conditions, provenance, sentences, numbers or negations prevent
    this conservative merge.
    """
    if document.kind in {"decision", "project-rule", "lesson"}:
        return None
    lines = content_lines(text)
    if len("".join(lines)) < 40:
        return None
    topic = anchors(catalog, document)
    for previous, previous_text in selected:
        if previous.status != document.status or not topic & anchors(catalog, previous):
            continue
        if any(
            previous.metadata.get(key) != document.metadata.get(key)
            for key in ("confidence", "source_type")
        ):
            continue
        if lines <= content_lines(previous_text):
            return previous.id
    return None
