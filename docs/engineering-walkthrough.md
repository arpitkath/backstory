# Backstory Engineering Walkthrough

Backstory is a local-first memory layer for AI-assisted coding. It captures
session context from tool-native hooks or exporters, stores the durable record
as OKF markdown, attaches that memory to commits, and later retrieves the
reasoning behind code changes.

- [Architecture Overview](#architecture-overview)
- [Data Flow (End-to-End)](#data-flow-end-to-end)
- [High-Level Design](#high-level-design)
- [Low-Level Design](#low-level-design)
- [Contradiction Detection](#contradiction-detection)
- [Indexing and Search](#indexing-and-search)
- [Current Limitations](#current-limitations)

---

## Architecture Overview

```
┌─────────────┐     ┌──────────────┐     ┌────────────────┐     ┌──────────────┐
│  AI Tool     │────▶│  backstory   │────▶│  OKF Markdown  │────▶│  Git Commit  │
│  (Claude,    │     │  dump        │     │  .backstory/   │     │  Link        │
│  Codex, etc) │     │              │     │  knowledge/    │     │              │
└─────────────┘     └──────────────┘     └────────────────┘     └──────┬───────┘
                                                                        │
                                              ┌─────────────────────────┤
                                              │                         │
                                              ▼                         ▼
                                  ┌───────────────────┐     ┌───────────────────┐
                                  │  Retrieval        │     │  Contradiction    │
                                  │  (why / file /    │     │  Detection        │
                                  │   line / range)   │     │  (backstory diff) │
                                  └───────────────────┘     └───────────────────┘
```

The system has four layers:

1. **Capture** — Ingests AI sessions via `backstory dump`. Reads a transcript
   (or accepts structured decisions directly), normalises it, optionally
   summarises it through the original AI agent, and writes an OKF markdown
   file.
2. **Storage** — Persists the extracted reasoning (decisions, risks,
   follow-ups) as OKF markdown files under `.backstory/knowledge/sessions/`.
   Git state, diffs, and file-change metadata are stored alongside — no raw
   conversation content.
3. **Link** — Attaches a saved session to a Git commit via `backstory attach
   HEAD`. Writes a stable session file, clears the pending session, and
   creates a Git note pointing back to the session for cross-reference.
4. **Retrieve** — Answers questions like "Why did this commit happen?" or "Why
   does this line exist?" by correlating Git history (log, blame) with stored
   sessions. Also warns when a new diff appears to contradict earlier
   decisions.

---

## Data Flow (End-to-End)

### 1. Init — `backstory init`

Creates the storage layout and writes a default config.

```
.backstory/
  config.json
  knowledge/
    index.md
    sessions/
      index.md
      latest.md         (pending session file)
      sha256-<hash>.md  (stable attached sessions)
  redactions/
    tombstones.log
```

`initialize_repo()` in `init.py` calls `ensure_storage_layout()` to create the
directory tree, writes `config.json` with default capture settings, and
optionally installs pre-commit and post-commit Git hooks.

### 2. Capture — `backstory dump`

The capture pipeline has four stages:

**Stage 1 — Transcript discovery.** If no explicit `--transcript` path is
given, the CLI walks environment variables
(`BACKSTORY_TRANSCRIPT`, `CLAUDE_TRANSCRIPT_PATH`, etc.) and known repo-local
paths to auto-discover a transcript. Any input transcript is an optional
artifact from the AI tool — backstory does not store it.

**Stage 2 — Import & normalise.** The raw transcript (AI tool output, usually
JSON) is read and normalised into a standard `[{role, content}, ...]` message
list. The normaliser (`transcript.py:normalize_messages`) handles Claude Code,
Codex, and generic formats.

**Stage 3 — Summarisation (optional).** The normalised messages are sent to
the original AI agent's CLI (e.g. `claude --print`), which is prompted to
return a structured summary as JSON containing task, decisions, risks,
follow-ups, and files changed. This JSON is an ephemeral intermediate format —
it is parsed into `ExtractedDecisions` and then discarded. Only the extracted
facts are persisted in OKF markdown.

**Stage 4 — Session assembly & save.** `capture_session()` in `dump.py` reads
current Git state (branch, HEAD hash, staged/unstaged diffs, changed files),
merges it with the extracted decisions, computes a content-addressed session
ID (`sha256:<truncated-hash>`), and writes the result as `latest.md` in OKF
markdown.

### 3. Link — `backstory attach HEAD`

`attach_pending_to_commit()` loads the pending session from `latest.md`,
augments it with the target commit's hash and message, writes a stable copy
to `sha256-<hash>.md`, attaches a Git note with session metadata, and clears
the pending file. The commit hash is stored in the session's frontmatter so
correlation works in either direction.

### 4. Retrieve — `backstory why HEAD`

`why_module.resolve_commit_spec()` resolves the user-supplied commit reference (e.g. HEAD, abc123, main~3) to a `(hash, message)` tuple via `git log -1 --format=%H%n%s`. Then `why_module.load_session_for_commit()` uses a two-strategy approach:

1. **Git notes** — reads the note attached to the commit via `git notes show <hash>` and looks up the session ID stored inside.
2. **Fallback scan** — lists every `.md` file in `.backstory/knowledge/sessions/` (skipping `latest.md`), parses the frontmatter, and returns the first session whose `commit_hash` matches.

`why_module.format_why_output()` then renders the session as a human-readable block showing Commit, Message, Branch, AI Agent, Session ID, Task, Key decisions, Files changed, Risks, Follow-ups, and the raw session path. The `--json` flag dumps the raw session dict instead.

### 5. Cross-reference — `backstory diff`

`backstory diff` combines retrieval and contradiction detection:
1. Lists files changed in the working tree.
2. For each changed file, shows the most recent commit that touched it.
3. Runs contradiction detection against all attached sessions.

---

## High-Level Design

### Module Map

| Module          | Responsibility |
|-----------------|----------------|
| `cli.py`        | Argument parsing, command dispatch |
| `init.py`       | Repository initialisation, config writing, hook installation |
| `dump.py`       | Session capture, transcript discovery, Git state capture |
| `attach.py`     | Commit linkage, Git note writing, pending session management |
| `okf.py`        | OKF markdown parsing and rendering |
| `storage.py`    | Path definitions, storage layout creation |
| `retrieval.py`  | Git-based code context retrieval (log, blame, diff) |
| `contradiction.py` | Knowledge-driven contradiction detection |
| `why.py`        | Commit-to-session resolution, human-readable why output formatting |
| `search.py`     | Text-based full-session search with file/branch filters and relevance scoring |
| `redact.py`     | Secret pattern scanning, session redaction, tombstone management |
| `git_notes.py`  | Git notes read/write/remove via backstory-specific ref (refs/notes/backstory) |
| `transcript.py` | Transcript import, normalisation, agent-name detection |
| `summarize.py`  | Agent-driven transcript summarisation |
| `config.py`     | Configuration defaults and loading |
| `hooks.py`      | Git hook installation and management |
| `git.py`        | Basic Git repository detection |

### Key Design Decisions

**1. OKF markdown as the sole persistence format.**
Sessions are stored as YAML-frontmatter markdown, not JSON. This keeps them
human-readable, Git-friendly (meaningful diffs), and directly editable by both
people and AI tools. Only the extracted decisions, risks, and metadata are
persisted, never the raw conversation.

**2. Git-native retrieval.**
Retrieval leans on `git log --follow` and `git blame --porcelain` rather than
a dedicated database. This avoids synchronisation problems — Git history is
the source of truth. The trade-off is that cross-session searches (e.g.
"find all sessions that mention auth") are O(n) scans of session files, which
is fine at repository scale but would not scale to thousands of sessions
without an index.

**3. Agent self-summarisation.**
When a transcript is available, backstory asks the original AI agent
(via its CLI) to summarise its own work. This preserves the agent's internal
understanding of what decisions were made, rather than relying on a fixed
extraction heuristic. The raw conversation is discarded after summarisation.

**4. No Git hooks for capture.**
Contradiction detection and retrieval are read-only operations that scan
already-stored knowledge. Capture comes from tool-native callbacks, not Git
hooks. The optional hooks (`pre-commit`, `post-commit`) exist to automate
`dump` and `attach` for tools that don't support native callbacks, but they
are not the primary path.

**5. Content-addressed session IDs.**
Each session gets a `sha256:<truncated>` ID computed from the timestamp,
task description, decisions, and Git HEAD. This makes session IDs
deterministic and verifiable — the same inputs produce the same ID.

---

## Low-Level Design

### Core Data Structures

**`SessionKnowledge`** (`okf.py`) — The central domain object.

```python
@dataclass
class SessionKnowledge:
    session_id: str        # sha256:<truncated>
    created_at: str        # ISO 8601
    task_title: str
    user_prompt: str
    agent_name: str
    agent_model: str | None
    agent_source: str       # "hook" or "manual"
    branch: str
    head: str               # Git HEAD hash at capture time
    commit_hash: str | None # set during attach
    commit_message: str | None
    files_changed: list[str]
    staged_diff: str
    unstaged_diff: str
    why: str
    decisions: list[str]
    risks: list[str]
    followups: list[str]
    alternatives: list[str]
```

**`BackstoryPaths`** (`storage.py`) — Immutable path bundle.

```python
@dataclass(frozen=True)
class BackstoryPaths:
    root: Path            # .backstory/
    knowledge: Path       # .backstory/knowledge/
    sessions: Path        # .backstory/knowledge/sessions/
    pending: Path         # .backstory/knowledge/sessions/latest.md
    redactions: Path      # .backstory/redactions/
    knowledge_index: Path # .backstory/knowledge/index.md
    sessions_index: Path  # .backstory/knowledge/sessions/index.md
```

**`CommitInfo`** (`retrieval.py`) — Git commit metadata for retrieval.

```python
@dataclass(frozen=True)
class CommitInfo:
    hash: str
    message: str
    authored_at: str  # ISO 8601
    author: str
```

**`ExtractedDecisions`** (`transcript.py`) — Structured summary from agent.

```python
@dataclass
class ExtractedDecisions:
    agent_name: str
    model: str | None
    task: str
    decisions: list[str]
    risks: list[str]
    followups: list[str]
    files_changed: list[str]
    alternatives: list[str]
```

### OKF Markdown Format

Each session file is a YAML-frontmatter markdown document:

```markdown
---
type: Backstory Session
title: Fix subscription renewal handling
description: The webhook handler was not updating the next billing date...
resource: git:8f21c9a
tags: [backstory, ai-session]
timestamp: 2026-07-06T12:00:00+00:00
session_id: sha256:a1b2c3d4...
agent: claude-code
model: claude-sonnet-5
source: manual
branch: main
head: 8f21c9a...
commit_hash: 8f21c9a...
commit_message: Fix subscription renewal handling
files_changed:
  - app/api/webhooks/razorpay/route.ts
  - lib/subscription.ts
---

# Task

Fix subscription renewal handling

# Decisions

- subscription.charged updates next_due_on
- payment.failed marks subscription as pending, not cancelled
- webhook handling must be idempotent

# Risks

- Idempotency depends on storing Razorpay event IDs

# Diff

## Staged

```diff
...
```
```

The frontmatter stores all structured metadata. The body sections are
variable-length human-readable lists. This structure is parsed by
`parse_session_markdown()` in `okf.py`, which splits on `---` fences and
interprets `# Section Name` headings.

### Git Interaction Layer

`retrieval.py` wraps git commands:

- **`commits_for_file(path)`** — `git log --follow --format=... <path>`
  Retrieves all commits that touched a file, most recent first.

- **`commit_for_line(path, line)`** — `git blame -L<line>,<line> --porcelain`
  Finds the last commit that modified a specific line.

- **`commits_for_range(path, start, end)`** — `git blame -L<start>,<end> --porcelain`
  Gets distinct commits touching a range of lines.

- **`files_in_diff()`** — `git diff --name-only HEAD`
  Lists files changed in the working tree.

These are wrappers around `subprocess.run(["git", ...])`. The porcelain format
is used for blame so output is machine-parseable.

### Session Lifecycle

```
[time]  backstory dump          backstory attach HEAD     backstory why HEAD
        ┌──────────────┐        ┌──────────────┐          ┌──────────────┐
        │ read         │        │ load         │          │ find session │
        │ transcript   │ ──────▶│ pending      │ ────────▶│ by commit    │
        │ normalise    │        │ set commit   │          │ render       │
        │ summarise    │        │ write stable │          │ output       │
        │ save pending │        │ git notes    │          │              │
        │ latest.md    │        │ clear pending│          │              │
        └──────────────┘        └──────────────┘          └──────────────┘
```

- **Pending**: `latest.md` exists after `dump`, before `attach`.
- **Stable**: `sha256-<id>.md` exists after `attach`. The session is now
  linked to a commit and will be included in contradiction checks.
- **No pending**: After attach, `latest.md` is removed. The next `dump`
  creates a fresh one.

### Git Notes

When attaching, backstory writes a lightweight Git note to the target commit:

```json
{
  "ai_session": "sha256:a1b2c3...",
  "agent": "claude-code",
  "created_at": "2026-07-06T12:00:00+00:00"
}
```

This provides a reverse lookup path: given a commit, find its session.
Git notes are best-effort (silently ignored if notes are not configured).

### CLI Command Wiring

Commands and their handler mapping in `_dispatch()`:

| Command    | Handler         | Status |
|------------|-----------------|--------|
| `init`     | `_handle_init`  | ✅ |
| `dump`     | `_handle_dump`  | ✅ |
| `attach`   | `_handle_attach`| ✅ |
| `file`     | `_handle_file`  | ✅ |
| `line`     | `_handle_line`  | ✅ |
| `range`    | `_handle_range` | ✅ |
| `code`     | `_handle_range` | ✅ (alias for range) |
| `diff`     | `_handle_diff`  | ✅ |
| `why`      | `_handle_why`   | ✅ |
| `show`     | —               | 🔲 not yet wired |
| `search`   | `_handle_search`| ✅ |
| `context`  | —               | 🔲 not yet wired |
| `status`   | `_handle_status`| ✅ |
| `redact`   | `_handle_redact`| ✅ |
| `repair`   | —               | 🔲 not yet wired |
| `hooks`    | `_handle_hooks` | ✅ enable/disable/status |

---

## Contradiction Detection

Contradiction detection lives in `contradiction.py`. It is a file-overlap plus
pattern-matching algorithm — intentionally conservative rather than semantic.

### Algorithm

```
for each attached session:
    if session shares any changed file with the current diff:
        for each decision in that session:
            if decision looks like a reversal pattern:
                warn
                break (one warning per session)
```

**Step 1: Load all attached sessions.** `_load_attached_sessions()` reads
every `.md` file in `.backstory/knowledge/sessions/` (excluding `latest.md`),
parses the OKF markdown, and converts each to a session dict.

**Step 2: File-overlap check.** The current diff's changed files are compared
against each session's `files_changed` list. Only sessions with at least one
file in common are considered — if a session touched completely different
files, no contradiction is possible.

**Step 3: Reversal-pattern detection.** `_looks_likes_reversal()` runs a regex
against each decision text. The `NEGATION_PATTERNS` tuple contains reversal
indicators:

```python
NEGATION_PATTERNS = (
    r"\bnot\b",
    r"\bnever\b",
    r"\binstead\b",
    r"\bavoid\b",
    r"\bprevent\b",
    r"\bno longer\b",
    r"\brather than\b",
)
```

If a decision contains any of these patterns, it triggers a warning. For
example, the decision *"payment.failed marks subscription as pending, not
cancelled"* matches `\bnot\b` and would warn if a new change touches the
payment file.

**Step 4: Warning assembly.** Each warning includes the commit hash, the
overlapping file(s), and the decision text.

### Design Rationale

- **Conservative by design.** The detection uses exact file paths and simple
  text patterns rather than semantic understanding. This produces fewer
  false positives at the cost of missing some subtle reversals.
- **File-first.** Only sessions touching overlapping files are checked. This
  limits noise and keeps the O(n) scan bounded by the size of the diff.
- **One warning per session.** Once a reversal pattern is found in a session,
  that session is done. This avoids spamming the user with duplicate warnings
  from the same session.

### Current Limitations

- **Pattern-only.** A reversal like *"change subscription.charged to call the
  old API again"* (without any negation keyword) would not be detected.
- **No semantic analysis.** The detection cannot distinguish *"not changed"*
  from *"not cancelled"* — both contain `\bnot\b`.
- **File-name matching.** Two changes to the same conceptual code in
  differently-named files would not trigger a warning.
- **No severity ranking.** All warnings are presented equally, even though
  some reversals are more consequential than others.

---

## Indexing and Search

### Current Indexing Strategy

Backstory does **not** maintain a separate content index for search. Instead,
it relies on two mechanisms:

**1. Filesystem-based session storage.**
All sessions are stored as individual `.md` files in
`.backstory/knowledge/sessions/`. The directory structure is the primary
"index":

- `latest.md` — the single pending session (unattached).
- `sha256-<id>.md` — stable attached sessions, one per commit.

Listing sessions is `ls .backstory/knowledge/sessions/*.md`. Loading a
session is `read_file → parse_frontmatter → parse_sections`.

**2. Index markdown files.**
Two `index.md` files serve as optional human-readable registries:

- `.backstory/knowledge/index.md` — knowledge directory index.
- `.backstory/knowledge/sessions/index.md` — sessions directory index.

These are created during `init` with a header line and left for future
population. They are not currently updated automatically.

**3. Git-based code retrieval.**
For retrieval queries (`backstory file`, `line`, `range`), Backstory leans on
Git rather than a database:

```
commits_for_file(path)      → git log --follow --format=... <path>
commit_for_line(path, n)    → git blame -L<n>,<n> --porcelain <path>
commits_for_range(p, s, e)  → git blame -L<s>,<e> --porcelain <path>
```

These return `CommitInfo` objects (hash, message, author, date). The caller
correlates commit hashes with session files by scanning the session directory
for files whose frontmatter contains a matching `commit_hash`.

**4. Session-to-commit correlation.**
Because sessions store the commit hash in frontmatter, and Git notes store
the session ID, cross-referencing works in both directions:

- **Commit → Session**: `git log` returns a hash → scan session files for
  frontmatter with `commit_hash: <hash>` → read the session.
- **Session → Commit**: read the session's `commit_hash` field → `git show`.

This is an O(n) scan of session files. With hundreds of sessions, this
remains fast.

### How Retrieval Works for Each Command

**`why HEAD`**:
Resolves the commit spec (default HEAD) via `git log -1 --format=%H%n%s`,
finds the attached session via Git notes or frontmatter scan, and renders
the session's decisions, risks, and why.

**`file <path>`**:
1. `git log --follow --format=... <path>` → list of commits.
2. For each commit hash, scan session files for matching `commit_hash`.
3. Render `CommitInfo` and linked session IDs.

**`line <path>:<line>`**:
1. `git blame -L<line>,<line> --porcelain <path>` → one commit hash.
2. Look up the commit in session files.
3. Render the commit and its linked session.

**`range <path>:<start>-<end>`**:
1. `git blame -L<start>,<end> --porcelain <path>` → unique commit hashes.
2. For each hash, look up in session files.
3. Return sorted by date descending.

**`diff`**:
1. `git diff --name-only HEAD` → changed files.
2. For each file, `commits_for_file(path)` → most recent commit.
3. Run `detect_potential_contradictions()` for contradiction warnings.

---

## Current Limitations

- Retrieval is heuristic and Git-backed — cross-session search is an O(n)
  file scan.
- Contradiction detection is textual-pattern-based, not semantic.
- Several CLI commands (`show`, `context`, `repair`) are declared but not
  yet wired to handlers.
- Git notes are best-effort — some Git configurations or hosting platforms
  do not support notes.
