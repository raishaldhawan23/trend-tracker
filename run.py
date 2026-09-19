"""
Niche Topic Tracker — run this weekly to get a ranked report of what's
trending vs evergreen in your niche (data analytics / AI in analytics /
analytics engineering).

Usage:
    python run.py                  # run everything, write report.md + report.csv
    python run.py --skip-trends    # skip Google Trends (useful if rate-limited)
    python run.py --skip-github    # skip GitHub (useful if rate-limited, no token)
"""
import argparse
import datetime
import re

import pandas as pd

import config
from aggregate import build_ranked_table, update_history_and_classify, build_evergreen_question_bank
from sources import reddit_signal, hn_signal, github_signal, trends_signal, suggest_signal, youtube_signal

# Competitive-check thresholds (see classify_competition below).
YOUTUBE_VIEW_THRESHOLD = 10_000
YOUTUBE_RECENT_DAYS = 365

# Casing overrides for terms that don't follow plain title-case in this niche
# (e.g. "power bi".title() -> "Power Bi", not "Power BI").
_CASING_OVERRIDES = {
    "bi": "BI", "ai": "AI", "llm": "LLM", "llms": "LLMs", "sql": "SQL", "api": "API",
    "etl": "ETL", "elt": "ELT", "ml": "ML", "aws": "AWS", "gcp": "GCP", "ui": "UI",
    "ux": "UX", "csv": "CSV", "json": "JSON", "kpi": "KPI", "kpis": "KPIs", "hn": "HN",
    "dbt": "dbt", "vs": "vs",
}


def _smart_title_case(phrase):
    return " ".join(
        _CASING_OVERRIDES.get(re.sub(r"[^\w]", "", w.lower()), w.capitalize())
        for w in phrase.split()
    )


def _extract_tool_name(title):
    """For a GitHub repo hit like 'owner/repo', use just the repo name — reads
    more naturally in a content angle than the full owner/repo string."""
    return title.rsplit("/", 1)[-1] if "/" in title else title


def _youtube_search_query(title, sources=""):
    """Cleans a raw topic string into a usable YouTube search query. Searching
    the literal 'owner/repo' GitHub string, or an HN headline's 'Show HN:'
    prefix, returns noisy/irrelevant matches — this strips that framing down
    to the actual subject. Also disambiguates overloaded terms: "pipeline" on
    its own matches as much CI/CD-pipeline content as data-pipeline content,
    so it gets "data engineering" appended to bias results toward the right
    sense of the word."""
    source_list = [s.strip() for s in sources.lower().split(",")] if sources else []
    t = title.strip()

    if "github" in source_list:
        t = _extract_tool_name(t)
    elif t.lower().startswith("show hn:"):
        t = t[len("show hn:"):].strip()

    if "pipeline" in t.lower():
        t = f"{t} data engineering"

    return t


def generate_content_angle(title, sources=""):
    """Turns a raw topic string into an actual post/video angle.

    Checked in order:
    1. Prefix/shape patterns (vs / what is / how to / best / why) — these
       mirror the same prefixes suggest_signal.py already queries for, so a
       topic that surfaced via one of those autosuggest prefixes gets
       rephrased the same way here.
    2. Source-specific angles for hits that don't match any of those
       patterns: a GitHub repo gets a "first impressions" angle, an HN story
       gets a "what this means for analytics people" angle.
    3. A generic fallback template, used only as a last resort — most rows
       should be caught by 1 or 2 above.
    """
    t = title.strip()
    lower = t.lower()
    year = datetime.date.today().year
    source_list = [s.strip() for s in sources.lower().split(",")] if sources else []

    m = re.match(r"^(.*?)\s+(?:vs\.?|versus)\s+(.*)$", lower)
    if m:
        a, b = m.group(1).strip(), m.group(2).strip()
        return f"{_smart_title_case(a)} vs {_smart_title_case(b)}: which should you actually pick in {year}?"

    m = re.match(r"^what\s+is\s+(.*)$", lower)
    if m:
        topic = m.group(1).strip()
        return f"{_smart_title_case(topic)}, explained in plain English (a {year} beginner's guide)"

    m = re.match(r"^how\s+to\s+(.*)$", lower)
    if m:
        topic = m.group(1).strip()
        return f"How to {topic}: a step-by-step walkthrough"

    m = re.match(r"^best\s+(.*)$", lower)
    if m:
        topic = m.group(1).strip()
        return f"The best {topic} in {year} (tested and compared)"

    m = re.match(r"^why\s+(.*)$", lower)
    if m:
        topic = m.group(1).strip()
        return f"Why {topic} is happening right now — and what it means for you"

    if "github" in source_list:
        return f"I tried {_extract_tool_name(t)} so you don't have to — first impressions"

    if "hn" in source_list:
        return f"What {t} means for analytics people (a quick take)"

    return f'Why everyone\'s suddenly talking about "{t}" (and what it should mean for your {year} content plan)'


