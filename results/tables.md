# Results tables

## Table 1. Undeclared-dependency detection (all FK constraints hidden)

| Schema set | Method | Precision | Recall | F1 |
|---|---|---|---|---|
| Chinook (11 deps) | Name-only | 1.000 | 0.818 | 0.900 |
| Chinook (11 deps) | Data-only (IND) | 1.000 | 0.636 | 0.778 |
| Chinook (11 deps) | Fixed-weight fusion | 1.000 | 0.818 | 0.900 |
| Chinook (11 deps) | Proposed (adaptive) | 1.000 | 0.818 | 0.900 |
| Northwind (13 deps) | Name-only | 1.000 | 0.846 | 0.917 |
| Northwind (13 deps) | Data-only (IND) | 0.833 | 0.769 | 0.800 |
| Northwind (13 deps) | Fixed-weight fusion | 1.000 | 0.923 | 0.960 |
| Northwind (13 deps) | Proposed (adaptive) | 1.000 | 0.923 | 0.960 |
| Sakila (22 deps) | Name-only | 1.000 | 1.000 | 1.000 |
| Sakila (22 deps) | Data-only (IND) | 0.789 | 0.682 | 0.732 |
| Sakila (22 deps) | Fixed-weight fusion | 1.000 | 1.000 | 1.000 |
| Sakila (22 deps) | Proposed (adaptive) | 1.000 | 1.000 | 1.000 |
| TPC-DS (102 deps) | Name-only | 1.000 | 0.167 | 0.286 |
| TPC-DS (102 deps) | Data-only (IND) | 0.753 | 0.657 | 0.702 |
| TPC-DS (102 deps) | Fixed-weight fusion | 0.936 | 0.716 | 0.811 |
| TPC-DS (102 deps) | Proposed (adaptive) | 0.879 | 0.853 | 0.866 |
| SynthModern-100 (5 seeds) | Name-only | 1.000 ± 0.000 | 0.945 ± 0.022 | 0.971 ± 0.012 |
| SynthModern-100 (5 seeds) | Data-only (IND) | 0.844 ± 0.132 | 0.525 ± 0.083 | 0.638 ± 0.067 |
| SynthModern-100 (5 seeds) | Fixed-weight fusion | 0.983 ± 0.035 | 0.999 ± 0.003 | 0.990 ± 0.019 |
| SynthModern-100 (5 seeds) | Proposed (adaptive) | 0.968 ± 0.064 | 1.000 ± 0.000 | 0.983 ± 0.035 |
| SynthLegacy-100 (5 seeds) | Name-only | 0.998 ± 0.005 | 0.636 ± 0.061 | 0.775 ± 0.047 |
| SynthLegacy-100 (5 seeds) | Data-only (IND) | 0.846 ± 0.129 | 0.531 ± 0.062 | 0.647 ± 0.058 |
| SynthLegacy-100 (5 seeds) | Fixed-weight fusion | 0.972 ± 0.045 | 0.791 ± 0.043 | 0.870 ± 0.015 |
| SynthLegacy-100 (5 seeds) | Proposed (adaptive) | 0.948 ± 0.061 | 0.883 ± 0.029 | 0.913 ± 0.023 |

TPC-DS ground truth: tpcds_ri.sql (2 invalid definitions excluded). Proposed-method detections not in that file: customer.c_last_review_date_sk → date_dim.d_date_sk; date_dim.d_first_dom → date_dim.d_date_sk; date_dim.d_last_dom → date_dim.d_date_sk; date_dim.d_same_day_lq → date_dim.d_date_sk; date_dim.d_same_day_ly → date_dim.d_date_sk; income_band.ib_lower_bound → customer_demographics.cd_demo_sk; income_band.ib_upper_bound → customer_demographics.cd_demo_sk; store_returns.sr_ticket_number → customer_demographics.cd_demo_sk; store_sales.ss_ticket_number → customer_demographics.cd_demo_sk; time_dim.t_time → time_dim.t_time_sk; warehouse.w_warehouse_sq_ft → customer_demographics.cd_demo_sk; web_page.wp_customer_sk → customer.c_customer_sk

## Table 2. Recall by naming style (SynthLegacy-100)

| Method | clean | role | abbrev | opaque | self |
|---|---|---|---|---|---|
| Name-only | 1.00 | 1.00 | 0.45 | 0.00 | 1.00 |
| Data-only (IND) | 0.53 | 0.53 | 0.54 | 0.53 | 0.41 |
| Fixed-weight fusion | 1.00 | 1.00 | 0.96 | 0.06 | 1.00 |
| Proposed (adaptive) | 1.00 | 1.00 | 0.97 | 0.49 | 1.00 |

Dependencies per style (5 seeds): clean=206, abbrev=219, opaque=167, role=177, self=17

## Table 3. Migration execution (target with FK constraints enforced)

