"""Deterministic task classification and soft context budgets."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

TASK_TYPES = (
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
)

# This is intentionally a small public vocabulary, not a learned classifier.
TASK_KEYWORDS = {
    "architecture": (
        "architecture",
        "設計",
        "構造",
        "migration",
        "移行",
    ),
    "implementation": ("implementation", "実装", "code", "機能追加", "api"),
    "ui": ("ui", "interface", "screen", "画面", "layout", "レイアウト"),
    "debugging": (
        "debug",
        "診断",
        "不具合",
        "原因",
        "再現",
        "例外",
        "エラー",
        "壊れ",
    ),
    "testing": ("test", "テスト", "回帰", "regression", "境界値", "検証"),
    "build": (
        "build",
        "ビルド",
        "compile",
        "コンパイル",
        "package",
        "ci",
    ),
    "documentation": (
        "documentation",
        "docs",
        "readme",
        "文書",
        "ドキュメント",
        "説明",
    ),
    "research": (
        "research",
        "調査",
        "文献",
        "evidence",
        "dataset",
        "出典",
    ),
    "analysis": (
        "analysis",
        "分析",
        "metrics",
        "statistics",
        "benchmark",
        "考察",
        "測定",
    ),
    "data": ("data", "dataset", "import", "export", "parse", "データ", "抽出"),
    "security": (
        "security",
        "セキュリティ",
        "secret",
        "credential",
        "脆弱性",
        "認証",
        "権限",
    ),
}

TASK_HINTS = {
    "architecture": ("architecture", "software-architecture", "decision"),
    "implementation": ("engineering", "software", "implementation"),
    "ui": ("ui", "interface", "accessibility", "layout"),
    "debugging": ("debugging", "failure", "rendering", "verification"),
    "testing": ("testing", "verification", "regression"),
    "build": ("build", "compile", "package", "toolchain", "ci"),
    "documentation": ("documentation", "writing", "readme", "reference"),
    "research": ("research", "source-provenance", "evidence", "dataset"),
    "analysis": (
        "analysis",
        "reasoning",
        "data",
        "metrics",
        "statistics",
    ),
    "data": ("data", "dataset", "import", "export", "extraction"),
    "security": ("security", "license", "credential"),
}

PROJECT_TYPE_DEFAULTS = {
    "data-project": "data",
    "knowledge-library": "architecture",
    "documentation": "documentation",
    "research": "research",
    "software": "implementation",
    "tool": "implementation",
}

TASK_BUDGETS = {
    "architecture": (9000, 8),
    "implementation": (5500, 5),
    "ui": (6000, 6),
    "debugging": (6500, 6),
    "testing": (5500, 5),
    "build": (8000, 7),
    "documentation": (7500, 6),
    "research": (7500, 7),
    "analysis": (7000, 6),
    "data": (6500, 6),
    "security": (7000, 6),
}

SIMPLE_TERMS = (
    "typo",
    "誤字",
    "脱字",
    "単純rename",
    "simple rename",
    "名前変更だけ",
    "1行変更",
    "one-line",
    "表記だけ",
)
COMPLEX_TERMS = (
    "複数file",
    "複数ファイル",
    "multi-file",
    "全面",
    "再設計",
    "migration",
    "移行",
    "architecture変更",
    "アーキテクチャ変更",
)


@dataclass(frozen=True)
class TaskProfile:
    """One transparent classification used by selection and rendering."""

    task_type: str
    source: str
    confidence: float
    complexity: str
    context_recommended: bool
    recommendation_reason: str
    soft_max_chars: int
    soft_max_items: int


def normalize_task(text: str) -> str:
    """Normalize width and case without changing task meaning."""
    return unicodedata.normalize("NFKC", text).casefold()


def _contains(text: str, phrase: str) -> bool:
    """Match short Latin labels as tokens and Japanese phrases literally."""
    normalized = normalize_task(phrase)
    if re.fullmatch(r"[a-z0-9_-]+", normalized):
        return re.search(rf"(?<![a-z0-9_-]){re.escape(normalized)}(?![a-z0-9_-])", text) is not None
    return normalized in text


def classify_task(
    query: str,
    *,
    project_type: str,
    project_domains: list[str],
    explicit: str | None = None,
) -> TaskProfile:
    """Classify a task from explicit input, lexical evidence, then Project metadata."""
    text = normalize_task(query)
    if explicit is not None and explicit not in TASK_TYPES:
        raise ValueError("unknown task type")

    scores = {
        task_type: sum(_contains(text, word) for word in words)
        for task_type, words in TASK_KEYWORDS.items()
    }
    if explicit is not None:
        task_type, source, confidence = explicit, "explicit", 1.0
    else:
        best = max(scores.values(), default=0)
        winners = [task_type for task_type in TASK_TYPES if scores[task_type] == best]
        project_default = PROJECT_TYPE_DEFAULTS.get(project_type, "implementation")
        if best:
            task_type = project_default if project_default in winners else winners[0]
            source = "lexical"
            confidence = min(0.95, 0.58 + 0.1 * best - (0.08 if len(winners) > 1 else 0))
        else:
            task_type = project_default
            domain_text = " ".join(project_domains)
            domain_matches = [
                candidate
                for candidate, hints in TASK_HINTS.items()
                if any(hint in domain_text for hint in hints)
            ]
            if domain_matches:
                task_type = domain_matches[0]
            source, confidence = "project_metadata", 0.45

    simple = any(_contains(text, term) for term in SIMPLE_TERMS)
    complex_task = task_type == "architecture" or any(
        _contains(text, term) for term in COMPLEX_TERMS
    )
    complexity = (
        "simple" if simple and not complex_task else "complex" if complex_task else "normal"
    )
    base_chars, base_items = TASK_BUDGETS[task_type]
    if complexity == "simple" and explicit is None:
        soft_chars, soft_items = 1800, 0
    elif complexity == "complex":
        soft_chars, soft_items = min(12000, base_chars + 2000), min(12, base_items + 2)
    else:
        soft_chars, soft_items = base_chars, base_items

    recommended = explicit is not None or complexity != "simple"
    if explicit is not None and complexity == "simple":
        reason = "explicit task type overrides the automatic trivial-task skip"
    elif complexity == "simple":
        reason = "trivial typo, rename, or deterministic one-line task"
    elif source == "project_metadata":
        reason = "no lexical type signal; conservative Project metadata fallback"
    else:
        reason = "task-specific Knowledge may change implementation or verification"
    return TaskProfile(
        task_type,
        source,
        round(confidence, 2),
        complexity,
        recommended,
        reason,
        soft_chars,
        soft_items,
    )
