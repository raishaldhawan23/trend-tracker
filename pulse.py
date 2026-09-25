"""
Niche Pulse — daily monitor for what your niche (data analytics / AI in
analytics / analytics engineering) is discussing right now on Reddit,
YouTube comments, and X/Twitter, clustered into themes.

Separate tool from run.py (the weekly Top-10 content-ideation tracker) —
this one answers "what is the community reacting to / debating today,"
not "what should I make content about this week." Same repo, same config.py
niche definitions, different job and a much shorter time window.

Usage:
    python pulse.py                    # run everything, write pulse_report.md/.xlsx/.json
    python pulse.py --skip-twitter     # skip X (useful since it's the least reliable source)
    python pulse.py --lookback-hours 24
    python pulse.py --email            # also send the digest via Gmail SMTP (see send_email.py)
"""
import argparse
import datetime

import config
from pulse_sources import reddit_pulse, youtube_comments, twitter_pulse
from pulse_cluster import cluster_items
import pulse_report


def collect_all(lookback_hours, skip_reddit=False, skip_youtube=False, skip_twitter=False):
    all_items = []
    platform_counts = {}
    run_notes = []

    if not skip_reddit:
        print("\n[1/3] Reddit (broad search)...")
        reddit_items = reddit_pulse.collect(config.PULSE_QUERIES, lookback_hours)
        all_items.extend(reddit_items)
        platform_counts["reddit"] = len(reddit_items)
    else:
        print("\n[1/3] Reddit... skipped")

    if not skip_youtube:
        print("\n[2/3] YouTube comments...")
        if youtube_comments.is_configured():
            yt_items = youtube_comments.collect(config.PULSE_QUERIES, lookback_hours)
            all_items.extend(yt_items)
            platform_counts["youtube"] = len(yt_items)
        else:
            run_notes.append("YouTube skipped — YOUTUBE_API_KEY not set.")
            platform_counts["youtube"] = 0
    else:
        print("\n[2/3] YouTube comments... skipped")

    if not skip_twitter:
        print("\n[3/3] X/Twitter (best-effort)...")
        tw_items = twitter_pulse.collect(config.PULSE_QUERIES, lookback_hours)
        all_items.extend(tw_items)
        platform_counts["twitter"] = len(tw_items)
        if not tw_items:
            run_notes.append(
                "X/Twitter returned 0 results — expected given free-tier access restrictions "
                "(see pulse_sources/twitter_pulse.py); not necessarily an error."
            )
    else:
        print("\n[3/3] X/Twitter... skipped")

    return all_items, platform_counts, run_notes


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lookback-hours", type=float, default=config.PULSE_LOOKBACK_HOURS)
    parser.add_argument("--skip-reddit", action="store_true")
    parser.add_argument("--skip-youtube", action="store_true")
    parser.add_argument("--skip-twitter", action="store_true")
    parser.add_argument("--email", action="store_true", help="also send the digest via Gmail SMTP")
    args = parser.parse_args()

    print(f"Collecting niche pulse — last {args.lookback_hours} hours...")
    items, platform_counts, run_notes = collect_all(
        args.lookback_hours,
        skip_reddit=args.skip_reddit,
        skip_youtube=args.skip_youtube,
        skip_twitter=args.skip_twitter,
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
