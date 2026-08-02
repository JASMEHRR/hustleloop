"""
Turns a researched Idea into a detailed, ready-to-paste design prompt for a
Claude chat (the user pastes it in, gets back an HTML/artifact design, and
uploads that themselves). This is the primary product now -- the prompt
itself has to be specific enough to produce something sellable, not generic
filler like "make it look nice, use nice colors."

Ideas are routed into a design "bucket" (planner/printable, icon/graphic
pack, template, guide/ebook, generic) by lightweight keyword match -- same
spirit as generate/generators.py's pick_format(), but the buckets here are
about design brief content, not file-generator routing, so they're kept
separate rather than importing that function.
"""

from __future__ import annotations

from research.trend_scan import Idea


def _bucket(title: str) -> str:
    text = title.lower()
    # Web signals checked first and specifically -- a bare "template" word
    # (e.g. "girlfriend day template") must NOT route to the website-style
    # bucket just because it shares the word "template" with "website
    # template"; only an explicit web/site signal should.
    if any(k in text for k in ("website", "landing page", "webpage", "web app", "site template", "newsletter")):
        return "template"
    if any(k in text for k in (
        "planner", "checklist", "tracker", "printable", "calendar", "journal",
        "template", "kit", "worksheet", "invite", "invitation", "itinerary",
    )):
        return "planner"
    if any(k in text for k in ("icon", "logo", "emoji", "sticker", "clipart", "graphic pack")):
        return "icon_pack"
    if any(k in text for k in ("guide", "ebook", "e-book", "workbook", "how to", "how-to", "course")):
        return "guide"
    if any(k in text for k in ("quote", "social media", "instagram", "post template", "announcement")):
        return "social"
    return "generic"


_BUCKET_BRIEFS = {
    "planner": """
Visual style: pick a single accent color plus a warm neutral background (e.g. cream/off-white paper tone, not stark white) -- avoid generic corporate blue. Typography: one serif or rounded-sans display font for headers, one clean sans for body/labels, sized for print legibility (headers 18-24pt equiv, body 10-11pt equiv). Layout: A4/Letter portrait grid with clear top header band (title + date field), a structured body with ruled sections/boxes (not just a bulleted list), and consistent margins (~20mm) so it prints cleanly.

Specific elements to include:
- A header zone with the title, a date/week field, and a thin divider rule
- 2-3 distinct content zones with visible borders or shaded backgrounds to separate sections (e.g. "Top priorities" box, checklist rows with checkbox squares, a notes/reflection strip at the bottom)
- Checkbox or tick-box elements that look intentionally designed (rounded square outlines, not browser default checkboxes)
- Subtle background texture or a single decorative accent (a corner flourish, a thin colored bar) -- restrained, not busy""",
    "icon_pack": """
Visual style: define ONE consistent style system before drawing anything -- pick either flat-fill or consistent-stroke-width outline (not both), pick a fixed corner radius, and a locked palette of 4-5 colors used consistently across every icon (not a random color per icon). Typography is not relevant here except for a small label/name under each icon if used as a preview sheet.

Specific elements to include:
- 8-12 icons covering the idea's theme, each drawn on the same canvas size/grid (e.g. 64x64) with consistent padding so they align as a set
- A visible grid or light guide showing consistent optical sizing across icons (some justify more visual weight, but bounding proportions should feel uniform)
- One "preview sheet" layout showing all icons together in a grid with even spacing, so the set reads as a cohesive product, not loose files

Keep strokes/fills as vector paths, not raster images, so the set stays crisp at any size.""",
    "template": """
Visual style: modern, uncluttered layout with generous whitespace, one primary accent color against a neutral (white/near-white or dark-mode) background, and a clear visual hierarchy (one dominant headline size, one supporting size, one body size -- no more than 3 type scales). Typography: a system-font stack or a widely-available web font pairing (one for headings, one for body) so it renders consistently without custom font loading.

Specific elements to include:
- A header/hero zone with a clear headline, one-line subheading, and a single obvious call-to-action button
- A structured content section broken into 2-3 visually distinct blocks (cards, alternating image/text rows, or a feature grid) rather than one long unstyled paragraph
- Consistent spacing rhythm (e.g. 8px/16px/32px multiples) and a footer or closing section so the page feels complete, not cut off""",
    "guide": """
Visual style: editorial/publication feel -- a serif or high-contrast display font for the title and section headers, a highly readable body sans/serif, and a restrained 2-color palette (one ink color, one accent used sparingly for section markers or pull quotes). Layout: single-column reading layout with generous line-height and margins, structured like a real published guide, not a wall of text.

Specific elements to include:
- A title page/section with the guide's title, a one-line subtitle, and a simple cover graphic or geometric accent (not a stock photo)
- Numbered or clearly labeled sections with consistent header styling, short paragraphs, and at least one visually distinct callout/tip box per major section
- A simple step-by-step or checklist component for any actionable content, styled consistently with the rest of the page""",
    "social": """
Visual style: bold, high-contrast, optimized to be legible at thumbnail size -- one strong background color or gradient, large type for the main message, minimal supporting text. Typography: one heavy display font for the headline (large enough to read on a phone screen at a glance), a much smaller secondary font for a handle/footer line only.

Specific elements to include:
- A square (1:1) composition with the core message centered or rule-of-thirds placed, sized to stay legible when scaled down to a feed thumbnail
- One accent shape or graphic element (a geometric shape, underline, or icon) that reinforces the message without cluttering it
- A small consistent footer/branding line in a corner (not competing with the main message)""",
    "generic": """
Visual style: infer a style direction from the product's theme and target use (professional vs. playful, digital-first vs. print) and commit to one consistent color palette (2-3 colors) and a clear type pairing (one display font, one body font) rather than defaulting to generic corporate blue-and-gray.

Specific elements to include:
- A clear primary focal element that communicates what the product is at a glance
- At least one structured content zone (not just a title and a paragraph) that shows how the product would actually be used
- Consistent spacing and alignment throughout so the piece reads as a finished product, not a draft""",
}

