# AI Summarizer

Web application for summarizing URLs, PDFs, and images using Ollama AI.

## Architecture

- **Backend**: FastAPI + Uvicorn
- **Frontend**: Jinja2 + HTMX + TailwindCSS (CDN)
- **AI**: Ollama (qwen3.5:2b)
- **Database**: SQLite (caching + logging)
- **PDF**: PyMuPDF
- **Image**: Pillow + Ollama vision
- **URL**: BeautifulSoup4 + readability-lxml

## Installation

```bash
cd /home/mqdd/apps/summarizer
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configuration

Copy `.env.example` to `.env` and adjust:

```bash
cp .env.example .env
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| OLLAMA_HOST | http://127.0.0.1:11434 | Ollama API endpoint |
| OLLAMA_MODEL | qwen3.5:2b | Model to use |
| OLLAMA_TIMEOUT | 300 | Request timeout (seconds) |
| OLLAMA_NUM_CTX | 8192 | Context window size |
| OLLAMA_NUM_PREDICT | 2048 | Max tokens to generate |
| OLLAMA_TEMPERATURE | 0.3 | Sampling temperature |
| APP_PORT | 8000 | Application port |

## Running Locally

```bash
source .venv/bin/activate
python app.py
```

## Running on Server

```bash
source /home/mqdd/apps/summarizer/.venv/bin/activate
cd /home/mqdd/apps/summarizer
uvicorn app:app --host 0.0.0.0 --port 8000
```

## systemd Service

Service file: `/etc/systemd/system/summarizer.service`

```bash
sudo systemctl enable summarizer
sudo systemctl start summarizer
sudo systemctl status summarizer
sudo journalctl -u summarizer -f
```

## Changing Model

Edit `.env`:
```
OLLAMA_MODEL=your-model-name
```
Then restart: `sudo systemctl restart summarizer`

## Changing Ollama Host

Edit `.env`:
```
OLLAMA_HOST=http://new-host:11434
```
Then restart: `sudo systemctl restart summarizer`

## Troubleshooting

- Check Ollama: `curl http://127.0.0.1:11434/api/tags`
- Check logs: `journalctl -u summarizer -f`
- Check port: `ss -lntp | grep 8000`
- Manual start: `cd /home/mqdd/apps/summarizer && source .venv/bin/activate && python app.py`
