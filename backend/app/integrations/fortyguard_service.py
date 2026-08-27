import asyncio
from app.integrations.fortyguard_client import FortyGuardClient

_client = FortyGuardClient()

async def create_heatmap_async(**kwargs) -> dict:
    return await asyncio.to_thread(_client.create_heatmap, **kwargs)

async def get_env_params_async(**kwargs) -> dict:
    return await asyncio.to_thread(_client.environmental_parameters, **kwargs)

async def get_usage_async() -> dict:
    return await asyncio.to_thread(_client.fetch_api_key_usage)