# API Providers

## Purpose

`providers/` contains one module per external API family. These modules define endpoint URLs and RPC request bodies only. They do not own parsing, joins, model variables, or regression logic.

## Files

- `jito.py`: endpoint builders for Jito public bundle APIs, Jito Kobe epoch/reward endpoints, public stats, tip floor, and block-engine tip accounts.
- `solana_rpc.py`: Solana JSON-RPC request body helpers, including `getBlock` parameters used by block/tip feature reconstruction.
- `bam.py`: BAM/IBRL endpoint builders for validator and block operation metrics.
- `helius.py`: Helius endpoint builders for enhanced transaction and address transaction history calls.
- `solscan.py`: Solscan account detail endpoint builder.
- `dune.py`: Dune SQL execution and execution-result endpoint builders.
- `validator_metadata.py`: public validator metadata endpoints from Stakewiz and Validators.app.
- `__init__.py`: package marker; it should remain lightweight.

## Upstream and Downstream

- Upstream: credentials and limits are supplied by `pipeline.api_reproduction` or individual pipeline arguments.
- Downstream: `api_sources/pipelines/*.py` calls these endpoint builders through `api_sources.common.request_json()` or Solana RPC helpers.

## Design Rule

Keep provider modules side-effect free. A provider function should return a URL or request body. If a change needs retries, pagination, joins, CSV writes, or model-specific columns, put that logic in a pipeline or parser instead.
