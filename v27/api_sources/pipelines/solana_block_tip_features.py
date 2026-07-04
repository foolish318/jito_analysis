from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from api_sources.common import request_json, save_json, solana_rpc_request, utc_now
from api_sources.providers import jito, solana_rpc as solana_provider
from api_sources.parsers.solana_block import (
    aggregate_solana_features,
    aggregate_tip_features,
    block_params,
    block_transactions,
    extract_tip_accounts,
    parse_solana_feature,
    parse_tip_feature,
)

SOLANA_RPC_URL_DEFAULT = solana_provider.DEFAULT_RPC_URL
JITO_TIP_ACCOUNTS_URL = jito.get_tip_accounts()

def solana_rpc(method: str, params: list[Any] | None = None, timeout: int = 90) -> tuple[dict[str, Any], Any | None]:
    rpc_url = os.environ.get('SOLANA_RPC_URL', SOLANA_RPC_URL_DEFAULT)
    return solana_rpc_request(
        rpc_url,
        method,
        params,
        timeout=timeout,
        user_agent='jito-analysis-v27-v18-online/1.0',
    )

def fetch_tip_accounts(raw_dir: Path) -> tuple[list[str], pd.DataFrame]:
    manifest: list[dict[str, Any]] = []
    body = {'jsonrpc': '2.0', 'id': 1, 'method': 'getTipAccounts', 'params': []}
    meta, obj = request_json(JITO_TIP_ACCOUNTS_URL, method='POST', body=body, timeout=45)
    manifest.append({**meta, 'attempt': 'post_jsonrpc'})
    accounts = extract_tip_accounts(obj)
    save_json(raw_dir / 'jito_tip_accounts_post.json', obj)
    if not accounts:
        meta2, obj2 = request_json(JITO_TIP_ACCOUNTS_URL, method='GET', timeout=45)
        manifest.append({**meta2, 'attempt': 'get'})
        accounts = extract_tip_accounts(obj2)
        save_json(raw_dir / 'jito_tip_accounts_get.json', obj2)
    pd.DataFrame({'tip_account': accounts}).to_csv(raw_dir / 'jito_tip_accounts.csv', index=False)
    man = pd.DataFrame(manifest)
    man.to_csv(raw_dir / 'jito_tip_accounts_manifest.csv', index=False)
    return accounts, man

def read_manifest(source_assets: Path, manifest_name: str, snapshot_name: str, keep_cols: list[str]) -> pd.DataFrame:
    manifest = source_assets / manifest_name
    if manifest.exists():
        return pd.read_csv(manifest)
    snapshot = source_assets / snapshot_name
    if snapshot.exists():
        df = pd.read_csv(snapshot)
        return df[[c for c in keep_cols if c in df.columns]].drop_duplicates()
    return pd.DataFrame(columns=keep_cols)

def fetch_blocks_for_slots(raw_dir: Path, slot_rows: pd.DataFrame, limit: int) -> tuple[dict[int, Any], pd.DataFrame]:
    block_cache: dict[int, Any] = {}
    manifest: list[dict[str, Any]] = []
    selected = slot_rows.dropna(subset=['slot']).copy()
    selected['slot'] = pd.to_numeric(selected['slot'], errors='coerce')
    selected = selected.dropna(subset=['slot']).drop_duplicates('slot').head(limit)
    for _, row in selected.iterrows():
        slot = int(row['slot'])
        meta, obj = solana_rpc('getBlock', block_params(slot), timeout=120)
        result, txs = block_transactions(obj)
        block_cache[slot] = obj
        save_json(raw_dir / 'blocks' / f'slot_{slot}.json', obj)
        manifest.append({**meta, 'slot': slot, 'leader': row.get('leader'), 'block_available': result is not None, 'tx_count': len(txs), 'error_obj': json.dumps(obj.get('error'), default=str)[:300] if isinstance(obj, dict) and obj.get('error') else ''})
        time.sleep(0.08)
    man = pd.DataFrame(manifest)
    man.to_csv(raw_dir / 'solana_getblock_rpc_manifest.csv', index=False)
    return block_cache, man

