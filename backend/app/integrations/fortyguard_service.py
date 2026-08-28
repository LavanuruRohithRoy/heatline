import asyncio
from app.integrations.fortyguard_client import FortyGuardClient
import os
from app.core.config import settings


os.environ.setdefault("FORTYGUARD_API_KEY", settings.fortyguard_api_key)

_client = FortyGuardClient()

async def create_heatmap_async(**kwargs) -> dict:
    return await asyncio.to_thread(_client.create_heatmap, **kwargs)

async def get_env_params_async(**kwargs) -> dict:
    return await asyncio.to_thread(_client.environmental_parameters, **kwargs)

async def get_usage_async() -> dict:
    return await asyncio.to_thread(_client.fetch_api_key_usage)