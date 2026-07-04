from __future__ import annotations

from .data_assembly import *


def candidate_preliminary(panel: pd.DataFrame) -> pd.DataFrame:
    variables = MECHANISM_SCORES + [
        "v22_total_tip_SOL",
        "v22_unique_tippers",
        "v22_relationship_score",
        "v25_total_mev_SOL",
        "v25_avg_excess_mev_share",
        "v25_positive_excess_epoch_share",
    ]
    rows = []
    for var in variables:
        if var not in panel.columns:
            continue
        x = pd.to_numeric(panel[var], errors="coerce")
        cand = x[panel[CANDIDATE].eq(1)]
        non = x[panel[CANDIDATE].eq(0)]
        rows.append(
            {
                "variable": var,
                "candidate_n": int(cand.notna().sum()),
                "non_candidate_n": int(non.notna().sum()),
                "candidate_mean": float(cand.mean()) if cand.notna().any() else np.nan,
                "non_candidate_mean": float(non.mean()) if non.notna().any() else np.nan,
                "candidate_median": float(cand.median()) if cand.notna().any() else np.nan,
                "non_candidate_median": float(non.median()) if non.notna().any() else np.nan,
                "mean_difference_candidate_minus_non": float(cand.mean() - non.mean())
                if cand.notna().any() and non.notna().any()
                else np.nan,
            }
        )
    out = pd.DataFrame(rows)
    out.to_csv(OUT / "v27_preliminary_candidate_comparison.csv", index=False)
    return out


def source_stage_label(source_key: str) -> str:
    lineage = SOURCE_LINEAGE.get(source_key)
    if lineage == "v22":
        return "v22_public_bundle_structural_data"
    if lineage == "v23":
        return "v23_external_api_structural_enrichment"
    if lineage == "v24":
        return "v24_integrated_empirical_structural_layer"
    if lineage == "v25":
        return "v25_50_epoch_jito_bam_expansion"
    return "other"


def dataframe_row_count(path: Path) -> int:
    if path.suffix.lower() == ".json":
        return 1
    try:
        return int(pd.read_csv(path, usecols=[0]).shape[0])
    except Exception:
        return 0


def build_v22_v25_ingestion_manifest(coverage: pd.DataFrame) -> pd.DataFrame:
    coverage_by_source = coverage.set_index("source").to_dict(orient="index") if not coverage.empty else {}
    unit_map = {
        "jito_public_bundles": "bundle",
        "jito_public_tipper_validator_edges": "tipper-validator edge",
        "jito_public_bundle_events": "bundle lifecycle event",
        "public_bundle_validator_orderflow_scores": "validator",
        "structural_validator_mechanism_score_panel": "validator with external API proxies",
        "structural_model_fit_stats": "prior model result",
        "structural_mechanism_attribution": "prior mechanism attribution",
        "structural_sequential_model_ladder": "prior structural ladder",
        "observable_proxy_validator_score_panel": "validator with integrated v22-v24 proxies",
        "structural_counterfactual_estimates": "prior counterfactual result",
        "observable_proxy_regression_stats": "prior regression result",
        "mechanism_identification_attribution": "prior mechanism attribution",
        "validator_epoch_mev_bam_summary_50epoch": "validator 50-epoch summary",
        "validator_epoch_mev_bam_panel_50epoch": "validator-epoch panel",
        "validator_epoch_mev_bam_regression_stats": "prior regression result",
        "validator_epoch_mev_bam_mechanism_attribution": "prior mechanism attribution",
    }
    api_map = {
        "v22": "Jito public bundle API; frozen snapshot in data/source_assets; optional online refresh via v27 api_sources/pipelines/jito_bundles.py and api_sources/pipelines/jito_epoch_bam.py.",
        "v23": "Solana RPC, Jito public, Stakewiz/Validators.app, Helius, Dune, Solscan-derived enrichment; frozen snapshot in data/source_assets.",
        "v24": "Joined/integrated outputs built from v22-v23 plus keyed data; frozen snapshot in data/source_assets.",
        "v25": "Jito Kobe epoch API plus BAM/IBRL validator-operation cache; frozen 50-epoch snapshot in data/source_assets.",
    }
    rows = []
    for key, path in SOURCES.items():
        version = SOURCE_LINEAGE.get(key)
        if version is None:
            continue
        cols = [] if path.suffix.lower() == ".json" else list(pd.read_csv(path, nrows=0).columns)
        cov = coverage_by_source.get(key, {})
        rows.append(
            {
                "version": version,
                "source_key": key,
                "content_stage": source_stage_label(key),
                "unit": unit_map.get(key, "table"),
                "source_path": str(path.relative_to(PKG)),
                "rows": dataframe_row_count(path),
                "columns": len(cols),
                "join_key_in_v27": "validator -> identity_account" if version in {"v22", "v23", "v24"} and "validator" in cols else "identity_account" if "identity_account" in cols else "not_joined_result_table",
                "matched_to_v26_rows": cov.get("matched_to_v26_rows", np.nan),
                "matched_unique_identities": cov.get("matched_unique_identities", np.nan),
                "matched_candidate_identities": cov.get("matched_candidate_identities", np.nan),
                "api_protocol": api_map.get(version, "local source asset"),
            }
        )
    out = pd.DataFrame(rows)
    out.to_csv(OUT / "v27_v22_v25_data_ingestion.csv", index=False)
    return out


