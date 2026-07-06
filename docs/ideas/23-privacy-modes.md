# Privacy Modes

## Priority

P0

## Idea

Add explicit privacy modes for capture and storage.

## Modes

```text
full     -> store full transcript plus summary
safe     -> store redacted transcript plus summary
summary  -> store only generated summary
off      -> do not capture
```

## Command

```bash
backstory mode summary
```

## Rationale

Many developers will be uncomfortable storing raw AI conversations. Control increases adoption.
