# Backstory

**Git shows what changed. Backstory shows why.**
*The reasoning layer your git history is missing.*

---

You're reading a commit the AI wrote three weeks ago. Something is broken.

- Why did it reject the simpler approach?
- What tradeoffs did it accept that you didn't notice?
- Which decision from last sprint is this about to undo?

There's no author to ask. The chat is gone. The commit message says *what* changed.

![Backstory terminal walkthrough](docs/assets/how-it-works-terminal.gif)

## How It Works

![Backstory flow diagram](docs/assets/how-it-works-flow.gif)

1. **Capture** — Claude Code's `SessionEnd` hook (set up by `backstory init`) copies the transcript to `.backstory/transcripts/latest.jsonl`.
2. **Ingest** — Backstory extracts the durable decisions, risks, and changed files. The raw conversation is discarded.
3. **Link** — The session is attached to the relevant Git commit via `backstory attach HEAD`.
4. **Retrieve** — Query reasoning by commit, file, line, range, or diff.

Git stays the linkage layer. Backstory stores the reasoning.

## Contradiction Detection

An archive is useful. A guardrail is valuable.

Backstory watches for new changes that reverse earlier recorded decisions — and warns you before you merge.

```text
⚠ This change may contradict a decision from commit 8f21c9a:
  "payment.failed should mark subscription as pending, not cancelled"
```

## What You Get

**Understand any commit.** `backstory why HEAD` tells you why a commit happened — rejected alternatives, accepted risks, the full chain of reasoning.

**Find the reasoning behind any line.** Query by file, line, or range. If the AI made a specific decision about that code, Backstory surfaces it.

**Catch reversals before they ship.** Contradiction detection warns when a new change undoes a past decision. Turns an archive into a guardrail.

## Quick Install

**Install from PyPI** (recommended):

```bash
pip install backstory-cli
```

**Run from source** (no install needed):

```bash
git clone https://github.com/arpitkath/backstory.git
cd backstory
python -m backstory init
python -m backstory test
```

Then initialize and verify in your repo:

```bash
backstory init
backstory test    # verify everything is set up correctly
```

> See a [full worked example](examples/ai-subscription-bug/demo.md) with before/after code and stored session.

## Commands at a Glance

| Command | What it does |
|---|---|
| `backstory init` | Set up Backstory in the current repo |
| `backstory why HEAD` | Explain why a commit happened |
| `backstory file <path>` | Show AI context relevant to a file |
| `backstory line <path>:<line>` | Show the decision behind a specific line |
| `backstory diff` | Show prior context for uncommitted changes |

See the [full reference](#reference) below.

## Privacy

Backstory is local-first by design. No cloud service or telemetry is required. Raw transcripts are never persisted — only extracted decisions, risks, follow-ups, and Git context are kept. Built-in redaction scans for and removes API keys and secrets during ingestion.

## Integration

**Works with Claude Code automatically** after `backstory init`. Cursor and Codex support planned.

Backstory uses a `SessionEnd` lifecycle hook in `.claude/settings.json` to capture
transcripts automatically — no env vars or manual paths needed:

```json
{
  "env": {
    "CLAUDE_CODE_SESSIONEND_HOOKS_TIMEOUT_MS": "120000"
  },
  "hooks": {
    "SessionEnd": [{
      "hooks": [{
        "type": "command",
        "command": "backstory session-end",
        "timeout": 600,
        "statusMessage": "Archiving session..."
      }]
    }]
  }
}
```

`backstory init` writes this config for you.

Backstory also supports Claude Code v2.1+'s JSONL transcript format natively.

See the [integration guide](docs/integration.md) for step-by-step setup.

## Reference

| Command | Status | What it does |
|---|---|---|
| `backstory init` | ✅ Stable | Set up Backstory in the current repo |
| `backstory dump` | ✅ Stable | Ingest an AI session into OKF markdown |
| `backstory attach HEAD` | ✅ Stable | Link a session to a commit |
| `backstory why HEAD` | ✅ Stable | Explain why a commit happened |
| `backstory test` | ✅ Stable | Run self-test to verify installation and setup |
| `backstory search <query>` | ✅ Stable | Search past sessions and decisions |
| `backstory diff` | ✅ Stable | Show prior context for uncommitted changes |
| `backstory file <path>` | ✅ Stable | Show AI context relevant to a file |
| `backstory line <path>:<line>` | ✅ Stable | Show the decision behind a specific line |
| `backstory range <path>:start-end` | ✅ Stable | Show context for a range of lines |
| `backstory code <path>:start-end` | ✅ Stable | Show why a code block exists |
| `backstory redact` | ✅ Stable | Re-scan and redact sensitive data |
| `backstory hooks` | ✅ Stable | Manage Git hook installation |
| `backstory show <session>` | 🧪 Experimental | View a stored session |
| `backstory session-end` | 🔧 Internal | SessionEnd hook handler (used by Claude Code) |

## Storage

```text
.backstory/
  config.json
  transcripts/
    latest.jsonl
  knowledge/
    index.md
    sessions/
      index.md
      latest.md
      sha256-<session>.md
  redactions/
    tombstones.log
```

Session memory is stored as Google's OKF-style markdown — human-readable, Git-friendly, and agent-friendly.

## Documentation

- [Integration guide](docs/integration.md) — Set up with Claude Code and other tools
- [Engineering walkthrough](docs/engineering-walkthrough.md)
- [Product spec](docs/prd.md)
- [Retrieval model](docs/retrieval.md)

---

[![PyPI version](https://img.shields.io/pypi/v/backstory-cli)]()
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)]()
[![License](https://img.shields.io/badge/license-MIT-green)]()
[![Knowledge Format](https://img.shields.io/badge/knowledge%20format-OKF-orange)]()
[![Local-first](https://img.shields.io/badge/local--first-no--cloud-purple)]()
[![CI](https://github.com/arpitkath/backstory/actions/workflows/publish.yml/badge.svg)](https://github.com/arpitkath/backstory/actions/workflows/publish.yml)

If you find this useful, [starring the repo](https://github.com/arpitkath/backstory) helps others discover it.
