# SheetBrain: A Neuro-Symbolic Agent for Accurate Reasoning over Complex and Large Spreadsheets

![img1](../img/SheetBrain_1.png)

## 1. Motivation
Large language models (LLMs) such as GPT-4 excel in text-based reasoning but struggle with **complex Excel-like spreadsheets** that have multi-table layouts, merged cells, and irregular structures.  
Traditional spreadsheet agents (e.g., SheetAgent, SheetCopilot) fail on these because they:
1. Lack deep spreadsheet structural understanding.  
2. Perform blind, token-limited reasoning.  
3. Have no self-correction or validation mechanisms.  

---

## 2. The SheetBrain Framework
SheetBrain introduces a **neuro-symbolic, three-stage pipeline** combining neural reasoning with symbolic code execution and validation.

### ① Understanding Module
- Builds a **global, query-aware overview** of the spreadsheet.  
- Produces:
  - **Sheet Summary:** Describes workbook purpose, sheet relationships, and layout.  
  - **Problem Insights:** Identifies relevant data regions and suggests execution strategies.  
- Uses **dynamic token budgeting** and **enhanced Markdown serialization** (includes cell positions, merged cell info) to preserve spatial layout efficiently.

### ② Execution Module
- Runs within a **Python sandbox** using `pandas` and a custom **Excel toolkit** (`inspector`, `search`, etc.).  
- Combines **neural planning** and **symbolic computation** for reasoning and manipulation.  
- Features:
  - **Symbolic dataflow:** Data stored as code variables (e.g., DataFrames), avoiding token overflow and ensuring precision.  
  - **Iterative reasoning:** Alternates between reasoning and code execution until the task converges.  

### ③ Validation Module
- Performs **post-execution verification** and self-correction.  
- Evaluates the reasoning trace and answer using a structured checklist.  
- If validation fails, provides **diagnostic feedback** and re-triggers execution.  
- Output includes:
  - `VALIDATION_STATUS`
  - `CONFIDENCE_SCORE`
  - `IMPROVEMENT_FEEDBACK`  

---

## 3. SheetBench Benchmark
To test complex real-world scenarios, the authors introduce **SheetBench** — a benchmark of **69 diverse spreadsheet tasks** across four categories:

1. Complex tables  
2. Multi-table layouts  
3. Large sheets  
4. Editing tasks  

It is compiled from 11 datasets, including HiTab, RealHiTBench, SheetAgent, and SheetCopilot, and focuses on both **QA** and **spreadsheet manipulation**.

---

## 4. Experimental Results
Compared against leading models and agents (GPT-4.1, o4-mini, Qwen-3, DeepSeek-R1, StructGPT, SheetAgent, BizChat), SheetBrain achieves **state-of-the-art performance**.

| Benchmark | Accuracy Improvement |
|------------|----------------------|
| MultiHiertt | +9.1% vs GPT-4.1 |
| RealHiTBench | +8.3% overall |
| SpreadsheetBench | +15% over SheetAgent |
| SheetBench | Top score: 55/69 cases |

- **Best performance** on complex and multi-table cases.  
- Handles hierarchical structures and messy real-world layouts more effectively.

---

## 5. Ablation Studies

| Removed Component | Accuracy Drop | Key Finding |
|--------------------|---------------|--------------|
| No Understanding Module | −3.3% | Context overview crucial |
| No Validation Module | −3.3% | Prevents logical errors |
| No Code Tools (sandbox) | −14% | Symbolic execution critical |
| JSON-based tool calls | −20% | API-only approaches insufficient |

Also, **HTML encoding with row/colspan metadata** was found most effective for maintaining sheet structure.

---

## 6. Key Insights
- **Symbolic computation** (code execution) scales to large spreadsheets and avoids context limits.  
- **Neural reasoning** is better for small, hierarchical sheets that fit in context.  
- Combining both — the **neuro-symbolic hybrid** — yields the strongest performance.  
- The **validation step** ensures global correctness, avoiding typical LLM issues like double-counting.

---

## 7. Contributions
1. **SheetBrain:** A neuro-symbolic spreadsheet agent with understanding, execution, and validation.  
2. **SheetBench:** A benchmark for evaluating reasoning and manipulation on complex spreadsheets.  
3. **Empirical success:** Outperforms both open-source and proprietary spreadsheet agents across all benchmarks.

---

## 8. Conclusion
SheetBrain represents a major advance in spreadsheet AI, merging symbolic computation with neural reasoning to achieve reliable, scalable performance.  
It provides:
- Strong global understanding of sheet structure,  
- Accurate code-driven reasoning, and  
- Iterative self-validation for error correction.  

This neuro-symbolic approach paves the way for **intelligent, enterprise-level spreadsheet automation** in the next generation of AI office assistants.
