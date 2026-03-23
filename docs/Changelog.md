## 30/10/2025
### Initial Commit

## 2/11/2025
### --- Added ---
- Added 4 user cases to dataset (See [dataset](/dataset))


## 4/11/2025
### --- Added ---
- New modern GUI interface that provides a better user-experience
  - Split menu functionality into three separate pages, `UploadPage`, `ConfigPage` and `PromptPage`.
    - `UploadPage` used to upload the data files into the GUI and specify the output file directory
    - `ConfigPage` used to specify configurations for the model
    - `PromptPage` used to interact with SheetHero, providing prompts and feedback to requests.
  - Configurations are now able to be made via the user-interface, this includes:
    - `API Key`, to specify the api key for the OpenAI model.
    - `Base URl`, to customise if the user wants to use a private server.
    - `Deployment`, to specify which model deployment wants to use.
    - `Max Turns`, to specify how many iterations the model can perform during analysis.
  - Buttons to open the generated log `.md` files as well as generated `.xlsx` file are now presented to the user.

## 6/11/2025
### --- Changed ---
- Updated [README.md](../README.md) with new content
  - Documented features that displays the software's current features
  - Documented preview that displays the software's user-interface as well as how to use it properly
  - Documented download instructions, including for different operating-systems

## 10/11/2025
### --- Added ---
- Added two wireframes for the software's user interface (See [SoftwareDesign](SoftwareDesign.md))

## 11/11/2025
### --- Added ---
- Added 12 test cases for evaluating LLM performance on spreadsheet
- Documented test results in [DatasetV1.md](/dataset/DatasetV1.md)

## 12/11/2025
### --- Added ---
- Added **Titanic correlation analysis script (Test 6)**
  - Calculates Pearson correlation between survival and key factors (Sex, Age, Fare, Cabin, Embarked).
  - Saved results to [output6.xlsx](/dataset/Task6/output6.xlsx).

- Added **Cycle detection script (Test 10)**
  - Detects cycles in 5 directed graph datasets using DFS.
  - Saved results to [output10.xlsx](/dataset/Task10/output10.xlsx)

- Added **Ice-cream sales regression script (Test 7)**
  - Performs multiple linear regression to analyze effects of temperature, price, tourists, and rain on ice cream sales.
  - Saved results to [output7.xlsx](/dataset/Task7/output7.xlsx)

- Added 5 new user cases to the dataset (Tests 16–20) (See [dataset](/dataset))

## 15/11/2025
### --- Added ---
- Added **background research folder** under `docs/` (`docs/BGResearch/`)
  - Collected reference papers used in the project
  - Added reading notes and background research summaries for the papers

## 21/11/2025
### --- Added ---
- Added ouyput mode handling in `core/agent.py`
  - Added `outputMode()` as a shared public entry point for all task scripts.
  - Added support for choosing **terminal** or **file** output modes.

### --- Changed ---
- Updated multi-file handling in `SheetBrain` to improve merging behaviour.

### --- Fixed ---
- Fixed a bug where numeric values were incorrectly summed when merging multiple Excel files.
  - Numeric columns are now aggregated correctly across all input files.

## 25/11/2025
### --- Added ---
- Added CLI handling in `main.py` so SheetBrain can be run directly from the command line with a question and one or more input files.
- Added support for choosing **text** or **file** output modes in the CLI, re-using the `outputMode()` logic from `task2.py`.
- Introduced `output_formatter` module to centralise result formatting and support **user** vs **verbose** output modes.

### --- Changed ---
- Updated `core/agent.py`, `modules/execution.py`, `modules/validation.py`, and `utils/logger.py` to integrate configurable output modes and cleaner, more focused logging.
- Reorganised the backend structure: moved previous ad-hoc test scripts into the `examples/scripts` folder to separate core library code from examples and experiments.

### --- Fixed ---
- Fixed `main.py` so CLI arguments are parsed correctly and passed into `SheetBrain`.
- Ensured the selected output mode (file or text) is respected end-to-end when running tasks via the command line.

## 30/11/2025
### --- Added ---
- Added centralized prompt management in `modules/prompts.py`
  - Integrated all prompts from Understanding, Execution, and Validation modules into a single file
  - Improved maintainability and consistency of AI prompts

- Added automatic verbose logging system
  - All detailed execution logs are now automatically saved to markdown files in `loggers/` folder
  - Logs include LLM thoughts, code execution, validation analysis, and iteration details
  - Log file path is displayed in the result output

### --- Changed ---
- Refactored output and logging architecture
  - Removed verbose/user mode selection - system now always generates detailed logs to file as the team discussed
  - Terminal output is always concise (user mode format)

