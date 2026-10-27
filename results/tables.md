# Results tables

Generated from results/results.json. Environment: Intel(R) Xeon(R) Processor @ 2.10GHz, 2 logical CPUs, Python 3.13.17, NetworkX 3.7, scikit-learn 1.9.1, SQLite 3.53.1.

## Detection (all declared constraints hidden)

| Dataset | Method | Precision | Recall | F1 |
|---|---|---|---|---|
| Chinook | Name-only | 1.000 | 0.818 | 0.900 |
| Chinook | Data-only (IND) | 1.000 | 0.636 | 0.778 |
| Chinook | Fixed-weight fusion | 1.000 | 0.818 | 0.900 |
| Chinook | Proposed (adaptive) | 1.000 | 0.818 | 0.900 |
| Chinook | Classifier (exact IND) | 0.750 | 0.818 | 0.783 |
| Chinook | Classifier (partial IND) | 0.750 | 0.818 | 0.783 |
| Chinook | Proposed without adaptive rule | 1.000 | 0.818 | 0.900 |
| Chinook | Proposed without specificity | 0.833 | 0.909 | 0.870 |
| Northwind | Name-only | 1.000 | 0.846 | 0.917 |
| Northwind | Data-only (IND) | 0.833 | 0.769 | 0.800 |
| Northwind | Fixed-weight fusion | 1.000 | 0.923 | 0.960 |
| Northwind | Proposed (adaptive) | 1.000 | 0.923 | 0.960 |
| Northwind | Classifier (exact IND) | 0.909 | 0.769 | 0.833 |
| Northwind | Classifier (partial IND) | 0.667 | 0.769 | 0.714 |
| Northwind | Proposed without adaptive rule | 0.923 | 0.923 | 0.923 |
| Northwind | Proposed without specificity | 0.846 | 0.846 | 0.846 |
| Sakila | Name-only | 1.000 | 1.000 | 1.000 |
| Sakila | Data-only (IND) | 0.789 | 0.682 | 0.732 |
| Sakila | Fixed-weight fusion | 1.000 | 1.000 | 1.000 |
| Sakila | Proposed (adaptive) | 1.000 | 1.000 | 1.000 |
| Sakila | Classifier (exact IND) | 0.875 | 0.955 | 0.913 |
| Sakila | Classifier (partial IND) | 0.875 | 0.955 | 0.913 |
| Sakila | Proposed without adaptive rule | 1.000 | 1.000 | 1.000 |
| Sakila | Proposed without specificity | 0.680 | 0.773 | 0.723 |
| TPC-DS | Name-only | 1.000 | 0.167 | 0.286 |
| TPC-DS | Data-only (IND) | 0.753 | 0.657 | 0.702 |
| TPC-DS | Fixed-weight fusion | 0.936 | 0.716 | 0.811 |
| TPC-DS | Proposed (adaptive) | 0.879 | 0.853 | 0.866 |
| TPC-DS | Classifier (exact IND) | 0.765 | 0.608 | 0.678 |
| TPC-DS | Classifier (partial IND) | 0.722 | 0.686 | 0.704 |
| TPC-DS | Proposed without adaptive rule | 0.950 | 0.941 | 0.946 |
| TPC-DS | Proposed without specificity | 0.424 | 0.706 | 0.529 |
| SynthModern-100 | Name-only | 1.000 ± 0.000 | 0.945 ± 0.022 | 0.971 ± 0.012 |
| SynthModern-100 | Data-only (IND) | 0.844 ± 0.132 | 0.525 ± 0.083 | 0.638 ± 0.067 |
| SynthModern-100 | Fixed-weight fusion | 0.983 ± 0.035 | 0.999 ± 0.003 | 0.990 ± 0.019 |
| SynthModern-100 | Proposed (adaptive) | 0.968 ± 0.064 | 1.000 ± 0.000 | 0.983 ± 0.035 |
| SynthModern-100 | Classifier (exact IND) | 1.000 ± 0.000 | 0.101 ± 0.021 | 0.183 ± 0.033 |
| SynthModern-100 | Classifier (partial IND) | 0.993 ± 0.006 | 0.977 ± 0.011 | 0.985 ± 0.007 |
| SynthModern-100 | Proposed without adaptive rule | 0.950 ± 0.058 | 1.000 ± 0.000 | 0.973 ± 0.032 |
| SynthModern-100 | Proposed without specificity | 0.409 ± 0.015 | 0.963 ± 0.019 | 0.574 ± 0.015 |
| SynthLegacy-100 | Name-only | 0.998 ± 0.005 | 0.636 ± 0.061 | 0.775 ± 0.047 |
| SynthLegacy-100 | Data-only (IND) | 0.846 ± 0.129 | 0.531 ± 0.062 | 0.647 ± 0.058 |
| SynthLegacy-100 | Fixed-weight fusion | 0.972 ± 0.045 | 0.791 ± 0.043 | 0.870 ± 0.015 |
| SynthLegacy-100 | Proposed (adaptive) | 0.948 ± 0.061 | 0.883 ± 0.029 | 0.913 ± 0.023 |
| SynthLegacy-100 | Classifier (exact IND) | 1.000 ± 0.000 | 0.081 ± 0.031 | 0.148 ± 0.053 |
| SynthLegacy-100 | Classifier (partial IND) | 0.987 ± 0.013 | 0.838 ± 0.037 | 0.906 ± 0.024 |
| SynthLegacy-100 | Proposed without adaptive rule | 0.921 ± 0.058 | 0.871 ± 0.029 | 0.893 ± 0.023 |
| SynthLegacy-100 | Proposed without specificity | 0.353 ± 0.022 | 0.806 ± 0.048 | 0.491 ± 0.030 |

