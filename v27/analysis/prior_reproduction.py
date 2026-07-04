from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

PKG = Path(__file__).resolve().parents[1]
SOURCE = PKG / "data" / "source_assets"
OUT = PKG / "output"
OUT.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class SourceTable:
    version: str
    source_key: str
    filename: str
    unit: str
    role: str
    identity_key: str | None = None

    @property
    def path(self) -> Path:
        return SOURCE / self.filename


SOURCE_TABLES = [
    SourceTable("v22", "jito_public_bundles", "jito_public_bundles.csv", "bundle", "public landed-bundle observations", "validator"),
    SourceTable("v22", "jito_public_bundle_events", "jito_public_bundle_events.csv", "event", "bundle lifecycle events", None),
    SourceTable("v22", "jito_public_tipper_validator_edges", "jito_public_tipper_validator_edges.csv", "edge", "tipper-validator relationship network", "validator"),
    SourceTable("v22", "public_bundle_validator_orderflow_scores", "jito_public_validator_orderflow_scores.csv", "validator", "validator-level v22 structural scores", "validator"),
    SourceTable("v23", "structural_validator_mechanism_score_panel", "structural_validator_mechanism_score_panel.csv", "validator", "external API enriched structural panel", "validator"),
    SourceTable("v23", "structural_model_fit_stats", "structural_model_fit_stats.csv", "model_result", "v23 structural model statistics", None),
    SourceTable("v23", "structural_mechanism_attribution", "structural_mechanism_attribution.csv", "mechanism_result", "v23 mechanism attribution", None),
    SourceTable("v23", "structural_sequential_model_ladder", "structural_sequential_model_ladder.csv", "structural_ladder", "v23 sequential structural ladder", None),
    SourceTable("v24", "observable_proxy_validator_score_panel", "observable_proxy_validator_score_panel.csv", "validator", "v24 integrated scored validator panel", "validator"),
    SourceTable("v24", "observable_proxy_regression_stats", "observable_proxy_regression_model_stats.csv", "model_result", "v24 regression model statistics", None),
    SourceTable("v24", "mechanism_identification_attribution", "mechanism_identification_attribution.csv", "mechanism_result", "v24 mechanism attribution", None),
    SourceTable("v24", "structural_counterfactual_estimates", "structural_counterfactual_estimates.csv", "counterfactual_result", "v24 structural counterfactuals", None),
    SourceTable("v25", "validator_epoch_mev_bam_summary_50epoch", "validator_epoch_mev_bam_summary_50epoch.csv", "validator", "v25 50-epoch validator summary", "identity_account"),
    SourceTable("v25", "validator_epoch_mev_bam_panel_50epoch", "validator_epoch_mev_bam_panel_50epoch.csv", "validator_epoch", "v25 50-epoch validator-epoch panel", "identity_account"),
    SourceTable("v25", "validator_epoch_mev_bam_regression_stats", "validator_epoch_mev_bam_regression_stats.csv", "model_result", "v25 50-epoch regression model statistics", None),
    SourceTable("v25", "validator_epoch_mev_bam_mechanism_attribution", "validator_epoch_mev_bam_mechanism_attribution.csv", "mechanism_result", "v25 available mechanism attribution", None),
]


def read_csv(filename: str) -> pd.DataFrame:
    path = SOURCE / filename
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path)


def num(value: Any) -> float:
    try:
        if pd.isna(value):
            return np.nan
        return float(value)
    except Exception:
        return np.nan


def safe_nunique(df: pd.DataFrame, col: str) -> int:
    return int(df[col].nunique()) if col in df.columns else 0


def median_ratio(df: pd.DataFrame, flag: str, value: str) -> float:
    if flag not in df.columns or value not in df.columns:
        return np.nan
    x = pd.to_numeric(df[value], errors="coerce")
    f = df[flag].astype(bool)
    cand = x[f].dropna()
    other = x[~f].dropna()
    if cand.empty or other.empty:
        return np.nan
    denom = other.median()
    if denom == 0 or pd.isna(denom):
        return np.nan
    return float(cand.median() / denom)


def md_table(df: pd.DataFrame, max_rows: int = 40, digits: int = 6) -> str:
    if df.empty:
        return "_No rows._"
    view = df.head(max_rows).copy()
    headers = [str(c) for c in view.columns]
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for _, row in view.iterrows():
        vals = []
        for col in view.columns:
            val = row[col]
            if isinstance(val, (float, np.floating)):
                vals.append("" if pd.isna(val) else f"{float(val):.{digits}g}")
            else:
                vals.append(str(val).replace("\n", " ").replace("|", "\\|"))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def data_summary() -> pd.DataFrame:
    rows = []
    for spec in SOURCE_TABLES:
        df = read_csv(spec.filename)
        rows.append(
            {
                "version": spec.version,
                "source_key": spec.source_key,
                "filename": spec.filename,
                "unit": spec.unit,
                "role": spec.role,
                "rows": len(df),
                "columns": len(df.columns),
                "identity_key": spec.identity_key or "not_identity_join_table",
                "unique_identities": safe_nunique(df, spec.identity_key) if spec.identity_key else np.nan,
            }
        )
    out = pd.DataFrame(rows)
    out.to_csv(OUT / "v27_prior_version_data_summary.csv", index=False)
    return out


