from pathlib import Path

from scripts.config import load_rss_feeds, load_search_queries


def test_load_rss_feeds_skips_disabled_by_default(tmp_path: Path) -> None:
    path = tmp_path / "feeds.yml"
    path.write_text(
        """
feeds:
  - name: Enabled Feed
    url: https://example.com/feed.xml
    category: test
    enabled: true
  - name: Disabled Feed
    url: https://example.com/disabled.xml
    enabled: false
""",
        encoding="utf-8",
    )

    feeds = load_rss_feeds(path)

    assert len(feeds) == 1
    assert feeds[0].name == "Enabled Feed"
    assert feeds[0].category == "test"


def test_load_search_queries_normalizes_apis_and_domains(tmp_path: Path) -> None:
    path = tmp_path / "queries.yml"
    path.write_text(
        """
queries:
  - name: Giving
    query: charitable giving Canada
    apis: [GDELT, NewsAPI]
    domains: [example.com]
    max_results: 3
""",
        encoding="utf-8",
    )

    queries = load_search_queries(path)

    assert len(queries) == 1
    assert queries[0].apis == ("gdelt", "newsapi")
    assert queries[0].domains == ("example.com",)
    assert queries[0].max_results == 3
