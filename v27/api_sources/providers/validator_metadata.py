from __future__ import annotations


def stakewiz_validators() -> str:
    return 'https://api.stakewiz.com/validators'


def validators_app_mainnet(limit: int = 5000) -> str:
    return f'https://www.validators.app/api/v1/validators/mainnet.json?limit={limit}'
