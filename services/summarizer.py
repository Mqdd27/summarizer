import time
import base64
import logging
import re
from contextvars import ContextVar
from typing import Any

import httpx

import config
from services.website import extract_from_url
from services.pdf import extract_from_pdf
from services.image import extract_from_image
from services.document import extract_document_text
from services.markdown import render_markdown
from services.cache import get_cached, set_cached, set_document_context, log_request

logger = logging.getLogger("summarizer")
logging.basicConfig(level=logging.INFO)

selected_model: ContextVar[str] = ContextVar("selected_model", default=config.OLLAMA_MODEL)


def set_model(model: str):
    return selected_model.set(model)


def reset_model(token):
    selected_model.reset(token)


def get_model() -> str:
    return selected_model.get()

SYSTEM_PROMPT = "You are an expert document summarizer and assistant. Respond directly in clean Markdown format without internal thinking tags. Language rule: Match the language of the source document or the user's question. If the document/question is in Indonesian (Bahasa Indonesia), write your response in Indonesian. If in English, write in English."

SUMMARY_PROMPT = """Analyze the following content and produce a structured summary in Markdown format.
Match the language of the source content (Indonesian if content is Indonesian, English if English).

Choose the most appropriate sections from:
- # Executive Summary
- ## Key Points
- ## Detailed Summary
- ## Important Facts
- ## Action Items
- ## TL;DR

Rules:
- Output Markdown directly
- Only include relevant sections
- Do NOT fabricate information
- Prioritize factual accuracy
- Language: Follow the document language (Indonesian or English)

Content:
"""

IMAGE_PROMPT = """Analyze this image thoroughly and provide a structured summary in Markdown format.

Include:
- # Image Analysis
- ## Description
- ## Key Details
- ## Text Content (if any visible text)
- ## Context & Significance
- ## TL;DR

Output Markdown directly in English (or Indonesian if the text inside the image is Indonesian).
"""


