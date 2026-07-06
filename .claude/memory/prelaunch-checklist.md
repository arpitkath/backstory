---
name: prelaunch-checklist
description: Items needed before Backstory repo is launch-ready for virality
metadata:
  type: feedback
---

## Priority order (from user review on 2026-07-06)

1. **Add demo GIF/video at top of README** — show `git show HEAD` vs `backstory why HEAD` in a 10-second terminal recording
2. **Fix GitHub metadata** — description ("Local-first memory for AI-assisted coding"), topics (ai-coding, ai-agents, developer-tools, git, cli, python, claude-code, cursor, codex, local-first, open-source), website
3. **Publish installable release** — PyPI package needs to be published; GitHub release needs to exist; pipx install backstory should work
4. **Add real example/demo folder** — e.g. examples/ai-subscription-bug/ with before/after code and .backstory/ showing a realistic `backstory why HEAD` output
5. **Sharper README opening** — lead with "AI writes the code. Git saves the diff. Backstory saves the reasoning." then the pain questions, then the demo
6. **Integration guide** — ✅ Done (docs/integration.md)
7. **First GitHub release** — tag + release notes
8. **Launch narrative** — "AI coding has a memory problem" angle for HN/X/LinkedIn

## Other gaps
- LICENSE file (MIT or Apache-2.0)
- CONTRIBUTING.md
- README badges (PyPI, Tests, License, Python version, "local-first / no cloud")
- Reduce ambiguity about which commands are implemented vs intended
- Pick one hero integration ("Works with Claude Code today") rather than listing all equally

**Why:** The idea is strong but the repo page leaks attention — 0 stars, no description/topics, no release. Cold visitors can't see the magic instantly.