_AUDIENCE_HINTS = {
    "planner": "people trying to organize a specific area of their life or work who want something more considered than a free template",
    "icon_pack": "designers, indie developers, and no-code builders who need a consistent, ready-to-use visual set instead of hand-drawing icons themselves",
    "template": "small business owners, freelancers, or solo creators who need something professional-looking fast without hiring a designer",
    "guide": "people actively trying to learn or solve the specific problem named in the title, willing to pay for a condensed, well-organized answer",
    "social": "creators and small brands who post regularly and want a consistent, on-brand visual system instead of designing each post from scratch",
    "generic": "buyers searching for a ready-made digital product related to this topic who want something polished, not a rough draft",
}

# What the product concretely IS, per bucket -- filled in with keyword-derived
# components pulled from the idea title where possible, so the brief commits
# to a buildable thing instead of restating the research title back vaguely.
_BUCKET_PRODUCT_TEMPLATES = {
    "planner": "a downloadable, fillable planner: a single printable page with labeled fill-in fields covering {components}",
    "icon_pack": "a set of 8-12 downloadable icon files (SVG/PNG) in one consistent visual style, sold as a themed icon pack",
    "template": "a ready-to-use template file the buyer customizes with their own content or branding, covering {components}",
    "guide": "a downloadable PDF guide: a short, structured written resource walking through {components} step by step",
    "social": "a set of ready-to-post social media graphic templates, sized for common platforms, covering {components}",
    "generic": "a downloadable digital product the buyer uses directly, built around {components}",
}

# Keyword -> named component, used to make _product_definition concrete
# instead of generic. Checked in order so the most specific match wins.
_COMPONENT_KEYWORDS = [
    ("budget", "a budget-tracking section"),
    ("gift", "a gift-idea checklist"),
    ("itinerary", "a time-blocked itinerary"),
    ("schedule", "a scheduled itinerary broken into time blocks"),
    ("goal", "a goal-setting section"),
    ("habit", "a habit-tracking grid"),
    ("meal", "a meal-planning grid"),
    ("workout", "a workout/exercise log"),
    ("checklist", "a checklist of key action items"),
    ("journal", "a guided reflection/journal section"),
    ("invite", "an event-details fill-in block (date, time, location, RSVP)"),
    ("invitation", "an event-details fill-in block (date, time, location, RSVP)"),
]


def _product_components(title: str) -> str:
    text = title.lower()
    hits = [label for kw, label in _COMPONENT_KEYWORDS if kw in text]
    if not hits:
        return "the core sections implied by the title"
    # de-dupe while preserving order (itinerary/schedule can both hit)
    seen = []
    for h in hits:
        if h not in seen:
            seen.append(h)
    return ", ".join(seen)


def _product_definition(idea: Idea) -> str:
    bucket = _bucket(idea.title)
    template = _BUCKET_PRODUCT_TEMPLATES[bucket]
    if "{components}" in template:
        return template.format(components=_product_components(idea.title))
    return template


# Output-format classification: what shape the finished file should take.
# "print" is the default per bucket unless the title clearly signals a
# website/landing-page product -- most digital-download products (planners,
# trackers, checklists, guides) are printed or exported to PDF, not browsed.
_WEB_SIGNAL_WORDS = ("website", "landing page", "webpage", "web app", "site template")
_VISUAL_BUCKETS = {"icon_pack", "social"}

_FORMAT_INSTRUCTIONS = {
    "print": (
        "Generate as a print-ready HTML page sized for standard Letter/A4 "
        "(8.5x11in / 210x297mm), using `@media print` CSS rules (`@page` size, "
        "print-safe margins, no hover-only or scroll-dependent content), and no "
        "browser-only UI elements (no nav bars, no sticky headers, no interactive "
        "widgets that don't render on paper). This must be designed to be printed "
        "directly or exported to PDF via the browser's print-to-PDF -- NOT a "
        "scrolling website layout."
    ),
    "web": (
        "Generate this as a single self-contained HTML artifact (inline CSS, no "
        "external stylesheets, fonts, or scripts) that renders correctly at both "
        "desktop width and a mobile viewport -- a responsive, scrollable webpage, "
        "since the product itself is a website/landing-page template."
    ),
    "visual": None,  # filled in per-bucket below with exact pixel dimensions
}