| Schema | Plan | Ordering score Sq | Rows loaded | Rows rejected | Waves | Cycles | Speedup (4 workers, model) |
|---|---|---|---|---|---|---|---|
| Chinook | No graph (alphabetical) | 0.636 | 331 | 15,276 | 11 | 0 | 1.00× |
| Chinook | Graph: Name-only | 0.909 | 12,896 | 2,711 | 4 | 0 | 1.21× |
| Chinook | Graph: Proposed | 0.909 | 12,896 | 2,711 | 4 | 0 | 1.21× |
| Chinook | Oracle (declared FKs) | 1.000 | 15,607 | 0 | 4 | 1 | 1.22× |
| Northwind | No graph (alphabetical) | 0.385 | 198 | 625,692 | 13 | 0 | 1.00× |
| Northwind | Graph: Name-only | 1.000 | 556,422 | 69,468 | 3 | 0 | 1.00× |
| Northwind | Graph: Proposed | 1.000 | 556,422 | 69,468 | 3 | 0 | 1.00× |
| Northwind | Oracle (declared FKs) | 1.000 | 625,890 | 0 | 3 | 1 | 1.00× |
| Sakila | No graph (alphabetical) | 0.545 | 331 | 45,942 | 16 | 0 | 1.00× |
| Sakila | Graph: Name-only | 0.955 | 46,273 | 0 | 7 | 1 | 1.07× |
| Sakila | Graph: Proposed | 0.955 | 46,273 | 0 | 7 | 1 | 1.07× |
| Sakila | Oracle (declared FKs) | 0.955 | 46,273 | 0 | 7 | 1 | 1.07× |
| TPC-DS | No graph (alphabetical) | 0.569 | 2,149,961 | 446,828 | 24 | 0 | 1.00× |
| TPC-DS | Graph: Name-only | 0.912 | 2,162,759 | 434,030 | 3 | 0 | 1.29× |
| TPC-DS | Graph: Proposed | 1.000 | 2,596,789 | 0 | 6 | 2 | 1.19× |
| TPC-DS | Oracle (declared FKs) | 1.000 | 2,596,789 | 0 | 4 | 0 | 1.20× |
| SynthModern-100 (mean of 5 seeds) | No graph (alphabetical) | 0.539 | 5,006 | 16,631 | 100.0 | 0.0 | 1.00× |
| SynthModern-100 (mean of 5 seeds) | Graph: Name-only | 0.978 | 16,107 | 5,530 | 11.0 | 2.8 | 3.50× |
| SynthModern-100 (mean of 5 seeds) | Graph: Proposed | 0.989 | 17,086 | 4,551 | 11.6 | 3.2 | 3.46× |
| SynthModern-100 (mean of 5 seeds) | Oracle (declared FKs) | 0.997 | 16,799 | 4,838 | 11.6 | 2.8 | 3.45× |
| SynthLegacy-100 (mean of 5 seeds) | No graph (alphabetical) | 0.513 | 4,536 | 17,102 | 100.0 | 0.0 | 1.00× |
| SynthLegacy-100 (mean of 5 seeds) | Graph: Name-only | 0.830 | 8,245 | 13,393 | 9.4 | 3.4 | 3.59× |
| SynthLegacy-100 (mean of 5 seeds) | Graph: Proposed | 0.951 | 12,897 | 8,740 | 11.8 | 4.0 | 3.48× |
| SynthLegacy-100 (mean of 5 seeds) | Oracle (declared FKs) | 0.992 | 17,030 | 4,608 | 12.8 | 3.6 | 3.47× |

Synthetic data contains ~2% planted orphan rows (legacy data-quality defects); the oracle row shows that floor.

## Table 4. Scalability (SynthLegacy, 50–2,000 tables, proposed method)

| Tables | Columns | True deps | KG nodes | KG edges | Extract (s) | Detect (s) | Plan (s) | F1 | Speedup 4w | Speedup 8w |
|---|---|---|---|---|---|---|---|---|---|---|
| 50 | 278 | 78 | 328 | 424 | 0.02 | 0.1 | 0.001 | 0.821 | 2.98× | 3.95× |
| 100 | 563 | 163 | 663 | 857 | 0.03 | 0.5 | 0.001 | 0.903 | 3.48× | 5.44× |
| 250 | 1,373 | 373 | 1,623 | 2,047 | 0.07 | 2.4 | 0.002 | 0.935 | 3.90× | 7.40× |
| 500 | 2,779 | 779 | 3,279 | 4,199 | 0.15 | 9.2 | 0.005 | 0.921 | 3.94× | 7.65× |
| 1000 | 5,568 | 1,568 | 6,568 | 8,402 | 0.30 | 38.1 | 0.008 | 0.917 | 3.95× | 7.70× |
| 2000 | 11,167 | 3,167 | 13,167 | 16,895 | 0.60 | 167.2 | 0.026 | 0.899 | 3.96× | 7.83× |

Tuned parameters (dev seeds 101–103 only): {"devF1": 0.9734836195360939, "alpha": 0.6, "tau": 0.35, "min_inc": 0.6, "h0": 0.35, "strict_inc": 0.9}
