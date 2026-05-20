# john-commentary-scan

Automates a Canadian media and research scan for PR commentary opportunities for John Bromley, Founder and CEO of Charitable Impact.

The scanner collects recent RSS and search API results, asks the OpenAI API to identify credible commentary opportunities, scores them from 1 to 5, writes a dated markdown brief, updates `latest_brief.md`, and can email the brief through SMTP.

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

Required for full runs:

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

## Local Usage

Run a no-network, no-API smoke test:

```bash
python scripts/generate_brief.py --mode daily --dry-run
```

Run the daily scan:

```bash
python scripts/generate_brief.py --mode daily
```

Run the weekly scan and email it:

```bash
python scripts/generate_brief.py --mode weekly --send-email
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

## Scheduling

GitHub Actions schedules use UTC. The included schedules approximate America/Toronto:

- Daily weekday scan: `30 12 * * 1-5`, which is 8:30 a.m. Toronto during daylight time.
- Weekly deep scan: `0 12 * * 1`, which is 8:00 a.m. Toronto during daylight time.

Toronto switches between UTC-4 and UTC-5. If exact winter timing matters, update the workflow cron schedules seasonally.

Both workflows also support manual dispatch with a `mode` input of `daily` or `weekly`.

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

## Verification

```bash
python -m compileall scripts
pytest
python scripts/generate_brief.py --mode daily --dry-run
```

## Limitations

- Some publishers do not provide stable public RSS feeds. Those are included as source URLs and covered through search queries where possible.
- NewsAPI is optional, but using it improves coverage for outlets without RSS.
- GitHub Actions cron schedules are UTC and only approximate America/Toronto across daylight saving changes.
- The OpenAI brief quality depends on source freshness, source metadata, and prompt tuning.
