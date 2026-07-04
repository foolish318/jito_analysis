from __future__ import annotations

from .data_assembly import *


def mechanism_identification(panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, Any]:
    common = panel.dropna(subset=[TARGET] + CORE_CONTROLS + MECHANISM_SCORES).copy()
    baseline_stats, baseline_coefs, _, _ = fit_ols(
        common,
        TARGET,
        CORE_CONTROLS,
        "mechanism_common_baseline_core",
        min_rows=40,
    )
    full_stats, full_coefs, _, full_fit = fit_ols(
        common,
        TARGET,
        CORE_CONTROLS + MECHANISM_SCORES,
        "structural_core_plus_all_four_scores",
        min_rows=40,
    )
    rows = []
    coef_frames = [baseline_coefs, full_coefs]
    ladder_rows = [
        {
            "step": "core_controls",
            "added": "candidate + active stake + scheduled slots",
            "n": baseline_stats["n"],
            "r_squared": baseline_stats["r_squared"],
            "delta_r2_vs_previous": np.nan,
            "candidate_coef": baseline_stats["candidate_coef"],
            "candidate_p_value": baseline_stats["candidate_p_value"],
        }
    ]
    current_x = CORE_CONTROLS.copy()
    current_r2 = baseline_stats["r_squared"]
    for score in MECHANISM_SCORES:
        add_stats, add_coefs, _, _ = fit_ols(
            common,
            TARGET,
            CORE_CONTROLS + [score],
            f"mechanism_add_{score}_to_core_common",
            min_rows=40,
        )
        drop_scores = [s for s in MECHANISM_SCORES if s != score]
        drop_stats, _, _, _ = fit_ols(
            common,
            TARGET,
            CORE_CONTROLS + drop_scores,
            f"mechanism_drop_{score}_from_full_common",
            min_rows=40,
        )
        coef_frames.append(add_coefs)
        score_term = add_coefs.loc[add_coefs["term"].eq(score)].iloc[0]
        rows.append(
            {
                "mechanism": score.replace("supp_", "").replace("_score", ""),
                "score_variable": score,
                "n_common": add_stats["n"],
                "baseline_r_squared": baseline_stats["r_squared"],
                "r_squared_after_adding_to_core": add_stats["r_squared"],
                "incremental_r2_vs_core": add_stats["r_squared"]
                - baseline_stats["r_squared"],
                "full_four_score_r_squared": full_stats["r_squared"],
                "r2_loss_if_dropped_from_full": full_stats["r_squared"]
                - drop_stats["r_squared"],
                "candidate_coef_core": baseline_stats["candidate_coef"],
                "candidate_coef_after_adding": add_stats["candidate_coef"],
                "candidate_attenuation_vs_core": baseline_stats["candidate_coef"]
                - add_stats["candidate_coef"],
                "score_coef": float(score_term["coef"]),
                "score_p_value": float(score_term["p_value"]),
                "evidence_read": evidence_read(
                    add_stats["r_squared"] - baseline_stats["r_squared"],
                    float(score_term["p_value"]),
                    full_stats["r_squared"] - drop_stats["r_squared"],
                ),
            }
        )
        current_x.append(score)
        ladder_stats, ladder_coefs, _, _ = fit_ols(
            common,
            TARGET,
            current_x,
            f"structural_ladder_add_{score}",
            min_rows=40,
        )
        coef_frames.append(ladder_coefs)
        ladder_rows.append(
            {
                "step": score,
                "added": score,
                "n": ladder_stats["n"],
                "r_squared": ladder_stats["r_squared"],
                "delta_r2_vs_previous": ladder_stats["r_squared"] - current_r2,
                "candidate_coef": ladder_stats["candidate_coef"],
                "candidate_p_value": ladder_stats["candidate_p_value"],
            }
        )
        current_r2 = ladder_stats["r_squared"]
    out = pd.DataFrame(rows).sort_values("incremental_r2_vs_core", ascending=False)
    ladder = pd.DataFrame(ladder_rows)
    coefs = pd.concat(coef_frames, ignore_index=True)
    out.to_csv(OUT / "v27_mechanism_identification.csv", index=False)
    ladder.to_csv(OUT / "v27_structural_sequential_ladder.csv", index=False)
    coefs.to_csv(OUT / "v27_structural_coefficients.csv", index=False)
    pd.DataFrame([baseline_stats, full_stats]).to_csv(
        OUT / "v27_structural_model_stats.csv", index=False
    )
    return out, ladder, full_fit


def evidence_read(incremental_r2: float, p_value: float, drop_loss: float) -> str:
    if pd.isna(incremental_r2) or pd.isna(p_value):
        return "not estimable"
    if incremental_r2 >= 0.02 and p_value < 0.05 and drop_loss >= 0.005:
        return "strong within proxy model"
    if incremental_r2 >= 0.005 and p_value < 0.10:
        return "supported but incomplete"
    if incremental_r2 > 0:
        return "weak/suggestive only"
    return "not supported in this specification"


