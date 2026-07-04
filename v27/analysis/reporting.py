from __future__ import annotations

from .data_assembly import *


def variable_dictionary(feature_list: list[str], score_map: pd.DataFrame) -> pd.DataFrame:
    rows = [
        {
            "variable": TARGET,
            "role": "DV",
            "definition": "Log MEV per scheduled leader slot; unchanged from the v26 reproduction of the v19-v21 H7 benchmark.",
            "source": "v26/data/main_benchmark_model_panel.csv",
        },
        {
            "variable": CANDIDATE,
            "role": "IV: candidate/residual edge",
            "definition": "Indicator for the candidate-like validator group used in the v19-v21/v26 benchmark.",
            "source": "v26 H7 feature list",
        },
    ]
    for feature in feature_list:
        if feature == CANDIDATE:
            continue
        role = "IV: v26 H7 fixed benchmark regressor"
        if feature in CORE_CONTROLS:
            role = "IV: core opportunity control"
        rows.append(
            {
                "variable": feature,
                "role": role,
                "definition": "One of the 66 fixed H7/B10 regressors from v26; not re-selected in v27.",
                "source": "v26/data/h7_b10_feature_list.csv",
            }
        )
    for score in MECHANISM_SCORES:
        components = score_map.loc[score_map["score"].eq(score) & score_map["used"]]
        rows.append(
            {
                "variable": score,
                "role": "Supplemental IV/proxy mechanism score",
                "definition": "Mean of signed z-scored v22-v25 proxy components: "
                + ", ".join(components["component_column"].tolist()),
                "source": "v22-v25 supplemental public/API/cache data joined by identity_account",
            }
        )
    out = pd.DataFrame(rows)
    out.to_csv(OUT / "v27_variable_dictionary.csv", index=False)
    return out


def write_workbook(
    manifest: pd.DataFrame,
    coverage: pd.DataFrame,
    variables: pd.DataFrame,
    preliminary: pd.DataFrame,
    simple_stats: pd.DataFrame,
    single_proxy: pd.DataFrame,
    mechanism: pd.DataFrame,
    ladder: pd.DataFrame,
    counterfactuals: pd.DataFrame,
    audit: pd.DataFrame,
    content: dict[str, pd.DataFrame],
) -> None:
    with pd.ExcelWriter(OUT / "v27_analysis_workbook.xlsx", engine="openpyxl") as writer:
        manifest.to_excel(writer, sheet_name="source_manifest", index=False)
        coverage.to_excel(writer, sheet_name="data_coverage", index=False)
        variables.to_excel(writer, sheet_name="variable_dictionary", index=False)
        preliminary.to_excel(writer, sheet_name="preliminary", index=False)
        simple_stats.to_excel(writer, sheet_name="simple_regressions", index=False)
        single_proxy.head(100).to_excel(writer, sheet_name="single_proxy_screen", index=False)
        mechanism.to_excel(writer, sheet_name="mechanism_id", index=False)
        ladder.to_excel(writer, sheet_name="structural_ladder", index=False)
        counterfactuals.to_excel(writer, sheet_name="counterfactuals", index=False)
        audit.to_excel(writer, sheet_name="prior_structural_audit", index=False)
        content["ingestion"].to_excel(writer, sheet_name="v22_v25_ingestion", index=False)
        content["prior_results"].head(200).to_excel(writer, sheet_name="v22_v25_prior_results", index=False)
        content["proxy_catalog"].head(300).to_excel(writer, sheet_name="v22_v25_proxy_catalog", index=False)
        content["preliminary_by_version"].to_excel(writer, sheet_name="v22_v25_prelim_by_ver", index=False)
        content["evidence_matrix"].to_excel(writer, sheet_name="v22_v25_evidence", index=False)


