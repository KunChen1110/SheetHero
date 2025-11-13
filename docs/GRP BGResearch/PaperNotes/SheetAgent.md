# SheetAgent: Towards a Generalist Agent for Spreadsheet Reasoning and Manipulation

![img1](../img/SheetAgent_1.png)
![img2](../img/SheetAgent_2.png)

## 1. Background
Spreadsheets are widely used in domains such as finance, research, and business operations. However, many spreadsheet tasks are complex, multi-step, and often ambiguously defined (e.g., *“Highlight all database-related books with sales greater than 40”*).  
Previous systems like **SheetCopilot** can only handle simple, one-step operations, lacking reasoning ability and multi-sheet understanding.

### Key Challenges
1. **Dynamic Spreadsheet Changes** – feeding the entire sheet repeatedly into LLMs is inefficient.  
2. **Limited Table Understanding** – LLMs are trained mainly on natural language.  
3. **Lack of Realistic Benchmarks** – existing datasets are too simple and don’t reflect real-world spreadsheet challenges.

---

## 2. SheetRM Benchmark
To address these gaps, the authors created **SheetRM (Spreadsheet Reasoning and Manipulation Benchmark)**.

### Features
- **Multi-category tasks** – 5 main types, 36 subtypes (e.g., chart design, format adjustment, value processing).  
- **Reasoning-dependent manipulation** – tasks require multi-step logic.  
- **Long-horizon tasks** – each task includes multiple subtasks (average 5, up to 10).  
- **Automatic evaluation** – a checklist-based system evaluates each operation step-by-step.

### Dataset Stats
| Metric | Value |
|---------|-------|
| Sheets | 137 |
| Tasks | 317 |
| Subtasks | 1,625 |
| Avg. Rows per File | 300 |
| Avg. Columns per File | 26 |

---

## 3. SheetAgent Framework
**SheetAgent** is an autonomous LLM-based agent that performs both reasoning and manipulation on spreadsheets.  
It consists of **three collaborative modules:**

### 1. Planner
- Generates **Python code** (via `openpyxl`) to perform spreadsheet operations.  
- Executes code in a **sandbox**, reflecting and correcting errors.  
- Code-centric design reduces hallucinations compared to API-based approaches.

### 2. Informer
- Generates **SQL queries** to extract task-specific data views.  
- Helps the Planner understand key data without loading the entire spreadsheet.  
- Handles ambiguous instructions and reasoning challenges.

### 3. Retriever
- When errors occur, retrieves similar **code snippets** from a large code repository (via **Milvus vector DB**) to assist corrections.  

---

## 4. Experimental Results

### Datasets Used
- **SheetRM** (new benchmark for reasoning + manipulation)  
- **SheetCopilot Benchmark (SCB)** (manipulation only)  
- **WTQ**, **FeTaQA**, **TabFact** (table reasoning tasks)

### Highlights
| Dataset | Capability | Improvement |
|----------|-------------|-------------|
| SheetRM | Reasoning + Manipulation | +20–40% Pass@1 |
| SCB | Manipulation | +16.8% (vs. SheetCopilot, GPT-3.5) |
| WTQ / TabFact / FeTaQA | Reasoning | Outperforms prior LLMs |

SheetAgent also works across various LLMs (GPT-4, GPT-4o, Claude, Llama 3, Qwen, etc.) and remains consistently superior.

---

## 5. Ablation Study

| Removed Component | Effect |
|--------------------|--------|
| **Informer** | Pass@1 ↓ 18% (reasoning accuracy drops) |
| **Retriever** | Exec@1 ↓ 8% (less stable code) |
| **Both removed** | Largest drop – confirms both are essential |

Also, **JSON** is the best data format for table representation compared to HTML or Markdown.

---

## 6. Key Contributions
1. **SheetRM:** First benchmark combining realistic multi-step reasoning with spreadsheet manipulation.  
2. **SheetAgent:** LLM-based generalist agent integrating planning, reasoning, and self-correction.  
3. **Superior Performance:** Outperforms all baselines by large margins (20–40% improvement).

---

## 7. Future Work
- Extend SheetAgent with **visual (multimodal)** spreadsheet understanding.  
- Reduce **token usage** and improve **Python library coverage**.  
- Explore **AI-powered office automation** with reasoning and collaboration.

---

### Summary
> **SheetAgent** is a generalist spreadsheet agent that can reason, plan, and manipulate complex spreadsheets autonomously.  
> The accompanying **SheetRM** benchmark establishes a new standard for evaluating LLM agents in real-world spreadsheet scenarios.
