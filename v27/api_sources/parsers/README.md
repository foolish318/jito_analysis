# API Parsers

## Purpose

`parsers/` converts raw API responses into deterministic feature rows. Parser modules should be pure transformation code: no credential loading, no network calls, no model fitting, and no writes to `output/`.

## Files

- `solana_block.py`: parses Solana `getBlock` responses and Jito tip-account balance deltas. It builds slot-level transaction and tip-flow features, then aggregates slot rows into validator-level feature snapshots.
- `__init__.py`: package marker.

## Main Objects in `solana_block.py`

- `parse_solana_feature(...)`: extracts transaction-count, program-use, compute, and block-level features from a single block response.
- `parse_tip_feature(...)`: extracts Jito tip-account flow features from a block response and a tip-account set.
- `aggregate_solana_features(...)`: aggregates slot-level Solana block features to the validator level.
- `aggregate_tip_features(...)`: aggregates slot-level Jito tip-flow features to the validator level.

## Downstream

`api_sources/pipelines/solana_block_tip_features.py` calls this parser and writes semantic source snapshots such as `solana_block_features_snapshot.csv` and `jito_tip_account_flow_features_snapshot.csv`.
