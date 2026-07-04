from __future__ import annotations

from .data_assembly import *


def run_simple_regressions(
    main: pd.DataFrame, panel: pd.DataFrame, feature_list: list[str], benchmark_stats: dict[str, Any]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    stats_rows = [benchmark_stats]
    coefficient_frames = []
    models = [
        ("simple_candidate_only", [CANDIDATE]),
        ("simple_core_opportunity_controls", CORE_CONTROLS),
    ]
    for score in MECHANISM_SCORES:
        models.append((f"simple_core_plus_{score}", CORE_CONTROLS + [score]))
    models.append(("simple_core_plus_all_four_supplemental_scores", CORE_CONTROLS + MECHANISM_SCORES))

    matched = panel.loc[panel["has_any_v22_v25_proxy"].eq(1)].copy()
    merged_main = main.merge(
        panel[["identity_account"] + MECHANISM_SCORES + ["has_any_v22_v25_proxy"]],
        on="identity_account",
        how="left",
    )
    models.append(("h7_only_on_v22_v25_matched_sample", feature_list))
    models.append(("h7_plus_all_four_scores_on_matched_sample", feature_list + MECHANISM_SCORES))

    frames_for_model = {
        "simple_candidate_only": panel,
        "simple_core_opportunity_controls": panel,
        "simple_core_plus_all_four_supplemental_scores": panel,
        "h7_only_on_v22_v25_matched_sample": merged_main.loc[
            merged_main["has_any_v22_v25_proxy"].eq(1)
        ],
        "h7_plus_all_four_scores_on_matched_sample": merged_main.loc[
            merged_main["has_any_v22_v25_proxy"].eq(1)
        ],
    }
    for score in MECHANISM_SCORES:
        frames_for_model[f"simple_core_plus_{score}"] = panel

    for model, x_cols in models:
        try:
            stats, coefs, _, _ = fit_ols(frames_for_model[model], TARGET, x_cols, model)
            if model.startswith("h7_"):
                stats["sample_note"] = "v26 H7 variables, restricted to rows with v22-v25 proxy coverage"
            else:
                stats["sample_note"] = "available rows after dropping missing DV/IV"
            stats_rows.append(stats)
            coefficient_frames.append(coefs)
        except Exception as exc:  # keep the runbook honest about sparse proxy failures
            stats_rows.append(
                {
                    "model": model,
                    "dependent_variable": TARGET,
                    "n": 0,
                    "independent_variable_count": len(x_cols),
                    "r_squared": np.nan,
                    "adj_r_squared": np.nan,
                    "candidate_coef": np.nan,
                    "candidate_p_value": np.nan,
                    "aic": np.nan,
                    "bic": np.nan,
                    "dropped_constant_terms": "",
                    "sample_note": f"NOT_RUN: {exc}",
                }
            )
    stats_df = pd.DataFrame(stats_rows)
    coefs_df = pd.concat(coefficient_frames, ignore_index=True) if coefficient_frames else pd.DataFrame()
    stats_df.to_csv(OUT / "v27_simple_regression_stats.csv", index=False)
    coefs_df.to_csv(OUT / "v27_simple_regression_coefficients.csv", index=False)
    return stats_df, coefs_df


def single_proxy_screen(panel: pd.DataFrame) -> pd.DataFrame:
    exclude = {
        "identity_account",
        "vote_account",
        TARGET,
        CANDIDATE,
        "has_any_v22_v25_proxy",
        "has_all_four_mechanism_scores",
    }
    exclude.update(MECHANISM_SCORES)
    numeric_candidates = []
    for col in panel.columns:
        if col in exclude or col.startswith("component_"):
            continue
        if not any(col.startswith(prefix) for prefix in ["v22_", "v23_", "v24_", "v25_"]):
            continue
        x = pd.to_numeric(panel[col], errors="coerce")
        if x.notna().sum() >= 50 and x.nunique(dropna=True) > 5:
            numeric_candidates.append(col)
    baseline_stats, _, baseline_sample, _ = fit_ols(
        panel, TARGET, CORE_CONTROLS, "single_proxy_baseline_core"
    )
    rows = []
    for col in numeric_candidates:
        tmp = panel[[TARGET] + CORE_CONTROLS + [col]].copy()
        z_col = f"z_screen__{col}"
        tmp[z_col] = zscore(pd.to_numeric(tmp[col], errors="coerce"))
        try:
            stats, coefs, _, _ = fit_ols(
                tmp, TARGET, CORE_CONTROLS + [z_col], f"single_proxy_{col}"
            )
            term = coefs.loc[coefs["term"].eq(z_col)].iloc[0]
            rows.append(
                {
                    "proxy": col,
                    "n": stats["n"],
                    "r_squared": stats["r_squared"],
                    "incremental_r2_vs_core_available": stats["r_squared"]
                    - baseline_stats["r_squared"],
                    "candidate_coef": stats["candidate_coef"],
                    "candidate_p_value": stats["candidate_p_value"],
                    "proxy_coef": term["coef"],
                    "proxy_p_value": term["p_value"],
                }
            )
        except Exception:
            continue
    out = pd.DataFrame(rows).sort_values(
        ["r_squared", "incremental_r2_vs_core_available"], ascending=False
    )
    out.to_csv(OUT / "v27_single_proxy_screen.csv", index=False)
    return out

