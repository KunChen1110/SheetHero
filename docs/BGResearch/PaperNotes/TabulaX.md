# TabulaX: Leveraging Large Language Models for Multi-Class Table Transformations

Here is a complete explanation of the research paper "TabulaX: Leveraging Large Language Models for Multi-Class Table Transformations."

---

## Overview of the Paper

This paper introduces **TabulaX**, a novel framework that uses Large Language Models (LLMs) to automate and interpret complex data transformations between tables. The primary goal is to address the significant challenge of integrating tabular data from diverse sources, which often suffers from inconsistent formatting and representation.

Unlike existing methods that are often limited to specific transformation types (like string manipulation) or lack interpretability, TabulaX is designed to handle a wide variety of transformations and generate human-readable functions that explain *how* the transformation is performed.

## The Core Problem

Data analysts and scientists frequently need to combine tables from different sources. This task is difficult because the columns used for joining (linking) the tables may represent the same information but in completely different formats.

The paper highlights three key types of mismatches:

1.  **String-Based:** A "Full Name" column (e.g., "Nadia Ralph Allen") needs to be transformed into a "Username" format (e.g., "n.r.allen").
2.  **Numerical:** A "Weight in Pounds" column (e.g., 51.5) needs to be converted to a "Weight in Kg" column (e.g., 23.4).
3.  **General (Knowledge-Based):** A "Company" name (e.g., "Microsoft") needs to be mapped to its "CEO" (e.g., "Satya Nadella"), which requires external knowledge not present in the table.

Existing state-of-the-art (SOTA) models struggle with these diverse types, often failing on numerical and knowledge-based tasks, or producing "black box" outputs that cannot be verified or trusted.

## The TabulaX Framework

TabulaX tackles this problem with a multi-stage architecture that first classifies the problem and then applies a specialized solution.

### 1. The Classifier
The framework's first component is an LLM-based **Classifier**. It analyzes a few examples of source-to-target mappings (e.g., `("Nadia Ralph Allen" -> "n.r.allen")`, `(51.5 -> 23.4)`) and assigns the transformation task to one of four distinct classes:

* **String-based:** Transformations that can be solved using string manipulation functions like `split`, `substring`, or `concatenation`.
* **Numerical:** Transformations where the source and target values are rational numbers with an underlying mathematical relationship.
* **Algorithmic:** Transformations that require a deterministic algorithm beyond simple string/numeric functions, such as converting Gregorian to Hijri dates or Unicode to ASCII.
* **General:** Transformations that require external, real-world knowledge (like mapping companies to CEOs or airport codes to countries).

### 2. The Function Generator
Once classified, the task is routed to a specific module designed to generate an **interpretable transformation function**.

* **For Numerical Transformations:** TabulaX *avoids* using LLMs for mathematical reasoning, as they are known to be unreliable in this area. Instead, it uses a **Numeric Function Fitting** component that applies curve-fitting algorithms to find the best mathematical function (e.g., Linear: $f(x) = ax+b$, Polynomial, etc.) that matches the examples.
* **For String-Based Transformations:** The framework leverages the LLM's strong code-generation capabilities. It prompts the LLM to write a **Python function** that takes the source string as input and produces the target string.
* **For Algorithmic Transformations:** This module uses **Chain-of-Thought (CoT) prompting** to help the LLM "think" step-by-step. It first prompts the LLM to identify the relationship (e.g., "Gregorian date to Jalali date") and then uses that relationship to generate the specific Python code to perform the conversion.
* **For General Transformations:** This is the most complex class, also using a CoT approach.
    1.  It first asks the LLM to detect the column types (e.g., "Airport Code to Country").
    2.  It then leverages the LLM's vast pre-trained knowledge to act as a **lookup table**, generating a function that queries the LLM itself to find the corresponding target value for each source value.

## Experiments and Results

TabulaX was evaluated against SOTA baselines (like DTT, GXJoin, and AFJ) on four real-world datasets: **WT** (Web Tables), **SS** (Spreadsheet), **TT** (Table Transformation), and **KBWT** (Knowledge Base Web Tables).

* **Superior Accuracy:** TabulaX achieved higher or comparable F1-scores across all datasets.
* **Versatility:** The performance gap was most significant on the complex **TT** and **KBWT** datasets, which contain a mix of numeric, algorithmic, and general transformations that other models cannot handle. For instance, on KBWT, TabulaX achieved an F1-score of **0.567**, while the next-best baseline (DTT) scored only **0.254**.
* **Interpretability:** Unlike "black-box" models like DTT, TabulaX generates explicit code or formulas, which is a major advantage for transparency and user trust.
* **Impact of Matching:** The paper also shows that for downstream tasks like table joins, using an "edit-distance-based matching" (which allows for minor typos or variations) significantly boosts performance compared to requiring an "exact match".

## Conclusion

The paper presents TabulaX as a powerful and versatile framework that significantly advances automated data transformation. By intelligently classifying tasks and applying specialized, LLM-based methods (while avoiding LLMs for tasks they are bad at, like math), it successfully handles a much broader range of transformations than previous methods and produces human-interpretable results.