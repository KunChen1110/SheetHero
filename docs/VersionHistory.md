# Version History

## Overview
This document records the main backend engineering milestones of SheetHero and explains how the system evolved from an initial spreadsheet-processing prototype into a skill-based spreadsheet pipeline.

The versioning here is not intended to describe every small commit or bug fix. Instead, each version marks a meaningful architectural stage in the backend development of the project.

## Versioning Principle
- `v1.x`: early usable backend and first major structural refactor
- `v2.x`: data-quality handling and conversational pipeline integration
- `v3.x`: local/offline LLM support and execution-stage hardening
- `v4.x`: benchmark-driven diagnose improvement, skill-based generalization, local-model upgrade validation, and output-mode polish
- `v5.x`: schema-grounded execution planning, full skill system migration, and advisor pipeline formalization

## Version Summary
| Version | Date | Tag Commit | Main Theme |
| --- | --- | --- | --- |
| `v1.0` | 2025-12-11 | `6ca5c2d1` | First usable backend baseline |
| `v1.1` | 2026-01-26 | `309fc060` | Backend refactor into staged architecture |
| `v2.0` | 2026-02-16 | `abb595ec` | Diagnose, QA, cleaning, and conversational data-quality pipeline |
| `v3.0` | 2026-02-22 | `f2029e6a` | Local/offline LLM pipeline with bounded execution |
| `v3.1` | 2026-03-10 | `3d53f617` | Execution architecture hardening and deterministic short answers |
| `v4.0` | 2026-03-23 | `485d6da8` | Skill-based spreadsheet pipeline with benchmark-driven validation |
| `v4.1` | 2026-03-26 | `88da932e` | Local LLM upgraded to `qwen3:8b` with validated CLI regression |
| `v4.2` | 2026-03-27 | `pending release commit` | Text-only output mode and execution/validation modular cleanup |
| `v5.0` | 2026-04-12 | `pending release commit` | Schema-grounded execution planning, full skill system migration, and advisor pipeline formalization |

---

## v1.0
**Date:** 2025-12-11  
**Tag:** `v1.0`  
**Commit:** `6ca5c2d1`

### Stage Position
This version represents the first usable backend baseline of the project.

### Main Characteristics
- Core spreadsheet-processing workflow was already in place.
- The system could accept spreadsheet inputs and produce outputs for many benchmark-style tasks.
- A functional execution-and-validation loop existed, but the overall design was still relatively early-stage.
- Data cleaning had not yet been integrated as a mature pipeline component.

### Engineering Improvements Achieved
- Established the backend as a runnable spreadsheet agent rather than a collection of isolated scripts.
- Completed most of the core task-solving path for the early benchmark tasks.
- Provided a usable baseline for later architectural refactoring.

### Main Engineering Focus At This Stage
- Improve correctness and consistency across tasks.
- Reduce runtime overhead.
- Move beyond a mostly functional prototype toward a more maintainable architecture.

---

## v1.1
**Date:** 2026-01-26  
**Tag:** `v1.1`  
**Commit:** `309fc060`

### Stage Position
This version marks the first major backend refactor.

### Main Characteristics
- The backend was reorganized into a much clearer staged architecture.
- Core responsibilities were separated into:
  - agent coordination
  - prompt construction
  - execution
  - validation
  - environment / sandbox handling
- The `SheetHero`-based structure became much more explicit.

### Engineering Improvements Achieved
- Improved maintainability by replacing a more ad hoc structure with a staged backend pipeline.
- Made the codebase easier to extend with new stages and execution policies.
- Created a stronger foundation for later diagnose, QA, and cleaning integration.

### Main Engineering Focus At This Stage
- Turn the refactored structure into a more complete interactive pipeline.
- Add stronger handling for ambiguous or imperfect spreadsheet data.
- Improve robustness rather than only task completion.

---

## v2.0
**Date:** 2026-02-16  
**Tag:** `v2.0`  
**Commit:** `abb595ec`

### Stage Position
This version marks the transition from a mainly functional spreadsheet agent to a conversational spreadsheet pipeline with explicit data-quality handling.

### Main Characteristics
- Introduced the major data-quality path into `dev`:
  - diagnose
  - QA
  - cleaning
- Added routing and service-level orchestration around clarification flow.
- Added stream-capable interaction support for frontend/backend integration.
- Extended test coverage around understanding, execution, cleaning, and diagnose-related modules.

### Engineering Improvements Achieved
- The system could now detect data issues before execution instead of only attempting direct task solving.
- User clarification became part of the pipeline, which improved handling of ambiguity and imperfect data.
- Cleaning actions became a first-class stage rather than an afterthought.
- The backend became significantly closer to the project brief requirement of handling unclear prompts and imperfect spreadsheet inputs.

### Main Engineering Focus At This Stage
- Stabilize the newly integrated diagnose / QA / cleaning pipeline.
- Reduce complexity introduced by the new interaction flow.
- Improve consistency between clarification decisions and downstream execution.

---

## v3.0
**Date:** 2026-02-22  
**Tag:** `v3.0`  
**Commit:** `f2029e6a`

