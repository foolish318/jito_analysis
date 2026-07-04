from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

PKG = Path(__file__).resolve().parents[1]
DATA = PKG / 'data'
SOURCE_ASSETS = DATA / 'source_assets'
PROCESSED = DATA / 'processed'
VARIABLES = DATA / 'variables'
OUT = PKG / 'output'
NOTEBOOKS = PKG / 'notebooks'

TARGET = 'log_mev_per_leader_slot'
DATA_FILE_SUFFIXES = {'.csv', '.json', '.parquet', '.xlsx'}


def md_table(df: pd.DataFrame, max_rows: int | None = None, digits: int = 6) -> str:
    if df is None or df.empty:
        return '_No rows._'
    use = df.head(max_rows).copy() if max_rows else df.copy()
    headers = [str(c) for c in use.columns]
    lines = ['| ' + ' | '.join(headers) + ' |', '| ' + ' | '.join(['---'] * len(headers)) + ' |']
    for _, row in use.iterrows():
        vals = []
        for c in use.columns:
            x = row[c]
            if isinstance(x, float):
                vals.append(f'{x:.{digits}g}')
            else:
                vals.append(str(x).replace('\n', ' ').replace('|', '\\|'))
        lines.append('| ' + ' | '.join(vals) + ' |')
    return '\n'.join(lines)


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def source_assets_inventory() -> pd.DataFrame:
    rows = []
    for path in sorted(SOURCE_ASSETS.glob('*')):
        if path.is_file() and path.suffix.lower() in DATA_FILE_SUFFIXES:
            rows.append({'file': path.name, 'relative_path': str(path.relative_to(PKG)), 'size_bytes': path.stat().st_size})
    return pd.DataFrame(rows)


def command_block() -> str:
    return """```bash
cd /path/to/v27
python -m pipeline.run_all
```"""


def write_runbook(summary: dict) -> None:
    text = f"""# v27 Runbook

## Purpose

v27 is organized as a self-contained reproduction folder. The default pipeline reads frozen local input snapshots from `data/source_assets/`, processes them, builds variables, runs the same-DV model suite, runs out-of-sample prediction validation, and executes the notebooks.

DV is fixed as `{TARGET}`. The pipeline may add or compare IV blocks, but it does not change the dependent variable.

## One-command Full Run

{command_block()}

Inside the current machine the equivalent command is:

```bash
cd {PKG}
python -m pipeline.run_all
```

## Expanded Run

```bash
cd {PKG}
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
cd {PKG}
python -m pipeline.api_reproduction --sources jito-public jito-epochs helius solscan
```

This writes online responses to `data/api_raw/`. Add `--write-source-assets` only if you intentionally want to overwrite the frozen local snapshots and rerun a refreshed analysis.

## Online API Reproduction Runner

For an isolated online pull plus model overlay, use `pipeline.api_reproduction`. It writes into `data/api_runs/<run_id>/` and does not overwrite frozen `data/source_assets/`. It reads keys from `v27/.env.local`, parent `.env.local`, and simple `KEY=VALUE` entries in `../api_key.md`; keys are not printed in manifests.

Smoke command validated on this machine:

```bash
cd {PKG}
python -m pipeline.api_reproduction \
  --run-id api_smoke_20260702_v18_audit \
  --bundle-limit 20 \
  --address-limit 5 \
  --signature-limit 10 \
  --getblock-limit 20 \
  --tip-limit 20 \
  --epoch-start 991 \
  --epoch-end 992 \
  --dune-max-wait-sec 30
```


Full v18-style online regeneration uses the historical v18 slot manifests now stored in `data/source_assets/`:

```bash
cd {PKG}
python -m pipeline.api_reproduction \
  --run-id api_full_v18_v25_refresh \
  --sources all \
  --bundle-limit 1000 \
  --address-limit 30 \
  --signature-limit 100 \
  --getblock-limit 500 \
  --tip-limit 423 \
  --epoch-start 943 \
  --epoch-end 992 \
  --dune-max-wait-sec 240
```

The full command can be slow and API-rate-limit sensitive. Public APIs that expose only live/recent windows cannot guarantee byte-identical historical samples. Exact model reproduction therefore remains the frozen local path; the online runner verifies acquisition, schema, joins, and same-DV overlay behavior.

## Refactor Full API Validation

The refactored API structure was validated with a non-smoke all-source run:

```bash
cd {PKG}
python -m pipeline.api_reproduction \
  --run-id api_refactor_full_validation_20260702 \
  --sources all \
  --bundle-limit 200 \
  --address-limit 30 \
  --signature-limit 100 \
  --getblock-limit 500 \
  --tip-limit 423 \
  --epoch-start 943 \
  --epoch-end 992 \
  --legacy-epoch-start 992 \
  --legacy-epoch-end 992 \
  --leader-limit 50 \
  --dune-max-wait-sec 240
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

- Main benchmark status vs v26 snapshot: `{summary.get('benchmark_status_vs_v26', 'unknown')}`.
- Main benchmark R2: `{summary.get('main_r_squared', '')}`.
- Main benchmark N: `{summary.get('main_n', '')}`.
- Main benchmark DV: `{TARGET}`.
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
"""
    (PKG / 'runbook.md').write_text(text, encoding='utf-8')