def ratio_candidate_to_non(frame: pd.DataFrame, flag: str, value: str) -> float:
    x = pd.to_numeric(frame[value], errors="coerce")
    cand = x[frame[flag].astype(bool)]
    non = x[~frame[flag].astype(bool)]
    if not cand.notna().any() or not non.notna().any() or non.median() == 0:
        return np.nan
    return float(cand.median() / non.median())


def build_v22_v25_prior_result_reproduction() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    bundles = read_csv(SOURCES["jito_public_bundles"])
    edges = read_csv(SOURCES["jito_public_tipper_validator_edges"])
    validators = read_csv(SOURCES["public_bundle_validator_orderflow_scores"])
    events = read_csv(SOURCES["jito_public_bundle_events"])
    rows.extend(
        [
            {"version": "v22", "analysis_stage": "data_ingestion", "model_or_metric": "observed_landed_bundles", "n": int(bundles["bundleId"].nunique()), "value": int(bundles["bundleId"].nunique()), "evidence_channel": "public landed bundle sample", "interpretation": "Raw v22 public bundle sample size."},
            {"version": "v22", "analysis_stage": "data_ingestion", "model_or_metric": "observed_validators", "n": int(validators["validator"].nunique()), "value": int(validators["validator"].nunique()), "evidence_channel": "validator-level bundle aggregation", "interpretation": "Validator identities observed in v22 public bundle data."},
            {"version": "v22", "analysis_stage": "data_ingestion", "model_or_metric": "observed_pseudo_searchers", "n": int(bundles["tipper"].nunique()), "value": int(bundles["tipper"].nunique()), "evidence_channel": "pseudo-searcher/tipper addresses", "interpretation": "Tipper is a pseudo-searcher proxy, not verified real-world entity."},
            {"version": "v22", "analysis_stage": "data_ingestion", "model_or_metric": "tipper_validator_edges", "n": len(edges), "value": len(edges), "evidence_channel": "relationship network", "interpretation": "Pair-level repeated matching object."},
            {"version": "v22", "analysis_stage": "data_ingestion", "model_or_metric": "bundle_lifecycle_events", "n": len(events), "value": len(events), "evidence_channel": "lifecycle timing/execution", "interpretation": "Events support lifecycle/execution proxies but do not observe losing bids."},
            {"version": "v22", "analysis_stage": "mechanism_proxy", "model_or_metric": "candidate_to_non_candidate_bundle_ratio", "n": len(validators), "value": ratio_candidate_to_non(validators, "v22_candidate_like", "bundles"), "evidence_channel": "arrival/order-flow access", "interpretation": "Candidate-like validators receive substantially more landed public bundles."},
            {"version": "v22", "analysis_stage": "mechanism_proxy", "model_or_metric": "candidate_to_non_candidate_tip_SOL_ratio", "n": len(validators), "value": ratio_candidate_to_non(validators, "v22_candidate_like", "total_tip_SOL"), "evidence_channel": "private order-flow/searcher-flow", "interpretation": "Candidate-like validators receive more landed tip value in the public sample."},
            {"version": "v22", "analysis_stage": "mechanism_proxy", "model_or_metric": "candidate_to_non_candidate_tip_per_cu_ratio", "n": len(validators), "value": ratio_candidate_to_non(validators, "v22_candidate_like", "avg_tip_per_cu"), "evidence_channel": "bundle outcome/execution", "interpretation": "Bid/value efficiency proxy among landed bundles."},
        ]
    )

    for version, key in [("v23", "structural_model_fit_stats"), ("v24", "observable_proxy_regression_stats"), ("v25", "validator_epoch_mev_bam_regression_stats")]:
        df = read_csv(SOURCES[key])
        for _, row in df.iterrows():
            rows.append(
                {
                    "version": version,
                    "analysis_stage": "prior_model_result",
                    "model_or_metric": row.get("model", "model"),
                    "n": row.get("n", np.nan),
                    "r_squared": row.get("r_squared", np.nan),
                    "adj_r_squared": row.get("adj_r_squared", np.nan),
                    "candidate_coef": row.get("candidate_coef", np.nan),
                    "candidate_p_value": row.get("candidate_p_value", np.nan),
                    "value": row.get("r_squared", np.nan),
                    "evidence_channel": row.get("analysis_role", "structural/new-data result"),
                    "interpretation": row.get("interpretation", "Prior version result reproduced from v27 source_assets."),
                }
            )
    out = pd.DataFrame(rows)
    out.to_csv(OUT / "v27_v22_v25_prior_result_reproduction.csv", index=False)
    return out


