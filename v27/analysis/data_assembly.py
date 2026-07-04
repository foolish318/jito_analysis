from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import nbformat as nbf
import numpy as np
import pandas as pd
import statsmodels.api as sm


PKG = Path(__file__).resolve().parents[1]
ROOT = PKG.parent
DATA = PKG / "data"
SOURCE_ASSETS = DATA / "source_assets"
PROCESSED = DATA / "processed"
API_RAW = DATA / "api_raw"
OUT = PKG / "output"
NOTEBOOKS = PKG / "notebooks"

for directory in [PKG, DATA, SOURCE_ASSETS, PROCESSED, API_RAW, OUT, NOTEBOOKS]:
    directory.mkdir(parents=True, exist_ok=True)

TARGET = "log_mev_per_leader_slot"
CANDIDATE = "candidate_indicator"
CORE_CONTROLS = [
    CANDIDATE,
    "v18_base_z__log_active_stake",
    "v18_base_z__log_scheduled_slots",
]

SOURCES = {
    "main_benchmark_source_panel": SOURCE_ASSETS / "main_benchmark_model_panel.csv",
    "h7_b10_feature_list": SOURCE_ASSETS / "h7_b10_feature_list.csv",
    "h7_b10_benchmark_run_summary": SOURCE_ASSETS / "h7_b10_benchmark_run_summary.json",
    "h7_b10_model_specification": SOURCE_ASSETS / "h7_b10_model_specification.csv",
    "public_bundle_validator_orderflow_scores": SOURCE_ASSETS / "jito_public_validator_orderflow_scores.csv",
    "jito_public_bundles": SOURCE_ASSETS / "jito_public_bundles.csv",
    "jito_public_tipper_validator_edges": SOURCE_ASSETS / "jito_public_tipper_validator_edges.csv",
    "jito_public_bundle_events": SOURCE_ASSETS / "jito_public_bundle_events.csv",
    "structural_validator_mechanism_score_panel": SOURCE_ASSETS / "structural_validator_mechanism_score_panel.csv",
    "structural_model_fit_stats": SOURCE_ASSETS / "structural_model_fit_stats.csv",
    "structural_mechanism_attribution": SOURCE_ASSETS / "structural_mechanism_attribution.csv",
    "structural_sequential_model_ladder": SOURCE_ASSETS / "structural_sequential_model_ladder.csv",
    "observable_proxy_validator_score_panel": SOURCE_ASSETS / "observable_proxy_validator_score_panel.csv",
    "structural_counterfactual_estimates": SOURCE_ASSETS / "structural_counterfactual_estimates.csv",
    "observable_proxy_regression_stats": SOURCE_ASSETS / "observable_proxy_regression_model_stats.csv",
    "mechanism_identification_attribution": SOURCE_ASSETS / "mechanism_identification_attribution.csv",
    "validator_epoch_mev_bam_summary_50epoch": SOURCE_ASSETS / "validator_epoch_mev_bam_summary_50epoch.csv",
    "validator_epoch_mev_bam_panel_50epoch": SOURCE_ASSETS / "validator_epoch_mev_bam_panel_50epoch.csv",
    "validator_epoch_mev_bam_regression_stats": SOURCE_ASSETS / "validator_epoch_mev_bam_regression_stats.csv",
    "validator_epoch_mev_bam_mechanism_attribution": SOURCE_ASSETS / "validator_epoch_mev_bam_mechanism_attribution.csv",
}

SOURCE_LINEAGE = {
    "jito_public_bundles": "v22",
    "jito_public_tipper_validator_edges": "v22",
    "jito_public_bundle_events": "v22",
    "public_bundle_validator_orderflow_scores": "v22",
    "structural_validator_mechanism_score_panel": "v23",
    "structural_model_fit_stats": "v23",
    "structural_mechanism_attribution": "v23",
    "structural_sequential_model_ladder": "v23",
    "observable_proxy_validator_score_panel": "v24",
    "structural_counterfactual_estimates": "v24",
    "observable_proxy_regression_stats": "v24",
    "mechanism_identification_attribution": "v24",
    "validator_epoch_mev_bam_summary_50epoch": "v25",
    "validator_epoch_mev_bam_panel_50epoch": "v25",
    "validator_epoch_mev_bam_regression_stats": "v25",
    "validator_epoch_mev_bam_mechanism_attribution": "v25",
}


