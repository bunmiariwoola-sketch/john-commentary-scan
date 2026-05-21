# john-commentary-scan

Automates a Canadian media and research scan for PR commentary opportunities for John Bromley, Founder and CEO of Charitable Impact.

The scanner collects recent RSS and search API results, writes a dated markdown brief, updates `latest_brief.md`, and can email the brief through SMTP.

By default, it runs in `source-only` mode, which does not call the OpenAI API and therefore does not use API credits. When API quota is available, use `ai` mode to identify commentary opportunities, score them from 1 to 5, and generate John angles, draft quotes, media targets, and recommended actions.

## What It Looks For

The default configuration is tuned for Canadian stories where John can credibly comment on:

- donor-advised funds and giving infrastructure
- donor behaviour and charitable giving trends in Canada
- affordability, inflation, household finances, and generosity
- tax-smart giving, securities donations, capital gains, and year-end giving
- wealth transfer and financial planning
- charity sector pressure, fundraising shortfalls, staffing constraints, and rising demand
- disaster relief and emergency giving
- community-led giving, crowdfunding, mutual aid, and local generosity
- trust, accountability, misinformation, and transparency in institutions
- family giving, youth generosity, financial literacy, and digital giving

## Setup

Requires Python 3.11.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` with your local credentials. Do not commit `.env`.

## Environment Variables

Required only for AI analysis mode:

- `OPENAI_API_KEY`

Optional for broader search collection:

- `NEWS_API_KEY`

Required only when sending email:

- `EMAIL_HOST`
- `EMAIL_PORT`
- `EMAIL_USER`
- `EMAIL_PASSWORD`
- `EMAIL_TO`
- `EMAIL_FROM`

Optional email settings:

- `EMAIL_USE_TLS=true`
- `EMAIL_USE_SSL=false`
- `EMAIL_SUBJECT_PREFIX=[John Commentary Scan]`

Optional OpenAI setting:

- `OPENAI_MODEL=gpt-4.1-mini`
- `ANALYSIS_MODE=source-only`

## Local Usage

Run a no-network, no-API smoke test:

```bash
python scripts/generate_brief.py --mode daily --dry-run
```

Run the free source-only daily scan:

```bash
python scripts/generate_brief.py --mode daily --analysis-mode source-only
```

Run the free source-only weekly scan and email it:

```bash
python scripts/generate_brief.py --mode weekly --analysis-mode source-only --send-email
```

Run the full AI-generated brief when OpenAI API quota is available:

```bash
python scripts/generate_brief.py --mode daily --analysis-mode ai
```

Collect sources only:

```bash
python scripts/collect_sources.py --mode daily --output outputs/source_snapshot.json
```

Each run writes a dated markdown file to `outputs/` and overwrites `latest_brief.md`.

## GitHub Secrets

In the GitHub repository, go to Settings -> Secrets and variables -> Actions -> New repository secret.

Add:

- `OPENAI_API_KEY`
- `NEWS_API_KEY` if available
- `EMAIL_HOST`
- `EMAIL_PORT`
- `EMAIL_USER`
- `EMAIL_PASSWORD`
- `EMAIL_TO`
- `EMAIL_FROM`

The workflows pass these values as environment variables at runtime.

`OPENAI_API_KEY` is not needed for the default `source-only` workflow mode. It is only needed when running with `analysis_mode: ai`.

## Scheduling

GitHub Actions schedules use UTC. The included schedules approximate America/Toronto:

- Daily weekday scan: `30 12 * * 1-5`, which is 8:30 a.m. Toronto during daylight time.
- Weekly deep scan: `0 12 * * 1`, which is 8:00 a.m. Toronto during daylight time.

Toronto switches between UTC-4 and UTC-5. If exact winter timing matters, update the workflow cron schedules seasonally.

Both workflows also support manual dispatch with:

- `mode`: `daily` or `weekly`
- `analysis_mode`: `source-only` or `ai`

Scheduled runs default to `source-only` so they do not spend OpenAI API credits.

## Customizing Sources

Edit:

- `sources/rss_feeds.yml` for RSS or monitored source URLs
- `sources/search_queries.yml` for search API queries

RSS entries with `source_type: rss` and `enabled: true` are fetched directly. Entries marked as `source_type: source_url` are documented as useful targets and are normally monitored through search queries.

Search queries can use:

- `gdelt`, no key required
- `newsapi`, uses `NEWS_API_KEY`

## Customizing Analysis

Edit:

- `prompts/system_prompt.md`
- `prompts/scoring_criteria.md`

The model is instructed to be selective, strategic, credible, and concise. Weak ties to Charitable Impact, donor-advised funds, donors, charities, or giving infrastructure should receive low scores.

These prompt files are used only in `ai` mode. `source-only` mode creates a basic source digest without AI scoring, John angles, draft quotes, media targets, or recommended actions.

## Verification

```bash
python -m compileall scripts
pytest
python scripts/generate_brief.py --mode daily --analysis-mode source-only --dry-run
```

## Limitations

- Some publishers do not provide stable public RSS feeds. Those are included as source URLs and covered through search queries where possible.
- NewsAPI is optional, but using it improves coverage for outlets without RSS.
- GitHub Actions cron schedules are UTC and only approximate America/Toronto across daylight saving changes.
- The OpenAI brief quality depends on source freshness, source metadata, and prompt tuning.
- `source-only` mode is intentionally simpler than the full AI brief. It is useful for monitoring links while avoiding API costs.
