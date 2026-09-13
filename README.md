# Niche Topic Tracker

Tracks what's trending vs. evergreen in data analytics / AI-in-analytics /
analytics engineering, by pulling signal from **5 free sources** and
combining them into one ranked list — instead of you manually parsing
Google Trends.

## Sources it pulls from

| Source | What it tells you | Auth needed? |
|---|---|---|
| Reddit | What practitioners are upvoting/discussing this week (r/analytics, r/dataengineering, r/PowerBI, etc.) | No |
| Hacker News | Dev/tool-facing buzz — good for catching launches early | No |
| GitHub | New/actively-updated tools gaining stars — catch a trend before it's mainstream | No (optional token for higher rate limit) |
| Google Trends | Related + **rising** search queries per seed keyword — this directly answers "what are people searching for right now" | No |
| Google Autosuggest | The actual questions people type constantly (how to / what is / best / vs) — your evergreen content bank | No |

## Setup

```bash
pip install -r requirements.txt
```

Optional: set a GitHub token as an env var if you hit rate limits on the GitHub source:
```bash
export GITHUB_TOKEN=ghp_yourtoken
```

## Running it

```bash
python run.py
```

This takes a few minutes (mostly Google Trends, which self-throttles to
avoid getting rate-limited). It writes two files:

- **`report.md`** — human-readable ranked report, open this first
- **`report.csv`** — raw ranked data if you want to pivot/filter in a spreadsheet

Flags:
```bash
python run.py --skip-trends   # if Google Trends starts 429-ing you
python run.py --skip-github   # if you hit GitHub's unauthenticated rate limit
```

## How ranking works

1. Every raw item (a Reddit post, an HN story, a GitHub repo, a Trends
   query, an autosuggest phrase) gets a **normalized 0–1 score within its
   own source** (so Reddit upvotes and HN points and Trends' 0–100 scale
   are comparable).
2. Each source has a weight (`config.py` → `WEIGHTS`) — Google Trends is
   weighted highest since it's the most direct search-intent signal.
3. Items are grouped by normalized topic text (lowercased, punctuation
   stripped). If **multiple sources** independently surface the same
   topic, it gets a cross-source agreement bonus — that's a stronger
   signal than one loud spike on a single platform.
4. Final list is sorted by composite score.

## How evergreen vs. spike detection works

Every run appends its top 40 topics + today's date to `history.csv`
(created automatically). On each run, a topic is classified as:

- **EVERGREEN** — appeared in 3+ separate run-dates → durable, safe content bet
- **RECURRING** — appeared in 2 separate run-dates → building momentum
- **NEW / SPIKE** — first time seeing it → move fast if you want the timing edge

This only becomes meaningful once you've run it a few times across
different weeks — the first run will show everything as NEW/SPIKE, which
is expected. **Run it weekly and let history.csv build up.**

## Suggested workflow

- Run it every Sunday night or Monday morning, ahead of your posting week.
- Scan the "Quick picks" section at the bottom of `report.md` first —
  evergreen picks for reliable posts, fresh spikes if you want to be
  first to cover something.
- Tune `config.py`:
  - `SEED_KEYWORDS` — the core topics Trends/Autosuggest expand from
  - `SUBREDDITS` / `HN_QUERIES` / `GITHUB_QUERIES` — where community
    signal comes from
  - `WEIGHTS` — if one source feels noisier than the others, turn it down

## Notes / limitations

- Google Trends (via `pytrends`) is an unofficial wrapper around Google's
  UI — it can occasionally rate-limit or change behavior. If it starts
  failing, run with `--skip-trends` and rely on the other 4 sources that day.
- The topic clustering is simple (normalized text match), not semantic —
  "AI in analytics" and "AI-powered analytics" will show up as separate
  rows. Good enough for spotting patterns, not perfect deduplication.
- This is a local script by design (no server/hosting needed) — just run
  it on your machine or schedule it with cron/Task Scheduler.