def build_v22_v25_proxy_catalog(panel: pd.DataFrame, score_map: pd.DataFrame) -> pd.DataFrame:
    component_to_mech = {}
    for _, row in score_map.iterrows():
        component_to_mech.setdefault(row["component_column"], []).append(row["mechanism"])
    rows = []
    for col in sorted(c for c in panel.columns if c.startswith(("v22_", "v23_", "v24_", "v25_", "supp_"))):
        x = pd.to_numeric(panel[col], errors="coerce")
        if x.notna().sum() == 0:
            continue
        cand = x[panel[CANDIDATE].eq(1)]
        non = x[panel[CANDIDATE].eq(0)]
        if col.startswith("supp_"):
            version = "v22_v25_composite"
            mechanisms = [col.replace("supp_", "").replace("_score", "")]
        else:
            version = col.split("_", 1)[0]
            mechanisms = component_to_mech.get(col, [])
        rows.append(
            {
                "version": version,
                "proxy": col,
                "mechanism": ";".join(mechanisms) if mechanisms else "not_in_score_directly",
                "used_in_mechanism_score": bool(mechanisms),
                "nonmissing": int(x.notna().sum()),
                "unique_values": int(x.nunique(dropna=True)),
                "candidate_nonmissing": int(cand.notna().sum()),
                "non_candidate_nonmissing": int(non.notna().sum()),
                "candidate_mean": float(cand.mean()) if cand.notna().any() else np.nan,
                "non_candidate_mean": float(non.mean()) if non.notna().any() else np.nan,
                "candidate_minus_non_mean": float(cand.mean() - non.mean()) if cand.notna().any() and non.notna().any() else np.nan,
                "candidate_to_non_median_ratio": float(cand.median() / non.median()) if cand.notna().any() and non.notna().any() and non.median() not in [0, np.nan] else np.nan,
            }
        )
    out = pd.DataFrame(rows)
    out.to_csv(OUT / "v27_v22_v25_proxy_catalog.csv", index=False)
    return out


