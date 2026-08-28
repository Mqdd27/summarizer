import httpx

import config


async def get_models() -> list[str]:
    base_url = config.OLLAMA_HOST.rstrip("/")
    endpoint = f"{base_url}/models" if base_url.endswith("/v1") else f"{base_url}/v1/models"
    headers = {"Authorization": f"Bearer {config.ROUTER_API_KEY}"} if config.ROUTER_API_KEY else {}
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(endpoint, headers=headers)
        response.raise_for_status()
    return sorted(
        item["id"]
        for item in response.json().get("data", [])
        if item.get("id") and not item["id"].startswith("ollama-local/")
    )


async def validate_model(model: str) -> str:
    models = await get_models()
    return model if model in models else config.OLLAMA_MODEL
