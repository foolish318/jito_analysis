from __future__ import annotations

BASE = 'https://explorer.bam.dev/api/v1'


def ibrl_validators() -> str:
    return f'{BASE}/ibrl_validators'


def ibrl_blocks() -> str:
    return f'{BASE}/ibrl_blocks'
