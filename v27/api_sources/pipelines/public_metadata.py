from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from api_sources.common import object_rows, request_json, save_json, solana_rpc_request
from api_sources.providers import jito, solana_rpc, validator_metadata


def fetch_public_metadata(run_dir: Path) -> dict[str, Any]:
    raw = run_dir / 'api_raw' / 'no_key_metadata'
    raw.mkdir(parents=True, exist_ok=True)
    rpc_url = os.environ.get('SOLANA_RPC_URL', solana_rpc.DEFAULT_RPC_URL)
    rows: list[dict[str, Any]] = []

    def rpc(method: str, params: list[Any] | None = None, timeout: int = 60) -> Any | None:
        meta, obj = solana_rpc_request(
            rpc_url,
            method,
            params,
            timeout=timeout,
            user_agent='jito-analysis-v27-metadata-online/1.0',
        )
        rows.append(meta)
        save_json(raw / f'solana_{method}.json', obj)
        return obj

    cluster = rpc('getClusterNodes')
    vote = rpc('getVoteAccounts', [{'commitment': 'finalized', 'keepUnstakedDelinquents': True}])
    bp = rpc('getBlockProduction', [{'commitment': 'finalized'}])
    rpc('getSlot')
    rpc('getEpochInfo')

    pd.DataFrame(object_rows(cluster.get('result') if isinstance(cluster, dict) else cluster)).to_csv(raw / 'solana_cluster_nodes.csv', index=False)
    if isinstance(vote, dict) and isinstance(vote.get('result'), dict):
        vote_rows = []
        for status in ['current', 'delinquent']:
            for item in vote['result'].get(status, []) or []:
                if isinstance(item, dict):
                    rec = dict(item)
                    rec['vote_status'] = status
                    vote_rows.append(rec)
        pd.DataFrame(vote_rows).to_csv(raw / 'solana_vote_accounts.csv', index=False)
    else:
        pd.DataFrame().to_csv(raw / 'solana_vote_accounts.csv', index=False)

    if isinstance(bp, dict) and isinstance(bp.get('result'), dict):
        value = bp['result'].get('value') if isinstance(bp['result'].get('value'), dict) else {}
        by_identity = value.get('byIdentity', {}) if isinstance(value, dict) else {}
        bp_rows = [
            {
                'identity_account': key,
                'leader_slots_current_epoch': val[0] if isinstance(val, list) and len(val) > 0 else np.nan,
                'blocks_produced_current_epoch': val[1] if isinstance(val, list) and len(val) > 1 else np.nan,
            }
            for key, val in by_identity.items()
        ]
        pd.DataFrame(bp_rows).to_csv(raw / 'solana_block_production.csv', index=False)
    else:
        pd.DataFrame().to_csv(raw / 'solana_block_production.csv', index=False)

    for name, url in [
        ('stakewiz_validators', validator_metadata.stakewiz_validators()),
        ('validators_app_mainnet', validator_metadata.validators_app_mainnet(limit=5000)),
        ('jito_bundles_stats', jito.public_stats()),
        ('jito_tip_floor', jito.public_tip_floor()),
    ]:
        meta, obj = request_json(url, timeout=60, user_agent='jito-analysis-v27-metadata-online/1.0')
        rows.append({**meta, 'source': name, 'rpc_method': ''})
        save_json(raw / f'{name}.json', obj)
        pd.DataFrame(object_rows(obj)).to_csv(raw / f'{name}.csv', index=False)

    pd.DataFrame(rows).to_csv(raw / 'no_key_metadata_manifest.csv', index=False)
    return {
        'source': 'solana_rpc_stakewiz_validators_app',
        'requests': len(rows),
        'ok': int(sum(bool(r.get('ok')) for r in rows)),
        'raw_dir': str(raw),
    }