### Stage Position
This version marks the introduction of a serious local/offline LLM execution path.

### Main Characteristics
- Added local inference support for offline deployment.
- Introduced dedicated online/offline prompt handling.
- Added bounded execution guardrails for local models.
- Added contract-based output validation for offline execution.
- Strengthened runtime error routing and forbidden-pattern handling.

### Engineering Improvements Achieved
- The project no longer depended only on hosted model endpoints.
- The system became much more usable in local-model settings.
- Offline execution became safer and more recoverable through bounded repair loops.
- Output correctness was enforced more explicitly through output contracts.

### Main Engineering Focus At This Stage
- Make local-model execution less fragile.
- Reduce dead loops and malformed-code retries.
- Improve reliability under weaker model conditions.

---

## v3.1
**Date:** 2026-03-10  
**Tag:** `v3.1`  
**Commit:** `3d53f617`

### Stage Position
This version marks the hardening of the execution architecture after local/offline support was in place.

### Main Characteristics
- Refactored the execution stage into clearer internal modules.
- Added deterministic short-answer generation for final responses.
- Reduced unnecessary end-of-run latency.
- Improved separation of execution internals such as:
  - grounding
  - forbidden checks
  - repair guidance
  - output checking

### Engineering Improvements Achieved
- Improved maintainability of the execution layer.
- Reduced the size and complexity of the previous monolithic execution runtime.
- Made final responses faster and more consistent.
- Prepared the system for broader generalization work by making execution control easier to reason about.

### Main Engineering Focus At This Stage
- Further reduce dependence on unconstrained code generation.
- Improve generalization beyond benchmark-specific logic.
- Strengthen execution control using more explicit backend policies.

---

## v4.0
**Date:** 2026-03-23  
**Tag:** `v4.0`  
**Commit:** `485d6da8`

### Stage Position
This version marks the most important architectural transition in the current project: from task-oriented handling to a skill-based spreadsheet pipeline.

### Main Characteristics
- Added diagnose benchmark integration as a formal evaluation asset.
- Improved QA/diagnose alignment and made clarification more concrete and context-aware.
- Reworked the backend around centralized skills instead of scattered task-specific branching.
- Introduced deterministic execution paths for covered spreadsheet families.
- Added synthetic skill regression to validate abstract spreadsheet capabilities independently of the original benchmark tasks.

### Engineering Improvements Achieved
- Diagnose became more measurable and evidence-driven through benchmark support.
- The backend moved from task-specific patching toward reusable spreadsheet capability families.
- Helper usage became more structured and less dependent on free-form model behavior.
- Synthetic skill regression provided a stronger argument that the system was not only solving benchmark tasks, but also supporting reusable spreadsheet capability patterns.
- The project became substantially more engineering-oriented in terms of extensibility, validation, and maintainability.

### Main Engineering Focus At This Stage
- Improve generalization across spreadsheet skills.
- Reduce dependence on free-form code generation.
- Validate family-level capabilities through both benchmark-based and synthetic regression-based testing.

---

## v4.1
**Date:** 2026-03-26  
**Tag:** `v4.1`  
**Commit:** `88da932e`

### Stage Position
This version marks the first validated local-model upgrade after the skill-based architecture had already become stable.

### Main Characteristics
- Upgraded the recommended local LLM path from the previous `qwen2.5-coder:7b-instruct` workflow to `qwen3:8b`.
- Kept the backend architecture unchanged and treated the model replacement as a controlled engineering upgrade rather than a new architecture rewrite.
- Revalidated the upgraded local model against:
  - diagnose benchmark
  - skill synthetic regression
  - representative CLI tasks
- Expanded natural-language detector coverage for reference-guided completion so the upgraded local model can more reliably route prompts like “fill any missing data ... using information from file ...” into the deterministic family path.

### Engineering Improvements Achieved
- Improved the practicality of local deployment by moving to a newer near-7B model without changing the surrounding backend architecture.
- Confirmed that the upgraded model still works with the benchmark-driven diagnose/QA path.
- Confirmed that the upgraded model still works with the abstract skill-based regression layer.
- Reduced the chance that natural prompt wording falls out of the `reference_guided_completion` family and drops back to free-form model handling.

### Main Engineering Focus At This Stage
- Upgrade the local model in a controlled way instead of changing it blindly.
- Preserve benchmark and family-regression pass rates while improving the local-model baseline.
- Keep the system architecture stable and treat model replacement as a validated runtime improvement.

---

## v4.2
**Date:** 2026-03-27  
**Tag:** `v4.2`  
**Commit:** `pending release commit`

### Stage Position
This version marks the first output-mode polish release after the local-model upgrade. The main goal of this iteration is to make the backend more usable for frontend integration while continuing the execution/validation modularization work.

### Main Characteristics
- Added a real backend-controlled `text` output mode while keeping `file` mode as the default.
- Added structured response metadata so the frontend can distinguish file outputs from text-only outputs without guessing from message strings.
- Ensured deterministic text-mode families no longer save workbooks to disk before rendering text previews.
- Reorganized execution and validation into clearer submodules:
  - execution skill strategy files grouped under `stages/execution/skill/`
  - validation reorganized into `core/`, `checks/`, and `inspectors/`
