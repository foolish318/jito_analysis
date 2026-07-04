from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

import pandas as pd

from api_sources.common import request_json, save_json
from api_sources.providers import helius, solscan

PKG = Path(__file__).resolve().parents[2]
DATA = PKG / 'data'
SOURCE_ASSETS = DATA / 'source_assets'
API_RAW = DATA / 'api_raw'

def sample_tipper_addresses(limit: int) -> list[str]:
    edges = SOURCE_ASSETS / 'jito_public_tipper_validator_edges.csv'
    if not edges.exists():
        return []
    df = pd.read_csv(edges)
    if 'tipper' not in df.columns:
        return []
    if 'total_tip_SOL' in df.columns:
        df = df.sort_values('total_tip_SOL', ascending=False)
    return df['tipper'].dropna().astype(str).drop_duplicates().head(limit).tolist()


def fetch_helius_addresses(limit: int) -> dict[str, Any]:
    key = os.environ.get('HELIUS_API_KEY')
    if not key:
        return {'source': 'helius_address_history', 'skipped': True, 'reason': 'HELIUS_API_KEY not set'}
    raw_dir = API_RAW / 'helius_address_history'
    raw_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    manifest = []
    for address in sample_tipper_addresses(limit):
        url = helius.address_transactions(address, key, limit=100)
        meta, obj = request_json(url, timeout=90)
        manifest.append({**meta, 'address': address})
        save_json(raw_dir / f'{address}.json', obj)
        if isinstance(obj, list):
            for tx in obj:
                if isinstance(tx, dict):
                    rows.append({'queried_address': address, 'signature': tx.get('signature'), 'slot': tx.get('slot'), 'timestamp': tx.get('timestamp'), 'feePayer': tx.get('feePayer'), 'type': tx.get('type'), 'source': tx.get('source'), 'fee': tx.get('fee'), 'instruction_count': len(tx.get('instructions') or [])})
        time.sleep(0.12)
    tx = pd.DataFrame(rows)
    tx.to_csv(API_RAW / 'helius_address_history_online.csv', index=False)
    pd.DataFrame(manifest).to_csv(API_RAW / 'helius_address_history_manifest.csv', index=False)
    return {'source': 'helius_address_history', 'addresses': len(manifest), 'rows': len(tx), 'skipped': False}


def fetch_solscan_accounts(limit: int) -> dict[str, Any]:
    key = os.environ.get('SOLSCAN_API_KEY')
    if not key:
        return {'source': 'solscan_accounts', 'skipped': True, 'reason': 'SOLSCAN_API_KEY not set'}
    raw_dir = API_RAW / 'solscan_accounts'
    raw_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    manifest = []
    headers = {'token': key}
    for address in sample_tipper_addresses(limit):
        url = solscan.account_detail(address)
        meta, obj = request_json(url, headers=headers, timeout=45)
        manifest.append({**meta, 'address': address})
        save_json(raw_dir / f'{address}.json', obj)
        data = obj.get('data') if isinstance(obj, dict) else None
        rows.append({'address': address, 'success': isinstance(data, dict), 'account_type': data.get('account_type') if isinstance(data, dict) else None, 'account_label': data.get('account_label') if isinstance(data, dict) else None})
        time.sleep(0.15)
    pd.DataFrame(rows).to_csv(API_RAW / 'solscan_account_detail_online.csv', index=False)
    pd.DataFrame(manifest).to_csv(API_RAW / 'solscan_account_manifest.csv', index=False)
    return {'source': 'solscan_accounts', 'addresses': len(rows), 'skipped': False}


