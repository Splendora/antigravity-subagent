"""
Universal CLI Installer & Runner for the Google Antigravity Sub-Agent.

Supports:
1. `antigravity-subagent install`: Auto-configures MCP & Subagent/Skill files for:
   - Claude Code (`claude`)
   - OpenAI Codex (`codex`)
   - Cursor (`cursor`)
   - Windsurf (`windsurf`)
2. `antigravity-subagent run`: Direct CLI execution with Smart Model Routing
   (useful for shell-based agents like Codex CLI, Aider, or CI scripts).
3. `antigravity-subagent models`: Displays smart-routing tiers and available models.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

from agy_mcp_server import (
    antigravity_list_models,
    antigravity_task,
)

SERVER_SCRIPT = Path(__file__).resolve().parent / "agy_mcp_server.py"


def _norm_path(p: Path | str) -> str:
    """Use forward slashes for cross-platform JSON/TOML compatibility (especially Windows)."""
    return str(Path(p).resolve()).replace("\\", "/")


CLAUDE_SUBAGENT_MD = """---
name: antigravity
description: Delegate tasks to Google Antigravity (Gemini-powered agent) for second opinions, deep codebase analysis, multi-turn debugging, or parallel implementation. Invoke this subagent when you want cross-model verification, architectural planning, or parallel coding tasks.
tools: mcp__antigravity__antigravity_task, mcp__antigravity__antigravity_list_models, Read, Glob, Grep
---

You are the **Google Antigravity Sub-Agent Bridge**.
Your role is to delegate tasks to Google Antigravity via the `mcp__antigravity__antigravity_task` MCP tool, dynamically route to the optimal model for the task, manage multi-turn follow-ups when necessary, and return a concise, high-signal synthesis back to the main conversation.

## Smart Model Routing Rules

Always select the best `model` and `effort` combination based on the delegated task (unless the user explicitly requested a specific model):

1. **Deep Architecture, Planning, Security Audits & Complex Bug Hunting:**
   - `model="gemini-3.1-pro-high"`, `effort="high"`
   - Use for architectural design, subtle race-condition/bug analysis, critical code reviews, and second opinions.
2. **Autonomous Coding, Refactoring & Test Generation:**
   - `model="gemini-3.8-flash-high"`, `effort="high"`
   - Use when `mode="accept-edits"` or `mode="autonomous"` for fast, high-accuracy code generation and refactoring.
3. **Balanced Codebase Research & Everyday Analysis:**
   - `model="gemini-3.8-flash-medium"`, `effort="medium"`
   - Use for general repository questions, tracing call graphs, or summarizing modules.
4. **Quick Lookups & Lightweight Verifications:**
   - `model="gemini-3.8-flash-low"`, `effort="low"`
   - Use for fast syntax/config checks or trivial follow-ups.

*(If you pass `model="auto"`, the MCP server will apply these routing rules automatically based on `mode` and `effort`.)*

## How to Use `mcp__antigravity__antigravity_task`

1. **Formulate a Self-Contained Prompt:**
   Include exact file paths, requirements, error messages, and constraints in `prompt`. Always pass the current workspace path in `cwd`.
2. **Choose the Appropriate `mode`:**
   - `"read-only"` (default): For code reviews, bug hunting, second opinions, and research.
   - `"plan"`: For architectural design and step-by-step implementation plans.
   - `"accept-edits"`: When delegated to write or refactor files without running shell commands.
   - `"autonomous"`: When Antigravity should both edit files and run shell/test commands.
3. **Multi-Turn Continuity (`conversation_id`):**
   - Every response returns a `conversation_id` and the resolved `model`.
   - If Antigravity's response needs refinement or a follow-up step, call `mcp__antigravity__antigravity_task` again with the **same `conversation_id`**.
"""

UNIVERSAL_SKILL_MD = """---
name: antigravity
description: Delegate coding, architectural planning, bug hunting, and cross-model verification tasks to Google Antigravity (Gemini 3.1 Pro & Gemini 3.8 Flash). Use when asked to consult Antigravity/Gemini, get a second opinion, or run parallel sub-agent tasks.
---

# Google Antigravity Sub-Agent Skill

Use this skill to delegate tasks to **Google Antigravity** as a stateful sub-agent from **OpenAI Codex**, **Claude Code**, **Cursor**, or any other coding agent.

## 1. Preferred Method: MCP Tool (`antigravity_task`)

If the `antigravity` MCP server is connected, call the `antigravity_task` tool directly:

- **`prompt`** *(required)*: Self-contained task description including relevant file paths, symbols, or error logs.
- **`cwd`**: Current repository root path.
- **`mode`**:
  - `"read-only"` (default): Code review, second opinion, bug analysis, Q&A.
  - `"plan"`: Deep architectural planning (`/plan`).
  - `"accept-edits"`: Allow Antigravity to create/edit files.
  - `"autonomous"`: Allow Antigravity to edit files and run shell test commands.