- Removed several leftover facades and migration-era wrappers after the skill-based architecture became stable.

### Engineering Improvements Achieved
- The frontend can now cleanly decide whether to show a file button by reading:
  - `result_kind`
  - `has_output_file`
  - `output_path`
  - `truncated`
- Text-only mode is now appropriate for scalar answers and preview-oriented spreadsheet results without forcing the user to open a generated workbook.
- The backend no longer relies on “always generate file, then hide it later” for covered deterministic text-mode paths.
- Execution and validation are easier to maintain because their main runtime files now act as orchestration layers rather than large mixed-logic modules.

### Main Engineering Focus At This Stage
- Improve product-facing output behavior without breaking the file-first spreadsheet workflow.
- Make frontend/backend integration cleaner through explicit result typing.
- Continue replacing transitional monolithic runtime logic with clearer execution and validation submodules.

---

## v5.0
**Date:** 2026-04-12  
**Tag:** `v5.0`  
**Commit:** `pending release commit`

### Stage Position
This version marks a major architectural break from v4: the legacy task-family routing system is completely removed and replaced by a schema-grounded execution planning layer built on top of the skill system.

### Main Characteristics
- Replaced the family-based routing module (`task_families.py`, `task_skills.py`, `execution/family/`) with a composable skill system (`skills/` package) built on `SkillSpec`, `HelperSpec`, keyword-based detectors, and rich helper metadata.
- Introduced `RuntimeExecutionPlan` — a schema-grounded execution plan inferred from observed workbook headers and detected skills, injected into LLM prompts to prevent hallucinated column references.
- Migrated execution advisors from `execution/family/` to `execution/skill/`: `ExecutionSkillPromptAdvisor`, `ExecutionSkillPreflightAdvisor`, `ExecutionGenericPreflightAdvisor`, `ExecutionQuestionInferenceAdvisor`.
- Added structured cleaning policy plans: QA decisions are now converted into deterministic actions and LLM-driven policy rules rather than free-form instructions.
- Simplified prompt templates for both offline and online profiles by removing hardcoded family-specific prompt fragments and replacing them with dynamic skill-injected guidance.
- Expanded helper function library in `SpreadsheetNamespace` with `summarize_numeric_column`, `add_rank_column`, `build_dependency_schedule`, and improved `concat_tables_with_same_headers`.
- Deleted ~5,700 lines of legacy code across `task_skills.py`, `execution/family/`, and `run_family_synthetic_regression.py`.
- Added ~3,200 lines of new code across `skills/` models, detectors, registry, strategies, helper metadata, prompt builders, runtime plan, and new test suites.
- Updated Software Manual Plan to v2 reflecting all architectural changes.

### Engineering Improvements Achieved
- Skill detection is now purely deterministic (keyword-based, no embeddings, no LLM call) and extensible: adding a new task type requires only a new `SkillSpec` entry, helper functions, and metadata.
- Runtime execution plans ground column references in actual observed headers, substantially reducing hallucination in code generation.
- The advisor pipeline (prompt → preflight → sandbox → output contract) provides layered safety: each module is independently testable and replaceable.
- Helper metadata drives preflight checks, output contract validation, and loop-breaker generation without additional LLM calls.
- Prompt templates are now ~40% shorter due to removal of hardcoded family-specific fragments, improving token efficiency for local models.

### Main Engineering Focus At This Stage
- Validate skill coverage across all 27 benchmark tasks.
- Improve runtime plan inference accuracy for edge-case column mappings.
- Prepare for Software Manual writing based on the updated plan.

---

## Overall Evolution
Across these versions, the backend evolved through four main stages:

1. **Usable baseline**  
   A functional spreadsheet-processing backend was established.

2. **Structured multi-stage pipeline**  
   The architecture was refactored into clearer stages and agent coordination.

3. **Data-quality and offline robustness**  
   Diagnose, QA, cleaning, local-model support, and bounded execution made the system more reliable.

4. **Skill-based generalization**  
   The backend moved away from task-specific branching and toward abstract spreadsheet capability families supported by deterministic execution and dedicated regression testing.

5. **Validated local-model refresh**  
   After the skill-based backend became stable, the local-model baseline was upgraded and revalidated using both benchmark and family-level CLI checks.

6. **Output-mode and integration polish**  
   After the local-model upgrade, the backend gained an explicit text-only result mode and clearer frontend-facing response metadata, while execution and validation were further modularized for maintainability.

7. **Complete skill-based migration with runtime plans**  
   The legacy task-family routing was fully replaced by a composable skill system with keyword detectors, rich helper metadata, and schema-grounded runtime execution plans. Prompt templates were simplified, the advisor pipeline was formalized, and structured cleaning policy plans were introduced.

This progression is the main engineering story of the backend and reflects how the system changed from an early task-solving prototype into a more systematic spreadsheet-processing platform.
