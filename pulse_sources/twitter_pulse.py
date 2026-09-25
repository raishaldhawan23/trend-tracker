"""
Best-effort X/Twitter coverage for the daily niche pulse.

Read this before relying on it: X shut down free API search access, and a
paid tier (their "Basic" plan) runs roughly $200/month for meaningful read
access. Scraping X while logged into a real account risks that account
being flagged, so this module deliberately never logs in or uses cookies —
it only tries anonymous, no-auth methods, which means it is genuinely
unreliable:

  1. snscrape (open-source, no API key, scrapes X's public search via its
     internal endpoints). X actively works against this and it has broken
     and been fixed repeatedly over the years — expect long stretches where
     it silently returns nothing.
  2. A public Nitter instance (an alternative X front-end), if one is
     reachable — Nitter instances are volunteer-run and most are offline or
     rate-limited at any given time. Configure via the NITTER_INSTANCE env
     var (e.g. "https://nitter.net"); no default is hardcoded because
     stable public instances change often.

Both are wrapped so a total failure just means "0 tweets this run", never a
crashed pipeline. If this consistently returns nothing and X coverage
matters enough to be worth it, the real fix is paying for X's API — this
module is the free-tier ceiling, not a permanent workaround.
"""
import datetime
import os

import requests

NITTER_INSTANCE = os.environ.get("NITTER_INSTANCE", "").strip().rstrip("/")


def _try_snscrape(query, cutoff, limit_per_query):
    try:
        import snscrape.modules.twitter as sntwitter
    except ImportError:
        print("  [twitter-pulse] snscrape not installed — skipping this method (pip install snscrape).")
        return []

    results = []
    search_query = f"{query} since:{cutoff.strftime('%Y-%m-%d')} lang:en"
    try:
        scraper = sntwitter.TwitterSearchScraper(search_query)
        for i, tweet in enumerate(scraper.get_items()):
            if i >= limit_per_query:
                break
            if tweet.date < cutoff:
                break  # results come back newest-first
            results.append({
                "platform": "twitter",
                "query": query,
                "title": tweet.rawContent[:280],
                "score": (tweet.likeCount or 0) + (tweet.retweetCount or 0),
                "num_comments": tweet.replyCount or 0,
                "url": tweet.url,
                "created_utc": tweet.date.timestamp(),
                "top_comments": [],
            })
    except Exception as e:
        print(f"  [twitter-pulse] snscrape failed for '{query}' (X likely changed something again): {e}")
        return []
    return results


def _try_nitter(query, cutoff, limit_per_query):
    if not NITTER_INSTANCE:
        return []
    try:
        resp = requests.get(f"{NITTER_INSTANCE}/search", params={
            "f": "tweets", "q": query, "since": cutoff.strftime("%Y-%m-%d"),
        }, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
    except Exception as e:
        print(f"  [twitter-pulse] Nitter instance unreachable for '{query}': {e}")
        return []

    # Deliberately not scraping Nitter's HTML here: its markup shifts often
    # enough between instances/versions that a hand-rolled parser would be
    # high-maintenance for a fallback path that's already best-effort. If
    # Nitter becomes the primary path worth investing in, add an HTML parser
    # (e.g. BeautifulSoup against the instance's .timeline-item elements)
    # here — left as a stub so the pipeline still runs cleanly without it.
    return []


def collect(queries, lookback_hours, limit_per_query=20):
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=lookback_hours)
    all_results = []
    for query in queries:
        print(f"  [twitter-pulse] searching '{query}' (best-effort, may return nothing)...")
        hits = _try_snscrape(query, cutoff, limit_per_query)
        if not hits:
            hits = _try_nitter(query, cutoff, limit_per_query)
        all_results.extend(hits)

    if not all_results:
        print(
            "  [twitter-pulse] 0 results across all queries — this is expected/common given X's "
            "restrictions on free access, not necessarily a bug. See this file's module docstring."
        )
    return all_results
