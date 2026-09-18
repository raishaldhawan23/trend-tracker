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


def fetch_related_queries(seed_keywords, geo="", timeframe="now 7-d"):
    # "now 7-d" (not the old "today 3-m") so a "rising" query actually means
    # rising over the last week, not the last quarter — otherwise a weekly
    # report ends up re-surfacing the same quarter-long trend every time.
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
                    val = 100 if str(raw_val).lower() == "breakout" else min(int(raw_val), 500)
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


def collect(seed_keywords, geo="", timeframe="now 7-d"):
    return fetch_related_queries(seed_keywords, geo=geo, timeframe=timeframe)
