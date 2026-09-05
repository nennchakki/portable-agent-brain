"""Command-line interface for the public engine and a separate user library."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import shlex
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from tools.validate import run_checks

from .catalog import BrainError, load_catalog
from .config import ConfigError, resolve_library_path
from .context import build_context, render_json, render_text
from .extract import learn_extract
from .hook import MAX_HOOK_INPUT_BYTES, capture_hook_decision
from .learn import MAX_INPUT_BYTES, decode_input, learn, read_input, reject_sensitive
from .release import load_denylist, release_check
from .search import search
from .setup import SetupError, SetupOptions, init_library, run_setup
from .tasking import TASK_TYPES

if TYPE_CHECKING:
    from .github import Connection, PushPlan

ENGINE_ROOT = Path(__file__).resolve().parents[2]


def _default_adapter() -> Path:
    """Locate the canonical adapter in a source checkout or installed wheel."""
    source = ENGINE_ROOT / "adapters" / "external-brain.md"
    if source.is_file():
        return source
    try:
        distribution = importlib.metadata.distribution("portable-agent-brain")
    except importlib.metadata.PackageNotFoundError as error:
        raise SetupError(
            "Shared agent instruction file is missing from this installation"
        ) from error
    for item in distribution.files or ():
        normalized = str(item).replace("\\", "/")
        if normalized.endswith("share/portable-agent-brain/adapters/external-brain.md"):
            candidate = Path(distribution.locate_file(item))
            if candidate.is_file():
                return candidate
    raise SetupError("Shared agent instruction file is missing from this installation")


def _library_argument(command: argparse.ArgumentParser) -> None:
    """Add the common external-library selector."""
    command.add_argument(
        "--library",
        "--root",
        dest="library",
        help="absolute notes folder path; overrides BRAIN_LIBRARY",
    )


def parser() -> argparse.ArgumentParser:
    """Build the stable public CLI parser."""
    result = argparse.ArgumentParser(
        prog="brain",
        description="Find relevant notes and save new notes for human review.",
    )
    result.add_argument("--version", action="version", version="%(prog)s 0.1.0")
    commands = result.add_subparsers(dest="command", required=True)

    initialize = commands.add_parser("init", help="create an empty notes folder")
    _library_argument(initialize)
    initialize.add_argument("--json", action="store_true")

    setup = commands.add_parser(
        "setup", help="set up a notes folder and optional agent connections"
    )
    _library_argument(setup)
    setup.add_argument(
        "--agent", action="append", choices=("claude", "codex", "generic"), default=[]
    )
    setup.add_argument("--adapter", help="path to the shared external-brain.md instruction file")
    setup.add_argument("--agent-home", help="isolated HOME for Agent instruction targets")
    setup.add_argument("--claude-file", help="explicit Claude Code global instruction file")
    setup.add_argument("--codex-file", help="explicit Codex global instruction file")
    setup.add_argument(
        "--generic-agents-file", help="explicit global AGENTS.md for a generic Agent"
    )
    setup.add_argument(
        "--codex-override",
        action="store_true",
        help="install into an active Codex AGENTS.override.md",
    )
    setup.add_argument(
        "--install-command-dir", help="directory in which to install the brain command"
    )
    setup.add_argument("--cli-method", choices=("auto", "symlink", "wrapper"), default="auto")
    setup.add_argument(
        "--git-mode", choices=("none", "local", "existing", "remote"), default="none"
    )
    setup.add_argument("--remote-url", help="explicit remote URL for --git-mode remote")
    setup.add_argument("--remote-name", default="origin")
    setup.add_argument(
        "--history-source",
        help="path for history-review guidance only; history content is not read",
    )
    setup.add_argument("--no-save-default", action="store_true")
    setup.add_argument("--non-interactive", action="store_true")
    setup.add_argument("--json", action="store_true")

    for name in ("search", "context", "learn", "learn-extract"):
        command = commands.add_parser(name)
        _library_argument(command)
        command.add_argument("--json", action="store_true")
        if name != "learn":
            command.add_argument("--project", required=name in {"context", "learn-extract"})
        else:
            command.add_argument("--project")
        if name in {"search", "context"}:
            command.add_argument("query")
            command.add_argument("--include-superseded", action="store_true")
        if name == "search":
            command.add_argument("--limit", type=int, default=5)
        elif name == "context":
            command.add_argument("--max-chars", type=int, default=12000)
            command.add_argument("--hops", type=int, choices=(1, 2), default=1)
            command.add_argument("--max-items", type=int, default=12)
            command.add_argument("--min-score", type=int, default=600)
            command.add_argument("--include-concepts", action="store_true")
            command.add_argument("--task-type", choices=TASK_TYPES)
            command.add_argument("--trace", action="store_true")
        else:
            inputs = command.add_mutually_exclusive_group(required=True)
            inputs.add_argument("file", type=Path, nargs="?")
            inputs.add_argument("--stdin", action="store_true")
            command.add_argument("--dry-run", action="store_true")
            if name == "learn-extract":
                command.add_argument("--task-type", required=True, choices=TASK_TYPES)

    validate = commands.add_parser("validate", help="check note formats and links")
    _library_argument(validate)
    validate.add_argument("--json", action="store_true")

    release = commands.add_parser(
        "release-check", help="scan the public distribution before release"
    )
    release.add_argument("--root", type=Path, default=Path.cwd())
    release.add_argument(
        "--denylist", type=Path, help="private JSON marker list outside the checkout"
    )
    release.add_argument("--json", action="store_true")

    hook = commands.add_parser(
        "capture-hook", help="check the note-saving result marker at task end"
    )
    hook.add_argument("--json", action="store_true", help=argparse.SUPPRESS)
    github = commands.add_parser(
        "github", help="connect and send notes to private GitHub repositories"
    )
    github_commands = github.add_subparsers(dest="github_command", required=True)
    for name in ("connect", "status", "push"):
        command = github_commands.add_parser(name)
        _library_argument(command)
        command.add_argument("--remote", default="origin")
        command.add_argument("--json", action="store_true")
        if name == "connect":
            command.add_argument("--repo", required=True, help="existing private owner/repository")
        elif name == "push":
            command.add_argument(
                "--approve", help="send only the exact plan from a reviewed preview"
            )
    return result


def _portable(value: Any) -> Any:
    """Convert dataclasses, paths, and tuples into JSON-compatible values."""
    if is_dataclass(value) and not isinstance(value, type):
        return _portable(asdict(value))
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, dict):
        return {str(key): _portable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_portable(item) for item in value]
    return value


def _print(value: Any, *, as_json: bool) -> None:
    """Print one structured result."""
    converted = _portable(value)
    if as_json:
        print(json.dumps(converted, ensure_ascii=False, indent=2))
    elif isinstance(converted, dict):
        for key, item in converted.items():
            print(f"{key}: {item}")
    else:
        print(converted)


def _github_connection_lines(connection: Connection) -> list[str]:
    """Render the verified destination, without reading authentication material."""
    lines = [
        f"接続先: github.com/{connection.repository.full_name} (private: 確認済み)",
        f"Git remote: {connection.remote}",
        f"repository ID: {connection.repository.repository_id}",
    ]
    if connection.initialized:
        lines.append("ローカルGit: 初期化しました")
    return lines


def _print_github(value: Connection | PushPlan, *, command: str, as_json: bool) -> None:
    """Display the full preview and distinguish it from an explicit completed push."""
    from .github import Connection

    if as_json:
        _print(value, as_json=True)
        return
    if isinstance(value, Connection):
        print("\n".join(_github_connection_lines(value)))
        print("内容は送信していません。" if command == "connect" else "接続状態を再確認しました。")
        return
    print("\n".join(_github_connection_lines(value.connection)))
    print(f"branch: {value.branch}")
    if value.pushed:
        print("送信済み: 確認済みの private GitHub 接続先へ push しました。")
        print(f"outgoing commits: {len(value.commits)}")
        print(f"reviewed files: {len(value.files)}")
        return
    if not value.commits:
        print("送信するコミットはありません。GitHubの対象ブランチと一致しています。")
        return
    print("GitHub push preview（未送信）")
    print(f"outgoing commits ({len(value.commits)}):")
    for commit in value.commits:
        print(f"  {commit}")
    print(f"reviewed files ({len(value.files)}):")
    for path in value.files:
        print(f"  {path}")
    print("patch (全文):")
    print(value.patch, end="" if value.patch.endswith("\n") else "\n")
    source_entrypoint = ENGINE_ROOT / "brain"
    entrypoint = (
        [str(source_entrypoint)]
        if source_entrypoint.is_file()
        else [sys.executable, "-m", "tools.brain"]
    )
    approve_command = shlex.join(
        [
            *entrypoint,
            "github",
            "push",
            "--library",
            value.connection.library,
            "--remote",
            value.connection.remote,
            "--approve",
            value.approval,
        ]
    )
    print(f"approval SHA-256: {value.approval}")
    print("差分とコミット履歴を確認後、次のコマンドで送信してください:")
    print(approve_command)


def _selected_library(value: str | None) -> Path:
    """Resolve an external Library and reject ambiguous relative CLI values."""
    if value is not None and not (
        Path(value).is_absolute() or value == "~" or value.startswith("~/")
    ):
        raise BrainError("--library must be an absolute path or start with ~")
    environment = os.environ
    configured = environment.get("BRAIN_LIBRARY")
    if (
        value is None
        and configured is not None
        and not (Path(configured).is_absolute() or configured == "~" or configured.startswith("~/"))
    ):
        raise BrainError("BRAIN_LIBRARY must be an absolute path or start with ~")
    return resolve_library_path(value)


def _require_external_library(library: Path) -> None:
    """Reject writes that would mix user knowledge into the public engine tree."""
    engine = ENGINE_ROOT.resolve()
    destination = library.resolve(strict=False)
    if destination == engine or destination.is_relative_to(engine):
        raise BrainError("notes folder must be outside the public engine checkout")


def _prompt(label: str, default: str = "") -> str:
    """Read one small setup answer from a terminal."""
    suffix = f" [{default}]" if default else ""
    answer = input(f"{label}{suffix}: ").strip()
    return answer or default


def _guide(arguments: argparse.Namespace) -> None:
    """Populate missing setup choices in a minimal terminal wizard."""
    if arguments.non_interactive or arguments.json or not sys.stdin.isatty():
        return
    default_library = resolve_library_path(arguments.library).as_posix()
    arguments.library = _prompt("Notes folder", default_library)
    if not arguments.agent:
        chosen = _prompt("Agents (comma separated: claude,codex; blank for none)")
        arguments.agent = [item.strip() for item in chosen.split(",") if item.strip()]
        invalid = set(arguments.agent) - {"claude", "codex", "generic"}
        if invalid:
            raise SetupError("Unsupported Agent selected")
    if arguments.install_command_dir is None:
        install = _prompt("Install brain command? (y/N)", "N").casefold()
        if install in {"y", "yes"}:
            arguments.install_command_dir = str(Path.home() / ".local" / "bin")
    if arguments.git_mode == "none":
        arguments.git_mode = _prompt("Git mode (none/local/existing/remote)", "none")
        if arguments.git_mode not in {"none", "local", "existing", "remote"}:
            raise SetupError("Unknown Git setup mode")
        if arguments.git_mode == "remote" and arguments.remote_url is None:
            arguments.remote_url = _prompt("Existing private remote URL")


def _setup(arguments: argparse.Namespace) -> dict[str, object]:
    """Run setup with explicit paths and no hidden hosted operations."""
    _guide(arguments)
    library = _selected_library(arguments.library)
    history_source: Path | None = None
    if arguments.history_source:
        history_source = Path(arguments.history_source).expanduser()
        if not history_source.is_absolute() or not history_source.exists():
            raise SetupError("--history-source must be an existing absolute path")
    agent_home = arguments.agent_home
    targets: dict[str, str] = {}
    explicit_targets = (
        ("claude", arguments.claude_file, "--claude-file"),
        ("codex", arguments.codex_file, "--codex-file"),
        ("generic", arguments.generic_agents_file, "--generic-agents-file"),
    )
    for agent, target, option in explicit_targets:
        if target and agent not in arguments.agent:
            raise SetupError(f"{option} requires --agent {agent}")
        if target:
            targets[agent] = target
    if "generic" in arguments.agent:
        if not arguments.generic_agents_file:
            raise SetupError("--agent generic requires --generic-agents-file")
    _require_external_library(library)
    adapter = Path(arguments.adapter).expanduser() if arguments.adapter else _default_adapter()
    entrypoint = Path(sys.argv[0]).expanduser().resolve()
    options = SetupOptions(
        library=library,
        home=agent_home,
        persist_config=not arguments.no_save_default,
        git_mode=arguments.git_mode,
        remote_url=arguments.remote_url,
        remote_name=arguments.remote_name,
        agents=tuple(dict.fromkeys(arguments.agent)),
        adapter_path=adapter,
        agent_targets=targets,
        use_codex_override=arguments.codex_override,
        cli_entrypoint=entrypoint if arguments.install_command_dir else None,
        bin_dir=arguments.install_command_dir,
        cli_method=arguments.cli_method,
        history_mining=history_source is not None,
    )
    result = run_setup(options)
    report = _portable(result)
    assert isinstance(report, dict)
    report["verification"] = {
        "library_exists": result.library.path.is_dir(),
        "library_is_external_to_engine": not result.library.path.is_relative_to(ENGINE_ROOT),
        "knowledge_nodes": len(load_catalog(result.library.path).documents),
        "history_source_read": False,
    }
    if history_source is not None:
        report["history_source"] = history_source.as_posix()
    return report


def _read_candidate_input(arguments: argparse.Namespace) -> str:
    """Read one bounded candidate or summary payload."""
    return (
        decode_input(sys.stdin.buffer.read(MAX_INPUT_BYTES + 1))
        if arguments.stdin
        else read_input(arguments.file)
    )


def main(argv: list[str] | None = None) -> int:
    """Run one command; errors never echo candidate or credential values."""
    arguments = parser().parse_args(argv)
    try:
        if arguments.command == "capture-hook":
            raw = sys.stdin.buffer.read(MAX_HOOK_INPUT_BYTES + 1)
            print(json.dumps(capture_hook_decision(raw), ensure_ascii=False, separators=(",", ":")))
            return 0
        if arguments.command == "release-check":
            try:
                denied_terms = load_denylist(arguments.denylist, arguments.root)
            except ValueError as error:
                raise BrainError(str(error)) from None
            report = release_check(arguments.root, denied_terms=denied_terms)
            _print(report, as_json=arguments.json)
            return 0 if report["ok"] else 1
        if arguments.command == "setup":
            _print(_setup(arguments), as_json=arguments.json)
            return 0
        library = _selected_library(arguments.library)
        if arguments.command == "github":
            from .github import connect, connection_status, prepare_push, push

            _require_external_library(library)
            if arguments.github_command == "connect":
                value = connect(library, arguments.repo, arguments.remote)
            elif arguments.github_command == "status":
                value = connection_status(library, arguments.remote)
            elif arguments.approve:
                value = push(library, arguments.approve, arguments.remote)
            else:
                value = prepare_push(library, arguments.remote)
            _print_github(value, command=arguments.github_command, as_json=arguments.json)
            return 0
        if arguments.command == "init":
            _require_external_library(library)
            _print(init_library(library), as_json=arguments.json)
            return 0
        if arguments.command == "validate":
            findings, graph = run_checks(library)
            report = {
                "library": library,
                "errors": sum(item.level == "error" for item in findings),
                "warnings": sum(item.level == "warning" for item in findings),
                "findings": [item.to_dict() for item in findings],
                "graph": graph,
            }
            _print(report, as_json=arguments.json)
            return 1 if report["errors"] else 0
        raw: str | None = None
        if arguments.command in {"learn", "learn-extract"}:
            raw = _read_candidate_input(arguments)
            reject_sensitive(raw)
            if not arguments.dry_run:
                _require_external_library(library)
        catalog = load_catalog(library)
        if arguments.command == "search":
            hits = search(
                catalog,
                arguments.query,
                project=arguments.project,
                limit=arguments.limit,
                include_superseded=arguments.include_superseded,
            )
            if arguments.json:
                _print(
                    {"results": [asdict(hit) for hit in hits], "io": catalog.metrics}, as_json=True
                )
            elif not hits:
                print("No results.")
            else:
                for hit in hits:
                    print(f"{hit.score}  {hit.type}  [{hit.status}]\n{hit.title}\n{hit.path}")
                    print("Project: " + (hit.project or "(shared)"))
                    print("Authority: " + hit.authority)
                    print("Matched: " + "; ".join(hit.reasons) + "\n")
        elif arguments.command == "context":
            trace: dict[str, object] | None = {} if arguments.trace else None
            bundle = build_context(
                catalog,
                arguments.project,
                arguments.query,
                max_chars=arguments.max_chars,
                hops=arguments.hops,
                max_items=arguments.max_items,
                include_superseded=arguments.include_superseded,
                min_score=arguments.min_score,
                include_concepts=arguments.include_concepts,
                task_type=arguments.task_type,
                trace=trace,
            )
            sys.stdout.write(render_json(bundle) if arguments.json else render_text(bundle))
            if trace is not None:
                print(json.dumps({"trace": trace}, ensure_ascii=False), file=sys.stderr)
        elif arguments.command == "learn":
            assert raw is not None
            value = learn(catalog, raw, project=arguments.project, dry_run=arguments.dry_run)
            _print(value, as_json=arguments.json)
        elif arguments.command == "learn-extract":
            assert raw is not None
            value = learn_extract(
                catalog,
                raw,
                project=arguments.project,
                task_type=arguments.task_type,
                dry_run=arguments.dry_run,
            )
            _print(value, as_json=arguments.json)
        return 0
    except (BrainError, ConfigError, SetupError) as error:
        message = str(error)
    except (OSError, UnicodeError):
        message = "filesystem or encoding operation failed; no input values displayed"
    if getattr(arguments, "json", False):
        print(json.dumps({"error": message}, ensure_ascii=False), file=sys.stderr)
    else:
        print("brain: " + message, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
