"""Generate a markdown PR commentary brief from collected sources."""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dry-run should work before dependencies are installed
    def load_dotenv() -> bool:
        return False

try:
    from scripts.config import PROJECT_ROOT, ensure_output_dir, load_prompt
except ModuleNotFoundError:  # pragma: no cover - supports direct script execution
    from config import PROJECT_ROOT, ensure_output_dir, load_prompt  # type: ignore

SCORE_LABELS = {
    5: "Pitch now",
    4: "Prepare commentary",
    3: "Monitor",
    2: "Keep for content",
    1: "Ignore",
}
ANALYSIS_MODES = ("source-only", "ai")

TORONTO = ZoneInfo("America/Toronto")


def normalize_score(value: Any) -> int:
    """Return a score from 1 to 5 from a model or test value."""

    if isinstance(value, int):
        score = value
    elif isinstance(value, float):
        score = round(value)
    else:
        match = re.search(r"\b([1-5])\b", str(value))
        score = int(match.group(1)) if match else 1

    return max(1, min(5, score))


def score_label(score: Any) -> str:
    return SCORE_LABELS[normalize_score(score)]


def brief_title(mode: str, now: datetime | None = None) -> str:
    current = now or datetime.now(TORONTO)
    label = "Daily" if mode == "daily" else "Weekly"
    return f"{label} PR Commentary Scan - {current:%Y-%m-%d}"


def normalize_analysis_mode(value: str | None) -> str:
    mode = (value or "source-only").strip().lower()
    if mode not in ANALYSIS_MODES:
        raise ValueError(f"Unsupported analysis mode: {mode}")
    return mode


def sample_items() -> list[dict[str, Any]]:
    return [
        {
            "id": "dry-run-affordability",
            "title": "Canadian households report tighter budgets as giving season approaches",
            "url": "https://example.com/household-budgets-giving",
            "source": "Dry Run News",
            "source_type": "dry_run",
            "category": "affordability",
            "published_at": datetime.now(TORONTO).isoformat(),
            "summary": "A placeholder item used to verify formatting without live APIs.",
            "query_name": "dry-run",
        },
        {
            "id": "dry-run-charities",
            "title": "Charities see rising demand and more complicated donor decisions",
            "url": "https://example.com/charity-demand",
            "source": "Dry Run Research",
            "source_type": "dry_run",
            "category": "charity_sector",
            "published_at": datetime.now(TORONTO).isoformat(),
            "summary": "A placeholder item used to exercise the opportunity brief structure.",
            "query_name": "dry-run",
        },
    ]


def item_context(items: list[dict[str, Any]], max_items: int) -> str:
    selected = items[:max_items]
    return json.dumps(selected, indent=2, ensure_ascii=False)


def category_label(value: Any) -> str:
    return str(value or "general").replace("_", " ").title()


def source_only_brief(mode: str, items: list[dict[str, Any]], max_items: int) -> str:
    """Build a no-cost digest that does not call OpenAI."""

    title = brief_title(mode)
    selected = items[:max_items]

    if not selected:
        return f"""# {title} (Source-Only)

## Executive Summary

No recent source items were collected. Check RSS availability, search API credentials, and workflow network access.

AI analysis is currently disabled, so this run did not call the OpenAI API.
"""

    categories = sorted({category_label(item.get("category")) for item in selected})
    lines = [
        f"# {title} (Source-Only)",
        "",
        "## Executive Summary",
        "",
        f"Collected {len(selected)} recent source items. AI scoring, John angles, draft quotes, and media recommendations are disabled for this no-cost mode.",
        "",
        f"Categories seen: {', '.join(categories)}.",
        "",
        "## Source Digest",
        "",
    ]

    for index, item in enumerate(selected, start=1):
        title_text = str(item.get("title") or "Untitled item").strip()
        source = str(item.get("source") or "Unknown source").strip()
        url = str(item.get("url") or "").strip()
        published_at = item.get("published_at") or "Date unavailable"
        category = category_label(item.get("category"))
        summary = str(item.get("summary") or "").strip()

        lines.extend(
            [
                f"### {index}. {title_text}",
                "",
                f"- Source: {source}",
                f"- Category: {category}",
                f"- Published: {published_at}",
            ]
        )
        if summary:
            lines.append(f"- Summary: {summary}")
        if url:
            lines.append(f"- Link: {url}")
        lines.append("")

    lines.extend(
        [
            "## Next Step",
            "",
            "When OpenAI API quota is available, run the same scan with `--analysis-mode ai` to generate opportunity scores, John angles, draft quotes, media targets, and recommended actions.",
        ]
    )
    return "\n".join(lines).strip() + "\n"


def build_user_prompt(
    *,
    mode: str,
    items: list[dict[str, Any]],
    scoring_criteria: str,
    max_items: int,
) -> str:
    depth = (
        "Create a concise brief focused on the strongest opportunities from the last 24 hours."
        if mode == "daily"
        else "Create a deeper strategic scan from the last 7 days, grouping themes where useful."
    )

    return f"""
Mode: {mode}

Briefing instruction:
{depth}

Scoring criteria:
{scoring_criteria}

Source items:
{item_context(items, max_items)}

Output requirements:
- Markdown only.
- Start with a short executive summary.
- Include only relevant opportunities. Be selective.
- For every opportunity, include:
  - What happened
  - Why it matters now
  - Connection to Charitable Impact, DAFs, donors, charities, or giving infrastructure
  - Score as "Score: N - Label"
  - Suggested John angle
  - Draft quote in John's voice
  - Suggested media targets
  - Recommended action
  - Source links
- End with a short watchlist for lower-scoring items if useful.
""".strip()


