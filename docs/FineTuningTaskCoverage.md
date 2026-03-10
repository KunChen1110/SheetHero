# Fine-Tuning Task Coverage

This file summarizes which dataset tasks are currently suitable for generating
fine-tuning data from the backend pipeline.

Principle:
- Only include tasks that have a successful end-to-end logger under the current
  helper-first / bounded execution design.
- Prefer tasks that are stable enough to represent reusable execution patterns,
  not just one-off lucky runs.
- Image-heavy tasks are excluded from the recommended set for now.

Last updated: 10/3/2026

## Recommended Stable Tasks

These tasks have successful execution logs and are suitable as the current
recommended fine-tuning coverage set.

| Task | Title | Capability Family | Output Type | Latest Successful Evidence |
|------|-------|-------------------|-------------|----------------------------|
| 01 | Budget calculating | multi-file merge + aggregation + highlight | spreadsheet | `artifacts/loggers/sheethero_tc01_input01_20260310_003605.md` |
| 02 | Meeting schdeuling | multi-file join + normalization + schedule table | spreadsheet | `artifacts/loggers/sheethero_tc02_input01_20260309_144853.md` |
| 03 | Internet Penetration Rate Analysis (visualization) | messy multi-row header cleaning + ranking + chart | spreadsheet | `artifacts/loggers/sheethero_tc03_input01_20260309_181822.md` |
| 04 | Task scheduling table | DAG scheduling + duration summary | spreadsheet | `artifacts/loggers/sheethero_tc04_input01_20260309_142236.md` |
| 05 | Indian Smartphone shipment and market share | timeline overlap + aligned multiplication report | spreadsheet | `artifacts/loggers/sheethero_tc05_input01_20260309_215507.md` |
| 07 | Ice-cream sales vs temperature, rain, price | regression coefficient estimation | spreadsheet | `artifacts/loggers/sheethero_tc07_input01_20260309_125713.md` |
| 08 | Iris datasets | filtered correlation matrix | spreadsheet | `artifacts/loggers/sheethero_tc08_input01_20260309_190645.md` |
| 09 | Business Analysis of Coca cola company | ratio computation + yearly summary table | spreadsheet | `artifacts/loggers/sheethero_tc09_input01_20260309_222528.md` |
| 10 | Cycle detection in graphs | multi-file graph analysis | spreadsheet | `artifacts/loggers/sheethero_tc10_input01_20260309_195814.md` |
| 11 | Inventory Management problem | EOQ / reorder point / sensitivity report | spreadsheet | `artifacts/loggers/sheethero_tc11_input01_20260309_203940.md` |
| 12 | Multi-Source Financial Performance Dashboard | multi-source financial dashboard | spreadsheet | `artifacts/loggers/sheethero_tc12_input01_20260309_201935.md` |
| 13 | Global Diabetes Population Analysis | multi-source healthcare aggregation | spreadsheet | `artifacts/loggers/sheethero_tc13_input01_20260309_223016.md` |
| 14 | Global Mobile Reviews Analysis | grouped review summary | spreadsheet | `artifacts/loggers/sheethero_tc14_input01_20260309_224156.md` |
| 17 | Store Feature Analysis | grouped numeric analysis across multiple sheets | spreadsheet | `artifacts/loggers/sheethero_tc17_input01_20260309_230702.md` |
| 20 | Hospital Resource Utilization Analysis | multi-source utilisation analysis + conditional highlight | spreadsheet | `artifacts/loggers/sheethero_tc20_input01_20260309_210811.md` |
| 21 | Interviewee screening | large multi-file candidate ranking | spreadsheet | `artifacts/loggers/sheethero_tc21_input01_20260309_202941.md` |
| 22 | Missing Data (Simple) | text-only missing-data scan report | text | `artifacts/loggers/sheethero_tc22_input01_20260309_212908.md` |
| 23 | Fill Missing Data from Another File (Simple) | reference-based fill / imputation | spreadsheet | `artifacts/loggers/sheethero_tc23_input01_20260309_164131.md` |
| 24 | Merge Two Files (Simple) | simple merge | spreadsheet | `artifacts/loggers/sheethero_tc24_input01_20260309_161719.md` |
| 25 | Merge Three Files (Simple) | simple multi-file merge | spreadsheet | `artifacts/loggers/sheethero_tc25_input01_20260309_164447.md` |
| 26 | Merge Four Files (Simple) | simple multi-file merge | spreadsheet | `artifacts/loggers/sheethero_tc26_input01_20260309_164808.md` |
| 27 | Room Syntax Difference (Simple) | text-only inconsistency report | text | `artifacts/loggers/sheethero_tc27_input01_20260309_213341.md` |

## Recommended Capability Coverage for Fine-Tuning

If the goal is to fine-tune execution behavior rather than memorize individual
testcases, the current stable set covers these reusable task families:

1. Multi-file merge and reconciliation
   - Tasks: 01, 02, 23, 24, 25, 26

2. Aggregation / summary / ranking reports
   - Tasks: 01, 09, 11, 12, 13, 14, 17, 20, 21

3. Structured algorithmic tasks
   - Tasks: 04, 10

4. Statistical / ML-style table generation
   - Tasks: 07, 08

5. Messy schema / header cleaning
   - Tasks: 03, 23, 27

6. Text-only diagnostic outputs
   - Tasks: 22, 27

## Suggested First Fine-Tuning Set

If only a smaller high-confidence subset is needed at first, use:

- Task 01
- Task 03
- Task 04
- Task 07
- Task 08
- Task 10
- Task 12
- Task 17
- Task 21
- Task 23
- Task 24
- Task 27

Reason:
- These tasks cover the main helper-first execution families.
- They include both spreadsheet-output tasks and text-output tasks.
- They include single-file, multi-file, algorithmic, statistical, and
  cleaning-oriented workflows.

## Not Recommended for the First Fine-Tuning Batch

These tasks are not in the current recommended training set:

### Task 06
- Has historical successful logs.
- Not recently re-validated after the latest large execution/runtime refactor.
- Use only after a fresh end-to-end confirmation.

### Task 15
- Helper path and output logic were checked during development.
- A fresh clean CLI confirmation was not completed in the final stabilization
  window.
- Treat as pending verification before using it as fine-tuning ground truth.

### Task 16, Task 18, Task 19
- Image / visualization-heavy tasks.
- Excluded from the current recommended set because the current effort focused
  on non-image execution stability.

## Important Note for Fine-Tuning Data Construction

The goal should be to fine-tune on stable execution patterns, not on
testcase-specific hardcoding.

The current backend is strongest when the model follows these patterns:
- use helper-first execution paths
- ground all logic in visible workbook schema
- avoid forbidden raw file I/O APIs
- produce either:
  - a structured spreadsheet output, or
  - a deterministic text answer when the task is diagnostic only

For that reason, the recommended fine-tuning examples should preserve:
- the original user request
- the grounded plan / understanding signal
- the execution code or structured execution decision
- the final expected spreadsheet/text result

They should not preserve:
- testcase-specific filename guessing
- deprecated execution paths
- older runtime behaviors that were later removed during stabilization
