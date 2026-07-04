# v27 Data, Proxy, and Variable Definitions

## Storage Layout

- Frozen local input snapshots: `data/source_assets/`.
- Standardized data/process audit: `data/processed/`.
- Constructed analysis variables and panels: `data/variables/` plus `data/model_panel.csv`.
- Model outputs and reports: `output/`.
- Optional online API responses: `data/api_raw/`.
- Isolated online reproduction runs: `data/api_runs/<run_id>/`.

## Source Assets

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

## Core DV/IV Discipline

- DV: `log_mev_per_leader_slot`.
- Main benchmark IVs: fixed 66 H7/B10 regressors from `data/source_assets/h7_b10_feature_list.csv`.
- Candidate IV: `candidate_indicator`.
- Supplemental IVs: v22-v25 mechanism scores and additional z-scored proxy blocks. These are added as IVs only; they never redefine the DV.

## Result Lineage

| result | reported_number | dv | iv_block | source_assets | join_key | processing_module | output_file | interpretation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| main benchmark | N=409, R2=0.814967, adj R2=0.779259, candidate coef=0.316263, p=0.001627 | log_mev_per_leader_slot | fixed 66 H7/B10 IVs from h7_b10_feature_list.csv | main_benchmark_model_panel.csv; h7_b10_feature_list.csv; h7_b10_benchmark_run_summary.json | identity_account retained for audit; OLS sample is nonmissing DV + 66 IV rows | data_processing.process -> data_processing.variables -> analysis.main | output/v27_simple_regression_stats.csv; output/v27_main_benchmark_coefficients.csv | canonical benchmark; exact v26 reproduction under fixed DV/IV discipline |
| H7 + four mechanism scores | N=192, R2=0.874588; same-sample H7 R2=0.869763; incremental R2=0.004825 | log_mev_per_leader_slot | 66 H7 IVs + four supplemental mechanism score IVs | v26 source panel + v22/v23/v24 validator panels + v25 50-epoch summary | identity_account; v22-v24 validator renamed to identity_account; v25 already identity_account | data_processing.variables constructs signed z-score mechanism scores; model_selection.same_dv_iv_extensions estimates model | output/v27_same_dv_iv_model_suite.csv; output/v27_mechanism_identification.csv | structural/proxy IV block; compare incremental R2 to same-sample H7, not raw R2 across samples |
| H7 + v25 quality/infra/entity block | N=409, R2=0.825413; incremental R2=0.010445 | log_mev_per_leader_slot | 66 H7 IVs + v25 non-MEV-history quality/infra/entity IVs | validator_epoch_mev_bam_summary_50epoch.csv plus v26 source panel | identity_account | data_processing.process standardizes v25; model_selection.same_dv_iv_extensions z-scores IVs and estimates | output/v27_same_dv_iv_model_suite.csv | same-DV operational quality/infra/entity extension; not a changed outcome |
| H7 + v25 MEV-history predictive block | N=409, R2=0.829025; incremental R2=0.014058 | log_mev_per_leader_slot | 66 H7 IVs + v25 MEV-history/persistence IVs | validator_epoch_mev_bam_summary_50epoch.csv plus v26 source panel | identity_account | model_selection.same_dv_iv_extensions | output/v27_same_dv_iv_model_suite.csv | predictive check only; not causal mechanism proof because IVs are MEV-history proxies |
| top5 mechanism screened proxies | N=134, R2=0.914683; same-sample H7 R2=0.903137; incremental R2=0.011547 | log_mev_per_leader_slot | 66 H7 IVs + top five screened mechanism proxy IVs excluding obvious MEV-history variables | v22/v24/v25 proxy fields plus v26 source panel | identity_account with stricter nonmissing proxy sample | analysis.main single proxy screen -> model_selection.same_dv_iv_extensions | output/v27_single_proxy_screen.csv; output/v27_same_dv_iv_model_suite.csv | exploratory; high raw R2 partly reflects smaller high-coverage sample |

## Same-DV IV Model Suite

| model | n | r_squared | adj_r_squared | baseline_h7_same_sample_r_squared | incremental_r2_vs_h7_same_sample | candidate_coef | candidate_p_value |
| --- | --- | --- | --- | --- | --- | --- | --- |
| same_dv_H7_v26_full_sample | 409 | 0.814967 | 0.779259 | 0.814967 | 0 | 0.316263 | 0.00162687 |
| same_dv_H7_plus_supp_private_orderflow_searcherflow_score | 192 | 0.870137 | 0.80157 | 0.869763 | 0.000374571 | 0.296169 | 0.0281262 |
| same_dv_H7_plus_supp_bundle_outcome_execution_score | 409 | 0.815063 | 0.778727 | 0.814967 | 9.58183e-05 | 0.318793 | 0.00163754 |
| same_dv_H7_plus_supp_latency_infra_reliability_score | 409 | 0.816393 | 0.780318 | 0.814967 | 0.00142575 | 0.305613 | 0.00242392 |
| same_dv_H7_plus_supp_entity_vertical_integration_score | 409 | 0.814971 | 0.778616 | 0.814967 | 3.39716e-06 | 0.315825 | 0.00166168 |
| same_dv_H7_plus_all_four_mechanism_scores | 192 | 0.874588 | 0.803658 | 0.869763 | 0.00482527 | 0.292777 | 0.0386025 |
| same_dv_H7_plus_v25_quality_infra_entity_block | 409 | 0.825413 | 0.785447 | 0.814967 | 0.0104455 | 0.308079 | 0.0024433 |
| same_dv_H7_plus_v25_mev_history_predictive_block | 409 | 0.829025 | 0.792388 | 0.814967 | 0.014058 | 0.273101 | 0.0132979 |
| same_dv_H7_plus_v22_public_orderflow_block | 192 | 0.873145 | 0.796392 | 0.869763 | 0.00338219 | 0.257782 | 0.0963374 |
| same_dv_H7_plus_top5_all_screened_proxy_IVs | 192 | 0.879783 | 0.810237 | 0.869763 | 0.0100207 | 0.0781816 | 0.640665 |
| same_dv_H7_plus_top5_mechanism_screened_proxy_IVs | 134 | 0.914683 | 0.822702 | 0.903137 | 0.0115469 | 0.0450046 | 0.830761 |
