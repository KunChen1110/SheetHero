## 30/10/2025
### Initial Commit

## 2/11/2025
### --- Added ---
- Added 4 user cases to dataset (See [dataset](/dataset))

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

## 4/11/2025
### --- Added ---
- New modern GUI interface that provides a better user-experience
  - Split menu functionality into three separate pages, `UploadPage`, `ConfigPage` and `PromptPage`.
    - `UploadPage` used to upload the data files into the GUI and specify the output file directory
    - `ConfigPage` used to specify configurations for the model
    - `PromptPage` used to interact with SheetHero, providing prompts and feedback to requests.

## 6/11/2025
### --- Changed ---
- Updated [README.md](../README.md) with new content
  - Documented features that displays the software's current features
  - Documented preview that displays the software's user-interface as well as how to use it properly
  - Documented download instructions, including for different operating-systems
