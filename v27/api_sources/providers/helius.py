from __future__ import annotations

from urllib.parse import urlencode, quote

BASE = 'https://mainnet.helius-rpc.com/v0'


def enhanced_transactions(api_key: str) -> str:
    return f'{BASE}/transactions?{urlencode({"api-key": api_key})}'


def address_transactions(address: str, api_key: str, *, limit: int = 100) -> str:
    params = {'api-key': api_key, 'limit': limit, 'sort-order': 'desc'}
    return f'{BASE}/addresses/{quote(address)}/transactions?{urlencode(params)}'