def _format_views(n):
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}".rstrip("0").rstrip(".") + "M views"
    if n >= 1_000:
        return f"{n / 1_000:.1f}".rstrip("0").rstrip(".") + "k views"
    return f"{n} views"


def _days_since(published_at_iso):
    published = datetime.datetime.fromisoformat(published_at_iso.replace("Z", "+00:00"))
    now = datetime.datetime.now(datetime.timezone.utc)
    return (now - published).days


def _format_age(published_at_iso):
    days = _days_since(published_at_iso)
    if days < 60:
        return "1 day ago" if days <= 1 else f"{days} days ago"
    months = days // 30
    if months < 24:
        return f"{months} months ago"
    years = days // 365
    return f"{years} year ago" if years == 1 else f"{years} years ago"


def _video_year(published_at_iso):
    return datetime.datetime.fromisoformat(published_at_iso.replace("Z", "+00:00")).year


def _video_scope(video_title):
    """A rough read on what an existing video's coverage level is, inferred
    from its title alone (no transcript access) — used to suggest what a
    differentiated take would need to go past, not to claim to know its
    actual content."""
    t = video_title.lower()
    if any(w in t for w in ("beginner", "for beginners", "101", "basics", "intro", "introduction")):
        return "a beginner-level walkthrough"
    if any(w in t for w in ("full course", "complete course", "bootcamp", "masterclass", "hours")):
        return "a broad, from-scratch course"
    if any(w in t for w in ("tutorial", "how to", "guide")):
        return "a standard how-to tutorial"
    return "a general overview"


# Signals that a topic is a specific, practical pain point (an error message,
# a "why won't this work" moment) rather than a general subject — these get a
# different WHITESPACE structure (fix-first) than an unfamiliar tool would.
_PAIN_POINT_INDICATORS = (
    "error", "fix", "issue", "problem", "not working", "fails", "failing",
    "broken", "crash", "bug", "troubleshoot", "circular dependency",
    "doesn't work", "won't", "cannot", "can't",
)


def _looks_like_pain_point(topic):
    t = topic.lower()
    return any(ind in t for ind in _PAIN_POINT_INDICATORS)


# A GitHub repo whose title AND description mention none of these is flagged
# as possibly off-niche for a data-analytics/BI/analytics-engineering
# audience (e.g. a general marketing tool, or low-level infra with no BI
# angle) — flagged, not dropped, so relevance is your call, not an assumption
# baked into the score.
_NICHE_SIGNAL_WORDS = (
    "data", "analytics", "dashboard", "bi", "business intelligence", "kpi",
    "reporting", "warehouse", "etl", "elt", "pipeline", "dbt", "sql",
    "visualization", "chart", "metrics", "insight", "llm", "ai agent",
)


def _is_likely_off_niche(topic, description, sources):
    if "github" not in str(sources):
        return False
    text = f"{topic} {description}".lower()
    return not any(w in text for w in _NICHE_SIGNAL_WORDS)


