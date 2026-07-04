# Data Processing Layer

## Purpose

`data_processing/` owns deterministic local data preparation. It reads frozen source files from `data/source_assets/`, validates schemas, standardizes selected tables, and builds model-ready variable panels. This layer should not run empirical model suites except for narrow reproduction checks that validate variable construction.

## Modules

- `process.py`: validates required source assets, records row/column/schema manifests, standardizes join keys, and writes `data/processed/`.
- `variables.py`: reads processed/local panels, copies canonical variable panels into `data/variables/`, builds variable dictionaries and construction summaries.
- `__init__.py`: package marker.

## Upstream and Downstream

```text
data/source_assets/ -> process.py -> data/processed/ -> variables.py -> data/variables/
```

Downstream modules in `analysis/` and `model_selection/` consume `data/variables/` and selected compatibility copies in `data/`.

## Commands

```bash
python -m data_processing.process --mode local
python -m data_processing.variables
```

