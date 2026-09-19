"""
This is the part that actually fixes the 'Google Trends is confusing' problem:
instead of you eyeballing the interest-over-time graph, this pulls the
RELATED QUERIES (top + rising) for each seed keyword and turns them into a
flat, ranked list — rising queries are the closest thing Trends has to
'what people are starting to search for right now'.

Uses pytrends (unofficial Google Trends API wrapper). Google occasionally
rate-limits this — if you see 429 errors, add delays or run fewer keywords
per session.
"""
import time
from pytrends.request import TrendReq

# A "breakout" rising query (Google's own label for "huge % increase, often
# from near-zero baseline") used to score an automatic max of 100 — meaning
# a single isolated one-day anomaly with no real relation to the seed (e.g.
# "lidl near me" showing up via loose session co-occurrence) could instantly
# outrank every genuine result. A fixed, moderate value keeps a breakout
# worth noting without letting it auto-dominate the ranked list.
BREAKOUT_SCORE = 60


def fetch_related_queries(seed_keywords, geo="", timeframe="today 1-m"):
    # "today 1-m" — narrow enough to stay fresher than the original "today
    # 3-m", but wide enough that a single-day anomaly doesn't look like
    # sustained rising signal the way the too-narrow "now 7-d" did.
    pytrends = TrendReq(hl="en-US", tz=0)
    results = []

    for kw in seed_keywords:
        print(f"  fetching Google Trends for '{kw}'...")
        try:
            pytrends.build_payload([kw], timeframe=timeframe, geo=geo)
            related = pytrends.related_queries()
            data = related.get(kw, {})

            top_df = data.get("top")
            rising_df = data.get("rising")

            if top_df is not None:
                for _, row in top_df.iterrows():
                    results.append({
                        "source": "trends",
                        "seed": kw,
                        "type": "top",
                        "title": row["query"],
                        "score": int(row["value"]),  # 0-100 relative popularity
                        "num_comments": 0,
                        "url": f"https://trends.google.com/trends/explore?q={row['query'].replace(' ', '+')}",
                    })

            if rising_df is not None:
                for _, row in rising_df.iterrows():
                    # 'value' for rising queries can be a huge % (breakout) — cap for scoring sanity
                    raw_val = row["value"]
                    val = BREAKOUT_SCORE if str(raw_val).lower() == "breakout" else min(int(raw_val), 500)
                    results.append({
                        "source": "trends",
                        "seed": kw,
                        "type": "rising",
                        "title": row["query"],
                        "score": val,
                        "num_comments": 0,
                        "url": f"https://trends.google.com/trends/explore?q={row['query'].replace(' ', '+')}",
                    })
        except Exception as e:
            print(f"  [trends] failed for '{kw}': {e}")

        time.sleep(2)  # avoid rate-limiting

    return results


def collect(seed_keywords, geo="", timeframe="today 1-m"):
    return fetch_related_queries(seed_keywords, geo=geo, timeframe=timeframe)
