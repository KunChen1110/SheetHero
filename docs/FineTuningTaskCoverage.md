# Fine-Tuning Task Coverage

This document summarizes the current backend coverage that is suitable for fine-tuning data construction.

The current system is no longer best described as a collection of task-specific handlers. After the `v4.0` backend work, the project is better understood as a **skill-based spreadsheet pipeline** with:
- benchmark-driven diagnose and QA improvement
- helper-first deterministic execution for covered workflow families
- synthetic skill regression for abstract spreadsheet capabilities

Therefore, this document now organizes fine-tuning coverage in three layers:
1. dataset task coverage
2. diagnose / QA coverage
3. abstract family coverage

Last updated: 26/3/2026

---

## Fine-Tuning Principle

A candidate training example should satisfy at least one of these goals:
- reinforce a stable spreadsheet workflow family
- reinforce diagnose / QA behavior for imperfect spreadsheet inputs
- reinforce helper-first execution and grounded parameter selection

It should **not** mainly teach the model to memorize a benchmark task ID or a one-off filename pattern.

---

## 1. Recommended Dataset Task Coverage

These dataset tasks remain useful as supervised fine-tuning anchors because they map cleanly onto reusable spreadsheet capability families.

| Task | Title | Current Role in Fine-Tuning | Covered Family / Pattern |
| --- | --- | --- | --- |
| 01 | Budget calculating | high-value anchor | schema-aligned merge + aggregation + summary metrics + highlight |
| 02 | Meeting scheduling | high-value anchor | relational assignment schedule / multi-table entity alignment |
| 03 | Internet Penetration Rate Analysis | useful advanced anchor | temporal growth visual report |
| 04 | Task scheduling table | high-value anchor | dependency-constrained schedule |
| 05 | Indian Smartphone shipment and market share | useful anchor | temporal alignment / derived efficiency style workflow |
| 07 | Ice-cream sales analysis | high-value anchor | tabular regression analysis |
| 08 | Iris datasets | high-value anchor | pairwise correlation matrix |
| 09 | Coca-Cola business analysis | useful anchor | ratio / summary reporting |
| 10 | Cycle detection in graphs | high-value anchor | graph consistency scan |
| 11 | Inventory Management problem | useful anchor | parameter-driven policy report |
| 12 | Multi-Source Financial Performance Dashboard | high-value anchor | multi-source metric dashboard |
| 13 | Global Diabetes Population Analysis | useful anchor | grouped aggregation / multi-source summary |
| 14 | Global Mobile Reviews Analysis | useful anchor | grouped metric summary |
| 17 | Store Feature Analysis | useful anchor | comparative multi-sheet summary / grouped analysis |
| 20 | Hospital Resource Utilization Analysis | high-value anchor | capacity / utilisation report |
| 21 | Interviewee screening | useful advanced anchor | entity ranking report |
| 22 | Missing Data (Simple) | high-value diagnose anchor | missing-data text scan |
| 23 | Fill Missing Data from Another File (Simple) | high-value anchor | reference-guided completion |
| 24 | Merge Two Files (Simple) | high-value anchor | relational join enrichment |
| 25 | Merge Three Files (Simple) | useful anchor | relational join enrichment |
| 26 | Merge Four Files (Simple) | useful anchor | relational join enrichment |
| 27 | Room Syntax Difference (Simple) | high-value diagnose anchor | identifier-format scan |

### Notes
- These tasks are now most valuable when used as **family examples**, not as isolated benchmark IDs.
- For training construction, prompts should be slightly paraphrased and file names should be varied so the model learns the workflow family rather than the task label.

---

## 2. New Diagnose / QA Coverage

The backend now includes a dedicated diagnose benchmark:
- `dataset/DiagnoseBenchmark/SpreadsheetDiagnosisData`
- CLI command: `!DiagnosebenchmarkTest`

This benchmark is especially valuable for fine-tuning or distillation of:
- diagnose triggering
- issue-family classification
- concrete QA wording
- preview-aware clarification behavior

### Recommended Diagnose / QA Training Targets
The current diagnose system covers these issue families well enough to be treated as reusable supervision targets:
- `missing_value`
- `missing_key_column`
- `format_inconsistency`
- `unit_or_time_format`
- `row_alignment`
- `semantic_anomaly`
- `duplicate_conflicting_rows`
- `missing_period_endpoint`

