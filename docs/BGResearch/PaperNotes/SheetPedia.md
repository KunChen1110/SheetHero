Based on the abstract and introduction of the article, this paper primarily introduces a novel, large-scale spreadsheet corpus called **Sheetpedia**.

Here are the main contents of the article:

### 1. Core Contribution: The Sheetpedia Corpus

* **Problem Context:** Although spreadsheets are widely used, their complex structures, free-form text, and formula logic make them very difficult for AI systems to understand automatically. Existing datasets (like EUSES, Enron, Fuse) have limitations in scale, domain, or the richness of their formula content.
* **What Sheetpedia Is:** This is a large-scale corpus containing **over 290,000** (final count 290,509) diverse spreadsheet worksheets, compiled from more than 324,000 workbooks.
* **Data Sources:** The corpus data comes from multiple channels, including enterprise email archives (Enron corpus), web crawling (Fuse corpus), and a new crawl of Excel online forums (ExcelForum).
* **Features:** Unlike many datasets that only contain static web tables, Sheetpedia provides extensive coverage of real-world **formulas and semantics**.

### 2. Data Processing

To build this high-quality corpus, the authors employed a rigorous preprocessing pipeline:
* **Format Standardization:** Converting `.xls` files to the `.xlsx` format.
* **Language Filtering:** Ensuring content quality, with 78.85% of the content being in English.
* **Formula Filtering:** Selecting formulas that are syntactically valid and functionally complex.
* **Spreadsheet Deduplication:** Using MinHash and LSH (Locality-Sensitive Hashing) techniques, 48.7% of near-duplicate worksheets were eliminated, resulting in 290,509 unique sheets.

### 3. Application & Experiments: Two New Tasks

To demonstrate the corpus's utility, the authors defined two novel spreadsheet understanding tasks and fine-tuned Large Language Models (LLMs) on them:

* **Natural Language to Semantic Range (NL2SR):**
    * **Task Definition:** Mapping a user's natural language request (e.g., "What is the total sales for Q1?") to the correct cell range in the spreadsheet.
    * **Example (Fig. 2):** A user queries "Detailed Budget Situation of Cultural Festival Expenses," and the model needs to identify the relevant cells like B12, F12, B20, F20, etc.
* **Natural Language to Formula (NL2Formula):**
    * **Task Definition:** Generating a syntactically correct and semantically accurate Excel formula based on a user's natural language description.
    * **Example (Fig. 2):** A user queries "Calculate the Credit enrollment for Spring 2009," and the model needs to generate the formula `SUM(G19:G25)`.

### 4. Key Results

* **Data Generation:** The authors used a "rejection sampling" strategy, utilizing LLMs (like Gemini-Flash-2.0 and Claude-3.7-Sonnet) to automatically generate and filter high-quality training data.
* **Model Performance:** LLMs (like LLaMA-3.1-8B) fine-tuned on Sheetpedia showed **significant outperformance** over baseline methods (like GPT-40 in few-shot settings) on the two new tasks.
* **Specific Accuracy:** The fine-tuned models achieved **97.5% accuracy on the NL2SR task** and **71.7% accuracy on the NL2Formula task**.

### 5. Limitations

The authors also pointed out the limitations of their research, primarily:
* The corpus is currently **overwhelmingly English-based**.
* The data filtering and deduplication methods might **omit** some small spreadsheets or complex cross-sheet formulas.

In summary, this article releases the largest-to-date, formula-rich public spreadsheet corpus (Sheetpedia), defines two new benchmark tasks (NL2SR and NL2Formula), and demonstrates that LLMs fine-tuned on this corpus achieve significant performance gains in spreadsheet intelligence.