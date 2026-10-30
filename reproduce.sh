#!/usr/bin/env bash
# Full reproduction: data, experiments, migration-critical analysis, figures, comparison.
set -euo pipefail
cp results/results.json /tmp/published_results.json
pip install -r requirements-lock.txt
python src/fetch_data.py
python src/build_tpcds.py
pytest -q
python src/run_experiments.py
python src/critical.py
python src/make_figures.py
python src/compare_results.py /tmp/published_results.json results/results.json
