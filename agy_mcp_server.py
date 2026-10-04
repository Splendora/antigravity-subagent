"""
Universal Google Antigravity Sub-Agent MCP Server.

Exposes stateful Google Antigravity sub-agent tools over Model Context Protocol (stdio)
for any MCP-compatible coding agent (Claude Code, OpenAI Codex, Cursor, Windsurf, Cline, etc.).

Supports two execution engines:
1. "cli" (default if GEMINI_API_KEY is not set): Invokes `agy` directly via
   `asyncio.create_subprocess_exec` (zero shell-escaping issues) using the user's
   cached Google Antigravity login, with full support for `--conversation` resumption,
   `--mode`, `--effort`, and `--model`.
2. "sdk" (used when `engine="sdk"` or `GEMINI_API_KEY` / Vertex AI is configured):
   Uses the official `google-antigravity` Python SDK (`Agent`, `LocalAgentConfig`,
   `CapabilitiesConfig`) with stateful session persistence and thought capture.

Environment Variables (optional):
- ANTIGRAVITY_DEFAULT_MODEL: Default model or "auto" (default: "auto")
- ANTIGRAVITY_DEFAULT_ENGINE: "auto", "cli", or "sdk" (default: "auto")
- ANTIGRAVITY_SESSIONS_DIR: Directory for SDK session state (default: ~/.gemini/antigravity-subagent/sessions)
- ANTIGRAVITY_BIN: Custom path to the `agy` binary (default: auto-detected from PATH)
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import uuid
from pathlib import Path
from typing import Literal

try:
    from mcp.server.mcpserver import MCPServer
except ImportError:
    from mcp.server.fastmcp import FastMCP as MCPServer  # type: ignore

mcp = MCPServer("antigravity")

DEFAULT_SESSIONS_DIR = Path(
    os.environ.get(
        "ANTIGRAVITY_SESSIONS_DIR",
        Path.home() / ".gemini" / "antigravity-subagent" / "sessions",
    )
)

SMART_ROUTING_TIERS = {
    "plan_or_high_effort": {
        "model": "gemini-3.1-pro-high",
        "use_for": "Deep architecture, planning, security audits, subtle bug hunting, and second opinions",
    },
    "coding_or_edits": {
        "model": "gemini-3.8-flash-high",
        "use_for": "Fast multi-file code edits, refactoring, and unit test generation (accept-edits / autonomous)",
    },
    "balanced_research": {
        "model": "gemini-3.8-flash-medium",
        "use_for": "Balanced everyday codebase analysis, call-graph tracing, and Q&A",
    },
    "quick_lookup": {
        "model": "gemini-3.8-flash-low",
        "use_for": "Low-latency lookups, syntax checks, and trivial follow-ups",
    },
}


def _resolve_agy_bin() -> str:
    custom = os.environ.get("ANTIGRAVITY_BIN")
    if custom:
        return custom
    return shutil.which("agy") or "agy"


def _resolve_engine(requested: str) -> str:
    if requested in ("cli", "sdk"):
        return requested
    env_default = os.environ.get("ANTIGRAVITY_DEFAULT_ENGINE", "auto").lower()
    if env_default in ("cli", "sdk"):
        return env_default
    # Auto-detect: if GEMINI_API_KEY or GOOGLE_GENAI_USE_VERTEXAI is set, allow SDK;
    # otherwise default to the authenticated `agy` CLI binary.
    if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_GENAI_USE_VERTEXAI"):
        return "sdk"
    return "cli"


def _resolve_model(model: str | None, mode: str, effort: str) -> str:
    """Smart routing between Gemini 3.1 Pro and Gemini 3.8 Flash when model is 'auto' or omitted."""
    effective_model = model or os.environ.get("ANTIGRAVITY_DEFAULT_MODEL", "auto")
    if effective_model and effective_model != "auto":
        return effective_model
    if mode == "plan" or effort in ("high", "max"):
        return SMART_ROUTING_TIERS["plan_or_high_effort"]["model"]
    if mode in ("accept-edits", "autonomous"):
        return SMART_ROUTING_TIERS["coding_or_edits"]["model"]
    if effort == "low":
        return SMART_ROUTING_TIERS["quick_lookup"]["model"]
    return SMART_ROUTING_TIERS["balanced_research"]["model"]


async def _run_via_sdk(
    prompt: str,
    cwd: str | None,
    conversation_id: str | None,
    mode: str,
    model: str | None,
    include_thoughts: bool,
    system_instructions: str,
) -> dict:
    from google.antigravity import Agent, CapabilitiesConfig, LocalAgentConfig

    DEFAULT_SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

    # SDK requires conversation_id to be >= 32 alphanumeric/hyphen chars
    session_id = conversation_id or f"session-{uuid.uuid4()}"
    allow_writes = mode in ("accept-edits", "autonomous")

    config_kwargs: dict = {
        "system_instructions": system_instructions,
        "save_dir": str(DEFAULT_SESSIONS_DIR),
        "conversation_id": session_id,
    }
    if allow_writes:
        config_kwargs["capabilities"] = CapabilitiesConfig()
    if model:
        config_kwargs["model"] = model

    prev_cwd = os.getcwd()
    try:
        if cwd and os.path.isdir(cwd):
            os.chdir(cwd)

        config = LocalAgentConfig(**config_kwargs)
        async with Agent(config) as agent:
            response = await agent.chat(prompt)

            thoughts: list[str] = []
            if include_thoughts and hasattr(response, "thoughts"):
                async for thought in response.thoughts:
                    thoughts.append(thought)

            text = await response.text()
            usage = {}
            if getattr(response, "usage_metadata", None):
                usage = {
                    "total_tokens": getattr(
                        response.usage_metadata, "total_token_count", None
                    )
                }

            return {
                "engine": "sdk",
                "status": "SUCCESS",
                "conversation_id": session_id,
                "response": text,
                "thoughts": "".join(thoughts) if thoughts else None,
                "usage": usage,
            }
    finally:
        if cwd and os.path.isdir(cwd):
            os.chdir(prev_cwd)


async def _run_via_cli(
    prompt: str,
    cwd: str | None,
    conversation_id: str | None,
    mode: str,
    effort: str | None,
    model: str | None,
) -> dict:
    agy_bin = _resolve_agy_bin()
    cmd: list[str] = [agy_bin, "-p", prompt, "--output-format", "json"]

    if conversation_id:
        cmd.extend(["--conversation", conversation_id])

    if mode == "plan":
        cmd.extend(["--mode", "plan"])
    elif mode == "accept-edits":
        cmd.extend(["--mode", "accept-edits"])
    elif mode == "autonomous":
        cmd.extend(["--mode", "accept-edits", "--dangerously-skip-permissions"])

    if effort in ("low", "medium", "high", "max"):
        cmd.extend(["--effort", effort])

    if model:
        cmd.extend(["--model", model])

    work_dir = cwd if (cwd and os.path.isdir(cwd)) else os.getcwd()

    # Uses create_subprocess_exec (argument array) -> 100% immune to shell escaping bugs
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=work_dir,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout_bytes, stderr_bytes = await proc.communicate()
    stdout_text = stdout_bytes.decode("utf-8", errors="replace").strip()
    stderr_text = stderr_bytes.decode("utf-8", errors="replace").strip()

    if proc.returncode != 0 and not stdout_text:
        return {
            "engine": "cli",
            "status": "ERROR",
            "error": stderr_text or f"agy exited with code {proc.returncode}",
        }

    # Parse the JSON envelope emitted by `agy --output-format json`
    for line in reversed(stdout_text.splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                payload = json.loads(line)
                payload["engine"] = "cli"
                return payload
            except json.JSONDecodeError:
                pass

    return {
        "engine": "cli",
        "status": "SUCCESS" if proc.returncode == 0 else "ERROR",
        "response": stdout_text,
        "stderr": stderr_text or None,
    }


@mcp.tool()
async def antigravity_task(
    prompt: str,
    cwd: str | None = None,
    conversation_id: str | None = None,
    mode: Literal["read-only", "plan", "accept-edits", "autonomous"] = "read-only",
    effort: Literal["low", "medium", "high", "max"] = "medium",
    model: str | None = "auto",
    engine: Literal["auto", "cli", "sdk"] = "auto",
    include_thoughts: bool = False,
) -> str:
    """
    Delegate a coding, architecture, debugging, or review task to Google Antigravity.

    Works as a specialist Gemini-powered sub-agent for any host AI coding assistant
    (Claude Code, OpenAI Codex, Cursor, Windsurf, Cline, etc.).

    Args:
        prompt: Detailed task instructions, file paths, and context for Antigravity.
        cwd: Working directory for the task (defaults to current workspace root).
        conversation_id: Optional conversation ID from a previous call to continue a multi-turn session.
        mode:
            - "read-only": Safe investigation, code review, and Q&A (default).
            - "plan": Deep architectural planning mode (`/plan`).
            - "accept-edits": Auto-approves file creations and edits.
            - "autonomous": Auto-approves both file edits and terminal test commands.
        effort: Reasoning effort level ("low", "medium", "high", "max").
        model: Target model ID or "auto" for smart routing:
            - "gemini-3.1-pro-high": Deep architecture, planning, security/bug audits
            - "gemini-3.8-flash-high": Fast multi-file edits, refactoring, unit test writing
            - "gemini-3.8-flash-medium": Balanced everyday analysis
            - "gemini-3.8-flash-low": Quick lookups and simple checks
            - "gpt-oss-120b-medium": Open-weights cross-model verification
        engine: "auto" (default), "cli" (uses authenticated `agy` CLI), or "sdk" (uses `google-antigravity` Python SDK).
        include_thoughts: When using the SDK engine, include Gemini's internal reasoning trace.
    """
    chosen_engine = _resolve_engine(engine)
    chosen_model = _resolve_model(model, mode, effort)

    if chosen_engine == "sdk":
        result = await _run_via_sdk(
            prompt=prompt,
            cwd=cwd,
            conversation_id=conversation_id,
            mode=mode,
            model=chosen_model,
            include_thoughts=include_thoughts,
            system_instructions=(
                "You are Google Antigravity operating as a specialist sub-agent for an orchestrating "
                "coding agent. Provide thorough, high-signal technical answers and clean code changes."
            ),
        )
    else:
        result = await _run_via_cli(
            prompt=prompt,
            cwd=cwd,
            conversation_id=conversation_id,
            mode=mode,
            effort=effort,
            model=chosen_model,
        )

    result["model"] = chosen_model
    return json.dumps(result, indent=2, ensure_ascii=False)


@mcp.tool()
async def antigravity_list_models() -> str:
    """
    List available Google Antigravity models and the active smart-routing configuration.
    """
    agy_bin = _resolve_agy_bin()
    models: list[dict[str, str]] = []
    try:
        proc = await asyncio.create_subprocess_exec(
            agy_bin,
            "models",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_bytes, _ = await proc.communicate()
        for line in stdout_bytes.decode("utf-8", errors="replace").splitlines():
            if "\t" in line:
                model_id, display_name = line.split("\t", 1)
                models.append({"id": model_id.strip(), "name": display_name.strip()})
    except Exception as exc:
        return json.dumps(
            {
                "smart_routing_tiers": SMART_ROUTING_TIERS,
                "error_fetching_live_models": str(exc),
            },
            indent=2,
        )

    return json.dumps(
        {
            "smart_routing_tiers": SMART_ROUTING_TIERS,
            "available_models": models,
        },
        indent=2,
        ensure_ascii=False,
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