def write_data_doc(inventory: pd.DataFrame, lineage: pd.DataFrame, model_suite: pd.DataFrame) -> None:
    model_cols = ['model', 'n', 'r_squared', 'adj_r_squared', 'baseline_h7_same_sample_r_squared', 'incremental_r2_vs_h7_same_sample', 'candidate_coef', 'candidate_p_value']
    text = f"""# v27 Data, Proxy, and Variable Definitions

## Storage Layout

- Frozen local input snapshots: `data/source_assets/`.
- Standardized data/process audit: `data/processed/`.
- Constructed analysis variables and panels: `data/variables/` plus `data/model_panel.csv`.
- Model outputs and reports: `output/`.
- Optional online API responses: `data/api_raw/`.
- Isolated online reproduction runs: `data/api_runs/<run_id>/`.

## Source Assets

{md_table(inventory, digits=4)}

## Core DV/IV Discipline

- DV: `{TARGET}`.
- Main benchmark IVs: fixed 66 H7/B10 regressors from `data/source_assets/h7_b10_feature_list.csv`.
- Candidate IV: `candidate_indicator`.
- Supplemental IVs: v22-v25 mechanism scores and additional z-scored proxy blocks. These are added as IVs only; they never redefine the DV.

## Result Lineage

{md_table(lineage, digits=6)}

## Same-DV IV Model Suite

{md_table(model_suite[model_cols] if not model_suite.empty else model_suite, digits=6)}
"""
    (PKG / 'data proxy variable.md').write_text(text, encoding='utf-8')


def write_api_doc(inventory: pd.DataFrame) -> None:
    text = f"""# v27 API Data Protocol and Join

## Default Protocol: Local Snapshot Reproduction

The default v27 reproduction does not call external APIs. It reads frozen input snapshots from `data/source_assets/`, validates their schemas through `data_processing.process`, builds variables through `data_processing.variables`, runs analysis/model-selection modules, and runs out-of-sample prediction validation.

## Optional Protocol: Online Refresh

Use `python -m api_sources.pipelines.local_inventory` only when you want to refresh standard source inputs from APIs:

```bash
cd {PKG}
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
cd {PKG}
python -m pipeline.api_reproduction \
  --run-id api_refactor_full_validation_20260702 \
  --sources all \
  --bundle-limit 200 \
  --address-limit 30 \
  --signature-limit 100 \
  --getblock-limit 500 \
  --tip-limit 423 \
  --epoch-start 943 \
  --epoch-end 992 \
  --legacy-epoch-start 992 \
  --legacy-epoch-end 992 \
  --leader-limit 50 \
  --dune-max-wait-sec 240
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

{md_table(inventory, digits=4)}
"""
    (PKG / 'API data protocol join.md').write_text(text, encoding='utf-8')


