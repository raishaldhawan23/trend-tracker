"""
Writes the daily niche-pulse digest: a markdown report (also used as the
email body), an .xlsx workbook with raw items, and a raw .json dump — same
"report + raw data" pattern as the weekly tracker's report.md/.csv/.xlsx.
"""
import datetime
import json

import pandas as pd


def _format_engagement(item):
    platform = item.get("platform", "")
    score, comments = item.get("score", 0), item.get("num_comments", 0)
    if platform == "youtube":
        return f"{score} comment likes, {comments} comments surfaced"
    if platform == "twitter":
        return f"{score} likes+RTs, {comments} replies"
    return f"{score} upvotes, {comments} comments"  # reddit default


def _theme_flags(theme):
    flags = []
    if theme["debate_score"] >= 0.35:
        flags.append("⚔️ Debated")
    if theme["job_seeker_share"] >= 0.5:
        flags.append("🎯 Mostly job-seeker audience — low priority for hiring-manager content")
    return " ".join(flags)


def build_markdown(themes, lookback_hours, platform_counts, run_notes=None):
    today = datetime.date.today().isoformat()
    lines = [f"# Niche Pulse — {today}\n"]
    lines.append(
        f"What your niche (data analytics / AI in analytics / analytics engineering) has been "
        f"discussing on Reddit, YouTube comments, and X over the last ~{lookback_hours} hours, "
        f"clustered into themes.\n"
    )
    lines.append(
        "**Audience lens:** this is filtered for content that shows up as a practitioner with "
        "real opinions — the kind of conversation that resonates with people who hire/manage "
        "analytics talent — not job-seeker discussion. Themes that skew job-seeker are tagged "
        "🎯 below rather than removed, so you can still see them if that's most of what's live "
        "today.\n"
    )

    lines.append("**Coverage this run:** " + ", ".join(
        f"{platform} ({count})" for platform, count in platform_counts.items()
    ) + "\n")

    if run_notes:
        lines.append("**Notes:**")
        for note in run_notes:
            lines.append(f"- {note}")
        lines.append("")

    if not themes:
        lines.append("No matching discussion found in this window.\n")
        return "\n".join(lines)

    lines.append("## Themes\n")
    for i, theme in enumerate(themes, 1):
        flags = _theme_flags(theme)
        flag_str = f" {flags}" if flags else ""
        lines.append(
            f"### {i}. {theme['label']} — {theme['item_count']} items, "
            f"{theme['total_engagement']} total engagement{flag_str}\n"
        )
        for item in theme["items"][:5]:
            title = item.get("title", "")[:140]
            lines.append(
                f"- **[{item['platform']}]** {title} — {_format_engagement(item)} "
                f"([link]({item.get('url', '')}))"
            )
            top_comment = (item.get("top_comments") or [None])[0]
            if top_comment and top_comment.get("body"):
                snippet = top_comment["body"][:180].replace("\n", " ")
                lines.append(f"  - top reply: \"{snippet}\"")
        lines.append("")

    lines.append("## What's getting reaction (top 5 overall)\n")
    all_items = [item for theme in themes for item in theme["items"]]
    all_items.sort(key=lambda i: i.get("_engagement", 0), reverse=True)
    for item in all_items[:5]:
        lines.append(f"- **[{item['platform']}]** {item.get('title', '')[:140]} ([link]({item.get('url', '')}))")

    lines.append("\n## What's being debated (top 5 by debate signal)\n")
    debated = [i for i in all_items if i.get("_debate_score", 0) > 0]
    debated.sort(key=lambda i: i.get("_debate_score", 0), reverse=True)
    if debated:
        for item in debated[:5]:
            lines.append(f"- **[{item['platform']}]** {item.get('title', '')[:140]} ([link]({item.get('url', '')}))")
    else:
        lines.append("_(nothing flagged as a clear debate this run)_")

    return "\n".join(lines)


def write_markdown(themes, lookback_hours, platform_counts, path="pulse_report.md", run_notes=None):
    content = build_markdown(themes, lookback_hours, platform_counts, run_notes=run_notes)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Wrote {path}")
    return content


def write_excel(themes, path="pulse_report.xlsx"):
    rows = []
    for theme in themes:
        for item in theme["items"]:
            rows.append({
                "Theme": theme["label"],
                "Platform": item.get("platform", ""),
                "Title": item.get("title", ""),
                "Score": item.get("score", 0),
                "Comments": item.get("num_comments", 0),
                "Engagement": item.get("_engagement", 0),
                "Debate Score": round(item.get("_debate_score", 0), 2),
                "Job-Seeker Flagged": item.get("_is_job_seeker", False),
                "URL": item.get("url", ""),
                "Top Comment": (item.get("top_comments") or [{}])[0].get("body", "")[:300],
            })

    themes_summary = pd.DataFrame([{
        "Theme": t["label"],
        "Items": t["item_count"],
        "Total Engagement": t["total_engagement"],
        "Debate Score": round(t["debate_score"], 2),
        "Job-Seeker Share": round(t["job_seeker_share"], 2),
    } for t in themes])

    items_df = pd.DataFrame(rows)

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        themes_summary.to_excel(writer, sheet_name="Themes", index=False)
        items_df.to_excel(writer, sheet_name="All Items", index=False)
    print(f"Wrote {path}")


def write_json(items, path="pulse_raw.json"):
    """Raw collected items (pre-clustering), so nothing is lost even if the
    clustering step's grouping isn't what you'd want for a given run."""
    clean = []
    for item in items:
        clean.append({k: v for k, v in item.items() if not k.startswith("_")})
    with open(path, "w", encoding="utf-8") as f:
        json.dump(clean, f, indent=2, default=str)
    print(f"Wrote {path}")
