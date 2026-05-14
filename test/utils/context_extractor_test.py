#!/usr/bin/env python3
"""CLI test for ContextExtractor.extract_workbook_purpose_domain()."""

from __future__ import annotations

import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def main() -> int:
    repo_root = _repo_root()
    sys.path.insert(0, str(repo_root))

    from backend.agent.utils.context_extractor import ContextExtractor

    extractor_input = """### 1. **Sheet Summary**:

**Workbook Purpose & Domain**:
The purpose of the Excel workbooks is to manage and maintain information about tutors, specifically their IDs and names. This could be relevant in an educational or training context where tracking tutor assignments or availability is essential. The primary use case is to consolidate and fill in missing tutor information to ensure a complete dataset for administrative or operational needs.

**File Organization**:
There are 2 separate Excel files:
- **File 1**: `tc23_input01.xlsx` contains tutor data (TutorID and Name) in sheet `Sheet1`.
- **File 2**: `tc23_input02.xlsx` contains tutor data (TutorID and Name) in sheet `Sheet1`.
- **IMPORTANT**: Calculations that span multiple files MUST read from each file separately using inspector_multi().

**Sheet Organization**:
- The overall organization includes two files, each with one sheet—indicating a simple structure aimed at managing tutor data.
- **Sheet Names**: Both files have a single sheet named `Sheet1`.
  - `Sheet1` in `tc23_input01.xlsx` contains partial tutor data with missing Name entries.
  - `Sheet1` in `tc23_input02.xlsx` contains complete tutor data that can be used to fill the gaps in `tc23_input01.xlsx`.
- The sheets share the same structure (same columns: TutorID, Name) and require data from both files to complete the dataset.

**Data Structure & Types**:
- In both sheets, the key columns are:
  - **TutorID**: Numerical identifier for tutors (integer type)
  - **Name**: Textual representation of the tutor's name (string type)
- Each sheet has a consistent structure, enabling straightforward merging of data based on matching TutorIDs.

### 2. **Problem Insights**:
- **Relevant Data Scope**:
  This question requires data from File 1: `tc23_input01.xlsx` and File 2: `tc23_input02.xlsx`.
  - Data must be read from each file separately using the inspector_multi() function.
  - **The calculation requires combining data from multiple files** to fill in missing information in `tc23_input01.xlsx` using data from `tc23_input02.xlsx`.

- **Potential Challenges**:
  - There may be alignment issues due to missing TutorIDs or names, requiring careful mapping to avoid incorrect data associations.
  - Ensuring that the names retrieved from `tc23_input02.xlsx` correspond accurately to the TutorIDs in `tc23_input01.xlsx` is essential; any mismatches need to be addressed to avoid data integrity issues.

- **Validation Strategy**:
  - Verify that all relevant sheets were included in the analysis, ensuring that both `Sheet1` of `tc23_input01.xlsx` and `Sheet1` of `tc23_input02.xlsx` were accessed.
  - Check that data from `tc23_input02.xlsx` is accurately combined and replaces the missing entries in `tc23_input01.xlsx` without duplications or errors.

- **Hierarchical Data Considerations**:
  - The relationship is straightforward since each TutorID should uniquely identify a tutor. There are no complex parent-child relationships or nested categories presented in this dataset. Each TutorID maps directly to a single Name, and the completion of this mapping will enhance the dataset's usability for further analysis or reporting."""

    extracted = ContextExtractor.extract_workbook_purpose_domain(extractor_input)


    print("=== Context Extractor Test ===")
    print("Input section: Workbook Purpose & Domain block")
    print("\nExtracted output:")
    print(extracted)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