def md_table(df: pd.DataFrame, max_rows: int | None = None, digits: int = 6) -> str:
    if df is None or df.empty:
        return "_No rows._"
    use = df.head(max_rows).copy() if max_rows else df.copy()
    headers = [str(c) for c in use.columns]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for _, row in use.iterrows():
        values: list[str] = []
        for col in use.columns:
            value = row[col]
            if isinstance(value, (float, np.floating)):
                if math.isnan(float(value)):
                    values.append("")
                else:
                    values.append(f"{float(value):.{digits}g}")
            elif isinstance(value, (int, np.integer)):
                values.append(str(int(value)))
            else:
                values.append(str(value).replace("\n", " "))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def read_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, **kwargs)


def source_manifest() -> pd.DataFrame:
    rows = []
    for key, path in SOURCES.items():
        rows.append(
            {
                "source_key": key,
                "source_path": str(path),
                "exists": path.exists(),
                "size_bytes": path.stat().st_size if path.exists() else np.nan,
            }
        )
    manifest = pd.DataFrame(rows)
    manifest.to_csv(OUT / "v27_source_manifest.csv", index=False)
    missing = manifest.loc[~manifest["exists"], "source_key"].tolist()
    if missing:
        raise FileNotFoundError("Missing required v27 sources: " + ", ".join(missing))
    return manifest


def as_numeric(frame: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    return (
        frame[cols]
        .replace([np.inf, -np.inf], np.nan)
        .apply(pd.to_numeric, errors="coerce")
    )


def zscore(series: pd.Series) -> pd.Series:
    x = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan)
    sd = x.std(ddof=0)
    if pd.isna(sd) or sd == 0:
        return pd.Series(np.nan, index=series.index)
    return (x - x.mean()) / sd


def log1p_clean(series: pd.Series) -> pd.Series:
    x = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan)
    return np.log1p(x.clip(lower=0))


def fit_ols(
    frame: pd.DataFrame,
    y_col: str,
    x_cols: list[str],
    model: str,
    min_rows: int | None = None,
) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame, Any]:
    cols = [y_col] + x_cols
    tmp = as_numeric(frame, cols).dropna().copy()
    usable_x = []
    dropped_constant = []
    for col in x_cols:
        nunique = tmp[col].nunique(dropna=True)
        if nunique > 1:
            usable_x.append(col)
        else:
            dropped_constant.append(col)
    if len(usable_x) != len(x_cols):
        x_cols = usable_x
        tmp = tmp[[y_col] + x_cols]
    row_floor = min_rows if min_rows is not None else max(40, len(x_cols) + 8)
    if len(tmp) < row_floor:
        raise ValueError(f"Insufficient rows for {model}: rows={len(tmp)}, x={len(x_cols)}")
    X = sm.add_constant(tmp[x_cols], has_constant="add")
    y = tmp[y_col]
    fit = sm.OLS(y, X).fit(cov_type="HC3")
    coefficients = pd.DataFrame(
        {
            "model": model,
            "term": fit.params.index,
            "coef": fit.params.values,
            "std_error_hc3": fit.bse.values,
            "t_stat": fit.tvalues.values,
            "p_value": fit.pvalues.values,
        }
    )
    stats = {
        "model": model,
        "dependent_variable": y_col,
        "n": int(fit.nobs),
        "independent_variable_count": len(x_cols),
        "r_squared": float(fit.rsquared),
        "adj_r_squared": float(fit.rsquared_adj),
        "candidate_coef": float(fit.params.get(CANDIDATE, np.nan)),
        "candidate_p_value": float(fit.pvalues.get(CANDIDATE, np.nan)),
        "aic": float(fit.aic),
        "bic": float(fit.bic),
        "dropped_constant_terms": ",".join(dropped_constant),
    }
    return stats, coefficients, tmp, fit


def prefix_columns(df: pd.DataFrame, key_col: str, prefix: str, selected: list[str]) -> pd.DataFrame:
    present = [col for col in selected if col in df.columns and col != key_col]
    out = df[[key_col] + present].drop_duplicates(key_col).copy()
    out = out.rename(columns={col: f"{prefix}_{col}" for col in present})
    return out


def selected_by_keywords(df: pd.DataFrame, keywords: list[str], always: list[str]) -> list[str]:
    cols = []
    for col in df.columns:
        low = col.lower()
        if col in always or any(k in low for k in keywords):
            cols.append(col)
    return list(dict.fromkeys(cols))


