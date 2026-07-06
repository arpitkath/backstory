# PRD: AI Commit Memory CLI

## 1. Product Name

Name: **backstory**

Tagline: "Every AI-assisted commit has a backstory. Never lose it again."

---

## 2. Problem Statement

Modern developers increasingly use AI coding agents like Claude Code, Codex, Cursor, Cline, and others to write, refactor, debug, and review code.

Git stores the final output of these changes through commits and diffs, but it does not preserve the full reasoning behind them.

Important context is lost, such as:

* What task was the AI agent solving?
* What files or documentation did it inspect before making changes?
* What alternatives were considered?
* What errors happened during implementation?
* Why was a specific approach chosen?
* What instructions or constraints did the developer give?
* What tests or commands were run?
* What risks or follow-ups were mentioned?
* What parts of the conversation influenced the final commit?

This creates a gap between **what changed** and **why it changed**.

The goal of this product is to preserve the complete AI development context behind code changes and link it to Git commits for future reference.

---

## 3. Product Goal

Build a local-first Python CLI tool that automatically captures AI coding sessions, compresses and stores them, summarizes the reasoning, and links the session to Git commits using pre-commit and post-commit hooks.

The product should make it easy for a developer to later ask:

```bash
backstory why HEAD
```

And understand the full context behind a commit.

---

## 4. Core Value Proposition

Git shows the code diff.

`backstory` shows the reason behind the diff.

The tool should help developers preserve:

* Task description and goal
* Files changed
* Key decisions made
* Risks and follow-ups
* Alternatives considered
* Commit linkage

---

## 5. Target Users

### Primary Users

Individual developers using AI agents to write code.

### Secondary Users

Small engineering teams using AI coding tools heavily.

### Future Users

Engineering teams that need AI-assisted code audit trails, compliance history, onboarding context, or review support.

---

## 6. Scope

### In Scope for MVP

The first version should be CLI-only.

It should support:

* Repository initialization
* Local session storage
* Git pre-commit hook
* Git post-commit hook
* Manual session dump
* Commit-to-session linking
* Compressed immutable session storage
* Human-readable summary generation
* Secret redaction before storage
* Search by commit, file, branch, or text query
* Viewing why a commit happened
* Basic integrations through local transcript files or manual capture

### Out of Scope for MVP

The first version should not include:

* Cloud dashboard
* Team sync
* Browser UI
* VS Code extension
* Cursor extension
* Full MCP server
* PR comments
* SaaS billing
* Organization management
* Realtime agent control
* Code generation features

The product is not an AI coding agent. It is a memory and provenance layer for AI-assisted code.

---

## 7. Core User Flow

### Initial Setup

Developer installs the CLI:

```bash
pipx install backstory
```

Or:

```bash
python -m pip install backstory
```

Then inside a Git repository:

```bash
backstory init
```

This should:

* Create `.backstory/`
* Create `.backstory/config.json`
* Create `.backstory/objects/`
* Create `.backstory/summaries/`
* Create `.backstory/index.sqlite`
* Install Git pre-commit hook
* Install Git post-commit hook
* Add recommended ignore rules
* Validate that the current directory is a Git repository

---

### AI Coding Session

Developer works normally with an AI coding tool.

At task completion, one of these happens:

```bash
backstory dump
```

Or the AI tool integration calls:

```bash
backstory dump --agent claude --transcript <path>
```

The tool captures:

* Current branch
* Git status
* Current diff
* Recent changed files
* AI transcript if available
* Optional user task description
* Timestamps
* Agent name
* Model name if available
* Commands/logs if available

The session is then:

* Sent to the AI agent for summarization (only structured decisions extracted)
* Normalized into JSON
* Compressed
* Stored locally — no raw conversation text is persisted
* Indexed for search
* Given a content hash

> **Privacy:** Raw transcripts are never stored. The agent reads its own
> conversation and returns only structured facts: task, decisions, risks,
> follow-ups, and file paths. Everything else is discarded.

---

### Commit Creation

Developer creates a commit:

```bash
git add .
git commit -m "Fix subscription renewal handling"
```

The pre-commit hook should:

* Detect whether there is an active or recent AI session
* Capture current staged diff
* Generate or update a short reasoning summary
* Warn if sensitive data is detected
* Store a pending session record
* Never block the commit unless configured to do so

