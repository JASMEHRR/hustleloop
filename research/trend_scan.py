"""
Open-ended trend research.

Deliberately does NOT hardcode a fixed list of product categories (icons,
logos, newsletters, etc.) -- those were just examples the user happened to
hear about. This module goes looking for whatever digital-product signal
actually exists right now, across any category, using free public sources.

Each source function is independent and wrapped so one source failing
(rate limit, network hiccup, API change) never kills the whole research
step -- it just contributes fewer ideas.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Callable

import requests


@dataclass
class Idea:
    title: str
    category: str          # freeform, whatever the source suggests -- not from a fixed enum
    source: str
    reason: str
    score: float = 0.0
    raw: dict = field(default_factory=dict)


def _safe(name: str, fn: Callable[[], list[Idea]], log: list[dict]) -> list[Idea]:
    try:
        ideas = fn()
        log.append({"source": name, "status": "ok", "count": len(ideas)})
        return ideas
    except Exception as e:  # noqa: BLE001 -- intentionally broad, this is a best-effort scan
        log.append({"source": name, "status": "error", "error": str(e)})
        return []


def scan_reddit_public(subreddits: list[str] | None = None) -> list[Idea]:
    """
    Uses Reddit's public read-only JSON endpoints (no API key required).
    Looks at small-business / side-hustle / digital-product communities
    for posts that mention selling something, to catch real signal about
    what people are actually making money with right now.
    """
    subreddits = subreddits or [
        "SideProject", "Entrepreneur", "smallbusiness", "digitalnomad",
        "EtsySellers", "SomebodyMakeThis", "passive_income",
    ]
    ideas: list[Idea] = []
    headers = {"User-Agent": "hustleloop-research-bot/1.0"}
    for sub in subreddits:
        url = f"https://www.reddit.com/r/{sub}/top.json?limit=15&t=week"
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        for post in data.get("data", {}).get("children", []):
            p = post.get("data", {})
            title = p.get("title", "").strip()
            if not title:
                continue
            ideas.append(Idea(
                title=title,
                category="unclassified",  # let the picker infer category from text later
                source=f"reddit:r/{sub}",
                reason=f"{p.get('ups', 0)} upvotes, {p.get('num_comments', 0)} comments this week",
                score=float(p.get("ups", 0)),
                raw={"permalink": p.get("permalink", ""), "subreddit": sub},
            ))
        time.sleep(1.5)  # be polite to the public endpoint, avoid rate-limit bans
    return ideas


def scan_google_trends(seed_terms: list[str] | None = None) -> list[Idea]:
    """
    Uses pytrends (unofficial, free, no key) to check rising related queries
    around a small set of broad seed terms. Seeds are broad on purpose so
    this doesn't quietly re-narrow back to "icons/logos/templates" only.
    """
    from pytrends.request import TrendReq

    seed_terms = seed_terms or ["digital download", "template", "printable", "notion template", "canva template"]
    pytrends = TrendReq(hl="en-US", tz=0)
    ideas: list[Idea] = []
    for term in seed_terms:
        pytrends.build_payload([term], timeframe="now 7-d")
        related = pytrends.related_queries()
        rising = related.get(term, {}).get("rising")
        if rising is None:
            continue
        for _, row in rising.head(10).iterrows():
            ideas.append(Idea(
                title=str(row["query"]),
                category="unclassified",
                source="google_trends",
                reason=f"rising search interest near seed term '{term}'",
                score=float(row.get("value", 0)) if str(row.get("value", "")).isdigit() else 50.0,
                raw={"seed_term": term},
            ))
        time.sleep(2)
    return ideas


def scan_gumroad_discover() -> list[Idea]:
    """
    Gumroad's public discover/search results give a live read on what
    digital products are actually being sold right now, across every
    category Gumroad supports -- not just the examples the user mentioned.
    """
    ideas: list[Idea] = []
    headers = {"User-Agent": "hustleloop-research-bot/1.0"}
    resp = requests.get("https://discover.gumroad.com/", headers=headers, timeout=10)
    resp.raise_for_status()
    # Gumroad's discover page is an Inertia.js app: product data lives as
    # HTML-entity-encoded JSON in a `data-page` attribute, not as plain
    # `"name":"..."` literals in the page text. Parse that instead of
    # regex-scraping raw HTML -- this is intentionally tolerant -- if Gumroad
    # changes their page structure again, this returns fewer/no ideas rather
    # than crashing, and the caller logs that as a source error via _safe().
    import html
    import json
    import re

    titles: list[str] = []
    match = re.search(r'data-page="([^"]*)"', resp.text)
    if match:
        page_data = json.loads(html.unescape(match.group(1)))
        products = page_data.get("props", {}).get("search_results", {}).get("products", [])
        titles = [p["name"] for p in products if p.get("name")]
    for t in titles[:30]:
        ideas.append(Idea(
            title=t,
            category="unclassified",
            source="gumroad_discover",
            reason="currently listed on Gumroad discover page",
            score=10.0,
        ))
    return ideas


def run_research(log_events: list[dict] | None = None) -> list[Idea]:
    """
    Runs every source, merges results, and returns a ranked idea list.
    Never raises -- a total research failure returns an empty list, and the
    caller (main.py) must handle that gracefully rather than crashing the run.
    """
    log_events = log_events if log_events is not None else []
    all_ideas: list[Idea] = []
    all_ideas += _safe("reddit", scan_reddit_public, log_events)
    all_ideas += _safe("google_trends", scan_google_trends, log_events)
    all_ideas += _safe("gumroad_discover", scan_gumroad_discover, log_events)

    # Simple rank: highest score first. This is a heuristic signal, not proof
    # of demand -- documented in the README under Honest limits.
    all_ideas.sort(key=lambda i: i.score, reverse=True)
    return all_ideas


if __name__ == "__main__":
    events: list[dict] = []
    results = run_research(events)
    print(json.dumps({"sources": events, "top_ideas": [r.title for r in results[:10]]}, indent=2))