def build_main_panel() -> tuple[pd.DataFrame, list[str], dict[str, Any], pd.DataFrame]:
    source_panel = read_csv(SOURCES["main_benchmark_source_panel"])
    feature_list = read_csv(SOURCES["h7_b10_feature_list"])["feature"].astype(str).tolist()
    required = [TARGET] + feature_list
    missing = [col for col in required if col not in source_panel.columns]
    if missing:
        raise ValueError("Missing v26 benchmark columns: " + ", ".join(missing[:20]))
    if "identity_account" not in source_panel.columns or "vote_account" not in source_panel.columns:
        raise ValueError("v26 source panel must contain identity_account and vote_account.")

    benchmark_stats, benchmark_coefs, common_numeric, _ = fit_ols(
        source_panel,
        TARGET,
        feature_list,
        "v27_main_H7_benchmark_v26_exact",
    )
    with open(SOURCES["h7_b10_benchmark_run_summary"], "r", encoding="utf-8") as handle:
        v26_summary = json.load(handle)
    expected_r2 = float(v26_summary["rerun_r_squared"])
    benchmark_stats["v26_expected_r_squared"] = expected_r2
    benchmark_stats["r2_error_vs_v26"] = benchmark_stats["r_squared"] - expected_r2
    benchmark_stats["status_vs_v26"] = (
        "PASS" if abs(benchmark_stats["r2_error_vs_v26"]) <= 1e-12 else "FAIL"
    )
    if benchmark_stats["status_vs_v26"] != "PASS":
        raise AssertionError("v27 failed to reproduce v26 H7 benchmark.")

    numeric_required = as_numeric(source_panel, required)
    common_mask = numeric_required.notna().all(axis=1)
    keep_cols = ["identity_account", "vote_account", TARGET] + feature_list
    main = source_panel.loc[common_mask, keep_cols].copy()
    for col in [TARGET] + feature_list:
        main[col] = pd.to_numeric(main[col], errors="coerce")
    main.to_csv(DATA / "main_benchmark_panel_with_ids.csv", index=False)
    benchmark_coefs.to_csv(OUT / "v27_main_benchmark_coefficients.csv", index=False)
    return main, feature_list, benchmark_stats, benchmark_coefs


