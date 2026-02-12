#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import subprocess
import time
import urllib.parse
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

import httpx


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def to_timestamp(value: Optional[str]) -> float:
    if not value:
        return 0.0
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def atomic_write_json(path: Path, payload: Dict[str, Any]) -> None:
    ensure_dir(path.parent)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def append_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    ensure_dir(path.parent)
    with path.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_json(path: Path, default: Dict[str, Any]) -> Dict[str, Any]:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def load_seen_ids(path: Path, key: str = "id") -> Set[str]:
    seen: Set[str] = set()
    if not path.exists():
        return seen
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                val = obj.get(key)
                if isinstance(val, str) and val:
                    seen.add(val)
            except json.JSONDecodeError:
                continue
    return seen


LIST_KEYS = ("data", "results", "items", "posts", "comments", "submolts")


def extract_list(payload: Any) -> List[Dict[str, Any]]:
    rows, _ = extract_list_and_flag(payload)
    return rows


def extract_list_and_flag(payload: Any) -> Tuple[List[Dict[str, Any]], bool]:
    if isinstance(payload, list):
        return payload, True
    if isinstance(payload, dict):
        for key in LIST_KEYS:
            if key in payload and isinstance(payload[key], list):
                return payload[key], True
    return [], False


def extract_has_more(payload: Any) -> Optional[bool]:
    if isinstance(payload, dict):
        pagination = payload.get("pagination")
        if isinstance(pagination, dict) and "hasMore" in pagination:
            return bool(pagination.get("hasMore"))
    return None


