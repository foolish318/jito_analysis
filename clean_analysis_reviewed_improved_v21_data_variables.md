# clean_analysis_reviewed_improved_v21 data variables and mechanism attribution

This document is the v21 **processing / interpretation** companion. The separate API/acquisition companion is `clean_analysis_reviewed_improved_v21_api_acquisition.md`.

## 1. What v21 adds

v19 already had many variables and a high-R² benchmark. The remaining problem was not missing feature construction, but missing **feature-to-mechanism attribution**.

v21 therefore repackages the existing v19 proxy set into four mechanism modules:

1. Latency / infra / reliability
2. Private order-flow / searcher-flow
3. Bundle outcome / landed execution
4. Entity / vertical integration

For each module, v21 reports:

- existing proxies used in H7;
- module-only R² from the opportunity baseline;
- incremental R² after the stake-entrenchment baseline;
- candidate coefficient attenuation;
- drop-one ablation from the full benchmark;
- what we can and cannot claim.

## 2. Benchmark

- Benchmark N: **411**
- Benchmark R²: **0.816**
- Benchmark adjusted R²: **0.781**
- Benchmark candidate coefficient: **0.316**
- Stake baseline R² before four mechanism modules: **0.702**

The benchmark remains high, but v21 is deliberately conservative: these are observable proxies, not direct proof of causal mechanisms.

## 3. Mechanism attribution summary

| mechanism | n_H7_variables | module_only_r_squared | add_to_stake_baseline_r_squared | incremental_r2_vs_stake_baseline | candidate_attenuation_vs_stake_baseline | r2_loss_when_dropped_from_full | evidence_strength | status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Latency / infra / reliability | 11 | 0.3464 | 0.7416 | 0.0393 | -0.0205 | 0.0116 | partial / indirect | partially tested |
| Private order-flow / searcher-flow | 18 | 0.5007 | 0.7658 | 0.0635 | -0.1030 | 0.0310 | strongest among available proxies | strongest current proxy family |
| Bundle outcome / landed execution | 18 | 0.3503 | 0.7475 | 0.0451 | -0.5246 | 0.0143 | partial / landed-only | partially tested |
| Entity / vertical integration | 6 | 0.2510 | 0.7195 | 0.0171 | 0.0965 | 0.0131 | weak / suggestive | weak proxy only |

## 4. Candidate attenuation summary

| mechanism | n_H7_variables | module_only_r_squared | add_to_stake_baseline_r_squared | incremental_r2_vs_stake_baseline | candidate_attenuation_vs_stake_baseline | r2_loss_when_dropped_from_full | candidate_change_when_dropped | evidence_strength |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Latency / infra / reliability | 11 | 0.3464 | 0.7416 | 0.0393 | -0.0205 | 0.0116 | 0.0227 | partial / indirect |
| Private order-flow / searcher-flow | 18 | 0.5007 | 0.7658 | 0.0635 | -0.1030 | 0.0310 | -0.0251 | strongest among available proxies |
| Bundle outcome / landed execution | 18 | 0.3503 | 0.7475 | 0.0451 | -0.5246 | 0.0143 | -0.1305 | partial / landed-only |
| Entity / vertical integration | 6 | 0.2510 | 0.7195 | 0.0171 | 0.0965 | 0.0131 | 0.0793 | weak / suggestive |

## 5. What each mechanism can and cannot support

| mechanism | can_say | cannot_say | missing_data_needed |
| --- | --- | --- | --- |
| Latency / infra / reliability | Latency-like, colocation/network, build-time, and reliability proxies are included; they test infrastructure/operational channels indirectly. | No raw relay-arrival timestamp or true network latency; cannot prove raw latency advantage. | raw latency, relay arrival timestamp, p95/p99 propagation delay, bundle arrival timestamp, leader region/data center ground truth |
| Private order-flow / searcher-flow | Tip-flow intensity and payer concentration explain part of the order-flow/searcher-flow channel in landed blocks. | Cannot identify private searcher relationships or true searcher identity without bundle/searcher mapping. | searcher identity, bundle IDs, repeated searcher-validator pairings, private flow contracts |
| Bundle outcome / landed execution | Observed landed block execution characteristics are tested via fees, compute, tx/program composition, and packing/IBRL proxies. | Cannot explain rejected bundles or full auction inclusion outcome without historical bundle archive. | submitted/landed/rejected bundle IDs, bundle failure rate, landed/submitted value ratio |
| Entity / vertical integration | External name, client/software, Jito flag, operator hints, and metadata provide weak affiliation/integration proxies. | Cannot prove vertical integration or ownership/commercial relationships. | validator-operator mapping, RPC/searcher/block-builder ownership, commercial relationship data |