def build_supplemental_proxy_panel(main: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    coverage_rows = []

    v22 = read_csv(SOURCES["public_bundle_validator_orderflow_scores"]).rename(
        columns={"validator": "identity_account"}
    )
    v22_selected = [
        "bundles",
        "total_tip_SOL",
        "avg_tip_SOL",
        "median_tip_SOL",
        "unique_tippers",
        "unique_slots",
        "avg_landed_cu",
        "avg_tip_per_cu",
        "median_tip_per_cu",
        "avg_received_to_forwarded_ms",
        "median_received_to_forwarded_ms",
        "avg_received_to_insert_ms",
        "avg_region_count",
        "total_prune_events",
        "total_rpc_simulation_failed_events",
        "tip_share",
        "bundle_share",
        "tip_per_bundle_ratio_vs_sample",
        "tip_per_cu_ratio_vs_sample",
        "tipper_tip_hhi",
        "top_tipper_tip_share",
        "relationship_score",
        "positive_relationship_tip_share",
        "v22_candidate_like",
    ]
    v22_pref = prefix_columns(v22, "identity_account", "v22", v22_selected)

    v23 = read_csv(SOURCES["structural_validator_mechanism_score_panel"]).rename(
        columns={"validator": "identity_account"}
    )
    v23_always = [
        "score_order_flow",
        "score_bundle_execution",
        "score_latency_infra",
        "score_entity_integration",
        "v23_tip_SOL_per_scheduled_slot",
        "helius_addr_matched_tippers",
        "helius_addr_matched_tip_SOL",
    ]
    v23_selected = selected_by_keywords(
        v23,
        keywords=["dune", "helius", "score_order", "score_bundle", "score_latency", "score_entity"],
        always=v23_always,
    )
    v23_pref = prefix_columns(v23, "identity_account", "v23", v23_selected)

    v24 = read_csv(SOURCES["observable_proxy_validator_score_panel"]).rename(
        columns={"validator": "identity_account"}
    )
    v24_always = [
        "score_private_orderflow_searcherflow",
        "score_bundle_outcome_execution",
        "score_latency_infra_reliability",
        "score_entity_vertical_integration",
        "address_history_matched_tippers",
        "address_history_matched_tip_sol",
        "target_log_total_tip_sol",
    ]
    v24_selected = selected_by_keywords(
        v24,
        keywords=["dune", "address_history", "score_private", "score_bundle", "score_latency", "score_entity"],
        always=v24_always,
    )
    v24_pref = prefix_columns(v24, "identity_account", "v24", v24_selected)

    v25 = read_csv(SOURCES["validator_epoch_mev_bam_summary_50epoch"])
    v25_selected = [
        "vote_account",
        "epochs_seen",
        "first_epoch",
        "last_epoch",
        "total_mev_SOL",
        "avg_mev_SOL",
        "avg_active_stake_SOL",
        "avg_mev_yield",
        "avg_excess_mev_share",
        "median_excess_mev_share",
        "positive_excess_epoch_share",
        "running_bam_epoch_share",
        "running_jito_epoch_share",
        "jito_directed_epoch_share",
        "avg_bam_connection_rate",
        "avg_mev_commission_bps",
        "total_blocks_produced",
        "avg_blocks_produced",
        "avg_ibrl_score",
        "avg_build_time_score",
        "avg_vote_packing_score",
        "avg_non_vote_packing_score",
        "avg_median_block_build_ms",
        "mev_per_block_SOL",
        "log_total_mev_SOL",
        "log_avg_active_stake_SOL",
        "log_epochs_seen",
        "log_total_blocks_produced",
        "log_mev_per_block_SOL",
        "candidate_like_50epoch",
        "coverage_min_epochs",
    ]
    v25_pref = prefix_columns(v25, "identity_account", "v25", v25_selected)

    sources = [
        ("public_bundle_validator_orderflow_scores", v22, v22_pref),
        ("structural_validator_mechanism_score_panel", v23, v23_pref),
        ("observable_proxy_validator_score_panel", v24, v24_pref),
        ("validator_epoch_mev_bam_summary_50epoch", v25, v25_pref),
    ]
    main_ids = set(main["identity_account"].dropna().astype(str))
    candidate_ids = set(
        main.loc[main[CANDIDATE].eq(1), "identity_account"].dropna().astype(str)
    )
    for label, raw, pref in sources:
        raw_ids = set(raw["identity_account"].dropna().astype(str))
        matched_ids = main_ids & raw_ids
        matched_candidates = candidate_ids & raw_ids
        coverage_rows.append(
            {
                "source": label,
                "source_rows": len(raw),
                "source_unique_identities": len(raw_ids),
                "v26_main_rows": len(main),
                "matched_to_v26_rows": int(main["identity_account"].astype(str).isin(raw_ids).sum()),
                "matched_unique_identities": len(matched_ids),
                "matched_rate_vs_v26": len(matched_ids) / len(main_ids) if main_ids else np.nan,
                "v26_candidate_identities": len(candidate_ids),
                "matched_candidate_identities": len(matched_candidates),
                "matched_candidate_rate": len(matched_candidates) / len(candidate_ids)
                if candidate_ids
                else np.nan,
                "selected_columns": len(pref.columns) - 1,
            }
        )

    base_cols = list(dict.fromkeys(["identity_account", "vote_account", TARGET] + CORE_CONTROLS))
    merged = main[base_cols].copy()
    for pref in [v22_pref, v23_pref, v24_pref, v25_pref]:
        merged = merged.merge(pref, on="identity_account", how="left")
    merged.to_csv(DATA / "supplemental_proxy_panel.csv", index=False)
    coverage = pd.DataFrame(coverage_rows)
    coverage.to_csv(OUT / "v27_data_coverage.csv", index=False)
    return merged, coverage


COMPONENTS: dict[str, list[dict[str, str]]] = {
    "private_orderflow_searcherflow": [
        {"column": "v22_unique_tippers", "transform": "log1p", "sign": "positive"},
        {"column": "v22_total_tip_SOL", "transform": "log1p", "sign": "positive"},
        {"column": "v22_bundles", "transform": "log1p", "sign": "positive"},
        {"column": "v22_relationship_score", "transform": "raw", "sign": "positive"},
        {
            "column": "v22_positive_relationship_tip_share",
            "transform": "raw",
            "sign": "positive",
        },
        {"column": "v23_score_order_flow", "transform": "raw", "sign": "positive"},
        {
            "column": "v23_helius_addr_matched_tippers",
            "transform": "log1p",
            "sign": "positive",
        },
        {
            "column": "v23_helius_addr_matched_tip_SOL",
            "transform": "log1p",
            "sign": "positive",
        },
        {
            "column": "v24_score_private_orderflow_searcherflow",
            "transform": "raw",
            "sign": "positive",
        },
        {
            "column": "v24_address_history_matched_tippers",
            "transform": "log1p",
            "sign": "positive",
        },
        {
            "column": "v24_address_history_matched_tip_sol",
            "transform": "log1p",
            "sign": "positive",
        },
    ],
    "bundle_outcome_execution": [
        {"column": "v22_avg_landed_cu", "transform": "log1p", "sign": "positive"},
        {"column": "v22_avg_tip_per_cu", "transform": "log1p", "sign": "positive"},
        {
            "column": "v22_tip_per_cu_ratio_vs_sample",
            "transform": "raw",
            "sign": "positive",
        },
        {"column": "v23_score_bundle_execution", "transform": "raw", "sign": "positive"},
        {
            "column": "v24_score_bundle_outcome_execution",
            "transform": "raw",
            "sign": "positive",
        },
        {"column": "v25_avg_ibrl_score", "transform": "raw", "sign": "positive"},
        {
            "column": "v25_avg_non_vote_packing_score",
            "transform": "raw",
            "sign": "positive",
        },
    ],
    "latency_infra_reliability": [
        {
            "column": "v22_avg_received_to_forwarded_ms",
            "transform": "log1p",
            "sign": "negative",
        },
        {
            "column": "v22_median_received_to_forwarded_ms",
            "transform": "log1p",
            "sign": "negative",
        },
        {
            "column": "v22_avg_received_to_insert_ms",
            "transform": "log1p",
            "sign": "negative",
        },
        {"column": "v23_score_latency_infra", "transform": "raw", "sign": "positive"},
        {
            "column": "v24_score_latency_infra_reliability",
            "transform": "raw",
            "sign": "positive",
        },
        {"column": "v25_avg_build_time_score", "transform": "raw", "sign": "positive"},
        {
            "column": "v25_avg_median_block_build_ms",
            "transform": "log1p",
            "sign": "negative",
        },
        {
            "column": "v25_avg_bam_connection_rate",
            "transform": "raw",
            "sign": "positive",
        },
    ],
    "entity_vertical_integration": [
        {"column": "v23_score_entity_integration", "transform": "raw", "sign": "positive"},
        {
            "column": "v24_score_entity_vertical_integration",
            "transform": "raw",
            "sign": "positive",
        },
        {
            "column": "v25_running_bam_epoch_share",
            "transform": "raw",
            "sign": "positive",
        },
        {
            "column": "v25_running_jito_epoch_share",
            "transform": "raw",
            "sign": "positive",
        },
        {
            "column": "v25_jito_directed_epoch_share",
            "transform": "raw",
            "sign": "positive",
        },
    ],
}

MECHANISM_SCORES = [f"supp_{name}_score" for name in COMPONENTS]


def component_series(df: pd.DataFrame, column: str, transform: str, sign: str) -> pd.Series:
    if transform == "log1p":
        base = log1p_clean(df[column])
    else:
        base = pd.to_numeric(df[column], errors="coerce").replace([np.inf, -np.inf], np.nan)
    z = zscore(base)
    if sign == "negative":
        z = -z
    return z


def add_mechanism_scores(panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    out = panel.copy()
    rows = []
    for mechanism, specs in COMPONENTS.items():
        component_cols = []
        for spec in specs:
            col = spec["column"]
            if col not in out.columns:
                rows.append(
                    {
                        "mechanism": mechanism,
                        "score": f"supp_{mechanism}_score",
                        "component_column": col,
                        "transform": spec["transform"],
                        "sign": spec["sign"],
                        "available_nonmissing": 0,
                        "used": False,
                    }
                )
                continue
            component_col = f"component_{mechanism}__{col}"
            out[component_col] = component_series(
                out, col, spec["transform"], spec["sign"]
            )
            component_cols.append(component_col)
            rows.append(
                {
                    "mechanism": mechanism,
                    "score": f"supp_{mechanism}_score",
                    "component_column": col,
                    "transform": spec["transform"],
                    "sign": spec["sign"],
                    "available_nonmissing": int(out[col].notna().sum()),
                    "used": bool(out[component_col].notna().sum() > 0),
                }
            )
        score_col = f"supp_{mechanism}_score"
        if component_cols:
            out[score_col] = out[component_cols].mean(axis=1, skipna=True)
        else:
            out[score_col] = np.nan
    score_map = pd.DataFrame(rows)
    score_map.to_csv(OUT / "v27_mechanism_score_component_map.csv", index=False)
    out["has_any_v22_v25_proxy"] = out[MECHANISM_SCORES].notna().any(axis=1).astype(int)
    out["has_all_four_mechanism_scores"] = out[MECHANISM_SCORES].notna().all(axis=1).astype(int)
    out.to_csv(DATA / "model_panel.csv", index=False)
    return out, score_map

