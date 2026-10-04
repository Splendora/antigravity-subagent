# Google Antigravity Sub-Agent Instructions (`AGENTS.md`)

You have access to **Google Antigravity** (powered by Gemini 3.1 Pro and Gemini 3.8 Flash) as a stateful specialist sub-agent for cross-model verification, architectural planning, deep bug hunting, and parallel code implementation.

## How to Delegate to Antigravity

### Option A: Via MCP Tool (`antigravity_task`) — *Preferred*
Call `antigravity_task` (or `mcp__antigravity__antigravity_task`) with:
- `prompt`: Detailed, self-contained instructions including file paths, symbols, or error traces.
- `cwd`: Current workspace root directory.
- `mode`:
  - `"read-only"` (default): Code review, second opinions, security/bug audits, codebase Q&A.
  - `"plan"`: Deep architectural planning (`/plan`).
  - `"accept-edits"`: Auto-approve file creations and edits.
  - `"autonomous"`: Auto-approve both file edits and terminal test execution.
- `effort`: `"low"`, `"medium"`, `"high"`, or `"max"`.
- `model`: `"auto"` (default) automatically routes to:
  - `gemini-3.1-pro-high` when `mode="plan"` or `effort="high"`/`"max"`
  - `gemini-3.8-flash-high` when `mode="accept-edits"` or `"autonomous"`
  - `gemini-3.8-flash-medium` for general analysis
  - `gemini-3.8-flash-low` when `effort="low"`
- `conversation_id`: Pass the `conversation_id` returned from a previous call to continue a multi-turn session without losing context.

### Option B: Via Terminal CLI (`antigravity-subagent run`)
If MCP is not active in the current session, run the CLI directly:
```bash
antigravity-subagent run "<prompt>" --cwd . --mode read-only --effort high
```
To follow up on the same session:
```bash
antigravity-subagent run "<follow-up prompt>" --cwd . --mode accept-edits --conversation <conversation_id>
```
