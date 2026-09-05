import re
import zipfile
from html import unescape
from pathlib import Path
from xml.etree import ElementTree

TEXT_EXTENSIONS = {
    ".txt", ".md", ".markdown", ".rst", ".csv", ".tsv", ".json", ".jsonl",
    ".xml", ".html", ".htm", ".rtf", ".log", ".yaml", ".yml", ".ini",
    ".cfg", ".conf", ".toml", ".py", ".js", ".ts", ".tsx", ".jsx", ".css",
    ".sql", ".sh", ".bash", ".zsh", ".java", ".c", ".cpp", ".h", ".go",
    ".rs", ".php", ".rb", ".swift", ".kt", ".tex",
}

DOCUMENT_EXTENSIONS = {".docx", ".odt"}


def decode_text(content: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-16", "utf-8", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            pass
    raise ValueError("Could not decode this text file.")


def extract_docx(file_path: str) -> str:
    with zipfile.ZipFile(file_path) as archive:
        xml = archive.read("word/document.xml")
    root = ElementTree.fromstring(xml)
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs = []
    for paragraph in root.findall(".//w:p", ns):
        text = "".join(node.text or "" for node in paragraph.findall(".//w:t", ns))
        if text.strip():
            paragraphs.append(text.strip())
    return "\n\n".join(paragraphs)


def extract_odt(file_path: str) -> str:
    with zipfile.ZipFile(file_path) as archive:
        xml = archive.read("content.xml")
    root = ElementTree.fromstring(xml)
    paragraphs = []
    for node in root.iter():
        if node.tag.endswith("}p") or node.tag.endswith("}h"):
            text = "".join(node.itertext()).strip()
            if text:
                paragraphs.append(text)
    return "\n\n".join(paragraphs)


def extract_rtf(content: bytes) -> str:
    text = decode_text(content)
    text = re.sub(r"\\par[d]?", "\n", text)
    text = re.sub(r"\\'[0-9a-fA-F]{2}", "", text)
    text = re.sub(r"\\[a-zA-Z]+-?\d* ?", "", text)
    return unescape(text.replace("{", "").replace("}", "")).strip()


def extract_document_text(file_path: str) -> dict:
    path = Path(file_path)
    suffix = path.suffix.lower()
    if suffix == ".docx":
        text = extract_docx(file_path)
    elif suffix == ".odt":
        text = extract_odt(file_path)
    else:
        content = path.read_bytes()
        text = extract_rtf(content) if suffix == ".rtf" else decode_text(content)
    return {"text": text, "title": path.stem, "extension": suffix}
