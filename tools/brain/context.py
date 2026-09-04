"""Build small, source-faithful context bundles with bounded graph traversal."""

from __future__ import annotations

import json
import re

from .catalog import BrainError, Catalog, Document
from .search import contains, normalize, query_terms
from .selection import MIN_CONTEXT_SCORE, candidates, redundant
from .tasking import TASK_TYPES, classify_task


def render_json(bundle: dict[str, object]) -> str:
    """Serialize a bundle without printing or changing its content."""
    return json.dumps(bundle, ensure_ascii=False, separators=(",", ":")) + "\n"


def render_text(bundle: dict[str, object]) -> str:
    """Render the same structured bundle as human-readable source excerpts."""
    task_type = (
        f"Task type: {bundle['task_type']} ({bundle['task_type_source']}, "
        f"confidence={bundle['task_type_confidence']})"
    )
    recommendation = (
        f"Context recommendation: {bundle['context_recommendation']} — "
        f"{bundle['context_recommendation_reason']}"
    )
    lines = [
        f"# Context: {bundle['project']}",
        f"Task: {bundle['query']}",
        task_type,
        recommendation,
        "Source excerpts, not automatic authority; respect status and task scope.",
        "Concepts (navigation only): " + ", ".join(bundle.get("concepts", [])),
    ]
    for item in bundle["items"]:
        lines.extend(
            [
                "",
                f"## {item['title']} [{item['type']}; {item['status']}]",
                f"Source: {item['path']}",
                f"ID: {item['id']}",
                f"Authority: {item['authority']}",
                f"Provenance: confidence={item['confidence']}; source_type={item['source_type']}",
            ]
        )
        if item.get("warning"):
            lines.append("Warning: " + item["warning"])
        if item.get("conflicts_with"):
            lines.append("Conflicts with: " + ", ".join(item["conflicts_with"]))
        lines.extend(
            [
                "Reason codes: " + ", ".join(item["reason_codes"]),
                "Why: " + "; ".join(item["reasons"]),
                f"Excerpt truncated: {str(item['excerpt_truncated']).lower()}",
                "",
                item["excerpt"],
            ]
        )
    lines.extend(
        [
            "",
            (
                f"Omitted: {bundle['omitted_count']}; required omitted: "
                f"{bundle['omitted_required_count']}"
            ),
            (
                f"Budget: target {bundle['target_chars']} / hard {bundle['max_chars']} "
                "characters (entire text and compact JSON)."
            ),
        ]
    )
    return "\n".join(lines) + "\n"


def bundle_size(bundle: dict[str, object]) -> int:
    """Budget both wire representations, including metadata and provenance."""
    return max(len(render_text(bundle)), len(render_json(bundle)))


def priority(doc: Document, project: str, canonical: str, always: set[str]) -> int:
    """Prioritize current project decisions/rules over generic related notes."""
    if doc.path == canonical:
        return 0
    if doc.path in always:
        return 5
    if doc.authority == "candidate":
        return 100
    if doc.authority == "observed":
        return 95
    if doc.authority in {"rejected", "superseded"}:
        return 110
    if doc.project == project:
        if doc.kind == "decision" and doc.status == "active":
            return 10
        if doc.kind == "project-rule":
            return 20
        if doc.kind == "lesson":
            return 30
    if doc.project == project and doc.kind == "project-knowledge":
        return 45
    return {"protocol": 50, "concept": 90, "lesson": 48, "reference": 80}.get(doc.kind, 90)


