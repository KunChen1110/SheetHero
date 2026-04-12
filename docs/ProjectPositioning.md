## Project Positioning

### 1. Project Goal
This project aims to reduce the technical barrier for spreadsheet analysis by allowing users to upload spreadsheet files and express tasks in natural language. The system then attempts to understand the task, diagnose data issues, ask clarification questions when necessary, execute the task safely, validate the result, and return either a generated spreadsheet or a concise text answer.

This framing is also consistent with the original project brief, which expected the tool to:
- accept multiple spreadsheet files as input
- accept a natural-language user prompt
- convert that prompt into executable spreadsheet operations
- flag issues in the data
- provide feedback when the prompt is unclear
- tolerate minor imperfections such as spelling or formatting inconsistencies
- remain usable even when the input format changes slightly, for example through reshuffled columns

Based on the original project brief, the primary design target of the system is spreadsheet-oriented analytical and transformation work rather than unrestricted office automation in general. In other words, the project began from a narrower and more realistic engineering goal: taking one or more spreadsheet files plus a natural-language prompt, then helping the user process data, identify issues, and produce a new spreadsheet result. As the implementation matured, the system started to generalize beyond a few fixed benchmark tasks, but its strongest and most defensible capability still lies in structured spreadsheet workflows, especially workflows common in university and administrative settings, such as:
- tabular aggregation and ranking
- relational joins between structured tables
- assignment and scheduling
- missing-data completion
- structured reporting
- regression / correlation style analysis

### 2. Why The Architecture Changed Over Time
The initial challenge in this project was not only getting an LLM to write code, but making the system reliable enough for repeated use on spreadsheet tasks with noisy schemas and ambiguous user prompts.

A purely prompt-driven or one-shot code generation design was insufficient because:
- spreadsheet tasks are structurally diverse
- users often provide incomplete or ambiguous instructions
- local models are more error-prone in code generation
- validation based only on natural language is unreliable

As a result, the project evolved from a prototype-style LLM workflow into a multi-stage, skill-based spreadsheet system.

### 3. Stage-Based Evolution Process

#### Stage 1: Prototype / Direct Prompting
At the beginning, the system mainly relied on prompt-driven execution and task-level handling. The focus was on proving that spreadsheet tasks could be attempted from natural language input and file uploads.

This stage established:
- the GUI and CLI interaction flow
- basic execution via model-generated code
- dataset-based experimentation

However, the main limitation of this stage was fragility:
- high dependence on prompt wording
- limited protection against invalid code paths
- poor generalization beyond known task setups

#### Stage 2: Multi-Stage Agent Pipeline
The next stage introduced a clearer backend pipeline:
- understanding
- diagnose
- QA clarification
- cleaning
- execution
- validation
- final response

This was the first major architectural improvement because the system stopped treating all requests as a single execution problem. Instead, it began to separate:
- task understanding
- data-quality diagnosis
- result generation
- result verification

This stage improved control flow and made the system much easier to explain and debug.

#### Stage 3: Helper-First And Deterministic Control
The next transition addressed the most important engineering issue: unrestricted code generation was too unstable.

To improve reliability, the project introduced:
- sandboxed execution
- spreadsheet helper functions
- forbidden policies
- bounded repair feedback
- deterministic validation rules

At this point, the system no longer treated the LLM as the sole executor. Instead, the LLM increasingly acted as a controller that selected and orchestrated stable spreadsheet helpers.

This stage significantly improved:
- safety
- repeatability
- correctness on structured tasks
- robustness in offline/local-model settings

#### Stage 4: Skill-Based Systematization
The latest stage is the most important architectural shift.

Instead of organizing the system around individual benchmark tasks, the backend now organizes logic around abstract spreadsheet capability families. These families represent reusable task structures rather than individual cases.

Examples include:
- schema-aligned merge summaries
- reference-guided completion
- grouped aggregation and ranking
- temporal aggregation and ranking
- relational join enrichment
- composite-key relational joins
- dependency-constrained scheduling
- relational assignment schedules
- capacity-constrained allocation
- regression analysis
- correlation matrices
- visual temporal growth reports

This transition matters because it changes the system from:

`task-specific patches`

to:

`skill-based spreadsheet reasoning`

This is the main reason the current system is more extensible and better aligned with software engineering principles than an ad hoc benchmark solver.

### 4. Current System Positioning
The current system should be described as a:

**skill-based spreadsheet agent with deterministic execution and validation support**

This is a more accurate and defensible description than claiming that it can already solve arbitrary office tasks end to end. A more balanced way to position it is:

> the system was originally scoped as an LLM-assisted spreadsheet processing tool, and it has now evolved into a skill-based spreadsheet agent that can generalize across multiple structured spreadsheet skills.

In practice, the system is now strongest when a user request falls into a covered spreadsheet family and the input tables are structurally reasonable.

For such tasks, the system can often rely on:
- family detection
- helper-first deterministic execution
- family-aware validation
- concise final-response formatting

### 5. What The System Can Reasonably Claim
At the current stage, the project can reasonably claim that it supports:
- multi-stage spreadsheet task processing
- family-aware diagnose and QA
- deterministic helper-first execution for covered skills
- deterministic validation for covered output structures
- benchmark-backed diagnose coverage
- synthetic skill regression beyond the original task dataset

This is a strong engineering result for a course project because the system is no longer only a testcase runner. It has begun to generalize at the skill level.

### 6. What It Should Not Overclaim
The system should not be presented as:
- a fully general spreadsheet agent
- a guaranteed solver for arbitrary user-defined spreadsheet tasks
- a system that never requires new family support

The more accurate statement is:

> The current system generalizes across multiple abstract spreadsheet skills, but it is still skill-based rather than open-world.

That framing is technically honest and aligns with the current implementation.

### 7. Why This Is Still A Valid Final Project Outcome
From a course-project perspective, the current system demonstrates:
- iterative architectural improvement
- a clear transition from prompt-heavy prototype to structured software system
- separation of concerns across stages
- practical handling of ambiguity through QA
- measurable evaluation through dataset tasks, diagnose benchmarks, and synthetic skill regression
- conscious limitation handling rather than unsupported claims

That is a stronger project outcome than a system that only appears flexible in demos but is not internally structured or defensible.
