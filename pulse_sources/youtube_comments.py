"""
YouTube half of the daily niche pulse: finds recently-published videos on
niche queries, then pulls their comments to see what viewers are actually
saying/reacting to/debating — not the video's own view count (that's
sources/youtube_signal.py's job for the weekly tracker).

Uses the same YOUTUBE_API_KEY env var as sources/youtube_signal.py. Degrades
gracefully (returns []) if the key isn't set or any call fails, so a
YouTube outage never takes down the rest of the pulse run.

Quota note: search.list costs 100 units, commentThreads.list costs 1 unit.
With ~12 PULSE_QUERIES x 3 videos each x 1 comment page, a daily run costs
roughly 12*100 + 36*1 ≈ 1,236 units/day against the free 10,000/day quota —
comfortable headroom alongside the weekly tracker's own usage.
"""
import datetime
import os
import time

import requests

SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
COMMENTS_URL = "https://www.googleapis.com/youtube/v3/commentThreads"


def _get_api_key():
    return os.environ.get("YOUTUBE_API_KEY", "").strip()


def is_configured():
    return bool(_get_api_key())


def _published_after(lookback_hours):
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=lookback_hours)
    return cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_iso(ts):
    return datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _recent_videos(query, lookback_hours, max_results=3, api_key=None):
    try:
        resp = requests.get(SEARCH_URL, params={
            "key": api_key,
            "q": query,
            "type": "video",
            "part": "id,snippet",
            "order": "relevance",
            "publishedAfter": _published_after(lookback_hours),
            "maxResults": max_results,
        }, timeout=15)
        resp.raise_for_status()
        items = resp.json().get("items", [])
        return [{
            "video_id": it["id"]["videoId"],
            "title": it["snippet"]["title"],
            "channel": it["snippet"]["channelTitle"],
            "url": f"https://www.youtube.com/watch?v={it['id']['videoId']}",
        } for it in items]
    except Exception as e:
        print(f"  [youtube-pulse] video search failed for '{query}': {e}")
        return []


def _comments_for_video(video_id, lookback_hours, api_key=None, max_comments=20):
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=lookback_hours)
    try:
        resp = requests.get(COMMENTS_URL, params={
            "key": api_key,
            "videoId": video_id,
            "part": "snippet",
            "order": "relevance",  # surfaces what's getting reaction, not just newest
            "maxResults": max_comments,
            "textFormat": "plainText",
        }, timeout=15)
        if resp.status_code == 403:
            # Comments disabled on this video — not an error worth logging loudly.
            return []
        resp.raise_for_status()
        comments = []
        for item in resp.json().get("items", []):
            top = item["snippet"]["topLevelComment"]["snippet"]
            published = _parse_iso(top["publishedAt"])
            comments.append({
                "text": top.get("textDisplay", ""),
                "like_count": top.get("likeCount", 0),
                "published_at": top["publishedAt"],
                "recent": published >= cutoff,
                "reply_count": item["snippet"].get("totalReplyCount", 0),
            })
        return comments
    except Exception as e:
        print(f"    [youtube-pulse] comments failed for video {video_id}: {e}")
        return []


def collect(queries, lookback_hours, videos_per_query=3, comments_per_video=20):
    """Returns a list of items shaped like the other pulse sources: one entry
    per (video, notable-comment-set), so the clustering step can treat the
    video's comment section as a single discussion unit."""
    api_key = _get_api_key()
    if not api_key:
        print("  [youtube-pulse] YOUTUBE_API_KEY not set — skipping YouTube comments.")
        return []

    items = []
    seen_videos = set()
    for query in queries:
        print(f"  [youtube-pulse] searching videos for '{query}'...")
        videos = _recent_videos(query, lookback_hours, max_results=videos_per_query, api_key=api_key)
        time.sleep(0.2)
        for video in videos:
            if video["video_id"] in seen_videos:
                continue
            seen_videos.add(video["video_id"])

            comments = _comments_for_video(video["video_id"], lookback_hours, api_key=api_key,
                                            max_comments=comments_per_video)
            time.sleep(0.2)
            recent_comments = [c for c in comments if c["recent"]]
            # Skip videos with genuinely no recent comment activity — nothing
            # to report on, and keeps clusters from being clogged with
            # single-comment noise.
            if not recent_comments:
                continue

            items.append({
                "platform": "youtube",
                "query": query,
                "title": video["title"],
                "channel": video["channel"],
                "url": video["url"],
                "score": sum(c["like_count"] for c in recent_comments),
                "num_comments": len(recent_comments),
                "top_comments": [
                    {"body": c["text"], "score": c["like_count"], "created_utc": None}
                    for c in sorted(recent_comments, key=lambda c: c["like_count"], reverse=True)[:8]
                ],
            })
    return items
