from __future__ import annotations

import math
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from api_sources.common import numeric, object_rows, request_json, save_json
from api_sources.providers import bam as bam_provider, jito

PKG = Path(__file__).resolve().parents[2]
DATA = PKG / 'data'
SOURCE_ASSETS = DATA / 'source_assets'
API_RAW = DATA / 'api_raw'
LAMPORTS_PER_SOL = 1_000_000_000

def post_jito_epoch(endpoint: str, epoch: int) -> tuple[dict[str, Any], Any | None]:
    return request_json(jito.kobe_endpoint(endpoint), method='POST', body={'epoch': int(epoch)}, timeout=90, user_agent='jito-analysis-v27-source-online/1.0')


def bool_like(series: pd.Series) -> pd.Series:
    if series.dtype == bool:
        return series.astype(float)
    return series.astype(str).str.lower().isin({'true', '1', 'yes'}).astype(float)


def fetch_jito_epochs(epochs: list[int], write_source_assets: bool) -> dict[str, Any]:
    raw_dir = API_RAW / 'jito_epochs'
    raw_dir.mkdir(parents=True, exist_ok=True)
    validator_frames = []
    bam_frames = []
    mev_rows = []
    manifest = []
    for epoch in epochs:
        meta_mev, mev = post_jito_epoch('mev_rewards', epoch)
        meta_val, validators = post_jito_epoch('validators', epoch)
        meta_bam, bam_obj = request_json(
            bam_provider.ibrl_validators(),
            params={'epoch': int(epoch)},
            timeout=90,
            user_agent='jito-analysis-v27-v25-bam-online/1.0',
        )
        manifest.extend([
            {**meta_mev, 'endpoint': 'mev_rewards', 'epoch': epoch},
            {**meta_val, 'endpoint': 'validators', 'epoch': epoch},
            {**meta_bam, 'endpoint': 'bam_ibrl_validators', 'epoch': epoch},
        ])
        save_json(raw_dir / f'jito_mev_rewards_epoch_{epoch}.json', mev)
        save_json(raw_dir / f'jito_validators_epoch_{epoch}.json', validators)
        save_json(raw_dir / f'bam_ibrl_validators_epoch_{epoch}.json', bam_obj)
        if isinstance(validators, dict):
            rows = validators.get('validators') or validators.get('data') or []
            if isinstance(rows, list):
                df = pd.DataFrame(rows)
                if not df.empty:
                    df['epoch'] = epoch
                    validator_frames.append(df)
        bam_rows = object_rows(bam_obj)
        if bam_rows:
            bam_df = pd.DataFrame(bam_rows)
            if not bam_df.empty:
                bam_df['epoch'] = epoch
                bam_frames.append(bam_df)
        if isinstance(mev, dict):
            row = dict(mev)
            row['epoch'] = epoch
            mev_rows.append(row)
        time.sleep(0.15)
    validators = pd.concat(validator_frames, ignore_index=True) if validator_frames else pd.DataFrame()
    bam_df = pd.concat(bam_frames, ignore_index=True) if bam_frames else pd.DataFrame()
    mev_df = pd.DataFrame(mev_rows)
    if not validators.empty:
        if 'identity_account' not in validators.columns:
            for candidate in ['identity', 'identity_pubkey', 'node_pubkey']:
                if candidate in validators.columns:
                    validators['identity_account'] = validators[candidate]
                    break
        if 'vote_account' not in validators.columns:
            for candidate in ['vote', 'vote_pubkey', 'voteAccount']:
                if candidate in validators.columns:
                    validators['vote_account'] = validators[candidate]
                    break
        for col in [
            'mev_rewards',
            'active_stake',
            'mev_commission_bps',
            'bam_connection_rate',
            'jito_directed_stake_lamports',
        ]:
            if col not in validators.columns:
                validators[col] = np.nan
            validators[col] = numeric(validators[col])
        validators['mev_rewards_SOL'] = validators['mev_rewards'] / LAMPORTS_PER_SOL
        validators['active_stake_SOL'] = validators['active_stake'] / LAMPORTS_PER_SOL
        validators['running_bam_num'] = bool_like(validators.get('running_bam', pd.Series(False, index=validators.index)))
        validators['running_jito_num'] = bool_like(validators.get('running_jito', pd.Series(False, index=validators.index)))
        if 'jito_directed_stake_target' in validators.columns:
            validators['jito_directed_target_num'] = bool_like(validators['jito_directed_stake_target'])
        else:
            validators['jito_directed_target_num'] = (validators['jito_directed_stake_lamports'].fillna(0) > 0).astype(float)
        validators['running_bam_epoch_share'] = validators['running_bam_num']
        validators['running_jito_epoch_share'] = validators['running_jito_num']
        validators['jito_directed_epoch_share'] = validators['jito_directed_target_num']

        epoch_totals = validators.groupby('epoch', as_index=False).agg(
            epoch_total_mev_SOL=('mev_rewards_SOL', 'sum'),
            epoch_total_active_stake_SOL=('active_stake_SOL', 'sum'),
        )
        panel = validators.merge(epoch_totals, on='epoch', how='left')
        panel['mev_share'] = panel['mev_rewards_SOL'] / panel['epoch_total_mev_SOL'].replace(0, np.nan)
        panel['stake_share'] = panel['active_stake_SOL'] / panel['epoch_total_active_stake_SOL'].replace(0, np.nan)
        panel['excess_mev_share'] = panel['mev_share'] - panel['stake_share']
        panel['mev_yield'] = panel['mev_rewards'] / panel['active_stake'].replace(0, np.nan)

        if not bam_df.empty:
            if 'identity' not in bam_df.columns and 'identity_account' in bam_df.columns:
                bam_df['identity'] = bam_df['identity_account']
            for col in [
                'build_time_score',
                'vote_packing_score',
                'non_vote_packing_score',
                'ibrl_score',
                'blocks_produced',
                'median_block_build_ms',
            ]:
                if col not in bam_df.columns:
                    bam_df[col] = np.nan
                bam_df[col] = numeric(bam_df[col])
            bam_cols = [
                'epoch',
                'identity',
                'build_time_score',
                'vote_packing_score',
                'non_vote_packing_score',
                'ibrl_score',
                'blocks_produced',
                'median_block_build_ms',
            ]
            panel = panel.merge(bam_df[bam_cols], left_on=['epoch', 'identity_account'], right_on=['epoch', 'identity'], how='left')
        else:
            for col in ['build_time_score', 'vote_packing_score', 'non_vote_packing_score', 'ibrl_score', 'blocks_produced', 'median_block_build_ms']:
                panel[col] = np.nan

        grouped = panel.groupby(['identity_account', 'vote_account'], dropna=False).agg(
            epochs_seen=('epoch', 'nunique'),
            first_epoch=('epoch', 'min'),
            last_epoch=('epoch', 'max'),
            total_mev_SOL=('mev_rewards_SOL', 'sum'),
            avg_mev_SOL=('mev_rewards_SOL', 'mean'),
            avg_active_stake_SOL=('active_stake_SOL', 'mean'),
            avg_mev_yield=('mev_yield', 'mean'),
            avg_excess_mev_share=('excess_mev_share', 'mean'),
            median_excess_mev_share=('excess_mev_share', 'median'),
            positive_excess_epoch_share=('excess_mev_share', lambda x: float((x > 0).mean())),
            running_bam_epoch_share=('running_bam_num', 'mean'),
            running_jito_epoch_share=('running_jito_num', 'mean'),
            jito_directed_epoch_share=('jito_directed_target_num', 'mean'),
            avg_bam_connection_rate=('bam_connection_rate', 'mean'),
            avg_mev_commission_bps=('mev_commission_bps', 'mean'),
            total_blocks_produced=('blocks_produced', 'sum'),
            avg_blocks_produced=('blocks_produced', 'mean'),
            avg_ibrl_score=('ibrl_score', 'mean'),
            avg_build_time_score=('build_time_score', 'mean'),
            avg_vote_packing_score=('vote_packing_score', 'mean'),
            avg_non_vote_packing_score=('non_vote_packing_score', 'mean'),
            avg_median_block_build_ms=('median_block_build_ms', 'mean'),
        ).reset_index()
        grouped['window'] = f'{min(epochs)}-{max(epochs)}' if epochs else ''
        grouped['mev_per_block_SOL'] = grouped['total_mev_SOL'] / grouped['total_blocks_produced'].replace(0, np.nan)
        grouped['log_total_mev_SOL'] = np.log1p(grouped['total_mev_SOL'].clip(lower=0))
        grouped['log_avg_active_stake_SOL'] = np.log1p(grouped['avg_active_stake_SOL'].clip(lower=0))
        grouped['log_epochs_seen'] = np.log1p(grouped['epochs_seen'])
        grouped['log_total_blocks_produced'] = np.log1p(grouped['total_blocks_produced'])
        grouped['log_mev_per_block_SOL'] = np.log1p(grouped['mev_per_block_SOL'])
        coverage_min = max(3, math.ceil(0.8 * len(epochs))) if epochs else 3
        eligible = grouped['epochs_seen'] >= coverage_min
        cutoff = grouped.loc[eligible, 'avg_excess_mev_share'].quantile(0.75) if eligible.any() else np.nan
        grouped['candidate_like_50epoch'] = ((eligible) & (grouped['avg_excess_mev_share'] >= cutoff) & (grouped['positive_excess_epoch_share'] >= 0.60)).astype(float) if pd.notna(cutoff) else 0.0
        grouped['candidate_cutoff_avg_excess'] = cutoff
        grouped['coverage_min_epochs'] = coverage_min
    else:
        grouped = pd.DataFrame()
    validators.to_csv(API_RAW / 'jito_validator_epoch_raw_online.csv', index=False)
    mev_df.to_csv(API_RAW / 'jito_epoch_mev_raw_online.csv', index=False)
    bam_df.to_csv(API_RAW / 'bam_validator_epoch_raw_online.csv', index=False)
    grouped.to_csv(API_RAW / 'validator_epoch_mev_bam_summary_50epoch_online.csv', index=False)
    pd.DataFrame(manifest).to_csv(API_RAW / 'jito_epoch_fetch_manifest.csv', index=False)
    if write_source_assets and not grouped.empty:
        grouped.to_csv(SOURCE_ASSETS / 'validator_epoch_mev_bam_summary_50epoch.csv', index=False)
    return {
        'source': 'jito_epochs',
        'epochs': len(epochs),
        'validator_epoch_rows': len(validators),
        'bam_validator_epoch_rows': len(bam_df),
        'summary_rows': len(grouped),
        'wrote_source_assets': write_source_assets,
    }

