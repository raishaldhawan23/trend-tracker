"""
Uses the free GitHub Search API to find repos related to niche queries that
have been created or actively pushed recently, sorted by stars. Good for
catching new tools before they hit mainstream content.

No auth required for light use, but GitHub rate-limits unauthenticated
requests to 10 req/min. If you hit limits, set a GITHUB_TOKEN env var and
the script will use it automatically for a much higher limit.
"""
import os
import time
import datetime
import requests

BASE_URL = "https://api.github.com/search/repositories"


def _headers():
    headers = {"Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def fetch_query(query, days_back=30):
    since = (datetime.date.today() - datetime.timedelta(days=days_back)).isoformat()
    q = f"{query} pushed:>{since}"
    params = {"q": q, "sort": "stars", "order": "desc", "per_page": 15}
    try:
        resp = requests.get(BASE_URL, headers=_headers(), params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"  [github] failed for '{query}': {e}")
        return []

    repos = []
    for r in data.get("items", []):
        repos.append({
            "source": "github",
            "query": query,
            "title": r.get("full_name", ""),
            "score": r.get("stargazers_count", 0),
            "num_comments": r.get("open_issues_count", 0),  # proxy for activity
            "url": r.get("html_url", ""),
            "description": r.get("description") or "",
        })
    return repos


def collect(queries, days_back=30):
    all_repos = []
    for q in queries:
        print(f"  searching GitHub for '{q}'...")
        all_repos.extend(fetch_query(q, days_back=days_back))
        time.sleep(2)  # unauthenticated rate limit is tight
    return all_repos