def classify_competition(videos):
    """videos: None (YOUTUBE_API_KEY not set, or the API call failed), []
    (checked, found nothing relevant), or a list of video dicts from
    youtube_signal.top_videos_for_topic(). Returns (tier, top_video) where
    top_video is the highest-view_count video, or None.

    Tiers:
      UNKNOWN       — no competitive data available at all
      WHITESPACE    — 0-1 relevant videos
      OPPORTUNITY   — 2+ videos, but none over YOUTUBE_VIEW_THRESHOLD views
      PROVEN DEMAND — a video over the threshold, published within the last year
      REVISIT       — a video over the threshold, published over a year ago
    """
    if videos is None:
        return "UNKNOWN", None
    if len(videos) <= 1:
        return "WHITESPACE", (videos[0] if videos else None)

    top_video = max(videos, key=lambda v: v["view_count"])
    if top_video["view_count"] <= YOUTUBE_VIEW_THRESHOLD:
        return "OPPORTUNITY", top_video
    if _days_since(top_video["published_at"]) <= YOUTUBE_RECENT_DAYS:
        return "PROVEN DEMAND", top_video
    return "REVISIT", top_video


def build_content_idea(topic, sources, tier, top_video, description=""):
    """A Content Idea entry: a structural suggestion tailored to the
    competitive tier — a hook and shape for the piece, not a competition
    verdict. Never asserts a personal claim or experience on your behalf
    (no assumed "I hit this on a client project" lines) — personalizing it
    is left to you. GitHub-sourced topics with no clear BI/analytics signal
    in their title or description get an off-niche flag prepended, so
    relevance is your judgment call, not an assumption baked into the score.
    """
    off_niche_note = ""
    if _is_likely_off_niche(topic, description, sources):
        off_niche_note = (
            "⚠️ Possibly off-niche for a BI/analytics audience (no clear data/BI "
            "angle in this repo's description) — judge for yourself. "
        )

    if tier == "UNKNOWN":
        # No YOUTUBE_API_KEY configured (or the API call failed) — fall back
        # to the old pattern-based angle rather than block the report on it.
        body = generate_content_angle(topic, sources) + " [competitive check unavailable — set YOUTUBE_API_KEY]"
        return off_niche_note + body

    if tier == "WHITESPACE":
        existing_note = (
            f' (only one relevant video exists: "{top_video["title"]}", {_format_views(top_video["view_count"])})'
            if top_video else ""
        )
        if _looks_like_pain_point(topic):
            body = (
                f'WHITESPACE — "{topic}" is a specific, practical pain point with almost no dedicated '
                f'coverage{existing_note}. Structure: state the actual fix up front, then explain why most '
                "existing explanations (forum answers, docs) get it wrong or skip the real cause."
            )
        elif "github" in str(sources):
            body = (
                f'WHITESPACE — "{topic}" has little to no video coverage yet{existing_note}. '
                "Structure: a quick hands-on first look — install it, then specifically test (1) setup/"
                "onboarding friction, (2) output quality on a real dataset (not the demo data), and "
                "(3) how it fits into an existing stack."
            )
        else:
            body = (
                f'WHITESPACE — "{topic}" has little to no video coverage yet{existing_note}. '
                "Structure: a clear, direct explainer that states plainly what it is and who actually "
                "needs it, before generic coverage catches up."
            )
        return off_niche_note + body

    if tier == "OPPORTUNITY":
        body = (
            f'OPPORTUNITY — a few videos exist on "{topic}" but none has broken through (best is '
            f'"{top_video["title"]}" at {_format_views(top_video["view_count"])}). Structure: the existing '
            "coverage clearly isn't landing — try a sharper, more specific hook (a concrete before/after "
            "or a named use case) instead of another general overview."
        )
        return off_niche_note + body

    if tier == "PROVEN DEMAND":
        scope = _video_scope(top_video["title"])
        body = (
            f'PROVEN DEMAND — "{top_video["title"]}" has {_format_views(top_video["view_count"])} from '
            f'{_format_age(top_video["published_at"])}: {scope}. There\'s a proven audience for this topic. '
            f"Structure: to stand out, go past what {scope} covers — leave room for a real edge case, a "
            "more advanced angle, or a current example instead of repeating the same overview."
        )
        return off_niche_note + body

    if tier == "REVISIT":
        year = _video_year(top_video["published_at"])
        body = (
            f'REVISIT — "{top_video["title"]}" has {_format_views(top_video["view_count"])}, but it\'s from '
            f'{_format_age(top_video["published_at"])} ({year}) and likely outdated. Structure: a direct '
            f'"what\'s changed since {year}" comparison — name the specific things that are different now '
            "(new versions, deprecated features, changed best practices) rather than a generic refresh."
        )
        return off_niche_note + body

    return off_niche_note + generate_content_angle(topic, sources)  # unreachable, but never crash over it


