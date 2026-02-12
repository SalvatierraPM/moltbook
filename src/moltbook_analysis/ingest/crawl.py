from __future__ import annotations

import csv
import json
import re
import time
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from bs4 import BeautifulSoup

from moltbook_analysis.ingest.html import parse_posts_from_html, _parse_relative_time


VIEW_RE = re.compile(r"(\d[\d,\.]*)\s*views?", re.IGNORECASE)
COMMENT_RE = re.compile(r"(\d[\d,\.]*)\s*comments?", re.IGNORECASE)


@dataclass
class CrawlConfig:
    base_url: str
    user_agent: str
    max_scrolls: int = 12
    wait_ms: int = 1200
    rate_ms: int = 300
    max_posts: int = 0
    max_post_pages: int = 0
    max_submolts: int = 0
    max_comments: int = 0
    headless: bool = True
    include_submolts: bool = True
    submolt_scrolls: int = 15
    filters: Tuple[str, ...] = ("Random", "New", "Top", "Discussed")
    dump_html: Optional[str] = None
    dump_screenshot: Optional[str] = None
    dump_every_page: bool = False
    stream_dir: Optional[str] = None
    log_every_posts: int = 50
    log_every_comments: int = 200
    log_post_pages: bool = False
    log_block_times: bool = True
    log_urls: bool = False
    log_file: Optional[str] = None
    metrics_csv: Optional[str] = None
    errors_jsonl: Optional[str] = None
    netlog_path: Optional[str] = None
    netlog_types: Tuple[str, ...] = ("xhr", "fetch")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_int(text: str) -> Optional[int]:
    if not text:
        return None
    digits = re.sub(r"[^0-9]", "", text)
    return int(digits) if digits else None


def _extract_views(text: str) -> Optional[int]:
    m = VIEW_RE.search(text or "")
    if not m:
        return None
    return _parse_int(m.group(1))


def _extract_comment_count(text: str) -> Optional[int]:
    m = COMMENT_RE.search(text or "")
    if not m:
        return None
    return _parse_int(m.group(1))


def _extract_submolt_paths(html: str) -> List[str]:
    soup = BeautifulSoup(html, "lxml")
    paths: Set[str] = set()
    for a in soup.find_all("a", href=True):
        href = a.get("href") or ""
        if href.startswith("/m/"):
            paths.add(href)
    return sorted(paths)


def _collect_submolts(page, cfg: CrawlConfig) -> List[str]:
    seen: Set[str] = set()
    no_new_rounds = 0
    more_patterns = [
        "show all",
        "view all",
        "see all",
        "all",
        "load more",
        "show more",
        "more",
        "mostrar",
        "ver todos",
        "todos",
        "mas",
        "más",
    ]
    for i in range(cfg.submolt_scrolls):
        html = page.content()
        new = _extract_submolt_paths(html)
        prev = len(seen)
        seen.update(new)
        if len(seen) == prev:
            no_new_rounds += 1
        else:
            no_new_rounds = 0
        if no_new_rounds >= 2:
            break
        # Try "show all"/"load more"/"mostrar todos" if present
        for pat in more_patterns:
            try:
                page.locator("button,a", has_text=re.compile(pat, re.I)).first.click(timeout=1000)
                break
            except Exception:
                continue
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(cfg.wait_ms)
    out = sorted(seen)
    if cfg.max_submolts and cfg.max_submolts > 0:
        out = out[: cfg.max_submolts]
    return out


