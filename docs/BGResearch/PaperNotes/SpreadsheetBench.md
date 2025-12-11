## SPREADSHEETBENCH: Towards Challenging Real World Spreadsheet Manipulation

This paper introduces **SPREADSHEETBENCH**, a new and challenging benchmark designed to evaluate the capabilities of Large Language Models (LLMs) on complex, real-world spreadsheet manipulation tasks.

The authors argue that while millions of users rely on spreadsheets, current AI agents (like SheetCopilot or Copilot in Excel) are not as helpful as they could be. A primary reason for this is that the benchmarks used to test them are flawed and do not represent the actual challenges users face.

## The Problem with Existing Benchmarks

The paper identifies three main limitations in previous benchmarks:

1.  **Synthetic Queries:** They often use "self-instruct" techniques or crowd-workers to create simple, artificial instructions. Real user questions are far more complex, often including descriptions of previous failed attempts, specific errors encountered, and detailed context.
2.  **Oversimplified Spreadsheets:** They typically use clean, simple files that contain only one standard relational table. This is more like a database task (Text2SQL) or a simple Table Question-Answering (TableQA) task.
3.  **Weak Evaluation:** They usually involve a single test for each instruction. This can lead to "false positive" solutions that work for one specific spreadsheet but fail to generalize to other files with different data values.

## Key Features of SPREADSHEETBENCH

SPREADSHEETBENCH is designed to solve these problems by grounding the entire benchmark in real-world data.

* **Real-World Instructions:**
    The benchmark is built from **912 real questions** gathered from popular online Excel forums like *excelforum.com*, *MrExcel*, and *Chandoo.org*. These instructions are much more complex and longer (averaging 85.7 words) than in other benchmarks. For example, a user might describe a complex problem, explain the formulas they already tried (e.g., `SUM`, `SUMPRODUCT`), and describe why those formulas failed.

* **Complex and Diverse Spreadsheets:**
    The spreadsheets are also taken directly from the forum posts. They reflect how real people organize data, which is often messy.
    * **Multiple Tables:** Over 35% of the spreadsheets contain multiple distinct tables on a single sheet.
    * **Non-Standard Tables:** Nearly 43% feature non-standard relational tables, such as those with nested headers, incomplete headers, or missing headers.
    * **Non-Textual Elements:** The files contain free-form text and non-textual elements like cell colors, which are often part of the user's request (e.g., "highlight the cell in yellow").

* **Robust "Online Judge" (OJ-Style) Evaluation:**
    To ensure solutions are robust, the benchmark introduces a new evaluation metric inspired by competitive programming platforms.
    * Instead of one test, each instruction is associated with **multiple test cases** (an average of three per instruction).
    * These test cases share the same structure but have different data values, including "corner cases" designed to break simple solutions.
    * An LLM's generated code solution is only considered fully correct if it passes **all** test cases for that instruction.
    * The paper proposes two scoring rules: a **soft restriction** ($S_{soft}$) that gives partial credit for passing some test cases, and a **hard restriction** ($S_{hard}$) that gives zero credit unless all test cases pass.

## Key Findings

The authors evaluated a wide range of models, including TableQA models, open-source code models, advanced closed-source models (like GPT-4o), and spreadsheet-specific agents (Copilot in Excel).

The results were stark:
* **A Massive Performance Gap:** There is a **"substantial gap"** between the best-performing (SOTA) models and human expert performance.
* **Low SOTA Scores:** Even the most advanced models performed poorly. GPT-4o achieved an overall accuracy of 18.35% (soft restriction), and Copilot in Excel scored 20.00% on a subset of the data.
* **Human Performance:** In contrast, human experts achieved an accuracy of 71.33% on a subset of the tasks.
* **Nature of Failures:** Case studies showed that models fail for different reasons. GPT-3.5 showed a lack of coding ability, producing incorrect code. GPT-4o, while better at coding, failed by misunderstanding the complex, non-standard table structures, such as misaligning tables or incompletely reading a lookup table.

## Conclusion

The paper concludes that SPREADSHEETBENCH effectively exposes the weaknesses of current LLMs in handling real-world spreadsheet tasks. Its difficulty highlights that proficient coding skills and a deep understanding of diverse spreadsheet structures are both essential for true automation. The benchmark serves as a more realistic and challenging target for developing the next generation of spreadsheet agents.