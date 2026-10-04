---
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
