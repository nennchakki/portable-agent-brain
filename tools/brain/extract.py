"""Turn bounded task summaries into low-authority, reviewable Knowledge candidates."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import secrets
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from tools.graph import split_frontmatter

from .catalog import BrainError, Catalog, Document, load_catalog
from .learn import (
    MAX_INPUT_BYTES,
    SECTIONS,
    candidate_markdown,
    candidate_review,
    parse_candidate,
    reject_sensitive,
    require_private_directory,
    save_inbox,
    unique_object,
)
from .search import normalize
from .tasking import TASK_TYPES, classify_task

SUMMARY_FIELDS = {
    "project",
    "task_type",
    "task",
    "outcome",
    "new_findings",
    "user_corrections",
    "failed_approaches",
    "successful_approaches",
}
OPTIONAL_SUMMARY_FIELDS = {"reusable_knowledge"}
OUTCOMES = {"success", "partial", "failure", "cancelled"}
AUTO_TYPES = {"fact", "preference", "constraint", "lesson", "procedure", "decision"}
MAX_SUMMARY_ITEMS = 20
MAX_ITEM_CHARS = 4000
PROMOTION_EVIDENCE = 4
SKILL_EVIDENCE = 3
SHARED_PROJECT = "shared"
EPHEMERAL = (
    re.compile(
        r"^(?:build|ビルド).*(?:pass|passed|success|通った|成功)[。.]?$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:tests?|テスト).*(?:pass|passed|通った|成功)[。.]?$",
        re.IGNORECASE,
    ),
    re.compile(r"^(?:typo|誤字|脱字).*(?:fix|fixed|修正)[。.]?$", re.IGNORECASE),
    re.compile(r"^(?:ありがとう|thanks?|thank you)[!！。.]?$", re.IGNORECASE),
    re.compile(r"^(?:line|page|行|ページ)\s*\d+", re.IGNORECASE),
    re.compile(
        r"^(?:edited|changed|modified|編集|変更).*(?:files?|ファイル)",
        re.IGNORECASE,
    ),
)
TRANSCRIPT_TURN = re.compile(r"(?im)^\s*(?:user|assistant|system|developer|tool)\s*:\s*\S+")


def _short_text(value: object, *, limit: int, label: str) -> str:
    """Validate one bounded, printable line without echoing rejected content."""
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > limit
        or any(ord(char) < 32 or ord(char) == 127 for char in value)
    ):
        raise BrainError(f"learn-extract {label} must be one bounded line")
    return value.strip()


def _text_list(value: object, label: str) -> list[str]:
    """Accept a small list of findings, never a conversation or tool transcript."""
    if not isinstance(value, list) or len(value) > MAX_SUMMARY_ITEMS:
        raise BrainError(f"learn-extract {label} must be a bounded text list")
    result: list[str] = []
    for item in value:
        if (
            not isinstance(item, str)
            or not item.strip()
            or len(item) > MAX_ITEM_CHARS
            or "\x00" in item
        ):
            raise BrainError(f"learn-extract {label} contains invalid text")
        result.append(item.strip())
    return result


def parse_summary(
    raw: str,
    catalog: Catalog,
    *,
    project: str,
    task_type: str,
) -> dict[str, object]:
    """Validate the documented task summary before reading or writing candidates."""
    if len(raw.encode("utf-8")) > MAX_INPUT_BYTES:
        raise BrainError("learn-extract input exceeds 65536 bytes; nothing was saved")
    reject_sensitive(raw)
    try:
        data = json.loads(raw, object_pairs_hook=unique_object)
    except (ValueError, RecursionError) as error:
        raise BrainError("invalid learn-extract JSON; nothing was saved") from error
    if (
        not isinstance(data, dict)
        or set(data) - SUMMARY_FIELDS - OPTIONAL_SUMMARY_FIELDS
        or SUMMARY_FIELDS - set(data)
    ):
        raise BrainError("learn-extract summary fields do not match the documented schema")
    structured_text = "\n".join(_nested_text(data))
    if len(TRANSCRIPT_TURN.findall(structured_text)) >= 2:
        raise BrainError("raw conversation-like input rejected; submit a short task summary")
    reject_sensitive(json.dumps(data, ensure_ascii=False))
    if data["project"] != project or data["task_type"] != task_type:
        raise BrainError("learn-extract project or task type conflicts with CLI scope")
    policy = None if project == SHARED_PROJECT else catalog.require_project(project)
    if task_type not in TASK_TYPES:
        raise BrainError("unknown task type")
    task = _short_text(data["task"], limit=300, label="task")
    if data["outcome"] not in OUTCOMES:
        raise BrainError("learn-extract outcome is unsupported")
    for key in (
        "new_findings",
        "user_corrections",
        "failed_approaches",
        "successful_approaches",
    ):
        data[key] = _text_list(data[key], key)
    reusable = data.get("reusable_knowledge", [])
    if not isinstance(reusable, list) or len(reusable) > MAX_SUMMARY_ITEMS:
        raise BrainError("reusable_knowledge must be a bounded candidate list")
    candidates: list[dict[str, object]] = []
    for item in reusable:
        if not isinstance(item, dict) or item.get("type") not in AUTO_TYPES:
            raise BrainError("reusable_knowledge contains an unsupported candidate")
        item_scopes = [
            value for value in (item.get("project"), item.get("project_id")) if value is not None
        ]
        if any(value != project for value in item_scopes):
            raise BrainError("reusable_knowledge project conflicts with the summary scope")
        enriched = {
            **{key: value for key, value in item.items() if key not in {"project", "project_id"}},
            "source_type": "task-observation",
        }
        if project != SHARED_PROJECT:
            enriched["project_id"] = project
        parsed = parse_candidate(
            json.dumps(enriched, ensure_ascii=False),
            catalog,
            None if project == SHARED_PROJECT else project,
        )
        candidates.append(parsed)
    data["reusable_knowledge"] = candidates
    data["task"] = task
    profile = classify_task(
        task,
        project_type=policy.project_type if policy is not None else "shared",
        project_domains=policy.domains if policy is not None else [],
        explicit=task_type,
    )
    data["trivial"] = profile.complexity == "simple"
    return data


def _nested_text(value: object) -> list[str]:
    """Collect decoded strings only for rejecting conversation-shaped payloads."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [text for item in value for text in _nested_text(item)]
    if isinstance(value, dict):
        return [text for item in value.values() for text in _nested_text(item)]
    return []


