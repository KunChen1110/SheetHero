# SheetHero

<p align="center">
  <img src="assets/README/logo.png" alt="SheetHero Logo" width="400"/>
</p>

<p align="center">
  <strong>Natural Language Processing Interface for Automated Excel Data Manipulation</strong><br/>
  <em>COMP2002 Group Project — Team 29</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/React-20232A?style=flat-square&logo=react&logoColor=61DAFB" alt="React"/>
  <img src="https://img.shields.io/badge/Node.js-339933?style=flat-square&logo=nodedotjs&logoColor=white" alt="Node.js"/>
  <img src="https://img.shields.io/badge/TypeScript-3178C6?style=flat-square&logo=typescript&logoColor=white" alt="TypeScript"/>
  <img src="https://img.shields.io/badge/Tailwind_CSS-06B6D4?style=flat-square&logo=tailwindcss&logoColor=white" alt="Tailwind CSS"/>
</p>

---

## Overview

SheetHero is a desktop application that enables users to perform complex spreadsheet operations through natural language instructions. The system combines a Large Language Model (LLM) with schema-grounded helpers, QA clarification, preflight checks, and deterministic validation so that spreadsheet tasks can be completed without users writing Python or Excel formulas.

The current pipeline supports multi-file joins, grouped summaries, dependency scheduling, QA-assisted data cleaning, and statistical analysis such as full-dataset Pearson correlation reports.

---

## Features

| Feature                    | Description                                                                                                             |
| -------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| **File Ingestion**         | Upload `.xlsx`, `.xlsm`, `.xltx`, `.xltm`, and `.csv` files via the native file picker                                  |
| **Multi-file Workflows**   | Join, merge, aggregate, schedule, and analyse one or more spreadsheet files using natural language                       |
| **Interactive QA**         | Detect data issues such as missing values or implausible numeric values and ask the user how to resolve them             |
| **Helper-first Execution** | Use schema-grounded helper functions and preflight guardrails to reduce LLM drift and incorrect spreadsheet operations   |
| **Statistical Analysis**   | Compute regression and correlation outputs using full-table reads, pairwise missing-value handling, and encoded features |
| **Stop Thinking**          | Interrupt an active frontend request and clear the current waiting state from the UI                                    |
| **Execution Logging**      | Save structured Markdown traces under `artifacts/loggers/` for debugging and auditability                               |

---

## Preview

### File Upload

> Users may add files via manual selection. An optional custom export directory may be specified for all generated outputs.

<p align="center">
  <img src="assets/README/preview_file_upload.png" alt="Upload interface, file picker with configurable output directory" width="300"/>
  <br/><em>Figure 1 — File upload and export directory configuration</em>
</p>

---

### Model Configuration

> Before invoking the agent, users supply an OpenAI-compatible API key and optionally override the base URL, select a model deployment, and set a maximum turn limit to bound execution.

<p align="center">
  <img src="assets/README/preview_settings.png" alt="Configuration panel showing API key, model deployment, max turns, and base URL fields" width="300"/>
  <br/><em>Figure 2 — Model configuration panel</em>
</p>

---

### Natural Language Prompting

> Users submit a plain-language instruction describing the desired transformation or analysis. SheetHero interprets the request, executes the appropriate operations, and surfaces the output file alongside a short result summary.

<p align="center">
  <img src="assets/README/preview_main.png" alt="Prompt interface showing query input, agent execution, and output/log access" width="800"/>
  <br/><em>Figure 3 — Prompt submission and agent execution</em>
</p>

---

### Interactive QA

> When the input data contains an issue that is material to the task, SheetHero asks a focused clarification question with a context preview and structured controls. The user's answer is converted into a cleaning action before execution continues.

Typical QA examples include:

- missing numeric values in a column used by the requested task
- implausible numeric values such as a negative task duration
- row-level repair decisions such as filling a corrected value, skipping a row, or keeping data as-is

---

### Execution Log

> Each run writes structured Markdown logs to `artifacts/loggers/`. SheetHero logs record workbook context, stage transitions, QA decisions, generated code, preflight feedback, execution output, validation results, and final summaries. Separate LLM input dumps may also be written for prompt debugging.

<p align="center">
  <img src="assets/README/preview_log.png" alt="Sample execution log showing agent reasoning steps and tool invocations" width="680"/>
  <br/><em>Figure 4 — Auto-generated execution log</em>
</p>

---

## Installation

### Prerequisites

- Python 3.11 or later
- Node.js 18 or later
- npm
- An OpenAI-compatible API key
- Optional for offline mode: a local OpenAI-compatible server such as Ollama

### Clone the Repository

```bash
git clone --branch main https://projects.cs.nott.ac.uk/comp2002/2025-2026/team29_project.git
cd team29_project
```

### First-time Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cd frontend
npm install
cd ..
```

On Windows, activate the virtual environment with:

```batch
venv\Scripts\activate
```

---

## Running the Application

### Full Desktop Application

From the repository root:

```bash
python main.py
```

This starts:

- FastAPI backend on port `8000`
- Vite frontend dev server
- Electron desktop window

### Frontend Development Mode

For frontend-only debugging, run the frontend from the `frontend/` directory:

```bash
cd frontend
npm run dev:frontend
```

For the full concurrent frontend/backend/Electron development workflow:

```bash
cd frontend
npm run dev
```

### Backend CLI / Benchmark Mode

For command-line debugging and benchmark runs:

```bash
python -m backend.main
```

Useful CLI commands include:

```text
!llm --show
!llm --switch--offline qwen3:8b
!dataset --index 6
!benchmark dev --index 6
!judge dev --index 6
```

---

## Configuration Reference

| Parameter          | Required | Description                                                                 |
| ------------------ | -------- | --------------------------------------------------------------------------- |
| `API Key`          | Yes      | OpenAI-compatible API key for hosted model access                           |
| `Base URL`         | No       | Leave blank for OpenAI; set to a custom endpoint such as Ollama for offline |
| `Model Deployment` | Yes      | Target model identifier, e.g. `gpt-4o-mini` or `qwen3:8b`                   |
| `Max Turns`        | Yes      | Maximum number of execution iterations per request                          |
| `Output Directory` | Yes      | Directory where generated spreadsheets are written; defaults to Documents   |
| `Output Mode`      | No       | `file` writes an Excel workbook; `text` returns a chat preview when enabled |

### Online Mode

Leave `Base URL` blank and provide an OpenAI API key.

### Offline Mode

Start a local model server first, then set `Base URL` to the local OpenAI-compatible endpoint:

```bash
ollama run qwen3:8b
```

Example base URL:

```text
http://localhost:11434/v1
```

---

## Outputs and Logs

| Artifact | Location | Notes |
| -------- | -------- | ----- |
| Generated workbook | Configured output directory, usually the user's Documents folder | One output workbook per file-mode run |
| SheetHero run log | `artifacts/loggers/sheethero_*.md` | Main stage-by-stage trace for the run |
| LLM prompt dump | `artifacts/loggers/llm_*.md` | Prompt/input debugging trace when enabled |
| CLI benchmark output | `artifacts/output/` | Used by backend CLI benchmark runs |

---

## Supported File Formats

| Extension | Format                       |
| --------- | ---------------------------- |
| `.xlsx`   | Excel Workbook               |
| `.xlsm`   | Excel Macro-Enabled Workbook |
| `.xltx`   | Excel Template               |
| `.xltm`   | Excel Macro-Enabled Template |
| `.csv`    | Comma-Separated Values       |

---

## Changelog

A full changelog of documented modifications is available in [`docs/Changelog.md`](docs/Changelog.md).