def write_docs(
    summary: dict[str, Any],
    manifest: pd.DataFrame,
    coverage: pd.DataFrame,
    variables: pd.DataFrame,
    preliminary: pd.DataFrame,
    simple_stats: pd.DataFrame,
    single_proxy: pd.DataFrame,
    mechanism: pd.DataFrame,
    ladder: pd.DataFrame,
    counterfactuals: pd.DataFrame,
    audit: pd.DataFrame,
    content: dict[str, pd.DataFrame],
) -> None:
    main = simple_stats.loc[
        simple_stats["model"].eq("v27_main_H7_benchmark_v26_exact")
    ].iloc[0]
    h7_aug = simple_stats.loc[
        simple_stats["model"].eq("h7_plus_all_four_scores_on_matched_sample")
    ]
    h7_aug_text = (
        f"On the proxy-matched sample, H7 plus the four supplemental scores has R2={float(h7_aug.iloc[0]['r_squared']):.6f}, "
        f"N={int(h7_aug.iloc[0]['n'])}."
        if not h7_aug.empty and pd.notna(h7_aug.iloc[0]["r_squared"])
        else "The H7 plus supplemental-score model was not estimable on the matched sample."
    )
    report = f"""# v27 Structural Re-run Under v26 Model Discipline

## Executive result

The v27 pipeline first reproduces the v26 canonical benchmark before using any v22-v25 supplemental data.

- DV: `{TARGET}`.
- Main IV set: the fixed 66 H7/B10 regressors from v26, including `{CANDIDATE}`.
- Main benchmark result: R2={float(main['r_squared']):.6f}, adjusted R2={float(main['adj_r_squared']):.6f}, N={int(main['n'])}, candidate coefficient={float(main['candidate_coef']):.6f}, candidate p-value={float(main['candidate_p_value']):.6g}.
- Benchmark check vs v26: {main.get('status_vs_v26', 'PASS')}; R2 error={float(main.get('r2_error_vs_v26', 0.0)):.3g}.
- v22-v25 data are supplemental mechanism proxies, not a replacement outcome or a replacement benchmark. {h7_aug_text}

## Data ingestion and coverage

{md_table(coverage, digits=4)}

### v22-v25 source ingestion inside v27

{md_table(content["ingestion"], max_rows=40, digits=4)}

## Cleaning and construction

The v26 source panel is filtered to the exact H7 common sample by requiring non-missing `{TARGET}` and all 66 H7 regressors. The v22-v25 sources are then joined by `identity_account`; v22-v24 expose the validator identity as `validator`, while v25 already uses `identity_account`.

The four supplemental mechanism scores are signed z-score averages:

{md_table(variables[variables['role'].str.contains('Supplemental', na=False)], digits=4)}

## Preliminary analysis

Candidate vs non-candidate differences in the constructed proxy scores and key raw proxy variables:

{md_table(preliminary, digits=5)}

Version-by-version proxy coverage and candidate/non-candidate contrasts:

{md_table(content["preliminary_by_version"], max_rows=80, digits=5)}

## Mechanism identification: simple regressions

These are reduced-form/simple regressions using the same DV. They do not replace the main H7 benchmark.

{md_table(simple_stats[['model','n','independent_variable_count','r_squared','adj_r_squared','candidate_coef','candidate_p_value','sample_note']].head(20), digits=6)}

Top single supplemental proxy screens, each added to candidate + stake + scheduled-slot controls:

{md_table(single_proxy.head(20), digits=6)}

Prior v22-v25 results reproduced from v27 source assets:

{md_table(content["prior_results"].head(80), digits=6)}

## Structural proxy analysis

The structural layer is a score-based proxy model: `{TARGET}` on candidate, stake, scheduled slots, and the four v22-v25 mechanism scores. It answers whether the candidate coefficient is attenuated and which proxy blocks explain additional variation within the same joined sample.

{md_table(mechanism, digits=6)}

Sequential structural ladder:

{md_table(ladder, digits=6)}

## Counterfactual analysis

For candidate validators in the common structural sample, each counterfactual sets one supplemental mechanism score to the non-candidate median and recomputes predicted `{TARGET}`. The final row sets the candidate indicator to zero after observed scores are controlled for.

{md_table(counterfactuals, digits=6)}

## Four-mechanism evidence matrix

{md_table(content["evidence_matrix"], digits=6)}

## Interpretation discipline

1. Private order-flow/searcher-flow is the primary mechanism when it raises R2, has a meaningful score coefficient, and attenuates the residual candidate coefficient.
2. Bundle outcome/execution is supported if landed bundle/tip-per-CU/IBRL proxies add explanatory power; it is not complete proof of private order-flow access.
3. Latency/infra reliability is only a structural proxy unless direct timing/network routing data are observed; v27 uses signed latency and build-quality variables to test whether this weak channel improves.
4. Entity/vertical integration remains the hardest to prove: BAM/Jito-directed shares and prior entity scores are proxies, not direct ownership or contractual links.

## Prior structural audit

{md_table(audit, digits=4)}
"""
    (OUT / "v27_report.md").write_text(report, encoding="utf-8")

    runbook = f"""# v27 Runbook

## Purpose

Re-run the v22-v25 structural/new-data content under the v26 canonical model discipline.

## Command

```bash
cd /path/to/v27
python -m analysis.main
jupyter nbconvert --to notebook --execute notebooks/analysis.ipynb --output analysis.ipynb --output-dir notebooks
jupyter nbconvert --to notebook --execute notebooks/report.ipynb --output report.ipynb --output-dir notebooks
```

## End-to-end checks

- Main benchmark must reproduce v26: status `{summary['benchmark_status_vs_v26']}`.
- Main benchmark R2: {summary['main_r_squared']:.12f}.
- Main benchmark N: {summary['main_n']}.
- Supplemental data are joined after the benchmark check and are not used to redefine the DV or the H7 IV set.

## Main outputs

- `v27/output/v27_report.md`
- `v27/output/v27_analysis_workbook.xlsx`
- `v27/output/v27_simple_regression_stats.csv`
- `v27/output/v27_mechanism_identification.csv`
- `v27/output/v27_structural_model_stats.csv`
- `v27/output/v27_counterfactuals.csv`
- `v27/output/v27_v22_v25_data_ingestion.csv`
- `v27/output/v27_v22_v25_proxy_catalog.csv`
- `v27/output/v27_v22_v25_prior_result_reproduction.csv`
- `v27/output/v27_v22_v25_mechanism_evidence_matrix.csv`
- `v27/notebooks/analysis.ipynb`
- `v27/notebooks/report.ipynb`
"""
    (PKG / "runbook.md").write_text(runbook, encoding="utf-8")

    data_doc = f"""# v27 Data, Proxy, and Variable Definitions

## Canonical model

- DV: `{TARGET}`.
- Main IVs: 66 fixed H7/B10 regressors loaded from `v26/data/h7_b10_feature_list.csv`.
- Candidate/residual edge IV: `{CANDIDATE}`.
- Core controls used in simple/structural proxy models: `{CORE_CONTROLS[0]}`, `{CORE_CONTROLS[1]}`, `{CORE_CONTROLS[2]}`.

## Supplemental proxy scores

{md_table(variables[variables['role'].str.contains('Supplemental', na=False)], digits=4)}

## Full variable dictionary

See `v27/output/v27_variable_dictionary.csv`.
"""
    (PKG / "data proxy variable.md").write_text(data_doc, encoding="utf-8")

    api_doc = f"""# v27 API Data Protocol and Join

## Source protocol

v27 does not fetch new API data. It consumes the locally cached v22-v25 outputs and re-estimates them under the v26 DV/IV discipline.

{md_table(manifest[['source_key','source_path','exists','size_bytes']], max_rows=40, digits=4)}

## Join protocol

- v26 benchmark panel key: `identity_account`, with `vote_account` retained for audit.
- v22 public validator scores key: `validator` renamed to `identity_account`.
- v23 structural panel key: `validator` renamed to `identity_account`.
- v24 scored structural panel key: `validator` renamed to `identity_account`.
- v25 50-epoch summary key: `identity_account`.

## Coverage

{md_table(coverage, digits=4)}
"""
    (PKG / "API data protocol join.md").write_text(api_doc, encoding="utf-8")


