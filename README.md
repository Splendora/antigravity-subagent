# Universal Google Antigravity Sub-Agent (MCP + CLI + Skills)

Delegate coding, architectural planning, security/bug audits, and cross-model verification tasks to **Google Antigravity** (Gemini 3.1 Pro & Gemini 3.8 Flash) from **any AI coding agent**—including **Claude Code**, **OpenAI Codex**, **Cursor**, **Windsurf**, and terminal workflows.

---

## Key Features

1. **Universal MCP Server ([`agy_mcp_server.py`](./agy_mcp_server.py))**
   - Exposes `antigravity_task` and `antigravity_list_models` over stdio (`MCPServer` / `mcp` 2.x with 1.x fallback).
   - **Dual-Engine Execution**:
     - **`cli` engine (default when `GEMINI_API_KEY` is not set)**: Invokes `agy` via `asyncio.create_subprocess_exec` (argument array, 100% immune to shell-escaping bugs) using your cached Google Antigravity login.
     - **`sdk` engine (auto-selected when `GEMINI_API_KEY` or `GOOGLE_GENAI_USE_VERTEXAI` is set, or `engine="sdk"`)**: Uses the official `google-antigravity` Python SDK (`Agent`, `LocalAgentConfig`, `CapabilitiesConfig`) with stateful session persistence and Gemini reasoning trace capture.
2. **Automatic Smart Model Routing**
   - When `model="auto"` (default), automatically selects the optimal model based on `mode` and `effort`:
     | Task Type | Mode / Effort | Routed Model |
     | :--- | :--- | :--- |
     | **Architecture, Planning, Security & Bug Audits** | `mode="plan"` or `effort="high"` / `"max"` | `gemini-3.1-pro-high` |
     | **Autonomous Coding, Refactoring & Unit Tests** | `mode="accept-edits"` or `mode="autonomous"` | `gemini-3.8-flash-high` |
     | **Everyday Codebase Research & Analysis** | `mode="read-only"`, `effort="medium"` | `gemini-3.8-flash-medium` |
     | **Quick Lookups & Trivial Checks** | `mode="read-only"`, `effort="low"` | `gemini-3.8-flash-low` |
3. **One-Command Multi-Agent Installer ([`agy_subagent_cli.py`](./agy_subagent_cli.py))**
   - Automatically configures MCP servers, subagents, skills, and rules for **Claude Code**, **OpenAI Codex**, **Cursor**, and **Windsurf** without manual path editing.
4. **Standalone CLI Runner (`antigravity-subagent run`)**
   - Allows shell-based agents (like OpenAI Codex CLI, Aider, or CI scripts) to invoke Antigravity directly from the terminal even when MCP is disabled.

---

## Quick Start (Any Machine / OS)

### 1. Install in a Virtual Environment

```bash
python -m venv .venv
# Windows:
.venv\Scripts\python -m pip install -e .
# macOS / Linux:
.venv/bin/pip install -e .
```

### 2. Auto-Configure Your Coding Agents

Install globally (`--scope user`) or into a specific repository (`--scope project`):

```bash
# Configure ALL supported clients (Claude Code, OpenAI Codex, Cursor, Windsurf) globally:
antigravity-subagent install --client all --scope user

# Or configure a specific client:
antigravity-subagent install --client codex --scope user
antigravity-subagent install --client claude --scope user
antigravity-subagent install --client cursor --scope project --target-dir /path/to/repo
```

---

## What Gets Configured Per Client

| Client | User-Scope Config (`--scope user`) | Project-Scope Config (`--scope project`) |
| :--- | :--- | :--- |
| **Claude Code** | `~/.claude.json` (`mcpServers.antigravity`) + `~/.claude/agents/antigravity.md` | `.mcp.json` + `.claude/agents/antigravity.md` |
| **OpenAI Codex** | `~/.codex/config.toml` (`[mcp_servers.antigravity]`) + `~/.agents/skills/antigravity/SKILL.md` + `~/.codex/skills/antigravity/SKILL.md` | `.codex/config.toml` + `.agents/skills/antigravity/SKILL.md` + `AGENTS.md` |
| **Cursor** | `~/.cursor/mcp.json` | `.cursor/mcp.json` + `.cursor/rules/antigravity.mdc` |
| **Windsurf** | `~/.codeium/windsurf/mcp_config.json` | — |

---

## Direct CLI Usage (No MCP Required)

Any agent with terminal access (or you directly) can run tasks and resume multi-turn conversations via CLI:

```bash
# Run a high-effort architectural review (routes to gemini-3.1-pro-high):
antigravity-subagent run "Review agy_mcp_server.py for edge cases" --cwd . --mode read-only --effort high

# Resume the same session using its conversation_id:
antigravity-subagent run "Apply your first suggestion" --cwd . --mode accept-edits --conversation <conversation_id>

# List smart routing tiers and available models:
antigravity-subagent models
```

---

## Optional Environment Variables

- `ANTIGRAVITY_DEFAULT_MODEL`: Override the default `"auto"` model (e.g., `"gemini-3.1-pro-high"`).
- `ANTIGRAVITY_DEFAULT_ENGINE`: Force `"cli"` or `"sdk"` (default: `"auto"`).
- `ANTIGRAVITY_SESSIONS_DIR`: Custom directory for SDK session persistence (default: `~/.gemini/antigravity-subagent/sessions`).
- `ANTIGRAVITY_BIN`: Custom path to the `agy` executable if not on `PATH`.
