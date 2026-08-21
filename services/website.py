import httpx
from bs4 import BeautifulSoup
from readability import Document


async def extract_from_url(url: str) -> dict:
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }
    async with httpx.AsyncClient(timeout=30, follow_redirects=True, max_redirects=5) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        html = resp.text

    doc = Document(html)
    title = doc.title()
    content_html = doc.summary()

    soup = BeautifulSoup(content_html, "lxml")
    for tag in soup.find_all(["script", "style", "nav", "footer", "iframe", "noscript"]):
        tag.decompose()

    text = soup.get_text(separator="\n", strip=True)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    clean_text = "\n".join(lines)

    return {"text": clean_text, "title": title}