### --- Removed ---
- Removed unused functions and imports
  - `_content_to_text()`, `_format_dataframe_to_markdown()`, `_detect_file_path()` from `utils/output_formatter.py`
  - `output_mode()` alias function from `core/agent.py`
  - Unused `pandas` and `re` imports from `output_formatter.py`
  - `verbose` configuration option from `config/settings.py` (always enabled now)

- Simplified code structure
  - Removed verbose comments from `core/__init__.py`
  - Removed `build_output_preferences` and `output_mode` exports from `core/__init__.py` (internal use only)

## 6/2/2026
### --- Added ---
- Added local LLM integration layer
  - Implemented interface to call local LLM backends
  - Extended runtime pipeline to support local inference execution

## 12/2/2026
### --- Added ---
- Introduced dedicated prompt modules for online and offline modes
  - `prompt_texts_online.py` now contains all default/online prompt templates.
  - `prompt_texts_offline.py` defines stricter offline prompts with verification-heavy guardrails.
- Added offline-specific execution guardrails and merge playbook
  - Enforced 6-step offline execution checklist (inventory, schema resolution, type checks, coverage proof, and output writing).
  - Added explicit column alias resolution, missing-value policy, and date coverage checks.
  - Added an offline merge/concat playbook to reduce hallucinations around multi-file joins.

### --- Changed ---
- Updated execution response formats for both online and offline modes
  - Online execution is now code-only and must always write an Output sheet and save the workbook via `save_workbook_to(output_path)`, returning the saved file path.
  - Offline execution is now strictly code-only as well, disallowing free-form natural language "Final Answer" responses.
- Refactored `prompt_data.py` to import shared building blocks from `prompt_texts_online.py` and offline-only pieces from `prompt_texts_offline.py`.

## 21/2/2026
### --- Added ---
- Added bounded error routing for offline execution in `stages/execution/runtime.py`
  - Detects common failure patterns and sends targeted minimal-fix feedback (e.g., wrong `inspector_multi` signature, undefined names, invalid helper imports).
  - Added consecutive-forbidden handling with a hard-reset code template to break repeated forbidden loops.
- Added explicit bounded forbidden rules in `stages/execution/executor.py`
  - Blocks `common_functions` imports and invalid `inspector_multi` call styles (keyword `range_ref`, missing required range argument).

### --- Changed ---
- Reworked offline bounded strategy from strict sentinel/format gating to bounded-lite guardrails
  - Kept function-level safety checks and runtime feedback loops.
  - Removed brittle sentinel-driven blocking that caused format oscillation.
- Simplified and refocused `prompt_texts_offline.py`
  - Kept concise high-value rules and helper signatures.
  - Added concrete correct-call examples for `inspector_multi`.
- Updated `prompt/prompt_builder.py` so offline mode uses offline-specific execution helper sections only (without online heavy sections).
- Updated parser behavior in `stages/execution/parser.py`
  - Prioritizes Python code-block extraction before `Final Answer` text detection.
- Updated output instruction text in `agent/core/SheetHero.py`
  - Aligns offline output behavior with `SAVED_FILE`/saved-path execution flow.

### --- Fixed ---
- Fixed runtime success/error accounting in `stages/execution/runtime.py`
  - Execution results containing traceback are now handled as failures and fed back into bounded repair flow instead of being treated as successful turns.
- Fixed repeated local-model dead loops caused by over-strict path blocking
  - Relaxed hard-blocking on absolute path literals to avoid immediate re-block when local models copy context paths.
- Added environment override for bounded mode in `agent/core/SheetHero.py`
  - `SHEETHERO_BOUNDED_MODE=0/1` can force disable/enable bounded behavior for quick A/B debugging.

## 22/2/2026
### --- Added ---
- Added strict prompt profile routing for execution environments
  - Introduced profile-based prompt packs (`offline_strict`, `online_rich`) and centralized selection in prompt builder.
  - Local/custom endpoint runs now route to `offline_strict`; hosted OpenAI runs keep `online_rich`.
- Added offline `Output Contract` in understanding prompt
  - Understanding stage now emits machine-readable intent flags:
    - `requires_detailed_table`
    - `requires_highlight`
    - `requires_summary_metrics`
  - Contract is used by runtime for output-shape validation instead of keyword guessing.
- Added stronger bounded forbidden checks in execution
  - Blocks invalid partial-patch placeholders like `... (previous code remains unchanged)`.
  - Added explicit guards for common drift patterns (`get_workbook(None)`, `wb.save`, `sheet.cell`, invalid `inspector_multi` kwargs).

### --- Changed ---
- Fully decoupled offline prompt texts from online prompt texts
  - `prompt_texts_offline.py` is now self-contained and no longer composed from online blocks.
  - Reorganized offline instructions around one stable helper-only pipeline.