def _reusable(value: str) -> bool:
    """Drop narrow completion chatter while preserving actionable task evidence."""
    compact = " ".join(value.split())
    return len(compact) >= 8 and not any(pattern.search(compact) for pattern in EPHEMERAL)


def _title(prefix: str, value: str) -> str:
    """Create a safe display title from one already structured observation."""
    compact = " ".join(value.split())
    compact = re.sub(r"[\[\]<>]", "", compact).strip(" .。")
    if len(compact) > 100:
        compact = compact[:97].rstrip() + "..."
    return f"{prefix}: {compact}"[:200]


def _candidate(
    catalog: Catalog,
    project: str,
    kind: str,
    title: str,
    **sections: str,
) -> dict[str, object]:
    """Reuse the strict learn schema instead of maintaining a second note format."""
    payload = {
        "type": kind,
        "title": title,
        "confidence": "low",
        "source_type": "task-observation",
        **sections,
    }
    if project != SHARED_PROJECT:
        payload["project_id"] = project
    return parse_candidate(
        json.dumps(payload, ensure_ascii=False),
        catalog,
        None if project == SHARED_PROJECT else project,
    )


def infer_candidates(catalog: Catalog, summary: dict[str, object]) -> list[dict[str, object]]:
    """Map explicit Agent extraction, or conservative fallback fields, to candidates."""
    explicit = summary["reusable_knowledge"]
    if explicit:
        return list(explicit)
    project = str(summary["project"])
    result: list[dict[str, object]] = []
    for finding in summary["new_findings"]:
        if _reusable(finding):
            result.append(
                _candidate(
                    catalog,
                    project,
                    "fact",
                    _title("Observed fact", finding),
                    statement=finding,
                )
            )
    constraint_markers = (
        "必ず",
        "禁止",
        "しないで",
        "使わない",
        "must ",
        "never ",
        "do not ",
        "don't ",
    )
    for correction in summary["user_corrections"]:
        if not _reusable(correction):
            continue
        kind = (
            "constraint"
            if any(marker in normalize(correction) for marker in constraint_markers)
            else "preference"
        )
        result.append(
            _candidate(
                catalog,
                project,
                kind,
                _title("User correction", correction),
                statement=correction,
            )
        )
    failed = [item for item in summary["failed_approaches"] if _reusable(item)]
    successful = [item for item in summary["successful_approaches"] if _reusable(item)]
    if failed and successful:
        result.append(
            _candidate(
                catalog,
                project,
                "lesson",
                _title("Verified workaround", str(summary["task"])),
                what_happened="\n".join(f"- {item}" for item in failed),
                root_cause=(
                    "The structured task summary associates the failure with the "
                    "listed approaches; deeper causality was not inferred."
                ),
                correct_approach="\n".join(f"- {item}" for item in successful),
                verification=(
                    f"The structured task outcome was {summary['outcome']}; "
                    "the listed successful approaches were reported as verified."
                ),
            )
        )
    elif successful and summary["outcome"] == "success":
        result.append(
            _candidate(
                catalog,
                project,
                "procedure",
                _title("Reusable procedure", str(summary["task"])),
                steps="\n".join(f"{index}. {item}" for index, item in enumerate(successful, 1)),
                verification="The structured task outcome was success.",
            )
        )
    unique: dict[str, dict[str, object]] = {}
    for item in result:
        unique.setdefault(candidate_fingerprint(item), item)
    return list(unique.values())


