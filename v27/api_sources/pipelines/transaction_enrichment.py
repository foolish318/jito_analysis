from __future__ import annotations

import ast
import os
import time
from pathlib import Path
from typing import Any

import pandas as pd

from api_sources.common import request_json, save_json
from api_sources.providers import dune, helius


def signatures_from_source(source_assets: Path, limit: int) -> list[str]:
    path = source_assets / 'jito_public_bundles.csv'
    if not path.exists():
        return []
    try:
        df = pd.read_csv(path, usecols=['txSignatures'])
    except Exception:
        return []
    sigs: list[str] = []
    for raw in df['txSignatures'].dropna().astype(str):
        try:
            parsed = ast.literal_eval(raw)
        except Exception:
            continue
        if isinstance(parsed, list):
            sigs.extend(str(x) for x in parsed if x)
        if len(sigs) >= limit:
            break
    return list(dict.fromkeys(sigs))[:limit]


def fetch_helius_enhanced(run_dir: Path, source_assets: Path, limit: int) -> dict[str, Any]:
    key = os.environ.get('HELIUS_API_KEY')
    if not key:
        return {'source': 'helius_enhanced_transactions', 'skipped': True, 'reason': 'HELIUS_API_KEY not set'}
    raw = run_dir / 'api_raw' / 'helius_enhanced'
    raw.mkdir(parents=True, exist_ok=True)
    sigs = signatures_from_source(source_assets, limit)
    if not sigs:
        return {'source': 'helius_enhanced_transactions', 'skipped': True, 'reason': 'no bundle signatures'}
    meta, obj = request_json(
        helius.enhanced_transactions(key),
        method='POST',
        body={'transactions': sigs},
        timeout=90,
        user_agent='jito-analysis-v27-helius-online/1.0',
    )
    save_json(raw / 'helius_enhanced_transactions.json', obj)
    rows = []
    if isinstance(obj, list):
        for row in obj:
            if not isinstance(row, dict):
                continue
            events = row.get('events') or {}
            rows.append({
                'signature': row.get('signature'),
                'slot': row.get('slot'),
                'timestamp': row.get('timestamp'),
                'fee': row.get('fee'),
                'feePayer': row.get('feePayer'),
                'type': row.get('type'),
                'source': row.get('source'),
                'instruction_count': len(row.get('instructions') or []),
                'has_swap_event': bool(events.get('swap')) if isinstance(events, dict) else False,
            })
    pd.DataFrame(rows).to_csv(raw / 'helius_enhanced_transactions.csv', index=False)
    pd.DataFrame([{**meta, 'requested_signatures': len(sigs), 'rows': len(rows)}]).to_csv(raw / 'helius_enhanced_manifest.csv', index=False)
    return {
        'source': 'helius_enhanced_transactions',
        'requested_signatures': len(sigs),
        'rows': len(rows),
        'skipped': False,
        'raw_dir': str(raw),
    }


def fetch_dune_direct_samples(run_dir: Path, max_wait: int) -> dict[str, Any]:
    key = os.environ.get('DUNE_API_KEY')
    if not key:
        return {'source': 'dune_direct_samples', 'skipped': True, 'reason': 'DUNE_API_KEY not set'}
    raw = run_dir / 'api_raw' / 'dune'
    raw.mkdir(parents=True, exist_ok=True)
    headers = {'X-Dune-Api-Key': key}
    queries = {
        'transactions_sample': 'SELECT block_time, id, fee, success FROM solana.transactions LIMIT 10',
        'blocks_sample': 'SELECT slot, time, total_transactions, failed_transactions FROM solana.blocks LIMIT 10',
        'instruction_calls_sample': 'SELECT tx_id, executing_account, is_inner FROM solana.instruction_calls LIMIT 10',
    }
    manifest = []
    for name, sql in queries.items():
        meta, obj = request_json(
            dune.sql_execute(),
            method='POST',
            body={'sql': sql, 'performance': 'small'},
            headers=headers,
            timeout=60,
            user_agent='jito-analysis-v27-dune-online/1.0',
        )
        rec = {**meta, 'query': name, 'rows': 0, 'state': None}
        raw_obj = obj
        rows = []
        execution_id = obj.get('execution_id') if isinstance(obj, dict) else None
        if execution_id:
            started = time.time()
            while time.time() - started < max_wait:
                meta2, result = request_json(
                    dune.execution_results(execution_id, limit=1000),
                    headers=headers,
                    timeout=60,
                    user_agent='jito-analysis-v27-dune-online/1.0',
                )
                raw_obj = result
                if isinstance(result, dict):
                    rec['state'] = result.get('state')
                    rec['result_status_code'] = meta2.get('status_code')
                    rows = ((result.get('result') or {}).get('rows') or []) if isinstance(result.get('result'), dict) else []
                    if rec['state'] in {'QUERY_STATE_COMPLETED', 'QUERY_STATE_FAILED', 'QUERY_STATE_CANCELLED', 'QUERY_STATE_EXPIRED'}:
                        break
                time.sleep(2)
        rec['rows'] = len(rows)
        manifest.append(rec)
        save_json(raw / f'{name}.json', raw_obj)
        pd.DataFrame(rows).to_csv(raw / f'{name}.csv', index=False)
    pd.DataFrame(manifest).to_csv(raw / 'dune_manifest.csv', index=False)
    return {
        'source': 'dune_direct_samples',
        'queries': len(manifest),
        'completed': int(sum(r.get('state') == 'QUERY_STATE_COMPLETED' for r in manifest)),
        'rows': int(sum(r.get('rows', 0) for r in manifest)),
        'skipped': False,
        'raw_dir': str(raw),
    }