- Reworked offline output-intent enforcement
  - Runtime now validates saved output against understanding `Output Contract`.
  - For merge/highlight/table-transform tasks, metric-only mini outputs are rejected and forced to repair.
- Updated output requirement wording in `SheetHero`
  - Clarified intent-priority: merge/highlight/table tasks require detailed table + highlight + summary.

### --- Fixed ---
- Fixed false-positive validation passes in offline mode
  - Fast-pass now respects intent contract and no longer passes metric-only outputs for merge/highlight tasks.
- Fixed unstable table construction from wide range reads (`A1:Z200`)
  - Offline prompt now enforces shape-safe header/row extraction to remove empty headers and blank rows before DataFrame creation.
- Fixed repeated malformed code continuation behavior
  - Runtime now rejects non-executable "patch-style" continuation responses and requires full executable blocks each turn.

## 23/2/2026
### --- Added --- 
- Updated offline prompts for `understanding`, `execution`, and `validation` in `src/backend/prompt/prompt_texts_offline.py`.
- Tightened `understanding` output constraints: plain-text only, no code blocks, no forbidden API mentions.
- Added stricter `execution` guidance for date handling and highlight row indexing (flat 1-based integer rows).
- Added local-model config visibility: `!llm --show`.
- Added one-step offline switch command: `!llm --switch--offline <model_full_name>`.
- `--switch--offline` now automatically sets:
  - `base_url = http://localhost:11434/v1`
  - clears configured `api_key`
  - `deployment = <model_full_name>`
- Kept existing dataset debug workflow unchanged (`!dataset --index N`, `run`).


## 23/2/2026
### --- Changeed --- 
- Refactored the execution prompt, execution module in `src/backend/prompt` and `src/backend/stages/execution`.

## 4/3/2026
### ---Changed---
- Refactored execution runtime into modular components for maintainability and clearer control flow.
- Added dedicated forbidden policy module with signature-based memory to reduce repeated violations.
- Added error feedback module for repeated-failure loop breaking and targeted minimal-fix guidance.
- Added workbook grounding module to enforce runtime-visible files/schemas and reduce hallucinated references.
- Added output contract checker to validate task-intent completion and block false-success saves.
- Kept offline bounded behavior while reducing runtime complexity and improving debuggability.


## 10/3/2026
### --- Added ---
- Added deterministic final response stage in `src/backend/stages/final_response/stage.py`
  - System now returns a short user-facing answer in addition to the original final result.
  - Scalar tasks can now answer directly with the computed value.
  - Spreadsheet-generation tasks now return a short content-aware summary instead of only a saved file path.
- Added frontend-facing config schema helpers in `src/backend/config`
  - Centralized editable UI fields, defaults, and deployment choices in `ConfigFactory`.
  - Reduced duplicated frontend hardcoded configuration values.
- Added clearer package exports and package-level documentation
  - Expanded `__init__.py` files across backend packages to clarify stable entrypoints vs internal implementation files.

### --- Changed ---
- Major execution-stage refactor in `src/backend/stages/execution`
  - Reorganized execution internals into subpackages:
    - `core/` for executor, parser, LLM client, history, and summary
    - `analysis/` for task-intent detection, workbook grounding, and helper-source analysis
    - `guards/` for forbidden policy, repair feedback, loop breakers, and output-contract checks
  - Kept `runtime.py` and `stage.py` as the stable outer execution entrypoints.
  - Reduced `runtime.py` size by moving large pure-function sections into dedicated files.
- Updated frontend/backend integration path
  - Frontend now uses `SheetHeroService` as the stable backend entrypoint instead of bypassing the full backend pipeline.
  - Frontend config pages now read defaults and editable fields from backend config schema.
- Reworked final output behavior for both online and offline modes
  - Final short answers now prefer deterministic generation instead of always making one more LLM call.
  - Reduced end-of-run delay after successful execution and validation.

### --- Removed ---
- Removed unused legacy output formatting code
  - Deleted deprecated `OutputFormatter` in `src/backend/agent/io/formatter.py`.
- Removed stale execution helper definitions from the main execution runtime after modular extraction
  - Old intent-detector and loop-breaker blocks are no longer kept inline in `runtime.py`.


## 15/3/2026
### --- Added ---
- Added shared sheet-table extraction helper in `src/backend/environment/spreadsheet/tools/cross_workbook.py`
  - Introduced `extract_sheet_table(...)` so diagnose and execution can use the same header detection, column trimming, note-row stopping, and text normalization logic.
  - Added row-to-Excel mapping metadata (`excel_rows`, `header_excel_row`) for more accurate QA previews.
  - Added overflow-row metadata for malformed CSV detection.

