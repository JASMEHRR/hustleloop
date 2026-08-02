# HustleLoop

A scheduled pipeline that researches trending digital-product ideas and turns them into a daily report of 10 ideas, each paired with a detailed, ready-to-paste design prompt — all on free tools and GitHub Actions' free tier.

**What this is:** a research-and-prompt assistant, not a fully automated design tool. Code alone can't produce good visual design, so HustleLoop doesn't try — it does the research and writes the brief, and you generate the actual design yourself using Claude.

## How it works (the loop)

```
research/  -> finds what's trending right now, across multiple free sources, no fixed category list
generate/  -> turns each idea into a detailed design prompt (generate/design_prompts.py)
main.py    -> writes output/YYYY-MM-DD_ideas.md: 10 distinct ideas + their design prompts
```

Then, manually:

1. Open `output/<date>_ideas.md`.
2. Pick an idea, copy its design prompt.
3. Paste it into a Claude chat and ask Claude to generate the design as an HTML artifact.
4. Review the artifact, tweak it if needed, and upload/export it yourself (e.g. as a Gumroad listing).

Runs automatically once a day via GitHub Actions (`.github/workflows/daily_run.yml`), or manually:

```bash
pip install -r requirements.txt
python main.py                          # default: writes today's ideas + design-prompts report
python main.py --youtube <url>          # include a YouTube video as inspiration
python main.py --also-generate-files    # also run the old rough auto-generated-file path (SVG/PDF/PNG)
```

## Secondary path: auto-generated files

The original file generators (`generate/generators.py` — icon packs, PDF guides, planners, HTML templates, social cards) still exist behind `--also-generate-files`. These are rougher, code-only outputs (no design taste applied) — useful if you want *something* auto-produced without the manual Claude step, but the daily ideas report is the primary, higher-quality path. Add `--publish` alongside `--also-generate-files` to push any generated files to Gumroad if `GUMROAD_API_KEY` is configured; `--publish` alone does nothing since there's nothing to publish in the default report-only flow.

## Setup (one-time, ~10 minutes)

1. Fork/clone this repo.
2. `pip install -r requirements.txt`
3. (Optional, only relevant with `--also-generate-files --publish`) Create a free Gumroad account, get an API key, add it as a GitHub repo secret named `GUMROAD_API_KEY` (Settings -> Secrets and variables -> Actions -> New repository secret).
4. (Optional) Reddit API keys are free at reddit.com/prefs/apps — add as `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` secrets to widen research sources further. Research also works without them via public JSON/RSS endpoints.
5. Enable GitHub Actions on the repo (Actions tab -> enable). It will then run daily and commit `output/<date>_ideas.md` back to the repo for you to read.

## Why it won't silently break

- Every run writes a timestamped entry to `logs/run_log.jsonl` — what it researched, what it picked, what it wrote, and any errors, in plain text you can read.
- Every step is wrapped so a failure in one step (e.g. one research source, YouTube analysis) doesn't crash the whole run — it logs the failure and continues with what it has.
- Nothing is marked "published" unless the publish step actually got a success response back — no silent fake-success.
- The daily commit step only commits/pushes when something actually changed — a day where every research source fails still runs cleanly, it just produces fewer ideas.

## Honest limits

- Research uses free public sources (Reddit's JSON API and old.reddit.com RSS feeds, Google Trends via pytrends, Gumroad discover, Etsy search results, Product Hunt's RSS feed). Any individual source can get rate-limited or change its markup on a given day — that's expected and handled, not a bug. It's a signal, not certainty — always sanity-check an idea before spending real time on it.
- The design prompts are detailed briefs, not the design itself — quality of the final output still depends on you reviewing what Claude generates from the prompt, not blindly uploading it.
- "Watching" a YouTube video means: pulling the transcript + sampling video frames + summarizing both. It is not literal human-level video comprehension.
- Nothing here spends money automatically. No paid API keys are used anywhere in this codebase.
