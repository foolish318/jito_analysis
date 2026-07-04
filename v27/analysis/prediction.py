from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import RidgeCV
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

PKG = Path(__file__).resolve().parents[1]
DATA = PKG / 'data'
SOURCE_ASSETS = DATA / 'source_assets'
OUT = PKG / 'output'
NOTEBOOKS = PKG / 'notebooks'
TARGET = 'log_mev_per_leader_slot'
SEED = 27
FOLDS = 5
MIN_TRAIN_ROWS = 80
MIN_TEST_ROWS = 8
RIDGE_ALPHAS = np.array([0.01, 0.1, 1.0, 3.0, 10.0, 30.0, 100.0, 300.0])

MECHANISM_SCORES = [
    'supp_private_orderflow_searcherflow_score',
    'supp_bundle_outcome_execution_score',
    'supp_latency_infra_reliability_score',
    'supp_entity_vertical_integration_score',
]

OUTCOME_LIKE_TOKENS = [
    'log_total_mev',
    'mev_per_block',
    'total_mev',
    'avg_mev',
    'target_log_total_tip',
]

V25_HISTORY_PROXIES = [
    'v25_log_total_mev_SOL',
    'v25_log_mev_per_block_SOL',
    'v25_mev_per_block_SOL',
    'v25_positive_excess_epoch_share',
    'v25_avg_excess_mev_share',
    'v25_median_excess_mev_share',
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


def load_feature_list() -> list[str]:
    return pd.read_csv(SOURCE_ASSETS / 'h7_b10_feature_list.csv')['feature'].astype(str).tolist()


def build_or_load_joined_panel() -> pd.DataFrame:
    path = DATA / 'same_dv_joined_iv_panel.csv'
    if path.exists():
        return pd.read_csv(path)
    main = pd.read_csv(DATA / 'main_benchmark_panel_with_ids.csv')
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
    joined.to_csv(path, index=False)
    return joined


def z_cols(cols: list[str], frame: pd.DataFrame) -> list[str]:
    out = []
    for col in cols:
        z = f'z_iv__{col}'
        if z in frame.columns and pd.to_numeric(frame[z], errors='coerce').notna().sum() >= 20:
            out.append(z)
    return out


def is_outcome_like(col: str) -> bool:
    lower = col.lower().replace('z_iv__', '')
    return any(token in lower for token in OUTCOME_LIKE_TOKENS)


def candidate_proxy_pool(frame: pd.DataFrame, *, exclude_outcome_like: bool) -> list[str]:
    pool = []
    for col in frame.columns:
        if not col.startswith('z_iv__'):
            continue
        raw = col.removeprefix('z_iv__')
        if not raw.startswith(('v22_', 'v23_', 'v24_', 'v25_', 'supp_')):
            continue
        if raw.startswith('has_'):
            continue
        if exclude_outcome_like and is_outcome_like(raw):
            continue
        x = pd.to_numeric(frame[col], errors='coerce')
        if x.notna().sum() >= 20 and x.nunique(dropna=True) > 1:
            pool.append(col)
    return sorted(pool)


def fixed_screen_features(frame: pd.DataFrame, *, exclude_outcome_like: bool, top_k: int = 5) -> list[str]:
    screen_path = OUT / 'v27_single_proxy_screen.csv'
    if not screen_path.exists():
        return []
    screen = pd.read_csv(screen_path)
    selected = []
    for proxy in screen['proxy'].astype(str).tolist():
        if exclude_outcome_like and is_outcome_like(proxy):
            continue
        z = f'z_iv__{proxy}'
        if z in frame.columns:
            selected.append(z)
        if len(selected) >= top_k:
            break
    return selected


def numeric_design(frame: pd.DataFrame, y_col: str, x_cols: list[str]) -> pd.DataFrame:
    cols = [y_col] + x_cols
    return frame[cols].replace([np.inf, -np.inf], np.nan).apply(pd.to_numeric, errors='coerce').dropna().copy()


def usable_features(train: pd.DataFrame, x_cols: list[str]) -> list[str]:
    out = []
    for col in x_cols:
        x = pd.to_numeric(train[col], errors='coerce')
        if x.notna().sum() >= 2 and x.nunique(dropna=True) > 1:
            out.append(col)
    return out


def fit_lstsq(train: pd.DataFrame, y_col: str, x_cols: list[str]) -> tuple[np.ndarray, list[str], float, int] | None:
    train = numeric_design(train, y_col, x_cols)
    use = usable_features(train, x_cols)
    train = numeric_design(train, y_col, use)
    if len(train) < max(MIN_TRAIN_ROWS, len(use) + 8):
        return None
    X = np.column_stack([np.ones(len(train)), train[use].to_numpy(dtype=float)])
    y = train[y_col].to_numpy(dtype=float)
    coef = np.linalg.lstsq(X, y, rcond=None)[0]
    yhat = X @ coef
    sse = float(np.sum((y - yhat) ** 2))
    sst = float(np.sum((y - y.mean()) ** 2))
    r2 = float(1 - sse / sst) if sst > 0 else np.nan
    return coef, use, r2, len(train)


def predict_lstsq(test: pd.DataFrame, y_col: str, coef: np.ndarray, x_cols: list[str]) -> pd.DataFrame:
    test = numeric_design(test, y_col, x_cols)
    if len(test) < MIN_TEST_ROWS:
        return pd.DataFrame()
    X = np.column_stack([np.ones(len(test)), test[x_cols].to_numpy(dtype=float)])
    out = pd.DataFrame({
        'row_id': test.index.astype(str),
        'y': test[y_col].to_numpy(dtype=float),
        'yhat': X @ coef,
    }, index=test.index)
    if 'identity_account' in test.columns:
        out['identity_account'] = test['identity_account'].astype(str).values
    return out


def ridge_usable_features(train: pd.DataFrame, x_cols: list[str]) -> list[str]:
    out = []
    for col in x_cols:
        if col not in train.columns:
            continue
        x = pd.to_numeric(train[col], errors='coerce')
        if x.notna().sum() >= 2 and x.nunique(dropna=True) > 1:
            out.append(col)
    return out


def fit_ridge_pipeline(train: pd.DataFrame, y_col: str, x_cols: list[str]) -> tuple[Pipeline, list[str], float, int, float] | None:
    train = train.copy()
    train[y_col] = pd.to_numeric(train[y_col], errors='coerce')
    train = train.loc[train[y_col].notna()].copy()
    use = ridge_usable_features(train, x_cols)
    if len(train) < max(MIN_TRAIN_ROWS, len(use) + 8) or not use:
        return None
    X = train[use].apply(pd.to_numeric, errors='coerce')
    y = train[y_col].to_numpy(dtype=float)
    cv = 5 if len(train) >= 80 else None
    model = Pipeline([
        ('imputer', SimpleImputer(strategy='median')),
        ('scaler', StandardScaler()),
        ('ridge', RidgeCV(alphas=RIDGE_ALPHAS, cv=cv, scoring='neg_mean_squared_error' if cv else None)),
    ])
    model.fit(X, y)
    yhat = model.predict(X)
    sse = float(np.sum((y - yhat) ** 2))
    sst = float(np.sum((y - y.mean()) ** 2))
    r2 = float(1 - sse / sst) if sst > 0 else np.nan
    alpha = float(model.named_steps['ridge'].alpha_)
    return model, use, r2, len(train), alpha


def predict_ridge(test: pd.DataFrame, y_col: str, model: Pipeline, x_cols: list[str]) -> pd.DataFrame:
    test = test.copy()
    test[y_col] = pd.to_numeric(test[y_col], errors='coerce')
    test = test.loc[test[y_col].notna()].copy()
    if len(test) < MIN_TEST_ROWS:
        return pd.DataFrame()
    X = test[x_cols].apply(pd.to_numeric, errors='coerce')
    out = pd.DataFrame({
        'row_id': test.index.astype(str),
        'y': test[y_col].to_numpy(dtype=float),
        'yhat': model.predict(X),
    }, index=test.index)
    if 'identity_account' in test.columns:
        out['identity_account'] = test['identity_account'].astype(str).values
    if 'epoch' in test.columns:
        out['epoch'] = pd.to_numeric(test['epoch'], errors='coerce').values
    return out


def full_sample_ridge_r2(frame: pd.DataFrame, y_col: str, x_cols: list[str]) -> tuple[float, int, int, float]:
    fit = fit_ridge_pipeline(frame, y_col, x_cols)
    if fit is None:
        return np.nan, 0, 0, np.nan
    _, use, r2, n, alpha = fit
    return r2, n, len(use), alpha


def make_folds(index: pd.Index, n_folds: int = FOLDS, seed: int = SEED) -> list[np.ndarray]:
    rng = np.random.default_rng(seed)
    values = np.array(index)
    rng.shuffle(values)
    return [fold for fold in np.array_split(values, n_folds) if len(fold)]


def full_sample_r2(frame: pd.DataFrame, y_col: str, x_cols: list[str]) -> tuple[float, int, int]:
    fit = fit_lstsq(frame, y_col, x_cols)
    if fit is None:
        return np.nan, 0, 0
    _, use, r2, n = fit
    return r2, n, len(use)


def evaluate_fixed_spec(
    frame: pd.DataFrame,
    feature_list: list[str],
    model: str,
    extra_ivs: list[str],
    notes: str,
) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    x_cols = feature_list + extra_ivs
    base = numeric_design(frame, TARGET, x_cols)
    folds = make_folds(base.index)
    pred_frames = []
    fold_rows = []
    for fold_id, test_idx in enumerate(folds, start=1):
        test_mask = base.index.isin(test_idx)
        train = base.loc[~test_mask].copy()
        test = base.loc[test_mask].copy()
        fit = fit_lstsq(train, TARGET, x_cols)
        if fit is None:
            continue
        coef, use, train_r2, train_n = fit
        pred = predict_lstsq(test, TARGET, coef, use)
        if pred.empty:
            continue
        pred['model'] = model
        pred['fold'] = fold_id
        pred['train_mean'] = float(numeric_design(train, TARGET, use)[TARGET].mean())
        pred_frames.append(pred)
        fold_rows.append({
            'model': model,
            'fold': fold_id,
            'train_n': train_n,
            'test_n': len(pred),
            'train_r_squared': train_r2,
            'selected_iv_count': len(use),
            'selected_extra_ivs': ','.join([c for c in use if c not in feature_list]),
        })
    preds = pd.concat(pred_frames, ignore_index=True) if pred_frames else pd.DataFrame()
    summary = summarize_predictions(frame, model, x_cols, preds, notes, 'fixed_specification')
    return summary, pd.DataFrame(fold_rows), selection_rows(model, 0, extra_ivs, 'fixed_full_sample_screen'), preds


def screen_train_candidates(train: pd.DataFrame, feature_list: list[str], pool: list[str], top_k: int) -> pd.DataFrame:
    rows = []
    for cand in pool:
        fit = fit_lstsq(train, TARGET, feature_list + [cand])
        if fit is None:
            continue
        _, use, r2, n = fit
        if cand not in use:
            continue
        adj = 1 - (1 - r2) * (n - 1) / max(n - len(use) - 1, 1)
        rows.append({'proxy': cand, 'train_n': n, 'train_r_squared': r2, 'train_adj_r_squared': adj})
    if not rows:
        return pd.DataFrame(columns=['proxy', 'train_n', 'train_r_squared', 'train_adj_r_squared'])
    out = pd.DataFrame(rows).sort_values(['train_adj_r_squared', 'train_r_squared', 'train_n'], ascending=[False, False, False])
    return out.head(top_k).reset_index(drop=True)


def evaluate_ridge_fixed_spec(
    frame: pd.DataFrame,
    feature_list: list[str],
    model: str,
    extra_ivs: list[str],
    notes: str,
) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    x_cols = feature_list + extra_ivs
    base = frame.loc[pd.to_numeric(frame[TARGET], errors='coerce').notna()].copy()
    folds = make_folds(base.index)
    pred_frames = []
    fold_rows = []
    for fold_id, test_idx in enumerate(folds, start=1):
        test_mask = base.index.isin(test_idx)
        train = base.loc[~test_mask].copy()
        test = base.loc[test_mask].copy()
        fit = fit_ridge_pipeline(train, TARGET, x_cols)
        if fit is None:
            continue
        model_obj, use, train_r2, train_n, alpha = fit
        pred = predict_ridge(test, TARGET, model_obj, use)
        if pred.empty:
            continue
        pred['model'] = model
        pred['fold'] = fold_id
        pred['train_mean'] = float(pd.to_numeric(train[TARGET], errors='coerce').dropna().mean())
        pred_frames.append(pred)
        fold_rows.append({
            'model': model,
            'fold': fold_id,
            'train_n': train_n,
            'test_n': len(pred),
            'train_r_squared': train_r2,
            'selected_iv_count': len(use),
            'ridge_alpha': alpha,
            'selected_extra_ivs': ','.join([c for c in use if c not in feature_list]),
        })
    preds = pd.concat(pred_frames, ignore_index=True) if pred_frames else pd.DataFrame()
    summary = summarize_predictions(frame, model, x_cols, preds, notes, 'ridge_fixed_imputed_cv_alpha')
    in_r2, in_n, iv_count, alpha = full_sample_ridge_r2(frame, TARGET, x_cols)
    summary['in_sample_n'] = in_n
    summary['in_sample_r_squared'] = in_r2
    summary['iv_count_full_spec'] = iv_count
    summary['ridge_alpha_full_sample'] = alpha
    return summary, pd.DataFrame(fold_rows), selection_rows(model, 0, extra_ivs, 'ridge_fixed_spec'), preds


def evaluate_nested_screen(
    frame: pd.DataFrame,
    feature_list: list[str],
    model: str,
    pool: list[str],
    notes: str,
    top_k: int = 5,
) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    base = numeric_design(frame, TARGET, feature_list)
    folds = make_folds(base.index)
    pred_frames = []
    fold_rows = []
    selected_rows = []
    for fold_id, test_idx in enumerate(folds, start=1):
        test_mask = base.index.isin(test_idx)
        train_idx = base.loc[~test_mask].index
        train_full = frame.loc[train_idx].copy()
        test_full = frame.loc[test_idx].copy()
        selected = screen_train_candidates(train_full, feature_list, pool, top_k)
        selected_cols = selected['proxy'].tolist()
        for rank, row in selected.reset_index(drop=True).iterrows():
            selected_rows.append({
                'model': model,
                'fold': fold_id,
                'rank': rank + 1,
                'selected_proxy': row['proxy'],
                'screen_train_n': row['train_n'],
                'screen_train_r_squared': row['train_r_squared'],
                'screen_train_adj_r_squared': row['train_adj_r_squared'],
                'selection_mode': 'nested_train_fold_screen',
            })
        x_cols = feature_list + selected_cols
        fit = fit_lstsq(train_full, TARGET, x_cols)
        if fit is None:
            continue
        coef, use, train_r2, train_n = fit
        pred = predict_lstsq(test_full, TARGET, coef, use)
        if pred.empty:
            continue
        pred['model'] = model
        pred['fold'] = fold_id
        pred['train_mean'] = float(numeric_design(train_full, TARGET, use)[TARGET].mean())
        pred_frames.append(pred)
        fold_rows.append({
            'model': model,
            'fold': fold_id,
            'train_n': train_n,
            'test_n': len(pred),
            'train_r_squared': train_r2,
            'selected_iv_count': len(use),
            'selected_extra_ivs': ','.join([c for c in use if c not in feature_list]),
        })
    preds = pd.concat(pred_frames, ignore_index=True) if pred_frames else pd.DataFrame()
    summary = summarize_predictions(frame, model, feature_list, preds, notes, 'nested_train_fold_screen')
    summary['in_sample_n'] = np.nan
    summary['in_sample_r_squared'] = np.nan
    summary['iv_count_full_spec'] = len(feature_list) + top_k
    return summary, pd.DataFrame(fold_rows), pd.DataFrame(selected_rows), preds


def selection_rows(model: str, fold: int, cols: list[str], mode: str) -> pd.DataFrame:
    return pd.DataFrame([
        {'model': model, 'fold': fold, 'rank': i + 1, 'selected_proxy': col, 'selection_mode': mode}
        for i, col in enumerate(cols)
    ])


def empty_prediction_summary(model: str, validation_design: str, in_n: int, in_r2: float, iv_count: int, notes: str) -> dict[str, Any]:
    keys = [
        'baseline_mse_train_mean',
        'baseline_rmse_train_mean',
        'baseline_mae_train_mean',
        'oos_mse',
        'oos_rmse',
        'oos_mae',
        'oos_median_abs_error',
        'oos_p75_abs_error',
        'oos_p90_abs_error',
        'oos_mean_abs_pct_error_from_log',
        'oos_median_abs_pct_error_from_log',
        'oos_p90_abs_pct_error_from_log',
        'oos_r2_vs_train_mean',
        'oos_r2_vs_test_mean',
        'rmse_ratio_vs_train_mean',
        'rmse_improvement_vs_train_mean',
        'residual_p10',
        'residual_p25',
        'residual_p50',
        'residual_p75',
        'residual_p90',
    ]
    out = {
        'model': model,
        'dependent_variable': TARGET,
        'validation_design': validation_design,
        'folds': 0,
        'test_n_total': 0,
        'in_sample_n': in_n,
        'in_sample_r_squared': in_r2,
        'iv_count_full_spec': iv_count,
        'notes': notes,
    }
    out.update({key: np.nan for key in keys})
    return out


def summarize_predictions(
    frame: pd.DataFrame,
    model: str,
    x_cols: list[str],
    preds: pd.DataFrame,
    notes: str,
    validation_design: str,
) -> dict[str, Any]:
    in_r2, in_n, iv_count = full_sample_r2(frame, TARGET, x_cols)
    if preds.empty:
        return empty_prediction_summary(model, validation_design, in_n, in_r2, iv_count, notes)

    y = preds['y'].to_numpy(dtype=float)
    yhat = preds['yhat'].to_numpy(dtype=float)
    train_mean = preds['train_mean'].to_numpy(dtype=float)
    residual = y - yhat
    abs_error = np.abs(residual)
    pct_abs_error = np.expm1(abs_error)
    baseline_error = y - train_mean
    sse = float(np.sum(residual ** 2))
    baseline_sse = float(np.sum(baseline_error ** 2))
    sst_test_mean = float(np.sum((y - y.mean()) ** 2))
    oos_mse = float(np.mean(residual ** 2))
    oos_rmse = float(np.sqrt(oos_mse))
    baseline_mse = float(np.mean(baseline_error ** 2))
    baseline_rmse = float(np.sqrt(baseline_mse))
    qs = np.quantile(residual, [0.10, 0.25, 0.50, 0.75, 0.90])
    return {
        'model': model,
        'dependent_variable': TARGET,
        'validation_design': validation_design,
        'folds': int(preds['fold'].nunique()),
        'test_n_total': int(len(preds)),
        'in_sample_n': in_n,
        'in_sample_r_squared': in_r2,
        'iv_count_full_spec': iv_count,
        'baseline_mse_train_mean': baseline_mse,
        'baseline_rmse_train_mean': baseline_rmse,
        'baseline_mae_train_mean': float(np.mean(np.abs(baseline_error))),
        'oos_mse': oos_mse,
        'oos_rmse': oos_rmse,
        'oos_mae': float(np.mean(abs_error)),
        'oos_median_abs_error': float(np.median(abs_error)),
        'oos_p75_abs_error': float(np.quantile(abs_error, 0.75)),
        'oos_p90_abs_error': float(np.quantile(abs_error, 0.90)),
        'oos_mean_abs_pct_error_from_log': float(np.mean(pct_abs_error)),
        'oos_median_abs_pct_error_from_log': float(np.median(pct_abs_error)),
        'oos_p90_abs_pct_error_from_log': float(np.quantile(pct_abs_error, 0.90)),
        'oos_r2_vs_train_mean': float(1 - sse / baseline_sse) if baseline_sse > 0 else np.nan,
        'oos_r2_vs_test_mean': float(1 - sse / sst_test_mean) if sst_test_mean > 0 else np.nan,
        'rmse_ratio_vs_train_mean': float(oos_rmse / baseline_rmse) if baseline_rmse > 0 else np.nan,
        'rmse_improvement_vs_train_mean': float(baseline_rmse - oos_rmse),
        'residual_p10': float(qs[0]),
        'residual_p25': float(qs[1]),
        'residual_p50': float(qs[2]),
        'residual_p75': float(qs[3]),
        'residual_p90': float(qs[4]),
        'notes': notes,
    }


def run_prediction_suite() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    frame = build_or_load_joined_panel()
    feature_list = load_feature_list()
    fixed_top_all = fixed_screen_features(frame, exclude_outcome_like=False, top_k=5)
    fixed_top_mech = fixed_screen_features(frame, exclude_outcome_like=True, top_k=5)
    v25_history = z_cols(V25_HISTORY_PROXIES, frame)
    score_z = z_cols(MECHANISM_SCORES, frame)
    pool_all = candidate_proxy_pool(frame, exclude_outcome_like=False)
    pool_mech = candidate_proxy_pool(frame, exclude_outcome_like=True)

    fixed_specs = [
        (
            'prediction_H7_benchmark',
            [],
            'Fixed 66 H7/B10 IV benchmark. This is the baseline prediction model under the canonical DV.',
        ),
        (
            'prediction_H7_plus_four_mechanism_scores',
            score_z,
            'Fixed four mechanism-score IV block. Same DV; evaluates whether mechanism scores predict held-out validators.',
        ),
        (
            'prediction_H7_plus_v25_mev_history_predictive_block',
            v25_history,
            'Predictive block using MEV-history variables. This can predict well but is not causal mechanism evidence.',
        ),
        (
            'prediction_H7_plus_top5_all_screened_proxy_fixed',
            fixed_top_all,
            'Fixed top five proxies selected on the full sample. This is intentionally reported as optimistic because selection used all rows.',
        ),
        (
            'prediction_H7_plus_top5_mechanism_screened_proxy_fixed',
            fixed_top_mech,
            'Fixed top five non-obvious-MEV-history mechanism proxies selected on the full sample. Still optimistic because selection used all rows.',
        ),
    ]

    summaries = []
    folds = []
    selections = []
    predictions = []
    for model, extra, notes in fixed_specs:
        summary, fold_df, selection_df, pred_df = evaluate_fixed_spec(frame, feature_list, model, extra, notes)
        summaries.append(summary)
        folds.append(fold_df)
        selections.append(selection_df)
        predictions.append(pred_df)

    ridge_specs = [
        (
            'prediction_ridge_H7_benchmark',
            [],
            'RidgeCV benchmark using the same 66 H7/B10 IVs. This tests whether shrinkage improves held-out error.',
        ),
        (
            'prediction_ridge_H7_plus_v25_mev_history_predictive_block',
            v25_history,
            'RidgeCV with v25 MEV-history predictive variables. Predictive only, not causal mechanism evidence.',
        ),
        (
            'prediction_ridge_H7_plus_all_proxy_pool_imputed',
            pool_all,
            'RidgeCV over the full z-scored proxy pool with train-fold median imputation. This is a high-dimensional predictive benchmark.',
        ),
        (
            'prediction_ridge_H7_plus_mechanism_proxy_pool_imputed',
            pool_mech,
            'RidgeCV over non-obvious-MEV-history mechanism proxies with train-fold median imputation.',
        ),
    ]
    for model, extra, notes in ridge_specs:
        summary, fold_df, selection_df, pred_df = evaluate_ridge_fixed_spec(frame, feature_list, model, extra, notes)
        summaries.append(summary)
        folds.append(fold_df)
        selections.append(selection_df)
        predictions.append(pred_df)

    for model, pool, notes in [
        (
            'prediction_H7_plus_top5_all_screened_proxy_nested',
            pool_all,
            'Nested 5-fold screen: top five proxies are re-selected inside each training fold. This is the more honest OOS analogue of the high in-sample screen.',
        ),
        (
            'prediction_H7_plus_top5_mechanism_screened_proxy_nested',
            pool_mech,
            'Nested 5-fold screen excluding obvious MEV-history variables. This is the more honest OOS mechanism-proxy check.',
        ),
    ]:
        summary, fold_df, selection_df, pred_df = evaluate_nested_screen(frame, feature_list, model, pool, notes)
        summaries.append(summary)
        folds.append(fold_df)
        selections.append(selection_df)
        predictions.append(pred_df)

    perf = pd.DataFrame(summaries).sort_values(['oos_rmse', 'oos_mae'], ascending=[True, True], na_position='last')
    fold_out = pd.concat(folds, ignore_index=True) if folds else pd.DataFrame()
    selection_out = pd.concat(selections, ignore_index=True) if selections else pd.DataFrame()
    prediction_out = pd.concat(predictions, ignore_index=True) if predictions else pd.DataFrame()
    return perf, fold_out, selection_out, prediction_out


def add_prediction_error_columns(predictions: pd.DataFrame) -> pd.DataFrame:
    if predictions.empty:
        return predictions.copy()
    out = predictions.copy()
    out['residual'] = out['y'] - out['yhat']
    out['abs_error'] = out['residual'].abs()
    out['squared_error'] = out['residual'] ** 2
    out['abs_pct_error_from_log'] = np.expm1(out['abs_error'])
    out['signed_pct_error_from_log'] = np.expm1(out['yhat'] - out['y'])
    return out


def build_calibration_table(predictions: pd.DataFrame, bins: int = 5) -> pd.DataFrame:
    if predictions.empty:
        return pd.DataFrame()
    pred = add_prediction_error_columns(predictions)
    rows = []
    for model, group in pred.groupby('model', sort=False):
        use = group.copy()
        try:
            use['prediction_bin'] = pd.qcut(use['yhat'], q=min(bins, use['yhat'].nunique()), duplicates='drop')
        except ValueError:
            use['prediction_bin'] = 'all'
        for i, (_, bin_df) in enumerate(use.groupby('prediction_bin', observed=True), start=1):
            rows.append({
                'model': model,
                'prediction_bin': i,
                'n': int(len(bin_df)),
                'mean_predicted_log_mev_per_leader_slot': float(bin_df['yhat'].mean()),
                'mean_actual_log_mev_per_leader_slot': float(bin_df['y'].mean()),
                'mean_residual_actual_minus_predicted': float(bin_df['residual'].mean()),
                'rmse': float(np.sqrt(bin_df['squared_error'].mean())),
                'mae': float(bin_df['abs_error'].mean()),
                'median_abs_error': float(bin_df['abs_error'].median()),
                'median_abs_pct_error_from_log': float(bin_df['abs_pct_error_from_log'].median()),
            })
    return pd.DataFrame(rows)


def update_report(
    perf: pd.DataFrame,
    folds: pd.DataFrame,
    selections: pd.DataFrame,
    calibration: pd.DataFrame,
    rank_metrics: pd.DataFrame,
    panel_perf: pd.DataFrame,
) -> None:
    report_path = OUT / 'v27_report.md'
    if report_path.exists():
        report = report_path.read_text(encoding='utf-8')
    else:
        report = '# v27 Report\n'
    marker = '\n## Prediction And Out-of-sample Validation\n'
    if marker in report:
        report = report.split(marker)[0].rstrip() + '\n'
    cols = [
        'model',
        'validation_design',
        'test_n_total',
        'in_sample_r_squared',
        'baseline_rmse_train_mean',
        'oos_rmse',
        'oos_mae',
        'oos_median_abs_error',
        'oos_p90_abs_error',
        'oos_median_abs_pct_error_from_log',
        'oos_p90_abs_pct_error_from_log',
        'oos_r2_vs_train_mean',
    ]
    text = marker + f"""

The prediction module keeps the DV fixed as `{TARGET}` and evaluates whether the in-sample explanatory models generalize to held-out validators. Prediction quality should be read primarily through out-of-sample error: RMSE, MAE, median absolute error, p90 absolute error, and the log-error-to-percent-error transform `exp(abs(error))-1`. `oos_r2_vs_train_mean` is retained only as a relative baseline comparison.

{md_table(perf[cols], max_rows=20, digits=6)}

### Prediction Calibration

The calibration table bins held-out predictions by predicted value and compares mean predicted log MEV to mean realized log MEV. Large residuals or monotone bin bias indicate prediction error even when relative R2 is positive.

{md_table(calibration, max_rows=35, digits=6)}

### Rank And Bucket Prediction

Rank metrics evaluate whether a model identifies high-MEV validators even when level prediction is noisy. Precision/recall are computed for held-out top-quartile and top-decile buckets.

{md_table(rank_metrics, max_rows=40, digits=6)}

### Panel Lag Forecast

This is an additional validator-epoch forecast, separate from the main cross-sectional DV. It predicts future epoch-level `log_mev_rewards_SOL` from lagged validator and operational variables.

{md_table(panel_perf, max_rows=20, digits=6)}

Interpretation guardrail: fixed full-sample screened proxy models are optimistic because variable selection used the whole sample. Nested screened models re-select proxies inside each training fold and are the more credible out-of-sample check. The panel lag forecast is predictive only and uses a different epoch-level target, so it is not a replacement for the main fixed-DV result.
"""
    report = report.rstrip() + '\n' + text
    report_path.write_text(report, encoding='utf-8')


def update_workbook(
    perf: pd.DataFrame,
    folds: pd.DataFrame,
    selections: pd.DataFrame,
    calibration: pd.DataFrame,
    predictions: pd.DataFrame,
    rank_metrics: pd.DataFrame,
    panel_perf: pd.DataFrame,
    panel_predictions: pd.DataFrame,
) -> None:
    workbook = OUT / 'v27_analysis_workbook.xlsx'
    if not workbook.exists():
        return
    with pd.ExcelWriter(workbook, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
        perf.to_excel(writer, sheet_name='prediction_performance', index=False)
        folds.to_excel(writer, sheet_name='prediction_folds', index=False)
        selections.to_excel(writer, sheet_name='prediction_selected', index=False)
        calibration.to_excel(writer, sheet_name='prediction_calibration', index=False)
        predictions.head(5000).to_excel(writer, sheet_name='prediction_rows', index=False)
        rank_metrics.to_excel(writer, sheet_name='prediction_rank_bucket', index=False)
        panel_perf.to_excel(writer, sheet_name='panel_lag_forecast', index=False)
        panel_predictions.head(5000).to_excel(writer, sheet_name='panel_lag_rows', index=False)



def build_rank_bucket_metrics(predictions: pd.DataFrame) -> pd.DataFrame:
    if predictions.empty:
        return pd.DataFrame()
    pred = add_prediction_error_columns(predictions)
    rows = []
    for model, group in pred.groupby('model', sort=False):
        use = group.dropna(subset=['y', 'yhat']).copy()
        if len(use) < 20:
            continue
        spearman = float(use[['y', 'yhat']].corr(method='spearman').iloc[0, 1])
        for label, q in [('top_quartile', 0.75), ('top_decile', 0.90)]:
            if label == 'top_decile' and len(use) < 80:
                continue
            actual_cut = float(use['y'].quantile(q))
            pred_cut = float(use['yhat'].quantile(q))
            actual_top = use['y'] >= actual_cut
            pred_top = use['yhat'] >= pred_cut
            tp = int((actual_top & pred_top).sum())
            pred_n = int(pred_top.sum())
            actual_n = int(actual_top.sum())
            precision = tp / pred_n if pred_n else np.nan
            recall = tp / actual_n if actual_n else np.nan
            f1 = 2 * precision * recall / (precision + recall) if precision + recall > 0 else np.nan
            rows.append({
                'model': model,
                'bucket': label,
                'n': int(len(use)),
                'spearman_rank_corr': spearman,
                'actual_threshold': actual_cut,
                'predicted_threshold': pred_cut,
                'actual_positive_n': actual_n,
                'predicted_positive_n': pred_n,
                'true_positive_n': tp,
                'precision': precision,
                'recall': recall,
                'f1': f1,
            })
    return pd.DataFrame(rows)


def build_panel_lag_dataset() -> pd.DataFrame:
    path = SOURCE_ASSETS / 'validator_epoch_mev_bam_panel_50epoch.csv'
    if not path.exists():
        return pd.DataFrame()
    panel = pd.read_csv(path)
    panel = panel.sort_values(['identity_account', 'epoch']).copy()
    target = 'log_mev_rewards_SOL'
    base_features = [
        target,
        'log_active_stake_SOL',
        'blocks_produced',
        'mev_per_produced_block_SOL',
        'build_time_score',
        'vote_packing_score',
        'non_vote_packing_score',
        'ibrl_score',
        'median_block_build_ms',
        'running_bam_num',
        'running_jito_num',
        'jito_directed_target_num',
        'network_mev_SOL',
        'epoch_total_mev_SOL',
    ]
    for col in base_features:
        if col in panel.columns:
            panel[col] = pd.to_numeric(panel[col], errors='coerce')
    g = panel.groupby('identity_account', sort=False)
    out = panel[['identity_account', 'vote_account', 'epoch', target]].copy()
    out = out.rename(columns={target: 'target_log_mev_rewards_SOL'})
    lag_cols = [c for c in base_features if c in panel.columns]
    for col in lag_cols:
        out[f'lag1_{col}'] = g[col].shift(1)
    out['lag2_log_mev_rewards_SOL'] = g[target].shift(2)
    out['lag3_log_mev_rewards_SOL'] = g[target].shift(3)
    out['rolling3_mean_log_mev_rewards_SOL'] = g[target].transform(lambda s: s.shift(1).rolling(3, min_periods=2).mean())
    out['rolling5_mean_log_mev_rewards_SOL'] = g[target].transform(lambda s: s.shift(1).rolling(5, min_periods=3).mean())
    out['rolling3_std_log_mev_rewards_SOL'] = g[target].transform(lambda s: s.shift(1).rolling(3, min_periods=2).std())
    out['epoch_trend'] = pd.to_numeric(panel['epoch'], errors='coerce') - pd.to_numeric(panel['epoch'], errors='coerce').min()
    return out.replace([np.inf, -np.inf], np.nan)


def summarize_panel_forecast(preds: pd.DataFrame, model: str, target: str, train_n: int, test_epochs: str, alpha: float) -> dict[str, Any]:
    if preds.empty:
        return {
            'model': model,
            'dependent_variable': target,
            'train_n': train_n,
            'test_n': 0,
            'test_epochs': test_epochs,
            'ridge_alpha': alpha,
            'baseline_rmse_train_mean': np.nan,
            'oos_rmse': np.nan,
            'oos_mae': np.nan,
            'oos_median_abs_error': np.nan,
            'oos_p90_abs_error': np.nan,
            'oos_r2_vs_train_mean': np.nan,
        }
    pred = add_prediction_error_columns(preds)
    y = pred['y'].to_numpy(dtype=float)
    yhat = pred['yhat'].to_numpy(dtype=float)
    train_mean = pred['train_mean'].to_numpy(dtype=float)
    residual = y - yhat
    baseline = y - train_mean
    sse = float(np.sum(residual ** 2))
    baseline_sse = float(np.sum(baseline ** 2))
    return {
        'model': model,
        'dependent_variable': target,
        'train_n': train_n,
        'test_n': int(len(pred)),
        'test_epochs': test_epochs,
        'ridge_alpha': alpha,
        'baseline_rmse_train_mean': float(np.sqrt(np.mean(baseline ** 2))),
        'oos_mse': float(np.mean(residual ** 2)),
        'oos_rmse': float(np.sqrt(np.mean(residual ** 2))),
        'oos_mae': float(np.mean(np.abs(residual))),
        'oos_median_abs_error': float(np.median(np.abs(residual))),
        'oos_p90_abs_error': float(np.quantile(np.abs(residual), 0.90)),
        'oos_median_abs_pct_error_from_log': float(np.median(np.expm1(np.abs(residual)))),
        'oos_p90_abs_pct_error_from_log': float(np.quantile(np.expm1(np.abs(residual)), 0.90)),
        'oos_r2_vs_train_mean': float(1 - sse / baseline_sse) if baseline_sse > 0 else np.nan,
    }


def run_panel_lag_forecast() -> tuple[pd.DataFrame, pd.DataFrame]:
    panel = build_panel_lag_dataset()
    if panel.empty:
        return pd.DataFrame(), pd.DataFrame()
    target = 'target_log_mev_rewards_SOL'
    feature_cols = [
        c for c in panel.columns
        if c not in {'identity_account', 'vote_account', 'epoch', target}
    ]
    panel = panel.loc[pd.to_numeric(panel[target], errors='coerce').notna()].copy()
    max_epoch = int(panel['epoch'].max())
    test_start = max_epoch - 9
    train = panel.loc[panel['epoch'] < test_start].copy()
    test = panel.loc[panel['epoch'] >= test_start].copy()
    fit = fit_ridge_pipeline(train, target, feature_cols)
    if fit is None:
        return pd.DataFrame(), pd.DataFrame()
    model_obj, use, train_r2, train_n, alpha = fit
    preds = predict_ridge(test, target, model_obj, use)
    if preds.empty:
        return pd.DataFrame(), pd.DataFrame()
    preds['model'] = 'panel_lag_ridge_next_epoch_mev'
    preds['fold'] = 1
    preds['train_mean'] = float(pd.to_numeric(train[target], errors='coerce').dropna().mean())
    preds = add_prediction_error_columns(preds)
    perf = pd.DataFrame([summarize_panel_forecast(
        preds,
        'panel_lag_ridge_next_epoch_mev',
        target,
        train_n,
        f'{test_start}-{max_epoch}',
        alpha,
    )])
    perf['train_r_squared'] = train_r2
    perf['selected_iv_count'] = len(use)
    perf['selected_features'] = ','.join(use)
    return perf, preds

def run() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    perf, folds, selections, predictions = run_prediction_suite()
    predictions = add_prediction_error_columns(predictions)
    calibration = build_calibration_table(predictions)
    rank_metrics = build_rank_bucket_metrics(predictions)
    panel_perf, panel_predictions = run_panel_lag_forecast()
    perf.to_csv(OUT / 'v27_prediction_model_performance.csv', index=False)
    folds.to_csv(OUT / 'v27_prediction_fold_results.csv', index=False)
    selections.to_csv(OUT / 'v27_prediction_selected_features.csv', index=False)
    calibration.to_csv(OUT / 'v27_prediction_calibration.csv', index=False)
    rank_metrics.to_csv(OUT / 'v27_prediction_rank_bucket_metrics.csv', index=False)
    panel_perf.to_csv(OUT / 'v27_prediction_panel_lag_performance.csv', index=False)
    panel_predictions.to_csv(OUT / 'v27_prediction_panel_lag_predictions.csv', index=False)
    if not predictions.empty:
        predictions.to_csv(OUT / 'v27_prediction_row_predictions.csv', index=False)
    update_report(perf, folds, selections, calibration, rank_metrics, panel_perf)
    update_workbook(perf, folds, selections, calibration, predictions, rank_metrics, panel_perf, panel_predictions)
    best = perf.iloc[0].to_dict() if not perf.empty else {}
    full_sample_perf = perf.loc[pd.to_numeric(perf.get('test_n_total'), errors='coerce').ge(400)] if not perf.empty else pd.DataFrame()
    best_full = full_sample_perf.iloc[0].to_dict() if not full_sample_perf.empty else {}
    panel_best = panel_perf.iloc[0].to_dict() if not panel_perf.empty else {}
    summary = {
        'finished_at': datetime.now(timezone.utc).isoformat(),
        'models': int(len(perf)),
        'best_rmse_model': best.get('model'),
        'best_rmse': best.get('oos_rmse'),
        'best_rmse_test_n': best.get('test_n_total'),
        'best_full_sample_rmse_model': best_full.get('model'),
        'best_full_sample_rmse': best_full.get('oos_rmse'),
        'best_full_sample_oos_r2_vs_train_mean': best_full.get('oos_r2_vs_train_mean'),
        'panel_lag_rmse': panel_best.get('oos_rmse'),
        'panel_lag_oos_r2_vs_train_mean': panel_best.get('oos_r2_vs_train_mean'),
        'outputs': [
            'output/v27_prediction_model_performance.csv',
            'output/v27_prediction_fold_results.csv',
            'output/v27_prediction_selected_features.csv',
            'output/v27_prediction_calibration.csv',
            'output/v27_prediction_row_predictions.csv',
            'output/v27_prediction_rank_bucket_metrics.csv',
            'output/v27_prediction_panel_lag_performance.csv',
            'output/v27_prediction_panel_lag_predictions.csv',
        ],
    }
    (OUT / 'v27_prediction_summary.json').write_text(json.dumps(summary, indent=2, sort_keys=True, default=str), encoding='utf-8')
    print(json.dumps(summary, indent=2, sort_keys=True, default=str))
    return summary


if __name__ == '__main__':
    run()
