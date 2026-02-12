from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential


@dataclass
class HttpClient:
    base_url: str
    api_token: Optional[str] = None
    rate_limit_rps: float = 1.0
    user_agent: str = "MoltbookAcademicBot/0.1"
    timeout: float = 30.0

    def __post_init__(self) -> None:
        self._last_request_ts = 0.0
        self._client = httpx.Client(timeout=self.timeout)

    def _sleep_if_needed(self) -> None:
        min_interval = 1.0 / max(self.rate_limit_rps, 0.01)
        elapsed = time.time() - self._last_request_ts
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)

    def _headers(self) -> Dict[str, str]:
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json, text/html;q=0.9",
        }
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        return headers

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> httpx.Response:
        self._sleep_if_needed()
        url = self.base_url.rstrip("/") + "/" + path.lstrip("/")
        resp = self._client.get(url, headers=self._headers(), params=params)
        self._last_request_ts = time.time()
        resp.raise_for_status()
        return resp

    def close(self) -> None:
        self._client.close()
