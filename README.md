# Niche Topic Tracker

Manually eyeballing Google Trends to figure out what to post about next is
slow and vague: it tells you a query is "rising" but not whether anyone's
already covered it well, or whether it's even a real topic vs. a one-day
anomaly. Paid tools like vidIQ solve a version of this, but they're built
for broad YouTube-wide keyword research, not a specific technical niche like
data analytics / AI-in-analytics / analytics engineering. This project is a
free, automated alternative: it pulls signal from five sources, ranks it,
and checks real YouTube competition for the topics that make the cut. Treat
it as a first-pass research radar that narrows a wide field down to a
short list worth a human look, not a full replacement for a specialized
tool, and not a guarantee that everything it surfaces is worth covering.

## It runs itself: no weekly setup

This runs automatically every **Friday at 7am UK time** via GitHub Actions
(handling the BST/GMT switch itself, plus a guard so a manual trigger
always runs regardless of the time). There's nothing to remember to kick
off day to day: check the repo on Friday morning and that week's report is
already there, committed by the workflow. You can also trigger a run
manually any time from the **Actions** tab → "Weekly Trend Report" → "Run
workflow", useful for testing changes without waiting for Friday.

## Where to find this week's report

Every run commits its output into **`reports/`**, dated by the run:

- `reports/report_YYYY-MM-DD.xlsx`: the spreadsheet, sheets described below
- `reports/report_YYYY-MM-DD.txt`: the same content as plain text/markdown

The repo root also always holds the **latest** run's `report.xlsx`,
`report.md`, and `report.csv` (all overwritten each run) for a quick look
without hunting through `reports/`.

## What's in `report.xlsx`

| Sheet | What it is |
|---|---|
| **Top 10 This Week** | The week's top-ranked topics. See "Why the Top 10 is category-balanced" below for how this list is built, not just sorted by raw score. |
| **Content Ideas** | One structural suggestion per Top 10 topic, tagged with a **Competition Tier**: `WHITESPACE` (0-1 competing videos), `OPPORTUNITY` (a few videos, none with real traction), `PROVEN DEMAND` (a video with real traction, published in the last year), `REVISIT` (a video with real traction, but old), backed by actual YouTube view-count and publish-date data, not a guess. The suggested structure adapts to the tier and the topic, but never invents a personal claim or experience on your behalf ("I hit this on a client project"); personalizing it is left to you. |
| **Full Ranked List** | Every topic that survived filtering this run, sorted by score. Useful for digging past the Top 10. |
| **Evergreen Questions** | Google Suggest's autocomplete data (the "how to" / "what is" / "best" / "vs" questions people constantly type): a plain, unranked list, since this data has no weekly time signal and can't represent "trending now." Good for reliably relevant content regardless of the week. |

## Why the Top 10 is category-balanced

Left to raw score, the Top 10 skewed hard toward data-engineering tooling:
GitHub only ever surfaces repos, and nobody publishes a repo for "how I
built a stakeholder dashboard," so GitHub's tool/engineering content
structurally crowds out data-analytics and AI-in-analytics topics that
don't have a natural GitHub presence, regardless of how genuinely
newsworthy they are.