## 6. Proxy-to-mechanism map

| module_label | raw_proxy | source_family | v19_mechanism_group | role |
| --- | --- | --- | --- | --- |
| Opportunity baseline | candidate_indicator | base/opportunity | base/opportunity controls | candidate residual edge |
| Opportunity baseline | log_active_stake | base/opportunity | base/opportunity controls | baseline/opportunity |
| Opportunity baseline | log_scheduled_slots | base/opportunity | base/opportunity controls | baseline/opportunity |
| Stake-side entrenchment baseline | v16_staker_log_total_reward | v16 benchmark | Full staker concentration | stake baseline control |
| Bundle outcome / landed execution | v16_detail_tick_cu_hhi_mean | v16 benchmark | Multi-block BAM detail flow/timing | mechanism proxy |
| Stake-side entrenchment baseline | v16_staker_full_total_reward_lamports | v16 benchmark | Full staker concentration | stake baseline control |
| Private order-flow / searcher-flow | v16_detail_maker_tick_hhi_mean | v16 benchmark | Multi-block BAM detail flow/timing | mechanism proxy |
| Latency / infra / reliability | v16_holdout_avg_bam_connection_rate | v16 benchmark | Production and skip operational proxies | mechanism proxy |
| Private order-flow / searcher-flow | v16_detail_high_maker_share_block_mean | v16 benchmark | Multi-block BAM detail flow/timing | mechanism proxy |
| Private order-flow / searcher-flow | v16_detail_maker_tick_hhi_max | v16 benchmark | Multi-block BAM detail flow/timing | mechanism proxy |
| Stake-side entrenchment baseline | v16_staker_log_full_rows | v16 benchmark | Full staker concentration | stake baseline control |
| Stake-side entrenchment baseline | v16_staker_reward_gini_full | v16 benchmark | Full staker concentration | stake baseline control |
| Private order-flow / searcher-flow | v16_detail_maker_plugin_share_nonvote_max | v16 benchmark | Multi-block BAM detail flow/timing | mechanism proxy |
| Latency / infra / reliability | v16_detail_block_build_ms_mean | v16 benchmark | Multi-block BAM detail flow/timing | mechanism proxy |
| Bundle outcome / landed execution | v16_detail_tick_cu_hhi_max | v16 benchmark | Multi-block BAM detail flow/timing | mechanism proxy |
| Bundle outcome / landed execution | v16_detail_tick_nonvote_hhi_max | v16 benchmark | Multi-block BAM detail flow/timing | mechanism proxy |
| Private order-flow / searcher-flow | v16_detail_maker_plugin_share_nonvote_mean | v16 benchmark | Multi-block BAM detail flow/timing | mechanism proxy |
| Bundle outcome / landed execution | v16_detail_cu_per_nonvote_tx_mean | v16 benchmark | Multi-block BAM detail flow/timing | mechanism proxy |
| Bundle outcome / landed execution | v16_detail_cu_per_tick_mean | v16 benchmark | Multi-block BAM detail flow/timing | mechanism proxy |
| Bundle outcome / landed execution | v16_detail_early50_cu_share_mean | v16 benchmark | Multi-block BAM detail flow/timing | mechanism proxy |
| Bundle outcome / landed execution | v16_detail_early25_cu_share_mean | v16 benchmark | Multi-block BAM detail flow/timing | mechanism proxy |
| Latency / infra / reliability | v16_holdout_jito_directed_target_rate | v16 benchmark | Production and skip operational proxies | mechanism proxy |
| Bundle outcome / landed execution | v16_detail_ibrl_score_std | v16 benchmark | Multi-block BAM detail flow/timing | mechanism proxy |
| Private order-flow / searcher-flow | v16_detail_maker_tx_share_mean | v16 benchmark | Multi-block BAM detail flow/timing | mechanism proxy |
| Stake-side entrenchment baseline | v16_staker_zero_reward_share_full | v16 benchmark | Full staker concentration | stake baseline control |
| Stake-side entrenchment baseline | v16_stake_authority_hhi_full | v16 benchmark | Full staker concentration | stake baseline control |
| Bundle outcome / landed execution | v16_detail_ibrl_score_min | v16 benchmark | Multi-block BAM detail flow/timing | mechanism proxy |
| Private order-flow / searcher-flow | v16_detail_maker_plugin_share_nonvote_std | v16 benchmark | Multi-block BAM detail flow/timing | mechanism proxy |
| Bundle outcome / landed execution | v16_detail_high_tick_cu_concentration_block_mean | v16 benchmark | Multi-block BAM detail flow/timing | mechanism proxy |
| Private order-flow / searcher-flow | v16_detail_maker_tick_hhi_std | v16 benchmark | Multi-block BAM detail flow/timing | mechanism proxy |
| Latency / infra / reliability | v16_block_production_rate_std | v16 benchmark | Production and skip operational proxies | mechanism proxy |
| Private order-flow / searcher-flow | v16_detail_early25_maker_share_mean | v16 benchmark | Multi-block BAM detail flow/timing | mechanism proxy |
| Latency / infra / reliability | v16_total_skipped_slots | v16 benchmark | Production and skip operational proxies | mechanism proxy |
| Other control | v16_total_blocks_produced | v16 benchmark | Production and skip operational proxies | mechanism proxy |
| Stake-side entrenchment baseline | v16_same_stake_withdraw_authority_share | v16 benchmark | Full staker concentration | stake baseline control |
| Private order-flow / searcher-flow | v16_detail_maker_tx_share_max | v16 benchmark | Multi-block BAM detail flow/timing | mechanism proxy |
| Other control | v16_log_total_blocks_produced | v16 benchmark | Production and skip operational proxies | mechanism proxy |
| Latency / infra / reliability | v16_detail_block_build_ms_std | v16 benchmark | Multi-block BAM detail flow/timing | mechanism proxy |
| Entity / vertical integration | vapp_va_client_is_rakurai | v17 external API | External client/software proxies | mechanism proxy |
| Entity / vertical integration | vapp_va_client_is_frankendancer | v17 external API | External client/software proxies | mechanism proxy |
| Latency / infra / reliability | vapp_va_is_dz | v17 external API | External operational quality proxies | mechanism proxy |
| Entity / vertical integration | vapp_va_log_same_software_version_total_stake | v17 external API | External client/software proxies | mechanism proxy |
| Entity / vertical integration | sw_stakewiz_known_staking_provider_name | v17 external API | External entity/name/operator proxies | mechanism proxy |
| Entity / vertical integration | vapp_va_log_active_stake | v17 external API | External Jito/APY/commission/stake proxies | mechanism proxy |
| Latency / infra / reliability | sw_ip_latitude | v17 external API | External network/location concentration | mechanism proxy |
| Latency / infra / reliability | sw_stakewiz_log_same_ip_city_total_stake | v17 external API | External network/location concentration | mechanism proxy |
| Latency / infra / reliability | vapp_vote_distance_score | v17 external API | External operational quality proxies | mechanism proxy |
| Entity / vertical integration | vapp_va_has_www | v17 external API | External entity/name/operator proxies | mechanism proxy |
| Latency / infra / reliability | sw_city_concentration | v17 external API | External network/location concentration | mechanism proxy |
| Private order-flow / searcher-flow | tip_avg_tx_share | v18 Jito tip-account flow | Jito tip-account flow proxy | mechanism proxy |
| Private order-flow / searcher-flow | tip_avg_unique_payers | v18 Jito tip-account flow | Jito tip-account flow proxy | mechanism proxy |
| Bundle outcome / landed execution | tx_p95_compute_units | v18 Solana getBlock | Solana getBlock execution/fee/program proxy | mechanism proxy |
| Private order-flow / searcher-flow | tip_log_avg_lamports_per_tip_tx | v18 Jito tip-account flow | Jito tip-account flow proxy | mechanism proxy |
| Private order-flow / searcher-flow | tx_fee_payer_fee_hhi | v18 Solana getBlock | Solana getBlock execution/fee/program proxy | mechanism proxy |
| Bundle outcome / landed execution | tx_log_avg_fee | v18 Solana getBlock | Solana getBlock execution/fee/program proxy | mechanism proxy |
| Bundle outcome / landed execution | tx_log_p95_priority_fee_proxy | v18 Solana getBlock | Solana getBlock execution/fee/program proxy | mechanism proxy |
| Bundle outcome / landed execution | tx_positive_priority_fee_tx_share | v18 Solana getBlock | Solana getBlock execution/fee/program proxy | mechanism proxy |
| Private order-flow / searcher-flow | tip_avg_payer_hhi | v18 Jito tip-account flow | Jito tip-account flow proxy | mechanism proxy |
| Private order-flow / searcher-flow | tip_log_total_SOL_sample | v18 Jito tip-account flow | Jito tip-account flow proxy | mechanism proxy |
| Private order-flow / searcher-flow | tx_fee_payer_tx_hhi | v18 Solana getBlock | Solana getBlock execution/fee/program proxy | mechanism proxy |
| Bundle outcome / landed execution | tx_blocks | v18 Solana getBlock | Solana getBlock execution/fee/program proxy | mechanism proxy |
| Bundle outcome / landed execution | tx_priority_fee_proxy_share | v18 Solana getBlock | Solana getBlock execution/fee/program proxy | mechanism proxy |
| Private order-flow / searcher-flow | tx_fee_payer_unique_ratio | v18 Solana getBlock | Solana getBlock execution/fee/program proxy | mechanism proxy |
| Bundle outcome / landed execution | tx_avg_compute_units | v18 Solana getBlock | Solana getBlock execution/fee/program proxy | mechanism proxy |
| Bundle outcome / landed execution | tx_token_ix_share | v18 Solana getBlock | Solana getBlock execution/fee/program proxy | mechanism proxy |

