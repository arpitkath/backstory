# Backstory Idea Priority Plan

This document uses the planning-with-files style: a goal, phases, item priorities, decisions, and progress-oriented structure. Each idea lives in its own markdown file under `docs/ideas/`.

## Goal

Prioritize Backstory's next product ideas so implementation can focus first on code-aware memory, passive capture, and trust-building workflows.

## Current Phase

Planning

## Priority Levels

- **P0:** Highest-leverage MVP or trust requirement.
- **P1:** Strong differentiator after the P0 base exists.
- **P2:** Valuable later expansion.

## P0 Items

| Item | File | Why It Is P0 |
|------|------|--------------|
| Zero-friction capture | [01-zero-friction-capture.md](ideas/01-zero-friction-capture.md) | Removes the main adoption failure mode: forgetting to capture. |
| Contradiction detection | [02-contradiction-detection.md](ideas/02-contradiction-detection.md) | Turns memory into active regression prevention. |
| PR and CI surfacing | [03-pr-ci-surfacing.md](ideas/03-pr-ci-surfacing.md) | Makes context visible during review and helps distribution. |
| Code memory cards | [04-code-memory-cards.md](ideas/04-code-memory-cards.md) | Creates the core data layer for code-aware memory. |
| `backstory code` | [05-backstory-code.md](ideas/05-backstory-code.md) | Provides the killer code-aware retrieval command. |
| Evolution timeline | [06-evolution-timeline.md](ideas/06-evolution-timeline.md) | Prevents stale reasoning by explaining how code changed over time. |
| Superseded and conflicting memory | [07-superseded-conflicting-memory.md](ideas/07-superseded-conflicting-memory.md) | Prevents old memory from misleading future agents. |
| `backstory before-edit` | [08-before-edit-context.md](ideas/08-before-edit-context.md) | Gives future agents and developers essential context before changes. |
| Decision extraction model | [12-decision-extraction-model.md](ideas/12-decision-extraction-model.md) | Makes decisions searchable, status-aware, and evidence-backed. |
| Adapter architecture | [16-adapter-architecture.md](ideas/16-adapter-architecture.md) | Avoids hard-coding one transcript format and supports passive capture. |
| Simple integration contract | [18-simple-integration-contract.md](ideas/18-simple-integration-contract.md) | Keeps the first integration surface scriptable and stable. |
| Rebase and amend repair | [20-rebase-amend-repair.md](ideas/20-rebase-amend-repair.md) | Broken Git links would quickly destroy trust. |
| Privacy modes | [23-privacy-modes.md](ideas/23-privacy-modes.md) | Gives users explicit control over sensitive local memory. |
| Init redaction posture | [24-init-redaction-posture.md](ideas/24-init-redaction-posture.md) | Forces an explicit privacy choice during setup. |

## P1 Items

| Item | File | Why It Is P1 |
|------|------|--------------|
| Agent context packet | [09-agent-context-packet.md](ideas/09-agent-context-packet.md) | Makes memory easy to hand to other AI agents. |
| Trace as events | [10-trace-as-events.md](ideas/10-trace-as-events.md) | Improves evidence quality beyond summary text. |
| Why confidence | [11-why-confidence.md](ideas/11-why-confidence.md) | Makes answers more trustworthy by exposing certainty. |
| `backstory explain-diff` | [13-explain-diff.md](ideas/13-explain-diff.md) | Helps before commit, not only after commit. |
| Review mode | [14-review-mode.md](ideas/14-review-mode.md) | Gives reviewers a focused view of AI-assisted commits. |
| PR markdown export | [15-pr-markdown-export.md](ideas/15-pr-markdown-export.md) | Useful team workflow without requiring hosted infrastructure. |
| Memory hygiene commands | [19-memory-hygiene-commands.md](ideas/19-memory-hygiene-commands.md) | Keeps local memory clean and repairable. |
| Session quality scoring | [21-session-quality-scoring.md](ideas/21-session-quality-scoring.md) | Surfaces thin or missing memory before users rely on it. |

## P2 Items

| Item | File | Why It Is P2 |
|------|------|--------------|
| Cross-agent session stitching | [17-cross-agent-session-stitching.md](ideas/17-cross-agent-session-stitching.md) | Valuable once multiple adapters and traces exist. |
| Retention and pruning | [22-retention-pruning.md](ideas/22-retention-pruning.md) | Important for long-term storage hygiene after storage policy settles. |
| Natural language search | [25-natural-language-search.md](ideas/25-natural-language-search.md) | Strong retrieval upgrade after structured memory exists. |
| Per-line why | [26-per-line-why.md](ideas/26-per-line-why.md) | Useful refinement after code-range retrieval works. |
| Local web viewer | [27-local-web-viewer.md](ideas/27-local-web-viewer.md) | Better browsing experience after the memory graph is useful. |

## Recommended Phases

### Phase 1: Trustworthy Capture Foundation

- Zero-friction capture
- Adapter architecture
- Simple integration contract
- Privacy modes
- Init redaction posture
- Rebase and amend repair

### Phase 2: Code-Aware Memory Core

- Decision extraction model
- Code memory cards
- `backstory code`
- Evolution timeline
- Superseded and conflicting memory
- `backstory before-edit`

### Phase 3: Team Workflow Surface

- PR and CI surfacing
- PR markdown export
- Review mode
- `backstory explain-diff`
- Why confidence

### Phase 4: Memory Quality And Operations

- Memory hygiene commands
- Session quality scoring
- Trace as events
- Agent context packet

### Phase 5: Later Retrieval And Browsing

- Cross-agent session stitching
- Retention and pruning
- Natural language search
- Per-line why
- Local web viewer

## Decisions Made

| Decision | Rationale |
|----------|-----------|
| Prioritize passive capture first | The largest adoption risk is developers forgetting to use the tool. |
| Prioritize code-aware memory before search/viewer expansion | Search and viewing are more valuable after memory is structured around code. |
| Treat privacy and repair as P0 | Trust failures can invalidate the product even if retrieval works. |

## Success Criteria

- Every idea has one dedicated markdown file.
- The priority plan links to every idea file.
- P0/P1/P2 priorities are explicit.
- The first recommended implementation phases emphasize adoption, trust, and code-aware retrieval.
