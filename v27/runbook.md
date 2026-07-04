# v27 Runbook

## Purpose

v27 is organized as a self-contained reproduction folder. The default pipeline reads frozen local input snapshots from `data/source_assets/`, processes them, builds variables, runs the same-DV model suite, runs out-of-sample prediction validation, and executes the notebooks.

DV is fixed as `log_mev_per_leader_slot`. The pipeline may add or compare IV blocks, but it does not change the dependent variable.

## One-command Full Run

```bash
cd /path/to/v27
python -m pipeline.run_all
```

Inside the current machine the equivalent command is:

```bash
cd /home/yimo/jito_analysis/v27
python -m pipeline.run_all
```

## Expanded Run

```bash
cd /home/yimo/jito_analysis/v27
python -m api_sources.pipelines.local_inventory
python -m data_processing.process --mode local
python -m data_processing.variables
python -m analysis.main
python -m model_selection.same_dv_iv_extensions
python -m pipeline.repo_docs
jupyter nbconvert --to notebook --execute notebooks/analysis.ipynb --output analysis.ipynb --output-dir notebooks
jupyter nbconvert --to notebook --execute notebooks/report.ipynb --output report.ipynb --output-dir notebooks
```

## Optional Online Data Refresh

Default reproduction does not call APIs. To refresh standard source inputs only, create `v27/.env.local` from `.env.example`, then run the source-like pipeline module:

```bash
cd /home/yimo/jito_analysis/v27
python -m pipeline.api_reproduction --sources jito-public jito-epochs helius solscan
```

This writes online responses to `data/api_raw/`. Add `--write-source-assets` only if you intentionally want to overwrite the frozen local snapshots and rerun a refreshed analysis.

## Online API Reproduction Runner

For an isolated online pull plus model overlay, use `pipeline.api_reproduction`. It writes into `data/api_runs/<run_id>/` and does not overwrite frozen `data/source_assets/`. It reads keys from `v27/.env.local`, parent `.env.local`, and simple `KEY=VALUE` entries in `../api_key.md`; keys are not printed in manifests.

Smoke command validated on this machine:

```bash
cd /home/yimo/jito_analysis/v27
python -m pipeline.api_reproduction   --run-id api_smoke_20260702_v18_audit   --bundle-limit 20   --address-limit 5   --signature-limit 10   --getblock-limit 20   --tip-limit 20   --epoch-start 991   --epoch-end 992   --dune-max-wait-sec 30
```


Full v18-style online regeneration uses the historical v18 slot manifests now stored in `data/source_assets/`:

```bash
cd /home/yimo/jito_analysis/v27
python -m pipeline.api_reproduction   --run-id api_full_v18_v25_refresh   --sources all   --bundle-limit 1000   --address-limit 30   --signature-limit 100   --getblock-limit 500   --tip-limit 423   --epoch-start 943   --epoch-end 992   --dune-max-wait-sec 240
```

The full command can be slow and API-rate-limit sensitive. Public APIs that expose only live/recent windows cannot guarantee byte-identical historical samples. Exact model reproduction therefore remains the frozen local path; the online runner verifies acquisition, schema, joins, and same-DV overlay behavior.

## Refactor Full API Validation

The refactored API structure was validated with a non-smoke all-source run:

```bash
cd /home/yimo/jito_analysis/v27
python -m pipeline.api_reproduction   --run-id api_refactor_full_validation_20260702   --sources all   --bundle-limit 200   --address-limit 30   --signature-limit 100   --getblock-limit 500   --tip-limit 423   --epoch-start 943   --epoch-end 992   --legacy-epoch-start 992   --legacy-epoch-end 992   --leader-limit 50   --dune-max-wait-sec 240
```

Validated output:

- Run directory: `data/api_runs/api_refactor_full_validation_20260702/`.
- Audit report: `output/v27_api_refactor_full_validation_report.md`.
- Main overlay benchmark: N=409, R2=0.8149674041398512, adjusted R2=0.7792593593247348.
- Full v18 regeneration: 500/500 Solana `getBlock` slots and 423/423 tip-flow slots available.
- v25 Jito epoch window: 50 epochs, 36,122 validator-epoch rows, 788 validator summary rows.
- - Helius and Dune succeeded; Solscan account detail remains permission-blocked by the current key.
- Jito public bundle detail/event live API returned some HTTP 429s; output still materialized 199 bundle rows and 6116 lifecycle event rows.

## End-to-end Checks

- Main benchmark status vs v26 snapshot: `PASS`.
- Main benchmark R2: `0.8149674041398512`.
- Main benchmark N: `409`.
- Main benchmark DV: `log_mev_per_leader_slot`.
- Main benchmark IVs: fixed 66 H7/B10 regressors from `data/source_assets/h7_b10_feature_list.csv`.
- Same-DV IV extension output: `output/v27_same_dv_iv_model_suite.csv`.
- Prediction validation output: `output/v27_prediction_model_performance.csv`.

## Main Outputs

- `output/v27_report.md`
- `output/v27_analysis_workbook.xlsx`
- `output/v27_result_lineage.csv`
- `output/v27_same_dv_iv_model_suite.csv`
- `output/v27_simple_regression_stats.csv`
- `output/v27_mechanism_identification.csv`
- `output/v27_structural_model_stats.csv`
- `output/v27_counterfactuals.csv`
- `output/v27_prediction_model_performance.csv`
- `output/v27_prediction_fold_results.csv`
- `output/v27_prediction_selected_features.csv`
- `output/v27_prediction_calibration.csv`
- `output/v27_prediction_row_predictions.csv`
- `output/v27_prediction_summary.json`
- `output/v27_prediction_rank_bucket_metrics.csv`
- `output/v27_prediction_panel_lag_performance.csv`
- `output/v27_prediction_panel_lag_predictions.csv`
- `notebooks/analysis.ipynb`
- `notebooks/report.ipynb`
