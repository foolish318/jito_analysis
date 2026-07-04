# v27 Architecture

## Target Layer Diagram

```text
                                +-------------------------------+
                                | pipeline/                     |
                                | - run_all.py                  |
                                | - api_reproduction.py         |
                                | - repo_docs.py                |
                                |                               |
                                | Only orchestration lives here:|
                                | call layers, run notebooks,   |
                                | write reproducible outputs.   |
                                +---------------+---------------+
                                                |
               +--------------------------------+--------------------------------+
               |                                                                 |
               v                                                                 v
+-------------------------------+                                 +-------------------------------+
| data_processing/              |                                 | model_selection/              |
| - process.py                  |                                 | - same_dv_iv_extensions.py    |
| - variables.py                |                                 |                               |
|                               |                                 | Chooses and compares IV       |
| source_assets -> processed -> |                                 | blocks under the fixed DV.    |
| variables. No model fitting   |                                 | It can screen proxies and run |
| except reproduction checks.   |                                 | combinations, but cannot      |
+---------------+---------------+                                 | redefine the DV silently.     |
                |                                                 +---------------+---------------+
                |                                                                 |
                v                                                                 v
+---------------------------------------------------------------------------------+
| analysis/                                                                        |
| - data_assembly.py        Build fixed-DV panels and supplemental proxy panels.    |
| - preliminary.py          Data ingestion, coverage, candidate comparisons.        |
| - regression.py           OLS helpers, benchmark/simple regressions, proxy screen.|
| - structural.py           Mechanism attribution, structural diagnostics,          |
|                           counterfactuals.                                       |
| - reporting.py            Workbook, Markdown report, notebooks, dictionaries.    |
| - prior_reproduction.py   Prior-version reproduction audit tables.               |
| - main.py                 Analysis-layer orchestrator, not a shell pipeline.      |
+---------------------------------------------------------------------------------+
```

## Data Flow

```text
data/source_assets/
    -> data_processing/process.py
    -> data/processed/
    -> data_processing/variables.py
    -> data/variables/
    -> analysis/main.py
    -> output/
    -> notebooks/
```

Optional online flow:

```text
pipeline/api_reproduction.py
    -> api_sources/pipelines/*
    -> data/api_runs/<run_id>/api_raw/
    -> data/api_runs/<run_id>/source_assets_overlay/
    -> analysis/main.py + model_selection/same_dv_iv_extensions.py on overlay
```

## Layer Rules

- `data_processing/` owns schema validation, standardization, and variable construction.
- `analysis/` owns empirical analysis outputs: preliminary tables, regressions, mechanism evidence, structural diagnostics, counterfactuals, reports, and notebooks.
- `model_selection/` owns IV-block selection, proxy screening, same-DV comparison, and model-suite ranking. The DV remains `log_mev_per_leader_slot` unless explicitly changed in a documented model-selection experiment.
- `pipeline/` owns orchestration only. It should not contain model equations, feature construction, or API endpoint details.
- `api_sources/` remains the external acquisition layer: providers, parsers, and source-specific API pipelines.

## Compatibility Entry Points

Use the layered modules directly:

```bash
python -m pipeline.run_all
python -m data_processing.process --mode local
python -m data_processing.variables
python -m analysis.main
python -m model_selection.same_dv_iv_extensions
python -m analysis.prior_reproduction
python -m pipeline.repo_docs
```
