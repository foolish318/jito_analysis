# Analysis Layer

## Purpose

`analysis/` owns empirical analysis after model-ready variables exist. It produces preliminary tables, regression outputs, mechanism evidence, structural diagnostics, counterfactuals, reports, workbooks, notebooks, and prior-version reproduction audits.

## Modules

- `data_assembly.py`: shared constants, source registry, path setup, OLS helpers, fixed-DV panel construction, supplemental proxy joins, and mechanism score construction.
- `preliminary.py`: candidate/non-candidate descriptive comparisons, v22-v25 ingestion manifests, source coverage, proxy catalog, preliminary source-layer summaries, and mechanism evidence matrix construction.
- `regression.py`: simple regression suite and single-proxy screening under the fixed DV.
- `structural.py`: mechanism identification, sequential structural ladder, structural model diagnostics, existing structural audit, and counterfactual analysis.
- `reporting.py`: variable dictionary, workbook writer, Markdown report writer, and notebook writer.
- `prior_reproduction.py`: independent audit that reproduces prior-version data/result/mechanism/counterfactual tables from v27 source assets.
- `main.py`: analysis-layer orchestrator. It composes the modules above and writes the core reproducible outputs.

## Flow

```text
data/variables/ + data/source_assets/
    -> data_assembly.py
    -> preliminary.py
    -> regression.py
    -> structural.py
    -> reporting.py
    -> output/ and notebooks/
```

## Commands

```bash
python -m analysis.main
python -m analysis.prediction
python -m analysis.prior_reproduction
```

