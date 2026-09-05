import os
from dotenv import load_dotenv

load_dotenv()

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3.5:2b")
ROUTER_API_KEY = os.getenv("ROUTER_API_KEY", "")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "300"))
OLLAMA_NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "8192"))
OLLAMA_NUM_PREDICT = int(os.getenv("OLLAMA_NUM_PREDICT", "1024"))
OLLAMA_TEMPERATURE = float(os.getenv("OLLAMA_TEMPERATURE", "0.3"))
OLLAMA_TOP_P = float(os.getenv("OLLAMA_TOP_P", "0.9"))
OLLAMA_KEEP_ALIVE = os.getenv("OLLAMA_KEEP_ALIVE", "30m")

UPLOAD_MAX_SIZE = int(os.getenv("UPLOAD_MAX_SIZE", str(20 * 1024 * 1024)))
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "/tmp/summarizer_uploads")
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_PDF_TYPES = {"application/pdf"}
ALLOWED_DOCUMENT_TYPES = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.oasis.opendocument.text",
    "text/plain", "text/markdown", "text/csv", "text/tab-separated-values",
    "application/json", "application/xml", "text/xml", "text/html", "application/rtf",
}
ALLOWED_DOCUMENT_EXTENSIONS = {
    ".docx", ".odt", ".txt", ".md", ".markdown", ".rst", ".csv", ".tsv",
    ".json", ".jsonl", ".xml", ".html", ".htm", ".rtf", ".log", ".yaml",
    ".yml", ".ini", ".cfg", ".conf", ".toml", ".py", ".js", ".ts", ".tsx",
    ".jsx", ".css", ".sql", ".sh", ".bash", ".zsh", ".java", ".c", ".cpp",
    ".h", ".go", ".rs", ".php", ".rb", ".swift", ".kt", ".tex",
}

DB_PATH = os.getenv("DB_PATH", "database.db")

CACHE_TTL_HOURS = int(os.getenv("CACHE_TTL_HOURS", "24"))

RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "10"))
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60"))

CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "3000"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "200"))

SSRF_BLOCKED_RANGES = [
    "127.", "0.", "10.", "172.16.", "172.17.", "172.18.", "172.19.",
    "172.20.", "172.21.", "172.22.", "172.23.", "172.24.", "172.25.",
    "172.26.", "172.27.", "172.28.", "172.29.", "172.30.", "172.31.",
    "192.168.", "169.254.", "::1", "fc00:", "fe80:", "fd",
]

APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT = int(os.getenv("APP_PORT", "8000"))
