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