async def call_ollama(prompt: str, images: list[str] | None = None) -> dict[str, Any]:
    model = get_model()
    # Check if using 9router / OpenAI-compatible endpoint
    is_openai_compat = "/v1" in config.OLLAMA_HOST or bool(config.ROUTER_API_KEY)
    
    if is_openai_compat:
        base_url = config.OLLAMA_HOST.rstrip("/")
        if not base_url.endswith("/v1"):
            endpoint = f"{base_url}/v1/chat/completions"
        else:
            endpoint = f"{base_url}/chat/completions"
        
        headers = {
            "Content-Type": "application/json",
        }
        if config.ROUTER_API_KEY:
            headers["Authorization"] = f"Bearer {config.ROUTER_API_KEY}"
        
        content_block: Any = prompt
        if images:
            content_block = [{"type": "text", "text": prompt}]
            for img in images:
                content_block.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{img}"}
                })
        
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": content_block}
        ]
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": config.OLLAMA_NUM_PREDICT,
            "temperature": config.OLLAMA_TEMPERATURE,
        }
    elif images:
        headers = {}
        endpoint = f"{config.OLLAMA_HOST}/api/chat"
        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": prompt, "images": images}
            ],
            "stream": False,
            "options": {
                "num_ctx": config.OLLAMA_NUM_CTX,
                "num_predict": config.OLLAMA_NUM_PREDICT,
                "temperature": config.OLLAMA_TEMPERATURE,
                "top_p": config.OLLAMA_TOP_P,
            },
            "keep_alive": config.OLLAMA_KEEP_ALIVE,
        }
    else:
        headers = {}
        endpoint = f"{config.OLLAMA_HOST}/api/generate"
        formatted_prompt = f"<|im_start|>system\n{SYSTEM_PROMPT}<|im_end|>\n<|im_start|>user\n{prompt}<|im_end|>\n<|im_start|>assistant\n<think>\n</think>\n"
        payload = {
            "model": model,
            "prompt": formatted_prompt,
            "raw": True,
            "stream": False,
            "options": {
                "num_ctx": config.OLLAMA_NUM_CTX,
                "num_predict": config.OLLAMA_NUM_PREDICT,
                "temperature": config.OLLAMA_TEMPERATURE,
                "top_p": config.OLLAMA_TOP_P,
            },
            "keep_alive": config.OLLAMA_KEEP_ALIVE,
        }

    max_retries = 3
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=config.OLLAMA_TIMEOUT) as client:
                start = time.time()
                logger.info(f"AI request attempt {attempt + 1}, model={model}, endpoint={endpoint}")
                resp = await client.post(endpoint, json=payload, headers=headers)
                duration = time.time() - start
                if resp.is_error:
                    logger.error("AI provider error status=%s body=%s", resp.status_code, resp.text[:1000])
                resp.raise_for_status()
                
                # Parse response
                content = ""
                if is_openai_compat:
                    raw_text = resp.text.strip()
                    # Strip any trailing 'data: [DONE]' from 9router responses
                    if "\ndata: [DONE]" in raw_text:
                        raw_text = raw_text.split("\ndata: [DONE]")[0].strip()
                    elif raw_text.endswith("data: [DONE]"):
                        raw_text = raw_text[:-12].strip()
                    
                    try:
                        # 1. Try standard JSON response
                        import json
                        data = json.loads(raw_text)
                        choice = data.get("choices", [{}])[0]
                        msg = choice.get("message", {})
                        content = msg.get("content", "").strip()
                        if not content and "reasoning_content" in msg:
                            content = msg.get("reasoning_content", "").strip()
                    except Exception:
                        pass
                    
                    # 2. If empty or failed, check for SSE streaming format
                    if not content:
                        for line in resp.text.strip().split("\n"):
                            line = line.strip()
                            if line.startswith("data: ") and line != "data: [DONE]":
                                try:
                                    import json
                                    chunk = json.loads(line[6:])
                                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                                    if "content" in delta and delta["content"]:
                                        content += delta["content"]
                                    elif "reasoning_content" in delta and delta["reasoning_content"]:
                                        content += delta["reasoning_content"]
                                except Exception:
                                    pass
                        content = content.strip()
                elif images:
                    data = resp.json()
                    content = data.get("message", {}).get("content", "").strip()
                    if not content:
                        content = data.get("message", {}).get("thinking", "").strip()
                else:
                    data = resp.json()
                    content = data.get("response", "").strip()
                    if not content:
                        content = data.get("thinking", "").strip()
                
                if not content:
                    raise ValueError("Empty response from model")
                logger.info(f"AI response received in {duration:.1f}s")
                return {"content": content, "duration": duration}
        except (httpx.TimeoutException, httpx.ConnectError) as e:
            logger.warning(f"AI attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                wait = 2 ** attempt
                logger.info(f"Retrying in {wait}s...")
                import asyncio
                await asyncio.sleep(wait)
            else:
                raise
        except Exception as e:
            logger.error(f"AI error: {e}")
            raise

    raise RuntimeError("AI request failed after retries")


def count_words(text: str) -> int:
    return len(text.split())


def chunk_text(text: str, chunk_size: int = None, overlap: int = None) -> list[str]:
    chunk_size = chunk_size or config.CHUNK_SIZE
    overlap = overlap or config.CHUNK_OVERLAP
    words = text.split()
    if len(words) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        start = end - overlap
    return chunks


async def hierarchical_summarize(text: str) -> dict[str, Any]:
    chunks = chunk_text(text)
    total_duration = 0.0

    if len(chunks) == 1:
        result = await call_ollama(SUMMARY_PROMPT + text)
        return {**result, "chunk_count": 1}

    chunk_summaries = []
    for i, chunk in enumerate(chunks):
        prompt = f"Summarize the following text chunk ({i+1}/{len(chunks)}). Be concise but capture all key information:\n\n{chunk}"
        result = await call_ollama(prompt)
        chunk_summaries.append(result["content"])
        total_duration += result["duration"]

    combined = "\n\n---\n\n".join(chunk_summaries)
    final_prompt = SUMMARY_PROMPT + combined
    final_result = await call_ollama(final_prompt)
    total_duration += final_result["duration"]

    return {
        "content": final_result["content"],
        "duration": total_duration,
        "chunk_count": len(chunks),
    }


async def process_text(text: str, title: str = "Pasted text") -> dict[str, Any]:
    model = get_model()
    start = time.time()
    try:
        text = text.strip()
        if not text:
            return {"error": "Text is required."}
        original_words = count_words(text)
        result = await hierarchical_summarize(text)
        summary_html = render_markdown(result["content"])
        summary_words = count_words(result["content"])
        total_time = time.time() - start
        context_id = await set_document_context("text", text, model)
        output = {
            "context_id": context_id,
            "source_kind": "text",
            "source_url": f"/api/document-source/{context_id}",
            "summary_html": summary_html,
            "summary_md": result["content"],
            "source_type": "Text",
            "source_title": title,
            "source_name": "Pasted text",
            "processing_time": f"{total_time:.1f}s",
            "original_words": original_words,
            "summary_words": summary_words,
            "compression_ratio": f"{(1 - summary_words / max(original_words, 1)) * 100:.0f}%",
            "reading_time": f"{max(1, summary_words // 200)} min",
            "model_used": model,
            "chunk_count": result.get("chunk_count", 1),
        }
        await log_request("text", title, model, total_time, original_words, summary_words, "success", "", result.get("chunk_count", 1))
        return output
    except Exception as e:
        total_time = time.time() - start
        logger.error(f"Text processing error: {e}")
        await log_request("text", title, model, total_time, 0, 0, "error", str(e), 0)
        return {"error": f"Failed to process text: {e}"}


async def process_url(url: str) -> dict[str, Any]:
    model = get_model()
    cached = await get_cached(url, model)
    if cached and cached.get("context_id"):
        cached["source_kind"] = "text"
        cached["source_url"] = f"/api/document-source/{cached['context_id']}"
        return cached

    start = time.time()
    try:
        extracted = await extract_from_url(url)
        if not extracted["text"].strip():
            return {"error": "Could not extract meaningful content from this URL."}

        original_words = count_words(extracted["text"])
        result = await hierarchical_summarize(extracted["text"])
        summary_html = render_markdown(result["content"])
        summary_words = count_words(result["content"])
        total_time = time.time() - start
        context_id = await set_document_context("text", extracted["text"], model)

        output = {
            "context_id": context_id,
            "source_kind": "text",
            "source_url": f"/api/document-source/{context_id}",
            "summary_html": summary_html,
            "summary_md": result["content"],
            "source_type": "URL",
            "source_title": extracted.get("title", url),
            "source_name": url,
            "processing_time": f"{total_time:.1f}s",
            "original_words": original_words,
            "summary_words": summary_words,
            "compression_ratio": f"{(1 - summary_words / max(original_words, 1)) * 100:.0f}%",
            "reading_time": f"{max(1, summary_words // 200)} min",
            "model_used": model,
            "chunk_count": result.get("chunk_count", 1),
        }
        await set_cached(url, model, output)
        await log_request("url", url, model, total_time, original_words, summary_words, "success", "", result.get("chunk_count", 1))
        return output
    except Exception as e:
        total_time = time.time() - start
        logger.error(f"URL processing error: {e}")
        await log_request("url", url, model, total_time, 0, 0, "error", str(e), 0)
        return {"error": f"Failed to process URL: {e}"}


def relevant_source_text(text: str, question: str) -> str:
    chunks = chunk_text(text, chunk_size=700, overlap=60)
    if len(chunks) <= 4:
        return "\n\n---\n\n".join(chunks)
    terms = set(re.findall(r"[\w-]{3,}", question.lower()))
    ranked = sorted(
        enumerate(chunks),
        key=lambda item: sum(item[1].lower().count(term) for term in terms),
        reverse=True,
    )[:3]
    return "\n\n---\n\n".join(chunk for _, chunk in sorted(ranked))


async def ask_document(context: dict, question: str, research: bool = False) -> tuple[str, list[dict[str, str]]]:
    sources: list[dict[str, str]] = []
    if research:
        try:
            from services.web_search import search_web
            sources = await search_web(question)
        except Exception as error:
            logger.warning("Web research unavailable: %s", error)

    if research:
        instructions = """Answer the user's question using the original source, your general knowledge, and the external web search notes when useful.
Reason carefully and distinguish claims from the original source versus external information.
Do not invent citations. Respond in Markdown and match the language of the user's question."""
        web_context = "\n".join(
            f"- {item['title']}: {item['snippet']} ({item['url']})" for item in sources
        ) or "No external web results were available."
    else:
        instructions = """Answer using the original source provided below, not merely its summary.
If the answer is not present in the source, clearly state so.
Respond in Markdown and match the language of the user's question."""
        web_context = ""

    if context["source_type"] == "image":
        prompt = f"{instructions}\n\nExternal Web Notes:\n{web_context}\n\nUser Question: {question}"
        result = await call_ollama(prompt, images=[context["content"]])
    else:
        source = relevant_source_text(context["content"], question)
        prompt = f"""{instructions}

Original Source:
\"\"\"
{source}
\"\"\"

External Web Notes:
{web_context}

User Question: {question}
"""
        result = await call_ollama(prompt)
    return render_markdown(result["content"]), sources


async def process_file(file_path: str, input_type: str, original_name: str) -> dict[str, Any]:
    model = get_model()
    start = time.time()
    try:
        if input_type == "pdf":
            extracted = extract_from_pdf(file_path)
            text = extracted["text"]
            title = extracted.get("title", original_name)
            if not text.strip():
                return {"error": "Could not extract text from this PDF."}
            original_words = count_words(text)
            result = await hierarchical_summarize(text)
            summary_html = render_markdown(result["content"])
            summary_words = count_words(result["content"])
            total_time = time.time() - start
            context_id = await set_document_context("text", text, model)
            output = {
                "context_id": context_id,
                "source_kind": "text",
                "source_url": f"/api/document-source/{context_id}",
                "summary_html": summary_html,
                "summary_md": result["content"],
                "source_type": "PDF",
                "source_title": title,
                "source_name": original_name,
                "processing_time": f"{total_time:.1f}s",
                "original_words": original_words,
                "summary_words": summary_words,
                "compression_ratio": f"{(1 - summary_words / max(original_words, 1)) * 100:.0f}%",
                "reading_time": f"{max(1, summary_words // 200)} min",
                "model_used": model,
                "chunk_count": result.get("chunk_count", 1),
                "page_count": extracted.get("page_count", 0),
            }
            await log_request("pdf", original_name, model, total_time, original_words, summary_words, "success", "", result.get("chunk_count", 1))
            return output

        elif input_type == "document":
            extracted = extract_document_text(file_path)
            text = extracted["text"]
            if not text.strip():
                return {"error": "Could not extract readable text from this document."}
            original_words = count_words(text)
            result = await hierarchical_summarize(text)
            summary_html = render_markdown(result["content"])
            summary_words = count_words(result["content"])
            total_time = time.time() - start
            context_id = await set_document_context("text", text, model)
            output = {
                "context_id": context_id,
                "source_kind": "text",
                "source_url": f"/api/document-source/{context_id}",
                "summary_html": summary_html,
                "summary_md": result["content"],
                "source_type": extracted["extension"].lstrip(".").upper() or "Document",
                "source_title": extracted["title"] or original_name,
                "source_name": original_name,
                "processing_time": f"{total_time:.1f}s",
                "original_words": original_words,
                "summary_words": summary_words,
                "compression_ratio": f"{(1 - summary_words / max(original_words, 1)) * 100:.0f}%",
                "reading_time": f"{max(1, summary_words // 200)} min",
                "model_used": model,
                "chunk_count": result.get("chunk_count", 1),
            }
            await log_request("document", original_name, model, total_time, original_words, summary_words, "success", "", result.get("chunk_count", 1))
            return output

        elif input_type == "image":
            img_data = extract_from_image(file_path)
            b64 = img_data["base64"]
            original_words = 0
            result = await call_ollama(IMAGE_PROMPT, images=[b64])
            summary_html = render_markdown(result["content"])
            summary_words = count_words(result["content"])
            total_time = time.time() - start
            w = img_data.get("width", 0)
            h = img_data.get("height", 0)
            context_id = await set_document_context("image", b64, model)
            output = {
                "context_id": context_id,
                "source_kind": "image",
                "source_url": f"/api/document-source/{context_id}",
                "summary_html": summary_html,
                "summary_md": result["content"],
                "source_type": "Image",
                "source_title": original_name,
                "source_name": original_name,
                "processing_time": f"{total_time:.1f}s",
                "original_words": 0,
                "summary_words": summary_words,
                "compression_ratio": "N/A",
                "reading_time": f"{max(1, summary_words // 200)} min",
                "model_used": model,
                "chunk_count": 1,
                "image_size": f"{w}x{h}",
            }
            await log_request("image", original_name, model, total_time, 0, summary_words, "success", "", 1)
            return output
        else:
            return {"error": f"Unsupported input type: {input_type}"}
    except Exception as e:
        total_time = time.time() - start
        logger.error(f"File processing error: {e}")
        await log_request(input_type, original_name, model, total_time, 0, 0, "error", str(e), 0)
        return {"error": f"Failed to process file: {e}"}
