"""
Combines raw hits from every source into one ranked, deduped topic list,
and classifies each topic as EVERGREEN (shows up run after run) or
TRENDING/SPIKE (new this run, high score) using a local history file.
"""
import re
import os
import datetime
import pandas as pd

import config


# Common connector words stripped during clustering so e.g. "what is data
# pipeline" and "what is a data pipeline" collapse into the same topic
# instead of splitting the signal across near-duplicates.
_FILLER_WORDS = {"a", "an", "the", "is", "does"}


def _normalize_title(title):
    """Rough clustering key: lowercase, strip punctuation, drop filler words,
    collapse whitespace."""
    t = title.lower()
    t = re.sub(r"[^\w\s]", "", t)
    words = [w for w in t.split() if w not in _FILLER_WORDS]
    return " ".join(words)


def _minmax_normalize(series):
    if series.max() == series.min():
        return series.apply(lambda x: 0.5)
    return (series - series.min()) / (series.max() - series.min())


def _passes_negative_filters(row):
    """Drops hits where a seed keyword got hijacked by an unrelated meaning
    (see config.NEGATIVE_FILTERS), e.g. 'dbt' meaning Direct Benefit Transfer
    instead of the data tool."""
    seed = str(row.get("seed", "")).lower()
    if not seed or seed not in config.NEGATIVE_FILTERS:
        return True
    title = str(row.get("title", "")).lower()
    return not any(bad in title for bad in config.NEGATIVE_FILTERS[seed])


def _weight_group(row):
    """Which config.WEIGHTS key a row's score gets normalized/weighted under.
    Trends is split by query type — "rising" is the real spiking-now signal,
    "top" is just permanent popularity — so it isn't grouped by source alone
    the way the other sources are."""
    if row["source"] == "trends":
        return "trends_rising" if str(row.get("type", "")).lower() == "rising" else "trends_top"
    return row["source"]


def build_ranked_table(all_hits):
    """
    all_hits: list of dicts from the various source `collect()` functions.
    Returns a DataFrame ranked by composite score, one row per normalized topic.

    Google Suggest (source == "suggest") is excluded entirely — it's static
    autocomplete data with no time signal, so it can't represent "trending
    this week." It's surfaced separately by build_evergreen_question_bank().
    """
    df = pd.DataFrame(all_hits)
    if df.empty:
        return df

    df = df[df["source"] != "suggest"]
    if df.empty:
        return df

    if "seed" not in df.columns:
        df["seed"] = ""
    df["seed"] = df["seed"].fillna("")
    df = df[df.apply(_passes_negative_filters, axis=1)]
    if df.empty:
        return df

    df["norm_title"] = df["title"].apply(_normalize_title)
    df = df[df["norm_title"].str.len() > 0]

    # normalize raw scores 0-1 WITHIN each weight group (so HN points, Reddit
    # upvotes, and Trends' rising/top values are comparable), then apply weight
    df["norm_score"] = 0.0
    for grp, sub in df.groupby(df.apply(_weight_group, axis=1)):
        weight = config.WEIGHTS.get(grp, 1.0)
        df.loc[sub.index, "norm_score"] = _minmax_normalize(sub["score"]) * weight

    # aggregate by normalized topic text: sum weighted scores across sources,
    # count how many sources mentioned it (cross-source agreement = stronger signal)
    grouped = df.groupby("norm_title").agg(
        composite_score=("norm_score", "sum"),
        source_count=("source", "nunique"),
        sources=("source", lambda s: ", ".join(sorted(set(s)))),
        example_title=("title", "first"),
        example_url=("url", "first"),
    ).reset_index()  # keep norm_title as a column — needed for history tracking

    # cross-source agreement bonus: a topic 3 sources agree on beats one loud single-source spike
    grouped["composite_score"] = grouped["composite_score"] * (1 + 0.25 * (grouped["source_count"] - 1))
    grouped = grouped.sort_values("composite_score", ascending=False).reset_index(drop=True)
    return grouped


def build_evergreen_question_bank(all_hits):
    """Google Suggest hits (source == "suggest") are static autocomplete
    data — no time signal, so they don't belong in the scored/ranked Top 10.
    But they're still useful as a running list of the questions people
    always ask, so they get collected here instead: deduped (same
    clustering key as build_ranked_table, including filler-word stripping),
    filtered against the same NEGATIVE_FILTERS, and returned as a plain
    sorted list — no scoring or ranking, by design.
    """
    df = pd.DataFrame([h for h in all_hits if h.get("source") == "suggest"])
    if df.empty:
        return []

    if "seed" not in df.columns:
        df["seed"] = ""
    df["seed"] = df["seed"].fillna("")
    df = df[df.apply(_passes_negative_filters, axis=1)]
    if df.empty:
        return []

    df["norm_title"] = df["title"].apply(_normalize_title)
    df = df[df["norm_title"].str.len() > 0]
    df = df.drop_duplicates(subset="norm_title", keep="first")

    return sorted(df["title"].tolist(), key=str.lower)


def update_history_and_classify(ranked_df, history_path=config.HISTORY_PATH):
    """
    Appends this run's top topics to a local history CSV, then classifies each
    topic in the current run as:
      - EVERGREEN: appeared in >=3 of the last runs (persistent demand)
      - RECURRING: appeared in 2 of the last runs
      - NEW/SPIKE: first time appearing (fresh trend worth jumping on fast)
    """
    today = datetime.date.today().isoformat()
    run_record = ranked_df.head(40).copy()
    run_record["run_date"] = today

    if os.path.exists(history_path):
        history = pd.read_csv(history_path)
        history = pd.concat([history, run_record[["norm_title", "run_date"]]], ignore_index=True)
    else:
        history = run_record[["norm_title", "run_date"]].copy()

    history.to_csv(history_path, index=False)

    appearance_counts = history.groupby("norm_title")["run_date"].nunique()

    def classify(topic):
        count = appearance_counts.get(topic, 1)
        if count >= 3:
            return "EVERGREEN"
        elif count == 2:
            return "RECURRING"
        else:
            return "NEW / SPIKE"

    ranked_df["status"] = ranked_df["norm_title"].apply(classify)
    return ranked_df
