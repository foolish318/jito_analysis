from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from api_sources.common import utc_now

PKG = Path(__file__).resolve().parents[2]
DATA = PKG / 'data'
SOURCE_ASSETS = DATA / 'source_assets'
API_RAW = DATA / 'api_raw'
DATA_FILE_SUFFIXES = {'.csv', '.json', '.parquet', '.xlsx'}
API_RAW.mkdir(parents=True, exist_ok=True)


def validate_local_snapshots() -> dict[str, Any]:
    files = sorted(SOURCE_ASSETS.glob('*'))
    rows = [
        {'file': f.name, 'size_bytes': f.stat().st_size}
        for f in files
        if f.is_file() and f.suffix.lower() in DATA_FILE_SUFFIXES
    ]
    pd.DataFrame(rows).to_csv(API_RAW / 'local_snapshot_inventory.csv', index=False)
    return {'source': 'local_snapshots', 'files': len(rows), 'skipped': False}


def run() -> dict[str, Any]:
    result = validate_local_snapshots()
    summary = {'finished_at': utc_now(), 'online': False, 'write_source_assets': False, 'results': [result]}
    (API_RAW / 'fetch_api_data_summary.json').write_text(json.dumps(summary, indent=2, sort_keys=True), encoding='utf-8')
    print(json.dumps(summary, indent=2, sort_keys=True))
    return summary


if __name__ == '__main__':
    run()
