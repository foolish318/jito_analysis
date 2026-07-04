from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

PKG = Path(__file__).resolve().parents[1]
DATA = PKG / 'data'
VARIABLES = DATA / 'variables'
OUT = PKG / 'output'
for path in [VARIABLES, OUT]:
    path.mkdir(parents=True, exist_ok=True)

from analysis import data_assembly as core
from analysis.preliminary import candidate_preliminary
from analysis.reporting import variable_dictionary


def copy_if_exists(src: Path, dst: Path) -> None:
    if src.exists():
        shutil.copy2(src, dst)


def run() -> dict[str, object]:
    manifest = core.source_manifest()
    main, feature_list, benchmark_stats, _ = core.build_main_panel()
    supplemental, coverage = core.build_supplemental_proxy_panel(main)
    panel, score_map = core.add_mechanism_scores(supplemental)
    variables = variable_dictionary(feature_list, score_map)
    preliminary = candidate_preliminary(panel)

    copy_if_exists(DATA / 'main_benchmark_panel_with_ids.csv', VARIABLES / 'main_benchmark_panel_with_ids.csv')
    copy_if_exists(DATA / 'supplemental_proxy_panel.csv', VARIABLES / 'supplemental_proxy_panel.csv')
    copy_if_exists(DATA / 'model_panel.csv', VARIABLES / 'model_panel_with_mechanism_scores.csv')
    copy_if_exists(OUT / 'v27_mechanism_score_component_map.csv', VARIABLES / 'mechanism_score_component_map.csv')
    copy_if_exists(OUT / 'v27_variable_dictionary.csv', VARIABLES / 'variable_dictionary.csv')
    copy_if_exists(OUT / 'v27_preliminary_candidate_comparison.csv', VARIABLES / 'preliminary_candidate_comparison.csv')

    feature_roles = []
    for feature in feature_list:
        role = 'H7 fixed IV'
        if feature == core.CANDIDATE:
            role = 'candidate/residual edge IV'
        elif feature in core.CORE_CONTROLS:
            role = 'core opportunity control IV'
        feature_roles.append({'variable': feature, 'role': role, 'dv': core.TARGET})
    pd.DataFrame(feature_roles).to_csv(VARIABLES / 'h7_feature_roles.csv', index=False)

    summary = {
        'finished_at': datetime.now(timezone.utc).isoformat(),
        'source_manifest_rows': len(manifest),
        'main_panel_rows': len(main),
        'h7_feature_count': len(feature_list),
        'supplemental_panel_rows': len(supplemental),
        'model_panel_rows': len(panel),
        'mechanism_score_components': len(score_map),
        'variable_dictionary_rows': len(variables),
        'preliminary_rows': len(preliminary),
        'benchmark_r_squared_check': benchmark_stats['r_squared'],
    }
    (VARIABLES / 'build_variables_summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps(summary, indent=2))
    return summary


if __name__ == '__main__':
    run()