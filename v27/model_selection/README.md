# Model Selection Layer

## Purpose

`model_selection/` owns model and variable-selection experiments. It chooses IV blocks, screens proxy candidates, compares same-sample baselines, and ranks alternative fixed-DV specifications. This layer may add or remove independent variables, but it must not silently change the dependent variable.

## Modules

- `same_dv_iv_extensions.py`: builds the same-DV joined panel, z-scores candidate supplemental IVs, runs H7 baseline plus IV-block extensions, records same-sample R2 increments, updates reports/workbooks/notebooks, and writes `output/v27_same_dv_iv_model_suite.csv`.
- `__init__.py`: package marker.

## DV Rule

The default DV is `log_mev_per_leader_slot`. Any experiment that changes the DV must be explicit in the model specification and output metadata. Current v27 production runs keep the DV fixed.

## Command

```bash
python -m model_selection.same_dv_iv_extensions
```