def excerpt(body: str, query: str, limit: int) -> tuple[str, bool]:
    """Select original heading sections, then complete lines, without summarizing."""
    if len(body) <= limit:
        return body.strip(), False
    sections = [
        part.strip() for part in re.split(r"(?=^#{1,6} )", body, flags=re.MULTILINE) if part.strip()
    ]
    terms, expanded = query_terms(query)
    important = (
        "invariant",
        "decision",
        "correct approach",
        "prevention",
        "verification",
        "rules",
    )
    ranked = sorted(
        enumerate(sections),
        key=lambda pair: (
            -any(word in normalize(pair[1].splitlines()[0]) for word in important),
            -sum(contains(normalize(pair[1]), term) for term in terms + expanded),
            pair[0],
        ),
    )
    chosen: dict[int, str] = {}
    remaining = limit
    for index, section in ranked:
        cost = len(section) + (2 if chosen else 0)
        if cost <= remaining:
            chosen[index] = section
            remaining -= cost
        elif not chosen and remaining > 0:
            lines: list[str] = []
            for line in section.splitlines():
                if len("\n".join([*lines, line])) > remaining:
                    break
                lines.append(line)
            partial = "\n".join(lines)
            chosen[index] = partial if partial.strip() else section[:remaining]
            remaining -= len(chosen[index])
    return "\n\n".join(chosen[index] for index in sorted(chosen)), True


