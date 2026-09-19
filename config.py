"""
Central config for the topic tracker.
Edit these lists to tune what 'your niche' means — no code changes needed elsewhere.
"""

# Seed keywords used for Google Trends (related/rising queries) and Google Suggest.
# Keep these broad-ish — the tools expand them into specific rising queries for you.
#
# Deliberately NOT here: "dbt". As a bare keyword it's too semantically
# overloaded for Trends/Suggest to ever fully disambiguate — Direct Benefit
# Transfer government schemes, Dialectical Behavior Therapy, and apparently
# even "meditation" via Google's own related-query graph, no matter how big
# NEGATIVE_FILTERS gets. Reddit, HN, and GitHub (see HN_QUERIES/GITHUB_QUERIES
# below) already use "dbt" unambiguously as a community/dev-facing search, so
# real dbt-the-tool signal still comes through those sources. If Trends-based
# dbt signal is wanted later, that would need Google's Knowledge Graph
# topic-ID feature (searching a specific "dbt (data tool)" entity ID instead
# of the plain keyword) — a possible future improvement, not implemented here.
# Grouped by CATEGORY_TAGS below rather than alphabetically, so it's obvious
# at a glance which of the three content niches each seed feeds. Analytics
# PRACTICE terms (dashboards, BI, stakeholder-facing work) were previously
# under-represented here relative to analytics ENGINEERING terms (dbt,
# pipelines) — GitHub only ever surfaces tool/engineering repos (nobody
# publishes a repo for "how I built a stakeholder dashboard"), so without
# enough practice-side seeds feeding Trends/Suggest, the Top 10 skewed toward
# data engineering by default. The additions below (Power BI DAX, dashboard
# design, KPI dashboard, etc.) balance that out.
#
# Also deliberately NOT here: "AI agent analytics" and "AI in analytics" —
# same class of problem as the earlier "dbt" removal. They're short/generic
# enough that Google's related-query graph can't tell they're supposed to be
# about analytics at all, and defaults to surfacing whatever's broadly
# trending among anyone who searched them for unrelated reasons — confirmed
# live: "music," "jobs," and "google analytics" outranking genuine content by
# roughly 100x under these seeds. "AI agent analytics" stays in HN_QUERIES
# (HN hasn't shown this failure mode — see build_mixed_top10 in run.py, which
# also excludes Trends specifically from the ai_analytics category slate for
# the same reason); real ai_analytics signal comes from HN/GitHub/Reddit now.
SEED_KEYWORDS = [
    # data_analytics
    "data analytics",
    "power bi",
    "Power BI DAX",
    "dashboard design",
    "stakeholder reporting",
    "KPI dashboard",
    "business intelligence trends",
    # ai_analytics
    "LLM analytics",
    "AI copilot for data analysis",
    "ChatGPT for data analysis",
    "LLM for BI",
    # analytics_engineering
    "analytics engineering",
    "data engineering",
    "data pipeline",
]

# Subreddits worth scanning for what practitioners are actually discussing/upvoting.
SUBREDDITS = [
    "analytics",
    "BusinessIntelligence",
    "dataengineering",
    "datascience",
    "PowerBI",
    "dataanalysis",
    "MachineLearning",
    "LocalLLaMA",  # picks up a lot of "AI in real workflows" chatter
]

# Hacker News search terms (Algolia API) — good for catching tool launches / dev-facing buzz.
# "LLM" and "AI agent" alone were too broad and pulled in generic AI stories with
# no analytics angle — narrowed to phrases that keep results on-topic.
HN_QUERIES = [
    "analytics engineering",
    "dbt",
    "data pipeline",
    "AI agent analytics",
    "LLM data analysis",
    "LLM analytics workflow",
    "data analyst",
]

# GitHub search terms — used to catch trending tools/repos in the space (created/pushed recently, sorted by stars).
GITHUB_QUERIES = [
    "analytics engineering",
    "dbt",
    "data pipeline AI",
    "llm agent analytics",
]

