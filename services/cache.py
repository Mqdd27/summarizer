import time
import json
import uuid
import aiosqlite
import config


def get_db():
    return aiosqlite.connect(config.DB_PATH)


async def init_db():
    async with get_db() as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS cache (
                url TEXT PRIMARY KEY,
                model TEXT,
                result TEXT,
                created_at REAL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS request_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL,
                input_type TEXT,
                source_name TEXT,
                model TEXT,
                duration REAL,
                original_size INTEGER,
                output_size INTEGER,
                status TEXT,
                error_message TEXT,
                chunk_count INTEGER
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS document_context (
                id TEXT PRIMARY KEY,
                source_type TEXT NOT NULL,
                content TEXT NOT NULL,
                model TEXT NOT NULL,
                created_at REAL NOT NULL
            )
        """)
        await db.commit()


async def get_cached(url: str, model: str) -> dict | None:
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT result, created_at FROM cache WHERE url = ? AND model = ?",
            (url, model),
        )
        row = await cursor.fetchone()
        if row:
            created_at = row[1]
            if time.time() - created_at < config.CACHE_TTL_HOURS * 3600:
                result = json.loads(row[0])
                result["cached"] = True
                return result
            else:
                await db.execute("DELETE FROM cache WHERE url = ?", (url,))
                await db.commit()
    return None


async def set_cached(url: str, model: str, result: dict):
    store = {k: v for k, v in result.items() if k != "cached"}
    async with get_db() as db:
        await db.execute(
            "INSERT OR REPLACE INTO cache (url, model, result, created_at) VALUES (?, ?, ?, ?)",
            (url, model, json.dumps(store), time.time()),
        )
        await db.commit()


async def set_document_context(source_type: str, content: str, model: str) -> str:
    context_id = uuid.uuid4().hex
    async with get_db() as db:
        await db.execute(
            "DELETE FROM document_context WHERE created_at < ?",
            (time.time() - config.CACHE_TTL_HOURS * 3600,),
        )
        await db.execute(
            "INSERT INTO document_context (id, source_type, content, model, created_at) VALUES (?, ?, ?, ?, ?)",
            (context_id, source_type, content, model, time.time()),
        )
        await db.commit()
    return context_id


async def get_document_context(context_id: str) -> dict | None:
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT source_type, content, model, created_at FROM document_context WHERE id = ?",
            (context_id,),
        )
        row = await cursor.fetchone()
        if not row or time.time() - row[3] >= config.CACHE_TTL_HOURS * 3600:
            if row:
                await db.execute("DELETE FROM document_context WHERE id = ?", (context_id,))
                await db.commit()
            return None
        return {"source_type": row[0], "content": row[1], "model": row[2]}


async def log_request(input_type: str, source_name: str, model: str, duration: float,
                      original_size: int, output_size: int, status: str,
                      error_message: str, chunk_count: int):
    async with get_db() as db:
        await db.execute(
            """INSERT INTO request_log
            (timestamp, input_type, source_name, model, duration, original_size, output_size, status, error_message, chunk_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (time.time(), input_type, source_name, model, duration, original_size, output_size, status, error_message, chunk_count),
        )
        await db.commit()
