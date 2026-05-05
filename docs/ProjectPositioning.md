# Project Positioning

## 1. Purpose

SheetHero is positioned as a natural-language spreadsheet assistant for structured spreadsheet workflows. The goal is not to build a fully general office automation agent. The project focuses on the narrower but more defensible problem of helping users process one or more spreadsheet files, detect relevant data issues, ask for clarification when needed, and produce a validated spreadsheet output or concise text result.

This positioning follows from the original project brief:

- accept one or more spreadsheet files
- accept a natural-language user request
- convert the request into spreadsheet operations
- identify issues in the data
- ask the user for clarification when the request or data is ambiguous
- tolerate small formatting or spelling imperfections
- remain usable when columns are reordered or schemas vary slightly

The final system therefore prioritises spreadsheet workflows where the operation can be grounded in table schemas, helper functions, and validation checks.

## 2. Why Scope Control Matters

An LLM can attempt many spreadsheet tasks, but attempting every possible task is not the same as building a reliable system. During development, unrestricted prompt-based execution produced several recurring problems:

- the model sometimes ignored available helper functions
- the model invented columns, rows, or intermediate assumptions
- simple tasks could become slow because the model explored unnecessary code paths
- local/offline models were more sensitive to long or ambiguous prompts
- validation was difficult when the expected output structure was not well defined

For this reason, the project deliberately moved away from an open-ended "LLM writes whatever code it wants" design. The current system is instead designed around covered spreadsheet skills, helper functions, structured QA, preflight checks, sandbox execution, and validation.

This is the key product and engineering trade-off:

> SheetHero should be reliable on important covered spreadsheet workflows rather than superficially flexible on every possible spreadsheet request.

## 3. Target Task Scope

The system is intended to support spreadsheet tasks that can be described as one or more structured operations over tabular data.

Primary target workflows include:

- merging or joining related tables
- aggregating, ranking, and summarising grouped records
- filling or repairing values using reference tables
- building dependency or schedule outputs
- allocating or matching records under simple constraints
- computing correlation, regression, or descriptive statistical reports
- creating formatted output workbooks with highlighted rows or summary sheets

These workflows were selected because they are common in spreadsheet use, demonstrate real value beyond a calculator-style demo, and can be supported through reusable skills and helpers rather than one-off task patches.

## 4. Target Data Issues

SheetHero does not attempt to solve every possible data-quality problem. It focuses on issues that are common, explainable to a user, and actionable before spreadsheet execution.

The main supported data issues are:

- missing values in columns required by the requested task
- implausible numeric values, such as negative durations or impossible quantities
- duplicate or repeated records when they affect the requested result
- inconsistent row-level values that can be repaired with a user decision
- schema variation, such as reordered columns or slightly different header names
- simple formatting inconsistencies that can be handled during helper-based processing

The QA system is designed for issues where the correct repair is a user or domain decision. For example, if a required spending value is missing, SheetHero should ask whether to fill a value, skip the row, or apply a custom instruction. It should not silently guess a business decision when the input data does not justify one.

## 5. Non-Goals

The system should not be presented as:

- a guaranteed solver for arbitrary spreadsheet tasks
- a full data-cleaning platform for every possible data-quality issue
- a replacement for domain experts in ambiguous business decisions
- an unrestricted Python automation assistant
- a system that never requires additional skill or helper support

Some problems are intentionally outside the current scope:

- deep semantic entity resolution, such as reliably deciding whether "Smith, John" and "John Smit" are the same person
- complex fuzzy matching where no reference table or rule is available
- open-ended chart design or dashboard generation
- arbitrary multi-step business analysis with unclear output requirements
- tasks requiring external web data or private domain knowledge not present in the workbook

These are not impossible future extensions, but they are not the most defensible target for the current project.

## 6. Design Implications

The current architecture follows directly from the scoped positioning.

### Skill + Helper Execution

Requests are routed to spreadsheet skills such as merge, aggregate, schedule, scan, or statistical analysis. Each skill contributes helper metadata, strategy guidance, runtime planning, and preflight expectations. This reduces the chance that the LLM solves a covered task in an unsupported way.

### Schema-Grounded Runtime Plans

The system inspects workbook headers and table structure before execution. Runtime plans ground generated code in observed schemas rather than allowing the model to rely only on the user's wording.

### Interactive QA

When a data issue is material to the requested task, the system asks a focused clarification question. The answer is converted into a cleaning action before execution continues.

### Sandboxed Execution and Validation

Generated code runs inside a restricted spreadsheet namespace. Preflight checks, output contracts, and validation stages catch unsupported operations, incomplete outputs, and common failure modes before the final response is returned.

## 7. Demonstration and Evaluation Strategy

The project demonstration should focus on tasks that show the system's intended strengths:

- multi-file spreadsheet workflows rather than single-cell arithmetic
- clear skill routing and helper use
- visible QA clarification for a real data issue
- successful generation of an output workbook
- logs that show stage-by-stage execution and validation

The best demonstrations are not necessarily the largest or most open-ended tasks. They are tasks where the input problem looks realistic, the user interaction is understandable, and the final result can be checked.

This is why the final demo set should favour representative task families such as:

- table merge and enrichment
- grouped summary and highlighting
- scheduling or dependency ordering
- large statistical or correlation-style output
- QA-assisted repair of a meaningful data issue

## 8. Current Claim

The current system is best described as:

> a skill-guided spreadsheet agent with helper-based execution, interactive QA, sandboxed code generation, and validation.

This claim is stronger and more accurate than saying the system is a general spreadsheet agent. It reflects what the implementation actually optimises for: reliable behaviour on covered spreadsheet workflows, with clear mechanisms for handling ambiguity and data issues.

## 9. Future Extension

Future work should extend the system by adding new skills, helpers, and validation contracts rather than by making prompts more open-ended. Good extension candidates include:

- stronger fuzzy matching with explicit confidence and user confirmation
- richer chart and dashboard generation
- more data-cleaning issue types
- broader statistical modelling helpers
- improved benchmark coverage for QA decisions

The core principle should remain the same: new capability should be added as structured system support, not as unsupported LLM freedom.
