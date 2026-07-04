from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from api_sources.common import ensure_columns, numeric, request_json, save_json
from api_sources.providers import jito

PKG = Path(__file__).resolve().parents[2]
DATA = PKG / 'data'
SOURCE_ASSETS = DATA / 'source_assets'
API_RAW = DATA / 'api_raw'
LAMPORTS_PER_SOL = 1_000_000_000

def first_list_item(value: Any) -> Any:
    if isinstance(value, list) and value:
        return value[0]
    return None



def fetch_jito_public_bundles(limit: int, write_source_assets: bool) -> dict[str, Any]:
    raw_dir = API_RAW / 'jito_public_bundles'
    raw_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    recent_url = jito.public_bundle_recent(limit)
    top_url = jito.public_bundle_recent(limit, sort='Tip', asc=False)
    meta_recent, recent = request_json(recent_url)
    meta_top, top = request_json(top_url)
    save_json(raw_dir / 'recent.json', recent)
    save_json(raw_dir / 'top_tip.json', top)
    manifest.extend([meta_recent, meta_top])
    rows = []
    for source, obj in [('recent', recent), ('top_tip', top)]:
        if isinstance(obj, list):
            for row in obj:
                if isinstance(row, dict):
                    rec = dict(row)
                    rec['source'] = source
                    rows.append(rec)
    summaries = pd.DataFrame(rows)
    detail_rows = []
    event_rows = []
    bundle_ids = summaries.get('bundleId', pd.Series(dtype=str)).dropna().astype(str).drop_duplicates().head(limit).tolist()
    for bundle_id in bundle_ids:
        detail_url = jito.public_bundle_detail(bundle_id)
        event_url = jito.public_bundle_events(bundle_id)
        meta_detail, detail = request_json(detail_url, timeout=45)
        meta_event, events = request_json(event_url, timeout=45)
        manifest.extend([meta_detail, meta_event])
        save_json(raw_dir / 'bundle' / f'{bundle_id}.json', detail)
        save_json(raw_dir / 'bundle_events' / f'{bundle_id}.json', events)
        if isinstance(detail, list):
            detail_rows.extend([r for r in detail if isinstance(r, dict)])
        elif isinstance(detail, dict):
            detail_rows.append(detail)
        if isinstance(events, list):
            for ev in events:
                if isinstance(ev, dict):
                    ev = dict(ev)
                    ev.setdefault('bundleId', bundle_id)
                    event_rows.append(ev)
        elif isinstance(events, dict):
            events = dict(events)
            events.setdefault('bundleId', bundle_id)
            event_rows.append(events)
        time.sleep(0.12)
    details = pd.DataFrame(detail_rows)
    if details.empty:
        details = summaries.copy()
    if not details.empty:
        if 'bundleId' not in details and 'uuid' in details:
            details = details.rename(columns={'uuid': 'bundleId'})
        if 'validator' not in details:
            details['validator'] = np.nan
        if 'tipper' not in details:
            details['tipper'] = details.get('tippers', pd.Series(index=details.index)).apply(first_list_item)
        if 'landedTipLamports' in details:
            details['tip_SOL'] = numeric(details['landedTipLamports']) / LAMPORTS_PER_SOL
        elif 'tip_SOL' not in details:
            details['tip_SOL'] = numeric(details.get('tip', pd.Series(index=details.index))) / LAMPORTS_PER_SOL
        if 'landedCu' not in details:
            details['landedCu'] = np.nan
        details['avg_tip_per_cu'] = numeric(details['tip_SOL']) / numeric(details['landedCu']).replace(0, np.nan)
        details['source_recent_bundles'] = details.get('source', '').astype(str).eq('recent') if 'source' in details else False
        details['source_top_tip_bundles'] = details.get('source', '').astype(str).eq('top_tip') if 'source' in details else False
    bundles_cols = ['bundleId', 'validator', 'slot', 'tipper', 'tip_SOL', 'landedCu', 'avg_tip_per_cu', 'source_recent_bundles', 'source_top_tip_bundles']
    bundles = ensure_columns(details, bundles_cols) if not details.empty else pd.DataFrame(columns=bundles_cols)
    if not bundles.empty:
        g = bundles.groupby('validator', dropna=False)
        scores = g.agg(
            bundles=('bundleId', 'nunique'),
            total_tip_SOL=('tip_SOL', 'sum'),
            avg_tip_SOL=('tip_SOL', 'mean'),
            median_tip_SOL=('tip_SOL', 'median'),
            unique_tippers=('tipper', 'nunique'),
            unique_slots=('slot', 'nunique'),
            avg_landed_cu=('landedCu', 'mean'),
            avg_tip_per_cu=('avg_tip_per_cu', 'mean'),
            median_tip_per_cu=('avg_tip_per_cu', 'median'),
        ).reset_index()
        total_tip = scores['total_tip_SOL'].sum()
        total_bundles = scores['bundles'].sum()
        scores['tip_share'] = scores['total_tip_SOL'] / total_tip if total_tip else np.nan
        scores['bundle_share'] = scores['bundles'] / total_bundles if total_bundles else np.nan
        scores['relationship_score'] = np.log1p(scores['unique_tippers']) + np.log1p(scores['total_tip_SOL'].clip(lower=0))
        scores['positive_relationship_tip_share'] = scores['tip_share']
        scores['tipper_tip_hhi'] = np.nan
        scores['top_tipper_tip_share'] = np.nan
        scores['v22_candidate_like'] = False
        edge = bundles.groupby(['tipper', 'validator'], dropna=False).agg(total_tip_SOL=('tip_SOL', 'sum'), bundles=('bundleId', 'nunique')).reset_index()
    else:
        scores = pd.DataFrame(columns=['validator'])
        edge = pd.DataFrame(columns=['tipper', 'validator'])
    events_df = pd.DataFrame(event_rows)
    bundles.to_csv(API_RAW / 'jito_public_bundles_online.csv', index=False)
    scores.to_csv(API_RAW / 'jito_public_validator_orderflow_scores_online.csv', index=False)
    edge.to_csv(API_RAW / 'jito_public_tipper_validator_edges_online.csv', index=False)
    events_df.to_csv(API_RAW / 'jito_public_bundle_events_online.csv', index=False)
    pd.DataFrame(manifest).to_csv(API_RAW / 'jito_public_bundle_fetch_manifest.csv', index=False)
    if write_source_assets:
        bundles.to_csv(SOURCE_ASSETS / 'jito_public_bundles.csv', index=False)
        scores.to_csv(SOURCE_ASSETS / 'jito_public_validator_orderflow_scores.csv', index=False)
        edge.to_csv(SOURCE_ASSETS / 'jito_public_tipper_validator_edges.csv', index=False)
        events_df.to_csv(SOURCE_ASSETS / 'jito_public_bundle_events.csv', index=False)
    return {'source': 'jito_public_bundles', 'bundles': len(bundles), 'validators': len(scores), 'edges': len(edge), 'events': len(events_df), 'wrote_source_assets': write_source_assets}