def fetch_solana_block_tip_features(run_dir: Path, source_assets: Path, getblock_limit: int, tip_limit: int) -> dict[str, Any]:
    raw_dir = run_dir / 'api_raw' / 'solana_block_tip_features'
    raw_dir.mkdir(parents=True, exist_ok=True)
    sol_manifest = read_manifest(
        source_assets,
        'solana_block_slot_manifest.csv',
        'solana_block_features_snapshot.csv',
        ['slot', 'leader', 'target_rank', 'candidate_indicator', 'target_v16_detail_total_cu', 'target_v16_detail_maker_plugin_share_nonvote'],
    )
    tip_manifest = read_manifest(
        source_assets,
        'jito_tip_account_slot_manifest.csv',
        'jito_tip_account_flow_features_snapshot.csv',
        ['slot', 'leader', 'target_rank', 'candidate_indicator'],
    )
    sol_manifest.to_csv(raw_dir / 'solana_block_slot_manifest_used.csv', index=False)
    tip_manifest.to_csv(raw_dir / 'jito_tip_account_slot_manifest_used.csv', index=False)

    sol_blocks, sol_fetch = fetch_blocks_for_slots(raw_dir / 'solana_getblock', sol_manifest, getblock_limit) if getblock_limit > 0 else ({}, pd.DataFrame())
    sol_rows = []
    for _, row in sol_manifest.dropna(subset=['slot']).head(getblock_limit).iterrows():
        slot = int(row['slot'])
        sol_rows.append(parse_solana_feature(row, sol_blocks.get(slot)))
    sol_slot = pd.DataFrame(sol_rows)
    sol_proxy = aggregate_solana_features(sol_slot)
    sol_slot.to_csv(raw_dir / 'solana_block_features_online.csv', index=False)
    sol_proxy.to_csv(raw_dir / 'solana_block_validator_proxy_online.csv', index=False)
    pd.DataFrame([{
        'target_slots': len(sol_manifest),
        'requested_slots': min(len(sol_manifest), getblock_limit),
        'available_blocks': int(sol_slot.get('solana_block_available', pd.Series(dtype=bool)).fillna(False).sum()) if not sol_slot.empty else 0,
        'error_blocks': int((~sol_slot.get('solana_block_available', pd.Series(dtype=bool)).fillna(False)).sum()) if not sol_slot.empty else 0,
        'generated_at': utc_now(),
    }]).to_csv(raw_dir / 'solana_block_fetch_audit_online.csv', index=False)

    tip_accounts, tip_account_manifest = fetch_tip_accounts(raw_dir)
    tip_selected = tip_manifest.dropna(subset=['slot']).head(tip_limit).copy()
    need_tip_slots = tip_selected[~tip_selected['slot'].astype(int).isin(sol_blocks.keys())] if not tip_selected.empty else pd.DataFrame()
    tip_blocks_extra, tip_fetch_extra = fetch_blocks_for_slots(raw_dir / 'tip_getblock', need_tip_slots, len(need_tip_slots)) if tip_limit > 0 and not need_tip_slots.empty else ({}, pd.DataFrame())
    block_cache = {**sol_blocks, **tip_blocks_extra}
    tip_rows = []
    tip_account_set = set(tip_accounts)
    for _, row in tip_selected.iterrows():
        slot = int(row['slot'])
        tip_rows.append(parse_tip_feature(row, block_cache.get(slot), tip_account_set))
    tip_slot = pd.DataFrame(tip_rows)
    tip_proxy = aggregate_tip_features(tip_slot)
    tip_slot.to_csv(raw_dir / 'jito_tip_account_flow_features_online.csv', index=False)
    tip_proxy.to_csv(raw_dir / 'jito_tip_account_validator_proxy_online.csv', index=False)
    pd.DataFrame([{
        'tip_accounts': len(tip_accounts),
        'target_slots_rank_lt': len(tip_manifest),
        'requested_slots': min(len(tip_manifest), tip_limit),
        'available_blocks': int(tip_slot.get('tip_block_available', pd.Series(dtype=bool)).fillna(False).sum()) if not tip_slot.empty else 0,
        'blocks_with_positive_tip': int((pd.to_numeric(tip_slot.get('tip_total_lamports', pd.Series(dtype=float)), errors='coerce').fillna(0) > 0).sum()) if not tip_slot.empty else 0,
        'generated_at': utc_now(),
    }]).to_csv(raw_dir / 'jito_tip_account_fetch_audit_online.csv', index=False)

    fetch_manifest = pd.concat([sol_fetch, tip_fetch_extra], ignore_index=True) if not sol_fetch.empty or not tip_fetch_extra.empty else pd.DataFrame()
    fetch_manifest.to_csv(raw_dir / 'solana_block_tip_fetch_manifest.csv', index=False)
    return {
        'source': 'v18_solana_getblock_tip_accounts',
        'getblock_target_slots': int(len(sol_manifest)),
        'getblock_requested_slots': int(min(len(sol_manifest), getblock_limit)),
        'getblock_available_blocks': int(sol_slot.get('solana_block_available', pd.Series(dtype=bool)).fillna(False).sum()) if not sol_slot.empty else 0,
        'getblock_validator_rows': int(len(sol_proxy)),
        'tip_target_slots': int(len(tip_manifest)),
        'tip_requested_slots': int(min(len(tip_manifest), tip_limit)),
        'tip_accounts': int(len(tip_accounts)),
        'tip_available_blocks': int(tip_slot.get('tip_block_available', pd.Series(dtype=bool)).fillna(False).sum()) if not tip_slot.empty else 0,
        'tip_positive_blocks': int((pd.to_numeric(tip_slot.get('tip_total_lamports', pd.Series(dtype=float)), errors='coerce').fillna(0) > 0).sum()) if not tip_slot.empty else 0,
        'tip_validator_rows': int(len(tip_proxy)),
        'raw_dir': str(raw_dir),
    }