def write_readme(summary: dict, lineage: pd.DataFrame) -> None:
    text = f"""# v27 Jito Structural Analysis Reproduction

This folder is intended to be a self-contained reproduction package for the v27 analysis.

Default reproduction uses local snapshots in `data/source_assets/`. Optional standard-source online refreshes are available through `python -m api_sources.pipelines.local_inventory`; isolated online acquisition plus overlay-model reproduction is available through `pipeline.api_reproduction`. The implementation is organized under `api_sources/` by provider, parser, and pipeline. Exact reproduction should use the frozen snapshots.

Key benchmark: DV `{TARGET}`, N={summary.get('main_n', '')}, R2={summary.get('main_r_squared', '')}, candidate coefficient={summary.get('main_candidate_coef', '')}, p={summary.get('main_candidate_p_value', '')}.

Run:

{command_block()}

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

{md_table(lineage[['result','reported_number','source_assets','output_file','interpretation']] if not lineage.empty else lineage, digits=6)}

Online API runner:

```bash
cd {PKG}
python -m pipeline.api_reproduction --run-id api_smoke_20260702_v18_audit --bundle-limit 20 --address-limit 5 --signature-limit 10 --getblock-limit 20 --tip-limit 20 --epoch-start 991 --epoch-end 992 --dune-max-wait-sec 30
```

The validated smoke output is in `data/api_runs/api_smoke_20260702_v18_audit/`; legacy v15-v19 endpoint smoke output is in `data/api_runs/api_legacy_smoke_20260702/`. For full v18 online regeneration use `--getblock-limit 500 --tip-limit 423`; for the v25 window use `--epoch-start 943 --epoch-end 992`.

Full refactor validation output is in `data/api_runs/api_refactor_full_validation_20260702/`; the audit report is `output/v27_api_refactor_full_validation_report.md`. This all-source run regenerated v18 500/423 slot features, refreshed the v25 50-epoch window, and reproduced the main overlay benchmark at R2 `0.8149674041398512`. Solscan account detail remains permission-blocked by the current key.
"""
    (PKG / 'README.md').write_text(text, encoding='utf-8')


def append_report_lineage(lineage: pd.DataFrame, inventory: pd.DataFrame) -> None:
    report_path = OUT / 'v27_report.md'
    if not report_path.exists():
        return
    report = report_path.read_text(encoding='utf-8')
    marker = '\n## Data Origin And Result Lineage\n'
    if marker in report:
        report = report.split(marker)[0].rstrip() + '\n'
    section = marker + f"""
All headline results use DV `{TARGET}`. Frozen local source assets are stored under `data/source_assets/`; optional online API refreshes write to `data/api_raw/` and do not affect exact reproduction unless explicitly promoted with `--write-source-assets`.

{md_table(lineage, digits=6)}

Source asset inventory:

{md_table(inventory, digits=4)}
"""
    report_path.write_text(report.rstrip() + '\n' + section, encoding='utf-8')


def run() -> dict[str, object]:
    summary_path = OUT / 'run_summary.json'
    summary = json.loads(summary_path.read_text(encoding='utf-8')) if summary_path.exists() else {}
    inventory = source_assets_inventory()
    lineage = read_csv(OUT / 'v27_result_lineage.csv')
    model_suite = read_csv(OUT / 'v27_same_dv_iv_model_suite.csv')
    write_runbook(summary)
    write_data_doc(inventory, lineage, model_suite)
    write_api_doc(inventory)
    write_readme(summary, lineage)
    append_report_lineage(lineage, inventory)
    result = {'finished_at': datetime.now(timezone.utc).isoformat(), 'source_assets': len(inventory), 'lineage_rows': len(lineage)}
    (OUT / 'write_repo_docs_summary.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))
    return result


if __name__ == '__main__':
    run()
