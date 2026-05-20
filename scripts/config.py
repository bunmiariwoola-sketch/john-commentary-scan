"""Configuration loading for the commentary scanner."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCES_DIR = PROJECT_ROOT / "sources"
PROMPTS_DIR = PROJECT_ROOT / "prompts"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"

DEFAULT_RSS_PATH = SOURCES_DIR / "rss_feeds.yml"
DEFAULT_SEARCH_PATH = SOURCES_DIR / "search_queries.yml"


@dataclass(frozen=True)
class RSSFeed:
    name: str
    url: str
    category: str = "general"
    enabled: bool = True
    source_type: str = "rss"
    notes: str = ""


@dataclass(frozen=True)
class SearchQuery:
    name: str
    query: str
    category: str = "general"
    enabled: bool = True
    apis: tuple[str, ...] = ("gdelt", "newsapi")
    max_results: int = 5
    domains: tuple[str, ...] = field(default_factory=tuple)


def load_yaml(path: str | Path) -> dict[str, Any]:
    """Load a YAML file and return an empty dict for blank files."""

    resolved = Path(path)
    if not resolved.exists():
        raise FileNotFoundError(f"Config file not found: {resolved}")

    with resolved.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def load_rss_feeds(
    path: str | Path = DEFAULT_RSS_PATH,
    *,
    include_disabled: bool = False,
) -> list[RSSFeed]:
    data = load_yaml(path)
    feeds: list[RSSFeed] = []

    for item in data.get("feeds", []):
        enabled = bool(item.get("enabled", True))
        if not enabled and not include_disabled:
            continue

        feeds.append(
            RSSFeed(
                name=str(item["name"]),
                url=str(item["url"]),
                category=str(item.get("category", "general")),
                enabled=enabled,
                source_type=str(item.get("source_type", "rss")),
                notes=str(item.get("notes", "")),
            )
        )

    return feeds


def load_search_queries(
    path: str | Path = DEFAULT_SEARCH_PATH,
    *,
    include_disabled: bool = False,
) -> list[SearchQuery]:
    data = load_yaml(path)
    queries: list[SearchQuery] = []

    for item in data.get("queries", []):
        enabled = bool(item.get("enabled", True))
        if not enabled and not include_disabled:
            continue

        apis = item.get("apis", ["gdelt", "newsapi"])
        domains = item.get("domains", [])

        queries.append(
            SearchQuery(
                name=str(item["name"]),
                query=str(item["query"]),
                category=str(item.get("category", "general")),
                enabled=enabled,
                apis=tuple(str(api).lower() for api in apis),
                max_results=int(item.get("max_results", 5)),
                domains=tuple(str(domain) for domain in domains),
            )
        )

    return queries


def load_prompt(name: str) -> str:
    path = PROMPTS_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8").strip()


def ensure_output_dir() -> Path:
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    return OUTPUTS_DIR
