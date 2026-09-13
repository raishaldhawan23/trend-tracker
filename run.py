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
from aggregate import build_ranked_table, update_history_and_classify
from sources import reddit_signal, hn_signal, github_signal, trends_signal, suggest_signal

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


def _top10_with_ideas(ranked_df):
    top10 = ranked_df.head(10).copy()
    top10["content_angle"] = top10.apply(
        lambda row: generate_content_angle(row["example_title"], row.get("sources", "")), axis=1
    )
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


def write_markdown_report(ranked_df, path="report.md"):
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

    top10 = _top10_with_ideas(ranked_df)

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

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"\nWrote {path}")


def write_excel_report(ranked_df, path="report.xlsx"):
    """Writes the same Top 10 / Content Ideas / Full Table structure as
    report.md, but as separate sheets in an .xlsx workbook."""
    top10 = _top10_with_ideas(ranked_df)

    top10_sheet = top10[["example_title", "status", "composite_score", "sources", "example_url"]].copy()
    top10_sheet.insert(0, "rank", range(1, len(top10_sheet) + 1))
    top10_sheet.columns = ["Rank", "Topic", "Status", "Score", "Sources", "Link"]

    ideas_sheet = top10[["content_angle", "example_title", "status", "composite_score", "example_url"]].copy()
    ideas_sheet.insert(0, "rank", range(1, len(ideas_sheet) + 1))
    ideas_sheet.columns = ["Rank", "Content Angle", "Based On Topic", "Status", "Score", "Link"]

    full_sheet = ranked_df[["example_title", "status", "composite_score", "sources", "example_url"]].copy()
    full_sheet.insert(0, "rank", range(1, len(full_sheet) + 1))
    full_sheet.columns = ["Rank", "Topic", "Status", "Score", "Sources", "Link"]

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        top10_sheet.to_excel(writer, sheet_name="Top 10 This Week", index=False)
        ideas_sheet.to_excel(writer, sheet_name="Content Ideas", index=False)
        full_sheet.to_excel(writer, sheet_name="Full Ranked List", index=False)
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
    if ranked.empty:
        print("No data collected — check network/API errors above.")
        return

    ranked = update_history_and_classify(ranked)
    ranked.to_csv("report.csv", index=False)
    write_markdown_report(ranked)
    write_excel_report(ranked)

    print(
        "\nDone. Open report.md for the ranked list, report.xlsx for a "
        "spreadsheet with Top 10 / Content Ideas / Full List sheets, or "
        "report.csv for raw data."
    )


if __name__ == "__main__":
    main()
