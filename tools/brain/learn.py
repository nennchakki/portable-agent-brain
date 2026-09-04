"""Validate structured candidates and write only pending inbox notes."""

from __future__ import annotations

import json
import os
import re
import secrets
import stat
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from tools.graph import WIKI
from tools.validate import secret_path_kind

from .catalog import BrainError, Catalog
from .search import Hit, normalize, search

MAX_INPUT_BYTES = 65536
CLASSIFICATIONS = {
    "none",
    "fact",
    "preference",
    "constraint",
    "lesson",
    "procedure",
    "decision",
    "protocol",
}
REQUIRED = {
    "fact": ("statement",),
    "preference": ("statement",),
    "constraint": ("statement",),
    "lesson": ("what_happened", "root_cause", "correct_approach", "verification"),
    "procedure": ("steps", "verification"),
    "decision": ("context", "decision", "why"),
    "protocol": ("steps", "verification"),
}
SECTIONS = {
    "statement": "Statement",
    "what_happened": "What happened",
    "root_cause": "Root cause",
    "correct_approach": "Correct approach",
    "prevention": "Prevention",
    "verification": "Verification",
    "context": "Context",
    "decision": "Decision",
    "why": "Why",
    "alternatives_considered": "Alternatives considered",
    "consequences": "Consequences",
    "revisit_when": "Revisit when",
    "steps": "Steps",
    "evidence": "Evidence",
}
ALLOWED = {
    "type",
    "title",
    "project",
    "project_id",
    "domains",
    "domain_ids",
    "related",
    "conflicts_with",
    "confidence",
    "source_type",
    "reason",
    *SECTIONS,
}
SECRET_PATTERNS = (
    r"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----",
    r"\bgh[pousr]_[A-Za-z0-9]{16,}\b",
    r"\bgithub_pat_[A-Za-z0-9_]{16,}\b",
    r"\bsk-[A-Za-z0-9_-]{16,}\b",
    r"\bAKIA[A-Z0-9]{16}\b",
    r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b",
    r"\bBearer\s+[A-Za-z0-9._~+/-]+=*",
    (
        r"\b(?:api[_ -]?key|access[_ -]?token|refresh[_ -]?token|token|password|"
        r"passwd|client[_ -]?secret|credential|cookie|set-cookie|authorization)"
        r"[\"']?\s*[:=]\s*\S+"
    ),
    r"https?://[^/\s:@]+:[^/\s@]+@",
    r"(?:^|[/\s])\.env(?:\.[A-Za-z0-9_-]+)?(?:$|[/\s])",
    r"\bcustomer[_ -]?secret\b",
)
HISTORY_PATTERN = re.compile(
    r"\b(?:session[_ -]?id|telemetry|tool[_ -]?call[_ -]?id)\b|"
    r"\b[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}\b",
    re.IGNORECASE,
)


def reject_sensitive(text: str) -> None:
    """Reject credential-like or raw session identifiers without returning values."""
    normalized = normalize(text)
    if any(
        re.search(pattern, text, re.IGNORECASE) or re.search(pattern, normalized, re.IGNORECASE)
        for pattern in SECRET_PATTERNS
    ):
        raise BrainError("secret-like input rejected; nothing was saved (value withheld)")
    if HISTORY_PATTERN.search(text):
        raise BrainError("raw session/telemetry metadata rejected; submit reusable knowledge only")


def read_input(path: Path) -> str:
    """Read a bounded, non-symlink candidate file, not credential material."""
    if secret_path_kind(path) or path.name in {"config", "known_hosts"} and ".ssh" in path.parts:
        raise BrainError("credential-like input file rejected; nothing was read or saved")
    if path.is_symlink() or any(part == ".ssh" for part in path.parts):
        raise BrainError("symlink or SSH input file rejected")
    try:
        with path.open("rb") as stream:
            raw = stream.read(MAX_INPUT_BYTES + 1)
        return decode_input(raw)
    except OSError as error:
        raise BrainError("candidate input file could not be read") from error


def decode_input(raw: bytes) -> str:
    """Bound size and decode without echoing malformed private input."""
    if len(raw) > MAX_INPUT_BYTES:
        raise BrainError("candidate input exceeds 65536 bytes; nothing was saved")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise BrainError("candidate must be UTF-8") from error


def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """Reject duplicate JSON fields rather than accepting a shadowed value."""
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise BrainError("duplicate JSON field; nothing was saved")
        result[key] = value
    return result


