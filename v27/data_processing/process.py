from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

PKG = Path(__file__).resolve().parents[1]
DATA = PKG / 'data'
SOURCE_ASSETS = DATA / 'source_assets'
PROCESSED = DATA / 'processed'
OUT = PKG / 'output'
for path in [DATA, SOURCE_ASSETS, PROCESSED, OUT]:
    path.mkdir(parents=True, exist_ok=True)

REQUIRED_SOURCES: dict[str, dict[str, Any]] = {
    'main_benchmark_model_panel.csv': {'key': 'main_benchmark_source_panel', 'required_columns': ['identity_account', 'vote_account', 'log_mev_per_leader_slot', 'candidate_indicator']},
    'h7_b10_feature_list.csv': {'key': 'h7_b10_feature_list', 'required_columns': ['feature']},
    'h7_b10_benchmark_run_summary.json': {'key': 'h7_b10_benchmark_run_summary', 'required_columns': []},
    'h7_b10_model_specification.csv': {'key': 'h7_b10_model_specification', 'required_columns': ['dependent_variable', 'independent_variable_count']},
    'jito_public_validator_orderflow_scores.csv': {'key': 'public_bundle_validator_orderflow_scores', 'required_columns': ['validator', 'bundles', 'total_tip_SOL', 'unique_tippers', 'relationship_score']},
    'jito_public_bundles.csv': {'key': 'jito_public_bundles', 'required_columns': ['bundleId', 'validator']},
    'jito_public_tipper_validator_edges.csv': {'key': 'jito_public_tipper_validator_edges', 'required_columns': ['validator']},
    'jito_public_bundle_events.csv': {'key': 'jito_public_bundle_events', 'required_columns': ['bundleId']},
    'structural_validator_mechanism_score_panel.csv': {'key': 'structural_validator_mechanism_score_panel', 'required_columns': ['validator', 'score_order_flow', 'score_bundle_execution', 'score_latency_infra', 'score_entity_integration']},
    'structural_model_fit_stats.csv': {'key': 'structural_model_fit_stats', 'required_columns': []},
    'structural_mechanism_attribution.csv': {'key': 'structural_mechanism_attribution', 'required_columns': []},
    'structural_sequential_model_ladder.csv': {'key': 'structural_sequential_model_ladder', 'required_columns': []},
    'observable_proxy_validator_score_panel.csv': {'key': 'observable_proxy_validator_score_panel', 'required_columns': ['validator', 'score_private_orderflow_searcherflow', 'score_bundle_outcome_execution', 'score_latency_infra_reliability', 'score_entity_vertical_integration']},
    'structural_counterfactual_estimates.csv': {'key': 'structural_counterfactual_estimates', 'required_columns': []},
    'observable_proxy_regression_model_stats.csv': {'key': 'observable_proxy_regression_stats', 'required_columns': []},
    'mechanism_identification_attribution.csv': {'key': 'mechanism_identification_attribution', 'required_columns': []},
    'validator_epoch_mev_bam_summary_50epoch.csv': {'key': 'validator_epoch_mev_bam_summary_50epoch', 'required_columns': ['identity_account', 'vote_account', 'total_mev_SOL', 'avg_ibrl_score', 'avg_build_time_score']},
    'validator_epoch_mev_bam_panel_50epoch.csv': {'key': 'validator_epoch_mev_bam_panel_50epoch', 'required_columns': ['identity_account', 'vote_account']},
    'validator_epoch_mev_bam_regression_stats.csv': {'key': 'validator_epoch_mev_bam_regression_stats', 'required_columns': []},
    'validator_epoch_mev_bam_mechanism_attribution.csv': {'key': 'validator_epoch_mev_bam_mechanism_attribution', 'required_columns': []},
}

