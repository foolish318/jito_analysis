# API Pipelines

## Purpose

`pipelines/` contains runnable acquisition jobs. A pipeline combines provider endpoints, common HTTP/RPC utilities, optional parsers, and CSV/JSON outputs. Pipelines are called either directly for targeted checks or by `pipeline.api_reproduction` for isolated online reproduction.

## Files

- `local_inventory.py`: validates the frozen local `data/source_assets/` inventory. This is the only API-source module used by the default `pipeline.run_all` path.
- `jito_bundles.py`: fetches Jito public bundle data and constructs bundle, bundle-event, tipper-validator edge, and validator order-flow score tables.
- `jito_epoch_bam.py`: fetches Jito/Kobe epoch data and BAM/IBRL metrics, then builds validator-epoch and 50-epoch validator summary tables.
- `account_enrichment.py`: fetches Helius address histories and Solscan account labels for address-level enrichment.
- `solana_block_tip_features.py`: fetches Solana `getBlock` payloads plus Jito tip accounts, then uses `parsers/solana_block.py` to regenerate Solana block and Jito tip-flow feature snapshots.
- `public_metadata.py`: fetches Solana RPC metadata, Stakewiz, Validators.app, and Jito public metadata for audit and enrichment.
- `transaction_enrichment.py`: fetches Helius enhanced transactions and Dune SQL sample outputs.
- `__init__.py`: package marker.

## Output Contract

- Direct online outputs should go under a run-specific raw directory, usually `data/api_runs/<run_id>/api_raw/`.
- Frozen reproducibility inputs live in `data/source_assets/` and should not be overwritten by default.
- `pipeline.api_reproduction` may promote nonempty online files into a temporary `source_assets_overlay/` for model testing without changing the frozen local inputs.

## Pipeline Relationships

- `jito_bundles.py` feeds public bundle/order-flow proxies used by the v22-style mechanism layer.
- `jito_epoch_bam.py` feeds the 50-epoch MEV/BAM validator summary used by the v25-style IV extensions.
- `solana_block_tip_features.py` feeds block/tip operational proxies used by the benchmark source layer and supplemental checks.
- `account_enrichment.py`, `public_metadata.py`, and `transaction_enrichment.py` provide enrichment and audit evidence; they are not allowed to change the dependent variable.

## Run Examples

```bash
python -m api_sources.pipelines.local_inventory
python -m pipeline.api_reproduction --sources jito-public jito-epochs helius solscan
```