def v22_results() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    bundles = read_csv("jito_public_bundles.csv")
    events = read_csv("jito_public_bundle_events.csv")
    edges = read_csv("jito_public_tipper_validator_edges.csv")
    validators = read_csv("jito_public_validator_orderflow_scores.csv")
    result_rows = [
        {"version": "v22", "analysis_module": "data_ingestion", "result_name": "observed_landed_bundles", "n": safe_nunique(bundles, "bundleId"), "value": safe_nunique(bundles, "bundleId"), "interpretation": "Public Jito landed bundle sample size."},
        {"version": "v22", "analysis_module": "data_ingestion", "result_name": "observed_validators", "n": safe_nunique(validators, "validator"), "value": safe_nunique(validators, "validator"), "interpretation": "Validator identities observed in v22 public bundle data."},
        {"version": "v22", "analysis_module": "data_ingestion", "result_name": "observed_pseudo_searchers", "n": safe_nunique(bundles, "tipper"), "value": safe_nunique(bundles, "tipper"), "interpretation": "Tipper address count; proxy for searcher identity, not verified entity."},
        {"version": "v22", "analysis_module": "data_ingestion", "result_name": "tipper_validator_edges", "n": len(edges), "value": len(edges), "interpretation": "Pair-level relationship network size."},
        {"version": "v22", "analysis_module": "data_ingestion", "result_name": "bundle_lifecycle_events", "n": len(events), "value": len(events), "interpretation": "Lifecycle event rows for timing/execution proxies."},
    ]
    mech_rows = [
        {"version": "v22", "mechanism": "private_orderflow_searcherflow", "metric": "candidate_to_non_bundle_ratio", "value": median_ratio(validators, "v22_candidate_like", "bundles"), "evidence_strength": "direct_landed_bundle_proxy", "limitation": "Landed bundles only; not full private contract evidence."},
        {"version": "v22", "mechanism": "private_orderflow_searcherflow", "metric": "candidate_to_non_tip_SOL_ratio", "value": median_ratio(validators, "v22_candidate_like", "total_tip_SOL"), "evidence_strength": "direct_landed_tip_proxy", "limitation": "Tipper is pseudo-searcher address."},
        {"version": "v22", "mechanism": "private_orderflow_searcherflow", "metric": "candidate_to_non_unique_tippers_ratio", "value": median_ratio(validators, "v22_candidate_like", "unique_tippers"), "evidence_strength": "flow_breadth_proxy", "limitation": "Does not identify off-chain relationship."},
        {"version": "v22", "mechanism": "bundle_outcome_execution", "metric": "candidate_to_non_tip_per_cu_ratio", "value": median_ratio(validators, "v22_candidate_like", "avg_tip_per_cu"), "evidence_strength": "landed_bid_efficiency_proxy", "limitation": "Only successful landed bundles; losing-bid frontier unobserved."},
        {"version": "v22", "mechanism": "latency_infra_reliability", "metric": "candidate_to_non_received_forwarded_ms_ratio", "value": median_ratio(validators, "v22_candidate_like", "avg_received_to_forwarded_ms"), "evidence_strength": "partial_lifecycle_timing_proxy", "limitation": "Public lifecycle timestamps are sparse and not raw network latency."},
        {"version": "v22", "mechanism": "entity_vertical_integration", "metric": "candidate_to_non_relationship_score_ratio", "value": median_ratio(validators, "v22_candidate_like", "relationship_score"), "evidence_strength": "suggestive_pairing_proxy", "limitation": "No verified ownership or contractual labels."},
    ]
    return result_rows, mech_rows


def append_model_stats(rows: list[dict[str, Any]], version: str, filename: str) -> None:
    df = read_csv(filename)
    for _, row in df.iterrows():
        rows.append(
            {
                "version": version,
                "analysis_module": "regression_or_structural_result",
                "result_name": row.get("model", "model"),
                "n": row.get("n", np.nan),
                "value": row.get("r_squared", np.nan),
                "r_squared": row.get("r_squared", np.nan),
                "adj_r_squared": row.get("adj_r_squared", np.nan),
                "candidate_coef": row.get("candidate_coef", np.nan),
                "candidate_p_value": row.get("candidate_p_value", np.nan),
                "interpretation": row.get("interpretation", "Prior-version model result reproduced from v27 static source_assets."),
            }
        )


