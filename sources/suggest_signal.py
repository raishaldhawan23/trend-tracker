"""
Google's autosuggest endpoint reflects real, frequently-typed queries —
it's a great source of EVERGREEN content ideas (the questions people ask
constantly, not just this week). No key required.

Strategy: for each seed keyword, query autosuggest for the bare keyword
plus common prefixes (how/what/why/best/vs) to surface the actual
long-tail questions people type.
"""
import re
import time
import requests

BASE_URL = "https://suggestqueries.google.com/complete/search"
PREFIXES = ["", "how to", "what is", "why", "best", "vs"]


def _keyword_is_whole_word(keyword, suggestion):
    """Make sure the seed keyword appears as a standalone word/phrase in the
    suggestion, not swallowed into a longer word (avoids junk like autosuggest
    returning something that merely contains the keyword's letters)."""
    return re.search(r"\b" + re.escape(keyword.lower()) + r"\b", suggestion.lower()) is not None


def fetch_suggestions(keyword):
    suggestions = []
    for prefix in PREFIXES:
        query = f"{prefix} {keyword}".strip()
        params = {"client": "firefox", "q": query}
        try:
            resp = requests.get(BASE_URL, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            for s in data[1]:
                if not _keyword_is_whole_word(keyword, s):
                    continue
                suggestions.append({
                    "source": "suggest",
                    "seed": keyword,
                    "title": s,
                    "score": 1,  # autosuggest has no volume number; treated as a flat evergreen signal
                    "num_comments": 0,
                    "url": f"https://www.google.com/search?q={s.replace(' ', '+')}",
                })
        except Exception as e:
            print(f"  [suggest] failed for '{query}': {e}")
        time.sleep(0.3)
    return suggestions


def collect(seed_keywords):
    all_suggestions = []
    for kw in seed_keywords:
        print(f"  fetching autosuggest for '{kw}'...")
        all_suggestions.extend(fetch_suggestions(kw))
    # de-dupe (same suggestion often surfaces from multiple prefixes)
    seen = set()
    deduped = []
    for s in all_suggestions:
        key = s["title"].lower().strip()
        if key not in seen:
            seen.add(key)
            deduped.append(s)
    return deduped
