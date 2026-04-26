# Dataset Layout

This directory contains three separate evaluation suites. Keep them separate because they measure different parts of the system.

## 1. Development End-to-End Suite

- Location: `dataset/DevelopmentBenchmark`
- Files: `dataset/DevelopmentBenchmark/Task01` through `dataset/DevelopmentBenchmark/Task27`
- Purpose: original project tasks used during development to define the system boundary and catch regressions.
- Backend CLI:

```text
!benchmark dev --list
!benchmark dev --index 1
```

Direct runner:

```bash
MPLCONFIGDIR=/tmp ./venv/bin/python test/core/run_test.py --test-n 1 --dataset-dir dataset/DevelopmentBenchmark
```

## 2. Diagnose Benchmark

- Location: `dataset/DiagnoseBenchmark/SpreadsheetDiagnosisData`
- Files: `dataset_small` and `dataset_median`
- Purpose: stage-level benchmark for diagnosing data quality issues and producing useful QA questions.
- Backend CLI:

```text
!benchmark diagnose small
!benchmark diagnose median
!benchmark diagnose all --limit 5
```

Direct runner:

```bash
MPLCONFIGDIR=/tmp ./venv/bin/python test/utils/run_diagnose_benchmark.py --split dataset_small
```

## 3. System Evaluation Benchmark

- Location: `dataset/SystemEvaluationBenchmark`
- Splits: `clean_cases`, `median_clean_cases`, `large_clean_cases`
- Purpose: final end-to-end system evaluation after the system is implemented.
- Backend CLI:

```text
!benchmark evaluation clean --list
!benchmark evaluation clean --index 1
!benchmark evaluation median --index 1
!benchmark evaluation large --index 1
```

Evaluation runs always call the LLM judge after generating the output.

Direct runner:

```bash
MPLCONFIGDIR=/tmp ./venv/bin/python test/core/run_test.py --test-n 1 --dataset-dir dataset/SystemEvaluationBenchmark/clean_cases
```

Manual LLM judge:

```text
!judge evaluation clean --index 1
!judge evaluation median --index 1
!judge evaluation large --index 1
```

Direct judge runner:

```bash
./venv/bin/python -m backend.Judger.evaluator "Test 1" --dataset dataset/SystemEvaluationBenchmark/clean_cases/dataset.json --logger artifacts/loggers/<logger>.md
```
