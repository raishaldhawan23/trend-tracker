"""
Broad, site-wide Reddit search for the daily niche pulse — deliberately NOT
scoped to config.SUBREDDITS (that fixed list is tuned for the weekly Top-10
tracker's "top posts of the week in these specific subs" job). The pulse's
job is different: catch discussion about the niche wherever on Reddit it's
happening, including subs that would never make a curated list. Uses
Reddit's public JSON search endpoint (no API key/auth needed for read-only
access) — same approach as sources/reddit_signal.py.

For each matching post within the lookback window, also pulls its top-level
comments, since "what people are saying about it" (the comment thread) is
often the actual discussion/debate, not just the headline.
"""
import datetime
import time

import requests

HEADERS = {"User-Agent": "niche-pulse-tracker/1.0 (personal research script)"}
SEARCH_URL = "https://www.reddit.com/search.json"


def _cutoff_epoch(lookback_hours):
    return (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=lookback_hours)).timestamp()


def _fetch_comments(permalink, max_comments=8):
    """Top-level comments for a post, sorted by Reddit's default (best/top),
    trimmed to max_comments. Best-effort: returns [] on any failure rather
    than aborting the whole post."""
    url = f"https://www.reddit.com{permalink}.json"
    try:
        resp = requests.get(url, headers=HEADERS, params={"limit": max_comments}, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if len(data) < 2:
            return []
        comments = []
        for child in data[1].get("data", {}).get("children", [])[:max_comments]:
            c = child.get("data", {})
            body = (c.get("body") or "").strip()
            if not body or body in ("[deleted]", "[removed]"):
                continue
            comments.append({
                "body": body,
                "score": c.get("score", 0),
                "created_utc": c.get("created_utc"),
            })
        return comments
    except Exception as e:
        print(f"    [reddit-pulse] comment fetch failed for {permalink}: {e}")
        return []


def search_query(query, lookback_hours, limit=50, fetch_comments=True, max_comments=8):
    """Site-wide search for `query`, newest first, filtered to posts created
    within lookback_hours. Reddit's search 't' param only supports coarse
    windows (hour/day/week/...), so 't=day' is used as a coarse pre-filter
    and created_utc is then checked precisely against the real cutoff."""
    cutoff = _cutoff_epoch(lookback_hours)
    time_filter = "hour" if lookback_hours <= 1 else "day"

    try:
        resp = requests.get(SEARCH_URL, headers=HEADERS, params={
            "q": query,
            "sort": "new",
            "t": time_filter,
            "limit": limit,
        }, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"  [reddit-pulse] search failed for '{query}': {e}")
        return []

    posts = []
    for child in data.get("data", {}).get("children", []):
        p = child.get("data", {})
        created = p.get("created_utc", 0)
        if created < cutoff:
            continue  # coarse t=day window pre-filters; this is the real cutoff

        permalink = p.get("permalink", "")
        comments = _fetch_comments(permalink, max_comments=max_comments) if fetch_comments else []
        if fetch_comments:
            time.sleep(0.5)  # be polite — one extra request per matched post

        posts.append({
            "platform": "reddit",
            "query": query,
            "subreddit": p.get("subreddit", ""),
            "title": p.get("title", ""),
            "selftext": (p.get("selftext") or "")[:500],
            "score": p.get("score", 0),
            "num_comments": p.get("num_comments", 0),
            "url": f"https://reddit.com{permalink}",
            "created_utc": created,
            "top_comments": comments,
        })
    return posts


def collect(queries, lookback_hours, limit_per_query=50, fetch_comments=True):
    all_posts = []
    for q in queries:
        print(f"  [reddit-pulse] searching '{q}'...")
        all_posts.extend(search_query(q, lookback_hours, limit=limit_per_query, fetch_comments=fetch_comments))
        time.sleep(1)  # be polite to Reddit's servers between queries

    # De-dupe: the same post can match multiple overlapping queries.
    seen = set()
    deduped = []
    for post in all_posts:
        if post["url"] in seen:
            continue
        seen.add(post["url"])
        deduped.append(post)
    return deduped