# The three content niches from config.CATEGORY_TAGS, in the order checked
# when building a mixed Top 10 (see build_mixed_top10).
CATEGORIES = ["data_analytics", "ai_analytics", "analytics_engineering"]

# Categories where Trends has demonstrably no real signal for the underlying
# seed and just surfaces broad, unrelated noise instead — confirmed live for
# ai_analytics ("music," "jobs," "google analytics" outranking genuine HN
# content by ~100x). A Trends-sourced row tagged with one of these categories
# is excluded from Top 10 selection for it entirely (not just its guaranteed
# slots — also the score-based leftover fill, so it can't sneak back in that
# way either); Reddit/HN/GitHub fill the category's slots instead. Trends
# still contributes normally everywhere else.
CATEGORIES_EXCLUDING_TRENDS = {"ai_analytics"}


def _is_excluded_trends_row(row):
    return row["category"] in CATEGORIES_EXCLUDING_TRENDS and "trends" in str(row.get("sources", ""))


def build_mixed_top10(ranked_df, per_category=3, total=10):
    """A single global top-N-by-score let GitHub's engineering-only results
    (nobody publishes a repo for "how I built a stakeholder dashboard")
    crowd out the data-analytics and AI-analytics niches entirely. This
    guarantees up to `per_category` rows from each of the three categories
    first, then fills any remaining slots with the next-best rows overall
    regardless of category — so a category with an unusually strong week
    can still claim more than its guaranteed share."""
    if ranked_df.empty or "category" not in ranked_df.columns:
        return ranked_df.head(total).copy()

    eligible = ranked_df[~ranked_df.apply(_is_excluded_trends_row, axis=1)]

    selected_idx = []
    for cat in CATEGORIES:
        cat_rows = eligible[eligible["category"] == cat]
        selected_idx.extend(cat_rows.head(per_category).index.tolist())

    remaining = total - len(selected_idx)
    if remaining > 0:
        leftover = eligible[~eligible.index.isin(selected_idx)]
        selected_idx.extend(leftover.head(remaining).index.tolist())

    return (
        ranked_df.loc[selected_idx]
        .sort_values("composite_score", ascending=False)
        .reset_index(drop=True)
    )


def _top10_with_ideas(ranked_df, youtube_results=None):
    """youtube_results: {topic: videos_or_None} from youtube_signal, already
    limited to this ranked_df's mixed Top 10 topics (see build_mixed_top10).
    Pass None (or omit) to fall back to the old pattern-based angle for
    every row, e.g. when the caller hasn't run the competitive check at all."""
    top10 = build_mixed_top10(ranked_df).copy()
    youtube_results = youtube_results or {}

    tiers, angles, video_titles, video_views, video_urls, off_niche_flags = [], [], [], [], [], []
    for _, row in top10.iterrows():
        topic = row["example_title"]
        sources = row.get("sources", "")
        description = row.get("description", "")
        videos = youtube_results.get(topic)
        tier, top_video = classify_competition(videos)
        angles.append(build_content_idea(topic, sources, tier, top_video, description))
        tiers.append(tier)
        video_titles.append(top_video["title"] if top_video else "")
        video_views.append(top_video["view_count"] if top_video else None)
        video_urls.append(top_video["url"] if top_video else "")
        off_niche_flags.append(_is_likely_off_niche(topic, description, sources))

    top10["competition_tier"] = tiers
    top10["content_angle"] = angles
    top10["top_video_title"] = video_titles
    top10["top_video_views"] = video_views
    top10["top_video_url"] = video_urls
    top10["possibly_off_niche"] = off_niche_flags
    return top10