### Best Use of Diagnose Benchmark Data
Use diagnose benchmark cases to train or distill:
- when to ask a clarification question
- how to describe the issue concretely
- how to reference file / sheet / row / column clearly
- how to attach a readable context preview

Do **not** use them mainly to teach final spreadsheet execution logic.

---

## 3. Abstract Family Coverage

The most important change in the current system is that backend logic has shifted from task-oriented branching to family-oriented handling.

The following abstract spreadsheet families are now the strongest fine-tuning targets because they correspond to reusable backend policies rather than one-off benchmark behavior.

### High-Priority Execution Families
- `schema_aligned_merge_summary`
- `reference_guided_completion`
- `grouped_aggregation_ranking`
- `temporal_aggregation_ranking`
- `relational_join_enrichment`
- `composite_key_relational_join`
- `dependency_constrained_schedule`
- `relational_assignment_schedule`
- `capacity_constrained_allocation`
- `tabular_regression_analysis`
- `pairwise_correlation_matrix`
- `temporal_growth_visual_report`

### High-Priority Text / Diagnose Families
- `missing_data_scan`
- `identifier_format_scan`
- related diagnose / QA issue families from the benchmark set

### Useful Report / Summary Families
- `multi_source_metric_dashboard`
- `entity_ranking_report`
- `parameter_driven_policy_report`
- `capacity_utilisation_report`
- `grouped_metric_summary`
- `comparative_multi_sheet_summary`
- `relational_flattening_report`

---

## 4. Recommended Fine-Tuning Construction Strategy

The most effective current strategy is **not** to build one large flat dataset of all task logs.

Instead, construct training data in layers.

### Layer A: Diagnose / QA examples
Source:
- diagnose benchmark
- stable QA task logs

Target behavior:
- detect issues
- ask concrete questions
- preserve structured clarification logic

### Layer B: Family-routing and grounded planning examples
Source:
- representative task logs
- synthetic skill regression prompts
- paraphrased versions of current benchmark tasks

Target behavior:
- recognize the correct spreadsheet family
- select the right helper-first path
- avoid drifting into unrelated pandas logic

### Layer C: Helper-first execution examples
Source:
- high-confidence stable task runs
- deterministic family outputs

Target behavior:
- call the right helper
- ground parameters in visible schema
- produce output that matches the family contract

---

## 5. Current Best First Fine-Tuning Set

If only a smaller high-confidence subset is needed first, the recommended set is:

### Diagnose / QA subset
- diagnose benchmark small + median splits
- Task 22
- Task 27
- selected QA-heavy portions of Task 01, Task 02, Task 04

### Execution family subset
- Task 01
- Task 02
- Task 04
- Task 07
- Task 08
- Task 10
- Task 12
- Task 20
- Task 23
- Task 24
- Task 25
- Task 26

### Why this subset
- It covers merge, fill, schedule, join, regression, correlation, dashboard, and diagnostic text output.
- It covers both spreadsheet-output and text-output behaviors.
- It aligns well with the current deterministic skill-based backend rather than older ad hoc execution behavior.

---

## 6. Not the Best First Fine-Tuning Targets

These are not necessarily bad tasks, but they are not the strongest first-batch training targets.

### Image-heavy / visualization-heavy tasks
- Tasks whose main success criteria depend heavily on charts or visual layout should be secondary.
- Use them after core family execution behavior is stable.

### One-off historical logs from older runtime designs
- Avoid using logs that came from earlier pre-family, pre-bounded, or pre-deterministic versions of the backend.
- The current goal should be to reinforce the **current** backend contract, not older behavior.

### Cleanup-only artifact outputs
- Old task artifacts and obsolete outputs are not useful training signals.
- Prefer freshly validated logs or deterministic family examples.

---

## 7. Current Conclusion

At the current project stage, the most valuable fine-tuning coverage is no longer simply “which benchmark tasks passed”.

The stronger view is:
- benchmark tasks provide anchor examples
- diagnose benchmark provides structured QA supervision
- synthetic skill regression defines abstract capability coverage

This means the current fine-tuning story should be presented as:

> the project now supports fine-tuning and distillation around reusable spreadsheet workflow families, concrete diagnose/QA behavior, and grounded helper-first execution, rather than only around fixed benchmark tasks.

That is much more aligned with the current backend design and with the direction established in `v4.0`.
