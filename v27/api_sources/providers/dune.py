from __future__ import annotations

BASE = 'https://api.dune.com/api/v1'


def sql_execute() -> str:
    return f'{BASE}/sql/execute'


def execution_results(execution_id: str, *, limit: int = 1000) -> str:
    return f'{BASE}/execution/{execution_id}/results?limit={limit}'