_VISUAL_FORMAT_INSTRUCTIONS = {
    "icon_pack": (
        "Generate as a fixed-canvas HTML/SVG artifact, not a flowing page: a "
        "1200x1200px preview sheet showing the full icon set arranged in an even "
        "grid, plus each icon as an individual inline SVG on its own 128x128px "
        "canvas so it can be exported separately."
    ),
    "social": (
        "Generate as a fixed-canvas HTML artifact at exactly 1080x1080px (a fixed-size "
        "container, not fluid width) so it can be screenshotted or exported directly "
        "as a square social image -- not a flowing/scrolling page."
    ),
}


def _output_format_kind(idea: Idea, bucket: str) -> str:
    text = idea.title.lower()
    if any(sig in text for sig in _WEB_SIGNAL_WORDS):
        return "web"
    if bucket in _VISUAL_BUCKETS:
        return "visual"
    return "print"


def _format_instruction(idea: Idea, bucket: str) -> str:
    kind = _output_format_kind(idea, bucket)
    if kind == "visual":
        return _VISUAL_FORMAT_INSTRUCTIONS[bucket]
    return _FORMAT_INSTRUCTIONS[kind]


# Default copy tone inferred from title keywords, falling back to a
# sensible per-bucket default rather than leaving tone unset.
_TONE_KEYWORDS = [
    ("warm & romantic", ("girlfriend", "boyfriend", "romantic", "anniversary", "wedding", "valentine", "love", "couple", "date night")),
    ("playful", ("fun", "party", "meme", "game", "celebration", "tiktok", "instagram")),
    ("clean & minimal", ("business", "professional", "invoice", "resume", "freelance", "brand", "startup", "client")),
]

_BUCKET_DEFAULT_TONE = {
    "planner": "warm & organized",
    "icon_pack": "clean & minimal",
    "template": "clean & minimal",
    "guide": "clear & authoritative",
    "social": "playful",
    "generic": "clean & minimal",
}


def _copy_tone(idea: Idea, bucket: str) -> str:
    text = idea.title.lower()
    for tone, keywords in _TONE_KEYWORDS:
        if any(k in text for k in keywords):
            return tone
    return _BUCKET_DEFAULT_TONE[bucket]


def build_design_prompt(idea: Idea) -> str:
    """
    Returns a detailed, copy-pasteable design brief for the given idea,
    meant to be pasted directly into a Claude chat to generate the finished
    product in one shot -- no clarifying questions needed on product
    definition, output format, or tone, since all three are decided here.
    """
    bucket = _bucket(idea.title)
    audience = _AUDIENCE_HINTS[bucket]
    brief = _BUCKET_BRIEFS[bucket].strip()
    product_definition = _product_definition(idea)
    format_instruction = _format_instruction(idea, bucket)
    tone = _copy_tone(idea, bucket)

    return (
        f"Design a finished, sellable digital product: \"{idea.title}\".\n\n"
        f"What it is: {product_definition} (surfaced via {idea.source}: {idea.reason}).\n\n"
        f"Deliverable: build the product itself, ready for the buyer to use directly -- "
        f"not a page marketing it and not a mockup/wireframe.\n\n"
        f"Target audience / use case: {audience}.\n\n"
        f"Copy tone: {tone}.\n\n"
        f"{brief}\n\n"
        f"Format: {format_instruction} Make it look like a finished product someone would pay for, "
        "not a wireframe or a rough draft -- commit fully to the color palette, typography, "
        "and layout choices above rather than leaving them generic."
    )


def demo() -> None:
    samples = [
        Idea(title="7-day social media content planner", category="unclassified", source="gumroad_discover", reason="currently listed on Gumroad discover page"),
        Idea(title="Minimal line-art icon pack for productivity apps", category="unclassified", source="etsy_search", reason="currently listed in Etsy digital-download search results"),
        Idea(title="Notion-style newsletter template for solo creators", category="unclassified", source="producthunt_rss", reason="newly launched product on Product Hunt"),
        Idea(title="Beginner's guide to freelance pricing", category="unclassified", source="reddit_rss:r/Entrepreneur", reason="top post this week (via old.reddit.com RSS)"),
    ]
    for idea in samples:
        prompt = build_design_prompt(idea)
        assert idea.title in prompt
        assert "Format:" in prompt or "artifact" in prompt.lower()
        assert len(prompt) > 400, "design prompt too short to be genuinely detailed"
    print(f"demo: built {len(samples)} design prompts, all passed basic content checks")


if __name__ == "__main__":
    demo()
