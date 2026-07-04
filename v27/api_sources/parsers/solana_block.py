from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

LAMPORTS_PER_SOL = 1_000_000_000
COMPUTE_BUDGET_PROGRAM = 'ComputeBudget111111111111111111111111111111'
SYSTEM_PROGRAM = '11111111111111111111111111111111'
TOKEN_PROGRAMS = {'TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA', 'TokenzQdBNbLqP5VEhdkAS6EPFhFvXfJxNoeWmK4rH'}

def hhi(values: list[float]) -> float:
    vals = [float(x) for x in values if pd.notna(x) and float(x) > 0]
    total = sum(vals)
    if total <= 0:
        return np.nan
    return float(sum((x / total) ** 2 for x in vals))

def pubkey(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ['pubkey', 'account', 'address']:
            if value.get(key):
                return str(value.get(key))
    return None

def tx_account_keys(tx_wrap: dict[str, Any]) -> list[str]:
    tx = tx_wrap.get('transaction') or {}
    message = tx.get('message') or {}
    raw_keys = message.get('accountKeys') or []
    return [k for k in (pubkey(x) for x in raw_keys) if k]

def tx_program_ids(tx_wrap: dict[str, Any]) -> list[str]:
    tx = tx_wrap.get('transaction') or {}
    message = tx.get('message') or {}
    out: list[str] = []
    for ix in message.get('instructions') or []:
        if isinstance(ix, dict):
            out.append(str(ix.get('programId') or ix.get('program') or ix.get('programIdIndex') or ''))
    meta = tx_wrap.get('meta') or {}
    for group in meta.get('innerInstructions') or []:
        if not isinstance(group, dict):
            continue
        for ix in group.get('instructions') or []:
            if isinstance(ix, dict):
                out.append(str(ix.get('programId') or ix.get('program') or ix.get('programIdIndex') or ''))
    return [x for x in out if x and x != 'None']

def is_jupiter(program_id: str) -> bool:
    p = program_id.lower()
    return p.startswith('jup') or 'jupiter' in p

def is_token(program_id: str) -> bool:
    return program_id in TOKEN_PROGRAMS or 'token' in program_id.lower()

def is_system(program_id: str) -> bool:
    return program_id == SYSTEM_PROGRAM or program_id.lower() == 'system'

def block_transactions(block_obj: Any) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    if not isinstance(block_obj, dict):
        return None, []
    result = block_obj.get('result') if 'result' in block_obj else block_obj
    if not isinstance(result, dict):
        return None, []
    txs = result.get('transactions') or []
    return result, [tx for tx in txs if isinstance(tx, dict)]

def block_params(slot: int) -> list[Any]:
    return [
        int(slot),
        {
            'encoding': 'jsonParsed',
            'transactionDetails': 'full',
            'rewards': False,
            'maxSupportedTransactionVersion': 0,
            'commitment': 'finalized',
        },
    ]

def parse_solana_feature(row: pd.Series, block_obj: Any) -> dict[str, Any]:
    slot = int(row['slot'])
    leader = row.get('leader')
    result, txs = block_transactions(block_obj)
    rec: dict[str, Any] = {
        'slot': slot,
        'leader': leader,
        'solana_block_available': result is not None,
        'block_time': result.get('blockTime') if result else np.nan,
        'block_height': result.get('blockHeight') if result else np.nan,
        'parent_slot': result.get('parentSlot') if result else np.nan,
    }
    for col in ['target_rank', 'candidate_indicator', 'target_v16_detail_total_cu', 'target_v16_detail_maker_plugin_share_nonvote']:
        if col in row.index:
            rec[col] = row.get(col)
    if result is None:
        empty_cols = [
            'solana_tx_count', 'solana_failed_tx_count', 'solana_failed_tx_share', 'solana_total_fee_lamports',
            'solana_avg_fee_lamports', 'solana_p95_fee_lamports', 'solana_total_base_fee_lamports',
            'solana_total_priority_fee_proxy_lamports', 'solana_avg_priority_fee_proxy_lamports',
            'solana_p95_priority_fee_proxy_lamports', 'solana_priority_fee_proxy_share',
            'solana_positive_priority_fee_tx_share', 'solana_total_compute_units', 'solana_avg_compute_units',
            'solana_p95_compute_units', 'solana_compute_units_per_tx', 'solana_compute_budget_tx_share',
            'solana_compute_budget_ix_per_tx', 'solana_jupiter_tx_share', 'solana_token_tx_share',
            'solana_system_tx_share', 'solana_jupiter_ix_share', 'solana_token_ix_share', 'solana_system_ix_share',
            'solana_unique_fee_payers', 'solana_fee_payer_unique_ratio', 'solana_fee_payer_tx_hhi',
            'solana_fee_payer_fee_hhi', 'solana_fee_payer_priority_fee_hhi', 'solana_unique_programs',
            'solana_top_program_share', 'solana_program_hhi', 'solana_total_instruction_count', 'solana_instruction_per_tx',
        ]
        for col in empty_cols:
            rec[col] = np.nan
        rec['fetch_source'] = 'online_rpc_missing'
        return rec

    fees: list[float] = []
    base_fees: list[float] = []
    priority_fees: list[float] = []
    compute_units: list[float] = []
    fee_payers: list[str] = []
    fee_by_payer: dict[str, float] = {}
    prio_by_payer: dict[str, float] = {}
    tx_by_payer: dict[str, float] = {}
    program_counts: dict[str, float] = {}
    failed = 0
    cb_tx = 0
    cb_ix = 0
    jup_tx = 0
    token_tx = 0
    system_tx = 0
    jup_ix = 0
    token_ix = 0
    system_ix = 0
    total_ix = 0

    for tx_wrap in txs:
        meta = tx_wrap.get('meta') or {}
        tx = tx_wrap.get('transaction') or {}
        sigs = tx.get('signatures') or []
        fee = pd.to_numeric(meta.get('fee'), errors='coerce')
        if pd.isna(fee):
            fee = 0.0
        sig_count = len(sigs) if isinstance(sigs, list) and sigs else 1
        base_fee = 5000.0 * sig_count
        priority_fee = max(float(fee) - base_fee, 0.0)
        fees.append(float(fee))
        base_fees.append(base_fee)
        priority_fees.append(priority_fee)
        cu = pd.to_numeric(meta.get('computeUnitsConsumed'), errors='coerce')
        if pd.notna(cu):
            compute_units.append(float(cu))
        if meta.get('err') is not None:
            failed += 1
        keys = tx_account_keys(tx_wrap)
        payer = keys[0] if keys else None
        if payer:
            fee_payers.append(payer)
            tx_by_payer[payer] = tx_by_payer.get(payer, 0.0) + 1.0
            fee_by_payer[payer] = fee_by_payer.get(payer, 0.0) + float(fee)
            prio_by_payer[payer] = prio_by_payer.get(payer, 0.0) + priority_fee
        programs = tx_program_ids(tx_wrap)
        total_ix += len(programs)
        seen = set(programs)
        if any(p == COMPUTE_BUDGET_PROGRAM or 'computebudget' in p.lower() for p in programs):
            cb_tx += 1
        cb_ix += sum(1 for p in programs if p == COMPUTE_BUDGET_PROGRAM or 'computebudget' in p.lower())
        if any(is_jupiter(p) for p in seen):
            jup_tx += 1
        if any(is_token(p) for p in seen):
            token_tx += 1
        if any(is_system(p) for p in seen):
            system_tx += 1
        for p in programs:
            program_counts[p] = program_counts.get(p, 0.0) + 1.0
            if is_jupiter(p):
                jup_ix += 1
            if is_token(p):
                token_ix += 1
            if is_system(p):
                system_ix += 1

    n = len(txs)
    total_fee = float(sum(fees))
    total_priority = float(sum(priority_fees))
    total_cu = float(sum(compute_units)) if compute_units else np.nan
    rec.update({
        'solana_tx_count': n,
        'solana_failed_tx_count': failed,
        'solana_failed_tx_share': failed / n if n else np.nan,
        'solana_total_fee_lamports': total_fee,
        'solana_avg_fee_lamports': float(np.mean(fees)) if fees else np.nan,
        'solana_p95_fee_lamports': float(np.percentile(fees, 95)) if fees else np.nan,
        'solana_total_base_fee_lamports': float(sum(base_fees)),
        'solana_total_priority_fee_proxy_lamports': total_priority,
        'solana_avg_priority_fee_proxy_lamports': float(np.mean(priority_fees)) if priority_fees else np.nan,
        'solana_p95_priority_fee_proxy_lamports': float(np.percentile(priority_fees, 95)) if priority_fees else np.nan,
        'solana_priority_fee_proxy_share': total_priority / total_fee if total_fee else np.nan,
        'solana_positive_priority_fee_tx_share': sum(x > 0 for x in priority_fees) / n if n else np.nan,
        'solana_total_compute_units': total_cu,
        'solana_avg_compute_units': float(np.mean(compute_units)) if compute_units else np.nan,
        'solana_p95_compute_units': float(np.percentile(compute_units, 95)) if compute_units else np.nan,
        'solana_compute_units_per_tx': total_cu / n if n and pd.notna(total_cu) else np.nan,
        'solana_compute_budget_tx_share': cb_tx / n if n else np.nan,
        'solana_compute_budget_ix_per_tx': cb_ix / n if n else np.nan,
        'solana_jupiter_tx_share': jup_tx / n if n else np.nan,
        'solana_token_tx_share': token_tx / n if n else np.nan,
        'solana_system_tx_share': system_tx / n if n else np.nan,
        'solana_jupiter_ix_share': jup_ix / total_ix if total_ix else np.nan,
        'solana_token_ix_share': token_ix / total_ix if total_ix else np.nan,
        'solana_system_ix_share': system_ix / total_ix if total_ix else np.nan,
        'solana_unique_fee_payers': len(set(fee_payers)),
        'solana_fee_payer_unique_ratio': len(set(fee_payers)) / n if n else np.nan,
        'solana_fee_payer_tx_hhi': hhi(list(tx_by_payer.values())),
        'solana_fee_payer_fee_hhi': hhi(list(fee_by_payer.values())),
        'solana_fee_payer_priority_fee_hhi': hhi(list(prio_by_payer.values())),
        'solana_unique_programs': len(program_counts),
        'solana_top_program_share': max(program_counts.values()) / total_ix if total_ix and program_counts else np.nan,
        'solana_program_hhi': hhi(list(program_counts.values())),
        'solana_total_instruction_count': total_ix,
        'solana_instruction_per_tx': total_ix / n if n else np.nan,
        'fetch_source': 'online_rpc',
    })
    return rec

def extract_tip_accounts(obj: Any) -> list[str]:
    if isinstance(obj, list):
        return [str(x) for x in obj if x]
    if not isinstance(obj, dict):
        return []
    result = obj.get('result') if 'result' in obj else obj
    if isinstance(result, list):
        return [str(x) for x in result if x]
    if isinstance(result, dict):
        for key in ['tipAccounts', 'tip_accounts', 'accounts']:
            val = result.get(key)
            if isinstance(val, list):
                return [str(x) for x in val if x]
    for key in ['tipAccounts', 'tip_accounts', 'accounts']:
        val = obj.get(key)
        if isinstance(val, list):
            return [str(x) for x in val if x]
    return []

def parse_tip_feature(row: pd.Series, block_obj: Any, tip_accounts: set[str]) -> dict[str, Any]:
    slot = int(row['slot'])
    leader = row.get('leader')
    result, txs = block_transactions(block_obj)
    rec: dict[str, Any] = {'slot': slot, 'leader': leader, 'tip_block_available': result is not None}
    for col in ['target_rank', 'candidate_indicator']:
        if col in row.index:
            rec[col] = row.get(col)
    if result is None:
        for col in ['tip_tx_count', 'tip_tx_share', 'tip_positive_event_count', 'tip_total_lamports', 'tip_total_SOL', 'tip_unique_tip_accounts_paid', 'tip_account_hhi', 'tip_top_account_share', 'tip_unique_payers', 'tip_payer_hhi', 'tip_top_payer_share', 'tip_lamports_per_tip_tx']:
            rec[col] = np.nan
        return rec
    account_amounts: dict[str, float] = {}
    payer_amounts: dict[str, float] = {}
    positive_events = 0
    tip_tx_count = 0
    for tx_wrap in txs:
        meta = tx_wrap.get('meta') or {}
        keys = tx_account_keys(tx_wrap)
        if not keys:
            continue
        payer = keys[0]
        pre = meta.get('preBalances') or []
        post = meta.get('postBalances') or []
        tx_tip = 0.0
        for i, key in enumerate(keys[: min(len(pre), len(post))]):
            if key not in tip_accounts:
                continue
            delta = float(post[i]) - float(pre[i])
            if delta <= 0:
                continue
            account_amounts[key] = account_amounts.get(key, 0.0) + delta
            payer_amounts[payer] = payer_amounts.get(payer, 0.0) + delta
            positive_events += 1
            tx_tip += delta
        if tx_tip > 0:
            tip_tx_count += 1
    total_lamports = float(sum(account_amounts.values()))
    n = len(txs)
    rec.update({
        'tip_tx_count': tip_tx_count,
        'tip_tx_share': tip_tx_count / n if n else np.nan,
        'tip_positive_event_count': positive_events,
        'tip_total_lamports': total_lamports,
        'tip_total_SOL': total_lamports / LAMPORTS_PER_SOL,
        'tip_unique_tip_accounts_paid': len(account_amounts),
        'tip_account_hhi': hhi(list(account_amounts.values())),
        'tip_top_account_share': max(account_amounts.values()) / total_lamports if total_lamports and account_amounts else np.nan,
        'tip_unique_payers': len(payer_amounts),
        'tip_payer_hhi': hhi(list(payer_amounts.values())),
        'tip_top_payer_share': max(payer_amounts.values()) / total_lamports if total_lamports and payer_amounts else np.nan,
        'tip_lamports_per_tip_tx': total_lamports / tip_tx_count if tip_tx_count else np.nan,
    })
    return rec

def aggregate_solana_features(slot_df: pd.DataFrame) -> pd.DataFrame:
    if slot_df.empty or 'leader' not in slot_df.columns:
        return pd.DataFrame()
    df = slot_df[slot_df.get('solana_block_available', False).astype(bool)].copy()
    if df.empty:
        return pd.DataFrame()
    g = df.groupby('leader', dropna=False)
    out = g.agg(
        tx_blocks=('slot', 'nunique'),
        tx_avg_tx_count=('solana_tx_count', 'mean'),
        tx_avg_failed_tx_share=('solana_failed_tx_share', 'mean'),
        tx_max_failed_tx_share=('solana_failed_tx_share', 'max'),
        tx_avg_fee_lamports=('solana_avg_fee_lamports', 'mean'),
        tx_p95_fee_lamports=('solana_p95_fee_lamports', 'mean'),
        tx_avg_priority_fee_proxy_lamports=('solana_avg_priority_fee_proxy_lamports', 'mean'),
        tx_p95_priority_fee_proxy_lamports=('solana_p95_priority_fee_proxy_lamports', 'mean'),
        tx_priority_fee_proxy_share=('solana_priority_fee_proxy_share', 'mean'),
        tx_positive_priority_fee_tx_share=('solana_positive_priority_fee_tx_share', 'mean'),
        tx_avg_compute_units=('solana_avg_compute_units', 'mean'),
        tx_p95_compute_units=('solana_p95_compute_units', 'mean'),
        tx_compute_units_per_tx=('solana_compute_units_per_tx', 'mean'),
        tx_compute_budget_tx_share=('solana_compute_budget_tx_share', 'mean'),
        tx_compute_budget_ix_per_tx=('solana_compute_budget_ix_per_tx', 'mean'),
        tx_jupiter_tx_share=('solana_jupiter_tx_share', 'mean'),
        tx_token_tx_share=('solana_token_tx_share', 'mean'),
        tx_system_tx_share=('solana_system_tx_share', 'mean'),
        tx_jupiter_ix_share=('solana_jupiter_ix_share', 'mean'),
        tx_token_ix_share=('solana_token_ix_share', 'mean'),
        tx_system_ix_share=('solana_system_ix_share', 'mean'),
        tx_fee_payer_unique_ratio=('solana_fee_payer_unique_ratio', 'mean'),
        tx_fee_payer_tx_hhi=('solana_fee_payer_tx_hhi', 'mean'),
        tx_fee_payer_fee_hhi=('solana_fee_payer_fee_hhi', 'mean'),
        tx_fee_payer_priority_fee_hhi=('solana_fee_payer_priority_fee_hhi', 'mean'),
        tx_unique_programs=('solana_unique_programs', 'mean'),
        tx_top_program_share=('solana_top_program_share', 'mean'),
        tx_program_hhi=('solana_program_hhi', 'mean'),
        tx_instruction_per_tx=('solana_instruction_per_tx', 'mean'),
    ).reset_index()
    out['tx_log_avg_priority_fee_proxy'] = np.log1p(out['tx_avg_priority_fee_proxy_lamports'].clip(lower=0))
    out['tx_log_p95_priority_fee_proxy'] = np.log1p(out['tx_p95_priority_fee_proxy_lamports'].clip(lower=0))
    out['tx_log_avg_fee'] = np.log1p(out['tx_avg_fee_lamports'].clip(lower=0))
    return out

def aggregate_tip_features(slot_df: pd.DataFrame) -> pd.DataFrame:
    if slot_df.empty or 'leader' not in slot_df.columns:
        return pd.DataFrame()
    df = slot_df[slot_df.get('tip_block_available', False).astype(bool)].copy()
    if df.empty:
        return pd.DataFrame()
    g = df.groupby('leader', dropna=False)
    out = g.agg(
        tip_blocks=('slot', 'nunique'),
        tip_avg_tx_share=('tip_tx_share', 'mean'),
        tip_total_SOL_sample=('tip_total_SOL', 'sum'),
        tip_avg_total_SOL=('tip_total_SOL', 'mean'),
        tip_max_total_SOL=('tip_total_SOL', 'max'),
        tip_avg_unique_payers=('tip_unique_payers', 'mean'),
        tip_avg_payer_hhi=('tip_payer_hhi', 'mean'),
        tip_max_payer_hhi=('tip_payer_hhi', 'max'),
        tip_avg_top_payer_share=('tip_top_payer_share', 'mean'),
        tip_max_top_payer_share=('tip_top_payer_share', 'max'),
        tip_avg_unique_tip_accounts_paid=('tip_unique_tip_accounts_paid', 'mean'),
        tip_avg_account_hhi=('tip_account_hhi', 'mean'),
        tip_avg_lamports_per_tip_tx=('tip_lamports_per_tip_tx', 'mean'),
    ).reset_index()
    out['tip_log_total_SOL_sample'] = np.log1p(out['tip_total_SOL_sample'].clip(lower=0))
    out['tip_log_avg_total_SOL'] = np.log1p(out['tip_avg_total_SOL'].clip(lower=0))
    out['tip_log_avg_lamports_per_tip_tx'] = np.log1p(out['tip_avg_lamports_per_tip_tx'].clip(lower=0))
    return out
