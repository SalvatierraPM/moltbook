from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

import pandas as pd

from moltbook_analysis.config import get_settings
from moltbook_analysis.http_client import HttpClient
from moltbook_analysis.compliance import robots_allows
from moltbook_analysis.ingest.api import fetch_posts, fetch_post_comments, normalize_post, normalize_comment
from moltbook_analysis.ingest.html import (
    fetch_posts_html,
    fetch_posts_html_dynamic,
    parse_posts_from_html,
)
from moltbook_analysis.storage import write_jsonl, write_parquet
from moltbook_analysis.report.build import build_report
from moltbook_analysis.ingest.crawl import CrawlConfig, crawl_site


def _read_jsonl(path: Path) -> Iterable[dict]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)


def cmd_ingest(args: argparse.Namespace) -> None:
    s = get_settings()
    client = None
    if not args.local_html:
        client = HttpClient(
            base_url=s.base_url,
            api_token=s.api_token,
            rate_limit_rps=s.rate_limit_rps,
            user_agent=s.user_agent,
        )

    posts_raw = []
    comments_raw = []

    if args.local_html:
        import glob
        from pathlib import Path

        paths = []
        if Path(args.local_html).is_dir():
            paths = glob.glob(str(Path(args.local_html) / "*.html"))
        else:
            paths = [args.local_html]

        for p in paths:
            html = Path(p).read_text(encoding="utf-8")
            posts_raw.extend(parse_posts_from_html(html))
    elif args.source == "api":
        for row in fetch_posts(client, since=args.since, max_pages=args.max_pages, page_size=args.page_size):
            posts_raw.append(row)
            if args.comments:
                post_id = row.get("id") or row.get("post_id")
                if post_id:
                    for c in fetch_post_comments(client, str(post_id)):
                        if isinstance(c, dict) and not c.get("post_id"):
                            c["post_id"] = str(post_id)
                        comments_raw.append(c)
    else:
        if not robots_allows(client, args.path, allow_if_unavailable=args.allow_no_robots):
            print("robots.txt does not allow scraping this path (or unavailable). Aborting.")
            client.close()
            return
        if args.dynamic:
            for row in fetch_posts_html_dynamic(
                base_url=s.base_url,
                path=args.path,
                max_scrolls=args.max_scrolls,
                wait_ms=args.wait_ms,
                user_agent=s.user_agent,
                dump_dir=args.dump_html,
                screenshot_dir=args.dump_screenshot,
            ):
                posts_raw.append(row)
        else:
            for row in fetch_posts_html(
                client, path=args.path, max_pages=args.max_pages, dump_dir=args.dump_html
            ):
                posts_raw.append(row)

    if client:
        client.close()

    if posts_raw:
        write_jsonl(s.raw_dir / "posts.jsonl", posts_raw)
    if comments_raw:
        write_jsonl(s.raw_dir / "comments.jsonl", comments_raw)

    print(f"Ingested posts={len(posts_raw)} comments={len(comments_raw)}")


def cmd_normalize(_: argparse.Namespace) -> None:
    s = get_settings()
    posts_path = s.raw_dir / "posts.jsonl"
    comments_path = s.raw_dir / "comments.jsonl"

    posts = []
    if posts_path.exists():
        for row in _read_jsonl(posts_path):
            posts.append(normalize_post(row).model_dump())

    comments = []
    if comments_path.exists():
        for row in _read_jsonl(comments_path):
            comments.append(normalize_comment(row).model_dump())

    if posts:
        write_jsonl(s.normalized_dir / "posts.jsonl", posts)
        write_parquet(s.normalized_dir / "posts.parquet", posts)
    if comments:
        write_jsonl(s.normalized_dir / "comments.jsonl", comments)
        write_parquet(s.normalized_dir / "comments.parquet", comments)

    print(f"Normalized posts={len(posts)} comments={len(comments)}")


def cmd_analyze(_: argparse.Namespace) -> None:
    s = get_settings()
    posts_path = s.normalized_dir / "posts.parquet"
    if not posts_path.exists():
        print("No normalized posts found. Run normalize first.")
        return

    df = pd.read_parquet(posts_path)
    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
    daily = df.groupby(df["created_at"].dt.date).size().reset_index(name="count")
    daily.to_csv(s.derived_dir / "daily_counts.csv", index=False)
    print("Derived metrics saved.")


def cmd_report(_: argparse.Namespace) -> None:
    path = build_report()
    print(f"Report written to {path}")


