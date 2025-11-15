# SheetBrain: A Neuro-Symbolic Agent for Accurate Reasoning over Complex and Large Spreadsheets

![img1](../../assets/SheetBrain_1.png)

## 1. Motivation
Large language models (LLMs) such as GPT-4 excel in text-based reasoning but struggle with **complex Excel-like spreadsheets** that have multi-table layouts, merged cells, and irregular structures.  
Traditional spreadsheet agents (e.g., SheetAgent, SheetCopilot) fail on these because they:
1. Lack deep spreadsheet structural understanding.  
2. Perform blind, token-limited reasoning.  
3. Have no self-correction or validation mechanisms.  

#### Key Problems Identified

- **Blind reasoning**: Methods don't analyze spreadsheet structure beforehand, leading to inefficient execution
- **Context overflow**: Neural approaches that embed raw data into LLM context hit token limits on large sheets
- **Local perspective** traps: Multi-step reasoning gets stuck without reflection mechanisms
- **Hierarchical structure blindness**: Agents fail to recognize relationships like "of which" subcategories, causing double-counting errors

---

## 2. The SheetBrain Framework
SheetBrain introduces a **neuro-symbolic, three-stage pipeline** combining neural reasoning with symbolic code execution and validation.

### ① Understanding Module
- Builds a **global, query-aware overview** of the spreadsheet.  
- Produces:
  - **Sheet Summary:** Describes workbook purpose, sheet relationships, and layout.  
  - **Problem Insights:** Identifies relevant data regions and suggests execution strategies.  
- Uses **dynamic token budgeting** and **enhanced Markdown serialization** (includes cell positions, merged cell info) to preserve spatial layout efficiently.

**Key innovation :** Recognizes structural patterns (e.g., "each user's data occupies a distinct multi-row block") to guide execution strategy, enabling block-level iteration instead of inefficient row-by-row processing.

### ② Execution Module
- Runs within a **Python sandbox** using `pandas` and a custom **Excel toolkit** (`inspector`, `search`, etc.).  
- Combines **neural planning** and **symbolic computation** for reasoning and manipulation.  
- Features:
  - **Symbolic dataflow:** Data stored as code variables (e.g., DataFrames), avoiding token overflow and ensuring precision.  
  - **Iterative reasoning:** Alternates between reasoning and code execution until the task converges.  


#### Excel-Specific Tooling Protocol
Custom Python functions designed from analyzing common failure patterns:
- `inspector(range_ref, sheet_name)`: Extract cell values with position info
- `inspector_attribute(range_ref, attributes, sheet_name)`: Get cell formatting (color, font, formulas)
- `search(value, sheet_name, case_sensitive, search_type)`: Robust search with partial/whitespace-tolerant matching
- `get_sheet_as_dataframe(sheet_name, header_row, max_rows)`: Convert sheets to pandas DataFrames

#### Why symbolic vs. neural dataflow?
- **Neural approach**: Returns thousands of raw entries into LLM context → token overflow
- **Symbolic approach**: Stores data in variables, performs computations in Python → scales to 100,000+ row tables

### ③ Validation Module
- Performs **post-execution verification** and self-correction.  
- Evaluates the reasoning trace and answer using a structured checklist.  
- If validation fails, provides **diagnostic feedback** and re-triggers execution.  
- Output includes:
  - `VALIDATION_STATUS`: PASSED/FAILED
  - `CONFIDENCE_SCORE`: 0.0-1.0
  - `IMPROVEMENT_FEEDBACK`  : Specific suggestions for correction

#### Validation Checklist:
- Data handling accuracy (extraction, transformation)
- Answer completeness and format adherence
- Alignment with user query
- Detection of hierarchical data issues (e.g., double-counting parent/child rows)

---

## 3. SheetBench Benchmark
To test complex real-world scenarios, the authors introduce **SheetBench** — a benchmark of **69 diverse spreadsheet tasks** across four categories:

1. **Complex tables**(21 cases): Multi-level headers, nested structures
2. **Multi-table layouts**(20 cases): Multiple interconnected tables in one sheet
3. **Large sheets**(20 cases): High row/column counts testing scalability
4. **Editing tasks**(8 cases): Formula propagation, layout modifications

It is compiled from 11 datasets, including HiTab, RealHiTBench, SheetAgent, and SheetCopilot, and focuses on both **QA** and **spreadsheet manipulation**.

**Quality assurance**: Human annotators corrected queries and sheet issues to ensure high-quality, reliable test cases.

---

## 4. Experimental Results
Compared against leading models and agents (GPT-4.1, o4-mini, Qwen-3, DeepSeek-R1, StructGPT, SheetAgent, BizChat), SheetBrain achieves **state-of-the-art performance**.

### Overall Performance

| Benchmark | Accuracy Improvement | SheetBrain Score |
|------------|----------------------|------------------|
| MultiHiertt | +9.1% vs GPT-4.1 | 62.6% |
| RealHiTBench (overall) | +8.3% vs GPT-4.1 | 78.3% |
| RealHiTBench (fact-checking) | +10.5% vs GPT-4.1 | 85.5% |
| SpreadsheetBench (cell-level) | +21.1% over SheetAgent | 35.4% |
| SpreadsheetBench (sheet-level) | +4.1% over SheetAgent | 37.8% |
| SheetBench | Best overall | **55/69 (80.3%)** |

### SheetBench Detailed Results

