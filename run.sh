#!/bin/sh
# Full pipeline: source database + upstream downloads -> results.
# Deterministic and safe to re-run. Each stage writes a provenance record to
# outputs/provenance/ and appends to outputs/audit.log; s09 verifies the chain.
set -e
cd "$(dirname "$0")"
PY=${PY:-.venv/bin/python}
rm -f outputs/audit.log
$PY s01_extract.py
$PY s02_fetch.py
$PY s03_locate.py
$PY s04_units.py
$PY s05_blocks.py
$PY s06_census.py
$PY s07_analyze.py
$PY s08_map.py
$PY s10_districts.py
$PY s11_district_analysis.py
$PY s09_provenance.py
echo "done: outputs/results.md, outputs/results_districts.md, outputs/map.html, PROVENANCE.md, outputs/audit.log"
