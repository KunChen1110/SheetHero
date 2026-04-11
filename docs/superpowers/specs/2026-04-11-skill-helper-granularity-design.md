# Skill-Driven Helper Granularity Refactor

## Summary

The current spreadsheet pipeline has moved from task-family routing toward skill-based routing, but helper granularity is still inconsistent. The system mixes:

- atomic helpers that perform one reusable transformation
- workflow helpers that implement a stable multi-step pattern
- task-shaped report helpers that bundle table loading, schema inference, preprocessing, business logic, and output formatting into one call

That mixture reduces generalization. It encourages the LLM to memorize a report recipe instead of assembling a solution from skill guidance, runtime schema inference, and composable helpers.

This design refactors the system toward:

1. `question -> skill family`
2. `question + runtime schema -> execution plan`
3. `execution plan + skill recipe -> composed helper calls`
4. `output contract enforcement -> final workbook/text result`

The design explicitly forbids benchmark-specific answer content in skill templates and loop breakers unless it was inferred at runtime from the current question and schema.

## Problem Statement

### Current issues

1. Some helpers are too large.
   Helpers such as `build_market_share_shipment_report`, `build_relational_assignment_schedule_report`, `build_financial_dashboard_report`, `build_candidate_screening_report`, and similar `build_*_report` functions currently absorb multiple responsibilities.

2. Prompt guidance is too close to testcase recipes.
   Some execution rules and loop breakers encode concrete columns, fixed preprocessing sequences, or a single helper path that fits one benchmark schema well but does not generalize.

3. Runtime inference is too weak relative to helper size.
   The system often selects one large helper early, then tries to force the problem into that helper shape instead of inferring plan parameters first and composing multiple smaller operations.

4. QA and cleaning are coupled through a flat action list.
   QA clarifies issue-by-issue and exports action strings directly. This loses structure, causes duplicate questions, and makes cleaning brittle.

5. Output contracts are sometimes over-applied.
   Statistical tasks that only require a ranked correlation table may still inherit matrix-style summary requirements, causing unnecessary repair turns.

### Why this matters

With `qwen3:8b`, prompt waste and overly specific recipes both hurt performance. The model needs:

- smaller, clearer helper contracts
- stable workflow guidance at the skill level
- explicit runtime plan variables
- fewer places where benchmark-specific text leaks into execution

## Goals

- Increase LLM generalization across datasets with different schemas.
- Keep helpers as the main execution building blocks.
- Move concrete column and preprocessing decisions to runtime inference.
- Support tasks that need multiple helper calls instead of forcing one oversized helper.
- Reduce repeated QA clarifications and improve cleaning policy quality.
- Preserve the real benchmark pass rate while removing testcase-shaped prompt logic.

## Non-Goals

- Replacing the current system with a full planner DSL or agent graph.
- Eliminating all workflow helpers. Some family-level workflows are still useful.
- Removing deterministic validation or rule checks unrelated to testcase answer leakage.
- Solving image tasks in this refactor.

## Design Principles

1. Skills define method, not answer.
   A skill recipe may describe workflow skeletons, helper contracts, pitfalls, and output shape expectations. It must not embed benchmark-specific columns or a fixed answer path.

2. Runtime inference chooses columns and table roles.
   Target columns, feature columns, join keys, date columns, value columns, and preprocessing choices come from the current question and observed schema.

3. Helpers should be explicit and composable.
   Helpers should accept clear inputs and return structured outputs. Avoid self-loading helpers unless workbook loading is intrinsic to the helper contract.

4. Loop breakers enforce contracts, not benchmark solutions.
   They may require use of a helper family, output a workbook, or avoid known anti-patterns. They must not contain fixed benchmark column names or handcrafted answer logic.

5. QA should produce policies, not ad hoc strings.
   Cleaning should consume structured policies that survive across multiple related issues.

## Helper Taxonomy

The system should distinguish three helper layers.

### 1. Atomic helpers

Atomic helpers perform one reusable transformation and require explicit inputs.

Examples:

- `compute_ratio_column`
- `compute_percentage_share`
- `compute_weighted_score`
- `concat_tables_with_same_headers`
- `merge_on_shared_period`
- `build_weighted_period_output`
- `find_table_by_headers`
- `normalize_period_column`
- `safe_numeric_coercion`
- `encode_categorical_columns`

Properties:

- one clear purpose
- no hidden table inference
- no output workbook writing unless that is the single purpose
- reusable across many skills

### 2. Workflow helpers

Workflow helpers encapsulate a stable multi-step family pattern, but still require explicit plan inputs.

Examples:

- `build_dependency_schedule`
- `compute_feature_correlations`
- `build_correlation_matrix_table`
- `fit_linear_regression_weights`
- `build_grouped_assignment_join`

Properties:

- solve a family-level operation
- do not infer question semantics internally
- do not hardcode benchmark column names
- may return structured payloads such as `output_df`, `summary`, `warnings`, `artifacts`