def cmd_crawl(args: argparse.Namespace) -> None:
    s = get_settings()
    client = HttpClient(
        base_url=s.base_url,
        api_token=s.api_token,
        rate_limit_rps=s.rate_limit_rps,
        user_agent=s.user_agent,
    )
    if not robots_allows(client, "/", allow_if_unavailable=args.allow_no_robots):
        print("robots.txt does not allow scraping this path (or unavailable). Aborting.")
        client.close()
        return
    client.close()

    filters = tuple([f.strip() for f in args.filters.split(",") if f.strip()])
    cfg = CrawlConfig(
        base_url=s.base_url,
        user_agent=s.user_agent,
        max_scrolls=args.max_scrolls,
        wait_ms=args.wait_ms,
        rate_ms=args.rate_ms,
        max_posts=args.max_posts,
        max_post_pages=args.max_post_pages,
        max_submolts=args.max_submolts,
        max_comments=args.max_comments,
        headless=not args.headed,
        include_submolts=not args.no_submolts,
        submolt_scrolls=args.submolt_scrolls,
        filters=filters if filters else ("Random", "New", "Top", "Discussed"),
        stream_dir=args.stream_dir,
        log_post_pages=args.log_post_pages,
        log_urls=args.log_urls,
        log_file=args.log_file,
        metrics_csv=args.metrics_csv,
        errors_jsonl=args.errors_jsonl,
        netlog_path=args.netlog,
        netlog_types=tuple([t.strip() for t in args.netlog_types.split(",") if t.strip()]),
        dump_html=args.dump_html,
        dump_screenshot=args.dump_screenshot,
        dump_every_page=args.dump_every_page,
        log_every_posts=args.log_every_posts,
        log_every_comments=args.log_every_comments,
    )

    posts_raw, comments_raw = crawl_site(cfg)

    if posts_raw:
        write_jsonl(s.raw_dir / "posts.jsonl", posts_raw)
    if comments_raw:
        write_jsonl(s.raw_dir / "comments.jsonl", comments_raw)

    print(f"Crawled posts={len(posts_raw)} comments={len(comments_raw)}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Moltbook analysis toolkit")
    sub = parser.add_subparsers(dest="command", required=True)

    p_ingest = sub.add_parser("ingest", help="Ingest data")
    p_ingest.add_argument("--source", choices=["api", "html"], default="api")
    p_ingest.add_argument("--since", default=None, help="YYYY-MM-DD")
    p_ingest.add_argument("--max-pages", type=int, default=50)
    p_ingest.add_argument("--page-size", type=int, default=50)
    p_ingest.add_argument("--comments", action="store_true")
    p_ingest.add_argument("--path", default="/", help="HTML path for scraping")
    p_ingest.add_argument("--dynamic", action="store_true", help="Use Playwright to render JS")
    p_ingest.add_argument("--max-scrolls", type=int, default=8)
    p_ingest.add_argument("--wait-ms", type=int, default=1200)
    p_ingest.add_argument("--dump-html", default=None, help="Directory to dump HTML pages")
    p_ingest.add_argument("--dump-screenshot", default=None, help="Directory to dump screenshots")
    p_ingest.add_argument("--local-html", default=None, help="Parse a local HTML file or directory")
    p_ingest.add_argument(
        "--allow-no-robots",
        action="store_true",
        help="Proceed if robots.txt is missing/unavailable (still respect ToS)",
    )
    p_ingest.set_defaults(func=cmd_ingest)

    p_norm = sub.add_parser("normalize", help="Normalize raw data")
    p_norm.set_defaults(func=cmd_normalize)

    p_an = sub.add_parser("analyze", help="Compute derived metrics")
    p_an.set_defaults(func=cmd_analyze)

    p_rep = sub.add_parser("report", help="Generate report")
    p_rep.set_defaults(func=cmd_report)

    p_crawl = sub.add_parser("crawl", help="Deep crawl via Playwright")
    p_crawl.add_argument("--filters", default="Random,New,Top,Discussed")
    p_crawl.add_argument("--max-posts", type=int, default=0, help="0 = unlimited")
    p_crawl.add_argument("--max-post-pages", type=int, default=0, help="0 = all collected posts")
    p_crawl.add_argument("--max-submolts", type=int, default=0, help="0 = unlimited")
    p_crawl.add_argument("--max-comments", type=int, default=0, help="0 = unlimited")
    p_crawl.add_argument("--max-scrolls", type=int, default=20)
    p_crawl.add_argument("--wait-ms", type=int, default=1200)
    p_crawl.add_argument("--rate-ms", type=int, default=300)
    p_crawl.add_argument("--headed", action="store_true")
    p_crawl.add_argument("--no-submolts", action="store_true")
    p_crawl.add_argument("--submolt-scrolls", type=int, default=15)
    p_crawl.add_argument("--stream-dir", default=None, help="Write progress JSONL streams here")
    p_crawl.add_argument("--log-post-pages", action="store_true", help="Log every post page visit")
    p_crawl.add_argument("--log-urls", action="store_true", help="Log every URL visit")
    p_crawl.add_argument("--log-file", default=None, help="Write crawl logs to a file")
    p_crawl.add_argument("--metrics-csv", default=None, help="Write crawl metrics to CSV")
    p_crawl.add_argument("--errors-jsonl", default=None, help="Write crawl errors to JSONL")
    p_crawl.add_argument("--netlog", default=None, help="Write network log JSONL")
    p_crawl.add_argument("--netlog-types", default="xhr,fetch", help="Comma-separated resource types")
    p_crawl.add_argument("--dump-html", default=None, help="Dump HTML on error or every page")
    p_crawl.add_argument("--dump-screenshot", default=None, help="Dump screenshots on error")
    p_crawl.add_argument("--dump-every-page", action="store_true", help="Dump HTML for every page visited")
    p_crawl.add_argument("--log-every-posts", type=int, default=50)
    p_crawl.add_argument("--log-every-comments", type=int, default=200)
    p_crawl.add_argument(
        "--allow-no-robots",
        action="store_true",
        help="Proceed if robots.txt is missing/unavailable (still respect ToS)",
    )
    p_crawl.set_defaults(func=cmd_crawl)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
