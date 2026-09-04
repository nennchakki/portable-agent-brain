"""Deterministic lexical ranking with explicit, small bilingual term groups."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from .catalog import BrainError, Catalog, Document

# Query expansion is explicit, generic vocabulary. It deliberately avoids
# product-, framework-, and user-specific tuning so every new library starts
# with the same neutral retrieval behavior.
TERM_GROUPS = (
    ("architecture", "design", "structure", "構成", "設計"),
    ("bug", "debug", "error", "failure", "不具合", "エラー"),
    ("test", "testing", "verification", "テスト", "検証"),
    ("build", "compile", "package", "ビルド", "コンパイル"),
    ("documentation", "docs", "readme", "文書", "ドキュメント"),
    ("security", "privacy", "credential", "セキュリティ", "プライバシー"),
    ("data", "dataset", "records", "データ"),
    ("import", "export", "extract", "parse", "取込", "抽出"),
)
STOP_WORDS = {
    "a",
    "an",
    "the",
    "and",
    "or",
    "for",
    "to",
    "in",
    "of",
    "を",
    "の",
    "で",
    "に",
    "する",
    "追加",
    "書く",
}
# These words describe many tasks, not a particular workflow. They remain
# searchable, but cannot give a partial ID/title a dominant relevance score.
GENERIC_TERMS = {
    "source",
    "data",
    "document",
    "export",
    "file",
    "project",
    "workflow",
    "knowledge",
    "context",
    "task",
    "report",
    "確認",
    "検証",
    "変更",
    "修正",
    "直す",
    "作る",
    "揃え",
    "指定",
    "だけ",
    "場合",
    "必要",
    "保存",
    "取得",
    "など",
}
AUTHORITY_BOOSTS = {
    "canonical": 0,
    "verified": 0,
    "observed": -300,
    "candidate": -1000,
    "rejected": -100000,
    "superseded": -100000,
}
LATIN = re.compile(r"[a-z0-9\u0370-\u03ff]+(?:[-_./=+][a-z0-9\u0370-\u03ff]+)*")
JAPANESE = re.compile(r"[\u3040-\u30ff\u3400-\u9fffー]+")


def normalize(text: str) -> str:
    """Normalize width/case while preserving technical punctuation."""
    return unicodedata.normalize("NFKC", text).casefold()


def contains(text: str, term: str) -> bool:
    """Match technical tokens exactly, including next to Japanese particles."""
    if LATIN.fullmatch(term):
        boundary = r"a-z0-9_\u0370-\u03ff"
        if any(character in term for character in "-_./=+"):
            boundary += r"./=+\-"
        return re.search(rf"(?<![{boundary}]){re.escape(term)}(?![{boundary}])", text) is not None
    return term in text


def query_terms(query: str, *, expand: bool = True) -> tuple[list[str], list[str]]:
    """Return original lexical terms and separately attributed expansion terms."""
    normalized = normalize(query.strip())
    terms = LATIN.findall(normalized)
    for run in JAPANESE.findall(normalized):
        terms.extend(piece for piece in re.split("[はがをにのとでへもや]", run) if len(piece) > 1)
    terms = sorted(set(terms) - STOP_WORDS)
    expansions: set[str] = set()
    if expand:
        for group in TERM_GROUPS:
            if any(contains(normalized, value) for value in group):
                expansions.update(group)
    return terms, sorted(expansions - set(terms))


@dataclass
class Hit:
    """One explainable result without a full Knowledge body."""

    path: str
    id: str
    title: str
    type: str
    project: str
    domains: list[str]
    status: str
    authority: str
    score: int
    reasons: list[str]
    signals: dict[str, object] = field(default_factory=dict)


def infer_projects(catalog: Catalog, query: str) -> set[str]:
    """Find named Projects without converting topic similarity into membership."""
    text = normalize(query)
    terms, _ = query_terms(query, expand=False)
    matches: set[str] = set()
    for slug, project in catalog.projects.items():
        doc = catalog.documents[project.node]
        names = [slug, doc.title, *doc.values("aliases")]
        if any(contains(text, normalize(name)) for name in names):
            matches.add(slug)
    for term in terms:
        if len(term) < 4:
            continue
        prefixes = {slug for slug in catalog.projects if slug.startswith(term + "-")}
        if len(prefixes) == 1:
            matches.update(prefixes)
    return matches


def eligible(document: Document, include_superseded: bool) -> bool:
    """Include marked candidates, while excluding rejected and old history by default."""
    if document.authority == "rejected":
        return False
    if document.status == "pending" and document.authority not in {
        "candidate",
        "observed",
    }:
        return False
    return include_superseded or document.authority != "superseded"


def search(
    catalog: Catalog,
    query: str,
    *,
    project: str | None = None,
    limit: int = 5,
    include_superseded: bool = False,
    paths: set[str] | None = None,
    preferred_project: str | None = None,
) -> list[Hit]:
    """Rank project identity, exact title and direct task evidence above domains.

    Bodies are streamed line by line. The corpus is not cached or returned.

    Args:
        catalog: Operation-local metadata catalog.
        query: Literal task or search text.
        project: Optional strict project_id filter.
        limit: Maximum results (1 through 50).
        include_superseded: Explicit history opt-in.
        paths: Optional safe subset for callers.
        preferred_project: Ranking boost without changing the strict project filter.

    Returns:
        Stable ordered hits with match reasons.
    """
    catalog.require_project(project)
    catalog.require_project(preferred_project)
    if not query.strip() or len(query) > 1000 or not 1 <= limit <= 50:
        raise BrainError("query must be 1–1000 characters and limit must be 1–50")
    original, expanded = query_terms(query)
    all_terms = original + expanded
    if not all_terms:
        return []
    named = (
        {project or preferred_project}
        if project or preferred_project
        else infer_projects(catalog, query)
    )
    normalized_query = normalize(query.strip())
    intents = [
        group for group in TERM_GROUPS if any(contains(normalized_query, term) for term in group)
    ]
    grouped_terms = {term for group in intents for term in group}
    intents.extend((term,) for term in original if term not in GENERIC_TERMS | grouped_terms)
    results: list[Hit] = []
    eligible_count = 0
    for path, doc in sorted(catalog.documents.items()):
        if paths is not None and path not in paths:
            continue
        if project is not None and doc.project != project:
            continue
        if not eligible(doc, include_superseded):
            continue
        eligible_count += 1
        aliases = [normalize(doc.title), *(normalize(x) for x in doc.values("aliases"))]
        exact = normalized_query in aliases
        project_match = doc.project in named if doc.project else False
        metadata_text = normalize(
            " ".join([doc.id, doc.project, *doc.values("domain_ids"), *doc.values("domains")])
        )
        if doc.kind == "concept":
            metadata_text += " " + " ".join(aliases)
        relation_text = normalize(
            " ".join(
                value
                for key in (
                    "related",
                    "uses",
                    "depends_on",
                    "implements",
                    "prevents",
                    "caused_by",
                    "conflicts_with",
                )
                for value in doc.values(key)
            )
        )
        meta_matches = {term for term in all_terms if contains(metadata_text, term)}
        relation_matches = {term for term in all_terms if contains(relation_text, term)}
        heading_matches: set[str] = set()
        body_matches: set[str] = set()
        with (catalog.root / path).open(encoding="utf-8") as stream:
            stream.seek(doc.body_offset)
            catalog.metrics["body_files_scanned"] += 1
            for line in stream:
                catalog.metrics["body_chars_scanned"] += len(line)
                lowered = normalize(line)
                found = {term for term in all_terms if contains(lowered, term)}
                body_matches.update(found)
                if line.startswith("#"):
                    heading_matches.update(found)
        title_matches = {
            term for term in all_terms if any(contains(alias, term) for alias in aliases)
        }
        heading_matches.update(title_matches)
        matched = meta_matches | relation_matches | heading_matches | body_matches
        if not exact and not matched:
            continue
        specific = set(original) - GENERIC_TERMS
        translated = set(expanded) - GENERIC_TERMS
        title_direct = specific & title_matches
        heading_direct = specific & heading_matches
        body_direct = specific & body_matches
        translated_title = translated & title_matches
        translated_body = translated & body_matches
        lexical_score = min(
            100_000,
            4000 * len(title_direct)
            + 1500 * len(heading_direct - title_direct)
            + 1000 * len(body_direct)
            + 300 * len(translated_title)
            + 150 * len(translated_body)
            + 2 * len(set(original) & GENERIC_TERMS & matched),
        )
        domain_score = min(
            2000,
            80 * len(specific & meta_matches) + 20 * len(translated & meta_matches),
        )
        relation_score = min(100, 10 * len((specific | translated) & relation_matches))
        intent_coverage = sum(any(term in matched for term in group) for group in intents)
        coverage_score = 2000 * max(0, intent_coverage - 1)
        score = (
            2_000_000 * project_match
            + 1_000_000 * exact
            + lexical_score
            + domain_score
            + relation_score
            + coverage_score
            + AUTHORITY_BOOSTS[doc.authority]
        )
        # Without a named Project, a scoped rule needs slightly more evidence
        # than generally applicable knowledge. Never infer another Project's rule
        # merely from a shared generic topic.
        scope_penalty = 500 if doc.project and not named and not exact else 0
        score -= scope_penalty
        reasons: list[str] = []
        if exact:
            reasons.append("exact title/alias")
        if project_match:
            reasons.append(f"project={doc.project}")
        for label, matches in (
            ("domain/id", meta_matches),
            ("heading", heading_matches),
            ("relation", relation_matches),
            ("body", body_matches),
        ):
            if matches:
                reasons.append(f"{label}=" + ", ".join(sorted(matches)[:8]))
        if set(expanded) & matched:
            reasons.append("expanded=" + ", ".join(sorted(set(expanded) & matched)[:6]))
        results.append(
            Hit(
                path,
                doc.id,
                doc.title,
                doc.kind,
                doc.project,
                doc.values("domains"),
                doc.status,
                doc.authority,
                score,
                reasons,
                {
                    "project_match": project_match,
                    "exact_title": exact,
                    "lexical_score": lexical_score,
                    "domain_score": domain_score,
                    "relation_score": relation_score,
                    "unscoped_project_penalty": scope_penalty,
                    "intent_coverage": intent_coverage,
                    "coverage_score": coverage_score,
                    "authority_score": AUTHORITY_BOOSTS[doc.authority],
                    "direct_title_terms": sorted(title_direct),
                    "direct_body_terms": sorted(body_direct),
                    "expanded_title_terms": sorted(translated_title),
                    "generic_terms": sorted(set(original) & GENERIC_TERMS & matched),
                },
            )
        )
    # Document frequency is computed from the same streamed search, never from
    # a persistent body cache. Rare task terms can qualify a body-only hit;
    # ubiquitous vocabulary cannot open every shared workflow.
    frequency: dict[str, int] = {}
    for hit in results:
        for term in hit.signals["direct_body_terms"]:
            frequency[term] = frequency.get(term, 0) + 1
    for hit in results:
        hit.signals["rare_body_terms"] = [
            term
            for term in hit.signals["direct_body_terms"]
            if frequency[term] <= max(1, eligible_count // 10)
        ]
    return sorted(results, key=lambda hit: (-hit.score, hit.path))[:limit]
