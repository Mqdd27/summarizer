from urllib.parse import urlencode

import httpx
from bs4 import BeautifulSoup


async def search_web(query: str) -> list[dict[str, str]]:
    params = urlencode({"q": query, "kl": "us-en"})
    headers = {"User-Agent": "Mozilla/5.0 (compatible; SummarizerResearch/1.0)"}
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        response = await client.get(f"https://html.duckduckgo.com/html/?{params}", headers=headers)
        response.raise_for_status()

    soup = BeautifulSoup(response.text, "lxml")
    results = []
    for item in soup.select(".result")[:4]:
        link = item.select_one(".result__a")
        snippet = item.select_one(".result__snippet")
        if not link or not link.get("href"):
            continue
        results.append({
            "title": link.get_text(" ", strip=True),
            "url": link["href"],
            "snippet": snippet.get_text(" ", strip=True) if snippet else "",
        })
    return results
