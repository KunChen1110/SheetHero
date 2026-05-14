# Software Design

## 1. Design Overview

SheetHero is designed as a layered spreadsheet assistant rather than a single prompt-to-code script. The frontend collects files, configuration, user prompts, and clarification answers. The service layer manages user sessions and dialogue memory. The backend agent then drives each request through a fixed spreadsheet pipeline:

`Understanding -> Diagnose -> QA -> Cleaning -> Execution -> Validation -> Final Response`

This design keeps user interaction, task orchestration, model prompting, spreadsheet execution, and validation separate enough to be tested and improved independently.

## 2. Main Layers

### Frontend Layer

The frontend is an Electron + React application. Its main responsibilities are:

- file selection and output-directory configuration
- API key, model, base URL, and turn-limit configuration
- prompt entry and response rendering
- structured clarification controls for QA questions
- stop-thinking interruption for active requests
- access to generated output files and logs

### Service Layer

The service layer exposes the frontend API and owns active SheetHero sessions. It keeps dialogue state, routes normal turns and clarification answers, and repeatedly steps the backend agent until the request reaches a terminal state.

### Orchestration Layer

The backend agent is implemented as a multi-stage pipeline. Each stage has a specific responsibility:

- `Understanding`: identify relevant files, sheets, columns, and expected operations
- `Diagnose`: detect data issues that may affect the requested task
- `QA`: ask the user focused clarification questions when a decision is required
- `Cleaning`: convert QA answers into deterministic cleaning actions
- `Execution`: generate and run spreadsheet code using skills, helpers, and sandbox tools
- `Validation`: check whether the output satisfies the request and output contract
- `Final Response`: return a concise user-facing result

## 3. Skill + Helper Execution

The execution subsystem is organised around spreadsheet skills rather than individual benchmark tasks. A skill describes a reusable class of spreadsheet operation, such as merge, aggregate, schedule, scan, or statistical analysis.

For each detected skill, the system can inject:

- strategy guidance
- helper-function descriptions
- helper metadata
- schema-grounded runtime plans
- preflight checks
- output contract expectations

This reduces unsupported LLM behaviour. The LLM is still used for flexible reasoning and code generation, but the surrounding system guides it toward known spreadsheet tools and validates the result.

## 4. Data Quality and QA

Data issues are handled before execution when they are material to the user's request. The system focuses on explainable and actionable issues such as missing values, implausible numeric values, duplicate rows, and simple schema inconsistencies.

When the correct repair is a user decision, SheetHero asks a focused QA question with structured controls. The answer is then converted into a cleaning policy before execution continues.

## 5. Execution Safety

Generated code runs inside a restricted spreadsheet namespace. The execution stage applies preflight checks before sandbox execution and validation checks afterwards. This protects against common LLM failure modes such as invented columns, placeholder paths, incomplete outputs, unsupported imports, or code that ignores the required helper contract.

## 6. Deployment Modes

SheetHero supports both online and offline model access through OpenAI-compatible APIs:

- online mode uses a hosted model endpoint
- offline mode uses a local OpenAI-compatible server such as Ollama

The pipeline remains the same across both modes. Only the model endpoint and prompt profile change.

## 7. Historical UI Wireframes

The following wireframes were created early in the project to explore the user interface layout. They are retained as design history rather than as the final UI specification.

### Wireframe Design 1

This design explored a simple spreadsheet assistant layout with file upload and prompt input.

![WireframeDesign1](/assets/WireframeDesign1.PNG)

### Wireframe Design 2

This design explored a denser layout with reduced whitespace and a larger prompt area.

![WireframeDesign2](/assets/WireframeDesign2.PNG)
