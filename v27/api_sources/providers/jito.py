from __future__ import annotations

from urllib.parse import urlencode, quote

BUNDLE_BASE = 'https://bundles.jito.wtf/api/v1/bundles'
KOBE_BASE = 'https://kobe.mainnet.jito.network/api/v1'
BLOCK_ENGINE_BASE = 'https://mainnet.block-engine.jito.wtf/api/v1'


def public_bundle_recent(limit: int, *, sort: str | None = None, asc: bool | None = None) -> str:
    params = {'limit': limit}
    if sort is not None:
        params['sort'] = sort
    if asc is not None:
        params['asc'] = str(asc).lower()
    return f'{BUNDLE_BASE}/recent?{urlencode(params)}'


def public_bundle_detail(bundle_id: str) -> str:
    return f'{BUNDLE_BASE}/bundle/{quote(bundle_id)}'


def public_bundle_events(bundle_id: str) -> str:
    return f'{BUNDLE_BASE}/bundle_events/{quote(bundle_id)}'


def public_stats() -> str:
    return f'{BUNDLE_BASE}/stats'


def public_tip_floor() -> str:
    return f'{BUNDLE_BASE}/tip_floor'


def kobe_endpoint(name: str) -> str:
    return f'{KOBE_BASE}/{name}'


def get_tip_accounts() -> str:
    return f'{BLOCK_ENGINE_BASE}/getTipAccounts'
