# Benchmark Recovery Plan

## Goal
Run the real spreadsheet benchmark tasks through the current system, identify the remaining failing tasks, and iteratively fix the underlying generic capability gaps until the benchmark passes without benchmark-shaped shortcuts.

## Phases
- [in_progress] Phase 1: Confirm runnable benchmark entrypoints and capture current pass/fail state.
- [pending] Phase 2: Inspect failing task logs and isolate root causes.
- [pending] Phase 3: Implement generic fixes in routing, helpers, execution, QA, or validation.
- [pending] Phase 4: Re-run affected tasks and expand to the remaining benchmark set.
- [pending] Phase 5: Summarize remaining failures, risks, and next actions.
- [complete] Phase 6: Clean dataset layout, remove obsolete dataset docs, and unify backend CLI benchmark entrypoints.
- [complete] Phase 7: Move original Task01-Task27 development suite into `dataset/DevelopmentBenchmark`.

## Constraints
- Do not add benchmark-specific routing, canned answers, or task-id shortcuts.
- Use the real benchmark runner, not synthetic-only tests.
- Preserve user changes already present in the working tree.
- Keep the three benchmark purposes separate: development end-to-end, diagnose-stage, and final system evaluation.

## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