### 3. Runtime plan inference helpers

These infer plan variables from the user question plus observed schema.

Examples:

- `infer_target_feature_plan`
- `infer_join_plan`
- `infer_period_alignment_plan`
- `infer_group_aggregate_plan`
- `infer_cleaning_policy_plan`

Properties:

- no workbook mutation
- no final output writing
- return explicit plan objects
- isolate the "decide what columns/roles matter" step from execution

## When a Helper Is Too Large

A helper should be split when at least two of these are true:

- it loads its own tables and also performs business logic
- it infers semantic roles internally and also formats final output
- it is only usable with one known schema family
- it requires prompt text to specify benchmark column names to work well
- it combines preprocessing, main computation, ranking/filtering, and workbook writing
- it has multiple valid sub-flows hidden behind one name

## Target Architecture

### End-to-end flow

1. Detect the `skill family`.
2. Build a `runtime execution plan` from question plus schema.
3. Generate code using:
   - the skill recipe
   - the plan object
   - a small set of allowed workflow and atomic helpers
4. Enforce output contract in preflight and repair.
5. Save workbook or text response.

### Plan object shape

Each skill family should consume a structured plan object rather than raw question heuristics inside loop breakers.

Illustrative shape:

```python
plan = {
    "skill": "statistical",
    "task_type": "target_feature_correlation",
    "table_roles": {
        "primary_table": "input01.csv",
    },
    "target_col": "inferred at runtime",
    "feature_cols": ["inferred", "at", "runtime"],
    "group_cols": [],
    "join_keys": [],
    "period_col": None,
    "value_cols": [],
    "categorical_cols_to_encode": [],
    "numeric_cols_to_coerce": [],
    "output_contract": {
        "kind": "ranked_rows",
        "sheet_name": "Output",
    },
}
```

The placeholders above represent runtime values, not spec defaults.

### Skill recipe shape

A skill recipe should describe:

- what kind of problem this family solves
- what plan fields it expects
- which workflow helpers are preferred
- which atomic helpers are available
- common pitfalls
- required output contract

It should not contain concrete benchmark column names.

## Family Refactor Plan

### A. Statistical family

This is the highest priority because it currently shows the clearest testcase-specific drift.

#### Current problems

- `compute_feature_correlations` guidance has been easy to contaminate with dataset-specific columns.
- regression and correlation tasks can still collide in detection and output expectations.
- the system can over-require summary fields for tasks that only need one ranked table.

#### Target split

- runtime inference:
  - `infer_target_feature_plan`
  - `infer_regression_plan`
  - `infer_correlation_matrix_plan`
- workflow helpers:
  - keep `compute_feature_correlations`
  - keep `fit_linear_regression_weights`
  - keep `build_correlation_matrix_table`
- atomic helpers:
  - `coerce_numeric_columns`
  - `encode_categorical_columns`
  - `select_candidate_feature_columns`

#### Recipe example

The correlation skill recipe should say:

- load the relevant table
- inspect schema and question
- infer the target column from the question
- infer candidate feature columns
- coerce numeric-like columns
- encode categorical columns only if needed
- call `compute_feature_correlations`
- write the returned dataframe to the output sheet

It must not say:

- use `Survived` as target
- use `Sex`, `Age`, `Fare`, `Cabin`, `Embarked` as features
- apply Titanic-specific preprocessing

### B. QA and cleaning

This is the second highest priority because the current flat action design does not generalize.

#### Current problems

- QA asks similar questions multiple times.
- exported actions are strings, not structured plans.
- cleaning receives partially resolved intent and has to guess the real policy.

#### Target split

- QA produces structured issue groups:
  - `issue_type`
  - `scope`
  - `affected_columns`
  - `affected_rows`
  - `proposed_options`
- QA deduplicates by policy domain before asking the user.
- QA finalizes a `cleaning_policy_plan` instead of a list of action strings.
- cleaning consumes that policy plan and maps it to deterministic or LLM-generated code paths.

#### Example

Two missing-value issues in the same column should become one clarification about policy for that column or issue class, not two separate row-level questions unless row-level distinction is truly necessary.

### C. Relational multi-table family

Large helpers in join and schedule workflows should be reduced to:

- plan inference for table roles and key roles
- workflow helpers for stable multi-table joins
- atomic helpers for table lookup, header matching, safe merge, and grouped summarization

Candidates to shrink:

- `build_relational_assignment_schedule_report`
- `build_multi_key_relational_join_report`
- `build_relational_join_enrichment_report`

Preferred decomposition:

- infer assignment table
- infer schedule table
- infer join keys
- use `find_table_by_headers`
- use `build_grouped_assignment_join`
- apply ranking, sorting, or output formatting separately

### D. Proportion and temporal aggregation family

Candidates to shrink:

- `build_market_share_shipment_report`
- `build_time_series_aggregation_report`
- `build_region_growth_analysis`

