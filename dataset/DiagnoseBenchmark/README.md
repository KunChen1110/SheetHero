# Diagnose Benchmark Dataset

## Why this dataset is kept separate
This dataset is suitable for **diagnose / QA evaluation**, not for the main end-to-end task pipeline used by `Task01`-`Task27`.

Reason:
- each case provides raw CSV tables
- each case includes `issue.json` as diagnosis ground truth
- it does **not** define a natural-language task prompt plus final output spreadsheet in the same format as the current main dataset

So this should be treated as a **diagnose benchmark**, not merged into the main task dataset manifest.

## What it is useful for
This dataset is good for checking whether the backend can:
1. decide when `diagnose` should trigger
2. identify the correct issue category
3. generate concrete QA questions
4. show a correct preview with the right table / column / row context

## Folder structure
- `dataset_small/`
  - 10 cases
  - 2 small tables per case
  - each table contains 2-3 issues
  - better for quick QA/diagnose regression
- `dataset_median/`
  - 10 cases
  - 3 medium tables per case
  - one table contains 1-3 issues
  - better for robustness / scaling checks

Each case contains:
- `table*.csv`
- `issue.json`

## Recommended usage
### Phase 1: Quick regression
Start with `dataset_small`.

For each case:
- load the CSV files
- run only the diagnose / QA pipeline
- compare router output against `issue.json`

Check:
- did diagnose trigger?
- was the issue type close to the ground truth?
- did the QA question point to the correct file / row / column?
- was the preview understandable?

### Phase 2: Mapping evaluation
Because your router issue labels are not identical to the benchmark labels, use a loose mapping.

Suggested mapping:
- benchmark `missing` -> router `missing_value`
- benchmark `inconsistency` -> router `format_inconsistency` / `unit_or_time_format` / `row_alignment`
- benchmark `semantic_anomaly` -> currently only partial support; treat as a gap to improve

### Phase 3: Future extension
If needed, create a small conversion script later to:
- read `issue.json`
- build a diagnose-only regression report
- compute precision / recall by issue family

## Important note
Do **not** mix this dataset into `dataset.json` for the main task runner right now.
That would blur two different evaluation goals:
- end-to-end spreadsheet task solving
- data-quality diagnosis and QA precision