## 7. Bottom-line interpretation

The strongest available mechanism evidence by fit contribution is the order-flow/searcher-flow family, especially `tip_avg_tx_share` and related tip/fee-payer concentration variables. However, the candidate-attenuation column must be read separately: if a module improves R? but makes the candidate coefficient larger, it improves fit without absorbing the residual candidate edge.

In the current run, the best positive candidate attenuation comes from the entity/integration family, but that family remains weak because it uses metadata and affiliation proxies rather than true ownership or private commercial relationship data.

Latency/infra and bundle-outcome mechanisms are partially tested through landed-block and operational proxies, but raw latency and rejected-bundle data are still missing.

Entity/vertical-integration remains the weakest mechanism channel: v21 can use metadata, client/software, names, Jito flags, and operator hints, but it cannot prove ownership or private commercial integration.


## v20-to-v21 rerun drift check

| metric | v20_reference | v21_full_rerun | delta_v21_minus_v20 | absolute_delta | tolerance_or_rule | status |
| --- | --- | --- | --- | --- | --- | --- |
| benchmark_r_squared | 0.8180 | 0.8155 | -0.0024 | 0.0024 | 0.0200 | WITHIN_TOLERANCE |
| benchmark_adj_r_squared | 0.7830 | 0.7808 | -0.0023 | 0.0023 | 0.0200 | WITHIN_TOLERANCE |
| benchmark_candidate_coef | 0.2948 | 0.3161 | 0.0213 | 0.0213 | 0.0600 | WITHIN_TOLERANCE |
| stake_baseline_r_squared | 0.7024 | 0.7024 | 0.0000 | 0.0000 | 0.0200 | WITHIN_TOLERANCE |
| strongest_fit_contribution_family | Private order-flow / searcher-flow | Private order-flow / searcher-flow |  |  | same family expected | SAME |
| strongest_candidate_attenuation_family | Entity / vertical integration | Entity / vertical integration |  |  | same family expected | SAME |

## Data-loss audit

| check | current_full_rerun | v20_source_snapshot | finding |
| --- | --- | --- | --- |
| validator_rows | 423 | 423 | no row loss in local diagnostic |
| panel_columns | 638 | 638 | same column count in local diagnostic |
| validator_key_intersection | 423 | 423 | intersection=423, current_only=0, snapshot_only=0 in local diagnostic |
| v21_final_benchmark_n | 411 | 411 | sample-preserving guardrail restores the v20-comparable benchmark sample |
| raw_H7_variable_count | 66 | 66 | same raw H7 variable count in local diagnostic |
| H7_variable_overlap | 54 | 66 | 12 current-only proxies and 12 snapshot-only proxies; drift comes from proxy substitution, not data loss |
| randomness_review | fixed seeds found where sampling is used | not applicable | No evidence of unseeded random sampling in the critical v18-v21 model path; the drift is better described as proxy-selection/version drift. |
