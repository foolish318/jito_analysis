from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

PKG = Path(__file__).resolve().parents[1]
DATA = PKG / 'data'
SOURCE_ASSETS = DATA / 'source_assets'
API_RUNS = DATA / 'api_runs'
API_RUNS.mkdir(parents=True, exist_ok=True)

from api_sources.common import load_env_files, md_table, utc_now
from api_sources.pipelines import account_enrichment, jito_bundles, jito_epoch_bam
from api_sources.pipelines.public_metadata import fetch_public_metadata
from api_sources.pipelines.solana_block_tip_features import fetch_solana_block_tip_features
from api_sources.pipelines.transaction_enrichment import fetch_dune_direct_samples, fetch_helius_enhanced


def run_id_now() -> str:
    return datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')


def load_api_env() -> None:
    load_env_files(PKG / '.env.local', PKG.parent / '.env.local', PKG.parent / 'api_key.md')


def run_standard_source_fetch(run_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    raw_dir = run_dir / 'api_raw' / 'standard_sources'
    raw_dir.mkdir(parents=True, exist_ok=True)
    for module in [jito_bundles, jito_epoch_bam, account_enrichment]:
        module.API_RAW = raw_dir
        module.SOURCE_ASSETS = SOURCE_ASSETS
    results: list[dict[str, Any]] = []
    selected = [s for s in args.sources if s in {'jito-public', 'jito-epochs', 'helius', 'solscan'}]
    if not selected:
        return {'source': 'standard_source_fetch', 'skipped': True, 'reason': 'no standard source fetch sources selected'}
    if 'jito-public' in selected:
        results.append(jito_bundles.fetch_jito_public_bundles(args.bundle_limit, write_source_assets=False))
    if 'jito-epochs' in selected:
        epochs = list(range(args.epoch_start, args.epoch_end + 1))
        results.append(jito_epoch_bam.fetch_jito_epochs(epochs, write_source_assets=False))
    if 'helius' in selected:
        results.append(account_enrichment.fetch_helius_addresses(args.address_limit))
    if 'solscan' in selected:
        results.append(account_enrichment.fetch_solscan_accounts(args.address_limit))
    summary = {'source': 'standard_source_fetch', 'online': True, 'results': results}
    (raw_dir / 'fetch_standard_sources_summary.json').write_text(json.dumps(summary, indent=2, sort_keys=True, default=str), encoding='utf-8')
    return summary

def copytree_replace(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def promote_if_nonempty(src: Path, dst: Path, promoted: list[dict[str, Any]]) -> None:
    if not src.exists():
        promoted.append({'source': str(src), 'target': str(dst), 'promoted': False, 'reason': 'missing'})
        return
    try:
        df = pd.read_csv(src)
    except Exception as exc:
        promoted.append({'source': str(src), 'target': str(dst), 'promoted': False, 'reason': repr(exc)})
        return
    if df.empty:
        promoted.append({'source': str(src), 'target': str(dst), 'promoted': False, 'reason': 'empty'})
        return
    df.to_csv(dst, index=False)
    promoted.append({'source': str(src), 'target': str(dst), 'promoted': True, 'rows': len(df), 'columns': len(df.columns)})


def build_overlay(run_dir: Path) -> tuple[Path, pd.DataFrame]:
    overlay = run_dir / 'source_assets_overlay'
    copytree_replace(SOURCE_ASSETS, overlay)
    raw = run_dir / 'api_raw' / 'standard_sources'
    promoted: list[dict[str, Any]] = []
    mappings = [
        ('jito_public_bundles_online.csv', 'jito_public_bundles.csv'),
        ('jito_public_validator_orderflow_scores_online.csv', 'jito_public_validator_orderflow_scores.csv'),
        ('jito_public_tipper_validator_edges_online.csv', 'jito_public_tipper_validator_edges.csv'),
        ('jito_public_bundle_events_online.csv', 'jito_public_bundle_events.csv'),
        ('validator_epoch_mev_bam_summary_50epoch_online.csv', 'validator_epoch_mev_bam_summary_50epoch.csv'),
    ]
    for src_name, dst_name in mappings:
        promote_if_nonempty(raw / src_name, overlay / dst_name, promoted)
    promoted_df = pd.DataFrame(promoted)
    promoted_df.to_csv(run_dir / 'api_overlay_promotion.csv', index=False)
    return overlay, promoted_df


def patch_analysis_modules(core: Any, run_dir: Path, overlay: Path) -> None:
    import analysis.data_assembly as data_assembly
    import analysis.preliminary as preliminary
    import analysis.regression as regression
    import analysis.reporting as reporting
    import analysis.structural as structural

    data_dir = run_dir / 'data'
    processed_dir = data_dir / 'processed'
    api_raw_dir = run_dir / 'api_raw'
    out_dir = run_dir / 'output'
    notebooks_dir = run_dir / 'notebooks'
    for path in [data_dir, processed_dir, api_raw_dir, out_dir, notebooks_dir]:
        path.mkdir(parents=True, exist_ok=True)

    old_sources = getattr(data_assembly, 'SOURCES')
    new_sources = {key: overlay / path.name for key, path in old_sources.items()}
    modules = [data_assembly, preliminary, regression, reporting, structural, core]
    for module in modules:
        for name, value in {
            'PKG': run_dir,
            'ROOT': run_dir.parent,
            'DATA': data_dir,
            'SOURCE_ASSETS': overlay,
            'PROCESSED': processed_dir,
            'API_RAW': api_raw_dir,
            'OUT': out_dir,
            'NOTEBOOKS': notebooks_dir,
        }.items():
            if hasattr(module, name):
                setattr(module, name, value)
        if hasattr(module, 'SOURCES'):
            setattr(module, 'SOURCES', new_sources)


def patch_ext_module(ext: Any, run_dir: Path, overlay: Path) -> None:
    ext.PKG = run_dir
    ext.ROOT = run_dir.parent
    ext.DATA = run_dir / 'data'
    ext.SOURCE_ASSETS = overlay
    ext.OUT = run_dir / 'output'
    ext.NOTEBOOKS = run_dir / 'notebooks'
    for path in [ext.DATA, ext.OUT, ext.NOTEBOOKS]:
        path.mkdir(parents=True, exist_ok=True)


def run_overlay_models(run_dir: Path, overlay: Path) -> dict[str, Any]:
    sys.path.insert(0, str(PKG)) if str(PKG) not in sys.path else None
    import analysis.main as core
    import model_selection.same_dv_iv_extensions as ext

    patch_analysis_modules(core, run_dir, overlay)
    summary: dict[str, Any] = {'core_ok': False, 'extension_ok': False}
    try:
        core_summary = core.run()
        summary.update({'core_ok': True, 'core_summary': core_summary})
    except Exception as exc:
        summary.update({'core_error': repr(exc)})
        (run_dir / 'output').mkdir(parents=True, exist_ok=True)
        (run_dir / 'output' / 'api_overlay_model_error.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
        return summary
    patch_ext_module(ext, run_dir, overlay)
    try:
        ext_summary = ext.run()
        summary.update({'extension_ok': True, 'extension_summary': ext_summary})
    except Exception as exc:
        summary.update({'extension_error': repr(exc)})
    (run_dir / 'output' / 'api_overlay_reproduction_summary.json').write_text(json.dumps(summary, indent=2, sort_keys=True, default=str), encoding='utf-8')
    return summary


def fit_api_v25_models(run_dir: Path, overlay: Path) -> dict[str, Any]:
    import numpy as np
    import statsmodels.api as sm

    out_dir = run_dir / 'output'
    out_dir.mkdir(parents=True, exist_ok=True)
    path = overlay / 'validator_epoch_mev_bam_summary_50epoch.csv'
    if not path.exists():
        return {'skipped': True, 'reason': 'v25 summary missing from overlay'}
    summary = pd.read_csv(path)
    specs = [
        ('summary_50_baseline', 'log_total_mev_SOL', ['candidate_like_50epoch', 'log_avg_active_stake_SOL', 'log_epochs_seen']),
        ('summary_50_opportunity', 'log_total_mev_SOL', ['candidate_like_50epoch', 'log_avg_active_stake_SOL', 'log_epochs_seen', 'log_total_blocks_produced']),
        (
            'summary_50_available_mechanisms',
            'log_total_mev_SOL',
            [
                'candidate_like_50epoch',
                'log_avg_active_stake_SOL',
                'log_epochs_seen',
                'log_total_blocks_produced',
                'avg_ibrl_score',
                'avg_build_time_score',
                'avg_median_block_build_ms',
                'running_bam_epoch_share',
                'jito_directed_epoch_share',
            ],
        ),
    ]
    rows = []
    for model, y_col, x_cols in specs:
        cols = [y_col] + x_cols
        missing = [c for c in cols if c not in summary.columns]
        if missing:
            rows.append({'model': model, 'n': 0, 'r_squared': np.nan, 'adj_r_squared': np.nan, 'candidate_coef': np.nan, 'candidate_p_value': np.nan, 'note': 'missing columns: ' + ','.join(missing)})
            continue
        data = summary[cols].replace([np.inf, -np.inf], np.nan).dropna().copy()
        if len(data) <= len(x_cols) + 8:
            rows.append({'model': model, 'n': len(data), 'r_squared': np.nan, 'adj_r_squared': np.nan, 'candidate_coef': np.nan, 'candidate_p_value': np.nan, 'note': 'insufficient rows'})
            continue
        X = sm.add_constant(data[x_cols], has_constant='add')
        fit = sm.OLS(data[y_col], X).fit(cov_type='HC3')
        rows.append({
            'model': model,
            'n': int(fit.nobs),
            'r_squared': float(fit.rsquared),
            'adj_r_squared': float(fit.rsquared_adj),
            'candidate_coef': float(fit.params['candidate_like_50epoch']) if 'candidate_like_50epoch' in fit.params.index else np.nan,
            'candidate_p_value': float(fit.pvalues['candidate_like_50epoch']) if 'candidate_like_50epoch' in fit.pvalues.index else np.nan,
            'note': '',
        })
    result = pd.DataFrame(rows)
    expected_path = overlay / 'validator_epoch_mev_bam_regression_stats.csv'
    if expected_path.exists():
        expected = pd.read_csv(expected_path)
        keep = [c for c in ['model', 'n', 'r_squared', 'adj_r_squared', 'candidate_coef', 'candidate_p_value'] if c in expected.columns]
        expected = expected[keep].rename(columns={c: f'expected_{c}' for c in keep if c != 'model'})
        result = result.merge(expected, on='model', how='left')
        for col in ['n', 'r_squared', 'adj_r_squared', 'candidate_coef', 'candidate_p_value']:
            exp = f'expected_{col}'
            if exp in result.columns and col in result.columns:
                result[f'delta_{col}'] = pd.to_numeric(result[col], errors='coerce') - pd.to_numeric(result[exp], errors='coerce')
    result.to_csv(out_dir / 'api_online_v25_model_reproduction.csv', index=False)
    key = {row['model']: row for row in result.to_dict('records')}
    return {
        'skipped': False,
        'output': str(out_dir / 'api_online_v25_model_reproduction.csv'),
        'summary_50_opportunity_r_squared': key.get('summary_50_opportunity', {}).get('r_squared'),
        'summary_50_available_mechanisms_r_squared': key.get('summary_50_available_mechanisms', {}).get('r_squared'),
    }


def write_api_coverage(run_dir: Path, results: list[dict[str, Any]], promoted: pd.DataFrame, model_summary: dict[str, Any]) -> None:
    coverage = pd.DataFrame([
        {'source': 'Jito public bundle API', 'status': 'implemented', 'v27_output': 'api_raw/standard_sources/v22_*_online.csv', 'role': 'v22 order-flow/bundle proxy refresh'},
        {'source': 'Jito epoch API', 'status': 'implemented', 'v27_output': 'api_raw/standard_sources/validator_epoch_mev_bam_summary_50epoch_online.csv', 'role': 'v25 50-epoch validator summary refresh'},
        {'source': 'Solana RPC', 'status': 'implemented', 'v27_output': 'api_raw/no_key_metadata/solana_*.json,csv', 'role': 'latency/infra/reliability metadata'},
        {'source': 'v18 Solana getBlock + Jito getTipAccounts', 'status': 'implemented sampled online; full v18 uses --getblock-limit 500 --tip-limit 423', 'v27_output': 'api_raw/solana_block_tip_features/v18_*_online.csv', 'role': 'v18 tx_* and tip_* mechanism proxy regeneration'},
        {'source': 'Stakewiz', 'status': 'implemented', 'v27_output': 'api_raw/no_key_metadata/stakewiz_validators.csv', 'role': 'entity/operator/stake metadata'},
        {'source': 'Validators.app', 'status': 'implemented', 'v27_output': 'api_raw/no_key_metadata/validators_app_mainnet.csv', 'role': 'entity/operator/location metadata'},
        {'source': 'Helius enhanced/address APIs', 'status': 'implemented; skipped if key missing', 'v27_output': 'api_raw/helius_enhanced; api_raw/standard_sources/helius_address_history_online.csv', 'role': 'fee-payer/searcher tx enrichment'},
        {'source': 'Solscan Pro API', 'status': 'implemented; skipped if key missing', 'v27_output': 'api_raw/standard_sources/solscan_account_detail_online.csv', 'role': 'account/entity label enrichment'},
        {'source': 'Dune API', 'status': 'implemented direct smoke; skipped if key missing', 'v27_output': 'api_raw/dune/*.csv', 'role': 'transactions/blocks/instruction table verification'},
    ])
    coverage.to_csv(run_dir / 'api_module_coverage.csv', index=False)
    lines = [
        '# v27 API Reproduction Run',
        '',
        f'Generated: `{utc_now()}`',
        '',
        '## Fetch Results',
        '',
        md_table(pd.DataFrame(results)),
        '',
        '## Promoted API Outputs Into Overlay',
        '',
        md_table(promoted) if not promoted.empty else '_No promotions._',
        '',
        '## API Source Coverage',
        '',
        md_table(coverage),
        '',
        '## Model Summary',
        '',
        '```json',
        json.dumps(model_summary, indent=2, sort_keys=True, default=str),
        '```',
    ]
    (run_dir / 'api_reproduction_report.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


def run(args: argparse.Namespace) -> dict[str, Any]:
    load_api_env()
    run_id = args.run_id or run_id_now()
    run_dir = API_RUNS / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    results.append(run_standard_source_fetch(run_dir, args))
    if 'solana-rpc' in args.sources or 'all' in args.sources:
        results.append(fetch_public_metadata(run_dir))
    if 'solana-block-tip' in args.sources or 'all' in args.sources:
        results.append(fetch_solana_block_tip_features(run_dir, SOURCE_ASSETS, args.getblock_limit, args.tip_limit))
    if 'helius-enhanced' in args.sources or 'all' in args.sources:
        results.append(fetch_helius_enhanced(run_dir, SOURCE_ASSETS, args.signature_limit))
    if 'dune' in args.sources or 'all' in args.sources:
        results.append(fetch_dune_direct_samples(run_dir, args.dune_max_wait_sec))
    overlay, promoted = build_overlay(run_dir)
    online_v25_validation = fit_api_v25_models(run_dir, overlay)
    model_summary = run_overlay_models(run_dir, overlay) if args.run_models else {'skipped': True}
    if isinstance(model_summary, dict):
        model_summary['online_v25_validation'] = online_v25_validation
    promoted_count = int(promoted.get('promoted', pd.Series(dtype=bool)).sum()) if not promoted.empty else 0
    summary = {
        'finished_at': utc_now(),
        'run_id': run_id,
        'run_dir': str(run_dir),
        'results': results,
        'promoted_rows': promoted_count,
        'model_summary': model_summary,
    }
    (run_dir / 'api_reproduction_summary.json').write_text(json.dumps(summary, indent=2, sort_keys=True, default=str), encoding='utf-8')
    write_api_coverage(run_dir, results, promoted, model_summary)
    print(json.dumps(summary, indent=2, sort_keys=True, default=str))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description='Run an online API refresh into data/api_runs/<run_id> and reproduce v27 models on an overlay source set.')
    parser.add_argument('--run-id', default='', help='Run id under data/api_runs. Defaults to UTC timestamp.')
    parser.add_argument('--sources', nargs='+', default=['jito-public', 'jito-epochs', 'solana-rpc', 'solana-block-tip', 'helius', 'solscan', 'helius-enhanced', 'dune'], choices=['all', 'jito-public', 'jito-epochs', 'solana-rpc', 'solana-block-tip', 'helius', 'solscan', 'helius-enhanced', 'dune'])
    parser.add_argument('--bundle-limit', type=int, default=50)
    parser.add_argument('--address-limit', type=int, default=10)
    parser.add_argument('--signature-limit', type=int, default=25)
    parser.add_argument('--getblock-limit', type=int, default=40, help='Number of v18 Solana getBlock slots to refresh online. Full v18 snapshot is 500.')
    parser.add_argument('--tip-limit', type=int, default=40, help='Number of v18 Jito tip-flow slots to refresh online. Full v18 snapshot is 423.')
    parser.add_argument('--epoch-start', type=int, default=991)
    parser.add_argument('--epoch-end', type=int, default=992)
    parser.add_argument('--dune-max-wait-sec', type=int, default=60)
    parser.add_argument('--no-models', action='store_true')
    args = parser.parse_args()
    args.run_models = not args.no_models
    if 'all' in args.sources:
        args.sources = ['jito-public', 'jito-epochs', 'solana-rpc', 'solana-block-tip', 'helius', 'solscan', 'helius-enhanced', 'dune']
    run(args)


if __name__ == '__main__':
    main()