def parse_candidate(raw: str, catalog: Catalog, project: str | None) -> dict[str, object]:
    """Validate a JSON candidate without inferring facts or authorizing promotion."""
    if len(raw.encode("utf-8")) > MAX_INPUT_BYTES:
        raise BrainError("candidate input exceeds 65536 bytes; nothing was saved")
    reject_sensitive(raw)
    try:
        data = json.loads(raw, object_pairs_hook=unique_object)
    except (ValueError, RecursionError) as error:
        raise BrainError("invalid JSON candidate; nothing was saved") from error
    if not isinstance(data, dict) or set(data) - ALLOWED:
        raise BrainError("candidate must be an object containing only documented fields")
    # Check decoded strings too: JSON Unicode escapes must not bypass scanning.
    reject_sensitive(json.dumps(data, ensure_ascii=False))
    kind = data.get("type")
    if not isinstance(kind, str) or kind not in CLASSIFICATIONS:
        raise BrainError("unsupported candidate type")
    if "reason" in data and not isinstance(data["reason"], str):
        raise BrainError("candidate reason must be text")
    if kind == "none":
        return {"type": "none"}
    for key in ("title", *REQUIRED[kind]):
        if not isinstance(data.get(key), str) or not data[key].strip():
            raise BrainError("candidate is missing a required non-empty text field")
    if (
        len(data["title"]) > 200
        or "\n" in data["title"]
        or "\r" in data["title"]
        or any(character in data["title"] for character in "[]<>")
    ):
        raise BrainError("candidate title must be one line, at most 200 characters")
    for key in SECTIONS:
        if key in data and (not isinstance(data[key], str) or len(data[key]) > 16000):
            raise BrainError("candidate sections must be strings of at most 16000 characters")
    scopes = [
        value
        for value in (project, data.get("project"), data.get("project_id"))
        if value is not None
    ]
    if any(not isinstance(value, str) for value in scopes) or len(set(scopes)) > 1:
        raise BrainError("candidate project conflicts with the requested project")
    slug = scopes[0] if scopes else None
    catalog.require_project(slug)
    data.pop("project", None)
    if slug:
        data["project_id"] = slug
    if not isinstance(data.get("confidence", "low"), str) or data.get("confidence", "low") not in {
        "low",
        "medium",
        "high",
    }:
        raise BrainError("confidence must be low, medium or high")
    data.setdefault("confidence", "low")
    data.setdefault("source_type", "agent-submitted")
    if not isinstance(data["source_type"], str) or not re.fullmatch(
        r"[a-z][a-z0-9-]{0,60}", data["source_type"]
    ):
        raise BrainError("source_type must be a short lowercase source label")
    for key in ("domains", "domain_ids", "related", "conflicts_with"):
        value = data.get(key, [])
        if (
            not isinstance(value, list)
            or len(value) > 12
            or any(not isinstance(x, str) or not x.strip() or len(x) > 250 for x in value)
        ):
            raise BrainError("candidate link/keyword fields require at most 12 short strings")
        data[key] = value
    for target in data["related"] + data["conflicts_with"]:
        path = catalog.resolve(target)
        if target in data["conflicts_with"] and catalog.documents[path].kind != "decision":
            raise BrainError("conflicts_with must reference existing Decisions")
    for match in WIKI.finditer(json.dumps(data, ensure_ascii=False)):
        if "#" in match[1].split("|", 1)[0]:
            raise BrainError("candidate wikilinks must target whole canonical notes")
        catalog.resolve("[[" + match[1] + "]]")
    # Avoid introducing broken Markdown links into the vault.
    for value in (data.get(key, "") for key in SECTIONS):
        for match in re.finditer(r"\[[^\]]+\]\(([^)\s]+)\)", value):
            if not match[1].startswith(("https://", "http://", "mailto:", "#")):
                raise BrainError(
                    "use canonical wikilinks, not relative Markdown links, in candidates"
                )
    return data