def build_v22_v25_preliminary_by_version(proxy_catalog: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (version, mechanism), g in proxy_catalog.groupby(["version", "mechanism"], dropna=False):
        rows.append(
            {
                "version": version,
                "mechanism": mechanism,
                "proxy_count": len(g),
                "used_proxy_count": int(g["used_in_mechanism_score"].sum()),
                "median_nonmissing": float(g["nonmissing"].median()),
                "median_candidate_minus_non_mean": float(g["candidate_minus_non_mean"].median(skipna=True)),
                "median_candidate_to_non_ratio": float(g["candidate_to_non_median_ratio"].median(skipna=True)),
            }
        )
    out = pd.DataFrame(rows).sort_values(["version", "mechanism"])
    out.to_csv(OUT / "v27_v22_v25_preliminary_by_version.csv", index=False)
    return out


def build_v22_v25_mechanism_evidence_matrix(mechanism: pd.DataFrame, prior_results: pd.DataFrame) -> pd.DataFrame:
    labels = {
        "private_orderflow_searcherflow": "Private order-flow / searcher-flow",
        "bundle_outcome_execution": "Bundle outcome / landed execution",
        "latency_infra_reliability": "Latency / infra / reliability",
        "entity_vertical_integration": "Entity / vertical integration",
    }
    limits = {
        "private_orderflow_searcherflow": "Supports landed flow and repeated pseudo-searcher matching; cannot prove private contracts or off-chain exclusivity.",
        "bundle_outcome_execution": "Supports bid/value/execution quality among landed bundles; cannot observe losing-bid auction frontier.",
        "latency_infra_reliability": "Supports operational and timing proxies; cannot directly prove network/shred latency without direct timestamps/routing data.",
        "entity_vertical_integration": "Supports affiliation/infrastructure proxies; cannot prove ownership or contractual vertical integration without verified labels/contracts.",
    }
    prior_hint = {
        "private_orderflow_searcherflow": "v22 tipper-validator edges, v23/v24 order-flow scores, Helius/Dune/address-history proxies.",
        "bundle_outcome_execution": "v22 tip per CU/lifecycle events, v23/v24 execution scores, v25 IBRL/BAM quality fields.",
        "latency_infra_reliability": "v22 lifecycle timing, v23 Solana metadata, v24 infra score, v25 build-time/BAM connection proxies.",
        "entity_vertical_integration": "v23/v24 entity scores and v25 BAM/Jito-directed shares; weakest direct proof channel.",
    }
    rows = []
    mech_by_name = mechanism.set_index("mechanism") if not mechanism.empty else pd.DataFrame()
    for key, label in labels.items():
        row = mech_by_name.loc[key].to_dict() if key in mech_by_name.index else {}
        rows.append(
            {
                "mechanism": key,
                "mechanism_label": label,
                "v27_incremental_r2_vs_core": row.get("incremental_r2_vs_core", np.nan),
                "v27_r2_loss_if_dropped": row.get("r2_loss_if_dropped_from_full", np.nan),
                "v27_score_coef": row.get("score_coef", np.nan),
                "v27_score_p_value": row.get("score_p_value", np.nan),
                "v27_candidate_attenuation_vs_core": row.get("candidate_attenuation_vs_core", np.nan),
                "evidence_read": row.get("evidence_read", "not estimated"),
                "supporting_v22_v25_sources": prior_hint[key],
                "what_it_supports": "Additional same-DV explanatory power and candidate-coefficient attenuation if R2/p/drop-loss move in the expected direction.",
                "what_is_incomplete": limits[key],
            }
        )
    out = pd.DataFrame(rows)
    out.to_csv(OUT / "v27_v22_v25_mechanism_evidence_matrix.csv", index=False)
    return out



def build_v22_v25_content_layer(
    coverage: pd.DataFrame,
    panel: pd.DataFrame,
    score_map: pd.DataFrame,
    mechanism: pd.DataFrame,
) -> dict[str, pd.DataFrame]:
    ingestion = build_v22_v25_ingestion_manifest(coverage)
    prior = build_v22_v25_prior_result_reproduction()
    proxy_catalog = build_v22_v25_proxy_catalog(panel, score_map)
    prelim_by_version = build_v22_v25_preliminary_by_version(proxy_catalog)
    evidence = build_v22_v25_mechanism_evidence_matrix(mechanism, prior)
    return {
        "ingestion": ingestion,
        "prior_results": prior,
        "proxy_catalog": proxy_catalog,
        "preliminary_by_version": prelim_by_version,
        "evidence_matrix": evidence,
    }