- **`effort`**: `"low"`, `"medium"`, `"high"`, or `"max"`.
- **`model`**:
  - `"auto"` (default): Smart-routes to `gemini-3.1-pro-high` for `plan`/`high` effort, `gemini-3.8-flash-high` for code edits, `gemini-3.8-flash-medium` for general research, or `gemini-3.8-flash-low` for quick lookups.
  - Explicit override: `"gemini-3.1-pro-high"`, `"gemini-3.8-flash-high"`, `"gemini-3.8-flash-medium"`, `"gemini-3.8-flash-low"`, or `"gpt-oss-120b-medium"`.
- **`conversation_id`**: Pass the `conversation_id` from a previous response to continue a multi-turn session with full context retention.

## 2. Fallback Method: CLI Runner (`antigravity-subagent run`)

If running in an environment where MCP is unavailable, invoke the CLI runner via shell command (passing arguments directly):

```bash
antigravity-subagent run "Review src/ for concurrency issues" --cwd . --mode read-only --effort high
```

To resume a previous session:
```bash
antigravity-subagent run "Apply fix #1 from your review" --cwd . --mode accept-edits --conversation <conversation_id>
```
"""

CURSOR_RULE_MDC = """---
description: Delegate second opinions, architectural planning, or parallel coding tasks to the Google Antigravity MCP sub-agent.
globs: 
alwaysApply: false
---

# Google Antigravity Sub-Agent Integration

When the user asks for a second opinion, cross-model verification, architectural plan, or delegates a task to Antigravity / Gemini:

1. Call the `antigravity_task` MCP tool (`mcp__antigravity__antigravity_task`).
2. Pass `cwd` set to the workspace root, and choose:
   - `mode="read-only"` + `effort="high"` (`gemini-3.1-pro-high`) for deep code reviews and bug hunting
   - `mode="plan"` (`gemini-3.1-pro-high`) for architecture and implementation planning
   - `mode="accept-edits"` (`gemini-3.8-flash-high`) for fast file edits and test generation