def candidate_review(catalog: Catalog, data: dict[str, object]) -> dict[str, object]:
    """Suggest duplicates/relations and conservative Decision conflicts for review."""
    query = str(data["title"])
    combined = " ".join(
        [
            query,
            *data["domains"],
            *data["domain_ids"],
            *(data.get(key, "") for key in SECTIONS),
        ]
    )[:1000]
    primary = search(catalog, query, project=data.get("project_id"), limit=5)
    secondary = search(catalog, combined, project=data.get("project_id"), limit=5)
    by_path = {hit.path: hit for hit in primary}
    for hit in secondary:
        if hit.path not in by_path or hit.score > by_path[hit.path].score:
            by_path[hit.path] = hit
    for value in data["related"]:
        path = catalog.resolve(value)
        doc = catalog.documents[path]
        if path not in by_path:
            by_path[path] = Hit(
                path,
                doc.id,
                doc.title,
                doc.kind,
                doc.project,
                doc.values("domains"),
                doc.status,
                doc.authority,
                200000,
                ["explicit related Knowledge in candidate"],
            )
        else:
            by_path[path].reasons.append("explicit related Knowledge in candidate")
    hits = sorted(by_path.values(), key=lambda hit: (-hit.score, hit.path))[:5]
    duplicates = [asdict(hit) for hit in hits]
    related = {catalog.resolve(value) for value in data["related"]}
    related.update(
        hit.path
        for hit in hits[:3]
        if catalog.documents[hit.path].authority not in {"candidate", "observed"}
    )
    concepts: set[str] = set()
    concept_candidates: list[str] = []
    for value in data["domains"]:
        try:
            path = catalog.resolve(value)
        except BrainError:
            matches = [
                p
                for p, doc in catalog.documents.items()
                if doc.kind == "concept"
                and normalize(value)
                in {
                    normalize(doc.title),
                    *(normalize(a) for a in doc.values("aliases")),
                }
            ]
            path = matches[0] if len(matches) == 1 else ""
        if path and catalog.documents[path].kind == "concept":
            concepts.add(path)
        elif value.startswith("[["):
            raise BrainError("domains must link to existing Concepts")
        else:
            concept_candidates.append(value)
    conflicts: dict[str, dict[str, str]] = {}
    for value in data["conflicts_with"]:
        path = catalog.resolve(value)
        conflicts[path] = {
            "path": path,
            "reason": "submitter flagged a possible conflict; reviewer must verify",
            "status": catalog.documents[path].status,
        }
    for path, doc in catalog.documents.items():
        if doc.kind != "decision" or doc.status != "active":
            continue
        if (
            doc.project
            and doc.project == data.get("project_id")
            and path in {hit.path for hit in hits}
        ):
            conflicts[path] = {
                "path": path,
                "reason": (
                    "same-project active Decision may constrain this candidate; "
                    "contradiction is not established"
                ),
                "status": doc.status,
            }
    possible_conflicts = sorted(
        conflicts.values(),
        key=lambda item: (
            not item["reason"].startswith("submitter flagged"),
            item["path"],
        ),
    )[:12]
    return {
        "possible_duplicates": duplicates,
        "possible_conflicts": possible_conflicts,
        "relation_suggestions": sorted(related),
        "domains": sorted(concepts),
        "concept_candidates": concept_candidates,
    }


