"""
Competitive-research check: for a given topic, how much YouTube coverage
already exists, and has any of it actually broken through? Unlike the other
sources/ modules this isn't a topic-discovery signal — it's run afterwards,
only on the Top 10 ranked topics, to conserve API quota (search.list costs
100 quota units against the free 10,000/day allowance, so scanning all ~500
raw topics every run would burn through it fast).

Uses the YouTube Data API v3. Requires an API key in the YOUTUBE_API_KEY env
var — get one at https://console.cloud.google.com/apis/credentials after
enabling "YouTube Data API v3" on a project. If the key isn't set, every
function here degrades to returning None so callers can distinguish "not
configured" from "checked, found nothing".
"""
import os
import re
import time
import requests

import config
from aggregate import _passes_negative_filters

SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"

# Generic connector words ignored by the relevance check below — a video
# title has to share at least one word with the search topic that ISN'T one
# of these, or it doesn't count as genuine competition.
_FILLER_WORDS = {
    "a", "an", "the", "is", "are", "was", "were", "what", "how", "to", "for",
    "of", "in", "on", "and", "or", "with", "vs", "versus", "your", "you",
    "this", "that", "it", "its", "from", "best", "why",
}


def _get_api_key():
    return os.environ.get("YOUTUBE_API_KEY", "").strip()


def is_configured():
    return bool(_get_api_key())


def _matching_negative_filter_seed(topic):
    """Which config.NEGATIVE_FILTERS key (if any) the search topic is about,
    so the same hijacked-keyword protection Trends/Suggest already get
    (aggregate._passes_negative_filters) can be reused for YouTube results —
    e.g. a "dbt" search shouldn't count an Indian government Direct Benefit
    Transfer scheme video as competition."""
    topic_lower = topic.lower()
    for seed in config.NEGATIVE_FILTERS:
        if seed in topic_lower:
            return seed
    return ""


def _shares_meaningful_word(topic, video_title):
    """A lightweight relevance floor: the video title must share at least one
    non-filler word with the searched topic, so a video that YouTube's own
    fuzzy search matched but that isn't actually about the topic (e.g. an
    unrelated video sharing no real subject words) doesn't count as
    competition."""
    topic_words = {w for w in re.findall(r"[a-z0-9]+", topic.lower()) if w not in _FILLER_WORDS and len(w) > 2}
    if not topic_words:
        return True  # nothing meaningful to compare against — don't filter blindly
    title_words = {w for w in re.findall(r"[a-z0-9]+", video_title.lower())}
    return bool(topic_words & title_words)


def top_videos_for_topic(topic, max_results=3):
    """Returns up to `max_results` videos for `topic`, each as
    {"title", "view_count", "published_at", "url"} — or None if
    YOUTUBE_API_KEY isn't set, or the API call failed (network/quota/auth
    error). Returns [] (not None) when the key works but no videos matched.

    search.list's order=viewCount is only an approximation of "most-viewed
    for this query" (it re-sorts a relevance-filtered result set, not a true
    global view-count sort) — videos.list is then used for authoritative,
    current statistics on those specific videos.
    """
    api_key = _get_api_key()
    if not api_key:
        return None

    try:
        search_resp = requests.get(SEARCH_URL, params={
            "key": api_key,
            "q": topic,
            "type": "video",
            "part": "id",
            "order": "viewCount",
            "maxResults": max_results,
        }, timeout=15)
        search_resp.raise_for_status()
        video_ids = [item["id"]["videoId"] for item in search_resp.json().get("items", [])]
        if not video_ids:
            return []

        stats_resp = requests.get(VIDEOS_URL, params={
            "key": api_key,
            "id": ",".join(video_ids),
            "part": "snippet,statistics",
        }, timeout=15)
        stats_resp.raise_for_status()

        videos = []
        for item in stats_resp.json().get("items", []):
            videos.append({
                "title": item["snippet"]["title"],
                "view_count": int(item.get("statistics", {}).get("viewCount", 0)),
                "published_at": item["snippet"]["publishedAt"],  # ISO 8601, e.g. 2025-01-15T12:00:00Z
                "url": f"https://www.youtube.com/watch?v={item['id']}",
            })

        # Relevance floor: drop videos that share no meaningful word with the
        # topic (catches a totally unrelated fuzzy-search match).
        videos = [v for v in videos if _shares_meaningful_word(topic, v["title"])]

        # Same hijacked-keyword protection Trends/Suggest already get.
        matched_seed = _matching_negative_filter_seed(topic)
        if matched_seed:
            videos = [v for v in videos if _passes_negative_filters({"seed": matched_seed, "title": v["title"]})]

        return videos
    except Exception as e:
        print(f"  [youtube] failed for '{topic}': {e}")
        return None


def collect_for_topics(topics, max_results=3):
    """topics: the Top 10 ranked topic strings — deliberately not the full
    ranked table, since this makes 2 API calls per topic. Returns
    {topic: videos_or_None}."""
    results = {}
    for topic in topics:
        print(f"  checking YouTube competition for '{topic}'...")
        results[topic] = top_videos_for_topic(topic, max_results=max_results)
        time.sleep(0.2)
    return results
