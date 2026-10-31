# Recovering Hidden Dependencies in Legacy Databases

Reproducibility package for *"Recovering Hidden Dependencies in Legacy Databases: A Metadata
Knowledge Graph Approach to Automated Migration Planning"* (G. Pullur Balu).

Legacy databases often enforce relationships in application code rather than as declared foreign
keys. This package infers those undeclared dependencies by fusing naming evidence with data
(inclusion-dependency) evidence, builds a metadata knowledge graph, and uses it to sequence,
parallelize, execute and validate a migration.

The framework is backend-agnostic. Experiments use NetworkX + SQLite so anyone can rerun them at no
cost; the same graph model runs on Amazon Neptune in the cloud deployment described in the paper.

## Quick start

Requires Python 3.9+ (and `gcc`/`make` for the TPC-DS step). Works out of the box in GitHub Codespaces.

```bash
pip install -r requirements.txt
python src/fetch_data.py        # Chinook, Northwind, Sakila: download + SHA-256 check
python src/build_tpcds.py       # TPC-DS: build generator, generate SF1, verify, load (~2 min)
python src/run_experiments.py   # ~40 min on 2 vCPUs; writes results/results.json (incl. hardware)
python src/critical.py          # migration-critical analysis of missed dependencies (results/critical.json)
python src/make_figures.py      # figures, LaTeX tables and results/tables.md, all from results.json
```

Or run everything, including the tests and a comparison with the published results, with
`./reproduce.sh`. Exact package versions are in `requirements-lock.txt`; the repository also opens
in a ready-made GitHub Codespaces container (`.devcontainer/`).

## Tests and verification

- `pytest -q` runs unit tests (naming rules, data score, cycle deferral and load order), invariant
  tests on Chinook (deterministic detection; every source row is exact, altered or missing; the
  ground-truth plan loses no rows), and a check that `results/results.json` matches its recorded digest.
- `python src/compare_results.py published.json results/results.json` compares a fresh run with the
  published file, ignoring wall-clock timings. The published results were reproduced this way on a
  second machine (GitHub Codespaces, AMD EPYC 7763) with zero non-timing differences.
- `results/expected_digest.txt` holds the SHA-256 of the published results with timings removed.

`python src/tune.py` re-derives `params.json` from the development seeds (optional).

## Datasets