The post-commit hook should:

* Get the final commit hash
* Attach the session pointer to the commit
* Save a human-readable summary for that commit
* Update the local index
* Optionally write Git notes

---

### Future Retrieval

Later, developer runs:

```bash
backstory why HEAD
```

Output:

```text
Commit: 8f21c9a
Message: Fix subscription renewal handling
Branch: main
AI Agent: Claude Code
Session: sha256:abc123

Task:
Fix renewal logic for subscriptions when payment succeeds, fails, or is halted.

Why this changed:
The webhook handler was not updating the next billing date after successful recurring charges. Failed payments were also not clearly separated from cancelled subscriptions.

Files changed:
- app/api/webhooks/razorpay/route.ts
- lib/subscription.ts
- db/migrations/add_next_due_on.sql

Key decisions:
- subscription.charged updates next_due_on.
- payment.failed marks subscription as pending, not cancelled.
- subscription.cancelled revokes Pro access.
- webhook events should be idempotent.

Commands run:
- uv run ruff check
- uv run pytest tests/test_webhooks.py

Risks:
- Idempotency depends on storing Razorpay event IDs.
- Existing users without next_due_on need backfill.

Raw session:
.backstory/objects/abc123.json.zst
```

---

## 8. CLI Commands

### `backstory init`

Initializes AI memory in the current Git repo.

```bash
backstory init
```

Options:

```bash
backstory init --no-hooks
backstory init --storage local
backstory init --force
```

Expected behavior:

* Validate Git repo
* Create local storage
* Install hooks
* Create config
* Print next steps

---

### `backstory dump`

Captures an AI session manually.

```bash
backstory dump
```

Options:

```bash
backstory dump --agent claude
backstory dump --agent codex
backstory dump --transcript ./session.json
backstory dump --task "Fix webhook subscription handling"
backstory dump --no-redact
backstory dump --attach HEAD
```

Expected behavior:

* Capture current Git state
* Import transcript if provided
* Generate session object
* Redact secrets
* Compress and store
* Add to index
* Optionally attach to commit

---

### `backstory attach`

Attaches a stored session to a commit.

```bash
backstory attach HEAD
backstory attach abc123
```

Options:

```bash
backstory attach HEAD --session latest
backstory attach HEAD --session sha256:abc123
```

Expected behavior:

* Resolve commit hash
* Resolve session hash
* Link session to commit
* Create or update Git note
* Save summary file

---

### `backstory why`

Explains why a commit happened.

```bash
backstory why HEAD
backstory why abc123
```

Options:

```bash
backstory why HEAD --raw
backstory why HEAD --summary
backstory why HEAD --json
```

Expected behavior:

* Load commit metadata
* Load attached session
* Print human-readable reason
* Include files, task, decisions, commands, risks, and raw session pointer

---

### `backstory show`

Shows the raw or structured session.

```bash
backstory show sha256:abc123
```

Options:

```bash
backstory show sha256:abc123 --raw
backstory show sha256:abc123 --json
backstory show sha256:abc123 --summary
```

---

### `backstory search`

Searches stored sessions.

```bash
backstory search "payment failed subscription"
```

Options:

```bash
backstory search "Razorpay" --file app/api/webhooks/razorpay/route.ts
backstory search "auth refresh" --branch main
backstory search "idempotency" --since 30d
```

Expected behavior:

* Search summaries first
* Search indexed metadata
* Optionally search decompressed transcripts
* Return matching sessions and commits

---

### `backstory context`

Shows previous AI context related to a file.

```bash
backstory context src/auth/session.ts
```

Expected behavior:

* Find commits touching the file
* Find attached AI sessions
* Summarize relevant prior decisions
* Show risks and previous constraints

---

### `backstory status`

Shows current AI memory status.

```bash
backstory status
```

Expected output:

```text
AI Memory: enabled
Git hooks: installed
Current branch: main
Pending session: yes
Latest session: sha256:abc123
Attached to HEAD: no
Storage size: 4.2 MB
```

---

### `backstory redact`

Runs redaction on stored or pending sessions.

```bash
backstory redact
backstory redact sha256:abc123
```

Expected behavior:

* Scan for secrets
* Create redacted replacement object
* Add tombstone record for old object
* Never silently mutate old records

---

## 9. Git Hook Behavior

### Pre-Commit Hook

