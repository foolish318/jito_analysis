from __future__ import annotations

import json
import math
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import nbformat as nbf
import numpy as np
import pandas as pd
import statsmodels.api as sm
from pandas.errors import PerformanceWarning

warnings.simplefilter('ignore', PerformanceWarning)

PKG = Path(__file__).resolve().parents[1]
ROOT = PKG.parent
DATA = PKG / 'data'
SOURCE_ASSETS = DATA / 'source_assets'
OUT = PKG / 'output'
NOTEBOOKS = PKG / 'notebooks'
TARGET = 'log_mev_per_leader_slot'
CANDIDATE = 'candidate_indicator'
MECHANISM_SCORES = [
    'supp_private_orderflow_searcherflow_score',
    'supp_bundle_outcome_execution_score',
    'supp_latency_infra_reliability_score',
    'supp_entity_vertical_integration_score',
]


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
            if isinstance(x, (float, np.floating)):
                vals.append('' if math.isnan(float(x)) else f'{float(x):.{digits}g}')
            elif isinstance(x, (int, np.integer)):
                vals.append(str(int(x)))
            else:
                vals.append(str(x).replace('\n', ' '))
        lines.append('| ' + ' | '.join(vals) + ' |')
    return '\n'.join(lines)


def zscore(series: pd.Series) -> pd.Series:
    x = pd.to_numeric(series, errors='coerce').replace([np.inf, -np.inf], np.nan)
    sd = x.std(ddof=0)
    if pd.isna(sd) or sd == 0:
        return pd.Series(np.nan, index=series.index)
    return (x - x.mean()) / sd


def fit_ols(frame: pd.DataFrame, y_col: str, x_cols: list[str], model: str) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame]:
    cols = [y_col] + x_cols
    tmp = frame[cols].replace([np.inf, -np.inf], np.nan).apply(pd.to_numeric, errors='coerce').dropna().copy()
    usable = []
    dropped = []
    for col in x_cols:
        if tmp[col].nunique(dropna=True) > 1:
            usable.append(col)
        else:
            dropped.append(col)
    tmp = tmp[[y_col] + usable]
    if len(tmp) < max(40, len(usable) + 8):
        raise ValueError(f'insufficient rows for {model}: n={len(tmp)} x={len(usable)}')
    X = sm.add_constant(tmp[usable], has_constant='add')
    fit = sm.OLS(tmp[y_col], X).fit(cov_type='HC3')
    coefs = pd.DataFrame({
        'model': model,
        'term': fit.params.index,
        'coef': fit.params.values,
        'std_error_hc3': fit.bse.values,
        't_stat': fit.tvalues.values,
        'p_value': fit.pvalues.values,
    })
    stats = {
        'model': model,
        'dependent_variable': y_col,
        'n': int(fit.nobs),
        'iv_count': len(usable),
        'r_squared': float(fit.rsquared),
        'adj_r_squared': float(fit.rsquared_adj),
        'candidate_coef': float(fit.params.get(CANDIDATE, np.nan)),
        'candidate_p_value': float(fit.pvalues.get(CANDIDATE, np.nan)),
        'dropped_constant_terms': ','.join(dropped),
    }
    return stats, coefs, tmp


def build_joined_panel() -> tuple[pd.DataFrame, list[str]]:
    main = pd.read_csv(DATA / 'main_benchmark_panel_with_ids.csv')
    feature_list = pd.read_csv(SOURCE_ASSETS / 'h7_b10_feature_list.csv')['feature'].astype(str).tolist()
    supplemental = pd.read_csv(DATA / 'model_panel.csv')
    extra_cols = [
        c for c in supplemental.columns
        if c == 'identity_account'
        or c.startswith('v22_')
        or c.startswith('v23_')
        or c.startswith('v24_')
        or c.startswith('v25_')
        or c.startswith('supp_')
        or c.startswith('has_')
    ]
    joined = main.merge(supplemental[extra_cols], on='identity_account', how='left')
    for col in [c for c in joined.columns if c.startswith(('v22_', 'v23_', 'v24_', 'v25_', 'supp_'))]:
        x = pd.to_numeric(joined[col], errors='coerce')
        if x.notna().sum() >= 20 and x.nunique(dropna=True) > 1:
            joined[f'z_iv__{col}'] = zscore(x)
    joined.to_csv(DATA / 'same_dv_joined_iv_panel.csv', index=False)
    return joined, feature_list


