"""
Niche Pulse — daily monitor for what your niche (data analytics / AI in
analytics / analytics engineering) is discussing right now on Reddit and
YouTube comments, clustered into themes.

Reddit note: this scans a curated subreddit list (config.SUBREDDITS), not
all of Reddit — see pulse_sources/reddit_pulse.py's module docstring for
why (Reddit closed free site-wide search access in 2026; per-subreddit
listing endpoints still work).

X/Twitter was tried and dropped (2026-09-26): free scraping libraries
(snscrape) are reliably blocked by X now, and paying for their API (~$200/mo)
wasn't worth it for this. See git history if that changes and it's worth
revisiting.

Separate tool from run.py (the weekly Top-10 content-ideation tracker) —
this one answers "what is the community reacting to / debating today,"
not "what should I make content about this week." Same repo, same config.py
niche definitions, different job and a much shorter time window.

Usage:
    python pulse.py                    # run everything, write pulse_report.md/.xlsx/.json
    python pulse.py --lookback-hours 24
    python pulse.py --email            # also send the digest via Gmail SMTP (see send_email.py)
"""
import argparse
import datetime

import config
from pulse_sources import reddit_pulse, youtube_comments
from pulse_cluster import cluster_items
import pulse_report


def collect_all(lookback_hours, skip_reddit=False, skip_youtube=False):
    all_items = []
    platform_counts = {}
    run_notes = []

    if not skip_reddit:
        print("\n[1/2] Reddit (curated subreddits)...")
        reddit_items = reddit_pulse.collect(config.SUBREDDITS, lookback_hours)
        all_items.extend(reddit_items)
        platform_counts["reddit"] = len(reddit_items)
    else:
        print("\n[1/2] Reddit... skipped")

    if not skip_youtube:
        print("\n[2/2] YouTube comments...")
        if youtube_comments.is_configured():
            yt_items = youtube_comments.collect(config.PULSE_QUERIES, lookback_hours)
            all_items.extend(yt_items)
            platform_counts["youtube"] = len(yt_items)
        else:
            run_notes.append("YouTube skipped — YOUTUBE_API_KEY not set.")
            platform_counts["youtube"] = 0
    else:
        print("\n[2/2] YouTube comments... skipped")

    return all_items, platform_counts, run_notes


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lookback-hours", type=float, default=config.PULSE_LOOKBACK_HOURS)
    parser.add_argument("--skip-reddit", action="store_true")
    parser.add_argument("--skip-youtube", action="store_true")
    parser.add_argument("--email", action="store_true", help="also send the digest via Gmail SMTP")
    args = parser.parse_args()

    print(f"Collecting niche pulse — last {args.lookback_hours} hours...")
    items, platform_counts, run_notes = collect_all(
        args.lookback_hours,
        skip_reddit=args.skip_reddit,
        skip_youtube=args.skip_youtube,
    )

    print(f"\nCollected {len(items)} raw items. Clustering into themes...")
    themes = cluster_items(items)

    pulse_report.write_json(items, path="pulse_raw.json")
    markdown = pulse_report.write_markdown(
        themes, args.lookback_hours, platform_counts, path="pulse_report.md", run_notes=run_notes,
    )
    pulse_report.write_excel(themes, path="pulse_report.xlsx")

    print(f"\nDone. {len(themes)} themes from {len(items)} items.")

    if args.email:
        import send_email
        today = datetime.date.today().isoformat()
        send_email.send_digest(subject=f"Niche Pulse — {today}", markdown_body=markdown)


if __name__ == "__main__":
    main()