def candidate_fingerprint(data: dict[str, object]) -> str:
    """Hash normalized reusable content, excluding display title and runtime IDs."""
    payload = {
        "type": data["type"],
        "project_id": data.get("project_id", ""),
        "sections": {
            key: " ".join(normalize(str(data[key])).split()) for key in SECTIONS if data.get(key)
        },
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def observation_signature(summary: dict[str, object], fingerprint: str) -> str:
    """Deduplicate a replayed task summary without storing a session identifier."""
    payload = "\n".join(
        (
            normalize(str(summary["project"])),
            normalize(str(summary["task_type"])),
            normalize(str(summary["task"])),
            normalize(str(summary["outcome"])),
            fingerprint,
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _body(catalog: Catalog, document: Document) -> str:
    """Read one bounded body only for conservative exact-duplicate confirmation."""
    with (catalog.root / document.path).open(encoding="utf-8") as stream:
        stream.seek(document.body_offset)
        return stream.read(200001)[:200000]


def exact_duplicate(
    catalog: Catalog, data: dict[str, object], fingerprint: str
) -> tuple[Document | None, str | None]:
    """Suppress only exact fingerprints or literal canonical reusable content."""
    compatible = {
        "procedure": {"procedure", "protocol"},
        "protocol": {"procedure", "protocol"},
    }.get(str(data["type"]), {str(data["type"])})
    project = str(data.get("project_id", ""))
    statements = [
        " ".join(normalize(str(data[key])).split())
        for key in SECTIONS
        if data.get(key) and len(str(data[key])) >= 20
    ]
    for document in catalog.documents.values():
        if document.project not in {"", project} or document.kind not in compatible:
            continue
        if document.metadata.get("fingerprint") == fingerprint:
            return document, "exact candidate fingerprint"
        if statements and all(
            value in " ".join(normalize(_body(catalog, document)).split()) for value in statements
        ):
            return document, "literal reusable content already exists"
    return None, None


@contextmanager
def candidate_lock(root: Path) -> Iterator[int]:
    """Serialize duplicate checks and candidate writes across local Agent processes."""
    descriptors: list[int] = []
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
        fcntl.flock(directory, fcntl.LOCK_EX)
        yield directory
    except OSError as error:
        raise BrainError("candidate store could not be locked; nothing was saved") from error
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def _replace_scalar(frontmatter: str, key: str, value: object) -> str:
    """Update one generated top-level scalar while preserving all other metadata."""
    line = f"{key}: {json.dumps(value, ensure_ascii=False)}"
    updated, count = re.subn(rf"(?m)^{re.escape(key)}:\s*.*$", line, frontmatter, count=1)
    return updated if count else frontmatter.rstrip() + "\n" + line + "\n"


def _replace_strings(frontmatter: str, key: str, values: list[str]) -> str:
    """Update one generated block list of internal hashes."""
    block = f"{key}:\n" + "".join("  - " + json.dumps(value) + "\n" for value in values)
    updated, count = re.subn(rf"(?m)^{re.escape(key)}:\n(?:  - .*\n)*", block, frontmatter, count=1)
    return updated if count else frontmatter.rstrip() + "\n" + block


def _confidence(evidence_count: int, current: str) -> str:
    """Increase evidence confidence without lowering an explicit confidence."""
    target = (
        "high"
        if evidence_count >= PROMOTION_EVIDENCE
        else "medium"
        if evidence_count >= 2
        else "low"
    )
    levels = {"low": 0, "medium": 1, "high": 2}
    return current if levels.get(current, 0) > levels[target] else target


def reinforce_candidate(
    catalog: Catalog,
    document: Document,
    signature: str,
    directory: int,
) -> tuple[bool, int]:
    """Atomically add independent evidence to one generated candidate note."""
    if not document.is_candidate or Path(document.path).parent.as_posix() != "inbox/candidates":
        raise BrainError("only generated candidates can receive reinforcement")
    signatures = document.values("evidence_signatures")
    if signature in signatures:
        return False, document.evidence_count
    filename = Path(document.path).name
    descriptor = os.open(filename, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory)
    try:
        info = os.fstat(descriptor)
        unsafe = stat.S_IMODE(info.st_mode) & (stat.S_IWGRP | stat.S_IWOTH)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or unsafe:
            raise BrainError("candidate reinforcement target is not a private regular file")
        with os.fdopen(descriptor, "r", encoding="utf-8") as stream:
            descriptor = -1
            content = stream.read(262145)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    if len(content) > 262144:
        raise BrainError("candidate is too large to reinforce safely")
    frontmatter, body = split_frontmatter(content)
    count = document.evidence_count + 1
    frontmatter = _replace_scalar(frontmatter, "evidence_count", count)
    frontmatter = _replace_scalar(
        frontmatter, "last_observed", datetime.now(UTC).date().isoformat()
    )
    frontmatter = _replace_scalar(
        frontmatter,
        "confidence",
        _confidence(count, str(document.metadata.get("confidence", "low"))),
    )
    frontmatter = _replace_strings(
        frontmatter, "evidence_signatures", [*signatures, signature][-64:]
    )
    updated = "---\n" + frontmatter.rstrip() + "\n---\n" + body
    reject_sensitive(updated)
    temporary = ".update-" + secrets.token_hex(8) + ".tmp"
    output = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
        0o600,
        dir_fd=directory,
    )
    replaced = False
    try:
        with os.fdopen(output, "w", encoding="utf-8") as stream:
            output = -1
            stream.write(updated)
            stream.flush()
            os.fsync(stream.fileno())
        os.rename(temporary, filename, src_dir_fd=directory, dst_dir_fd=directory)
        replaced = True
        os.fsync(directory)
    except OSError as error:
        if output >= 0:
            os.close(output)
        try:
            os.unlink(temporary, dir_fd=directory)
        except FileNotFoundError:
            pass
        message = (
            "candidate reinforcement durability check failed; inspect the candidate"
            if replaced
            else "candidate reinforcement failed; original was preserved"
        )
        raise BrainError(message) from error
    return True, count


def learn_extract(
    catalog: Catalog,
    raw: str,
    *,
    project: str,
    task_type: str,
    dry_run: bool = False,
) -> dict[str, object]:
    """Extract, suppress, reinforce or save candidates without canonical promotion."""
    summary = parse_summary(raw, catalog, project=project, task_type=task_type)
    base = {
        "project": project,
        "task_type": task_type,
        "meaningful_task": not summary["trivial"],
        "learn_extraction_attempted": True,
        "knowledge_created": False,
        "candidates_created": [],
        "duplicates_suppressed": [],
        "reinforcements": [],
        "conflicts": [],
        "promotion_suggestions": [],
    }
    if summary["trivial"]:
        return {**base, "reason": "trivial task"}
    extracted = infer_candidates(catalog, summary)
    if not extracted:
        return {**base, "reason": "no reusable knowledge"}

    def process(current: Catalog, directory: int | None) -> dict[str, object]:
        """Process a bounded list while holding the candidate-store lock when writing."""
        result = dict(base)
        result.update(
            candidates_created=[],
            duplicates_suppressed=[],
            reinforcements=[],
            conflicts=[],
            promotion_suggestions=[],
        )
        for data in extracted:
            fingerprint = candidate_fingerprint(data)
            signature = observation_signature(summary, fingerprint)
            duplicate, duplicate_reason = exact_duplicate(current, data, fingerprint)
            if duplicate is not None:
                result["duplicates_suppressed"].append(
                    {
                        "id": duplicate.id,
                        "path": duplicate.path,
                        "reason": duplicate_reason,
                    }
                )
                if duplicate.is_candidate and directory is not None and not dry_run:
                    changed, count = reinforce_candidate(current, duplicate, signature, directory)
                    if changed:
                        result["reinforcements"].append(
                            {
                                "id": duplicate.id,
                                "path": duplicate.path,
                                "evidence_count": count,
                            }
                        )
                        if count >= PROMOTION_EVIDENCE:
                            result["promotion_suggestions"].append(
                                {
                                    "id": duplicate.id,
                                    "kind": "human-review-for-canonical-promotion",
                                }
                            )
                        if duplicate.kind == "procedure" and count >= SKILL_EVIDENCE:
                            result["promotion_suggestions"].append(
                                {
                                    "id": duplicate.id,
                                    "kind": "procedure-to-skill-review",
                                }
                            )
                continue
            review = candidate_review(current, data)
            conflicts = [item["path"] for item in review["possible_conflicts"]]
            result["conflicts"].extend(conflicts)
            identifier = datetime.now(UTC).strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(6)
            content = candidate_markdown(
                data,
                review,
                identifier,
                task_type=task_type,
                fingerprint=fingerprint,
                evidence_signatures=[signature],
            )
            reject_sensitive(content)
            path = None
            if not dry_run:
                path = save_inbox(current.root, identifier + ".md", content)
            result["candidates_created"].append(
                {
                    "id": f"candidate:{identifier}",
                    "path": path,
                    "type": data["type"],
                    "authority": "candidate",
                    "saved": not dry_run,
                }
            )
            if not dry_run:
                current = load_catalog(current.root)
        result["conflicts"] = sorted(set(result["conflicts"]))
        result["knowledge_created"] = bool(result["candidates_created"] and not dry_run)
        if result["knowledge_created"]:
            result["reason"] = "reusable candidate knowledge saved"
        elif result["reinforcements"]:
            result["reason"] = "existing candidate reinforced"
        elif result["duplicates_suppressed"]:
            result["reason"] = "reusable knowledge already exists"
        elif dry_run and result["candidates_created"]:
            result["reason"] = "dry run; candidates not saved"
        else:
            result["reason"] = "no reusable knowledge"
        return result

    if dry_run:
        return process(catalog, None)
    with candidate_lock(catalog.root) as directory:
        return process(load_catalog(catalog.root), directory)
