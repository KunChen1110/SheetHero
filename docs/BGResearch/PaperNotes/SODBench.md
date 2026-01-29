# SODBench: A Large Language Model Approach to Documenting Spreadsheet Operations

This paper introduces a new benchmark called **SODBench** and defines a new AI task named **Spreadsheet Operations Documentation (SOD)**. The core goal is to use Large Language Models (LLMs) to automatically generate human-readable documentation from the actions performed in a spreadsheet.

---

## 1. The Core Problem

The research addresses a common problem in business, accounting, and finance where spreadsheets are heavily used.

* **Lack of Documentation:** Spreadsheets often lack systematic documentation methods.
* **Hindered Collaboration:** This makes it difficult to collaborate, automate processes, or transfer knowledge to new team members.
* **Loss of Knowledge:** When employees leave, this undocumented institutional knowledge is often lost, which can take new staff months to reconstruct.

## 2. The Proposed Solution: SOD (Spreadsheet Operations Documentation)

To solve this, the paper formalizes the SOD task, which involves generating natural language explanations *from* spreadsheet operations.

This is described as a "reverse approach". Much previous research has focused on using LLMs to generate spreadsheet code (like formulas) *from* a natural language instruction. This paper focuses on the opposite: capturing the code *behind* an operation and translating it back *into* a natural language description for documentation purposes.

## 3. The Benchmark & Methodology

The paper's main contribution is the creation of the **SODBench** dataset, which is used to test this new task.

* **Dataset (SODBench):** The benchmark consists of **111 validated spreadsheet manipulation task instances**. Each instance is a pair containing:
    1.  A snippet of **xwAPI code** (a set of atomic operations for spreadsheet manipulation).
    2.  A corresponding **natural language summary** or description of that code's actions.
* **The Experiment:** The researchers evaluated five LLMs to see how well they could perform this code-to-natural-language translation task.
* **Models Tested:** GPT-40, GPT-40-mini, LLaMA-3.3-70B, Mixtral-8x7B, and Gemma2-9B.
* **Evaluation Metrics:** Performance was measured using standard NLP metrics: BLEU, GLEU, ROUGE-L, and METEOR.
* **Prompting:** The models were evaluated using a 4-shot learning configuration (except for Mixtral-8x7B, which used 1-shot due to its limited context window).

## 4. Key Findings

The study found that using LLMs for SOD is a feasible and promising approach.

* **Top Performers:** The three best-performing models were **GPT-40-mini**, **LLaMA-3.3-70B**, and **GPT-40**.
* **No Statistical Difference at the Top:** While GPT-40-mini had the highest mean scores, the overlapping margins of error (MOE) and a pairwise two-sample t-test showed that the performance differences between these top three models were **not statistically significant**.
* **Model Size vs. Performance:** The results showed that larger model size does not guarantee better performance on this specialized task. The smaller GPT-40-mini outperformed the larger Mixtral-8x7B and Gemma2-9B models.
* **Underperformers:** Gemma2-9B performed the worst, with Mixtral-8x7B being the second-lowest. Their performance was statistically inferior to the other LLMs.

## 5. Other Contributions and Conclusion

Beyond the main benchmark, the paper also presented a **Retrieval-Augmented Generation (RAG) pipeline** as a proof of concept. This pipeline was designed to generate executable JavaScript (JS) code for spreadsheet automation by retrieving relevant API documentation to help the LLM.

In conclusion, the paper demonstrates that LLMs can capably translate spreadsheet operation code into accurate, human-readable documentation. This SOD approach is proposed as a viable step toward improving reproducibility, knowledge transfer, and collaboration for spreadsheet-heavy workflows. The authors suggest this work could be extended into a practical tool, such as a browser extension for Google Sheets or a plugin for Excel.