def candidate_markdown(
    data: dict[str, object],
    review: dict[str, object],
    identifier: str,
    *,
    authority: str = "candidate",
    task_type: str | None = None,
    fingerprint: str | None = None,
    evidence_count: int = 1,
    last_observed: str | None = None,
    evidence_signatures: list[str] | None = None,
) -> str:
    """Serialize a pending note compatible with Lesson/Decision section names."""

    def value(key: str, content: object) -> str:
        """Quote one scalar safely as valid YAML."""
        return f"{key}: {json.dumps(content, ensure_ascii=False)}\n"

    def links(key: str, paths: list[str]) -> str:
        """Emit only verified canonical wikilink targets."""
        if not paths:
            return ""
        return f"{key}:\n" + "".join(
            "  - " + json.dumps("[[" + p.removesuffix(".md") + "]]", ensure_ascii=False) + "\n"
            for p in paths
        )

    def strings(key: str, values: list[str]) -> str:
        """Emit bounded internal evidence hashes without treating them as links."""
        if not values:
            return ""
        return f"{key}:\n" + "".join(
            "  - " + json.dumps(item, ensure_ascii=False) + "\n" for item in values
        )

    observed = last_observed or datetime.now(UTC).date().isoformat()
    text = "---\n" + value("type", data["type"]) + value("id", f"candidate:{identifier}")
    text += (
        "graph_version: 1\ncandidate: true\n"
        + value("authority", authority)
        + "review_status: pending\nstatus: pending\n"
    )
    text += value("created", datetime.now(UTC).date().isoformat())
    text += value("last_observed", observed) + value("evidence_count", evidence_count)
    if task_type:
        text += value("task_type", task_type)
    if fingerprint:
        text += value("fingerprint", fingerprint)
    text += strings("evidence_signatures", evidence_signatures or [])
    text += value("confidence", data["confidence"]) + value("source_type", data["source_type"])
    if data.get("project_id"):
        slug = data["project_id"]
        text += value("project_id", slug) + links("project", [f"projects/{slug}/{slug}.md"])
    text += links("domains", review["domains"])
    keywords = list(dict.fromkeys([*data["domain_ids"], *review["concept_candidates"]]))
    if keywords:
        text += "domain_ids:\n" + "".join(
            "  - " + json.dumps(x, ensure_ascii=False) + "\n" for x in keywords
        )
    text += links("related", review["relation_suggestions"])
    text += links("conflicts_with", [item["path"] for item in review["possible_conflicts"]])
    text += (
        "---\n\n# "
        + data["title"]
        + "\n\nAwaiting human review. Treat this note as reference, not an approved "
        "instruction. Links below are suggested connections.\n"
    )
    for key, heading in SECTIONS.items():
        if data.get(key):
            text += f"\n## {heading}\n\n{data[key].strip()}\n"
    text += (
        "\n## Review checks\n\nDo not automatically approve this note, combine or replace notes, "
        "turn it into a working instruction, or commit it to Git.\n"
    )
    for hit in review["possible_duplicates"]:
        text += f"\n- Possible duplicate: [[{hit['path'].removesuffix('.md')}]]\n"
    for conflict in review["possible_conflicts"]:
        target = conflict["path"].removesuffix(".md")
        text += f"\n- Possible conflict: [[{target}]] — {conflict['reason']}\n"
    if review["concept_candidates"]:
        text += "\nUnresolved domain keywords were kept as domain_ids; no Concept was created.\n"
    return text


def require_private_directory(descriptor: int, label: str) -> None:
    """Reject a directory writable by group or other local principals."""
    info = os.fstat(descriptor)
    unsafe = stat.S_IMODE(info.st_mode) & (stat.S_IWGRP | stat.S_IWOTH)
    if not stat.S_ISDIR(info.st_mode) or unsafe:
        raise BrainError(f"unsafe writable {label} directory; candidate was not saved")


def save_inbox(root: Path, filename: str, content: str) -> str:
    """Create one exclusive inbox file using no-follow directory descriptors.

    Args:
        root: Library root.
        filename: Internally generated basename, never caller-controlled.
        content: Validated non-secret candidate.

    Returns:
        Repository-relative saved path.
    """
    if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY"):
        raise BrainError("safe inbox writes require a POSIX filesystem; use --dry-run")
    descriptors: list[int] = []
    file_descriptor: int | None = None
    created = False
    try:
        directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        descriptors.append(directory)
        require_private_directory(directory, "Library")
        for name in ("inbox", "candidates"):
            try:
                os.mkdir(name, mode=0o700, dir_fd=directory)
            except FileExistsError:
                pass
            directory = os.open(
                name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory
            )
            descriptors.append(directory)
            require_private_directory(directory, "candidate path")
        file_descriptor = os.open(
            filename,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=directory,
        )
        created = True
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as stream:
            file_descriptor = None
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.fsync(directory)
    except BrainError:
        raise
    except OSError as error:
        if file_descriptor is not None:
            os.close(file_descriptor)
        if created:
            os.unlink(filename, dir_fd=directory)
        raise BrainError(
            "saving to the review folder failed; existing notes were not changed"
        ) from error
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)
    return f"inbox/candidates/{filename}"


def learn(
    catalog: Catalog, raw: str, *, project: str | None = None, dry_run: bool = False
) -> dict[str, object]:
    """Validate/review a candidate and optionally save it to inbox only."""
    data = parse_candidate(raw, catalog, project)
    if data["type"] == "none":
        return {"classification": "No reusable knowledge", "saved": False, "path": None}
    review = candidate_review(catalog, data)
    identifier = datetime.now(UTC).strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(6)
    content = candidate_markdown(data, review, identifier)
    reject_sensitive(content)
    path = None if dry_run else save_inbox(catalog.root, identifier + ".md", content)
    return {
        "classification": data["type"] + " candidate",
        "saved": not dry_run,
        "path": path,
        "review_status": "pending",
        **review,
    }