3. Reuse the returned `conversation_id` for any multi-turn follow-ups.
"""


def _merge_json_mcp_server(
    json_path: Path, python_exe: str, server_script: str, include_type: bool = False
) -> None:
    data: dict = {}
    if json_path.exists():
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}

    mcp_servers = data.setdefault("mcpServers", {})
    entry: dict = {
        "command": python_exe,
        "args": [server_script],
    }
    if include_type:
        entry = {"type": "stdio", **entry}
    mcp_servers["antigravity"] = entry

    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _merge_codex_toml_mcp_server(
    toml_path: Path, python_exe: str, server_script: str
) -> None:
    toml_path.parent.mkdir(parents=True, exist_ok=True)
    existing = toml_path.read_text(encoding="utf-8") if toml_path.exists() else ""

    block = (
        f"[mcp_servers.antigravity]\n"
        f'command = "{python_exe}"\n'
        f'args = ["{server_script}"]\n'
    )

    pattern = re.compile(
        r"\[mcp_servers\.antigravity\]\r?\n(?:(?!\[).*\r?\n)*", re.MULTILINE
    )
    if pattern.search(existing):
        updated = pattern.sub(block, existing)
    else:
        sep = "\n" if (existing and not existing.endswith("\n")) else ""
        extra_nl = "\n" if existing.strip() else ""
        updated = f"{existing}{sep}{extra_nl}{block}"

    toml_path.write_text(updated, encoding="utf-8")


def install_for_client(
    client: str, scope: str, target_dir: Path, python_exe: str, server_script: str
) -> list[str]:
    home = Path.home()
    installed_paths: list[str] = []

    if client in ("claude", "all"):
        if scope == "user":
            claude_json = home / ".claude.json"
            _merge_json_mcp_server(
                claude_json, python_exe, server_script, include_type=True
            )
            installed_paths.append(str(claude_json))

            agent_md = home / ".claude" / "agents" / "antigravity.md"
            agent_md.parent.mkdir(parents=True, exist_ok=True)
            agent_md.write_text(CLAUDE_SUBAGENT_MD, encoding="utf-8")
            installed_paths.append(str(agent_md))
        else:
            mcp_json = target_dir / ".mcp.json"
            _merge_json_mcp_server(
                mcp_json, python_exe, server_script, include_type=False
            )
            installed_paths.append(str(mcp_json))

            agent_md = target_dir / ".claude" / "agents" / "antigravity.md"
            agent_md.parent.mkdir(parents=True, exist_ok=True)
            agent_md.write_text(CLAUDE_SUBAGENT_MD, encoding="utf-8")
            installed_paths.append(str(agent_md))

    if client in ("codex", "all"):
        if scope == "user":
            codex_toml = home / ".codex" / "config.toml"
            _merge_codex_toml_mcp_server(codex_toml, python_exe, server_script)
            installed_paths.append(str(codex_toml))

            for skill_root in (
                home / ".agents" / "skills" / "antigravity" / "SKILL.md",
                home / ".codex" / "skills" / "antigravity" / "SKILL.md",
            ):
                skill_root.parent.mkdir(parents=True, exist_ok=True)
                skill_root.write_text(UNIVERSAL_SKILL_MD, encoding="utf-8")
                installed_paths.append(str(skill_root))
        else:
            codex_toml = target_dir / ".codex" / "config.toml"
            _merge_codex_toml_mcp_server(codex_toml, python_exe, server_script)
            installed_paths.append(str(codex_toml))

            skill_md = target_dir / ".agents" / "skills" / "antigravity" / "SKILL.md"
            skill_md.parent.mkdir(parents=True, exist_ok=True)
            skill_md.write_text(UNIVERSAL_SKILL_MD, encoding="utf-8")
            installed_paths.append(str(skill_md))

    if client in ("cursor", "all"):
        if scope == "user":
            cursor_mcp = home / ".cursor" / "mcp.json"
            _merge_json_mcp_server(
                cursor_mcp, python_exe, server_script, include_type=False
            )
            installed_paths.append(str(cursor_mcp))
        else:
            cursor_mcp = target_dir / ".cursor" / "mcp.json"
            _merge_json_mcp_server(
                cursor_mcp, python_exe, server_script, include_type=False
            )
            installed_paths.append(str(cursor_mcp))

            cursor_rule = target_dir / ".cursor" / "rules" / "antigravity.mdc"
            cursor_rule.parent.mkdir(parents=True, exist_ok=True)
            cursor_rule.write_text(CURSOR_RULE_MDC, encoding="utf-8")
            installed_paths.append(str(cursor_rule))

    if client in ("windsurf", "all"):
        if scope == "user":
            ws_mcp = home / ".codeium" / "windsurf" / "mcp_config.json"
            _merge_json_mcp_server(
                ws_mcp, python_exe, server_script, include_type=False
            )
            installed_paths.append(str(ws_mcp))

    return installed_paths


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="antigravity-subagent",
        description="Universal Google Antigravity Sub-Agent installer and runner for Claude Code, OpenAI Codex, Cursor, and Windsurf.",
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # 1. `install` subcommand
    install_p = subparsers.add_parser(
        "install",
        help="Install MCP server & subagent/skill definitions for coding agents.",
    )
    install_p.add_argument(
        "--client",
        choices=["all", "claude", "codex", "cursor", "windsurf"],
        default="all",
        help="Target coding agent client to configure (default: all).",
    )
    install_p.add_argument(
        "--scope",
        choices=["user", "project"],
        default="user",
        help="Install globally in user home (~/.claude, ~/.codex, ~/.cursor) or into a project directory.",
    )
    install_p.add_argument(
        "--target-dir",
        default=".",
        help="Target project directory when --scope=project (default: current directory).",
    )

    # 2. `run` subcommand
    run_p = subparsers.add_parser(
        "run",
        help="Run a delegated Antigravity sub-agent task directly from the CLI.",
    )
    run_p.add_argument("prompt", help="Task instructions for Google Antigravity.")
    run_p.add_argument("--cwd", default=None, help="Working directory for the task.")
    run_p.add_argument(
        "--conversation",
        default=None,
        help="Conversation ID to resume a multi-turn session.",
    )
    run_p.add_argument(
        "--mode",
        choices=["read-only", "plan", "accept-edits", "autonomous"],
        default="read-only",
        help="Execution permission mode (default: read-only).",
    )
    run_p.add_argument(
        "--effort",
        choices=["low", "medium", "high", "max"],
        default="medium",
        help="Reasoning effort level (default: medium).",
    )
    run_p.add_argument(
        "--model",
        default="auto",
        help="Model ID or 'auto' for smart routing (default: auto).",
    )
    run_p.add_argument(
        "--engine",
        choices=["auto", "cli", "sdk"],
        default="auto",
        help="Execution engine: 'auto', 'cli', or 'sdk' (default: auto).",
    )
    run_p.add_argument(
        "--include-thoughts",
        action="store_true",
        help="Include Gemini reasoning thoughts when using SDK engine.",
    )

    # 3. `models` subcommand
    subparsers.add_parser(
        "models",
        help="List smart-routing tiers and available Google Antigravity models.",
    )

    args = parser.parse_args()

    if args.subcommand == "install":
        python_exe = _norm_path(sys.executable)
        server_script = _norm_path(SERVER_SCRIPT)
        target_dir = Path(args.target_dir).resolve()
        paths = install_for_client(
            client=args.client,
            scope=args.scope,
            target_dir=target_dir,
            python_exe=python_exe,
            server_script=server_script,
        )
        print(
            json.dumps(
                {
                    "status": "INSTALLED",
                    "client": args.client,
                    "scope": args.scope,
                    "python_executable": python_exe,
                    "mcp_server_script": server_script,
                    "configured_files": paths,
                },
                indent=2,
            )
        )
    elif args.subcommand == "run":
        out = asyncio.run(
            antigravity_task(
                prompt=args.prompt,
                cwd=args.cwd,
                conversation_id=args.conversation,
                mode=args.mode,
                effort=args.effort,
                model=args.model,
                engine=args.engine,
                include_thoughts=args.include_thoughts,
            )
        )
        print(out)
    elif args.subcommand == "models":
        out = asyncio.run(antigravity_list_models())
        print(out)


if __name__ == "__main__":
    main()