def existing_z(joined: pd.DataFrame, cols: list[str]) -> list[str]:
    out = []
    for col in cols:
        z = f'z_iv__{col}'
        if z in joined.columns and joined[z].notna().sum() >= 20:
            out.append(z)
    return out


def run_model_suite(joined: pd.DataFrame, feature_list: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    screen = pd.read_csv(OUT / 'v27_single_proxy_screen.csv')
    top_all = [p for p in screen['proxy'].tolist() if f'z_iv__{p}' in joined.columns][:5]
    outcome_like_tokens = ['log_total_mev', 'mev_per_block', 'total_mev', 'avg_mev', 'target_log_total_tip']
    top_mechanism = [
        p for p in screen['proxy'].tolist()
        if f'z_iv__{p}' in joined.columns and not any(tok in p.lower() for tok in outcome_like_tokens)
    ][:5]

    v25_quality = existing_z(joined, [
        'v25_avg_ibrl_score',
        'v25_avg_build_time_score',
        'v25_avg_vote_packing_score',
        'v25_avg_non_vote_packing_score',
        'v25_avg_bam_connection_rate',
        'v25_running_bam_epoch_share',
        'v25_running_jito_epoch_share',
        'v25_jito_directed_epoch_share',
        'v25_avg_median_block_build_ms',
        'v25_avg_mev_commission_bps',
        'v25_log_total_blocks_produced',
        'v25_log_epochs_seen',
    ])
    v25_history = existing_z(joined, [
        'v25_log_total_mev_SOL',
        'v25_log_mev_per_block_SOL',
        'v25_mev_per_block_SOL',
        'v25_positive_excess_epoch_share',
        'v25_avg_excess_mev_share',
        'v25_median_excess_mev_share',
    ])
    v22_orderflow = existing_z(joined, [
        'v22_unique_tippers',
        'v22_total_tip_SOL',
        'v22_bundles',
        'v22_relationship_score',
        'v22_positive_relationship_tip_share',
        'v22_tipper_tip_hhi',
        'v22_top_tipper_tip_share',
    ])
    score_z = existing_z(joined, MECHANISM_SCORES)

    specs: list[dict[str, Any]] = [
        {
            'model': 'same_dv_H7_v26_full_sample',
            'extra_ivs': [],
            'iv_block': 'canonical_v26_H7',
            'interpretation_guardrail': 'Main benchmark. Same DV and same 66 H7 IVs as v26.',
        },
    ]
    for score in MECHANISM_SCORES:
        specs.append({
            'model': f'same_dv_H7_plus_{score}',
            'extra_ivs': existing_z(joined, [score]),
            'iv_block': score,
            'interpretation_guardrail': 'Same DV. Adds one supplemental mechanism score as IV; compare only to H7 on the same nonmissing sample.',
        })
    specs.extend([
        {
            'model': 'same_dv_H7_plus_all_four_mechanism_scores',
            'extra_ivs': score_z,
            'iv_block': 'four_v22_v25_mechanism_scores',
            'interpretation_guardrail': 'Same DV. Structural/proxy IV block, not a changed outcome.',
        },
        {
            'model': 'same_dv_H7_plus_v25_quality_infra_entity_block',
            'extra_ivs': v25_quality,
            'iv_block': 'v25_50epoch_non_mev_history_quality_infra_entity',
            'interpretation_guardrail': 'Same DV. Uses 50-epoch operational/infra/entity IVs; excludes MEV-history variables from this block.',
        },
        {
            'model': 'same_dv_H7_plus_v25_mev_history_predictive_block',
            'extra_ivs': v25_history,
            'iv_block': 'v25_50epoch_mev_history_predictive',
            'interpretation_guardrail': 'Same DV, but these IVs are lag/parallel MEV-history proxies. Useful prediction check, not causal mechanism proof.',
        },
        {
            'model': 'same_dv_H7_plus_v22_public_orderflow_block',
            'extra_ivs': v22_orderflow,
            'iv_block': 'v22_public_bundle_orderflow',
            'interpretation_guardrail': 'Same DV. Public bundle/order-flow IV block; sample is limited by v22-v24 validator coverage.',
        },
        {
            'model': 'same_dv_H7_plus_top5_all_screened_proxy_IVs',
            'extra_ivs': existing_z(joined, top_all),
            'iv_block': 'top5_screened_all_proxies',
            'interpretation_guardrail': 'Same DV. Exploratory predictive IV screen; may include outcome-like historical proxies, so do not read causally.',
        },
        {
            'model': 'same_dv_H7_plus_top5_mechanism_screened_proxy_IVs',
            'extra_ivs': existing_z(joined, top_mechanism),
            'iv_block': 'top5_screened_mechanism_proxies_excluding_mev_history',
            'interpretation_guardrail': 'Same DV. Exploratory mechanism IV screen excluding obvious MEV-history variables.',
        },
    ])

    rows = []
    coef_frames = []
    for spec in specs:
        x_cols = feature_list + spec['extra_ivs']
        try:
            stats, coefs, sample = fit_ols(joined, TARGET, x_cols, spec['model'])
            baseline_stats, _, _ = fit_ols(joined.loc[sample.index], TARGET, feature_list, spec['model'] + '__H7_same_sample_baseline')
            stats.update({
                'same_dv_guardrail': True,
                'h7_iv_count': len(feature_list),
                'extra_iv_count': len(spec['extra_ivs']),
                'extra_ivs': ','.join(spec['extra_ivs']),
                'iv_block': spec['iv_block'],
                'baseline_h7_same_sample_r_squared': baseline_stats['r_squared'],
                'incremental_r2_vs_h7_same_sample': stats['r_squared'] - baseline_stats['r_squared'],
                'baseline_h7_same_sample_candidate_coef': baseline_stats['candidate_coef'],
                'candidate_attenuation_vs_h7_same_sample': baseline_stats['candidate_coef'] - stats['candidate_coef'],
                'interpretation_guardrail': spec['interpretation_guardrail'],
            })
            rows.append(stats)
            coef_frames.append(coefs)
        except Exception as exc:
            rows.append({
                'model': spec['model'],
                'dependent_variable': TARGET,
                'n': 0,
                'iv_count': len(x_cols),
                'r_squared': np.nan,
                'adj_r_squared': np.nan,
                'candidate_coef': np.nan,
                'candidate_p_value': np.nan,
                'same_dv_guardrail': True,
                'h7_iv_count': len(feature_list),
                'extra_iv_count': len(spec['extra_ivs']),
                'extra_ivs': ','.join(spec['extra_ivs']),
                'iv_block': spec['iv_block'],
                'baseline_h7_same_sample_r_squared': np.nan,
                'incremental_r2_vs_h7_same_sample': np.nan,
                'baseline_h7_same_sample_candidate_coef': np.nan,
                'candidate_attenuation_vs_h7_same_sample': np.nan,
                'interpretation_guardrail': 'NOT_RUN: ' + str(exc),
                'dropped_constant_terms': '',
            })
    out = pd.DataFrame(rows)
    coefs = pd.concat(coef_frames, ignore_index=True) if coef_frames else pd.DataFrame()
    out.to_csv(OUT / 'v27_same_dv_iv_model_suite.csv', index=False)
    coefs.to_csv(OUT / 'v27_same_dv_iv_coefficients.csv', index=False)
    return out, coefs


def update_report(model_suite: pd.DataFrame) -> None:
    report_path = OUT / 'v27_report.md'
    report = report_path.read_text(encoding='utf-8')
    marker = '\n## Same-DV Alternative IV Suite\n'
    if marker in report:
        report = report.split(marker)[0].rstrip() + '\n'
    table_cols = [
        'model', 'n', 'iv_count', 'extra_iv_count', 'r_squared', 'adj_r_squared',
        'baseline_h7_same_sample_r_squared', 'incremental_r2_vs_h7_same_sample',
        'candidate_coef', 'candidate_p_value', 'candidate_attenuation_vs_h7_same_sample',
        'iv_block', 'interpretation_guardrail'
    ]
    section = marker + f"""
This section is added specifically to enforce the modeling rule: DV is always `{TARGET}`. Only the IV set changes.

{md_table(model_suite[table_cols], digits=6)}

Reading rule: compare `incremental_r2_vs_h7_same_sample`, not raw R2 across different samples. The H7 full-sample benchmark remains the main result. IV blocks that use v25 MEV-history variables are predictive checks, not causal mechanism proof.
"""
    report_path.write_text(report.rstrip() + '\n' + section, encoding='utf-8')


def update_runbook_and_docs(model_suite: pd.DataFrame) -> None:
    runbook_path = PKG / 'runbook.md'
    runbook = runbook_path.read_text(encoding='utf-8')
    insert = "python -m model_selection.same_dv_iv_extensions"
    if insert not in runbook:
        runbook = runbook.replace(
            "python -m analysis.main\n",
            "python -m analysis.main\n" + insert + "\n",
        )
        runbook += "\n## Same-DV IV extension\n\n`v27/model_selection.same_dv_iv_extensions` adds alternative IV blocks while keeping DV fixed as `log_mev_per_leader_slot`. The main output is `v27/output/v27_same_dv_iv_model_suite.csv`.\n"
        runbook_path.write_text(runbook, encoding='utf-8')

    data_doc_path = PKG / 'data proxy variable.md'
    data_doc = data_doc_path.read_text(encoding='utf-8')
    marker = '\n## Same-DV IV Extension\n'
    if marker in data_doc:
        data_doc = data_doc.split(marker)[0].rstrip() + '\n'
    block = marker + """
The same-DV extension tries additional IV blocks without changing the dependent variable.

- DV remains `log_mev_per_leader_slot` in every model.
- Baseline IVs remain the 66 fixed H7/B10 regressors.
- Extra IVs are z-scored v22-v25 proxy variables or constructed mechanism scores.
- The correct comparison column is `incremental_r2_vs_h7_same_sample`.

See `v27/output/v27_same_dv_iv_model_suite.csv` and `v27/output/v27_same_dv_iv_coefficients.csv`.
"""
    data_doc_path.write_text(data_doc.rstrip() + '\n' + block, encoding='utf-8')


def update_workbook(model_suite: pd.DataFrame, coefs: pd.DataFrame) -> None:
    workbook = OUT / 'v27_analysis_workbook.xlsx'
    if workbook.exists():
        with pd.ExcelWriter(workbook, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
            model_suite.to_excel(writer, sheet_name='same_DV_IV_suite', index=False)
            coefs.to_excel(writer, sheet_name='same_DV_IV_coeffs', index=False)


def update_notebooks() -> None:
    analysis_path = NOTEBOOKS / 'analysis.ipynb'
    if analysis_path.exists():
        nb = nbf.read(analysis_path, as_version=4)
        marker = '# Same-DV IV extension'
        nb.cells = [c for c in nb.cells if marker not in ''.join(c.get('source', ''))]
        nb.cells.insert(3, nbf.v4.new_code_cell(
            marker + "\n"
            "same_dv = pd.read_csv(OUT / 'v27_same_dv_iv_model_suite.csv')\n"
            "display(Markdown('## Same-DV IV model suite'))\n"
            "display(same_dv)"
        ))
        nbf.write(nb, analysis_path)


def update_summary(model_suite: pd.DataFrame) -> dict[str, Any]:
    summary_path = OUT / 'run_summary.json'
    summary = json.loads(summary_path.read_text(encoding='utf-8'))
    valid = model_suite.dropna(subset=['r_squared']).copy()
    best = valid.sort_values('r_squared', ascending=False).iloc[0]
    best_inc = valid.sort_values('incremental_r2_vs_h7_same_sample', ascending=False).iloc[0]
    summary.update({
        'same_dv_iv_extension_finished_at': datetime.now(timezone.utc).isoformat(),
        'same_dv_best_model_by_r2': str(best['model']),
        'same_dv_best_r_squared': float(best['r_squared']),
        'same_dv_best_incremental_model': str(best_inc['model']),
        'same_dv_best_incremental_r2_vs_h7_same_sample': float(best_inc['incremental_r2_vs_h7_same_sample']),
        'same_dv_extension_output': 'v27/output/v27_same_dv_iv_model_suite.csv',
    })
    summary_path.write_text(json.dumps(summary, indent=2), encoding='utf-8')
    return summary


def run() -> dict[str, Any]:
    joined, feature_list = build_joined_panel()
    model_suite, coefs = run_model_suite(joined, feature_list)
    update_report(model_suite)
    update_runbook_and_docs(model_suite)
    update_workbook(model_suite, coefs)
    update_notebooks()
    return update_summary(model_suite)


if __name__ == '__main__':
    print(json.dumps(run(), indent=2))