## Migration: initially loaded / exact (null-and-flag) / exact (strict) (share of source rows)

| Dataset | No graph | Name-only graph | Proposed graph | Oracle |
|---|---|---|---|---|
| Chinook | 2.1% / 2.1% / 2.1% | 82.6% / 82.6% / 82.6% | 82.6% / 82.6% / 82.6% | 100.0% / 100.0% / 100.0% |
| Northwind | 0.0% / 0.0% / 0.0% | 88.9% / 88.9% / 88.9% | 88.9% / 88.9% / 88.9% | 100.0% / 100.0% / 100.0% |
| Sakila | 0.7% / 0.7% / 0.7% | 100.0% / 100.0% / 100.0% | 100.0% / 100.0% / 100.0% | 100.0% / 100.0% / 100.0% |
| TPC-DS | 82.8% / 82.8% / 82.8% | 83.3% / 83.3% / 83.3% | 100.0% / 100.0% / 100.0% | 100.0% / 100.0% / 100.0% |
| SynthModern-100 | 23.1% / 23.1% / 23.1% | 74.4% / 74.2% / 70.2% | 79.0% / 78.7% / 73.2% | 77.6% / 77.4% / 73.2% |
| SynthLegacy-100 | 21.0% / 21.0% / 21.0% | 38.1% / 38.1% / 38.1% | 59.6% / 58.7% / 55.0% | 78.7% / 78.4% / 66.9% |

## Validation (proposed graph, 50 deleted rows + 50 corrupted references injected)

| Dataset | Missing rows found (graph) | Corruptions found on recovered deps (graph) | on missed deps (graph) | Corruptions found (audit) | False-alarm rows |
|---|---|---|---|---|---|
| Chinook | 50.0/50 | 42.0/42.0 | 0.0/8.0 | 50.0/50 | 0.0 |
| Northwind | 50.0/50 | 47.0/47.0 | 0.0/3.0 | 50.0/50 | 0.0 |
| Sakila | 50.0/50 | 50.0/50.0 | 0.0/0.0 | 50.0/50 | 0.0 |
| TPC-DS | 50.0/50 | 43.0/43.0 | 0.0/7.0 | 50.0/50 | 669.0 |
| SynthModern-100 | 50.0/50 | 50.0/50.0 | 0.0/0.0 | 50.0/50 | 80.6 |
| SynthLegacy-100 | 50.0/50 | 43.8/43.8 | 0.0/5.4 | 50.0/50 | 171.0 |

## Stress test (SynthLegacy profile, seeds 301-305, F1)

| Condition | Name-only | Data-only (IND) | Fixed-weight fusion | Proposed (adaptive) | Classifier (partial IND) | Proposed + key inference |
|---|---|---|---|---|---|---|
| Baseline (new seeds) | 0.773 | 0.611 | 0.875 | 0.906 | 0.887 | -- |
| Dirty references (10% orphans) | 0.773 | 0.573 | 0.844 | 0.838 | 0.812 | -- |
| Dirty references (25% orphans) | 0.773 | 0.336 | 0.712 | 0.701 | 0.672 | -- |
| Sparse references (30% NULL) | 0.773 | 0.610 | 0.868 | 0.909 | 0.887 | -- |
| Ambiguous keys (all integer) | 0.763 | 0.000 | 0.849 | 0.796 | 0.731 | -- |
| Missing primary keys (20% of tables) | 0.690 | 0.498 | 0.771 | 0.787 | 0.782 | 0.905 |
| Composite keys (15 composite parents) | 0.773 | 0.604 | 0.875 | 0.902 | 0.881 | -- |
| Combined | 0.677 | 0.000 | 0.699 | 0.643 | 0.515 | 0.769 |

## Scalability (SynthLegacy, proposed method)

| Tables | Columns | Detect median [min-max] (s) | F1 |
|---|---|---|---|
| 50 | 278 | 0.12 [0.11-0.13] | 0.821 |
| 100 | 563 | 0.53 [0.48-0.58] | 0.903 |
| 250 | 1373 | 2.74 [2.54-3.05] | 0.935 |
| 500 | 2779 | 11.77 [11.38-12.14] | 0.921 |
| 1000 | 5568 | 45.71 [43.33-46.54] | 0.917 |
| 2000 | 11167 | 176.83 [174.31-184.29] | 0.899 |
