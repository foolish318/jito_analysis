# v27 Jito Structural Analysis Reproduction

This folder is intended to be a self-contained reproduction package for the v27 analysis.

Default reproduction uses local snapshots in `data/source_assets/`. Optional standard-source online refreshes are available through `python -m api_sources.pipelines.local_inventory`; isolated online acquisition plus overlay-model reproduction is available through `pipeline.api_reproduction`. The implementation is organized under `api_sources/` by provider, parser, and pipeline. Exact reproduction should use the frozen snapshots.

Key benchmark: DV `log_mev_per_leader_slot`, N=409, R2=0.8149674041398512, candidate coefficient=0.3162628017069881, p=0.0016268736700554615.

Run:

```bash
cd /path/to/v27
python -m pipeline.run_all
```

## Directory Documentation

Each production directory has its own README:

- `api_sources/README.md`: API acquisition layer contract.
- `api_sources/providers/README.md`: endpoint-builder modules.
- `api_sources/parsers/README.md`: response parsing and feature construction.
- `api_sources/pipelines/README.md`: runnable acquisition jobs and their outputs.
- `data/README.md`: data-layer flow from frozen sources to model variables.
- `data/source_assets/README.md`: frozen input file meanings.
- `data/processed/README.md`: standardized intermediate tables and manifests.
- `data/variables/README.md`: model-ready panels, DV/IV definitions, and variable dictionaries.
- `data/api_raw/README.md`: current local API/inventory summaries.
- `data/api_runs/README.md`: isolated online reproduction archives.
- `notebooks/README.md`: reporting notebooks.
- `output/README.md`: generated result artifacts.

## Layered Entry Points

- `pipeline.run_all`: one-command offline reproduction entry. It runs local inventory, processing, variable construction, analysis, model selection, prediction validation, documentation, and notebook execution.
- `data_processing.process`: validates `data/source_assets/`, checks required schemas, writes manifests, and standardizes selected source tables into `data/processed/`.
- `data_processing.variables`: reads processed tables, constructs benchmark panels, supplemental proxies, mechanism scores, and variable dictionaries in `data/variables/`.
- `analysis.main`: main empirical runner. It reproduces the fixed-DV benchmark, builds ingestion/proxy/evidence tables, runs preliminary analysis, simple regressions, mechanism identification, structural analysis, and counterfactuals.
- `model_selection.same_dv_iv_extensions`: same-DV extension runner. It keeps `log_mev_per_leader_slot` fixed and compares added IV blocks against same-sample H7 baselines.
- `analysis.prediction`: out-of-sample validation runner. It evaluates fixed-DV models with deterministic folds, nested proxy screening, RMSE/MAE/error quantiles, percent-error transforms, and calibration bins.
- `analysis.prior_reproduction`: audit runner for reproduced prior-version data/result/mechanism/counterfactual tables inside v27.
- `pipeline.api_reproduction`: optional online API runner. It creates an isolated API run, builds a source-assets overlay, and reruns same-DV model scripts without changing frozen inputs.
- `pipeline.repo_docs`: regenerates root-level runbook/data/API documentation and appends lineage to the main report.



Result lineage:

| result | reported_number | source_assets | output_file | interpretation |
| --- | --- | --- | --- | --- |
| main benchmark | N=409, R2=0.814967, adj R2=0.779259, candidate coef=0.316263, p=0.001627 | main_benchmark_model_panel.csv; h7_b10_feature_list.csv; h7_b10_benchmark_run_summary.json | output/v27_simple_regression_stats.csv; output/v27_main_benchmark_coefficients.csv | canonical benchmark; exact v26 reproduction under fixed DV/IV discipline |
| H7 + four mechanism scores | N=192, R2=0.874588; same-sample H7 R2=0.869763; incremental R2=0.004825 | v26 source panel + v22/v23/v24 validator panels + v25 50-epoch summary | output/v27_same_dv_iv_model_suite.csv; output/v27_mechanism_identification.csv | structural/proxy IV block; compare incremental R2 to same-sample H7, not raw R2 across samples |
| H7 + v25 quality/infra/entity block | N=409, R2=0.825413; incremental R2=0.010445 | validator_epoch_mev_bam_summary_50epoch.csv plus v26 source panel | output/v27_same_dv_iv_model_suite.csv | same-DV operational quality/infra/entity extension; not a changed outcome |
| H7 + v25 MEV-history predictive block | N=409, R2=0.829025; incremental R2=0.014058 | validator_epoch_mev_bam_summary_50epoch.csv plus v26 source panel | output/v27_same_dv_iv_model_suite.csv | predictive check only; not causal mechanism proof because IVs are MEV-history proxies |
| top5 mechanism screened proxies | N=134, R2=0.914683; same-sample H7 R2=0.903137; incremental R2=0.011547 | v22/v24/v25 proxy fields plus v26 source panel | output/v27_single_proxy_screen.csv; output/v27_same_dv_iv_model_suite.csv | exploratory; high raw R2 partly reflects smaller high-coverage sample |

Online API runner:

```bash
cd /home/yimo/jito_analysis/v27
python -m pipeline.api_reproduction --run-id api_smoke_20260702_v18_audit --bundle-limit 20 --address-limit 5 --signature-limit 10 --getblock-limit 20 --tip-limit 20 --epoch-start 991 --epoch-end 992 --dune-max-wait-sec 30
```

The validated smoke output is in `data/api_runs/api_smoke_20260702_v18_audit/`; legacy v15-v19 endpoint smoke output is in `data/api_runs/api_legacy_smoke_20260702/`. For full v18 online regeneration use `--getblock-limit 500 --tip-limit 423`; for the v25 window use `--epoch-start 943 --epoch-end 992`.

Full refactor validation output is in `data/api_runs/api_refactor_full_validation_20260702/`; the audit report is `output/v27_api_refactor_full_validation_report.md`. This all-source run regenerated v18 500/423 slot features, refreshed the v25 50-epoch window, and reproduced the main overlay benchmark at R2 `0.8149674041398512`. Solscan account detail remains permission-blocked by the current key.
