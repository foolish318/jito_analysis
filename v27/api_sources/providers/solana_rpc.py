from __future__ import annotations

DEFAULT_RPC_URL = 'https://api.mainnet-beta.solana.com'


def rpc_body(method: str, params: list | None = None) -> dict:
    return {'jsonrpc': '2.0', 'id': method, 'method': method, 'params': params or []}


def get_block_params(slot: int) -> list:
    return [int(slot), {'encoding': 'jsonParsed', 'transactionDetails': 'full', 'rewards': False, 'maxSupportedTransactionVersion': 0, 'commitment': 'finalized'}]