| Model | Complex | Multi-table | Large | Edit | Total |
|-------|---------|-------------|-------|------|-------|
| **SheetBrain** | **20/21** | **18/20** | **11/20** | **6/8** | **55/69** |
| BizChat Analyst | 18/21 | 14/20 | 9/20 | 6/8 | 47/69 |
| o3 | 19/21 | 15/20 | 4/20 | N/A | 38/69 |
| GPT-4.1 | 16/21 | 17/20 | 1/20 | N/A | 34/69 |
| SheetAgent | 11/21 | 10/20 | 10/20 | 4/8 | 35/69 |
| StructGPT | 12/21 | 1/20 | 0/20 | N/A | 13/69 |

#### Key findings:
- **Best performance** on complex and multi-table cases.
- Handles hierarchical structures and messy real-world layouts more effectively.
- Particularly strong on fact-checking tasks requiring cross-referencing
- SpreadsheetBench manipulation tasks show significant gains at cell-level precision

---

## 5. Ablation Studies

### Component Removal Impact

| Removed Component | RealHiTBench | SheetBench | Key Finding |
|--------------------|--------------|------------|--------------|
| **Full method** | 78.3% | 80.3% | Baseline |
| No Understanding Module | 75.0% (−3.3%) | 77.0% (−3.3%) | Context overview crucial |
| No Validation Module | 76.7% (−1.6%) | 77.0% (−3.3%) | Prevents logical errors |
| No Understanding + No Validation | 73.3% (−5.0%) | 73.8% (−6.5%) | Components are complementary |

### Execution Module Tools (SheetBench)

| Configuration | Accuracy | Impact |
|---------------|----------|--------|
| **Full method (all tools)** | **79.1%** | Baseline |
| Without inspector tool | 77.3% (−1.8%) | Moderate impact |
| Without search tool | 73.1% (−6.0%) | Significant impact |
| Without all custom tools | 73.1% (−6.0%) | Major degradation |
| **Neural calling (JSON-based)** | **65.1% (−14.0%)** | **Critical finding** |

**Critical insight:** The stark 14% drop when replacing code sandbox with traditional JSON-based tool calling demonstrates the overwhelming advantage of symbolic computation for data-intensive spreadsheet tasks.

### Serialization Strategies

| Encoding Type | Variant | Accuracy | Notes |
|---------------|---------|----------|-------|
| **Markdown** | Pure Markdown | 63.3% | Baseline |
| | With Cell Position | 75.0% | +11.7% |
| **HTML** | Pure HTML | 59.7% | Worse than markdown |
| | MD-like + Cell Pos. | 76.3% | +1.3% over Markdown |
| | HTML + Colspan + Cell Pos. | 76.0% | Slightly lower |
| | **HTML + Colspan + Row Tag** | **76.7%** | **Best** |

**Key finding:** Cell position information is critical (+11.7% improvement). High-level structure (row tags, colspan) outperforms overly detailed positional encoding, possibly reducing noise.


---

## 6. Key Insights
### When to Use Symbolic vs. Neural Reasoning

#### Symbolic Computation Excels:
- **Large/extra-large tables** (e.g., 100,000+ rows)
- **Multi-step calculations** requiring filtering, aggregation, joins
- **Data-intensive operations** that would overflow context
- **Example:** Filter 100K rows + compute conditional average → pandas handles gracefully

#### Neural Reasoning Excels:
- **Small-to-medium tables** that fit fully in context
- **Complex hierarchical structures** with intricate headers
- **Pattern-matching scenarios** requiring holistic understanding
- **Example:** Understanding "of which" breakdown items in nested row headers

**Best practice:** Dynamic strategy selection based on table size and query complexity maximizes performance.

### Common Failure Patterns Identified

1. **Limited preview blindness:** Existing agents (ChatGPT, BizChat) only load first few rows (df.head()), missing non-standard headers and complex layouts
2. **Double-counting in hierarchies:** Agents sum both parent rows and "of which" subcategories without recognizing relationships
3. **Local focus loss:** During code execution, agents fixate on immediate outputs and ignore global context
4. **Inadequate verification:** Without validation step, logical errors propagate to final answer

### The Validation Module's Critical Role

**Case study (fishery landings):**
- **Without validator:** Summed all rows including "of which" subcategories → 261,155 tonnes (WRONG, double-counted)
- **With validator:** Detected hierarchical structure issue, re-executed excluding breakdown rows → 163,802 tonnes (CORRECT)

The validator caught the double-counting by prompting global verification against initial data structure.

---

## 7. Contributions
1. **SheetBrain:** A neuro-symbolic spreadsheet agent with understanding, execution, and validation.  
2. **SheetBench:** A benchmark for evaluating reasoning and manipulation on complex spreadsheets.  
3. **Empirical success:** Outperforms both open-source and proprietary spreadsheet agents across all benchmarks.
4. **Excel toolkit protocol:** Reusable Python functions designed from systematic failure analysis
5. **Serialization analysis:** Comprehensive study of encoding strategies for preserving spreadsheet structure
6. **Design principles:** Actionable insights for future spreadsheet agent development

---

## 8. Conclusion
SheetBrain represents a major advance in spreadsheet AI, merging symbolic computation with neural reasoning to achieve reliable, scalable performance.  
It provides:
- Strong global understanding of sheet structure,  
- Accurate code-driven reasoning, and  
- Iterative self-validation for error correction.  

This neuro-symbolic approach paves the way for **intelligent, enterprise-level spreadsheet automation** in the next generation of AI office assistants.
