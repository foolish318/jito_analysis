from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from .data_assembly import (
    CORE_CONTROLS,
    MECHANISM_SCORES,
    OUT,
    TARGET,
    add_mechanism_scores,
    build_main_panel,
    build_supplemental_proxy_panel,
    source_manifest,
)
from .preliminary import build_v22_v25_content_layer, candidate_preliminary
from .regression import run_simple_regressions, single_proxy_screen
from .reporting import variable_dictionary, write_docs, write_notebooks, write_workbook
from .structural import counterfactual_analysis, existing_structural_audit, mechanism_identification


def run() -> dict[str, Any]:
    manifest = source_manifest()
    main, feature_list, benchmark_stats, _ = build_main_panel()
    supplemental, coverage = build_supplemental_proxy_panel(main)
    panel, score_map = add_mechanism_scores(supplemental)
    preliminary = candidate_preliminary(panel)
    simple_stats, _ = run_simple_regressions(main, panel, feature_list, benchmark_stats)
    single_proxy = single_proxy_screen(panel)
    mechanism, ladder, structural_fit = mechanism_identification(panel)
    counterfactuals = counterfactual_analysis(panel, structural_fit)
    audit = existing_structural_audit()
    content = build_v22_v25_content_layer(coverage, panel, score_map, mechanism)
    variables = variable_dictionary(feature_list, score_map)

    summary = {
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "benchmark_status_vs_v26": benchmark_stats["status_vs_v26"],
        "main_r_squared": benchmark_stats["r_squared"],
        "main_adj_r_squared": benchmark_stats["adj_r_squared"],
        "main_n": benchmark_stats["n"],
        "main_candidate_coef": benchmark_stats["candidate_coef"],
        "main_candidate_p_value": benchmark_stats["candidate_p_value"],
        "structural_common_n": int(
            panel.dropna(subset=[TARGET] + CORE_CONTROLS + MECHANISM_SCORES).shape[0]
        ),
        "structural_full_score_r_squared": float(
            pd.read_csv(OUT / "v27_structural_model_stats.csv")
            .set_index("model")
            .loc["structural_core_plus_all_four_scores", "r_squared"]
        ),
        "v22_v25_ingestion_rows": int(len(content["ingestion"])),
        "v22_v25_proxy_catalog_rows": int(len(content["proxy_catalog"])),
        "v22_v25_prior_result_rows": int(len(content["prior_results"])),
        "outputs": [
            "v27/output/v27_report.md",
            "v27/output/v27_analysis_workbook.xlsx",
            "v27/output/v27_v22_v25_data_ingestion.csv",
            "v27/output/v27_v22_v25_proxy_catalog.csv",
            "v27/output/v27_v22_v25_prior_result_reproduction.csv",
            "v27/output/v27_v22_v25_mechanism_evidence_matrix.csv",
            "v27/notebooks/analysis.ipynb",
            "v27/notebooks/report.ipynb",
        ],
    }
    (OUT / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    write_workbook(
        manifest,
        coverage,
        variables,
        preliminary,
        simple_stats,
        single_proxy,
        mechanism,
        ladder,
        counterfactuals,
        audit,
        content,
    )
    write_docs(
        summary,
        manifest,
        coverage,
        variables,
        preliminary,
        simple_stats,
        single_proxy,
        mechanism,
        ladder,
        counterfactuals,
        audit,
        content,
    )
    write_notebooks()
    return summary


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
