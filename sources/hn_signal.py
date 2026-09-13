"""
Pulls recent Hacker News stories matching niche queries using the free
Algolia HN Search API (no key required).
"""
import time
import requests

BASE_URL = "https://hn.algolia.com/api/v1/search"

# A query like "LLM" or "AI agent" still returns plenty of hits with no
# analytics angle at all — this is a lightweight relevance floor: a hit's
# title must contain at least one of these niche terms to survive.
NICHE_TERMS = [
    "data", "analytics", "dbt", "pipeline", "sql", "dashboard",
    "bi", "warehouse", "etl", "llm", "ai agent",
]


def _is_relevant(title):
    title_lower = title.lower()
    return any(term in title_lower for term in NICHE_TERMS)


def fetch_query(query, days_back=7):
    ts_cutoff = int(time.time()) - days_back * 86400
    params = {
        "query": query,
        "tags": "story",
        "numericFilters": f"created_at_i>{ts_cutoff}",
        "hitsPerPage": 20,
    }
    try:
        resp = requests.get(BASE_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"  [hn] failed for '{query}': {e}")
        return []

    hits = []
    for h in data.get("hits", []):
        title = h.get("title", "")
        if not _is_relevant(title):
            continue
        hits.append({
            "source": "hn",
            "query": query,
            "title": title,
            "score": h.get("points", 0),
            "num_comments": h.get("num_comments", 0),
            "url": h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID')}",
            "created_utc": h.get("created_at_i"),
        })
    return hits


def collect(queries, days_back=7):
    all_hits = []
    for q in queries:
        print(f"  searching HN for '{q}'...")
        all_hits.extend(fetch_query(q, days_back=days_back))
        time.sleep(0.5)
    return all_hits