| Dataset name | Source | Tables | Columns | Rows | Ground-truth dependencies | File |
|---|---|---|---|---|---|---|
| Chinook | [lerocha/chinook-database](https://github.com/lerocha/chinook-database) | 11 | 64 | 15,607 | 11 declared FKs | `schemas/chinook.db` |
| Northwind | [jpwhite3/northwind-SQLite3](https://github.com/jpwhite3/northwind-SQLite3) | 13 | 88 | 625,890 | 13 declared FKs | `schemas/northwind.db` |
| Sakila | [bradleygrant/sakila-sqlite3](https://github.com/bradleygrant/sakila-sqlite3) | 16 | 89 | 46,273 | 22 declared FKs | `schemas/sakila.db` |
| TPC-DS (SF 1) | TPC-DS kit ([gregrahn/tpcds-kit](https://github.com/gregrahn/tpcds-kit) @ `5a3a817`) | 24 | 425 | 2,596,789 | 102 FKs from `tpcds_ri.sql` | `schemas/tpcds_sf1.db` |
| SynthModern-100 | `src/synth.py`, seeds 201–205 | 100 each | ~570 each | ~21k each | ~146 planted each (mean) | `synth/synth_modern_s201.db` … |
| SynthLegacy-100 | `src/synth.py`, seeds 201–205 | 100 each | ~570 each | ~21k each | ~157 planted each (mean) | `synth/synth_legacy_s201.db` … |

Development (tuning) data: `synth_{modern,legacy}_s{101,102,103}.db`, 60 tables each.
Scalability data: `synth_legacy_scale{N}_s{900+N}.db`, N = 50 … 2,000 tables.

In every experiment, **all declared FK constraints are hidden** from the methods and used only as
ground truth.

### TPC-DS notes
- Generated with `dsdgen -scale 1 -rngseed 19620718`; every `.dat` file is verified against
  `src/tpcds_sf1_checksums.json`.
- Dimension tables are loaded in full; the 7 fact tables are stride-sampled (every k-th row) to at
  most 50,000 rows each to keep migration runs tractable.
- `tpcds_ri.sql` contains 104 constraints; 2 name columns that do not exist in `tpcds.sql`
  (`catalog_page.cp_promo_id`, `catalog_returns.cr_ship_date_sk`) and are excluded, leaving 102.
- This package uses the TPC-DS schema and data generator under the TPC EULA. Its numbers are research
  measurements, **not TPC-DS benchmark results**. The kit is cloned at build time and not redistributed.

### Synthetic naming styles (SynthLegacy-100 / SynthModern-100)

| Style | Example (child column → parent key) | Legacy share | Modern share |
|---|---|---|---|
| Clean | `tax_log.corr_key` → `corr_log.corr_key` | 25% | 80% |
| Role-qualified | `div_mast.alt_corr_nbr` → `corr_dtl.corr_nbr` | 25% | 10% |
| Abbreviated | `exch_ctl.fnd_key` → `fund_dtl.fund_key` | 30% | 10% |
| Opaque | `brkr_hist.link_val6` → `cust_rel.cust_nbr` | 20% | 0% |

Plus ~3% self-references, ~3% cyclic back-references, noise columns (codes, quantities, amounts,
external references) and ~2% orphan reference values to mimic legacy data-quality defects.

### Stress test (revision 1, seeds 301–305)

SynthLegacy schemas with harder conditions, generated by the same generator with options that draw
from a separate random stream (default schemas are byte-identical with or without them):
10% and 25% orphan references, 30% NULL references, integer-only (ambiguous) keys, 20% of tables
without a declared primary key, 15 composite-key parent tables referenced by two columns, and all
combined. Composite dependencies are out of scope for single-column detection and are reported
separately.

## Methods compared

- **Name-only**: naming-convention rules (exact key name, `<table>_id`, role-qualified suffix).
- **Data-only (IND)**: partial inclusion dependencies with coverage and specificity.
- **Fixed-weight fusion**: C = α·H + (1−α)·S.
- **Proposed (adaptive)**: fusion in which a name with no signal (H < h0) is treated as neutral; such
  columns are accepted on data evidence only if the inclusion is near-complete and unambiguous.
- **Ablations**: the proposed method without the adaptive rule, and without the specificity term.
- **Classifier (exact / partial IND)**: a decision tree on ten features modeled on Rostin et al.
  (WebDB 2009), trained on the development seeds only; candidates are exact inclusion dependencies
  (as in that paper) or partial ones (same gate as the proposed method). Not a reproduction of
  their system. Ties in predicted probability are broken by name similarity, then inclusion.
- **Proposed + key inference** (stress test only): for tables without a declared primary key,
  non-null unique columns are treated as candidate keys.

## What each experiment measures

- **Migration**: rows are loaded in plan order into a target with the true foreign keys enforced.
  Cyclic references are loaded as NULL and set in a second phase. Reported per plan: rows loaded in
  phase 1, phase-2 failures, and the final state of every source row: *exact* (all values equal),
  *altered* (a deferred reference left NULL because its update failed) or *missing* (rejected).
- **Validation**: the proposed plan is loaded without constraints; 50 rows are deleted and 50
  references along true dependencies are corrupted. *Graph-based validation* uses only the recovered
  dependencies (key-set lineage per table, orphan check per recovered edge). The *independent audit*
  compares every row with the source and checks the true dependencies. Both are reported, together
  with alerts on the clean target (source data defects, and false alarms from wrong edges).

## Protocol and development timeline

1. Naming rules and the fallback for columns without data were developed while inspecting detection
   output on Chinook, Northwind and Sakila. Results on those three schemas are therefore **not**
   strictly held out.
2. Parameters were tuned on development seeds 101–103 only and frozen in `params.json`.
3. The first run on test seeds 201–205 showed 6% recall on opaque names; the adaptive rule was then
   added and its parameters tuned on development seeds only. The test seeds thus influenced the
   design of the rule, though not its parameters.
4. TPC-DS was added after step 3 and evaluated with the frozen method: the only fully held-out
   public evaluation.
5. Revision 1 added the classifier baseline, ablations, validation, final-state accounting,
   sampling sensitivity and the stress test (new seeds 301–305), without changing the method or
   its parameters.

Determinism: synthetic data comes from fixed seeds, TPC-DS from a fixed generator seed with verified
checksums, and value sampling is sorted, not random. Reruns under a different `PYTHONHASHSEED`
give identical results apart from wall-clock timings. All timings in the paper come from the single
`results/results.json`, which records the CPU, core count and software versions it ran on;
scalability timings are the median of three repetitions.

## Limitations

- Legacy naming is simulated by `src/synth.py`; real mainframe catalogs (DB2, VSAM copybooks) are not included.
- Semantic role names (e.g. `ReportsTo → Employee`) are not recovered by any method.
- Parallel speedup is a cost model (table cost = rows, LPT scheduling), not wall-clock time.
- Single-column keys only; composite FKs are not inferred.
- Primary keys are assumed declared; key inference is evaluated only in the stress test.
- Two-phase loading inserts NULL into deferred (cyclic) reference columns in phase 1. The evaluation
  target declares types, primary keys and the true foreign keys, but no NOT NULL constraints. In Sakila,
  the two deferred columns (`store.manager_staff_id`, `staff.store_id`) are NOT NULL in the source; they
  are NULL only between the phases and phase 2 restores every value. A target that keeps NOT NULL would
  reject the phase-1 inserts and needs deferred constraint checking or NOT NULL added after loading.
- Validation based on the recovered graph cannot detect broken references along dependencies it
  missed; an independent source-to-target audit is required for full coverage.

## Layout

```
src/kgmig.py            framework: extraction, standardization, detection, KG, planning, migration, validation
src/baselines.py        feature-classifier baseline (after Rostin et al.)
src/synth.py            synthetic legacy-schema generator with planted ground truth
src/build_tpcds.py      TPC-DS build, checksum verification and load
src/fetch_data.py       public data download + checksum verification
src/tune.py             development-only parameter tuning
src/run_experiments.py  all experiments
src/make_figures.py     figures + tables
params.json             frozen parameters
results/                results.json, tables.md, figures/, latex/ (tables and numbers used by the paper)
```
