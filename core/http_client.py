"""Async HTTP client with retry logic."""
import asyncio
import json
from typing import Optional, Any, Dict
import aiohttp
from config.settings import DEBUG_MODE

class HttpClient:
    """Async HTTP client with retry logic and rate limiting."""
    
    def __init__(self, timeout: int = 25, concurrency: int = 12, retries: int = 2):
        self.timeout = timeout
        self.retries = retries
        self.semaphore = asyncio.Semaphore(concurrency)
        self.session: Optional[aiohttp.ClientSession] = None
        self.default_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Accept-Language": "nl-NL,nl;q=0.9,en;q=0.6",
        }

    async def __aenter__(self):
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        self.session = aiohttp.ClientSession(timeout=timeout, headers=self.default_headers)
        return self

    async def __aexit__(self, *exc):
        if self.session:
            await self.session.close()

    async def _request_with_retry(self, method: str, url: str, **kwargs) -> Optional[Any]:
        """Execute HTTP request with retry logic."""
        headers = dict(self.default_headers)
        if kwargs.get("headers"):
            headers.update(kwargs["headers"])
        kwargs["headers"] = headers

        for attempt in range(self.retries + 1):
            try:
                async with self.semaphore:
                    async with self.session.request(method, url, **kwargs) as resp:
                        if resp.status == 200:
                            try:
                                return await resp.json(content_type=None)
                            except Exception:
                                text = await resp.text()
                                try:
                                    return json.loads(text)
                                except Exception:
                                    return None
                        elif resp.status in (204, 304, 404):
                            return None
                        await resp.text()
                        return None
            except Exception as e:
                if DEBUG_MODE:
                    print(f"Request failed (attempt {attempt + 1}): {e}")
                if attempt < self.retries:
                    await asyncio.sleep(0.5 * (attempt + 1))
        return None

    async def get(self, url: str, params: Optional[Dict] = None, headers: Optional[Dict] = None) -> Optional[Any]:
        return await self._request_with_retry("GET", url, params=params, headers=headers)

    async def post_json(self, url: str, json_body: Any, headers: Optional[Dict] = None) -> Optional[Any]:
        return await self._request_with_retry("POST", url, json=json_body, headers=headers)