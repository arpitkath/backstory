# Task Plan: Split Next-Step Ideas

## Goal

Implement the first two P0 Backstory ideas: zero-friction capture and contradiction detection.

## Current Phase

Complete

## Phases

### Phase 1: Requirements & Discovery

- [x] Confirm requested structure: individual markdown files for each idea.
- [x] Confirm planning-with-files requirement.
- [x] Inspect existing docs and worktree state.
- **Status:** complete

### Phase 2: File Structure Plan

- [x] Define destination directory and filenames.
- [x] Decide whether to keep or replace the aggregate `docs/next-step-ideas.md`.
- [x] Record decisions in findings.
- **Status:** complete

### Phase 3: Create Idea Files

- [x] Create one markdown file for each idea.
- [x] Preserve the intent and examples from the provided notes.
- [x] Remove the aggregate file if it would violate "all ideas in their own files."
- **Status:** complete

### Phase 4: Create Priority Planning Document

- [x] Create a markdown plan using planning-with-files style.
- [x] Assign priorities to every idea.
- [x] Link to every individual idea file.
- **Status:** complete

### Phase 5: Verification & Delivery

- [x] Verify expected files exist.
- [x] Check worktree status.
- [x] Summarize the result for the user.
- **Status:** complete

### Phase 6: Backstory Rename Sweep

- [x] Replace remaining `backstory` command names and references uniformly.
- [x] Rename any path names that still use the old branding.
- [x] Update shared docs and planning notes to match the new command name.
- **Status:** complete

### Phase 7: Zero-Friction Capture and Contradiction Detection

- [x] Add transcript auto-discovery for `dump`.
- [x] Add contradiction warning helpers for current diffs.
- [x] Wire warnings into the existing `diff` command.
- **Status:** complete

### Phase 8: OKF Storage Migration

- [x] Replace JSON session persistence with OKF markdown.
- [x] Update storage paths and init/config defaults.
- [x] Verify round-trip tests for pending and attached sessions.
- **Status:** complete

## Key Questions

1. How should transcript auto-discovery behave? Answer: prefer explicit `--transcript`, then environment variables, then repo-local transcript files.
2. What counts as a contradiction warning? Answer: start with a conservative heuristic that flags prior sessions touching the same file and containing negated or reversed decisions.

## Decisions Made

| Decision | Rationale |
|----------|-----------|
| Use `docs/ideas/` for individual files | Keeps the top-level docs readable while satisfying "under docs/." |
| Remove `docs/next-step-ideas.md` | An aggregate idea file conflicts with the requested one-file-per-idea structure. |
| Create `docs/ideas-priority-plan.md` | Provides the requested planning-with-files style priority document without mixing it with the root operational plan. |
| Start with discovery-based passive capture | Gives the first low-friction path without a new background service. |
| Use a heuristic contradiction detector | Gets useful warnings in place quickly, before deeper semantic analysis exists. |
| Install pytest in a local venv | The system Python is externally managed, so the test runner lives in `/tmp/backstory-venv`. |
| Store sessions as OKF markdown | Makes the persisted source of truth human-readable and portable. |

## Errors Encountered

| Error | Attempt | Resolution |
|-------|---------|------------|

## Notes

- This is documentation restructuring only; no product code changes are needed.