def append_mechanisms(rows: list[dict[str, Any]], version: str, filename: str) -> None:
    df = read_csv(filename)
    for _, row in df.iterrows():
        mechanism = row.get("mechanism", "mechanism")
        rows.append(
            {
                "version": version,
                "mechanism": mechanism,
                "metric": row.get("score", row.get("analysis_role", "mechanism_attribution")),
                "value": row.get("incremental_r2_vs_baseline", row.get("incremental_r2_vs_stake_baseline", np.nan)),
                "r2_after_adding": row.get("add_to_baseline_r_squared", row.get("add_to_stake_r_squared", np.nan)),
                "incremental_r2": row.get("incremental_r2_vs_baseline", row.get("incremental_r2_vs_stake_baseline", np.nan)),
                "r2_loss_when_dropped_from_full": row.get("r2_loss_when_dropped_from_full", np.nan),
                "candidate_coef_add_module": row.get("candidate_coef_add_module", np.nan),
                "candidate_p_value_add_module": row.get("candidate_p_value_add_module", np.nan),
                "evidence_strength": row.get("evidence_strength", "prior_version_mechanism_result"),
                "limitation": row.get("interpretation", "Read as proxy evidence; not standalone causal proof."),
            }
        )


def append_counterfactuals(rows: list[dict[str, Any]]) -> None:
    path = SOURCE / "structural_counterfactual_estimates.csv"
    if not path.exists():
        return
    df = pd.read_csv(path)
    for _, row in df.iterrows():
        rows.append(
            {
                "version": "v24",
                "analysis_module": "counterfactual_result",
                "result_name": row.get("counterfactual", "counterfactual"),
                "n": row.get("candidate_validators", np.nan),
                "value": row.get("predicted_tip_sol_change", np.nan),
                "mechanism": row.get("mechanism", ""),
                "actual_predicted_tip_sol_sum": row.get("actual_predicted_tip_sol_sum", np.nan),
                "counterfactual_predicted_tip_sol_sum": row.get("counterfactual_predicted_tip_sol_sum", np.nan),
                "interpretation": "Prior v24 counterfactual reproduced from v27 static source_assets.",
            }
        )


def build_reproduction_tables() -> dict[str, pd.DataFrame]:
    data = data_summary()
    result_rows, mechanism_rows = v22_results()
    append_model_stats(result_rows, "v23", "structural_model_fit_stats.csv")
    append_model_stats(result_rows, "v24", "observable_proxy_regression_model_stats.csv")
    append_model_stats(result_rows, "v25", "validator_epoch_mev_bam_regression_stats.csv")
    append_mechanisms(mechanism_rows, "v23", "structural_mechanism_attribution.csv")
    append_mechanisms(mechanism_rows, "v24", "mechanism_identification_attribution.csv")
    append_mechanisms(mechanism_rows, "v25", "validator_epoch_mev_bam_mechanism_attribution.csv")
    counter_rows: list[dict[str, Any]] = []
    append_counterfactuals(counter_rows)

    results = pd.DataFrame(result_rows)
    mechanisms = pd.DataFrame(mechanism_rows)
    counterfactuals = pd.DataFrame(counter_rows)
    results.to_csv(OUT / "v27_prior_version_result_reproduction.csv", index=False)
    mechanisms.to_csv(OUT / "v27_prior_version_mechanism_reproduction.csv", index=False)
    counterfactuals.to_csv(OUT / "v27_prior_version_counterfactual_reproduction.csv", index=False)
    return {"data": data, "results": results, "mechanisms": mechanisms, "counterfactuals": counterfactuals}


def write_report(tables: dict[str, pd.DataFrame]) -> None:
    results = tables["results"]
    key_results = results.loc[
        results["result_name"].isin(
            [
                "observed_landed_bundles",
                "baseline_candidate_stake_opportunity",
                "full_structural_scores",
                "empirical_full_observable_proxy_benchmark",
                "summary_50_opportunity",
                "summary_50_available_mechanisms",
            ]
        )
    ]
    text = f"""# v27 Prior-Version Result Reproduction

This analysis module reproduces v22-v25 prior-version results from the static files already stored in `v27/data/source_assets/`. It does not call APIs, does not change the v27 dependent variable, and does not alter the main H7 benchmark.

## Data inputs

{md_table(tables['data'], max_rows=40)}

## Headline reproduced results

{md_table(key_results, max_rows=40)}

## Mechanism reproduction

{md_table(tables['mechanisms'], max_rows=80)}

## Counterfactual reproduction

{md_table(tables['counterfactuals'], max_rows=40)}
"""
    (OUT / "v27_prior_version_reproduction_report.md").write_text(text, encoding="utf-8")


def run() -> dict[str, Any]:
    tables = build_reproduction_tables()
    write_report(tables)
    summary = {
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "data_sources": int(len(tables["data"])),
        "result_rows": int(len(tables["results"])),
        "mechanism_rows": int(len(tables["mechanisms"])),
        "counterfactual_rows": int(len(tables["counterfactuals"])),
        "outputs": [
            "output/v27_prior_version_data_summary.csv",
            "output/v27_prior_version_result_reproduction.csv",
            "output/v27_prior_version_mechanism_reproduction.csv",
            "output/v27_prior_version_counterfactual_reproduction.csv",
            "output/v27_prior_version_reproduction_report.md",
        ],
    }
    (OUT / "v27_prior_version_reproduction_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    run()
