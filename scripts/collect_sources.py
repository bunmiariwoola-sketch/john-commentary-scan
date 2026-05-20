"""Collect recent RSS and search API results for the commentary scan."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import feedparser
import requests
from dateutil import parser as date_parser

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - only used before dependencies are installed
    def load_dotenv() -> bool:
        return False

try:
    from scripts.config import (
        DEFAULT_RSS_PATH,
        DEFAULT_SEARCH_PATH,
        RSSFeed,
        SearchQuery,
        load_rss_feeds,
        load_search_queries,
    )
except ModuleNotFoundError:  # pragma: no cover - supports direct script execution
    from config import (  # type: ignore
        DEFAULT_RSS_PATH,
        DEFAULT_SEARCH_PATH,
        RSSFeed,
        SearchQuery,
        load_rss_feeds,
        load_search_queries,
    )

LOGGER = logging.getLogger(__name__)
USER_AGENT = "john-commentary-scan/0.1 (+https://charitableimpact.com)"
MODE_WINDOWS = {
    "daily": timedelta(hours=24),
    "weekly": timedelta(days=7),
}


def clean_text(value: Any, max_length: int = 600) -> str:
    text = re.sub(r"<[^>]+>", " ", html.unescape(str(value or "")))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_length].rstrip()


def parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None

    try:
        parsed = date_parser.parse(str(value))
    except (TypeError, ValueError, OverflowError):
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def parse_feed_entry_datetime(entry: Any) -> datetime | None:
    for attr in ("published_parsed", "updated_parsed", "created_parsed"):
        parsed_struct = entry.get(attr)
        if parsed_struct:
            return datetime(*parsed_struct[:6], tzinfo=timezone.utc)

    for attr in ("published", "updated", "created"):
        parsed = parse_datetime(entry.get(attr))
        if parsed:
            return parsed

    return None


def item_key(url: str, title: str) -> str:
    raw = (url or title).strip().lower().encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def mode_start(mode: str, now: datetime | None = None) -> datetime:
    if mode not in MODE_WINDOWS:
        raise ValueError(f"Unsupported mode: {mode}")

    current = now or datetime.now(timezone.utc)
    return current - MODE_WINDOWS[mode]


def make_item(
    *,
    title: str,
    url: str,
    source: str,
    source_type: str,
    category: str,
    published_at: datetime | None,
    summary: str = "",
    query_name: str | None = None,
) -> dict[str, Any]:
    return {
        "id": item_key(url, title),
        "title": clean_text(title, 280),
        "url": url.strip(),
        "source": source,
        "source_type": source_type,
        "category": category,
        "published_at": published_at.isoformat() if published_at else None,
        "summary": clean_text(summary),
        "query_name": query_name,
    }


def collect_rss_items(
    feeds: list[RSSFeed],
    *,
    mode: str,
    now: datetime | None = None,
    per_feed_limit: int = 8,
) -> list[dict[str, Any]]:
    start = mode_start(mode, now)
    items: list[dict[str, Any]] = []

    for feed in feeds:
        if not feed.enabled or feed.source_type != "rss":
            continue

        try:
            response = requests.get(
                feed.url,
                timeout=20,
                headers={"User-Agent": USER_AGENT},
            )
            response.raise_for_status()
            parsed = feedparser.parse(response.content)
        except Exception as exc:  # pragma: no cover - network dependent
            LOGGER.warning("Failed to fetch RSS feed %s: %s", feed.name, exc)
            continue

        added = 0
        for entry in parsed.entries:
            title = entry.get("title")
            url = entry.get("link")
            if not title or not url:
                continue

            published_at = parse_feed_entry_datetime(entry)
            if published_at and published_at < start:
                continue

            items.append(
                make_item(
                    title=title,
                    url=url,
                    source=feed.name,
                    source_type="rss",
                    category=feed.category,
                    published_at=published_at,
                    summary=entry.get("summary") or entry.get("description", ""),
                )
            )
            added += 1
            if added >= per_feed_limit:
                break

    return items


def collect_newsapi_items(
    queries: list[SearchQuery],
    *,
    mode: str,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    api_key = os.getenv("NEWS_API_KEY")
    if not api_key:
        return []

    current = now or datetime.now(timezone.utc)
    start = mode_start(mode, current)
    items: list[dict[str, Any]] = []

    for query in queries:
        if "newsapi" not in query.apis:
            continue

        params: dict[str, Any] = {
            "q": query.query,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": min(query.max_results, 20),
            "from": start.isoformat(timespec="seconds").replace("+00:00", "Z"),
            "to": current.isoformat(timespec="seconds").replace("+00:00", "Z"),
            "apiKey": api_key,
        }
        if query.domains:
            params["domains"] = ",".join(query.domains)

        try:
            response = requests.get(
                "https://newsapi.org/v2/everything",
                params=params,
                timeout=20,
                headers={"User-Agent": USER_AGENT},
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:  # pragma: no cover - network dependent
            LOGGER.warning("NewsAPI query failed for %s: %s", query.name, exc)
            continue

        for article in payload.get("articles", [])[: query.max_results]:
            title = article.get("title")
            url = article.get("url")
            if not title or not url:
                continue

            items.append(
                make_item(
                    title=title,
                    url=url,
                    source=(article.get("source") or {}).get("name") or "NewsAPI",
                    source_type="newsapi",
                    category=query.category,
                    published_at=parse_datetime(article.get("publishedAt")),
                    summary=article.get("description") or article.get("content", ""),
                    query_name=query.name,
                )
            )

    return items


def collect_gdelt_items(
    queries: list[SearchQuery],
    *,
    mode: str,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    timespan = "24h" if mode == "daily" else "7d"

    for query in queries:
        if "gdelt" not in query.apis:
            continue

        params = {
            "query": query.query,
            "mode": "ArtList",
            "format": "json",
            "maxrecords": min(query.max_results, 20),
            "sort": "HybridRel",
            "timespan": timespan,
        }

        try:
            response = requests.get(
                "https://api.gdeltproject.org/api/v2/doc/doc",
                params=params,
                timeout=20,
                headers={"User-Agent": USER_AGENT},
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:  # pragma: no cover - network dependent
            LOGGER.warning("GDELT query failed for %s: %s", query.name, exc)
            continue

        for article in payload.get("articles", [])[: query.max_results]:
            title = article.get("title")
            url = article.get("url")
            if not title or not url:
                continue

            items.append(
                make_item(
                    title=title,
                    url=url,
                    source=article.get("sourceCommonName") or article.get("domain") or "GDELT",
                    source_type="gdelt",
                    category=query.category,
                    published_at=parse_datetime(article.get("seendate")),
                    summary=article.get("socialimage") or "",
                    query_name=query.name,
                )
            )

    return items


def dedupe_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []

    for item in items:
        key = item["url"].split("?")[0].strip().lower() or item["id"]
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)

    def sort_key(item: dict[str, Any]) -> str:
        return item.get("published_at") or ""

    return sorted(deduped, key=sort_key, reverse=True)


def collect_sources(
    *,
    mode: str,
    rss_path: str | Path = DEFAULT_RSS_PATH,
    search_path: str | Path = DEFAULT_SEARCH_PATH,
    max_items: int = 80,
) -> list[dict[str, Any]]:
    load_dotenv()

    feeds = load_rss_feeds(rss_path)
    queries = load_search_queries(search_path)

    items: list[dict[str, Any]] = []
    items.extend(collect_rss_items(feeds, mode=mode))
    items.extend(collect_gdelt_items(queries, mode=mode))
    items.extend(collect_newsapi_items(queries, mode=mode))

    return dedupe_items(items)[:max_items]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect recent commentary scan sources.")
    parser.add_argument("--mode", choices=("daily", "weekly"), default="daily")
    parser.add_argument("--rss-path", default=str(DEFAULT_RSS_PATH))
    parser.add_argument("--search-path", default=str(DEFAULT_SEARCH_PATH))
    parser.add_argument("--max-items", type=int, default=80)
    parser.add_argument("--output", help="Optional JSON output path.")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)

    items = collect_sources(
        mode=args.mode,
        rss_path=args.rss_path,
        search_path=args.search_path,
        max_items=args.max_items,
    )

    payload = json.dumps(items, indent=2, ensure_ascii=False)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)

    LOGGER.info("Collected %s items", len(items))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
