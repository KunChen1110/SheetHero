# Findings

## Runner Discovery
- `test/core/run_test.py` is the direct single-task benchmark entrypoint.
- `test/core/test_user_case.py` can run multiple tasks by list or range and shells out to `run_test.py`.
- Dataset roots include `dataset/SystemEvaluationBenchmark/clean_cases`, `dataset/SystemEvaluationBenchmark/median_clean_cases`, and `dataset/SystemEvaluationBenchmark/large_clean_cases`.

## Current Working Assumption
- The fastest path is to run the real benchmark tasks via `run_test.py` first, then widen with `test_user_case.py` once single-task failures are addressed.

## Dataset Cleanup
- `dataset/DevelopmentBenchmark/dataset.json` plus `Task01`-`Task27` is the original development end-to-end suite.
- `dataset/DiagnoseBenchmark/SpreadsheetDiagnosisData` is the diagnose-stage benchmark.
- `dataset/SystemEvaluationBenchmark` is the final system end-to-end evaluation suite, renamed from the previous spreadsheet benchmark name.
- `dataset` top level now contains only the three benchmark suite directories plus `README.md`.
- New backend CLI commands:
  - `!benchmark dev --index N`
  - `!benchmark diagnose small|median|all [--limit N]`
  - `!benchmark evaluation clean|median|large --index N`
  - `!judge dev --index N`
  - `!judge evaluation clean|median|large --index N`