STANDARDIZED = {
    'main_benchmark_model_panel.csv': 'standardized_main_benchmark_model_panel.csv',
    'jito_public_validator_orderflow_scores.csv': 'standardized_public_bundle_validator_orderflow_scores.csv',
    'structural_validator_mechanism_score_panel.csv': 'standardized_structural_validator_mechanism_score_panel.csv',
    'observable_proxy_validator_score_panel.csv': 'standardized_observable_proxy_validator_score_panel.csv',
    'validator_epoch_mev_bam_summary_50epoch.csv': 'standardized_validator_epoch_mev_bam_summary_50epoch.csv',
}

RESULT_LINEAGE = [
    {
        'result': 'main benchmark',
        'reported_number': 'N=409, R2=0.814967, adj R2=0.779259, candidate coef=0.316263, p=0.001627',
        'dv': 'log_mev_per_leader_slot',
        'iv_block': 'fixed 66 H7/B10 IVs from h7_b10_feature_list.csv',
        'source_assets': 'main_benchmark_model_panel.csv; h7_b10_feature_list.csv; h7_b10_benchmark_run_summary.json',
        'join_key': 'identity_account retained for audit; OLS sample is nonmissing DV + 66 IV rows',
        'processing_module': 'data_processing.process -> data_processing.variables -> analysis.main',
        'output_file': 'output/v27_simple_regression_stats.csv; output/v27_main_benchmark_coefficients.csv',
        'interpretation': 'canonical benchmark; exact v26 reproduction under fixed DV/IV discipline',
    },
    {
        'result': 'H7 + four mechanism scores',
        'reported_number': 'N=192, R2=0.874588; same-sample H7 R2=0.869763; incremental R2=0.004825',
        'dv': 'log_mev_per_leader_slot',
        'iv_block': '66 H7 IVs + four supplemental mechanism score IVs',
        'source_assets': 'v26 source panel + v22/v23/v24 validator panels + v25 50-epoch summary',
        'join_key': 'identity_account; v22-v24 validator renamed to identity_account; v25 already identity_account',
        'processing_module': 'data_processing.variables constructs signed z-score mechanism scores; model_selection.same_dv_iv_extensions estimates model',
        'output_file': 'output/v27_same_dv_iv_model_suite.csv; output/v27_mechanism_identification.csv',
        'interpretation': 'structural/proxy IV block; compare incremental R2 to same-sample H7, not raw R2 across samples',
    },
    {
        'result': 'H7 + v25 quality/infra/entity block',
        'reported_number': 'N=409, R2=0.825413; incremental R2=0.010445',
        'dv': 'log_mev_per_leader_slot',
        'iv_block': '66 H7 IVs + v25 non-MEV-history quality/infra/entity IVs',
        'source_assets': 'validator_epoch_mev_bam_summary_50epoch.csv plus v26 source panel',
        'join_key': 'identity_account',
        'processing_module': 'data_processing.process standardizes v25; model_selection.same_dv_iv_extensions z-scores IVs and estimates',
        'output_file': 'output/v27_same_dv_iv_model_suite.csv',
        'interpretation': 'same-DV operational quality/infra/entity extension; not a changed outcome',
    },
    {
        'result': 'H7 + v25 MEV-history predictive block',
        'reported_number': 'N=409, R2=0.829025; incremental R2=0.014058',
        'dv': 'log_mev_per_leader_slot',
        'iv_block': '66 H7 IVs + v25 MEV-history/persistence IVs',
        'source_assets': 'validator_epoch_mev_bam_summary_50epoch.csv plus v26 source panel',
        'join_key': 'identity_account',
        'processing_module': 'model_selection.same_dv_iv_extensions',
        'output_file': 'output/v27_same_dv_iv_model_suite.csv',
        'interpretation': 'predictive check only; not causal mechanism proof because IVs are MEV-history proxies',
    },
    {
        'result': 'top5 mechanism screened proxies',
        'reported_number': 'N=134, R2=0.914683; same-sample H7 R2=0.903137; incremental R2=0.011547',
        'dv': 'log_mev_per_leader_slot',
        'iv_block': '66 H7 IVs + top five screened mechanism proxy IVs excluding obvious MEV-history variables',
        'source_assets': 'v22/v24/v25 proxy fields plus v26 source panel',
        'join_key': 'identity_account with stricter nonmissing proxy sample',
        'processing_module': 'analysis.main single proxy screen -> model_selection.same_dv_iv_extensions',
        'output_file': 'output/v27_single_proxy_screen.csv; output/v27_same_dv_iv_model_suite.csv',
        'interpretation': 'exploratory; high raw R2 partly reflects smaller high-coverage sample',
    },
]


