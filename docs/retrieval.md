Yes, that is the **right retrieval model**.

The tool should not only retrieve by commit or keyword. It should retrieve based on:

> "Which piece of code am I looking at, and what AI sessions/commits previously changed or explained this code?"

This makes the product much more useful.

Add this section to the PRD.

## Code-Aware Retrieval Model

### Goal

`backstory` should retrieve context based on the specific part of code the developer is asking about.

Instead of only answering:

```bash
backstory why HEAD
```

The tool should also answer:

```bash
backstory why-file app/api/webhooks/razorpay/route.ts
backstory why-line app/api/webhooks/razorpay/route.ts:120
backstory why-code app/api/webhooks/razorpay/route.ts:100-160
```

The goal is to explain the history and reasoning behind a specific file, function, class, or line range.

---

## Retrieval Problem

Git already knows when code changed, but it does not preserve why it changed.

For a given code section, the tool should find:

1. Which commits modified this code.
2. Which AI sessions were linked to those commits.
3. What reasoning, prompts, constraints, and decisions were captured.
4. Whether the same code was changed multiple times.
5. What the latest relevant reasoning is.
6. What older reasoning may still matter.

---

## Core Retrieval Flow

When the user asks:

```bash
backstory why-code src/billing/subscription.ts:80-140
```

The tool should:

1. Resolve the file path and line range.
2. Use Git history to find commits that touched that range.
3. Include previous commits that touched nearby or related code.
4. Find AI sessions attached to those commits.
5. Load summaries first.
6. Fall back to raw compressed sessions if needed.
7. Produce a timeline of why that code evolved.

---

## Git-Based Code Retrieval

The MVP should use Git as the source of truth for code history.

Useful Git strategies:

```bash
git log --follow -- <file>
```

Find commits that changed a file.

```bash
git blame -L <start>,<end> <file>
```

Find commits responsible for current lines.

```bash
git log -L :<function_name>:<file>
```

Track history of a function where supported.

```bash
git log -p -- <file>
```

Inspect historical patches for the file.

The tool should combine these with the local AI memory index.

---

## Retrieval Types

### 1. Commit-Based Retrieval

Command:

```bash
backstory why HEAD
```

Answers:

```text
Why did this commit happen?
```

Used when the developer already knows the commit.

---

### 2. File-Based Retrieval

Command:

```bash
backstory file src/auth/session.ts
```

Answers:

```text
What important AI-assisted decisions affected this file?
```

Output should include:

* Recent AI-assisted commits touching the file
* Major decisions
* Risks
* Follow-ups
* Linked sessions

---

### 3. Line-Based Retrieval

Command:

```bash
backstory line src/auth/session.ts:120
```

Answers:

```text
Why does this specific line exist?
```

The tool should use `git blame` to find the commit that last touched the line, then retrieve the linked AI memory.

---

### 4. Range-Based Retrieval

Command:

```bash
backstory range src/auth/session.ts:100-160
```

Answers:

```text
Why does this block of code exist?
```

The tool should retrieve commits that touched any line in the range.

---

### 5. Function-Based Retrieval

Command:

```bash
backstory function src/auth/session.ts refreshToken`
```

Answers:

```text
Why was this function implemented this way?
```

MVP can approximate this using line ranges.

Later versions can parse ASTs to identify function boundaries automatically.

---

### 6. Current Diff Retrieval

Command:

```bash
backstory diff
```

Answers:

```text
What previous AI context is relevant to my current uncommitted changes?
```

This is very important for future agent workflows.

The tool should:

* Inspect current changed files
* Find previous commits touching those files
* Retrieve attached AI memory
* Surface relevant warnings, decisions, and constraints

Example output:

```text
Relevant prior context for current diff:

1. app/api/webhooks/razorpay/route.ts
   Previous decision:
   payment.failed should mark subscription as pending, not cancelled.

2. lib/subscription.ts
   Previous risk:
   next_due_on must be updated only after verified webhook events.

