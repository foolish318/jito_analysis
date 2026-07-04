# v27 API Data Protocol and Join

## Default Protocol: Local Snapshot Reproduction

The default v27 reproduction does not call external APIs. It reads frozen input snapshots from `data/source_assets/`, validates their schemas through `data_processing.process`, builds variables through `data_processing.variables`, runs analysis/model-selection modules, and runs out-of-sample prediction validation.

## Optional Protocol: Online Refresh

Use `python -m api_sources.pipelines.local_inventory` only when you want to refresh standard source inputs from APIs:

```bash
cd /home/yimo/jito_analysis/v27
cp .env.example .env.local
# fill keys if using Solscan/Helius/Dune
python -m pipeline.api_reproduction --sources jito-public jito-epochs helius solscan
```

Online outputs go to `data/api_raw/`. Use `--write-source-assets` only after inspecting the API outputs, because it overwrites the frozen snapshots used for exact reproduction.

## API Module Layout

The online acquisition layer is split under `api_sources/`:

- `api_sources/providers/`: one file per API family (`jito.py`, `solana_rpc.py`, `bam.py`, `helius.py`, `solscan.py`, `dune.py`, `validator_metadata.py`). These files define endpoint builders and keep endpoint names in one place.
- `api_sources/parsers/`: response parsers. `solana_block.py` converts Solana `getBlock` responses and Jito tip-account balance deltas into v18 `tx_*` and `tip_*` variables.
- `api_sources/pipelines/`: runnable acquisition jobs. `jito_bundles.py` refreshes v22 public bundle tables, `jito_epoch_bam.py` refreshes the v25 Jito+BAM 50-epoch summary, `solana_block_tip_features.py` regenerates v18 slot features.
- Top-level API orchestration stays in `pipeline.api_reproduction`; default local reproduction calls `python -m api_sources.pipelines.local_inventory`.

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

## API Reproduction Run Output

The full API runner is `pipeline.api_reproduction`. It calls `api_sources.pipelines.local_inventory` for Jito bundle, Jito+BAM epoch, Helius, and Solscan pulls, adds v16-v18/v23 no-key and keyed sources, builds a source-assets overlay, and reruns the v27 models under the fixed DV.

Validated smoke run:

```text
data/api_runs/api_smoke_20260702_v18_audit/
```

Key outputs:

- `api_reproduction_summary.json`: online fetch and model summary.
- `api_overlay_promotion.csv`: which online files replaced frozen overlay copies.
- `api_module_coverage.csv`: implemented API modules and their roles.
- `api_raw/solana_block_tip_features/solana_block_features_online.csv`: regenerated v18 `tx_*` slot features from Solana `getBlock`.
- `api_raw/solana_block_tip_features/jito_tip_account_flow_features_online.csv`: regenerated v18 `tip_*` slot features from Jito `getTipAccounts` plus Solana balance deltas.
- `output/run_summary.json`: same-DV model results on the overlay.

The smoke run confirmed 20/20 v18 `getBlock` slots, 20/20 v18 tip-flow slots, 8 Jito tip accounts, 10 Helius enhanced transaction rows, 30 Dune sample rows, and a main benchmark overlay reproduction with R2 `0.8149674041398512`. The legacy smoke output is `data/api_runs/api_legacy_smoke_20260702/`; it confirmed 10/10 v15-v19 requests, including Solana `getLeaderSchedule`, Jito daily/validator/staker rewards, and BAM IBRL validators/blocks.

## API Sources Implemented

- Jito public bundle API: `https://bundles.jito.wtf/api/v1/bundles` for landed bundle, bundle event, validator bundle-summary, and tipper-validator edge data.
- Jito epoch API: `https://kobe.mainnet.jito.network/api/v1` for validator and MEV epoch data used to refresh v25-style 50-epoch summaries.
- Helius enhanced/address history API: optional enrichment, requires `HELIUS_API_KEY`.
- Solscan Pro account API: optional account metadata enrichment, requires `SOLSCAN_API_KEY`.
- Solana JSON-RPC `getBlock`: v18 sampled slot execution, fee, compute, program-mix, and fee-payer concentration features.
- Jito block-engine `getTipAccounts`: v18 tip-account list, joined to Solana `getBlock` pre/post balance deltas for tip-flow features.
- Solana JSON-RPC metadata: `getSlot`, `getEpochInfo`, `getClusterNodes`, `getVoteAccounts`, `getBlockProduction`, `getLeaderSchedule`.
- Jito/Kobe legacy GET endpoints: `validator_rewards`, `daily_mev_rewards`, and sampled `staker_rewards`.
- BAM/IBRL validator endpoint: `https://explorer.bam.dev/api/v1/ibrl_validators`, used by `jito_epoch_bam.py` for the v25 50-epoch summary.
- Stakewiz and Validators.app: no-key validator metadata for entity/operator/client/infrastructure proxies.
- Dune API: direct smoke samples for Solana transactions, blocks, and instruction calls, requires `DUNE_API_KEY`.

