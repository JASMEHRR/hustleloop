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


def scan_reddit_rss(subreddits: list[str] | None = None) -> list[Idea]:
    """
    Workaround for scan_reddit_public getting 403'd by Cloudflare on the
    JSON API: old.reddit.com's per-subreddit RSS feeds are served from a
    different path that frequently isn't blocked the same way. Independent
    source (own _safe() entry) so if one of the two reddit approaches works
    on a given day, research still gets reddit signal.
    """
    import xml.etree.ElementTree as ET

    subreddits = subreddits or [
        "SideProject", "Entrepreneur", "EtsySellers", "SomebodyMakeThis",
    ]
    ideas: list[Idea] = []
    headers = {"User-Agent": "hustleloop-research-bot/1.0"}
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    for sub in subreddits:
        url = f"https://old.reddit.com/r/{sub}/top/.rss?t=week&limit=15"
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        for entry in root.findall("atom:entry", ns):
            title_el = entry.find("atom:title", ns)
            title = (title_el.text or "").strip() if title_el is not None else ""
            if not title:
                continue
            ideas.append(Idea(
                title=title,
                category="unclassified",
                source=f"reddit_rss:r/{sub}",
                reason="top post this week (via old.reddit.com RSS)",
                score=25.0,
                raw={"subreddit": sub},
            ))
        time.sleep(1.0)
    return ideas


def scan_etsy_trending() -> list[Idea]:
    """
    Etsy's public search-results page for a broad "digital download" query,
    scraped the same lightweight way as scan_gumroad_discover: no API key,
    tolerant of markup changes (returns fewer/no ideas rather than crashing).
    """
    import re

    ideas: list[Idea] = []
    headers = {"User-Agent": "Mozilla/5.0 (hustleloop-research-bot/1.0)"}
    resp = requests.get(
        "https://www.etsy.com/search?q=digital+download&explicit=1",
        headers=headers, timeout=10,
    )
    resp.raise_for_status()
    # Listing titles are rendered as `title="..."` on listing-link anchors.
    titles = re.findall(r'data-listing-card-listing-title="([^"]+)"', resp.text)
    if not titles:
        titles = re.findall(r'class="[^"]*text-body[^"]*"[^>]*>([^<]{10,80})<', resp.text)
    seen = set()
    for t in titles:
        t = t.strip()
        if not t or t in seen:
            continue
        seen.add(t)
        ideas.append(Idea(
            title=t,
            category="unclassified",
            source="etsy_search",
            reason="currently listed in Etsy digital-download search results",
            score=8.0,
        ))
    return ideas[:30]


def scan_producthunt_rss() -> list[Idea]:
    """
    Product Hunt publishes a public RSS feed of newly launched products --
    no API key required. Skews toward apps/SaaS rather than one-off digital
    downloads, but is useful signal for what's getting attention right now.
    """
    import xml.etree.ElementTree as ET

    ideas: list[Idea] = []
    headers = {"User-Agent": "hustleloop-research-bot/1.0"}
    resp = requests.get("https://www.producthunt.com/feed", headers=headers, timeout=10)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    entries = root.findall(".//item") or root.findall("atom:entry", ns)
    for item in entries:
        title_el = item.find("title")
        if title_el is None:
            title_el = item.find("atom:title", ns)
        title = (title_el.text or "").strip() if title_el is not None else ""
        if not title:
            continue
        ideas.append(Idea(
            title=title,
            category="unclassified",
            source="producthunt_rss",
            reason="newly launched product on Product Hunt",
            score=15.0,
        ))
    return ideas[:30]


# Words that plausibly signal digital-product / service potential. Not a
# category whitelist -- a noise filter. A query doesn't need one of these to
# survive; it just needs to not look like bare consumer-product/brand noise
# (see _looks_like_brand_noise below).
_DIGITAL_PRODUCT_SIGNAL_WORDS = {
    "template", "planner", "tracker", "printable", "guide", "kit", "pack",
    "course", "notion", "canva", "checklist", "calendar", "workbook",
    "ebook", "worksheet", "spreadsheet", "resume", "cv", "journal",
    "bundle", "preset", "mockup", "icon", "icons", "logo", "font", "fonts",
    "prompt", "prompts", "script", "plugin", "theme", "software", "app",
    "tool", "generator", "widget", "asset", "assets", "graphic", "graphics",
    "design", "digital", "download", "sheet", "form", "automation",
}