3. db/migrations/add_next_due_on.sql
   Follow-up:
   Existing paid users may require backfill.
```

---

## Retrieval Ranking

When multiple commits are found, rank them by relevance.

Suggested ranking factors:

1. Exact line blame commit
2. Commits touching the selected range
3. Commits touching the same function
4. Commits touching the same file
5. Recent commits
6. Commits with attached AI sessions
7. Commits whose summaries mention similar terms
8. Commits from the same branch
9. Commits touching related files in the same session

The most relevant result is usually:

```text
The commit that last changed this exact line/range and has an attached AI memory session.
```

But older commits should still be shown if they explain the original design.

---

## Example Output

Command:

```bash
backstory range app/api/webhooks/razorpay/route.ts:90-150
```

Output:

```text
Code context:
app/api/webhooks/razorpay/route.ts:90-150

This code was affected by 4 commits with AI memory.

Most relevant commit:
8f21c9a - Fix subscription renewal handling

Why this code exists:
This block handles Razorpay subscription lifecycle events. It was added because successful recurring charges, failed payments, halted subscriptions, and cancellations needed separate handling.

Key decisions:
- subscription.charged updates next_due_on.
- payment.failed should not immediately cancel the subscription.
- subscription.cancelled is the event that revokes Pro access.
- Webhook handling should be idempotent.

Previous related commits:
1. 4ad93c1 - Add Razorpay webhook verification
   Reason:
   Verify webhook signatures before updating subscription state.

2. c78a11b - Add next_due_on column
   Reason:
   Track the next billing date after successful recurring payments.

3. 91fa002 - Handle failed subscription payments
   Reason:
   Keep user in pending state before revoking access.

Risks mentioned:
- Duplicate Razorpay events may cause repeated updates.
- Existing users may need a next_due_on backfill.
- Failed payments and cancellations should not be treated the same.

Raw sessions:
- sha256:abc123
- sha256:def456
- sha256:ghi789
```

---

## Required Index Changes

The local index should not only store commit-to-session mappings.

It should also store file-level and code-level metadata.

Suggested tables:

```text
sessions
- session_id
- created_at
- agent
- model
- branch
- summary_path
- object_path

commits
- commit_hash
- commit_message
- authored_at
- branch

commit_sessions
- commit_hash
- session_id

file_changes
- commit_hash
- session_id
- file_path
- change_type
- lines_added
- lines_deleted
- hunks_json

session_files
- session_id
- file_path
- role
  values: read, changed, created, deleted

session_decisions
- session_id
- file_path
- decision
- risk
- followup
```

For MVP, `file_changes` can store patch hunks from Git diff.

Later, this can be improved with AST-aware function mapping.

---

## MVP Implementation Approach

For MVP, avoid complex AST parsing.

Use Git primitives first:

```text
File query:
git log --follow -- <file>

Line query:
git blame -L <line>,<line> <file>

Range query:
git blame -L <start>,<end> <file>

Previous history:
git log -p -- <file>
```

Then map the resulting commits to `backstory` sessions.

This will already provide high value.

---

## Future Enhancement: Function-Aware Retrieval

Later, the tool can parse code structure.

For example:

```bash
backstory function src/auth/session.ts refreshToken
```

The tool should:

1. Parse file AST.
2. Find function start and end lines.
3. Run range-based retrieval on those lines.
4. Retrieve previous commits and AI sessions.
5. Summarize why the function evolved.

This can support:

* JavaScript/TypeScript
* Python
* Go
* Java
* Rust

But this should not be required for MVP.

---

## Product Principle

Retrieval should start from code, not chat.

The developer should be able to point at a file, function, or line and ask:

```text
Why is this code like this?
```

`backstory` should answer using Git history plus AI session memory.

This makes the product much stronger. The killer command is probably:

```bash
backstory code path/to/file.ts:120-180
```

because that directly solves the daily developer pain: **"Why is this block written this way?"**
