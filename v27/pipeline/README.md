# Pipeline Layer

## Purpose

`pipeline/` owns orchestration only. It calls data-processing, analysis, model-selection, API acquisition, documentation, and notebook execution in the right order. It should not contain feature construction, regression equations, structural model logic, or endpoint parsing.

## Modules

- `run_all.py`: one-command offline reproduction. It runs local inventory, data processing, variable construction, main analysis, same-DV model-selection extensions, prior-version audit, repo-doc generation, and notebook execution.
- `api_reproduction.py`: optional online API reproduction runner. It calls `api_sources/pipelines/*`, builds an isolated source-assets overlay in `data/api_runs/<run_id>/`, and reruns analysis/model-selection modules against that overlay.
- `repo_docs.py`: regenerates root-level runbook, data/proxy/variable doc, API protocol doc, root README, and report lineage appendix.
- `__init__.py`: package marker.

## Commands

```bash
python -m pipeline.run_all
python -m pipeline.api_reproduction --sources jito-public jito-epochs helius solscan
python -m pipeline.repo_docs
```

