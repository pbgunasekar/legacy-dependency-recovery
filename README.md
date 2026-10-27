# kgmig — Confidence-aware dependency inference for graph-driven legacy data migration

Reproducibility package for the experiments in *"Leveraging a Metadata Knowledge Graph to Automate
and Optimize Data Migration Pipelines in Legacy Enterprise Systems"* (G. Pullur Balu).

The framework is backend-agnostic: experiments use NetworkX + SQLite so anyone can rerun them at no
cost. The same graph model and Gremlin traversals run on Amazon Neptune in the cloud deployment
described in the paper.

## Quick start

```bash
pip install -r requirements.txt
python src/fetch_data.py        # downloads 3 public DBs, verifies SHA-256
python src/tune.py              # optional: re-tunes on DEV seeds 101-103 -> params.json
python src/run_experiments.py   # ~6 min; writes results/results.json
python src/make_figures.py      # figures (PNG, 300 dpi) + results/tables.md
```

## What is evaluated

| Experiment | Data | Measures |
|---|---|---|
| Undeclared-dependency recovery | Chinook, Northwind, Sakila (all FK constraints hidden); synthetic modern & legacy schemas (5 seeds × 100 tables) | Precision, recall, F1 vs. declared FKs |
| Recall by naming style | Synthetic legacy | clean / role-qualified / abbreviated / opaque names |
| Migration execution | Same | Rows loaded into a target with FK constraints enforced, ordering score Sq, cycles |
| Parallel planning | Same | Speedup from topological waves (cost model: table cost = rows, LPT on k workers) |
| Scalability | Synthetic legacy, 50–2,000 tables | Stage timings, KG size, F1 |
| Sensitivity | Synthetic | F1 vs. α |

## Methods compared

- **Name-only**: naming-convention rules (exact key name, `<table>_id`, role-qualified suffix).
- **Data-only (IND)**: partial inclusion dependencies with coverage and specificity.
- **Fixed-weight fusion**: C = α·H + (1−α)·S.
- **Proposed (adaptive)**: fusion where a name with no signal (H < h0) is treated as neutral; such
  columns are accepted on data evidence only if the inclusion is near-complete and unambiguous.

## Protocol and integrity

- Parameters are tuned **only** on dev seeds 101–103 (`src/tune.py`), frozen in `params.json`.
  Test seeds are 201–205; public schemas are never used for tuning.
- Disclosure: the name-score rule set and the empty-column fallback were refined after inspecting the
  public schemas; the adaptive variant was added after observing low opaque-name recall on the
  first test run. Its parameters were tuned on dev seeds only.
- Determinism: all synthetic data comes from fixed seeds; value sampling is sorted, not random.
  Two full runs under different `PYTHONHASHSEED` values produced identical results (timings excepted).
- Synthetic data plants ~2% orphan rows to mimic legacy data-quality defects, so even the oracle
  plan rejects some rows.

## Limitations

- Legacy naming is simulated by `src/synth.py`; real mainframe catalogs (DB2, VSAM copybooks) are not included.
- Semantic role names (e.g. `ReportsTo → Employee`) are not recovered by any method.
- Parallel speedup is a cost model, not wall-clock time.
- Single-column keys only; composite FKs are not inferred.

## Layout

```
src/kgmig.py            framework: extraction, standardization, detection, KG, planning, migration, validation
src/synth.py            synthetic legacy-schema generator with planted ground truth
src/tune.py             dev-only parameter tuning
src/run_experiments.py  all experiments
src/make_figures.py     figures + tables
src/fetch_data.py       public data download + checksum verification
params.json             frozen parameters
results/                results.json, tables.md, figures
```

Environment used: Python 3.13, NetworkX 3.7, matplotlib 3.11.
