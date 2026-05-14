import httpx
import logging
from typing import Optional, List, Dict, Any
from app.config import settings

logger = logging.getLogger(__name__)

class D1Client:
    def __init__(self):
        self.account_id = settings.cf_account_id
        self.db_id = settings.cf_database_id
        self.api_token = settings.cf_api_token
        self.base_url = f"https://api.cloudflare.com/client/v4/accounts/{self.account_id}/d1/database/{self.db_id}/query"
        self.headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }

    async def execute(self, sql: str, params: Optional[List[Any]] = None) -> List[Dict[str, Any]]:
        if not self.account_id or not self.db_id or not self.api_token:
            logger.error("Cloudflare D1 credentials are not fully configured.")
            return []

        payload = {
            "sql": sql,
            "params": params or []
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self.base_url,
                    headers=self.headers,
                    json=payload,
                    timeout=10.0
                )
                response.raise_for_status()
                data = response.json()
                
                if data.get("success") and data.get("result") and len(data["result"]) > 0:
                    return data["result"][0].get("results", [])
                else:
                    logger.warning(f"D1 query returned unexpected format or failed: {data}")
                    return []
            except httpx.HTTPStatusError as e:
                logger.error(f"D1 HTTP Error: {e.response.text}")
                return []
            except Exception as e:
                logger.error(f"D1 Connection Error: {e}")
                return []

d1 = D1Client()

async def init_db():
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        hash TEXT UNIQUE,
        content_type TEXT,
        body TEXT,
        media_path TEXT,
        og_title TEXT,
        og_description TEXT,
        og_image_path TEXT,
        deleted INTEGER DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """
    await d1.execute(create_table_sql)
