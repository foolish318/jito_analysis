from __future__ import annotations

API_REGISTRY = {
    'jito': ['bundles/recent', 'bundles/bundle/{id}', 'bundles/bundle_events/{id}', 'bundles/stats', 'bundles/tip_floor', 'kobe/mev_rewards', 'kobe/validators', 'kobe/validator_rewards', 'kobe/daily_mev_rewards', 'kobe/staker_rewards', 'block-engine/getTipAccounts'],
    'solana_rpc': ['getSlot', 'getEpochInfo', 'getClusterNodes', 'getVoteAccounts', 'getBlockProduction', 'getLeaderSchedule', 'getBlock'],
    'bam': ['ibrl_validators', 'ibrl_blocks'],
    'helius': ['enhanced transactions', 'address transactions'],
    'solscan': ['account detail'],
    'dune': ['sql/execute', 'execution/{id}/results'],
    'validator_metadata': ['Stakewiz validators', 'Validators.app mainnet validators'],
}
