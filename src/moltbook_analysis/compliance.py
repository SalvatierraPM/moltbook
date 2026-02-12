from __future__ import annotations

from urllib import robotparser

import httpx

from moltbook_analysis.http_client import HttpClient


def robots_allows(client: HttpClient, path: str, allow_if_unavailable: bool = False) -> bool:
    try:
        resp = client.get("/robots.txt")
        content = resp.text.splitlines()
    except httpx.HTTPStatusError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            return allow_if_unavailable
        return allow_if_unavailable
    except Exception:
        return allow_if_unavailable

    rp = robotparser.RobotFileParser()
    rp.parse(content)
    url = client.base_url.rstrip("/") + "/" + path.lstrip("/")
    return rp.can_fetch(client.user_agent, url)
