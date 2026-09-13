"""
Pulls top posts from target subreddits over the past week using Reddit's
public JSON endpoints (no API key/auth needed for read-only access).
"""
import time
import requests

HEADERS = {"User-Agent": "niche-trend-tracker/1.0 (personal research script)"}


def fetch_subreddit_top(subreddit, time_filter="week", limit=25):
    """Fetch top posts for a subreddit in the given time window."""
    url = f"https://www.reddit.com/r/{subreddit}/top.json"
    params = {"t": time_filter, "limit": limit}
    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"  [reddit] failed for r/{subreddit}: {e}")
        return []

    posts = []
    for child in data.get("data", {}).get("children", []):
        p = child.get("data", {})
        posts.append({
            "source": "reddit",
            "subreddit": subreddit,
            "title": p.get("title", ""),
            "score": p.get("score", 0),
            "num_comments": p.get("num_comments", 0),
            "url": f"https://reddit.com{p.get('permalink', '')}",
            "created_utc": p.get("created_utc"),
        })
    return posts


def collect(subreddits, time_filter="week"):
    all_posts = []
    for sub in subreddits:
        print(f"  scanning r/{sub}...")
        all_posts.extend(fetch_subreddit_top(sub, time_filter=time_filter))
        time.sleep(1)  # be polite to Reddit's servers
    return all_posts
