"""
Reddit source for the daily niche pulse.

History worth knowing if you're reading this later: an earlier version of
this file searched all of Reddit via www.reddit.com/search.json. That
endpoint is explicitly blocked from GitHub Actions' shared IPs (confirmed
live: a 403 "Blocked" response on every query) — Reddit closed broad
self-service access to it in 2026, and self-service OAuth app approval is
now gated behind a manual "Responsible Builder Policy" review that routinely
rejects personal projects. Free, automated site-wide Reddit search is
genuinely not available anymore.

What still works, confirmed live: per-subreddit listing endpoints
(www.reddit.com/r/<sub>/new.json) — the same technique
sources/reddit_signal.py (the weekly tracker) has been using successfully
for weeks. So this module scopes back to config.SUBREDDITS (a curated list)
instead of searching all of Reddit. You lose "catches discussion in subs
nobody thought to add," you keep free, automated, working Reddit coverage.
"""
import datetime
import time

import requests

import config

HEADERS = {"User-Agent": "niche-pulse-tracker/1.0 (personal research script)"}


def _cutoff_epoch(lookback_hours):
    return (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=lookback_hours)).timestamp()


def _fetch_comments(permalink, max_comments=8):
    """Top-level comments for a post, trimmed to max_comments. Best-effort:
    returns [] on any failure rather than aborting the whole post."""
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


def _fetch_subreddit_new(subreddit, lookback_hours, limit=50, fetch_comments=True, max_comments=8):
    """Newest posts in `subreddit`, filtered to those created within
    lookback_hours. Uses /new.json (chronological) rather than /top.json
    (score-sorted, which would miss anything posted after the window's top
    posts settle) so nothing recent gets skipped just because it hasn't
    accumulated votes yet."""
    cutoff = _cutoff_epoch(lookback_hours)
    url = f"https://www.reddit.com/r/{subreddit}/new.json"
    try:
        resp = requests.get(url, headers=HEADERS, params={"limit": limit}, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"  [reddit-pulse] fetch failed for r/{subreddit}: {e}")
        return []

    posts = []
    for child in data.get("data", {}).get("children", []):
        p = child.get("data", {})
        created = p.get("created_utc", 0)
        if created < cutoff:
            continue  # /new.json is chronological, so once we're past the
                       # cutoff every remaining post is older still — but a
                       # stickied post can appear out of order, so `continue`
                       # (not `break`) to be safe rather than risk an early cutoff

        permalink = p.get("permalink", "")
        comments = _fetch_comments(permalink, max_comments=max_comments) if fetch_comments else []
        if fetch_comments:
            time.sleep(0.5)

        posts.append({
            "platform": "reddit",
            "query": subreddit,
            "subreddit": p.get("subreddit", subreddit),
            "title": p.get("title", ""),
            "selftext": (p.get("selftext") or "")[:500],
            "score": p.get("score", 0),
            "num_comments": p.get("num_comments", 0),
            "url": f"https://reddit.com{permalink}",
            "created_utc": created,
            "top_comments": comments,
        })
    return posts


def collect(subreddits, lookback_hours, limit_per_sub=50, fetch_comments=True):
    all_posts = []
    for sub in subreddits:
        print(f"  [reddit-pulse] scanning r/{sub}...")
        all_posts.extend(_fetch_subreddit_new(sub, lookback_hours, limit=limit_per_sub, fetch_comments=fetch_comments))
        time.sleep(1)  # be polite to Reddit's servers between subreddits

    seen = set()
    deduped = []
    for post in all_posts:
        if post["url"] in seen:
            continue
        seen.add(post["url"])
        deduped.append(post)
    return deduped