The Top 10 is built to guarantee representation instead: every topic is
tagged with one of three categories (`data_analytics`, `ai_analytics`,
`analytics_engineering`, via `config.py`'s `CATEGORY_TAGS`), and selection
takes the top-scoring topics from **each** category first (3 by default),
then fills any remaining slots with the next-best topics overall regardless
of category. A category having an unusually strong week can still claim
more than its guaranteed share; this stops any one category from being
silently crowded out, it doesn't force an artificial even split.

## Sources it pulls from

| Source | What it tells you | Auth needed? |
|---|---|---|
| Reddit | What practitioners are upvoting/discussing this week (r/analytics, r/dataengineering, r/PowerBI, etc.) | No |
| Hacker News | Dev/tool-facing buzz: good for catching launches early | No |
| GitHub | New/actively-updated tools gaining stars: catch a trend before it's mainstream | No (optional token for higher rate limit) |
| Google Trends | **Rising** search queries per seed keyword (weighted heavily) plus permanently-**top** queries (weighted low, since they'd show up any week regardless of what's trending) | No |
| Google Suggest | The actual questions people type constantly; feeds the Evergreen Questions sheet only, not the ranked Top 10 (see above) | No |
| YouTube (competitive check) | Not a discovery source; runs *after* ranking, only on the Top 10, to keep API quota use low. Answers "has anyone already covered this well?" for the Content Ideas sheet. | Yes, `YOUTUBE_API_KEY` |

## Setup

Since this runs on GitHub Actions, there's exactly **one manual step**:
add your YouTube Data API v3 key as a repo secret.

1. Get a key at [console.cloud.google.com/apis/credentials](https://console.cloud.google.com/apis/credentials) after enabling "YouTube Data API v3" on a project.
2. In this repo: **Settings → Secrets and variables → Actions → New repository secret**, name it `YOUTUBE_API_KEY`, paste the key.

That's it: the workflow already reads it via `${{ secrets.YOUTUBE_API_KEY }}`.
Without it, everything else still runs fine; the Content Ideas sheet just
falls back to a simpler topic-based angle instead of real competition data.

### Running it locally (optional)

Useful for testing config changes without waiting for Friday or spending an
Actions run.

```bash
pip install -r requirements.txt
export YOUTUBE_API_KEY=your_key_here     # optional, same fallback as above
export GITHUB_TOKEN=ghp_yourtoken        # optional, raises GitHub's rate limit
python run.py
```

Flags:
```bash
python run.py --skip-trends   # if Google Trends starts 429-ing you
python run.py --skip-github   # if you hit GitHub's unauthenticated rate limit
```

## How ranking works

1. Every raw item (a Reddit post, an HN story, a GitHub repo, a Trends
   query) gets normalized onto a 0-1 scale against a **fixed per-source
   cap** (`config.py` → `SCALE_CAPS`), deliberately not a within-run
   min-max, which would hand any single day's highest-scoring item full
   weight regardless of whether it's actually strong or just today's
   fluke.
2. Each source (and Trends' rising/top split specifically) has a weight
   (`config.py` → `WEIGHTS`).
3. Items are grouped by normalized topic text (lowercased, punctuation and
   filler words stripped). If **multiple sources** independently surface
   the same topic, it gets a cross-source agreement bonus: a stronger
   signal than one loud spike on a single platform.
4. The list is sorted by composite score, then the Top 10 is selected via
   the category-balancing pass described above.

## How evergreen vs. spike detection works

Every run appends its top 40 topics + today's date to `history.csv`
(committed automatically). On each run, a topic is classified as:

- **EVERGREEN**: appeared in 3+ separate run-dates → durable, safe content bet
- **RECURRING**: appeared in 2 separate run-dates → building momentum
- **NEW / SPIKE**: first time seeing it → move fast if you want the timing edge

This only becomes meaningful once `history.csv` has a few weeks of runs in
it: the first few runs will show everything as NEW/SPIKE, which is expected.

## Tuning `config.py`

- `SEED_KEYWORDS`: the core topics Trends/Suggest expand from
- `CATEGORY_TAGS`: which of the three niches each seed/HN-query/GitHub-query belongs to
- `SUBREDDITS` / `HN_QUERIES` / `GITHUB_QUERIES`: where community signal comes from
- `NEGATIVE_FILTERS`: blocks a seed keyword's hijacked/unrelated senses (e.g. "dbt" the tool vs. an unrelated government scheme)
- `WEIGHTS` / `SCALE_CAPS`: if one source feels noisier than the others, turn it down

## Notes / limitations

- **This uses free proxy signals, not real search-volume data.** Reddit
  upvotes, HN points, GitHub stars, Trends' relative interest, and YouTube
  view counts are all indirect stand-ins for actual demand, good enough to
  narrow a wide field down to a short list, not a substitute for real
  keyword-volume tools when it's time to commit to a specific piece.
  Treat this as a narrowing tool, not a final content-decision tool.
- Google Trends (via `pytrends`) is an unofficial wrapper around Google's
  UI; it can occasionally rate-limit or return one-off unrelated spikes
  from its own related-query graph. If it starts failing, run with
  `--skip-trends` and rely on the other sources that day.
- The topic clustering is simple (normalized text match), not semantic:
  "AI in analytics" and "AI-powered analytics" will show up as separate
  rows. Good enough for spotting patterns, not perfect deduplication.
- The YouTube relevance check is lightweight (a shared-word overlap, not
  real semantic matching). A hashtag-only match (a video tagging a topic
  purely for reach, unrelated to its actual content) is filtered out. A
  coincidental plain-text word collision with an unrelated foreign-language
  video is not: a search for a short topic name has, more than once, matched
  a completely unrelated song that happens to contain the same word. Left
  unfixed deliberately: a single observed instance isn't worth heavier
  language filtering for, but it's a known, recurring gap, not a solved one.
- The off-niche flag on GitHub-sourced Content Ideas is a simple
  keyword-presence check on the repo's description, not a real classifier:
  a repo can mention "analytics" once in an otherwise unrelated description
  and evade the flag. Absence of the flag isn't a guarantee of relevance.
- This is designed to run on GitHub Actions (see above), but `run.py` has
  no hard dependency on that; it runs anywhere Python does.