# Which content niche each seed keyword / HN query / GitHub query belongs to:
# "data_analytics" (dashboards, BI, stakeholder-facing analytics practice),
# "ai_analytics" (AI/LLM applied to analytics work), or "analytics_engineering"
# (dbt, pipelines, the underlying data infra). aggregate.py propagates this
# onto each ranked row via its originating seed/query, and run.py uses it to
# build a guaranteed mixed Top 10 instead of one that GitHub's engineering-only
# results can crowd out on raw score alone. A row whose source doesn't map to
# any of these (e.g. Reddit, which searches subreddits rather than a keyword)
# is left uncategorized and only fills leftover Top 10 slots by score.
CATEGORY_TAGS = {
    # data_analytics
    "data analytics": "data_analytics",
    "power bi": "data_analytics",
    "Power BI DAX": "data_analytics",
    "dashboard design": "data_analytics",
    "stakeholder reporting": "data_analytics",
    "KPI dashboard": "data_analytics",
    "business intelligence trends": "data_analytics",
    "data analyst": "data_analytics",  # HN_QUERIES
    # ai_analytics
    "LLM analytics": "ai_analytics",
    "AI agent analytics": "ai_analytics",  # HN_QUERIES only now — see SEED_KEYWORDS comment
    "AI copilot for data analysis": "ai_analytics",
    "ChatGPT for data analysis": "ai_analytics",
    "LLM for BI": "ai_analytics",
    "LLM data analysis": "ai_analytics",       # HN_QUERIES
    "LLM analytics workflow": "ai_analytics",  # HN_QUERIES
    "llm agent analytics": "ai_analytics",     # GITHUB_QUERIES
    # analytics_engineering
    "analytics engineering": "analytics_engineering",
    "data engineering": "analytics_engineering",
    "data pipeline": "analytics_engineering",
    "dbt": "analytics_engineering",             # HN_QUERIES / GITHUB_QUERIES
    "data pipeline AI": "analytics_engineering",  # GITHUB_QUERIES
}

# Substrings that mean a seed keyword got hijacked by an unrelated meaning
# (e.g. "dbt" = Direct Benefit Transfer / govt scheme / therapy, not the tool).
# Any Trends/Suggest hit for that seed whose title contains one of these is dropped.
#
# "dbt" is no longer in SEED_KEYWORDS (see the comment there), so this entry
# no longer filters any Trends/Suggest rows directly — but it's still used by
# sources/youtube_signal.py, which matches a search topic against these keys
# by substring regardless of where the topic came from (e.g. a legitimate
# Reddit/HN/GitHub "dbt" topic could still coincidentally pull a bad YouTube
# match). Kept for that reason.
NEGATIVE_FILTERS = {
    "dbt": [
        "therapy", "therapie", "cbt", "bpd", "psycholog", "counsel",
        "mental health", "workbook", "skills for adults",
        "npci", "kisan", "maha", "sevana", "pension", "scholarship",
        "farmer", "agricultur", "bihar", "karnataka", "aadhaar",
        "bank account", "bank", "sbi", "pnb", "portal", "login",
        "status check", "check status", "link", "mp dbt", "mha dbt",
        "biocare", "pfms",
    ],
    "power bi": [
        "power bill", "power bike", "power big building", "power biomass",
        "power bioreactor", "satisfactory", "subnautica", "pokopia",
    ],
    # "engineering" alone is broad enough that Google's related-query graph
    # pulled in the unrelated cybersecurity sense ("social engineering
    # attack") under one of these two seeds — added to both since the exact
    # seed couldn't be confirmed live (Trends was rate-limiting at the time).
    "analytics engineering": ["social engineering attack", "social engineering"],
    "data engineering": ["social engineering attack", "social engineering"],
}

# Where run history (for evergreen vs spike detection) is stored.
HISTORY_PATH = "history.csv"

# How many days back counts as "recent" for Reddit/HN/GitHub scans.
LOOKBACK_DAYS = 7

# Composite score weights — tune if one source feels noisier than the others.
# Google Trends is split by query type (see trends_signal.py's "type" field):
# "rising" queries are the real spiking-now signal, so they're weighted heavily.
# "top" queries are just permanently popular terms (e.g. "power bi", "data
# analytics") that would show up in the Top 10 in any given week regardless of
# what's actually trending — weighted low so they barely register.
WEIGHTS = {
    "reddit": 1.0,
    "hn": 1.2,           # HN points are a strong practitioner-buzz signal, weighted slightly higher
    "github": 0.8,
    "trends_rising": 3.0,
    "trends_top": 0.3,
}

# Fixed upper bounds per source's raw score, used to normalize scores onto a
# comparable 0-1 scale (see aggregate.py — norm_score = min(raw/cap, 1.0)).
# Deliberately NOT min-max within each run's batch: min-max always maps
# today's single highest-scoring item to exactly 1.0 (full weight) no matter
# how strong or weak it actually is or whether it's even topically relevant
# — that's what let an off-topic one-day Trends spike ("lidl near me", then
# "ice cream") get crowned #1 purely for being the day's top number. A fixed
# cap means a moderate spike scores as moderate, and only a score that's
# genuinely strong in absolute terms reaches full weight. These are rough
# estimates of what a strong (not just "today's highest") result looks like
# for each source — tune from observed data as the tracker accumulates runs.
SCALE_CAPS = {
    "trends": 500,   # matches the existing rising-query percentage cap
    "reddit": 3000,
    "hn": 800,
    "github": 20000,  # raised from 5000 — real runs saw raw scores up to 50,900,
                       # so 5000 was blowing through by a wide margin and tying
                       # 9-11 repos per run at the 1.0 ceiling
}