def collect_all(skip_trends=False, skip_github=False):
    all_hits = []

    print("\n[1/5] Reddit...")
    all_hits.extend(reddit_signal.collect(config.SUBREDDITS))

    print("\n[2/5] Hacker News...")
    all_hits.extend(hn_signal.collect(config.HN_QUERIES, days_back=config.LOOKBACK_DAYS))

    if not skip_github:
        print("\n[3/5] GitHub...")
        all_hits.extend(github_signal.collect(config.GITHUB_QUERIES))
    else:
        print("\n[3/5] GitHub... skipped")

    if not skip_trends:
        print("\n[4/5] Google Trends...")
        all_hits.extend(trends_signal.collect(config.SEED_KEYWORDS))
    else:
        print("\n[4/5] Google Trends... skipped")

    print("\n[5/5] Google Autosuggest (evergreen queries)...")
    all_hits.extend(suggest_signal.collect(config.SEED_KEYWORDS))

    return all_hits


def write_markdown_report(ranked_df, path="report.md", youtube_results=None, evergreen_questions=None):
    today = datetime.date.today().isoformat()
    lines = [f"# Niche Topic Report — {today}\n"]

    lines.append(
        "Ranked by a composite score across Reddit upvotes, Hacker News points, "
        "GitHub star velocity, and Google Trends interest — weighted, and boosted "
        "when multiple sources independently surface the same topic.\n"
    )
    lines.append(
        "**Status key:** `EVERGREEN` = shows up run after run (safe, durable content). "
        "`RECURRING` = showing up a second time (building momentum). "
        "`NEW / SPIKE` = first appearance — jump on it fast if you want the timing edge.\n"
    )

    top10 = _top10_with_ideas(ranked_df, youtube_results=youtube_results)

    lines.append("## Top 10 This Week\n")
    for i, row in top10.iterrows():
        link = f" ([link]({row['example_url']}))" if row.get("example_url") else ""
        lines.append(
            f"{i+1}. **{row['example_title']}** — {row['status']}, "
            f"score {row['composite_score']:.2f} ({row['sources']}){link}"
        )

    lines.append("\n## Content Topic Ideas\n")
    lines.append("Ready-to-use post/video angles based on the topics above:\n")
    for i, row in top10.iterrows():
        lines.append(f"{i+1}. {row['content_angle']}")
        lines.append(f'   _(based on: "{row["example_title"]}")_')

    n_full = min(50, len(ranked_df))
    lines.append(f"\n## Full Ranked List (top {n_full})\n")
    lines.append("| Rank | Topic | Status | Score | Sources | Example Link |")
    lines.append("|---|---|---|---|---|---|")
    for i, row in ranked_df.head(50).iterrows():
        link = f"[link]({row['example_url']})" if row.get("example_url") else ""
        lines.append(
            f"| {i+1} | {row['example_title']} | {row['status']} | "
            f"{row['composite_score']:.2f} | {row['sources']} | {link} |"
        )

    evergreen_questions = evergreen_questions or []
    lines.append(f"\n## Evergreen Question Bank ({len(evergreen_questions)} questions)\n")
    lines.append(
        "Google autocomplete data — no weekly time signal, so it doesn't compete "
        "in the ranking above, but it's a reliable list of the questions people "
        "always ask. Good for always-relevant, not necessarily timely, content.\n"
    )
    if evergreen_questions:
        for q in evergreen_questions:
            lines.append(f"- {q}")
    else:
        lines.append("_(none collected this run)_")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"\nWrote {path}")


