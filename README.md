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
python src/run_experiments.py   # ~15 min; writes results/results.json
python src/make_figures.py      # figures (PNG, 300 dpi) + results/tables.md
```

`python src/tune.py` re-derives `params.json` from the development seeds (optional).

## Datasets

| Dataset name | Source | Tables | Columns | Rows | Ground-truth dependencies | File |
|---|---|---|---|---|---|---|
| Chinook | [lerocha/chinook-database](https://github.com/lerocha/chinook-database) | 11 | 64 | 15,607 | 11 declared FKs | `schemas/chinook.db` |
| Northwind | [jpwhite3/northwind-SQLite3](https://github.com/jpwhite3/northwind-SQLite3) | 13 | 88 | 625,890 | 13 declared FKs | `schemas/northwind.db` |
| Sakila | [bradleygrant/sakila-sqlite3](https://github.com/bradleygrant/sakila-sqlite3) | 16 | 89 | 46,273 | 22 declared FKs | `schemas/sakila.db` |
| TPC-DS (SF 1) | TPC-DS kit ([gregrahn/tpcds-kit](https://github.com/gregrahn/tpcds-kit) @ `5a3a817`) | 24 | 425 | 2,596,789 | 102 FKs from `tpcds_ri.sql` | `schemas/tpcds_sf1.db` |
| SynthModern-100 | `src/synth.py`, seeds 201–205 | 100 each | ~570 each | ~21k each | ~145 planted each | `synth/synth_modern_s201.db` … |
| SynthLegacy-100 | `src/synth.py`, seeds 201–205 | 100 each | ~570 each | ~21k each | ~155 planted each | `synth/synth_legacy_s201.db` … |

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

## Methods compared

- **Name-only**: naming-convention rules (exact key name, `<table>_id`, role-qualified suffix).
- **Data-only (IND)**: partial inclusion dependencies with coverage and specificity.
- **Fixed-weight fusion**: C = α·H + (1−α)·S.
- **Proposed (adaptive)**: fusion in which a name with no signal (H < h0) is treated as neutral; such
  columns are accepted on data evidence only if the inclusion is near-complete and unambiguous.

## Protocol and integrity

- Parameters are tuned **only** on development seeds 101–103 (`src/tune.py`) and frozen in
  `params.json`. Test seeds are 201–205. Chinook, Northwind, Sakila and TPC-DS are never used for tuning;
  TPC-DS was added after tuning and evaluated with the frozen parameters.
- Disclosure: the name-score rule set and the empty-column fallback were refined after inspecting the
  public schemas; the adaptive variant was added after observing low opaque-name recall on the first
  synthetic test run. Its parameters were tuned on development seeds only.
- Determinism: synthetic data comes from fixed seeds; TPC-DS from a fixed generator seed with verified
  checksums; value sampling is sorted, not random. Independent reruns (a different `PYTHONHASHSEED`, and a
  separate machine via GitHub Codespaces) produced identical results apart from wall-clock timings.

## Limitations

- Legacy naming is simulated by `src/synth.py`; real mainframe catalogs (DB2, VSAM copybooks) are not included.
- Semantic role names (e.g. `ReportsTo → Employee`) are not recovered by any method.
- Parallel speedup is a cost model (table cost = rows, LPT scheduling), not wall-clock time.
- Single-column keys only; composite FKs are not inferred.

## Layout

```
src/kgmig.py            framework: extraction, standardization, detection, KG, planning, migration, validation
src/synth.py            synthetic legacy-schema generator with planted ground truth
src/build_tpcds.py      TPC-DS build, checksum verification and load
src/fetch_data.py       public data download + checksum verification
src/tune.py             development-only parameter tuning
src/run_experiments.py  all experiments
src/make_figures.py     figures + tables
params.json             frozen parameters
results/                results.json, tables.md, figures
```
