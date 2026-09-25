"""
Clusters the raw items collected from Reddit/YouTube/X into themes, so the
daily digest reads as "here's what the community is discussing" (a handful
of themes) rather than a flat list of 60 unrelated links.

Approach: TF-IDF over each item's text (title + selftext/top comments) +
KMeans. This is a bag-of-words clustering, not semantic/LLM clustering — it
groups items that share vocabulary, which works reasonably well for this use
case (niche discussion tends to cluster around shared tool/topic names) but
will sometimes split a theme across two clusters or lump two unrelated ones
together if their wording overlaps. Good enough for a daily first-pass
digest; treat cluster labels as a starting point; read the items yourself.
"""
import re
from collections import Counter

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans

import config

_STOPWORD_EXTRAS = {
    "data", "analytics", "analyst", "analysis", "using", "use", "used",
    "like", "just", "really", "im", "ive", "dont", "doesnt", "isnt",
    "get", "got", "one", "also", "would", "could", "think", "know",
    "want", "need", "make", "made", "way", "good", "new", "people",
    "honestly", "actually", "literally", "lol", "yeah", "true", "right",
    "thing", "things", "say", "said", "look", "looking", "went", "going",
}


def _item_text(item):
    parts = [item.get("title", ""), item.get("selftext", "")]
    for c in item.get("top_comments", []) or []:
        parts.append(c.get("body", ""))
    return " ".join(p for p in parts if p)


def _label_text(item):
    """Text used specifically for picking a cluster's display label — titles
    weighted 3x over comment bodies. Comment text tends toward generic
    conversational filler ("honestly", "this is so true", "lol") that isn't
    distinctive per-item, so without this weighting a cluster full of
    unrelated items that all happen to share a bland reply style can get a
    label built from that filler instead of what the items are actually
    about. Full _item_text() (title + comments, unweighted) is still what's
    fed to the clustering vectorizer itself — this only affects labeling."""
    title = item.get("title", "")
    rest = [item.get("selftext", "")] + [c.get("body", "") for c in (item.get("top_comments") or [])]
    return " ".join([title] * 3 + [r for r in rest if r])


def _engagement(item):
    """A single comparable engagement number across platforms — Reddit/X use
    score+comments, YouTube comment-sets use total likes+comment count (see
    pulse_sources/youtube_comments.py, where 'score' is already summed likes).
    Not perfectly apples-to-apples across platforms (a Reddit upvote and a
    YouTube like aren't equivalent signals), but good enough for *within-run*
    ranking of "what's getting the most reaction," which is the actual use."""
    return (item.get("score") or 0) + 2 * (item.get("num_comments") or 0)


def _matches_any(text, phrases):
    t = text.lower()
    return any(p in t for p in phrases)


def _is_job_seeker_content(item):
    return _matches_any(_item_text(item), config.JOB_SEEKER_FILTERS)


def _debate_score(item):
    """0-1ish heuristic: fraction of (title + comments) text chunks that
    contain a debate-signal phrase, plus a small bump for a high
    comment-to-score ratio (lots of replies relative to approval = people
    arguing about it, not just upvoting and moving on)."""
    chunks = [item.get("title", "")] + [c.get("body", "") for c in (item.get("top_comments") or [])]
    chunks = [c for c in chunks if c]
    if not chunks:
        return 0.0
    hits = sum(1 for c in chunks if _matches_any(c, config.DEBATE_SIGNAL_PHRASES))
    phrase_signal = hits / len(chunks)

    score, comments = item.get("score") or 0, item.get("num_comments") or 0
    ratio_bump = 0.0
    if score > 0 and comments / max(score, 1) > 0.5:
        ratio_bump = 0.2

    return min(1.0, phrase_signal + ratio_bump)


def _top_terms(texts, n=4):
    """Top distinguishing terms for a cluster's own texts, via a fresh
    single-cluster TF-IDF pass (so terms are ranked within this cluster, not
    against the whole corpus)."""
    try:
        vec = TfidfVectorizer(max_features=50, stop_words="english", ngram_range=(1, 2))
        matrix = vec.fit_transform(texts)
        scores = matrix.sum(axis=0).A1
        terms = vec.get_feature_names_out()
        ranked = sorted(zip(terms, scores), key=lambda t: t[1], reverse=True)
        picked = []
        for term, _ in ranked:
            words = set(re.findall(r"[a-z]+", term))
            if words & _STOPWORD_EXTRAS:
                continue
            picked.append(term)
            if len(picked) >= n:
                break
        return picked or [t for t, _ in ranked[:n]]
    except Exception:
        return []


def cluster_items(items, target_cluster_size=6, max_clusters=8):
    """Returns a list of theme dicts, sorted by total engagement descending:
    {label, items, item_count, total_engagement, debate_score,
     job_seeker_share}. Items too few to meaningfully cluster (< 4) come back
     as a single 'Everything else' theme."""
    if not items:
        return []

    for item in items:
        item["_engagement"] = _engagement(item)
        item["_debate_score"] = _debate_score(item)
        item["_is_job_seeker"] = _is_job_seeker_content(item)

    if len(items) < 4:
        return [{
            "label": "This run's discussion",
            "items": sorted(items, key=lambda i: i["_engagement"], reverse=True),
            "item_count": len(items),
            "total_engagement": sum(i["_engagement"] for i in items),
            "debate_score": sum(i["_debate_score"] for i in items) / len(items),
            "job_seeker_share": sum(1 for i in items if i["_is_job_seeker"]) / len(items),
        }]

    texts = [_item_text(i) for i in items]
    n_clusters = max(2, min(max_clusters, len(items) // target_cluster_size))

    try:
        vectorizer = TfidfVectorizer(max_features=300, stop_words="english", min_df=1, ngram_range=(1, 2))
        matrix = vectorizer.fit_transform(texts)
        km = KMeans(n_clusters=n_clusters, n_init=10, random_state=42)
        labels = km.fit_predict(matrix)
    except Exception as e:
        print(f"  [pulse-cluster] clustering failed ({e}) — falling back to one combined theme.")
        return [{
            "label": "This run's discussion",
            "items": sorted(items, key=lambda i: i["_engagement"], reverse=True),
            "item_count": len(items),
            "total_engagement": sum(i["_engagement"] for i in items),
            "debate_score": sum(i["_debate_score"] for i in items) / len(items),
            "job_seeker_share": sum(1 for i in items if i["_is_job_seeker"]) / len(items),
        }]

    groups = {}
    for item, label in zip(items, labels):
        groups.setdefault(label, []).append(item)

    themes = []
    for label, group_items in groups.items():
        terms = _top_terms([_label_text(i) for i in group_items])
        theme_label = " / ".join(terms[:3]).title() if terms else "Mixed discussion"
        group_items.sort(key=lambda i: i["_engagement"], reverse=True)
        themes.append({
            "label": theme_label,
            "items": group_items,
            "item_count": len(group_items),
            "total_engagement": sum(i["_engagement"] for i in group_items),
            "debate_score": sum(i["_debate_score"] for i in group_items) / len(group_items),
            "job_seeker_share": sum(1 for i in group_items if i["_is_job_seeker"]) / len(group_items),
        })

    themes.sort(key=lambda t: t["total_engagement"], reverse=True)
    return themes