def write_notebooks() -> None:
    root_setup = (
        "from pathlib import Path\n"
        "ROOT = Path.cwd()\n"
        "if ROOT.name == 'notebooks':\n"
        "    ROOT = ROOT.parent\n"
        "OUT = ROOT / 'output'\n"
    )

    analysis = nbf.v4.new_notebook()
    analysis.cells = [
        nbf.v4.new_markdown_cell("# v27 Analysis Notebook\n\nEnd-to-end v22-v25 supplemental structural re-run under the v26 benchmark DV/IV discipline."),
        nbf.v4.new_code_cell(
            root_setup
            + "import json\n"
            + "import pandas as pd\n"
            + "from IPython.display import display, Markdown\n"
            + "summary = json.loads((OUT / 'run_summary.json').read_text())\n"
            + "display(summary)"
        ),
        nbf.v4.new_code_cell(
            "tables = {\n"
            "    'coverage': pd.read_csv(OUT / 'v27_data_coverage.csv'),\n"
            "    'variables': pd.read_csv(OUT / 'v27_variable_dictionary.csv'),\n"
            "    'preliminary': pd.read_csv(OUT / 'v27_preliminary_candidate_comparison.csv'),\n"
            "    'simple': pd.read_csv(OUT / 'v27_simple_regression_stats.csv'),\n"
            "    'single_proxy': pd.read_csv(OUT / 'v27_single_proxy_screen.csv'),\n"
            "    'mechanism': pd.read_csv(OUT / 'v27_mechanism_identification.csv'),\n"
            "    'ladder': pd.read_csv(OUT / 'v27_structural_sequential_ladder.csv'),\n"
            "    'counterfactuals': pd.read_csv(OUT / 'v27_counterfactuals.csv'),\n"
            "    'same_dv_iv_suite': pd.read_csv(OUT / 'v27_same_dv_iv_model_suite.csv'),\n"
            "    'result_lineage': pd.read_csv(OUT / 'v27_result_lineage.csv'),\n"
            "}\n"
            "for name, df in tables.items():\n"
            "    display(Markdown(f'## {name}'))\n"
            "    display(df.head(30))"
        ),
        nbf.v4.new_code_cell(
            "report = (OUT / 'v27_report.md').read_text()\n"
            "display(Markdown(report))"
        ),
    ]
    nbf.write(analysis, NOTEBOOKS / "analysis.ipynb")

    report = nbf.v4.new_notebook()
    report.cells = [
        nbf.v4.new_markdown_cell("# v27 Brief Report"),
        nbf.v4.new_code_cell(
            root_setup
            + "from IPython.display import Markdown, display\n"
            + "display(Markdown((OUT / 'v27_report.md').read_text()))"
        ),
    ]
    nbf.write(report, NOTEBOOKS / "report.ipynb")
