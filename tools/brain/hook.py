"""Portable Stop-hook gate for automatic low-authority Knowledge capture."""

from __future__ import annotations

import json
import re

MAX_HOOK_INPUT_BYTES = 256 * 1024
CAPTURE_MARKER = re.compile(
    r"(?m)^[ \t]*<!--[ \t]*brain-capture:v1[ \t]+"
    r"(?:saved|duplicate|reinforced|none|error)[ \t]*-->[ \t]*$"
)
ALLOW_STOP: dict[str, object] = {"continue": True}
CAPTURE_REMINDER = (
    "Before finishing, perform the External Brain capture check for this completed "
    "turn. Do not redo the user's task and do not save the raw conversation. If the "
    "turn produced a new reusable Fact, Preference, Constraint, Lesson, Procedure, or "
    "Decision, run `brain learn-extract --project <registered-slug> --task-type <type> "
    "--stdin --json` with exactly these bounded JSON fields: `project`, `task_type`, "
    "`task`, `outcome`, `new_findings`, `user_corrections`, `failed_approaches`, and "
    "`successful_approaches`; the last four are arrays. Use `shared` only for truly "
    "cross-project knowledge when no registered project applies. Never include secrets, "
    "session IDs, or tool logs, and never approve, merge, supersede, commit, or promote a "
    "candidate automatically. If the task was trivial or produced no new reusable "
    "knowledge, do not call learn-extract. Then return the same user-facing answer with "
    "exactly one hidden receipt at the end: `<!-- brain-capture:v1 saved -->`, "
    "`duplicate`, `reinforced`, `none`, or `error`, matching the actual result."
)


def capture_hook_decision(raw: bytes) -> dict[str, object]:
    """Return a fail-open Stop decision without retaining hook input.

    Args:
        raw: One vendor hook payload read from standard input.

    Returns:
        A shared Codex and Claude Code Stop-hook response.
    """
    if len(raw) > MAX_HOOK_INPUT_BYTES:
        return dict(ALLOW_STOP)
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError, RecursionError):
        return dict(ALLOW_STOP)
    if not isinstance(value, dict) or value.get("hook_event_name") != "Stop":
        return dict(ALLOW_STOP)
    if value.get("stop_hook_active") is True:
        return dict(ALLOW_STOP)
    if value.get("background_tasks") or value.get("session_crons"):
        return dict(ALLOW_STOP)
    message = value.get("last_assistant_message")
    if not isinstance(message, str) or not message.strip():
        return dict(ALLOW_STOP)
    if CAPTURE_MARKER.search(message):
        return dict(ALLOW_STOP)
    return {"decision": "block", "reason": CAPTURE_REMINDER}
