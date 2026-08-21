import pymupdf as fitz


def extract_from_pdf(file_path: str) -> dict:
    doc = fitz.open(file_path)
    pages = []
    full_text = []

    for i, page in enumerate(doc):
        text = page.get_text()
        if text.strip():
            pages.append({"page": i + 1, "text": text})
            full_text.append(text)

    title = doc.metadata.get("title", "") if doc.metadata else ""
    doc.close()

    return {
        "text": "\n\n".join(full_text),
        "title": title or "",
        "page_count": len(pages),
    }