Preferred decomposition:

- infer period column
- infer value/share columns
- normalize period representation
- align across tables
- compute share or weighted output
- render workbook output

### E. Domain-specific report helpers

Helpers that encode one domain example should either be removed from routing or split into reusable pieces.

High-risk candidates:

- `build_candidate_screening_report`
- `build_financial_dashboard_report`
- `build_hospital_utilisation_report`
- `build_diabetes_region_report`
- `build_mobile_reviews_summary_report`
- `build_store_feature_analysis_report`
- `build_ecommerce_merge_report`
- `build_inventory_eoq_report`
- `build_cash_flow_efficiency_report`

Decision rule:

- if the helper represents a stable cross-domain workflow, keep it and rename it to the workflow
- if it mostly represents one benchmark or domain story, split it and remove direct registry exposure

## Registry Changes

The registry should expose family-level workflow helpers, not benchmark-shaped report helpers.

### Desired registry behavior

- `detect_skill(question)` remains family-level
- `select_helper(skill, question)` becomes a lighter workflow selection step
- plan inference happens before execution guidance is built
- prompt builders receive `skill + helper + plan summary`, not only `skill + helper`

### Registry rules

- prefer generic workflow helpers in `SkillSpec.helpers`
- keep atomic helpers available in execution namespace, but not necessarily as `select_helper` alternatives
- do not register helpers whose names encode a benchmark-specific story unless they are temporary compatibility shims

## Prompt and Loop Breaker Rules

### Allowed content

- workflow skeletons
- helper call shapes
- helper input/output contracts
- output sheet and save requirements
- anti-pattern guards such as "do not merge on file order"

### Forbidden content

- fixed benchmark column names
- fixed feature column lists
- benchmark-specific preprocessing steps
- references to one known dataset unless derived from the active runtime schema
- implicit answer code hidden inside loop breakers

### Example of an acceptable loop breaker

```python
plan = infer_target_feature_plan(user_question, df.columns)
prepared_df = prepare_feature_correlation_inputs(df, plan)
result = compute_feature_correlations(
    prepared_df,
    target_col=plan["target_col"],
    feature_cols=plan["feature_cols"],
    round_digits=3,
)
create_output_sheet("Output")
write_dataframe_to_sheet(result["output_df"], "Output", "A1")
saved_file = save_workbook_to(output_path)
print(f"SAVED_FILE: {saved_file}")
saved_file
```

This is acceptable because it enforces workflow and output contract without embedding the answer.

## Migration Strategy

### Phase 1

- Freeze new testcase-specific prompt additions.
- Introduce helper split criteria into code review guidance.
- Add plan-object plumbing to prompt builders and execution runtime.

### Phase 2

- Refactor the statistical family first.
- Remove benchmark-specific content from correlation guidance.
- Adjust understanding/output-contract inference for ranked-table correlation tasks.

### Phase 3

- Refactor QA to deduplicate issue groups.
- Replace exported action strings with structured cleaning policy plans.
- Update cleaning to consume structured plans.

### Phase 4

- Shrink relational and proportion workflow helpers.
- Replace large helper routing with plan inference plus smaller helper composition.

### Phase 5

- Audit the registry and remove direct routing to remaining domain-story helpers.
- Keep compatibility shims only where needed for transition, with a removal deadline.

## Testing and Verification

### Unit-level coverage

- detector tests for skill and sub-detector routing
- plan inference tests for target, feature, join-key, period, and output-contract decisions
- prompt guidance tests that assert absence of benchmark-specific answer text
- QA tests for issue deduplication and policy grouping
- cleaning tests for policy-plan consumption

### End-to-end verification

Use the real CLI path:

```bash
./venv/bin/python -m src.backend.main
```

Then:

```text
!llm --switch--offline qwen3:8b
!dataset --index N
```

Success criteria are based on actual task completion, not only synthetic tests.

## Acceptance Criteria

1. No benchmark-specific column names appear in skill templates or loop breakers unless they were inferred from the current runtime question and schema.
2. A skill recipe remains usable across different datasets with different schemas.
3. The same skill supports multiple helper compositions instead of one prewritten code path.
4. Loop breakers enforce workflow and output contract only, not testcase answer content.
5. QA groups related issues into policy-level clarifications rather than repeated row-level questions by default.
6. Cleaning consumes structured policy plans rather than only opaque action strings.
7. Real CLI runs remain the source of truth for task completion.

## Risks

- Splitting helpers too aggressively could push too much burden back to the LLM.
- Leaving oversized workflow helpers in the registry too long will preserve hidden benchmark bias.
- QA policy grouping can over-merge genuinely distinct issues if grouping rules are too coarse.

## Recommendation

Implement this as an incremental refactor centered on `runtime plan inference + family-level workflow helpers + atomic helper composition`. This is the best balance between generalization, controllability, and compatibility with the current codebase.
