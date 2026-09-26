# Niche Topic Tracker

> **⚠️ Retired (2026-09-25).** This tool's automatic weekly run is turned
> off — see **Niche Pulse** further down for the active tool. This one
> ranked Trends/Suggest keyword signal, which turned out to surface generic
> or off-topic "trending" terms rather than real conversation; Niche Pulse
> replaces it with actual Reddit/YouTube/X discussion, clustered into
> themes and emailed daily. `run.py` still works if triggered manually (see
> "Setup" below) — kept in case the Top-10/evergreen-question angle is ever
> useful again — but nothing here runs on a schedule anymore.

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

---

# Niche Pulse (daily conversation monitor)

A second, separate tool in this repo (`pulse.py`) with a different job from
the weekly tracker above: instead of ranking search/trend signal for content
ideation, it answers **"what is my niche actually discussing right now, and
what's getting a reaction or a debate"** — pulled from Reddit and YouTube
comments over roughly the last 30 hours, clustered into themes, and emailed
to you daily.

## Platforms and their real limitations

| Platform | Status | Why |
|---|---|---|
| Reddit | Full support, scoped | Scans `config.SUBREDDITS` (the same curated list the weekly tracker uses) via the free per-subreddit `.json` endpoint — no key, no setup. **Not** site-wide search: Reddit closed free self-service search/OAuth access in 2026 (confirmed live: an explicit `403 Blocked` on `www.reddit.com/search.json` from GitHub Actions, and new OAuth app approval now needs manual review that routinely rejects personal projects). The per-subreddit endpoint isn't affected by that block, so this still works — you get real discussion from ~10 curated niche subreddits, not the whole site. |
| YouTube comments | Full support | Uses the same `YOUTUBE_API_KEY` as the weekly tracker's competitive check — `commentThreads.list` on recently-published niche videos. No new cost. |
| X/Twitter | **Dropped entirely** | X's API dropped free search access (paid tier runs ~$200/month), and the free scraping workaround (`snscrape`) is reliably blocked by X now (confirmed live: 403 on every query). Not worth the noise for what it returns — decided against paying for it. |
| LinkedIn | **Not included** | No public search API exists, and scraping it risks your own account being flagged — especially relevant since you post there under your own name. Left out entirely rather than done unreliably or riskily. |

## Audience filter

The digest is meant to surface conversation useful for showing up as a
practitioner with real opinions — the kind that resonates with people who
hire/manage analytics talent — not job-seeker discussion (which doesn't
convert into that audience even when it's topically on-niche). `config.py`'s
`JOB_SEEKER_FILTERS` is a keyword heuristic that **flags and demotes**
matching themes (tagged 🎯 in the report) rather than deleting them, so nothing
disappears silently.

## Running it

```bash
python pulse.py                    # full run: reddit + youtube, ~30h lookback
python pulse.py --lookback-hours 24
python pulse.py --email            # also email the digest (see Email setup below)
```

Outputs, written locally wherever it runs (repo root):
- `pulse_report.md` — the themed digest (also used as the email body)
- `pulse_report.xlsx` — `Themes` summary sheet + `All Items` raw sheet
- `pulse_raw.json` — every collected item pre-clustering, so nothing is lost even if a given run's clustering isn't ideal

**Nothing here gets committed to the repo.** This repo is public, and the
digest content is real discussion/opinions pulled from other people's posts
and comments — not something to publish into a public folder. When run via
GitHub Actions, these files exist only on that run's disposable runner and
are discarded when the job ends; the email is the only place the content
leaves the job. Running `python pulse.py` locally still writes these files
to your own machine as normal, for your own reference.

## Automation

`.github/workflows/daily-pulse.yml` runs this daily at 7am UK time (same
BST/GMT-aware gating as the weekly workflow used) and emails you the digest
— nothing is committed. Trigger it manually any time from the **Actions**
tab → "Daily Niche Pulse" → "Run workflow".

Reddit needs no setup — it's free and keyless, same as the weekly tracker's Reddit source.

## Email setup (one-time)

The daily email sends from your own Gmail address to itself via SMTP, using
a Gmail **App Password** (not your normal password):

1. Turn on 2-Step Verification if it isn't already: [myaccount.google.com/security](https://myaccount.google.com/security)
2. Generate an App Password: [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords) → app "Mail" → copy the 16-character code.
3. In this repo: **Settings → Secrets and variables → Actions → New repository secret**, add:
   - `GMAIL_ADDRESS` — your full Gmail address
   - `GMAIL_APP_PASSWORD` — the 16-character code from step 2

Without these two secrets, the pipeline still runs — the report files just
get written to the runner's disposable workspace and discarded as usual
(see "Nothing here gets committed to the repo" above), with no email sent
and a note in the logs saying so. In other words, the run happens but you
never see the output — so these two secrets aren't optional in practice.

## Tuning `config.py` for the pulse

- `PULSE_LOOKBACK_HOURS` — how far back counts as "recent" (default 30)
- `PULSE_QUERIES` — the YouTube search terms for this tool (Reddit instead uses `SUBREDDITS`, below); separate from `SEED_KEYWORDS`, which is tuned specifically for Trends/Suggest
- `SUBREDDITS` — shared with the weekly tracker; the pulse scans these same subreddits for recent posts/comments
- `JOB_SEEKER_FILTERS` — the audience heuristic described above
- `DEBATE_SIGNAL_PHRASES` — phrases used to flag "what's being debated" separately from raw engagement

## Notes / limitations

- Clustering is TF-IDF + KMeans (bag-of-words), not semantic/LLM clustering — it groups items that share vocabulary. It will occasionally split one real theme across two clusters, or lump two unrelated ones together. Treat theme labels as a starting point; read the underlying items in `All Items`.
- The debate/job-seeker tags are keyword heuristics, not classifiers — they will both miss things and occasionally mistag a calm thread. `pulse_raw.json` always has everything unfiltered if you want to double-check a given run.
