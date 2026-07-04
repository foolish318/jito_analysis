from __future__ import annotations

from urllib.parse import urlencode

BASE = 'https://pro-api.solscan.io/v2.0'


def account_detail(address: str) -> str:
    return f'{BASE}/account/detail?{urlencode({"address": address})}'