Runs before commit creation.

Responsibilities:

* Capture staged diff
* Detect active or recent AI session
* Generate pending session snapshot
* Run secret scan
* Warn user if raw transcript contains likely secrets
* Store temporary pending metadata

Default behavior:

* Should not block commit
* Should only warn
* Should be fast

Configurable behavior:

```json
{
  "hooks": {
    "preCommit": {
      "enabled": true,
      "blockOnSecrets": false,
      "captureStagedDiff": true
    }
  }
}
```

---

### Post-Commit Hook

Runs after commit creation.

Responsibilities:

* Resolve final commit hash
* Attach latest pending session to commit
* Save commit summary
* Write Git note or local metadata
* Update search index

Default behavior:

* Attach automatically if a pending session exists
* If no session exists, do nothing
* Never modify committed code

Configurable behavior:

```json
{
  "hooks": {
    "postCommit": {
      "enabled": true,
      "autoAttach": true,
      "writeGitNotes": true
    }
  }
}
```

---

## 10. Data Model

### Session Object

Each session stores only factual reasoning — never raw conversations.

The session is built from structured decisions extracted by the AI agent
that made the changes (Claude Code, Codex, etc.). No transcript text is
persisted.

Example:

Example:

```json
{
  "version": "1.0",
  "session_id": "sha256:abc123",
  "created_at": "2026-07-05T12:00:00Z",
  "repo": {
    "name": "agenticprep",
    "root": "/repo/path",
    "branch": "main",
    "head_before": "a1b2c3",
    "head_after": "8f21c9a"
  },
  "agent": {
    "name": "claude-code",
    "model": "claude-sonnet",
    "source": "hook"
  },
  "task": {
    "title": "Fix subscription renewal handling",
    "user_prompt": "Handle Razorpay subscription charged, failed, halted and cancelled events."
  },
  "files": {
    "changed": [],
    "created": [],
    "deleted": []
  },
  "commands": [
    {
      "command": "uv run ruff check",
      "status": "success"
    }
  ],
  "diff": {
    "staged": "",
    "unstaged": "",
    "summary": ""
  },
  "reasoning_summary": {
    "why": "The webhook handler was not updating the next billing date after successful recurring charges.",
    "decisions": [
      "subscription.charged updates next_due_on",
      "payment.failed marks subscription as pending, not cancelled"
    ],
    "alternatives": [],
    "risks": [
      "Existing users without next_due_on need backfill"
    ],
    "followups": [
      "Add monitoring for webhook failures"
    ]
  },
  "commit": {
    "hash": "8f21c9a",
    "message": "Fix subscription renewal handling"
  },
  "redaction": {
    "status": "redacted",
    "matches": []
  }
}
```

---

## 11. Local Storage Structure

```text
.backstory/
  config.json
  index.sqlite
  objects/
    abc123.json.zst
  summaries/
    8f21c9a.md
  pending/
    latest.json
  redactions/
    tombstones.log
```

### Storage Rules

* Raw sessions should be compressed.
* Session objects should be content-addressed by hash.
* Stored session objects should be immutable.
* If redaction is needed, create a new redacted object.
* Add a tombstone entry pointing from old object to new object.
* Do not store raw secrets after redaction.

---

## 12. Commit Linking

The tool should support two linking strategies.

### Preferred: Git Notes

Attach metadata to a commit without changing the commit message.

Example note:

```json
{
  "ai_session": "sha256:abc123",
  "summary": ".backstory/summaries/8f21c9a.md",
  "agent": "claude-code",
  "created_at": "2026-07-05T12:05:00Z"
}
```

### Fallback: Local Index

If Git notes are disabled, store mapping locally:

```text
commit_hash -> session_hash
```

In:

```text
.backstory/index.sqlite
```

MVP should support both, with Git notes enabled by default.

---

## 13. Redaction and Privacy

This is critical.

AI conversations may contain:

* API keys
* Tokens
* Customer data
* Production URLs
* Database credentials
* Private business context
* Internal architecture details

The product should be local-first by default.

### Redaction Requirements

Before storing a session:

* Scan for common secret patterns
* Detect `.env` values
* Detect private keys
* Detect tokens
* Detect passwords
* Detect database URLs
* Detect cloud credentials
* Warn the user

Default behavior:

* Redact obvious secrets automatically
* Warn but do not block