def build_context(
    catalog: Catalog,
    project: str,
    query: str,
    *,
    max_chars: int = 12000,
    hops: int = 1,
    max_items: int = 12,
    include_superseded: bool = False,
    include_concepts: bool = False,
    min_score: int = MIN_CONTEXT_SCORE,
    task_type: str | None = None,
    trace: dict[str, object] | None = None,
) -> dict[str, object]:
    """Select project policy and relevant graph neighbors under a hard output budget.

    Args:
        catalog: Metadata-only catalog.
        project: Exact registered slug.
        query: Current task.
        max_chars: Entire rendered-output budget.
        hops: One by default; two only by explicit request.
        max_items: Additional anti-dump bound, never more than twenty.
        include_superseded: Explicit historical opt-in.
        include_concepts: Opt in to Concept bodies, normally navigation metadata only.
        min_score: Minimum optional relevance score; not provenance confidence.
        task_type: Optional explicit task type; otherwise infer it transparently.
        trace: Optional diagnostic sink, outside the budgeted Agent context.

    Returns:
        JSON-compatible bundle, not a printed response.
    """
    policy = catalog.require_project(project)
    assert policy is not None
    if (
        not 1024 <= max_chars <= 100000
        or hops not in (1, 2)
        or not 1 <= max_items <= 20
        or type(min_score) is not int
        or not 0 <= min_score <= 100000
    ):
        raise BrainError(
            "context requires max-chars 1024–100000, hops 1–2, max-items 1–20, min-score 0–100000"
        )
    try:
        task = classify_task(
            query,
            project_type=policy.project_type,
            project_domains=policy.domains,
            explicit=task_type,
        )
    except ValueError as error:
        raise BrainError("unknown task type; choose one of: " + ", ".join(TASK_TYPES)) from error
    target_chars = min(max_chars, task.soft_max_chars)
    target_items = min(max_items, task.soft_max_items)
    bundle: dict[str, object] = {
        "project": project,
        "query": query,
        "task_type": task.task_type,
        "task_type_source": task.source,
        "task_type_confidence": task.confidence,
        "complexity": task.complexity,
        "context_recommended": task.context_recommended,
        "context_recommendation": "use" if task.context_recommended else "skip",
        "context_recommendation_reason": task.recommendation_reason,
        "max_chars": max_chars,
        "target_chars": target_chars,
        "max_items": max_items,
        "target_items": target_items,
        "hops": hops,
        "items": [],
        "candidate_items": 0,
        "omitted_count": 0,
        "omitted_required_count": 0,
        "candidate_limit": 48,
        "concepts": [],
        "deduplicated_count": 0,
    }
    if bundle_size(bundle) > target_chars:
        raise BrainError("budget is too small for query and provenance metadata")
    if not task.context_recommended:
        if trace is not None:
            trace.update(
                {
                    "task_type": task.task_type,
                    "task_type_source": task.source,
                    "context_recommendation": "skip",
                }
            )
        return bundle
    options = candidates(
        catalog,
        policy,
        query,
        hops=hops,
        min_score=min_score,
        include_superseded=include_superseded,
        include_concepts=include_concepts,
        task=task,
        trace=trace,
    )
    required = {policy.node, *policy.required_for(task.task_type)}
    bundle["omitted_count"] = len(options)
    bundle["omitted_required_count"] = len(required)
    selected: set[str] = set()
    selected_texts: list[tuple[Document, str]] = []
    ordered = sorted(
        options,
        key=lambda p: (
            priority(
                catalog.documents[p],
                project,
                policy.node,
                set(policy.required_for(task.task_type)),
            ),
            -options[p].score,
            p,
        ),
    )
    for path in ordered:
        if len(selected) >= target_items:
            break
        doc = catalog.documents[path]
        item = {
            "id": doc.id,
            "path": path,
            "title": doc.title,
            "type": doc.kind,
            "status": doc.status,
            "authority": doc.authority,
            "confidence": doc.metadata.get("confidence", "unspecified"),
            "source_type": doc.metadata.get("source_type", "unspecified"),
            "reasons": options[path].reasons,
            "reason_codes": options[path].reason_codes,
            "hop": options[path].hop,
            "excerpt": "",
            "excerpt_truncated": True,
        }
        if doc.authority in {"candidate", "observed"}:
            item["warning"] = (
                "Unverified task observation; do not override current source or active Knowledge."
            )
            item["evidence_count"] = doc.evidence_count
            item["last_observed"] = doc.metadata.get("last_observed", "unspecified")
        conflicts = [
            catalog.documents[catalog.resolve(raw)].id for raw in doc.values("conflicts_with")
        ]
        if conflicts:
            item["conflicts_with"] = conflicts
            item["warning"] = (
                "Unverified task observation with a possible conflict; active Knowledge "
                "wins until human review."
            )
        bundle["items"].append(item)
        if bundle_size(bundle) + 120 > target_chars:
            bundle["items"].pop()
            break
        with (catalog.root / path).open(encoding="utf-8") as stream:
            stream.seek(doc.body_offset)
            body = stream.read(200001)
        oversized = len(body) > 200000
        body = body[:200000]
        allowance = min(
            2200,
            target_chars // 3,
            target_chars - bundle_size(bundle) - 16,
        )
        # Escaping in JSON can increase size; shrink actual excerpts, not JSON bytes.
        while allowance >= 80:
            text, truncated = excerpt(body, query, allowance)
            item["excerpt"], item["excerpt_truncated"] = text, truncated or oversized
            if bundle_size(bundle) <= target_chars:
                break
            allowance -= max(32, bundle_size(bundle) - target_chars)
        if allowance < 80:
            bundle["items"].pop()
            break
        duplicate = (
            redundant(catalog, doc, item["excerpt"], selected_texts)
            if path not in required
            else None
        )
        if duplicate is not None:
            bundle["items"].pop()
            bundle["deduplicated_count"] += 1
            if trace is not None:
                trace.setdefault("deduplicated", []).append({"id": doc.id, "covered_by": duplicate})
            continue
        selected.add(path)
        selected_texts.append((doc, item["excerpt"]))
        if doc.authority == "candidate":
            bundle["candidate_items"] += 1
    bundle["omitted_count"] = len(options) - len(selected)
    bundle["omitted_required_count"] = len(required - selected)
    navigation = sorted(
        {
            catalog.documents[catalog.resolve(raw)].id
            for doc, _ in selected_texts
            for raw in doc.values("domains")
        }
    )
    for identifier in navigation[:8]:
        bundle["concepts"].append(identifier)
        if bundle_size(bundle) > target_chars:
            bundle["concepts"].pop()
            break
    if trace is not None:
        trace["selected"] = [item["id"] for item in bundle["items"]]
        trace["omitted_required_count"] = bundle["omitted_required_count"]
    assert bundle_size(bundle) <= target_chars <= max_chars
    return bundle
