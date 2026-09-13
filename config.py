"""
Central config for the topic tracker.
Edit these lists to tune what 'your niche' means — no code changes needed elsewhere.
"""

# Seed keywords used for Google Trends (related/rising queries) and Google Suggest.
# Keep these broad-ish — the tools expand them into specific rising queries for you.
SEED_KEYWORDS = [
    "data analytics",
    "AI in analytics",
    "analytics engineering",
    "dbt",
    "power bi",
    "data engineering",
    "data pipeline",
    "LLM analytics",
    "AI agent analytics",
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

# Substrings that mean a seed keyword got hijacked by an unrelated meaning
# (e.g. "dbt" = Direct Benefit Transfer / govt scheme / therapy, not the tool).
# Any Trends/Suggest hit for that seed whose title contains one of these is dropped.
NEGATIVE_FILTERS = {
    "dbt": [
        "therapy", "therapie", "cbt", "bpd", "psycholog", "counsel",
        "mental health", "workbook", "skills for adults",
        "npci", "kisan", "maha", "sevana", "pension", "scholarship",
        "farmer", "agricultur", "bihar", "karnataka", "aadhaar",
        "bank account", "bank", "sbi", "pnb", "portal", "login",
        "status check", "check status", "link", "mp dbt", "mha dbt",
    ],
    "power bi": [
        "power bill", "power bike", "power big building", "power biomass",
        "power bioreactor", "satisfactory", "subnautica", "pokopia",
    ],
}

# Where run history (for evergreen vs spike detection) is stored.
HISTORY_PATH = "history.csv"

# How many days back counts as "recent" for Reddit/HN/GitHub scans.
LOOKBACK_DAYS = 7

# Composite score weights — tune if one source feels noisier than the others.
WEIGHTS = {
    "reddit": 1.0,
    "hn": 1.2,       # HN points are a strong practitioner-buzz signal, weighted slightly higher
    "github": 0.8,
    "trends": 1.5,   # Google Trends rising queries weighted highest — direct search-intent signal
}
