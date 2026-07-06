# Integration Guide

How to connect Backstory to AI coding tools so session memory captures
automatically.

---

## How Backstory Integrates

Backstory exposes three integration surfaces:

| Surface | What it does | Used by |
|---|---|---|
| `backstory dump --transcript` | Ingest an exported transcript file | Any tool that writes transcripts to disk |
| `backstory dump --stdin` | Ingest a transcript piped via stdin | Scripts, wrapper commands |
| Git hooks | Auto-capture on commit | Any Git-based workflow |

The Git hooks are the simplest path — they work with every tool because they
fire on `git commit`, regardless of which AI tool produced the work.

---

## Git Hooks (Works with Any Tool)

Installed by `backstory init`:

```bash
backstory init
```

This writes two Git hooks:

- **pre-commit** — runs `backstory dump --hook pre-commit` to capture any
  pending session context before the commit.
- **post-commit** — runs `backstory attach HEAD --hook post-commit` to link
  the captured session to the new commit.

No tool-specific configuration needed. Every `git commit` captures and
attaches the reasoning behind the change.

---

## Claude Code

### Option A: Git Hooks (simplest)

Just run `backstory init` in the repo. The pre-commit and post-commit hooks
capture Claude Code sessions automatically on each commit.

### Option B: CLAUDE.md Instructions

Add a section to your project's `CLAUDE.md` so Claude Code knows about
Backstory and runs it as part of its workflow:

```markdown
## Memory

After completing a task or making changes, capture the session:

    backstory dump --agent claude-code --transcript /path/to/transcript.md
    backstory attach HEAD
```

Or for a self-contained workflow where Claude runs Backstory after each task
completion, add instructions like:

```markdown
## After each task

1. Run `backstory dump --stdin` with a summary of what was done.
2. Run `backstory attach HEAD` to link it to the commit.
```

### Option C: Claude Code Settings Hooks

Claude Code supports lifecycle hooks via `.claude/settings.json`. These fire
on events like task completion, letting Backstory capture automatically:

```json
{
  "hooks": {
    "onTaskComplete": "backstory dump --stdin"
  }
}
```

This creates a session from the final conversation summary every time a
Claude Code task finishes. The `--stdin` flag accepts piped content, so if
your workflow has structured output, pipe it:

```json
{
  "hooks": {
    "onTaskComplete": "echo 'Task complete' | backstory dump --stdin"
  }
}
```

### Option D: Manual Retrieval During a Session

While working with Claude Code, query past decisions:

```bash
# Why did this file change?
backstory why HEAD

# What decisions touched this file?
backstory file src/api/handler.py

# Why does this exact line exist?
backstory line src/api/handler.py:42
```

Add these as `read-only` commands in your CLAUDE.md to let Claude Code
retrieve context automatically:

```markdown
## Context Retrieval

Before modifying a file, check what decisions exist for it:

    backstory file <path>
```

---

## Codex

Codex supports post-session scripts and commit hooks.

### Post-Session Hook

Configure Codex to run Backstory after each session by adding a shell
command to your Codex configuration:

```bash
# In your Codex config or post-session script:
backstory dump --agent codex --transcript ./codex-session.log
```

The exact path depends on where Codex writes its transcript/log files.
Check your Codex output directory and point `--transcript` at it.

### Git Hooks

Same as any other tool — `backstory init` hooks fire on `git commit`
regardless of which tool wrote the code.

---

## Cursor

### Cursor Rules

Add a Cursor rule to run Backstory after changes. Create or edit
`.cursorrules` in your project root:

```
After making changes and committing, run:
  backstory attach HEAD
```

### Git Hooks

As with every other tool, `backstory init` hooks work automatically
with Cursor — the hooks fire on `git commit`, not on the AI tool.

---

## General Tool Integration

### Transcript Ingestion

For any AI tool that writes a transcript, log, or session file to disk:

```bash
backstory dump --agent <tool-name> --transcript <path>
```

Supported agent names: `claude`, `claude-code`, `codex`, `cursor`, `copilot`,
or a custom label.

### Stdin Ingestion

For tools or scripts that produce structured output:

```bash
generate-transcript | backstory dump --stdin --agent my-tool
```

### Automatic Capture Wrapper

Wrap your AI tool in a script that captures after every session:

```bash
#!/bin/sh
# save as ~/bin/ai-code
ai-tool "$@"
backstory dump --stdin --agent ai-tool
backstory attach HEAD
```

---

## Claude / Tools — Using Backstory as a Claude Tool

Backstory commands can be listed as available tools for Claude (Claude Code,
claude.ai, or any Claude-powered coding tool) so Claude can invoke them
directly during a session.

### In CLAUDE.md (Claude Code)

Add a tools block to your `CLAUDE.md`:

````markdown
## Available Tools

Before modifying code, you can retrieve past decisions:

- `backstory file <path>` — Show decisions linked to a file
- `backstory line <path>:<line>` — Show why a specific line exists
- `backstory why HEAD` — Explain the last commit
- `backstory search <query>` — Search across all stored sessions

After making changes:

- `backstory dump --stdin` — Ingest the session
- `backstory attach HEAD` — Link it to the commit
````

Then instruct Claude to use them:

```markdown
## Workflow

1. Before editing a file, check `backstory file <path>` for context.
2. After completing changes, run `backstory dump --stdin` followed by
   `backstory attach HEAD`.
```

### In Claude Code Hooks (`.claude/settings.json`)

For fully automatic capture, configure lifecycle hooks:

```json
{
  "hooks": {
    "onTaskStart": "backstory file . 2>/dev/null | head -20",
    "onTaskComplete": "echo 'Task completed.' | backstory dump --stdin --agent claude-code"
  }
}
```

- `onTaskStart` — retrieves relevant past decisions at the start of a task.
- `onTaskComplete` — captures the session reasoning when the task finishes.

### In MCP / Tool-Use APIs

If you're building a custom Claude integration (via the API or MCP),
Backstory commands can be exposed as tools that Claude can call:

```json
{
  "name": "backstory_why",
  "description": "Explain why a commit was made by retrieving stored decisions",
  "input_schema": {
    "type": "object",
    "properties": {
      "commit": {
        "type": "string",
        "description": "Commit reference (default: HEAD)"
      }
    }
  }
}
```

Point the tool handler at `backstory why <commit>` or `backstory file <path>`
and Claude can retrieve past decisions during a conversation.

---

## Summary

| Tool | Recommended approach |
|---|---|
| Any tool (Git-based) | `backstory init` — Git hooks |
| Claude Code | Git hooks + CLAUDE.md instructions |
| Claude Code (advanced) | `.claude/settings.json` lifecycle hooks |
| Codex | Post-session script + Git hooks |
| Cursor | Git hooks + .cursorrules note |
| Custom Claude integration | MCP tool or CLAUDE.md tool list |
| Any AI tool | `backstory dump --transcript <path>` |