Configurable behavior:

```json
{
  "redaction": {
    "enabled": true,
    "blockOnHighConfidenceSecrets": false,
    "customPatterns": []
  }
}
```

---

## 14. Summary Generation

The tool should generate a human-readable summary for each session.

Summary should include:

* Task
* Why change was needed
* Files changed
* Key decisions
* Alternatives considered
* Commands run
* Tests run
* Errors encountered
* Risks
* Follow-ups
* Linked commit

Example summary file:

```md
# AI Memory for Commit 8f21c9a

## Task

Fix subscription renewal handling.

## Why

The webhook handler was not correctly updating subscription state after recurring payment events.

## Key Decisions

- `subscription.charged` updates `next_due_on`.
- `payment.failed` marks subscription as pending.
- `subscription.cancelled` revokes Pro access.
- Webhook handling must be idempotent.

## Files Changed

- `app/api/webhooks/razorpay/route.ts`
- `lib/subscription.ts`

## Commands Run

- `uv run ruff check`
- `uv run pytest tests/test_webhooks.py`

## Risks

- Existing subscriptions may need data backfill.
- Duplicate webhook events must be handled safely.

## Raw Session

`sha256:abc123`
```

---

## 15. Configuration

Example `.backstory/config.json`:

```json
{
  "version": "1.0",
  "storage": {
    "mode": "local",
    "compress": true,
    "compression": "zstd"
  },
  "git": {
    "useGitNotes": true,
    "autoAttach": true
  },
  "hooks": {
    "preCommit": {
      "enabled": true,
      "captureStagedDiff": true,
      "blockOnSecrets": false
    },
    "postCommit": {
      "enabled": true,
      "autoAttach": true
    }
  },
  "redaction": {
    "enabled": true,
    "blockOnHighConfidenceSecrets": false,
    "customPatterns": []
  },
  "summary": {
    "enabled": true,
    "provider": "local-or-configured-llm"
  }
}
```

---

## 16. Functional Requirements

### P0 Requirements

* CLI can initialize in a Git repo.
* CLI can install Git hooks.
* CLI can capture a session manually.
* CLI can store compressed session files.
* CLI can attach a session to a Git commit.
* CLI can show why a commit happened.
* CLI can generate a readable summary.
* CLI can redact obvious secrets.
* CLI can search summaries by text.
* CLI works fully local-first.

### P1 Requirements

* Import transcript from Claude Code.
* Import transcript from Codex.
* Support multiple sessions per commit.
* Support multiple commits per session.
* Support file-level context lookup.
* Support branch-level search.
* Support JSON output for scripting.
* Support redaction tombstones.

### P2 Requirements

* Optional team sync.
* Optional PR comment generation.
* Optional MCP server.
* Optional IDE extension.
* Optional hosted dashboard.
* Optional embeddings-based semantic search.

---

## 17. Non-Functional Requirements

### Performance

* Pre-commit hook should complete quickly.
* Large transcript compression should happen asynchronously where possible.
* Commit should not be slowed significantly.

### Reliability

* Tool should never corrupt Git history.
* Tool should never block normal Git usage by default.
* If `backstory` fails, Git commit should continue unless strict mode is enabled.

### Security

* Local-first storage.
* Redaction enabled by default.
* No cloud upload by default.
* No telemetry by default.
* Clear handling of sensitive data.

### Portability

* Should work on macOS, Linux, and Windows.
* Should work in any Git repository.
* Should not depend on a specific AI coding tool.

---

## 18. MVP User Stories

### Story 1: Initialize Repo

As a developer, I want to run:

```bash
backstory init
```

So that my repository starts capturing AI coding context automatically.

Acceptance criteria:

* `.backstory/` is created.
* Git hooks are installed.
* Config file is created.
* CLI confirms setup.

---

### Story 2: Capture AI Session

As a developer, I want to run:

```bash
backstory dump --task "Fix auth refresh bug"
```

So that my AI coding session is saved before I commit.

Acceptance criteria:

* Current Git state is captured.
* Session is compressed.
* Summary is generated.
* Session appears in `backstory status`.

---

### Story 3: Auto-Link Session to Commit

As a developer, I want the latest AI session to automatically link to my Git commit.

Acceptance criteria:

