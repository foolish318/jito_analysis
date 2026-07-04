from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

SECRET_ENV_NAMES = ['SOLSCAN_API_KEY', 'HELIUS_API_KEY', 'DUNE_API_KEY', 'SOLANA_RPC_URL']


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True, default=str), encoding='utf-8')


def load_env_files(*paths: Path) -> None:
    for path in paths:
        if not path.exists():
            continue
        if path.suffix == '.md':
            text = path.read_text(encoding='utf-8', errors='ignore')
            for key, value in re.findall(r'\b([A-Z0-9_]+(?:API_KEY|RPC_URL))\b\s*[:=]\s*`?([^\s`]+)', text):
                if key and value and not value.startswith('<'):
                    os.environ.setdefault(key, value.strip().strip(chr(34)).strip(chr(39)))
            continue
        for raw_line in path.read_text(encoding='utf-8').splitlines():
            line = raw_line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            os.environ.setdefault(key.strip(), value.strip().strip(chr(34)).strip(chr(39)))


def redact_url(url: str) -> str:
    out = url
    for key_name in SECRET_ENV_NAMES:
        key = os.environ.get(key_name)
        if key:
            out = out.replace(key, '$' + key_name)
    return out


def request_json(url: str, *, method: str = 'GET', body: Any | None = None, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None, timeout: int = 60, user_agent: str = 'jito-analysis-v27-api/1.0') -> tuple[dict[str, Any], Any | None]:
    if params:
        url = url + ('&' if '?' in url else '?') + urllib.parse.urlencode(params)
    started = time.time()
    data = json.dumps(body).encode('utf-8') if body is not None else None
    req_headers = {'Accept': 'application/json', 'User-Agent': user_agent}
    if body is not None:
        req_headers['Content-Type'] = 'application/json'
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, data=data, method=method, headers=req_headers)
    meta = {'url': redact_url(url), 'method': method, 'status_code': None, 'ok': False, 'elapsed_sec': None, 'error': None}
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode('utf-8')
            meta.update({'status_code': resp.status, 'ok': 200 <= resp.status < 300, 'elapsed_sec': round(time.time() - started, 3)})
            return meta, json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode('utf-8', errors='replace') if exc.fp else ''
        meta.update({'status_code': exc.code, 'elapsed_sec': round(time.time() - started, 3), 'error': raw[:500] or str(exc)})
        return meta, None
    except Exception as exc:
        meta.update({'elapsed_sec': round(time.time() - started, 3), 'error': repr(exc)})
        return meta, None


def object_rows(obj: Any) -> list[dict[str, Any]]:
    if isinstance(obj, list):
        return [x for x in obj if isinstance(x, dict)]
    if isinstance(obj, dict):
        for key in ['data', 'validators', 'items', 'results', 'rewards', 'blocks', 'rows', 'result']:
            val = obj.get(key)
            if isinstance(val, list):
                return [x for x in val if isinstance(x, dict)]
        result = obj.get('result')
        if isinstance(result, dict):
            rows = []
            for key in ['current', 'delinquent']:
                val = result.get(key)
                if isinstance(val, list):
                    rows.extend(x for x in val if isinstance(x, dict))
            return rows
    return []



def numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors='coerce')


def ensure_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    out = df.copy()
    for col in columns:
        if col not in out.columns:
            out[col] = np.nan
    return out[columns]


def solana_rpc_request(
    rpc_url: str,
    method: str,
    params: list[Any] | None = None,
    *,
    timeout: int = 90,
    user_agent: str = 'jito-analysis-v27-api/1.0',
) -> tuple[dict[str, Any], Any | None]:
    meta, obj = request_json(
        rpc_url,
        method='POST',
        body={'jsonrpc': '2.0', 'id': method, 'method': method, 'params': params or []},
        timeout=timeout,
        user_agent=user_agent,
    )
    meta['source'] = 'solana_rpc'
    meta['rpc_method'] = method
    return meta, obj


def md_table(df: pd.DataFrame) -> str:
    if df.empty:
        return '_No rows._'
    cols = [str(c) for c in df.columns]
    lines = ['| ' + ' | '.join(cols) + ' |', '| ' + ' | '.join(['---'] * len(cols)) + ' |']
    for _, row in df.iterrows():
        vals = []
        for col in df.columns:
            value = row[col]
            if isinstance(value, (list, dict, tuple, set)):
                vals.append(json.dumps(value, sort_keys=True, default=str).replace('|', '\\|').replace('\n', ' ')[:500])
            elif pd.isna(value):
                vals.append('')
            else:
                vals.append(str(value).replace('|', '\\|').replace('\n', ' ')[:500])
        lines.append('| ' + ' | '.join(vals) + ' |')
    return '\n'.join(lines)
