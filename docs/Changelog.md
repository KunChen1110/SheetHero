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