## Join Protocol

- v26 benchmark source panel key: `identity_account`; `vote_account` retained for audit.
- v22/v23/v24 validator-level files expose validator identity as `validator`; `data_processing.process` standardizes this to `identity_account`.
- v25 50-epoch summary already uses `identity_account`.
- Models compare R2 using the same DV, and same-sample comparisons use `baseline_h7_same_sample_r_squared`.

## Frozen Source Inventory

| file | relative_path | size_bytes |
| --- | --- | --- |
| h7_b10_benchmark_run_summary.json | data/source_assets/h7_b10_benchmark_run_summary.json | 437 |
| h7_b10_feature_list.csv | data/source_assets/h7_b10_feature_list.csv | 2587 |
| h7_b10_model_specification.csv | data/source_assets/h7_b10_model_specification.csv | 853 |
| jito_public_bundle_events.csv | data/source_assets/jito_public_bundle_events.csv | 6211777 |
| jito_public_bundles.csv | data/source_assets/jito_public_bundles.csv | 1023082 |
| jito_public_tipper_validator_edges.csv | data/source_assets/jito_public_tipper_validator_edges.csv | 466949 |
| jito_public_validator_orderflow_scores.csv | data/source_assets/jito_public_validator_orderflow_scores.csv | 72964 |
| jito_tip_account_flow_features_snapshot.csv | data/source_assets/jito_tip_account_flow_features_snapshot.csv | 88318 |
| jito_tip_account_slot_manifest.csv | data/source_assets/jito_tip_account_slot_manifest.csv | 26471 |
| main_benchmark_model_panel.csv | data/source_assets/main_benchmark_model_panel.csv | 4219119 |
| mechanism_identification_attribution.csv | data/source_assets/mechanism_identification_attribution.csv | 2412 |
| observable_proxy_regression_model_stats.csv | data/source_assets/observable_proxy_regression_model_stats.csv | 3630 |
| observable_proxy_validator_score_panel.csv | data/source_assets/observable_proxy_validator_score_panel.csv | 786139 |
| online_source_lineage_audit.csv | data/source_assets/online_source_lineage_audit.csv | 1561 |
| solana_block_features_snapshot.csv | data/source_assets/solana_block_features_snapshot.csv | 322443 |
| solana_block_slot_manifest.csv | data/source_assets/solana_block_slot_manifest.csv | 46233 |
| structural_counterfactual_estimates.csv | data/source_assets/structural_counterfactual_estimates.csv | 1086 |
| structural_mechanism_attribution.csv | data/source_assets/structural_mechanism_attribution.csv | 870 |
| structural_model_fit_stats.csv | data/source_assets/structural_model_fit_stats.csv | 1652 |
| structural_sequential_model_ladder.csv | data/source_assets/structural_sequential_model_ladder.csv | 430 |
| structural_validator_mechanism_score_panel.csv | data/source_assets/structural_validator_mechanism_score_panel.csv | 767117 |
| validator_epoch_mev_bam_mechanism_attribution.csv | data/source_assets/validator_epoch_mev_bam_mechanism_attribution.csv | 557 |
| validator_epoch_mev_bam_panel_50epoch.csv | data/source_assets/validator_epoch_mev_bam_panel_50epoch.csv | 19100471 |
| validator_epoch_mev_bam_regression_stats.csv | data/source_assets/validator_epoch_mev_bam_regression_stats.csv | 995 |
| validator_epoch_mev_bam_summary_50epoch.csv | data/source_assets/validator_epoch_mev_bam_summary_50epoch.csv | 375467 |