def flatten_comments(
    comments: List[Dict[str, Any]],
    post_id: str,
    parent_id: Optional[str] = None,
    depth: int = 0,
    thread_path: Optional[str] = None,
    out: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    if out is None:
        out = []
    for c in comments or []:
        if not isinstance(c, dict):
            continue
        cid = c.get("id")
        if post_id and not c.get("post_id"):
            c["post_id"] = post_id
        if parent_id and not c.get("parent_id"):
            c["parent_id"] = parent_id
        if "depth" not in c:
            c["depth"] = depth
        if "thread_path" not in c:
            base = thread_path or post_id or ""
            if base and cid:
                c["thread_path"] = f"{base}/{cid}"
            elif base:
                c["thread_path"] = base
            elif cid:
                c["thread_path"] = cid
        replies = c.get("replies") if isinstance(c.get("replies"), list) else []
        if "replies" in c:
            c.pop("replies", None)
        out.append(c)
        if replies:
            next_parent = cid or parent_id
            next_path = c.get("thread_path") or thread_path
            flatten_comments(
                replies,
                post_id=post_id,
                parent_id=next_parent,
                depth=depth + 1,
                thread_path=next_path,
                out=out,
            )
    return out


def extract_submolt_name(item: Dict[str, Any]) -> Optional[str]:
    for key in ("name", "slug", "id"):
        val = item.get(key)
        if isinstance(val, str) and val:
            return val
    return None


def parse_submolt_list(value: Optional[str]) -> Optional[List[str]]:
    if not value:
        return None
    p = Path(value)
    if p.exists():
        lines = [line.strip() for line in p.read_text(encoding="utf-8").splitlines()]
        return [line for line in lines if line]
    return [s.strip() for s in value.split(",") if s.strip()]


def pagination_start(mode: str) -> int:
    return 1 if mode == "page" else 0


@dataclass
class Pagination:
    mode: str
    limit: int
    start: int

    def params(self, cursor: int) -> Dict[str, Any]:
        if self.mode == "limit":
            return {"limit": self.limit}
        if self.mode == "page":
            return {"limit": self.limit, "page": cursor}
        return {"limit": self.limit, "offset": cursor}

    def next_cursor(self, cursor: int, count: int) -> int:
        if self.mode == "limit":
            return cursor
        if self.mode == "page":
            return cursor + 1
        step = count if count > 0 else self.limit
        return cursor + step


class AsyncRateLimiter:
    def __init__(self, rps: float) -> None:
        self._rps = max(rps, 0.01)
        self._lock = asyncio.Lock()
        self._last_ts = 0.0

    async def wait(self) -> None:
        async with self._lock:
            min_interval = 1.0 / self._rps
            now = time.perf_counter()
            elapsed = now - self._last_ts
            if elapsed < min_interval:
                await asyncio.sleep(min_interval - elapsed)
            self._last_ts = time.perf_counter()


class ApiFetcher:
    def __init__(self, args: argparse.Namespace) -> None:
        self.base_url = args.base_url.rstrip("/")
        self.token = args.token
        self.user_agent = args.user_agent
        self.rate_limit_rps = args.rate_limit_rps
        self.out_dir = Path(args.out_dir)
        self.headers = self._build_headers(args.headers)
        self.submolt_page = Pagination(
            args.submolts_pagination,
            args.submolts_page_size,
            pagination_start(args.submolts_pagination if args.submolts_pagination != "auto" else "offset"),
        )
        self.submolt_posts_page = Pagination(
            args.submolt_posts_pagination,
            args.submolt_posts_page_size,
            pagination_start(args.submolt_posts_pagination if args.submolt_posts_pagination != "auto" else "page"),
        )
        self.global_posts_page = Pagination(
            args.global_posts_pagination,
            args.global_posts_page_size,
            pagination_start(args.global_posts_pagination if args.global_posts_pagination != "auto" else "page"),
        )
        self.comment_page = Pagination(
            args.comments_pagination,
            min(args.comments_page_size, 500),
            pagination_start(args.comments_pagination if args.comments_pagination != "auto" else "page"),
        )
        self.submolt_sorts = [s.strip() for s in args.submolt_sorts.split(",") if s.strip()]
        self.global_sorts = [s.strip() for s in args.global_sorts.split(",") if s.strip()]
        self.submolt_batch_size = args.submolt_batch_size
        self.max_submolts = args.max_submolts
        self.max_posts = args.max_posts
        self.max_comment_pages = args.max_comment_pages
        self.post_concurrency = max(1, args.post_concurrency)
        self.max_connections = max(1, args.max_connections)
        self.max_keepalive = max(1, args.max_keepalive)
        self.only_submolts = parse_submolt_list(args.only_submolts)
        self.force_submolts = args.force_submolts
        self.submolt_priority = args.submolt_priority
        self.skip_comments_when_zero = args.skip_comments_when_zero
        self.skip_comments = args.skip_comments
        self.comments_only = args.comments_only
        self.log_requests = args.log_requests
        self.run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.snapshot = args.snapshot
        self.max_pages_per_sort = args.max_pages_per_sort
        self.requeue_submolts = args.requeue_submolts
        self.http2 = args.http2
        self.trust_env = args.trust_env
        self.curl_fallback = args.curl_fallback
        self.preflight = not args.skip_preflight
        self.force_preflight = args.force_preflight
        self.continue_on_preflight_fail = args.continue_on_preflight_fail
        self.include_global = not args.no_global

        if self.snapshot:
            self.state_path = self.out_dir / f"state_snapshot_{self.run_id}.json"
        else:
            self.state_path = self.out_dir / "state.json"
        self.log_path = self.out_dir / "log.jsonl"
        self.errors_path = self.out_dir / "errors.jsonl"
        self.submolts_path = self.out_dir / "submolts.jsonl"
        self.posts_path = self.out_dir / "posts.jsonl"
        self.comments_path = self.out_dir / "comments.jsonl"
        self.comments_done_path = self.out_dir / "comments_done.jsonl"
        self.listings_path = self.out_dir / "listings.jsonl"
        self.preflight_dir = self.out_dir / "preflight"

        default_state = {
            "version": 1,
            "base_url": self.base_url,
            "started_at": now_iso(),
            "updated_at": now_iso(),
            "run_id": self.run_id,
            "preflight": {"done": False, "submolt": None, "post_id": None, "ts": None},
            "submolts": {"cursor": self.submolt_page.start, "done": False, "count": 0},
            "submolt_names": [],
            "submolt_progress": {},
            "global_posts": {"cursor": self.global_posts_page.start, "done": False, "sorts": {}},
            "counts": {"posts": 0, "comments": 0, "submolts": 0},
            "errors": {"count": 0, "last": None},
            "pagination": {},
            "submolt_posts_endpoint": None,
            "submolt_endpoint_by_name": {},
        }
        self.state = load_json(self.state_path, default_state)
        if "pagination" not in self.state:
            self.state["pagination"] = {}
        if "submolt_endpoint_by_name" not in self.state:
            self.state["submolt_endpoint_by_name"] = {}
        if "global_posts" not in self.state:
            self.state["global_posts"] = {"cursor": self.global_posts_page.start, "done": False, "sorts": {}}
        if "sorts" not in self.state["global_posts"]:
            self.state["global_posts"]["sorts"] = {}

        self.seen_posts = load_seen_ids(self.posts_path, key="id")
        self.seen_comments = load_seen_ids(self.comments_path, key="id")
        self.comments_done = load_seen_ids(self.comments_done_path, key="post_id")

        self.state_lock = asyncio.Lock()
        self.file_lock = asyncio.Lock()
        self.stop_event = asyncio.Event()
        self.post_sem = asyncio.Semaphore(self.post_concurrency)
        self.network_failures = 0
        self.network_lock = asyncio.Lock()

    def _build_headers(self, headers_path: Optional[str]) -> Dict[str, str]:
        headers = {
            "Accept": "application/json, text/html;q=0.9",
            "User-Agent": self.user_agent,
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if headers_path:
            p = Path(headers_path)
            extra = json.loads(p.read_text(encoding="utf-8"))
            for k, v in extra.items():
                if isinstance(k, str) and isinstance(v, str):
                    headers[k] = v
        return headers

    async def log_event(self, event: Dict[str, Any]) -> None:
        event = dict(event)
        event["ts"] = now_iso()
        async with self.file_lock:
            append_jsonl(self.log_path, [event])

    async def log_error(self, err: Dict[str, Any]) -> None:
        err = dict(err)
        err["ts"] = now_iso()
        async with self.file_lock:
            append_jsonl(self.errors_path, [err])
        async with self.state_lock:
            self.state["errors"]["count"] += 1
            self.state["errors"]["last"] = err
            self.state["updated_at"] = now_iso()
            atomic_write_json(self.state_path, self.state)
        await self._network_backoff_if_needed(err)

    async def _network_backoff_if_needed(self, err: Dict[str, Any]) -> None:
        msg = str(err.get("error") or "")
        if (
            "nodename nor servname" not in msg
            and "Name or service not known" not in msg
            and "Temporary failure in name resolution" not in msg
        ):
            return
        async with self.network_lock:
            self.network_failures += 1
            failures = self.network_failures
        wait_s = min(60, 5 * failures)
        await self.log_event({"event": "network_backoff", "wait_s": wait_s, "failures": failures})
        await asyncio.sleep(wait_s)

    async def save_state(self) -> None:
        async with self.state_lock:
            self.state["updated_at"] = now_iso()
            atomic_write_json(self.state_path, self.state)

    async def _set_pagination_mode(self, key: str, mode: str, pagination: Pagination) -> None:
        pagination.mode = mode
        self.state.setdefault("pagination", {})[key] = mode
        await self.save_state()

    async def _detect_pagination_mode(
        self,
        client: httpx.AsyncClient,
        limiter: AsyncRateLimiter,
        path: str,
        base_params: Dict[str, Any],
        page_size: int,
    ) -> str:
        params_page = dict(base_params)
        params_page.update({"limit": page_size, "page": 1})
        payload_page = await self.fetch_json(client, limiter, path, params=params_page)
        rows_page, has_page = extract_list_and_flag(payload_page) if payload_page else ([], False)

        params_offset = dict(base_params)
        params_offset.update({"limit": page_size, "offset": 0})
        payload_offset = await self.fetch_json(client, limiter, path, params=params_offset)
        rows_offset, has_offset = extract_list_and_flag(payload_offset) if payload_offset else ([], False)

        if has_page and not has_offset:
            return "page"
        if has_offset and not has_page:
            return "offset"
        if has_page and has_offset:
            return "offset" if len(rows_offset) >= len(rows_page) else "page"
        return "page"

    async def ensure_pagination_mode(
        self,
        key: str,
        pagination: Pagination,
        client: httpx.AsyncClient,
        limiter: AsyncRateLimiter,
        path: str,
        base_params: Dict[str, Any],
    ) -> str:
        if pagination.mode != "auto":
            await self._set_pagination_mode(key, pagination.mode, pagination)
            return pagination.mode
        stored = self.state.get("pagination", {}).get(key)
        if stored in ("page", "offset", "limit"):
            pagination.mode = stored
            return stored
        mode = await self._detect_pagination_mode(client, limiter, path, base_params, pagination.limit)
        await self._set_pagination_mode(key, mode, pagination)
        await self.log_event({"event": "pagination_resolved", "key": key, "mode": mode})
        return mode

    def _submolt_posts_path(self, endpoint: str, name: str) -> str:
        if endpoint == "feed":
            return f"/api/v1/submolts/{name}/feed"
        return "/api/v1/posts"

    def _submolt_posts_params(self, endpoint: str, name: str, sort: str) -> Dict[str, Any]:
        params = {"sort": sort}
        if endpoint == "posts":
            params["submolt"] = name
        return params

    async def resolve_submolt_posts_endpoint(
        self,
        name: str,
        client: httpx.AsyncClient,
        limiter: AsyncRateLimiter,
    ) -> str:
        per_submolt = self.state.get("submolt_endpoint_by_name", {})
        cached = per_submolt.get(name)
        if cached == "submolt":
            cached = None
        if cached in ("feed", "posts"):
            return cached
        sort = self.submolt_sorts[0] if self.submolt_sorts else "new"
        candidates = [
            ("feed", f"/api/v1/submolts/{name}/feed", {"sort": sort, "limit": 1}),
            ("posts", "/api/v1/posts", {"sort": sort, "limit": 1, "submolt": name}),
        ]
        for kind, path, params in candidates:
            payload = await self.fetch_json(client, limiter, path, params=params)
            if payload is None:
                continue
            _, has_list = extract_list_and_flag(payload)
            if has_list:
                self.state.setdefault("submolt_endpoint_by_name", {})[name] = kind
                await self.save_state()
                await self.log_event({"event": "submolt_endpoint_resolved", "endpoint": kind, "name": name})
                return kind
        await self.log_event({"event": "submolt_endpoint_fallback", "endpoint": "posts", "name": name})
        return "posts"

    async def fetch_json(
        self,
        client: httpx.AsyncClient,
        limiter: AsyncRateLimiter,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        max_retries: int = 3,
    ) -> Optional[Dict[str, Any]]:
        url = f"{self.base_url}/{path.lstrip('/')}"
        for attempt in range(1, max_retries + 1):
            try:
                await limiter.wait()
                t0 = time.perf_counter()
                resp = await client.get(url, params=params, headers=self.headers)
                elapsed = time.perf_counter() - t0
                resp.raise_for_status()
                data = resp.json()
                if self.log_requests:
                    await self.log_event(
                        {
                            "event": "request",
                            "path": path,
                            "params": params or {},
                            "status": resp.status_code,
                            "elapsed_s": round(elapsed, 3),
                        }
                    )
                async with self.network_lock:
                    self.network_failures = 0
                return data
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code if exc.response else None
                # For missing comment endpoints, skip retries and mark as not found
                if status == 404 and path.endswith("/comments"):
                    await self.log_error(
                        {
                            "event": "request_error",
                            "path": path,
                            "params": params or {},
                            "attempt": attempt,
                            "status": status,
                            "error": str(exc),
                            "skip": "comments_404",
                        }
                    )
                    return {"__not_found__": True}
                err_text = str(exc)
                await self.log_error(
                    {
                        "event": "request_error",
                        "path": path,
                        "params": params or {},
                        "attempt": attempt,
                        "status": status,
                        "error": err_text,
                    }
                )
                await asyncio.sleep(min(2 ** attempt, 8))
            except Exception as exc:
                err_text = str(exc)
                if self.curl_fallback and "nodename nor servname" in err_text:
                    data = await asyncio.to_thread(self._fetch_json_curl, url, params)
                    if data is not None:
                        if self.log_requests:
                            await self.log_event(
                                {
                                    "event": "request",
                                    "path": path,
                                    "params": params or {},
                                    "status": 200,
                                    "elapsed_s": None,
                                    "source": "curl",
                                }
                            )
                        async with self.network_lock:
                            self.network_failures = 0
                        return data
                await self.log_error(
                    {
                        "event": "request_error",
                        "path": path,
                        "params": params or {},
                        "attempt": attempt,
                        "error": err_text,
                    }
                )
                await asyncio.sleep(min(2 ** attempt, 8))
        return None

    def _fetch_json_curl(self, url: str, params: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if params:
            qs = urllib.parse.urlencode(params, doseq=True)
            if qs:
                url = f"{url}?{qs}"
        cmd = [
            "curl",
            "-sS",
            "--retry",
            "2",
            "--retry-all-errors",
            "--connect-timeout",
            "10",
            "--max-time",
            "20",
            url,
        ]
        for key, value in self.headers.items():
            cmd.extend(["-H", f"{key}: {value}"])
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
        except Exception:
            return None
        if result.returncode != 0:
            return None
        payload = (result.stdout or "").strip()
        if not payload:
            return None
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            return None

    async def run_preflight(self, client: httpx.AsyncClient, limiter: AsyncRateLimiter) -> bool:
        if self.state.get("preflight", {}).get("done") and not self.force_preflight:
            return True
        ensure_dir(self.preflight_dir)
        await self.ensure_pagination_mode("submolts", self.submolt_page, client, limiter, "/api/v1/submolts", {})
        payload = await self.fetch_json(
            client,
            limiter,
            "/api/v1/submolts",
            params=self.submolt_page.params(pagination_start(self.submolt_page.mode)),
        )
        if not payload:
            await self.log_error({"event": "preflight_failed", "reason": "no_submolts_payload"})
            return False
        submolts = extract_list(payload)
        if not submolts:
            await self.log_error({"event": "preflight_failed", "reason": "empty_submolts"})
            return False
        submolt = random.choice(submolts)
        submolt_name = extract_submolt_name(submolt)
        if not submolt_name:
            await self.log_error({"event": "preflight_failed", "reason": "submolt_no_name"})
            return False
        endpoint_kind = await self.resolve_submolt_posts_endpoint(submolt_name, client, limiter)
        sort = self.submolt_sorts[0] if self.submolt_sorts else "new"
        path = self._submolt_posts_path(endpoint_kind, submolt_name)
        params = self._submolt_posts_params(endpoint_kind, submolt_name, sort)
        params["limit"] = min(self.submolt_posts_page.limit, 25)
        submolt_payload = await self.fetch_json(client, limiter, path, params=params)
        if not submolt_payload:
            await self.log_error({"event": "preflight_failed", "reason": "submolt_fetch_failed"})
            return False
        (self.preflight_dir / f"submolt_posts_{endpoint_kind}_{submolt_name}.json").write_text(
            json.dumps(submolt_payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        posts = extract_list(submolt_payload)
        if not posts:
            await self.log_error({"event": "preflight_failed", "reason": "submolt_no_posts"})
            return False
        post = random.choice(posts)
        post_id = post.get("id") or post.get("post_id")
        if not post_id:
            await self.log_error({"event": "preflight_failed", "reason": "post_no_id"})
            return False
        detail = await self.fetch_json(client, limiter, f"/api/v1/posts/{post_id}")
        if not detail:
            await self.log_error({"event": "preflight_failed", "reason": "post_detail_failed"})
            return False
        (self.preflight_dir / f"post_{post_id}.json").write_text(
            json.dumps(detail, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        await self.ensure_pagination_mode(
            "comments",
            self.comment_page,
            client,
            limiter,
            f"/api/v1/posts/{post_id}/comments",
            {},
        )
        comments_payload = await self.fetch_json(
            client,
            limiter,
            f"/api/v1/posts/{post_id}/comments",
            params=self.comment_page.params(pagination_start(self.comment_page.mode)),
        )
        comments = extract_list(comments_payload) if comments_payload else None
        if not comments and isinstance(detail, dict):
            maybe = detail.get("comments")
            if isinstance(maybe, list):
                comments = maybe
        if isinstance(comments, list):
            (self.preflight_dir / f"comments_{post_id}.json").write_text(
                json.dumps(comments, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        self.state["preflight"] = {"done": True, "submolt": submolt_name, "post_id": post_id, "ts": now_iso()}
        await self.save_state()
        return True

    async def fetch_submolts(self, client: httpx.AsyncClient, limiter: AsyncRateLimiter) -> None:
        if self.state["submolts"]["done"]:
            return
        await self.ensure_pagination_mode("submolts", self.submolt_page, client, limiter, "/api/v1/submolts", {})
        cursor = self.state["submolts"].get("cursor")
        if not isinstance(cursor, int):
            cursor = pagination_start(self.submolt_page.mode)
        if cursor == 0 and self.submolt_page.mode == "page":
            cursor = 1
        while not self.stop_event.is_set():
            params = self.submolt_page.params(cursor)
            payload = await self.fetch_json(client, limiter, "/api/v1/submolts", params=params)
            if not payload:
                break
            rows = extract_list(payload)
            if not rows:
                self.state["submolts"]["done"] = True
                await self.save_state()
                break
            has_more = extract_has_more(payload)
            await self.log_event({"event": "submolts_page", "cursor": cursor, "count": len(rows)})
            async with self.file_lock:
                append_jsonl(self.submolts_path, rows)
            names = [n for n in (extract_submolt_name(r) for r in rows) if n]
            self.state["submolt_names"].extend([n for n in names if n not in self.state["submolt_names"]])
            self.state["counts"]["submolts"] += len(rows)
            self.state["submolts"]["count"] = self.state["counts"]["submolts"]
            cursor = self.submolt_page.next_cursor(cursor, len(rows))
            self.state["submolts"]["cursor"] = cursor
            self.state["submolts"].pop("offset", None)
            await self.save_state()
            if has_more is False:
                self.state["submolts"]["done"] = True
                await self.save_state()
                break
            if self.max_submolts and len(self.state["submolt_names"]) >= self.max_submolts:
                self.state["submolts"]["done"] = True
                await self.save_state()
                break
        if self.state["submolts"]["done"]:
            await self.log_event({"event": "submolts_done", "count": len(self.state["submolt_names"])})

    async def process_post(
        self,
        client: httpx.AsyncClient,
        limiter: AsyncRateLimiter,
        post_id: str,
        listing: Optional[Dict[str, Any]] = None,
        comment_count: Optional[int] = None,
    ) -> None:
        if not post_id:
            return
        if self.max_posts and self.state["counts"]["posts"] >= self.max_posts:
            self.stop_event.set()
            return
        if post_id not in self.seen_posts:
            detail = await self.fetch_json(client, limiter, f"/api/v1/posts/{post_id}")
            post_obj = None
            if isinstance(detail, dict):
                post_obj = detail.get("post") if isinstance(detail.get("post"), dict) else detail
                comments = detail.get("comments") if isinstance(detail.get("comments"), list) else None
                if comments and not self.skip_comments:
                    await self.write_comments(post_id, comments)
            if post_obj is None and listing is not None:
                post_obj = dict(listing)
                post_obj["_source"] = "listing"
            if post_obj is not None:
                post_obj["_scrape_ts"] = now_iso()
                post_obj["_run_id"] = self.run_id
                async with self.file_lock:
                    append_jsonl(self.posts_path, [post_obj])
                self.seen_posts.add(post_id)
                self.state["counts"]["posts"] += 1
                await self.save_state()
                if self.max_posts and self.state["counts"]["posts"] >= self.max_posts:
                    self.stop_event.set()
                    return
        if self.skip_comments:
            return
        if post_id not in self.comments_done:
            if self.skip_comments_when_zero and comment_count == 0:
                async with self.file_lock:
                    append_jsonl(self.comments_done_path, [{"post_id": post_id}])
                self.comments_done.add(post_id)
                return
            await self.fetch_comments(client, limiter, post_id)

    async def write_comments(self, post_id: str, comments: List[Dict[str, Any]]) -> None:
        ts = now_iso()
        flat = flatten_comments(comments, post_id=post_id)
        new_rows: List[Dict[str, Any]] = []
        for c in flat:
            if not isinstance(c, dict):
                continue
            if not c.get("post_id"):
                c["post_id"] = post_id
            if "_scrape_ts" not in c:
                c["_scrape_ts"] = ts
            c["_run_id"] = self.run_id
            cid = c.get("id")
            if isinstance(cid, str) and cid:
                if cid in self.seen_comments:
                    continue
                self.seen_comments.add(cid)
            new_rows.append(c)
        if not new_rows:
            return
        async with self.file_lock:
            append_jsonl(self.comments_path, new_rows)
        self.state["counts"]["comments"] += len(new_rows)
        await self.save_state()

    async def fetch_comments(self, client: httpx.AsyncClient, limiter: AsyncRateLimiter, post_id: str) -> None:
        await self.ensure_pagination_mode(
            "comments",
            self.comment_page,
            client,
            limiter,
            f"/api/v1/posts/{post_id}/comments",
            {},
        )
        if self.comment_page.mode == "limit":
            params = {"limit": self.comment_page.limit}
            payload = await self.fetch_json(
                client,
                limiter,
                f"/api/v1/posts/{post_id}/comments",
                params=params,
            )
            if payload and payload.get("__not_found__"):
                async with self.file_lock:
                    append_jsonl(self.comments_done_path, [{"post_id": post_id}])
                self.comments_done.add(post_id)
                return
            if payload:
                rows = extract_list(payload)
                if rows:
                    await self.write_comments(post_id, rows)
                async with self.file_lock:
                    append_jsonl(self.comments_done_path, [{"post_id": post_id}])
                self.comments_done.add(post_id)
            return
        cursor = pagination_start(self.comment_page.mode)
        page_idx = 0
        seen_ids: Set[str] = set()
        had_error = False
        while not self.stop_event.is_set():
            params = self.comment_page.params(cursor)
            payload = await self.fetch_json(
                client,
                limiter,
                f"/api/v1/posts/{post_id}/comments",
                params=params,
            )
            if payload and payload.get("__not_found__"):
                had_error = False
                break
            if not payload:
                had_error = True
                break
            rows = extract_list(payload)
            if not rows:
                break
            ids = [r.get("id") for r in rows if isinstance(r, dict) and r.get("id")]
            new_ids = [rid for rid in ids if rid not in seen_ids]
            if not new_ids and page_idx > 0:
                if self.comment_page.mode != "limit":
                    await self._set_pagination_mode("comments", "limit", self.comment_page)
                break
            seen_ids.update(new_ids)
            await self.write_comments(post_id, rows)
            cursor = self.comment_page.next_cursor(cursor, len(rows))
            page_idx += 1
            if self.max_comment_pages and page_idx >= self.max_comment_pages:
                break
        if self.stop_event.is_set():
            had_error = True
        if not had_error:
            async with self.file_lock:
                append_jsonl(self.comments_done_path, [{"post_id": post_id}])
            self.comments_done.add(post_id)

    async def process_submolt(
        self,
        client: httpx.AsyncClient,
        limiter: AsyncRateLimiter,
        name: str,
    ) -> None:
        progress = self.state["submolt_progress"].setdefault(name, {"sorts": {}, "done": False})
        endpoint_kind = await self.resolve_submolt_posts_endpoint(name, client, limiter)
        first_sort = self.submolt_sorts[0] if self.submolt_sorts else "new"
        base_params = self._submolt_posts_params(endpoint_kind, name, first_sort)
        path = self._submolt_posts_path(endpoint_kind, name)
        await self.ensure_pagination_mode(
            "submolt_posts",
            self.submolt_posts_page,
            client,
            limiter,
            path,
            base_params,
        )
        for sort in self.submolt_sorts or ["new"]:
            sort_state = progress["sorts"].setdefault(sort, {"done": False})
            if sort_state["done"]:
                continue
            cursor = sort_state.get("cursor")
            if not isinstance(cursor, int):
                cursor = pagination_start(self.submolt_posts_page.mode)
            if cursor == 0 and self.submolt_posts_page.mode == "page":
                cursor = 1
            seen_ids: Set[str] = set()
            page_idx = 0
            while not self.stop_event.is_set():
                params = self.submolt_posts_page.params(cursor)
                params.update(self._submolt_posts_params(endpoint_kind, name, sort))
                payload = await self.fetch_json(
                    client,
                    limiter,
                    path,
                    params=params,
                )
                if not payload:
                    if page_idx == 0:
                        sort_state["done"] = True
                        sort_state["failed"] = True
                        await self.log_event(
                            {"event": "submolt_failed", "submolt": name, "sort": sort, "reason": "fetch_failed"}
                        )
                    else:
                        sort_state["done"] = False
                    break
                rows = extract_list(payload)
                if not rows:
                    sort_state["done"] = True
                    break
                has_more = extract_has_more(payload)
                batch_ts = now_iso()
                listing_rows: List[Dict[str, Any]] = []
                ids = [r.get("id") or r.get("post_id") for r in rows if isinstance(r, dict)]
                new_ids = [rid for rid in ids if rid and rid not in seen_ids]
                if not new_ids and page_idx > 0:
                    sort_state["done"] = True
                    break
                seen_ids.update(new_ids)
                await self.log_event(
                    {"event": "submolt_page", "submolt": name, "sort": sort, "cursor": cursor, "count": len(rows)}
                )
                tasks: List[asyncio.Task] = []
                for idx, row in enumerate(rows):
                    post_id = row.get("id") or row.get("post_id") if isinstance(row, dict) else None
                    if post_id:
                        comment_count = row.get("comment_count") if isinstance(row, dict) else None
                        listing_rows.append(
                            {
                                "post_id": post_id,
                                "submolt": name,
                                "sort": sort,
                                "endpoint": endpoint_kind,
                                "cursor": cursor,
                                "rank": idx + 1,
                                "scrape_ts": batch_ts,
                                "run_id": self.run_id,
                                "snapshot": self.snapshot,
                                "score": row.get("upvotes") if isinstance(row, dict) else None,
                                "comment_count": row.get("comment_count") if isinstance(row, dict) else None,
                                "created_at": row.get("created_at") if isinstance(row, dict) else None,
                            }
                        )
                        if not (post_id in self.seen_posts and post_id in self.comments_done):
                            tasks.append(
                                asyncio.create_task(
                                    self._process_post_guarded(
                                        client, limiter, str(post_id), listing=row, comment_count=comment_count
                                    )
                                )
                            )
                    if self.stop_event.is_set():
                        break
                if tasks:
                    await asyncio.gather(*tasks)
                if listing_rows:
                    async with self.file_lock:
                        append_jsonl(self.listings_path, listing_rows)
                cursor = self.submolt_posts_page.next_cursor(cursor, len(rows))
                sort_state["cursor"] = cursor
                await self.save_state()
                page_idx += 1
                if self.max_pages_per_sort and page_idx >= self.max_pages_per_sort:
                    sort_state["done"] = True
                    break
                if has_more is False:
                    sort_state["done"] = True
                    break
                if self.stop_event.is_set():
                    break
            if self.stop_event.is_set():
                break
        if self.stop_event.is_set():
            progress["done"] = False
        else:
            progress["done"] = all(s.get("done") for s in progress.get("sorts", {}).values())
        await self.save_state()

    async def process_global_posts(self, client: httpx.AsyncClient, limiter: AsyncRateLimiter) -> None:
        if not self.include_global or self.state["global_posts"]["done"]:
            return
        await self.ensure_pagination_mode("global_posts", self.global_posts_page, client, limiter, "/api/v1/posts", {})
        gp_state = self.state["global_posts"]
        for sort in self.global_sorts or ["hot"]:
            sort_state = gp_state["sorts"].setdefault(sort, {"done": False})
            if sort_state.get("done"):
                continue
            cursor = sort_state.get("cursor")
            if not isinstance(cursor, int):
                cursor = pagination_start(self.global_posts_page.mode)
            if cursor == 0 and self.global_posts_page.mode == "page":
                cursor = 1
            seen_ids: Set[str] = set()
            page_idx = 0
            while not self.stop_event.is_set():
                params = self.global_posts_page.params(cursor)
                params.update({"sort": sort})
                payload = await self.fetch_json(client, limiter, "/api/v1/posts", params=params)
                if not payload:
                    if page_idx == 0:
                        sort_state["done"] = True
                        sort_state["failed"] = True
                        await self.log_event({"event": "global_posts_failed", "sort": sort})
                    break
                rows = extract_list(payload)
                if not rows:
                    sort_state["done"] = True
                    break
                has_more = extract_has_more(payload)
                batch_ts = now_iso()
                listing_rows: List[Dict[str, Any]] = []
                ids = [r.get("id") or r.get("post_id") for r in rows if isinstance(r, dict)]
                new_ids = [rid for rid in ids if rid and rid not in seen_ids]
                if not new_ids and cursor != pagination_start(self.global_posts_page.mode):
                    sort_state["done"] = True
                    break
                seen_ids.update(new_ids)
                await self.log_event({"event": "global_posts_page", "cursor": cursor, "count": len(rows), "sort": sort})
                tasks: List[asyncio.Task] = []
                for idx, row in enumerate(rows):
                    post_id = row.get("id") or row.get("post_id") if isinstance(row, dict) else None
                    if post_id:
                        submolt_name = None
                        if isinstance(row, dict):
                            sm = row.get("submolt")
                            if isinstance(sm, dict):
                                submolt_name = sm.get("name")
                            elif isinstance(sm, str):
                                submolt_name = sm
                        listing_rows.append(
                            {
                                "post_id": post_id,
                                "submolt": submolt_name,
                                "sort": sort,
                                "endpoint": "posts",
                                "cursor": cursor,
                                "rank": idx + 1,
                                "scrape_ts": batch_ts,
                                "run_id": self.run_id,
                                "snapshot": self.snapshot,
                                "score": row.get("upvotes") if isinstance(row, dict) else None,
                                "comment_count": row.get("comment_count") if isinstance(row, dict) else None,
                                "created_at": row.get("created_at") if isinstance(row, dict) else None,
                            }
                        )
                        comment_count = row.get("comment_count") if isinstance(row, dict) else None
                        if not (post_id in self.seen_posts and post_id in self.comments_done):
                            tasks.append(
                                asyncio.create_task(
                                    self._process_post_guarded(
                                        client, limiter, str(post_id), listing=row, comment_count=comment_count
                                    )
                                )
                            )
                    if self.stop_event.is_set():
                        break
                if tasks:
                    await asyncio.gather(*tasks)
                if listing_rows:
                    async with self.file_lock:
                        append_jsonl(self.listings_path, listing_rows)
                cursor = self.global_posts_page.next_cursor(cursor, len(rows))
                sort_state["cursor"] = cursor
                await self.save_state()
                page_idx += 1
                if self.max_pages_per_sort and page_idx >= self.max_pages_per_sort:
                    sort_state["done"] = True
                    break
                if has_more is False:
                    sort_state["done"] = True
                    break
                if self.max_posts and self.state["counts"]["posts"] >= self.max_posts:
                    self.stop_event.set()
                    break
            if self.stop_event.is_set():
                break
        gp_state["done"] = all(s.get("done") for s in gp_state.get("sorts", {}).values())
        await self.save_state()
        if gp_state["done"]:
            await self.log_event({"event": "global_posts_done"})

    async def run(self) -> None:
        limiter = AsyncRateLimiter(self.rate_limit_rps)
        timeout = httpx.Timeout(30.0, connect=10.0)
        max_keepalive = min(self.max_keepalive, self.max_connections)
        limits = httpx.Limits(max_connections=self.max_connections, max_keepalive_connections=max_keepalive)
        use_http2 = False
        if self.http2:
            try:
                import h2  # noqa: F401

                use_http2 = True
            except Exception:
                use_http2 = False
                await self.log_event({"event": "http2_disabled", "reason": "h2_missing"})
        async with httpx.AsyncClient(
            timeout=timeout,
            limits=limits,
            http2=use_http2,
            trust_env=self.trust_env,
        ) as client:
            if self.comments_only:
                await self.run_comments_only(client, limiter)
                return
            if self.preflight:
                ok = await self.run_preflight(client, limiter)
                if not ok and not self.continue_on_preflight_fail:
                    return
            await self.fetch_submolts(client, limiter)
            if self.requeue_submolts:
                self.state["submolt_progress"] = {}
                await self.save_state()
            if self.force_submolts and self.only_submolts:
                for name in self.only_submolts:
                    self.state.get("submolt_progress", {}).pop(name, None)
                await self.save_state()
            submolts = list(self.state.get("submolt_names", []))
            if self.max_submolts:
                submolts = submolts[: self.max_submolts]
            if self.only_submolts:
                only = set(self.only_submolts)
                submolts = [s for s in submolts if s in only]
            submolts = self._prioritize_submolts(submolts)
            todo = [s for s in submolts if not self.state["submolt_progress"].get(s, {}).get("done")]
            queue: asyncio.Queue[str] = asyncio.Queue()
            for name in todo:
                queue.put_nowait(name)

            async def worker() -> None:
                while not self.stop_event.is_set():
                    try:
                        name = queue.get_nowait()
                    except asyncio.QueueEmpty:
                        return
                    try:
                        await self.process_submolt(client, limiter, name)
                    finally:
                        queue.task_done()

            workers = [asyncio.create_task(worker()) for _ in range(max(1, self.submolt_batch_size))]
            await queue.join()
            for w in workers:
                w.cancel()
            await self.process_global_posts(client, limiter)

    async def run_comments_only(self, client: httpx.AsyncClient, limiter: AsyncRateLimiter) -> None:
        posts: List[Tuple[str, Optional[int]]] = []
        if not self.posts_path.exists():
            return
        only = set(self.only_submolts) if self.only_submolts else None
        with self.posts_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                post_id = obj.get("id") or obj.get("post_id")
                if not isinstance(post_id, str):
                    continue
                if only is not None:
                    sm = obj.get("submolt")
                    if isinstance(sm, dict):
                        sm = sm.get("name") or sm.get("display_name") or sm.get("id")
                    if isinstance(sm, str):
                        sm_name = sm
                    else:
                        sm_name = None
                    if sm_name not in only:
                        continue
                comment_count = obj.get("comment_count")
                try:
                    comment_count = int(comment_count) if comment_count is not None else None
                except Exception:
                    comment_count = None
                if post_id in self.comments_done:
                    continue
                if self.skip_comments_when_zero and comment_count == 0:
                    continue
                posts.append((post_id, comment_count))

        queue: asyncio.Queue[Tuple[str, Optional[int]]] = asyncio.Queue()
        for item in posts:
            queue.put_nowait(item)

        async def worker() -> None:
            while not self.stop_event.is_set():
                try:
                    post_id, comment_count = queue.get_nowait()
                except asyncio.QueueEmpty:
                    return
                try:
                    await self.fetch_comments(client, limiter, post_id)
                finally:
                    queue.task_done()

        workers = [asyncio.create_task(worker()) for _ in range(max(1, self.post_concurrency))]
        await queue.join()
        for w in workers:
            w.cancel()

    async def _process_post_guarded(
        self,
        client: httpx.AsyncClient,
        limiter: AsyncRateLimiter,
        post_id: str,
        listing: Optional[Dict[str, Any]] = None,
        comment_count: Optional[int] = None,
    ) -> None:
        async with self.post_sem:
            await self.process_post(client, limiter, post_id, listing=listing, comment_count=comment_count)

    def _load_submolt_meta(self) -> Dict[str, Dict[str, Any]]:
        meta: Dict[str, Dict[str, Any]] = {}
        if not self.submolts_path.exists():
            return meta
        with self.submolts_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                name = extract_submolt_name(obj)
                if not name:
                    continue
                meta[name] = {
                    "subscriber_count": obj.get("subscriber_count") or 0,
                    "last_activity_at": obj.get("last_activity_at"),
                }
        return meta

    def _prioritize_submolts(self, names: List[str]) -> List[str]:
        if self.submolt_priority == "none":
            return names
        meta = self._load_submolt_meta()

        def sort_key(name: str) -> Tuple[float, float]:
            info = meta.get(name, {})
            subs = float(info.get("subscriber_count") or 0)
            last_act = to_timestamp(info.get("last_activity_at"))
            if self.submolt_priority == "last_activity":
                return (last_act, subs)
            return (subs, last_act)

        return sorted(names, key=sort_key, reverse=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch Moltbook API content with resume support.")
    parser.add_argument("--base-url", default=os.getenv("MOLTBOOK_BASE_URL", "https://www.moltbook.com"))
    parser.add_argument("--token", default=os.getenv("MOLTBOOK_API_TOKEN"))
    parser.add_argument(
        "--user-agent",
        default=os.getenv("MOLTBOOK_USER_AGENT", "MoltbookAcademicBot/0.1 (contact: research@example.org)"),
    )
    parser.add_argument("--rate-limit-rps", type=float, default=float(os.getenv("MOLTBOOK_RATE_LIMIT_RPS", "1.0")))
    parser.add_argument("--headers", default=None, help="Path to JSON file with extra headers")
    parser.add_argument("--out-dir", default="data/raw/api_fetch")
    parser.add_argument("--run-id", default=None, help="Override run identifier used in outputs")
    parser.add_argument("--snapshot", action="store_true", help="Use snapshot state file and tag run_id")
    parser.add_argument("--max-pages-per-sort", type=int, default=0, help="0 = unlimited")

    parser.add_argument("--submolts-page-size", type=int, default=100)
    parser.add_argument("--submolts-pagination", choices=["offset", "page", "auto"], default="offset")
    parser.add_argument("--submolt-posts-page-size", type=int, default=100)
    parser.add_argument("--submolt-posts-pagination", choices=["offset", "page", "auto"], default="offset")
    parser.add_argument("--submolt-sorts", default="new,hot,top")
    parser.add_argument("--submolt-batch-size", type=int, default=6)
    parser.add_argument("--post-concurrency", type=int, default=8)
    parser.add_argument(
        "--max-connections",
        type=int,
        default=int(os.getenv("MOLTBOOK_MAX_CONNECTIONS", "100")),
        help="Max total HTTP connections (httpx).",
    )
    parser.add_argument(
        "--max-keepalive",
        type=int,
        default=int(os.getenv("MOLTBOOK_MAX_KEEPALIVE", "50")),
        help="Max keep-alive HTTP connections (httpx).",
    )
    parser.add_argument(
        "--only-submolts",
        default=None,
        help="Comma-separated list or path to file with submolt names to process.",
    )
    parser.add_argument(
        "--force-submolts",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="If set with --only-submolts, clears progress for those submolts.",
    )
    parser.add_argument(
        "--submolt-priority",
        choices=["subscriber_count", "last_activity", "none"],
        default="subscriber_count",
    )
    parser.add_argument(
        "--skip-comments-when-zero",
        action=argparse.BooleanOptionalAction,
        default=True,
    )

    parser.add_argument("--global-posts-page-size", type=int, default=100)
    parser.add_argument("--global-posts-pagination", choices=["offset", "page", "auto"], default="offset")
    parser.add_argument("--global-sorts", default="new,hot,top")
    parser.add_argument("--comments-page-size", type=int, default=500)
    parser.add_argument("--comments-pagination", choices=["offset", "page", "auto", "limit"], default="limit")
    parser.add_argument("--max-comment-pages", type=int, default=0, help="0 = unlimited")
    parser.add_argument(
        "--requeue-submolts",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Clear submolt progress and reprocess all submolts.",
    )
    parser.add_argument(
        "--skip-comments",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Skip all comment fetches during post crawl (faster).",
    )
    parser.add_argument(
        "--comments-only",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Only fetch comments for posts already in posts.jsonl.",
    )
    parser.add_argument(
        "--http2",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable HTTP/2 if h2 is installed.",
    )
    parser.add_argument(
        "--trust-env",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Allow httpx to read proxy settings from the environment.",
    )
    parser.add_argument(
        "--curl-fallback",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Use curl as a fallback when httpx fails to resolve DNS.",
    )

    parser.add_argument(
        "--log-requests",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Write per-request events to log.jsonl (can be I/O heavy).",
    )

    parser.add_argument("--max-submolts", type=int, default=0, help="0 = unlimited")
    parser.add_argument("--max-posts", type=int, default=0, help="0 = unlimited")
    parser.add_argument("--no-global", action="store_true", help="Skip global /posts crawl")

    parser.add_argument("--skip-preflight", action="store_true")
    parser.add_argument("--force-preflight", action="store_true")
    parser.add_argument("--continue-on-preflight-fail", action="store_true")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.max_comment_pages < 0:
        args.max_comment_pages = 0
    fetcher = ApiFetcher(args)
    asyncio.run(fetcher.run())


if __name__ == "__main__":
    main()