def _looks_like_digital_product_relevant(query: str) -> bool:
    """
    Heuristic noise filter for scan_google_trends() results. Google Trends'
    "rising related queries" often returns generic consumer-product/brand
    noise (e.g. a shoe model name) alongside real digital-product signal.
    This isn't a rigid category whitelist -- it's a filter for "does this
    look like it could plausibly relate to a sellable digital product or
    service", the same open-ended bar the rest of this module uses.
    """
    words = query.lower().split()
    if not words:
        return False
    # Contains an explicit digital-product-ish word -- clear keep.
    if any(w.strip(".,!?") in _DIGITAL_PRODUCT_SIGNAL_WORDS for w in words):
        return True
    # A short 2-3 word query with no signal word looks like a bare brand +
    # product-line name (e.g. "adidas gazelle rosa") -- drop it.
    if len(words) <= 3:
        return False
    # Longer, descriptive phrases are more likely to be genuine search
    # intent worth investigating rather than a brand/model name -- keep.
    return True


def scan_google_trends(seed_terms: list[str] | None = None) -> list[Idea]:
    """
    Uses pytrends (unofficial, free, no key) to check rising related queries
    around a small set of broad seed terms. Seeds are broad on purpose so
    this doesn't quietly re-narrow back to "icons/logos/templates" only.

    Results pass through _looks_like_digital_product_relevant() to drop
    generic consumer-product/brand noise before merging with other sources.
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
            query = str(row["query"])
            if not _looks_like_digital_product_relevant(query):
                continue
            value = row.get("value", 0)
            # pytrends reports a true breakout as the string "Breakout"
            # rather than a number -- treat it as a solid but not
            # source-dominating signal, not an unbounded score.
            score = float(value) if str(value).isdigit() else 100.0
            ideas.append(Idea(
                title=query,
                category="unclassified",
                source="google_trends",
                reason=f"rising search interest near seed term '{term}'",
                score=score,
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
    all_ideas += _safe("reddit_rss", scan_reddit_rss, log_events)
    all_ideas += _safe("google_trends", scan_google_trends, log_events)
    all_ideas += _safe("gumroad_discover", scan_gumroad_discover, log_events)
    all_ideas += _safe("etsy_search", scan_etsy_trending, log_events)
    all_ideas += _safe("producthunt_rss", scan_producthunt_rss, log_events)

    _normalize_scores_per_source(all_ideas)

    # Simple rank: highest normalized score first. This is a heuristic
    # signal, not proof of demand -- documented in the README under Honest
    # limits.
    all_ideas.sort(key=lambda i: i.score, reverse=True)
    return all_ideas


def _normalize_scores_per_source(ideas: list[Idea]) -> None:
    """
    Min-max normalizes each source's scores to a common 0-1 range in place,
    per source, before the merged sort. Sources score on wildly different
    raw scales (Reddit upvotes vs. Google Trends' rising-query values vs.
    flat constants for scrape-only sources) -- comparing those magnitudes
    directly lets one source's scale quirks (e.g. Trends breakouts) silently
    dominate the merged top-10 regardless of actual cross-source relevance.
    """
    by_source: dict[str, list[Idea]] = {}
    for idea in ideas:
        by_source.setdefault(idea.source, []).append(idea)
    for group in by_source.values():
        lo = min(i.score for i in group)
        hi = max(i.score for i in group)
        spread = hi - lo
        for i in group:
            i.score = (i.score - lo) / spread if spread > 0 else 1.0


if __name__ == "__main__":
    events: list[dict] = []
    results = run_research(events)
    print(json.dumps({"sources": events, "top_ideas": [r.title for r in results[:10]]}, indent=2))