def _safe_slug(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_")
    return slug[:80] if slug else "page"


class CrawlLogger:
    def __init__(self, path: Optional[str]) -> None:
        self._fh = Path(path).open("a", encoding="utf-8") if path else None

    def info(self, msg: str) -> None:
        print(msg)
        if self._fh:
            self._fh.write(msg + "\n")
            self._fh.flush()

    def close(self) -> None:
        if self._fh:
            self._fh.close()


class MetricsWriter:
    def __init__(self, path: Optional[str]) -> None:
        self._fh = None
        self._writer = None
        if path:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            self._fh = Path(path).open("a", encoding="utf-8", newline="")
            self._writer = csv.DictWriter(
                self._fh,
                fieldnames=["ts", "event", "url", "duration_s", "count", "extra"],
            )
            if self._fh.tell() == 0:
                self._writer.writeheader()

    def write(self, event: Dict) -> None:
        if not self._writer:
            return
        self._writer.writerow(event)
        self._fh.flush()

    def close(self) -> None:
        if self._fh:
            self._fh.close()


def _write_error(path: Optional[str], payload: Dict) -> None:
    if not path:
        return
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _click_filter(page, label: str) -> bool:
    if not label:
        return False
    pattern = re.compile(label, re.IGNORECASE)
    try:
        page.get_by_role("button", name=pattern).click(timeout=4000)
        return True
    except Exception:
        pass
    try:
        page.locator("button", has_text=pattern).first.click(timeout=4000)
        return True
    except Exception:
        return False


def _merge_post(existing: Dict, new: Dict) -> Dict:
    for k, v in new.items():
        if v is None or v == "":
            continue
        if k in ("source", "filter"):
            continue
        if existing.get(k) in (None, ""):
            existing[k] = v
    if new.get("source"):
        existing.setdefault("sources", [])
        if new["source"] not in existing["sources"]:
            existing["sources"].append(new["source"])
    if new.get("filter"):
        existing.setdefault("filters", [])
        if new["filter"] not in existing["filters"]:
            existing["filters"].append(new["filter"])
    if new.get("listing_rank") is not None:
        current = existing.get("listing_rank")
        if current is None or new["listing_rank"] < current:
            existing["listing_rank"] = new["listing_rank"]
    return existing


def _collect_listing_posts(
    page,
    url: str,
    cfg: CrawlConfig,
    source: str,
    filter_label: Optional[str],
    preloaded: bool = False,
) -> List[Dict]:
    if not preloaded:
        page.goto(url, wait_until="networkidle", timeout=60000)
    if filter_label:
        _click_filter(page, filter_label)
        page.wait_for_timeout(cfg.wait_ms)

    seen_ids: Set[str] = set()
    collected: List[Dict] = []
    no_new_rounds = 0

    for i in range(cfg.max_scrolls):
        html = page.content()
        if cfg.dump_every_page and cfg.dump_html:
            Path(cfg.dump_html).mkdir(parents=True, exist_ok=True)
            fname = _safe_slug(f"listing_{source}_{filter_label}_{i}") + ".html"
            (Path(cfg.dump_html) / fname).write_text(html, encoding="utf-8")
        posts = parse_posts_from_html(html)
        new_count = 0
        for idx, p in enumerate(posts):
            pid = p.get("id") or p.get("url")
            if not pid:
                continue
            if pid in seen_ids:
                continue
            seen_ids.add(pid)
            p["source"] = source
            if filter_label:
                p["filter"] = filter_label
            p["listing_rank"] = idx
            p["scrape_ts"] = _now_iso()
            collected.append(p)
            new_count += 1

            if cfg.max_posts and len(collected) >= cfg.max_posts:
                return collected

        if new_count == 0:
            no_new_rounds += 1
        else:
            no_new_rounds = 0
        if no_new_rounds >= 2:
            break

        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(cfg.wait_ms)
        time.sleep(cfg.rate_ms / 1000.0)

    return collected


def _parse_post_detail(html: str) -> Tuple[Dict, List[Dict]]:
    soup = BeautifulSoup(html, "lxml")
    text_all = " ".join(soup.get_text(" ", strip=True).split())

    title_el = soup.find("h1") or soup.find("h2")
    body_el = soup.find("article")
    if not body_el:
        body_el = soup.find("div", class_=lambda c: c and ("prose" in c or "content" in c))
    if not body_el:
        body_el = soup.find("p")

    author_name = None
    for a in soup.find_all("a", href=True):
        href = a.get("href") or ""
        if href.startswith("/u/") or "/user" in href:
            author_name = a.get_text(strip=True)
            if author_name:
                break

    created_at_raw = None
    created_at = None
    for span in soup.find_all("span"):
        t = span.get_text(" ", strip=True)
        if t and "ago" in t:
            created_at_raw = t
            created_at = _parse_relative_time(t)
            break

    detail = {
        "title": title_el.get_text(" ", strip=True) if title_el else None,
        "body": body_el.get_text(" ", strip=True) if body_el else None,
        "author_name": author_name,
        "created_at": created_at,
        "created_at_raw": created_at_raw,
        "comment_count": _extract_comment_count(text_all),
        "views": _extract_views(text_all),
    }

    comments = _parse_comments(soup)
    return detail, comments


def _parse_comments(soup: BeautifulSoup) -> List[Dict]:
    comments: List[Dict] = []
    candidates = soup.find_all(attrs={"data-comment-id": True})
    if not candidates:
        candidates = [
            el
            for el in soup.find_all(["div", "article"], class_=lambda c: c and "comment" in c)
            if el.find("p")
        ]

    for idx, el in enumerate(candidates):
        comment_id = el.get("data-comment-id") or f"c{idx}"
        body_el = el.find("p") or el.find("div", class_=lambda c: c and "content" in c)
        author = None
        for a in el.find_all("a", href=True):
            href = a.get("href") or ""
            if href.startswith("/u/") or "/user" in href:
                author = a.get_text(strip=True)
                if author:
                    break
        created_at_raw = None
        created_at = None
        for span in el.find_all("span"):
            t = span.get_text(" ", strip=True)
            if t and "ago" in t:
                created_at_raw = t
                created_at = _parse_relative_time(t)
                break

        comments.append(
            {
                "id": comment_id,
                "body": body_el.get_text(" ", strip=True) if body_el else None,
                "author_name": author,
                "created_at": created_at,
                "created_at_raw": created_at_raw,
            }
        )

    return comments


def crawl_site(cfg: CrawlConfig) -> Tuple[List[Dict], List[Dict]]:
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "Playwright is not installed. Install with: pip install playwright && playwright install"
        ) from exc

    posts_by_id: Dict[str, Dict] = {}
    comments_out: List[Dict] = []

    stream_posts = None
    stream_comments = None
    if cfg.stream_dir:
        Path(cfg.stream_dir).mkdir(parents=True, exist_ok=True)
        stream_posts = (Path(cfg.stream_dir) / "posts_stream.jsonl").open("a", encoding="utf-8")
        stream_comments = (Path(cfg.stream_dir) / "comments_stream.jsonl").open("a", encoding="utf-8")

    def _stream_write(handle, obj: Dict) -> None:
        if not handle:
            return
        handle.write(json.dumps(obj, ensure_ascii=False) + "\n")
        handle.flush()

    logger = CrawlLogger(cfg.log_file)
    metrics = MetricsWriter(cfg.metrics_csv)

    netlog_handle = None
    if cfg.netlog_path:
        Path(cfg.netlog_path).parent.mkdir(parents=True, exist_ok=True)
        netlog_handle = Path(cfg.netlog_path).open("a", encoding="utf-8")

    def _netlog_response(resp) -> None:
        if not netlog_handle:
            return
        try:
            req = resp.request
            rtype = req.resource_type
            if cfg.netlog_types and rtype not in cfg.netlog_types:
                return
            entry = {
                "ts": _now_iso(),
                "url": resp.url,
                "status": resp.status,
                "method": req.method,
                "resource_type": rtype,
                "content_type": resp.headers.get("content-type"),
            }
            netlog_handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
            netlog_handle.flush()
        except Exception:
            return

    def _safe_goto(page, url: str, label: str) -> bool:
        t0 = time.perf_counter()
        ok = True
        err = None
        try:
            page.goto(url, wait_until="networkidle", timeout=60000)
        except Exception as exc:
            ok = False
            err = exc
        dt = time.perf_counter() - t0
        metrics.write(
            {
                "ts": _now_iso(),
                "event": f"goto:{label}",
                "url": url,
                "duration_s": f"{dt:.2f}",
                "count": 1,
                "extra": "ok" if ok else "error",
            }
        )
        if cfg.log_urls:
            logger.info(f"[crawl] goto {url} ({dt:.1f}s) ok={ok}")
        if not ok:
            _write_error(
                cfg.errors_jsonl,
                {
                    "ts": _now_iso(),
                    "url": url,
                    "label": label,
                    "error": str(err),
                    "trace": traceback.format_exc(),
                },
            )
            if cfg.dump_screenshot:
                Path(cfg.dump_screenshot).mkdir(parents=True, exist_ok=True)
                fname = _safe_slug(label + "_" + url) + ".png"
                try:
                    page.screenshot(path=str(Path(cfg.dump_screenshot) / fname), full_page=True)
                except Exception:
                    pass
            if cfg.dump_html:
                Path(cfg.dump_html).mkdir(parents=True, exist_ok=True)
                fname = _safe_slug(label + "_" + url) + ".html"
                try:
                    (Path(cfg.dump_html) / fname).write_text(page.content(), encoding="utf-8")
                except Exception:
                    pass
        return ok

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=cfg.headless)
        context = browser.new_context(user_agent=cfg.user_agent)
        page = context.new_page()
        if netlog_handle:
            context.on("response", _netlog_response)

        # 1) Collect submolts
        submolts: List[str] = []
        if cfg.include_submolts:
            m_url = cfg.base_url.rstrip("/") + "/m"
            t0 = time.perf_counter()
            if _safe_goto(page, m_url, "submolts"):
                page.wait_for_timeout(cfg.wait_ms)
                submolts = _collect_submolts(page, cfg)
            if cfg.log_block_times:
                dt = time.perf_counter() - t0
                logger.info(f"[crawl] submolts={len(submolts)} in {dt:.1f}s")

        # 2) Collect listings from home and submolts
        entry_paths = ["/"] + submolts
        for path in entry_paths:
            url = cfg.base_url.rstrip("/") + path
            for flt in cfg.filters:
                logger.info(f"[crawl] listing source={path} filter={flt}")
                t0 = time.perf_counter()
                if not _safe_goto(page, url, f"listing:{path}:{flt}"):
                    continue
                posts = _collect_listing_posts(
                    page, url, cfg, source=path, filter_label=flt, preloaded=True
                )
                new_unique = 0
                for p in posts:
                    pid = p.get("id") or p.get("url")
                    if not pid:
                        continue
                    if pid not in posts_by_id:
                        posts_by_id[pid] = p
                        _stream_write(stream_posts, p)
                        new_unique += 1
                        if cfg.log_every_posts and len(posts_by_id) % cfg.log_every_posts == 0:
                            logger.info(f"[crawl] posts_collected={len(posts_by_id)}")
                    else:
                        posts_by_id[pid] = _merge_post(posts_by_id[pid], p)

                    if cfg.max_posts and len(posts_by_id) >= cfg.max_posts:
                        break
                if cfg.max_posts and len(posts_by_id) >= cfg.max_posts:
                    break
                if cfg.log_block_times:
                    dt = time.perf_counter() - t0
                    logger.info(
                        f"[crawl] listing done source={path} filter={flt} posts={len(posts)} new_unique={new_unique} in {dt:.1f}s"
                    )
                metrics.write(
                    {
                        "ts": _now_iso(),
                        "event": f"listing:{path}:{flt}",
                        "url": url,
                        "duration_s": f"{(time.perf_counter() - t0):.2f}",
                        "count": len(posts),
                        "extra": f"new_unique={new_unique}",
                    }
                )
            if cfg.max_posts and len(posts_by_id) >= cfg.max_posts:
                break

        # 3) Visit post pages for details and comments
        post_ids = list(posts_by_id.keys())
        if cfg.max_post_pages and cfg.max_post_pages > 0:
            post_ids = post_ids[: cfg.max_post_pages]

        t_posts = time.perf_counter()
        for idx, pid in enumerate(post_ids):
            url = cfg.base_url.rstrip("/") + "/post/" + pid.split("/post/")[-1]
            t0 = time.perf_counter()
            if not _safe_goto(page, url, "post"):
                continue
            page.wait_for_timeout(cfg.wait_ms)
            html = page.content()
            if cfg.dump_every_page and cfg.dump_html:
                Path(cfg.dump_html).mkdir(parents=True, exist_ok=True)
                fname = _safe_slug(f"post_{pid}") + ".html"
                (Path(cfg.dump_html) / fname).write_text(html, encoding="utf-8")

            detail, comments = _parse_post_detail(html)
            detail["scrape_ts"] = _now_iso()
            posts_by_id[pid] = _merge_post(posts_by_id[pid], detail)

            for c_idx, c in enumerate(comments):
                c["post_id"] = pid
                c["id"] = c.get("id") or f"{pid}:{c_idx}"
                c["scrape_ts"] = _now_iso()
                comments_out.append(c)
                _stream_write(stream_comments, c)
                if cfg.log_every_comments and len(comments_out) % cfg.log_every_comments == 0:
                    logger.info(f"[crawl] comments_collected={len(comments_out)}")
                if cfg.max_comments and len(comments_out) >= cfg.max_comments:
                    break

            if cfg.max_comments and len(comments_out) >= cfg.max_comments:
                break

            if cfg.log_post_pages:
                dt = time.perf_counter() - t0
                logger.info(
                    f"[crawl] post {idx+1}/{len(post_ids)} id={pid} comments={len(comments)} in {dt:.1f}s"
                )
            time.sleep(cfg.rate_ms / 1000.0)

        browser.close()

    if cfg.log_block_times:
        dt = time.perf_counter() - t_posts if post_ids else 0.0
        logger.info(
            f"[crawl] post detail phase posts={len(post_ids)} comments={len(comments_out)} in {dt:.1f}s"
        )

    if stream_posts:
        stream_posts.close()
    if stream_comments:
        stream_comments.close()
    if netlog_handle:
        netlog_handle.close()
    metrics.close()
    logger.close()

    return list(posts_by_id.values()), comments_out
