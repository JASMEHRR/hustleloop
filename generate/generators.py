"""
Pluggable output generation.

Each generator is a function that takes an Idea and produces one or more
files on disk. New formats get added by writing a function and registering
it in GENERATORS -- the core loop never needs to change. This deliberately
avoids hardcoding "icons, logos, newsletters, templates" as the only
possible outputs; those were just examples, not the whole scope.
"""

from __future__ import annotations

import os
import random
import textwrap
from datetime import datetime, timezone

from jinja2 import Template


def _slug(text: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in text.lower())[:50].strip("_")


def _out_path(idea_title: str, filename: str, output_root: str) -> str:
    folder = os.path.join(output_root, _slug(idea_title))
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, filename)


def generate_icon_pack(idea_title: str, output_root: str) -> list[str]:
    """Simple geometric SVG icon set -- no paid design tools needed."""
    shapes = ["circle", "rect", "polygon"]
    colors = ["#2563eb", "#16a34a", "#dc2626", "#f59e0b", "#7c3aed"]
    paths = []
    for i in range(6):
        shape = shapes[i % len(shapes)]
        color = colors[i % len(colors)]
        if shape == "circle":
            body = f'<circle cx="32" cy="32" r="24" fill="{color}"/>'
        elif shape == "rect":
            body = f'<rect x="10" y="10" width="44" height="44" rx="8" fill="{color}"/>'
        else:
            body = f'<polygon points="32,8 56,56 8,56" fill="{color}"/>'
        svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">{body}</svg>'
        path = _out_path(idea_title, f"icon_{i+1}.svg", output_root)
        with open(path, "w") as f:
            f.write(svg)
        paths.append(path)
    return paths


NEWSLETTER_TEMPLATE = Template("""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>{{ title }}</title></head>
<body style="font-family: -apple-system, Arial, sans-serif; max-width: 600px; margin: 0 auto; background:#f4f4f5;">
  <div style="background:#ffffff; padding:32px; border-radius:8px; margin-top:24px;">
    <h1 style="color:#111827; font-size:22px;">{{ title }}</h1>
    <p style="color:#4b5563; line-height:1.6;">{{ intro }}</p>
    <div style="border-left:3px solid #2563eb; padding-left:16px; margin:24px 0;">
      <p style="color:#111827; font-weight:600;">This week's highlight</p>
      <p style="color:#4b5563;">{{ highlight }}</p>
    </div>
    <a href="#" style="display:inline-block; background:#2563eb; color:#fff; padding:10px 20px; border-radius:6px; text-decoration:none;">Read more</a>
  </div>
</body>
</html>""")


def generate_newsletter_template(idea_title: str, output_root: str) -> list[str]:
    html = NEWSLETTER_TEMPLATE.render(
        title=idea_title,
        intro=f"A ready-to-customize newsletter layout inspired by: {idea_title}.",
        highlight="Replace this block with your own content -- structure and styling are done for you.",
    )
    path = _out_path(idea_title, "newsletter_template.html", output_root)
    with open(path, "w") as f:
        f.write(html)
    return [path]


WEBSITE_TEMPLATE = Template("""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>{{ title }}</title>
  <style>
    body { font-family: -apple-system, Arial, sans-serif; margin:0; color:#111827; }
    header { background:#111827; color:#fff; padding:64px 24px; text-align:center; }
    header h1 { font-size:36px; margin:0 0 12px; }
    section { padding:48px 24px; max-width:800px; margin:0 auto; }
    .cta { display:inline-block; background:#2563eb; color:#fff; padding:14px 28px; border-radius:6px; text-decoration:none; margin-top:16px; }
  </style>
</head>
<body>
  <header>
    <h1>{{ title }}</h1>
    <p>{{ subtitle }}</p>
    <a class="cta" href="#">Get Started</a>
  </header>
  <section>
    <h2>About</h2>
    <p>{{ body_text }}</p>
  </section>
</body>
</html>""")


def generate_website_template(idea_title: str, output_root: str) -> list[str]:
    html = WEBSITE_TEMPLATE.render(
        title=idea_title,
        subtitle="A clean single-page landing template, ready to customize.",
        body_text=f"This template was scaffolded based on current interest around: {idea_title}.",
    )
    path = _out_path(idea_title, "website_template.html", output_root)
    with open(path, "w") as f:
        f.write(html)
    return [path]


def generate_generic_text_pack(idea_title: str, output_root: str) -> list[str]:
    """
    Fallback for any idea that doesn't cleanly match a known format --
    produces a structured outline/starter doc rather than silently
    skipping ideas that fall outside icons/newsletters/websites.
    """
    content = textwrap.dedent(f"""\
        # {idea_title}

        Generated: {datetime.now(timezone.utc).isoformat()}

        ## Why this idea surfaced
        This was picked up as a trending signal by the research step.
        Category didn't map to a specific generator format, so this is a
        starter outline you can develop further -- not a finished product.

        ## Suggested next steps
        - Validate demand (search volume, existing competitors, pricing)
        - Decide on a concrete deliverable format
        - Build a minimal first version and test with a small audience
    """)
    path = _out_path(idea_title, "idea_outline.md", output_root)
    with open(path, "w") as f:
        f.write(content)
    return [path]


# Registry: add new formats here without touching the core loop.
GENERATORS = {
    "icon_pack": generate_icon_pack,
    "newsletter_template": generate_newsletter_template,
    "website_template": generate_website_template,
    "generic": generate_generic_text_pack,
}


def pick_format(idea_title: str) -> str:
    """
    Very lightweight keyword match to route an idea to a format.
    Falls back to 'generic' rather than forcing a bad fit -- this keeps
    the system honest about not being limited to 3-4 fixed categories.
    """
    text = idea_title.lower()
    if any(k in text for k in ("icon", "logo", "emoji", "sticker")):
        return "icon_pack"
    if any(k in text for k in ("newsletter", "email template")):
        return "newsletter_template"
    if any(k in text for k in ("website", "landing page", "site template")):
        return "website_template"
    return "generic"


def generate(idea_title: str, output_root: str, fmt: str | None = None) -> dict:
    fmt = fmt or pick_format(idea_title)
    generator_fn = GENERATORS.get(fmt, generate_generic_text_pack)
    files = generator_fn(idea_title, output_root)
    return {"idea": idea_title, "format": fmt, "files": files}
