# API Source Layer

## Purpose

`api_sources/` is the online data acquisition layer for v27. It is not the default offline reproduction path. The default run reads frozen files from `data/source_assets/`; the online runner uses this package to fetch comparable data into isolated `data/api_runs/<run_id>/` directories and then tests whether the same-DV models still run.

## Layering

1. `providers/` defines endpoint builders for each external API family. Provider files should not parse model variables or write analysis outputs.
2. `parsers/` turns raw API responses into normalized feature rows. Parsers should not perform network calls.
3. `pipelines/` combines providers, parsers, manifests, and CSV writes into runnable acquisition jobs.
4. `pipeline.api_reproduction` orchestrates selected pipelines, builds a source-assets overlay, and reruns the v27 model scripts against that overlay.

## Files

- `common.py`: shared utilities for environment loading, HTTP JSON requests, redacted URLs, Solana RPC calls, numeric coercion, and small Markdown tables.
- `registry.py`: endpoint inventory used as documentation and audit metadata. It records which API endpoint families are represented by the provider modules.
- `providers/`: endpoint-builder modules, one file per API family.
- `parsers/`: response parser modules for API responses that need feature construction.
- `pipelines/`: runnable data acquisition modules.
- `README.md`: this directory contract.

## Relationship to Top-level Scripts

- `pipeline.run_all` calls only `python -m api_sources.pipelines.local_inventory` in the default offline path.
- `data_processing.process` consumes `data/source_assets/`, not live API responses.
- `pipeline.api_reproduction` is the online path. It calls pipeline modules, writes raw online data into `data/api_runs/<run_id>/api_raw/`, copies frozen `data/source_assets/` into an overlay, promotes nonempty online outputs into that overlay, then reruns the same-DV model scripts.

## Naming Rule

File names in `data/source_assets/`, `data/processed/`, and `data/variables/` should describe the data or model object, not the historical version number. Historical lineage belongs in manifests, reports, and source keys, not in file names.