def counterfactual_analysis(panel: pd.DataFrame, fit: Any) -> pd.DataFrame:
    x_cols = CORE_CONTROLS + MECHANISM_SCORES
    common = panel.dropna(subset=[TARGET] + x_cols).copy()
    X = sm.add_constant(common[x_cols], has_constant="add")
    predicted_log = fit.predict(X)
    common["_predicted_log"] = predicted_log
    common["_predicted_level"] = np.expm1(predicted_log)
    candidate_mask = common[CANDIDATE].eq(1)
    non_candidate = common.loc[~candidate_mask]
    rows = []

    for score in MECHANISM_SCORES:
        cf = common.copy()
        replacement = float(non_candidate[score].median())
        cf.loc[candidate_mask, score] = replacement
        cf_pred_log = fit.predict(sm.add_constant(cf[x_cols], has_constant="add"))
        cf_pred_level = np.expm1(cf_pred_log)
        rows.append(
            {
                "counterfactual": f"candidate_{score}_set_to_non_candidate_median",
                "mechanism": score.replace("supp_", "").replace("_score", ""),
                "candidate_rows": int(candidate_mask.sum()),
                "replacement_value": replacement,
                "actual_predicted_log_sum": float(common.loc[candidate_mask, "_predicted_log"].sum()),
                "counterfactual_predicted_log_sum": float(cf_pred_log[candidate_mask].sum()),
                "predicted_log_change": float(
                    cf_pred_log[candidate_mask].sum()
                    - common.loc[candidate_mask, "_predicted_log"].sum()
                ),
                "actual_predicted_level_sum": float(
                    common.loc[candidate_mask, "_predicted_level"].sum()
                ),
                "counterfactual_predicted_level_sum": float(cf_pred_level[candidate_mask].sum()),
                "predicted_level_change": float(
                    cf_pred_level[candidate_mask].sum()
                    - common.loc[candidate_mask, "_predicted_level"].sum()
                ),
            }
        )

    cf = common.copy()
    cf.loc[candidate_mask, CANDIDATE] = 0
    cf_pred_log = fit.predict(sm.add_constant(cf[x_cols], has_constant="add"))
    cf_pred_level = np.expm1(cf_pred_log)
    rows.append(
        {
            "counterfactual": "candidate_indicator_set_to_zero",
            "mechanism": "residual_candidate_edge_after_observed_scores",
            "candidate_rows": int(candidate_mask.sum()),
            "replacement_value": 0.0,
            "actual_predicted_log_sum": float(common.loc[candidate_mask, "_predicted_log"].sum()),
            "counterfactual_predicted_log_sum": float(cf_pred_log[candidate_mask].sum()),
            "predicted_log_change": float(
                cf_pred_log[candidate_mask].sum()
                - common.loc[candidate_mask, "_predicted_log"].sum()
            ),
            "actual_predicted_level_sum": float(
                common.loc[candidate_mask, "_predicted_level"].sum()
            ),
            "counterfactual_predicted_level_sum": float(cf_pred_level[candidate_mask].sum()),
            "predicted_level_change": float(
                cf_pred_level[candidate_mask].sum()
                - common.loc[candidate_mask, "_predicted_level"].sum()
            ),
        }
    )
    out = pd.DataFrame(rows)
    out.to_csv(OUT / "v27_counterfactuals.csv", index=False)
    return out


def existing_structural_audit() -> pd.DataFrame:
    rows = []
    audit_sources = [
        ("structural_model_fit_stats", SOURCES["structural_model_fit_stats"]),
        ("structural_mechanism_attribution", SOURCES["structural_mechanism_attribution"]),
        ("structural_sequential_model_ladder", SOURCES["structural_sequential_model_ladder"]),
        ("structural_counterfactual_estimates", SOURCES["structural_counterfactual_estimates"]),
        ("observable_proxy_regression_stats", SOURCES["observable_proxy_regression_stats"]),
        ("mechanism_identification_attribution", SOURCES["mechanism_identification_attribution"]),
        ("validator_epoch_mev_bam_regression_stats", SOURCES["validator_epoch_mev_bam_regression_stats"]),
        ("validator_epoch_mev_bam_mechanism_attribution", SOURCES["validator_epoch_mev_bam_mechanism_attribution"]),
    ]
    for label, path in audit_sources:
        try:
            df = read_csv(path)
            rows.append(
                {
                    "source": label,
                    "path": str(path),
                    "rows": len(df),
                    "columns": len(df.columns),
                    "first_columns": ", ".join(df.columns[:8]),
                    "note": "Imported for v27 audit; v27 re-estimates new proxy scores under the v26 DV/IV discipline.",
                }
            )
        except Exception as exc:
            rows.append(
                {
                    "source": label,
                    "path": str(path),
                    "rows": np.nan,
                    "columns": np.nan,
                    "first_columns": "",
                    "note": f"NOT_READ: {exc}",
                }
            )
    out = pd.DataFrame(rows)
    out.to_csv(OUT / "v27_existing_structural_audit.csv", index=False)
    return out