def row_count(path: Path) -> int | None:
    if path.suffix.lower() == '.json':
        return None
    try:
        return int(pd.read_csv(path, usecols=[0]).shape[0])
    except Exception:
        return None


def header(path: Path) -> list[str]:
    if path.suffix.lower() == '.json':
        return []
    return list(pd.read_csv(path, nrows=0).columns)


def standardize_csv(src: Path, dst: Path) -> dict[str, Any]:
    df = pd.read_csv(src)
    if 'validator' in df.columns and 'identity_account' not in df.columns:
        df = df.rename(columns={'validator': 'identity_account'})
    df.to_csv(dst, index=False)
    return {'processed_path': str(dst), 'processed_rows': len(df), 'processed_columns': len(df.columns)}


def run(mode: str = 'local') -> dict[str, Any]:
    if mode != 'local':
        raise SystemExit('data_processing.process currently processes local source_assets. Run python -m api_sources.pipelines.local_inventory first for source-like online refresh, or run pipeline.api_reproduction for isolated online overlay runs.')
    inventory = []
    schema_rows = []
    missing = []
    for filename, spec in REQUIRED_SOURCES.items():
        path = SOURCE_ASSETS / filename
        exists = path.exists()
        if not exists:
            missing.append(filename)
            cols = []
        else:
            cols = header(path)
        required_cols = spec['required_columns']
        missing_cols = [c for c in required_cols if c not in cols]
        inventory.append({
            'source_key': spec['key'],
            'filename': filename,
            'path': str(path),
            'exists': exists,
            'size_bytes': path.stat().st_size if exists else None,
            'row_count': row_count(path) if exists else None,
            'column_count': len(cols),
            'required_columns_present': not missing_cols,
            'missing_required_columns': ','.join(missing_cols),
        })
        for col in cols:
            schema_rows.append({'source_key': spec['key'], 'filename': filename, 'column': col})
    if missing:
        raise FileNotFoundError('Missing v27 source_assets: ' + ', '.join(missing))
    bad = [r for r in inventory if not r['required_columns_present']]
    if bad:
        raise ValueError('Source assets failed schema checks: ' + '; '.join(f"{r['filename']} missing {r['missing_required_columns']}" for r in bad))

    processed_rows = []
    for filename, outname in STANDARDIZED.items():
        info = standardize_csv(SOURCE_ASSETS / filename, PROCESSED / outname)
        processed_rows.append({'source_file': filename, 'processed_file': outname, **info})

    inv = pd.DataFrame(inventory)
    schema = pd.DataFrame(schema_rows)
    processed = pd.DataFrame(processed_rows)
    lineage = pd.DataFrame(RESULT_LINEAGE)
    inv.to_csv(PROCESSED / 'input_manifest.csv', index=False)
    schema.to_csv(PROCESSED / 'schema_manifest.csv', index=False)
    processed.to_csv(PROCESSED / 'processed_manifest.csv', index=False)
    lineage.to_csv(OUT / 'v27_result_lineage.csv', index=False)
    summary = {
        'finished_at': datetime.now(timezone.utc).isoformat(),
        'mode': mode,
        'source_assets': len(inv),
        'processed_files': len(processed),
        'result_lineage_rows': len(lineage),
    }
    (PROCESSED / 'process_summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps(summary, indent=2))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['local'], default='local')
    args = parser.parse_args()
    run(args.mode)


if __name__ == '__main__':
    main()