def write_excel_report(ranked_df, path="report.xlsx", youtube_results=None, evergreen_questions=None):
    """Writes the same Top 10 / Content Ideas / Full Table structure as
    report.md, but as separate sheets in an .xlsx workbook."""
    top10 = _top10_with_ideas(ranked_df, youtube_results=youtube_results)

    top10_sheet = top10[["example_title", "status", "composite_score", "sources", "example_url"]].copy()
    top10_sheet.insert(0, "rank", range(1, len(top10_sheet) + 1))
    top10_sheet.columns = ["Rank", "Topic", "Status", "Score", "Sources", "Link"]

    ideas_sheet = top10[[
        "competition_tier", "content_angle", "example_title", "possibly_off_niche",
        "top_video_title", "top_video_views", "status", "composite_score", "example_url",
    ]].copy()
    ideas_sheet.insert(0, "rank", range(1, len(ideas_sheet) + 1))
    ideas_sheet.columns = [
        "Rank", "Competition Tier", "Content Angle", "Based On Topic", "Possibly Off-Niche",
        "Top Competing Video", "Video Views", "Status", "Score", "Link",
    ]

    full_sheet = ranked_df[["example_title", "status", "composite_score", "sources", "example_url"]].copy()
    full_sheet.insert(0, "rank", range(1, len(full_sheet) + 1))
    full_sheet.columns = ["Rank", "Topic", "Status", "Score", "Sources", "Link"]

    evergreen_sheet = pd.DataFrame({"Question": evergreen_questions or []})

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        top10_sheet.to_excel(writer, sheet_name="Top 10 This Week", index=False)
        ideas_sheet.to_excel(writer, sheet_name="Content Ideas", index=False)
        full_sheet.to_excel(writer, sheet_name="Full Ranked List", index=False)
        evergreen_sheet.to_excel(writer, sheet_name="Evergreen Questions", index=False)
    print(f"Wrote {path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-trends", action="store_true")
    parser.add_argument("--skip-github", action="store_true")
    args = parser.parse_args()

    print("Collecting signal from all sources — this takes a few minutes...")
    all_hits = collect_all(skip_trends=args.skip_trends, skip_github=args.skip_github)

    print(f"\nCollected {len(all_hits)} raw items. Ranking and classifying...")
    ranked = build_ranked_table(all_hits)
    evergreen_questions = build_evergreen_question_bank(all_hits)
    if ranked.empty:
        print("No data collected — check network/API errors above.")
        return

    ranked = update_history_and_classify(ranked)

    top10_rows = build_mixed_top10(ranked)
    # Map each Top 10 topic to a cleaned-up search query (e.g. a GitHub
    # 'owner/repo' hit searches on just the repo name, not the literal path).
    queries = {
        row["example_title"]: _youtube_search_query(row["example_title"], row.get("sources", ""))
        for _, row in top10_rows.iterrows()
    }
    if youtube_signal.is_configured():
        print("\nChecking YouTube competition for the Top 10 topics...")
        youtube_by_query = youtube_signal.collect_for_topics(list(queries.values()))
        youtube_results = {topic: youtube_by_query.get(query) for topic, query in queries.items()}
    else:
        print(
            "\nYOUTUBE_API_KEY not set — skipping the YouTube competitive check "
            "(Content Ideas will fall back to the pattern-based angle instead)."
        )
        youtube_results = {topic: None for topic in queries}

    ranked.to_csv("report.csv", index=False)
    write_markdown_report(ranked, youtube_results=youtube_results, evergreen_questions=evergreen_questions)
    write_excel_report(ranked, youtube_results=youtube_results, evergreen_questions=evergreen_questions)

    print(
        "\nDone. Open report.md for the ranked list, report.xlsx for a "
        "spreadsheet with Top 10 / Content Ideas / Full List sheets, or "
        "report.csv for raw data."
    )


if __name__ == "__main__":
    main()