### --- Changed ---
- Improved diagnose and QA behavior in `src/backend/router/diagnose_router.py`
  - Diagnose now reuses shared table extraction instead of rebuilding DataFrames from raw workbook first rows.
  - QA previews now preserve original column order and use real Excel row numbers.
  - For first-row issues, previews now include a comparison row automatically.
  - Missing dependency questions are now more concrete, e.g. asking whether a blank `Depends on` means a root task.
  - Added stronger relevance scoring for dependency-related columns in scheduling tasks.
  - Reworked CSV row-shift detection to identify rows whose raw values overflow the visible header structure.

- Improved QA answer handling in `src/backend/stages/qa/stage.py`
  - Reply matching now prioritizes the exact user-facing clarification question instead of the internal abstract description.
  - Interpretation-style answers such as “this is the root task” are now preserved as explicit policies instead of being silently dropped.

- Updated session/execution context flow
  - Added QA interpretation policy storage to `SheetHeroSession`.
  - `SheetHero` now forwards interpretation policies into execution context before code generation.

- Updated execution preflight coverage in `src/backend/stages/execution/runtime.py`
  - Added helper-first allowlisting for `build_ecommerce_merge_report(...)` so ecommerce merge tasks are not incorrectly blocked by generic linear I/O preflight checks.

- Updated final logging output in `src/backend/agent/utils/sheethero_helpers.py`
  - Final logger summaries now include both `Final Answer` and `Short Answer`.

### --- Fixed ---
- Fixed repeated QA mismatch loops for valid direct answers
  - Responses like “this is the root task” are now accepted correctly for dependency clarification.
- Fixed incorrect preview labeling
  - `comparison row` and `issue row` are now shown correctly in QA previews.
- Fixed diagnose/execution schema drift
  - Diagnose no longer uses a separate raw-workbook interpretation path that could disagree with execution-time table extraction.
- Fixed vague CSV clarification issues in merge-like tasks
  - `Task02`-style malformed CSV rows are now surfaced as row-alignment problems instead of unrelated abstract conflicts.

## 23/3/2026
### --- Added ---
- Added a centralized task-family registry in `src/backend/task_families.py`
  - Introduced abstract spreadsheet capability families instead of relying on scattered task-specific branching.
  - Centralized family-level policy for:
    - helper selection
    - diagnose skip behavior
    - output mode
    - output contract expectations
    - execution strict rules
    - loop breakers
    - final-response labels

- Added deterministic execution families for high-frequency spreadsheet workflows
  - Added or formalized deterministic family paths for:
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
    - text-only scan/report families
    - dashboard / ranking / summary helper families

- Added generalized helper workflows for new abstract families
  - `build_time_series_aggregation_report(...)`
  - `build_grouped_aggregation_ranking_report(...)`
  - `build_relational_join_enrichment_report(...)`
  - `build_multi_key_relational_join_report(...)`
  - `build_capacity_constrained_allocation_report(...)`

- Added synthetic family regression coverage
  - Added `test/utils/run_family_synthetic_regression.py` to validate abstract family routing and deterministic runtime behavior without depending only on dataset tasks.
  - Added CLI support for one-command execution via `!FamilySyntheticTest`.

### --- Changed ---
- Reworked the backend from task-oriented patches to family-oriented architecture
  - Understanding, diagnose, execution, validation, and final response now share the same family abstraction.
  - The system now reasons in terms of spreadsheet capability families rather than individual benchmark task IDs.

- Strengthened deterministic execution and reduced LLM dependence
  - For covered families, execution now prefers deterministic helper-first fast paths before invoking model-generated code.
  - Reduced runtime latency and improved reliability for covered spreadsheet task families.

- Strengthened family-aware validation
  - Added family-specific deterministic workbook inspectors for:
    - grouped aggregation
    - temporal aggregation
    - relational join
    - allocation
    - assignment schedule
    - dependency schedule
    - regression
    - correlation
    - comparative multi-sheet summaries
    - temporal growth visual reports

- Improved detector generalization
  - Expanded natural-language family detection for:
    - grouped analysis
    - temporal analysis
    - regression and correlation
    - assignment/scheduling
    - capacity-constrained allocation
    - multi-key joins
  - Detection is now less dependent on testcase wording and better aligned with generic spreadsheet task phrasing.

### --- Fixed ---
- Fixed validation mismatches for deterministic allocation outputs
  - Allocation outputs are no longer incorrectly rejected for missing a generic summary-metrics block when a family-specific summary row is already valid.

- Fixed large-task architectural drift
  - Moved additional execution/validation family routing logic into centralized registry mappings to reduce duplicated branching and future regression risk.

- Fixed synthetic regression coverage gaps
  - Added end-to-end synthetic validation for newly introduced abstract families, including multi-key joins, temporal growth reporting, and capacity-constrained allocation.
