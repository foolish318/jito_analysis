# clean_analysis_reviewed_improved_v21 API acquisition and mechanism-source map

This v21 acquisition document is intentionally separate from the processing/interpreting document. v21 did **not** require a new broad data pull. It reorganizes data already acquired in v15–v19 into four mechanism modules.

## 1. Data source coverage inherited from v19

| source | units | matched_validators | note |
| --- | --- | --- | --- |
| v16 high-R2 benchmark | 423 | 413 | Benchmark built from v16 selected/pruned proxies. |
| Stakewiz + Validators.app | 423 | 423 | External validator metadata / client / operator / location proxies. |
| Solana getBlock execution features | 500 | 423 | 500 sampled slots; at least one sampled slot for all 423 validators. |
| Jito tip-account flow features | 423 | 423 | 423 sampled slots; getTipAccounts returned 8 accounts; 421 blocks had positive tip flow. |

## 2. Mechanism-to-source map

| mechanism | main sources | acquisition method | current limitation |
| --- | --- | --- | --- |
| Latency / infra / reliability | Validators.app, Stakewiz, BAM/IBRL, Solana schedule/BAM production | validator metadata plus block-building and skip/reliability proxies | no raw relay-arrival timestamp, p95/p99 propagation delay, or leader-region ground truth |
| Private order-flow / searcher-flow | Jito `getTipAccounts`, Solana `getBlock`, Jito tip-account balance deltas | identify Jito tip accounts, parse sampled blocks, compute tip/payer concentration | no direct searcher identity and no private searcher-validator relationship map |
| Bundle outcome / landed execution | Solana `getBlock`, BAM/IBRL block detail | parse landed transactions, fees, compute units, programs, IBRL/packing proxies | no submitted/rejected bundle archive or bundle-level auction outcome |
| Entity / vertical integration | Stakewiz, Validators.app, validator names/keybase/www/client/software/Jito flags | metadata matching against validator identity/vote accounts | weak proxy only; no ownership, RPC/searcher, or commercial relationship mapping |

## 3. What was already fetched

- Stakewiz `/validators`: validator metadata, entity/name hints, IP/city/country/version/Jito/APY/commission fields.
- Validators.app `/api/v1/validators/mainnet.json?limit=5000`: software client/version, data-center/network, scores, vote/skip/latency-like metadata.
- Solana JSON-RPC `getBlock`: sampled slot-level transactions, fees, compute, programs, fee payers, and balances.
- Jito block engine `getTipAccounts`: tip account list used with Solana `getBlock` balance deltas.
- BAM/IBRL validators and blocks: block-building quality, timing, packing, compute/tick concentration, produced blocks.

## 4. Rate-limit / acquisition notes

- Heavy block-level calls were cached by slot.
- `getBlock` is feasible as a sampled public-RPC pull but should not be used for full historical scans without an archival provider.
- Bundle-status cannot build a broad panel without historical bundle IDs.
- API-key endpoints such as Helius/Solscan Pro were not available without credentials.

## 5. Future data priorities by mechanism

| mechanism | missing | cannot_say |
| --- | --- | --- |
| Latency / infra / reliability | raw latency, relay arrival timestamp, p95/p99 propagation delay, bundle arrival timestamp, leader region/data center ground truth | No raw relay-arrival timestamp or true network latency; cannot prove raw latency advantage. |
| Private order-flow / searcher-flow | searcher identity, bundle IDs, repeated searcher-validator pairings, private flow contracts | Cannot identify private searcher relationships or true searcher identity without bundle/searcher mapping. |
| Bundle outcome / landed execution | submitted/landed/rejected bundle IDs, bundle failure rate, landed/submitted value ratio | Cannot explain rejected bundles or full auction inclusion outcome without historical bundle archive. |
| Entity / vertical integration | validator-operator mapping, RPC/searcher/block-builder ownership, commercial relationship data | Cannot prove vertical integration or ownership/commercial relationships. |

## 6. Interpretation discipline

v21 should be read as mechanism attribution through observable proxies. It can rank which channels are most consistent with the residual edge, but it should not claim direct causal proof of latency advantage, private order flow, rejected-bundle auction outcomes, or vertical integration without the missing data above.


## v21 rerun note

The final v21 mechanism-output step uses the current full-rerun v18/v19 outputs. The benchmark can drift slightly from the older v20 workbook because the tournament/proxy-pruning step may substitute closely related proxy variables. The final v21 model applies a sample-preserving guardrail that drops a redundant Validators.app skipped-slots proxy with two missing values. The local audit found no validator-row loss, restored the v20-comparable benchmark sample, and found no unseeded random sampling in the critical model path.