def call_openai(system_prompt: str, user_prompt: str) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required unless --dry-run is used.")

    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

    response = client.responses.create(
        model=model,
        instructions=system_prompt,
        input=user_prompt,
        temperature=0.2,
    )

    output_text = getattr(response, "output_text", None)
    if output_text:
        return output_text.strip()

    # Compatibility fallback for SDK response shapes that expose output parts.
    parts: list[str] = []
    for item in getattr(response, "output", []) or []:
        for content in getattr(item, "content", []) or []:
            text = getattr(content, "text", None)
            if text:
                parts.append(text)
    return "\n".join(parts).strip()


def dry_run_brief(mode: str, items: list[dict[str, Any]]) -> str:
    title = brief_title(mode)
    first = items[0]
    second = items[1] if len(items) > 1 else items[0]

    return f"""# {title}

## Executive Summary

Dry run completed successfully. This sample shows the expected markdown structure without calling live feeds, search APIs, OpenAI, or SMTP.

## Opportunity 1: Household Affordability And Generosity

**What happened:** {first["title"]}.

**Why it matters now:** Affordability pressure can change how Canadians think about generosity, timing, and tax-smart giving.

**Connection:** Charitable Impact can help donors plan thoughtful giving even when household finances feel tighter.

**Score: 4 - {score_label(4)}**

**Suggested John angle:** Generosity is strongest when giving tools help people act intentionally, not reactively.

**Draft quote:** "Canadians are still generous, but many are being more deliberate. The opportunity is to make giving easier to plan, easier to understand, and easier to sustain."

**Suggested media targets:** Canadian personal finance reporters, business desks, charity-sector newsletters.

**Recommended action:** Prepare a short comment linking affordability, donor behaviour, and planned giving.

**Source links:** [{first["source"]}]({first["url"]})

## Opportunity 2: Charity Sector Pressure

**What happened:** {second["title"]}.

**Why it matters now:** Rising demand and uneven giving can put pressure on charities just as community needs increase.

**Connection:** Giving infrastructure can help move resources to charities more efficiently and keep donors engaged.

**Score: 3 - {score_label(3)}**

**Suggested John angle:** The sector needs both trust and better tools for sustained donor participation.

**Draft quote:** "When charities face more demand, the answer is not only more generosity. It is better-connected generosity that helps donors follow through."

**Suggested media targets:** Future of Good, charity-sector trade media, local CBC business/community programs.

**Recommended action:** Monitor for a stronger data point or government release before pitching broadly.

**Source links:** [{second["source"]}]({second["url"]})
"""


def write_brief(markdown: str, mode: str, now: datetime | None = None) -> tuple[Path, Path]:
    current = now or datetime.now(TORONTO)
    output_dir = ensure_output_dir()
    dated_path = output_dir / f"{current:%Y-%m-%d}_{mode}_brief.md"
    latest_path = PROJECT_ROOT / "latest_brief.md"

    dated_path.write_text(markdown.rstrip() + "\n", encoding="utf-8")
    latest_path.write_text(markdown.rstrip() + "\n", encoding="utf-8")
    return dated_path, latest_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a PR commentary brief.")
    parser.add_argument("--mode", choices=("daily", "weekly"), default="daily")
    parser.add_argument(
        "--analysis-mode",
        choices=ANALYSIS_MODES,
        default=None,
        help="Use source-only for a no-cost digest, or ai for the full OpenAI-generated PR brief.",
    )
    parser.add_argument("--max-items", type=int, default=80)
    parser.add_argument("--dry-run", action="store_true", help="Use sample items and skip external services.")
    parser.add_argument("--send-email", action="store_true", help="Email the generated brief using SMTP env vars.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_dotenv()
    analysis_mode = normalize_analysis_mode(args.analysis_mode or os.getenv("ANALYSIS_MODE"))

    if args.dry_run:
        items = sample_items()
        markdown = source_only_brief(args.mode, items, args.max_items) if analysis_mode == "source-only" else dry_run_brief(args.mode, items)
    else:
        try:
            from scripts.collect_sources import collect_sources
        except ModuleNotFoundError:  # pragma: no cover - supports direct script execution
            from collect_sources import collect_sources  # type: ignore

        items = collect_sources(mode=args.mode, max_items=args.max_items)
        if analysis_mode == "source-only":
            markdown = source_only_brief(args.mode, items, args.max_items)
        elif not items:
            markdown = source_only_brief(args.mode, items, args.max_items)
        else:
            system_prompt = load_prompt("system_prompt.md")
            scoring_criteria = load_prompt("scoring_criteria.md")
            user_prompt = build_user_prompt(
                mode=args.mode,
                items=items,
                scoring_criteria=scoring_criteria,
                max_items=args.max_items,
            )
            markdown = call_openai(system_prompt, user_prompt)

    dated_path, latest_path = write_brief(markdown, args.mode)

    if args.send_email:
        try:
            from scripts.send_email import send_brief_email
        except ModuleNotFoundError:  # pragma: no cover - supports direct script execution
            from send_email import send_brief_email  # type: ignore

        send_brief_email(brief_title(args.mode), markdown)

    print(f"Wrote {dated_path}")
    print(f"Updated {latest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
