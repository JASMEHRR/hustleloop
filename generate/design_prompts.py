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
    if any(k in text for k in ("planner", "checklist", "tracker", "printable", "calendar", "journal")):
        return "planner"
    if any(k in text for k in ("icon", "logo", "emoji", "sticker", "clipart", "graphic pack")):
        return "icon_pack"
    if any(k in text for k in ("newsletter", "website", "landing page", "template", "capcut")):
        return "template"
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
- Subtle background texture or a single decorative accent (a corner flourish, a thin colored bar) -- restrained, not busy

Format: single HTML page/artifact sized for A4 or US Letter (set explicit width/height in mm or in via CSS @page or a fixed-aspect container), print-ready with print-safe margins and no interactive-only elements (no hover states that hide content). Design for both light background printing and an on-screen preview that looks finished, not like a wireframe.""",
    "icon_pack": """
Visual style: define ONE consistent style system before drawing anything -- pick either flat-fill or consistent-stroke-width outline (not both), pick a fixed corner radius, and a locked palette of 4-5 colors used consistently across every icon (not a random color per icon). Typography is not relevant here except for a small label/name under each icon if used as a preview sheet.

Specific elements to include:
- 8-12 icons covering the idea's theme, each drawn on the same canvas size/grid (e.g. 64x64) with consistent padding so they align as a set
- A visible grid or light guide showing consistent optical sizing across icons (some justify more visual weight, but bounding proportions should feel uniform)
- One "preview sheet" layout showing all icons together in a grid with even spacing, so the set reads as a cohesive product, not loose files

Format: generate as an HTML/SVG artifact showing the full icon set on one preview sheet (this is the sales-listing thumbnail), plus describe each icon as an individual inline SVG so it can be exported separately. Keep strokes/fills as vector paths, not raster images, so the set stays crisp at any size.""",
    "template": """
Visual style: modern, uncluttered layout with generous whitespace, one primary accent color against a neutral (white/near-white or dark-mode) background, and a clear visual hierarchy (one dominant headline size, one supporting size, one body size -- no more than 3 type scales). Typography: a system-font stack or a widely-available web font pairing (one for headings, one for body) so it renders consistently without custom font loading.

Specific elements to include:
- A header/hero zone with a clear headline, one-line subheading, and a single obvious call-to-action button
- A structured content section broken into 2-3 visually distinct blocks (cards, alternating image/text rows, or a feature grid) rather than one long unstyled paragraph
- Consistent spacing rhythm (e.g. 8px/16px/32px multiples) and a footer or closing section so the page feels complete, not cut off

Format: as a single self-contained HTML artifact (inline CSS, no external dependencies) that renders correctly at both desktop width and a mobile viewport -- make it responsive with a simple breakpoint, not fixed-width only.""",
    "guide": """
Visual style: editorial/publication feel -- a serif or high-contrast display font for the title and section headers, a highly readable body sans/serif, and a restrained 2-color palette (one ink color, one accent used sparingly for section markers or pull quotes). Layout: single-column reading layout with generous line-height and margins, structured like a real published guide, not a wall of text.

Specific elements to include:
- A title page/section with the guide's title, a one-line subtitle, and a simple cover graphic or geometric accent (not a stock photo)
- Numbered or clearly labeled sections with consistent header styling, short paragraphs, and at least one visually distinct callout/tip box per major section
- A simple step-by-step or checklist component for any actionable content, styled consistently with the rest of the page

Format: as an HTML artifact laid out for print/PDF export at A4/Letter proportions (defined page width, printable margins, page-break-friendly section spacing), readable equally well on-screen or exported to PDF.""",
    "social": """
Visual style: bold, high-contrast, optimized to be legible at thumbnail size -- one strong background color or gradient, large type for the main message, minimal supporting text. Typography: one heavy display font for the headline (large enough to read on a phone screen at a glance), a much smaller secondary font for a handle/footer line only.

Specific elements to include:
- A square (1:1) composition with the core message centered or rule-of-thirds placed, sized to stay legible when scaled down to a feed thumbnail
- One accent shape or graphic element (a geometric shape, underline, or icon) that reinforces the message without cluttering it
- A small consistent footer/branding line in a corner (not competing with the main message)

Format: as an HTML artifact rendered at a fixed 1080x1080px canvas (use a fixed-size container, not fluid width), so it can be screenshotted/exported directly as a square social image.""",
    "generic": """
Visual style: infer a style direction from the product's theme and target use (professional vs. playful, digital-first vs. print) and commit to one consistent color palette (2-3 colors) and a clear type pairing (one display font, one body font) rather than defaulting to generic corporate blue-and-gray.

Specific elements to include:
- A clear primary focal element that communicates what the product is at a glance
- At least one structured content zone (not just a title and a paragraph) that shows how the product would actually be used
- Consistent spacing and alignment throughout so the piece reads as a finished product, not a draft

Format: as a single self-contained HTML artifact, sized appropriately for how the product would actually be consumed (print page proportions for anything printable, square/social proportions for anything shareable, standard webpage proportions otherwise).""",
}

_AUDIENCE_HINTS = {
    "planner": "people trying to organize a specific area of their life or work who want something more considered than a free template",
    "icon_pack": "designers, indie developers, and no-code builders who need a consistent, ready-to-use visual set instead of hand-drawing icons themselves",
    "template": "small business owners, freelancers, or solo creators who need something professional-looking fast without hiring a designer",
    "guide": "people actively trying to learn or solve the specific problem named in the title, willing to pay for a condensed, well-organized answer",
    "social": "creators and small brands who post regularly and want a consistent, on-brand visual system instead of designing each post from scratch",
    "generic": "buyers searching for a ready-made digital product related to this topic who want something polished, not a rough draft",
}


def build_design_prompt(idea: Idea) -> str:
    """
    Returns a detailed, copy-pasteable design brief for the given idea,
    meant to be pasted directly into a Claude chat to generate the visual
    design as an HTML artifact.
    """
    bucket = _bucket(idea.title)
    audience = _AUDIENCE_HINTS[bucket]
    brief = _BUCKET_BRIEFS[bucket].strip()

    return (
        f"Design a finished, sellable digital product: \"{idea.title}\".\n\n"
        f"What it is: a {bucket.replace('_', ' ')}-style digital product based on current market signal "
        f"(surfaced via {idea.source}: {idea.reason}).\n\n"
        f"Target audience / use case: {audience}.\n\n"
        f"{brief}\n\n"
        "Generate this as an HTML artifact I can review directly, with all styling inline "
        "(no external stylesheets, fonts, or scripts) so it renders standalone. Make it look like "
        "a finished product someone would pay for, not a wireframe or a rough draft -- commit fully "
        "to the color palette, typography, and layout choices above rather than leaving them generic."
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
