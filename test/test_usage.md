# Instruction for testing

## Run the whole backend

``` bash
python -m src.backend.main --task-json dataset/dataset.json --task-index 1
```
Run the first integration test






## Run diagnose module test

``` bash
python test/stages/diagnose_test.py --test-id 27 --dataset-dir dataset
```
Run the 27th test in the dataset

## Run understanding module test

``` bash
python test/stages/test_understanding.py --test-id 27 --dataset-dir dataset
```
Run the 27th test in the dataset


## Run Geometric Sampling in diagnose module

``` bash
python3 test/utils/geometric_sampling_test.py --test-id 1 --dataset-dir dataset
```

By default, `DIAGNOSE_GEOM_DEBUG=1`, which means that you can see the reason why a certain row is sampled.