* Pre-commit captures staged diff.
* Post-commit attaches session to commit hash.
* `backstory why HEAD` shows the session summary.

---

### Story 4: Explain Commit Later

As a developer, I want to run:

```bash
backstory why HEAD
```

So that I can understand why the code changed.

Acceptance criteria:

* Shows task.
* Shows reason.
* Shows files changed.
* Shows decisions.
* Shows tests/commands.
* Shows risks/follow-ups.
* Shows raw session reference.

---

### Story 5: Search Old Context

As a developer, I want to run:

```bash
backstory search "subscription renewal"
```

So that I can find past AI work related to that topic.

Acceptance criteria:

* Returns matching sessions.
* Shows linked commits.
* Shows summary snippets.
* Supports opening full session.

---

## 19. Edge Cases

### No AI Session Exists

If developer commits without any captured AI session:

```text
No AI session found. Commit will continue.
```

No failure.

---

### Multiple Sessions Exist

If multiple sessions are pending:

Default behavior:

* Attach latest session.

Advanced behavior:

```bash
backstory attach HEAD --session sha256:abc123
```

---

### Commit Fails

If commit fails after pre-commit:

* Keep pending session.
* Do not attach to any commit.
* Show pending state in `backstory status`.

---

### Commit Amend

If user runs:

```bash
git commit --amend
```

The post-commit hook should update the session-to-commit mapping.

---

### Rebase

If commit hashes change during rebase:

* Git notes may need manual propagation.
* Local index should detect missing commits.
* CLI should provide repair command later:

```bash
backstory repair
```

This can be P1.

---

### Secret Detected

Default:

```text
Potential secret detected and redacted.
Commit will continue.
```

Strict mode:

```text
Potential secret detected.
Commit blocked due to strict redaction policy.
```

---

## 20. Success Metrics

### MVP Success Metrics

* Developer can set up tool in under 2 minutes.
* `backstory why HEAD` works reliably after AI-assisted commits.
* Pre/post hooks do not interfere with normal Git workflow.
* Raw session storage remains compact.
* Developers can find old context faster than reading chat history manually.

### Product Success Metrics

* Number of repos initialized.
* Number of AI sessions captured.
* Percentage of commits with attached AI memory.
* Number of `backstory why` queries.
* Number of `backstory search` queries.
* Repeat usage per developer.
* GitHub stars if open source.

---

## 21. Risks

### Risk 1: Developers may not want raw conversations stored

Mitigation:

* Local-first by default.
* Clear config.
* Redaction.
* Option to store only summaries.

---

### Risk 2: AI tool integrations may be fragile

Mitigation:

* MVP should not depend on any single AI tool.
* Manual `backstory dump` should always work.
* Git diff capture should work universally.

---

### Risk 3: Pre/post hooks may annoy developers

Mitigation:

* Hooks should be fast.
* Never block by default.
* Easy disable command:

```bash
backstory hooks disable
```

---

### Risk 4: Storage may grow large

Mitigation:

* Compression enabled by default.
* Configurable retention.
* Summary-first search.
* Optional raw transcript pruning.

---

## 22. Recommended MVP Build Order

### Phase 1: Core CLI

Build:

* `backstory init`
* `.backstory/` storage
* `backstory dump`
* `backstory status`
* compressed session object

---

### Phase 2: Git Hooks

Build:

* pre-commit capture
* post-commit attach
* commit-to-session mapping
* Git notes support

---

### Phase 3: Explanation Interface

Build:

* `backstory why`
* summary generation
* markdown summary files

---

### Phase 4: Search

Build:

* `backstory search`
* file-level lookup
* commit-level lookup

---

### Phase 5: Integrations

Build:

* Claude transcript import
* Codex transcript import
* generic transcript import
* custom transcript path config

---

## 23. MVP Definition

The MVP is complete when a developer can:

```bash
backstory init
```

Then work with any AI coding tool.

Then run:

```bash
backstory dump --task "Fix subscription renewal bug"
git add .
git commit -m "Fix subscription renewal bug"
backstory why HEAD
```

And see a useful explanation of:

* What task was done
* Why code changed
* What files changed
* What decisions were made
* What risks remain
* Where the raw AI session is stored

---

## 24. Final Product Principle

The tool should feel like Git history for AI reasoning.

Git answers:

```text
What changed?
```

`backstory` answers:

```text
Why did it change?
```
