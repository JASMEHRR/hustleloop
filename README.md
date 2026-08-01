# HustleLoop

A scheduled pipeline that researches trending digital-product ideas, optionally analyzes a YouTube video you feed it, generates a sellable output file, and (optionally) publishes it to Gumroad — all on free tools and GitHub Actions' free tier.

**What this is not:** a fully autonomous business. It automates research and file generation. Selling still requires you to have a Gumroad account; for the first few runs, review the output before it auto-publishes.

## How it works (the loop)

```
research/          -> finds what's trending right now (no fixed category list)
youtube_analysis/  -> (optional) you give it a YouTube URL, it summarizes what makes the video's content work
generate/           -> turns the chosen idea into an actual file (SVG, HTML, etc.) — pluggable, add new formats anytime
publish/            -> saves output to output/, pushes to Gumroad if GUMROAD_API_KEY secret is set
```

Runs automatically once a day via GitHub Actions (`.github/workflows/daily_run.yml`), or manually:

```bash
pip install -r requirements.txt
python main.py                          # full loop, no video input
python main.py --youtube <url>          # include a YouTube video as inspiration
```

## Setup (one-time, ~10 minutes)

1. Fork/clone this repo.
2. `pip install -r requirements.txt`
3. (Optional, for auto-publish) Create a free Gumroad account, get an API key, add it as a GitHub repo secret named `GUMROAD_API_KEY` (Settings -> Secrets and variables -> Actions -> New repository secret). Without this secret, the loop still runs and saves files to `output/` — it just won't auto-publish.
4. (Optional) Reddit API keys are free at reddit.com/prefs/apps — add as `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` secrets to widen research sources. Works without them using public JSON endpoints, just more rate-limited.
5. Enable GitHub Actions on the repo (Actions tab -> enable). It will then run daily on its own.

## Why it won't silently break

- Every run writes a timestamped entry to `logs/run_log.jsonl` — what it researched, what it picked, what it generated, and any errors, in plain text you can read.
- Every step is wrapped so a failure in one step (e.g. YouTube analysis) doesn't crash the whole run — it logs the failure and continues with what it has.
- Nothing is marked "published" unless the publish step actually got a success response back — no silent fake-success.

## Honest limits

- "Watching" a YouTube video means: pulling the transcript + sampling video frames + summarizing both. It is not literal human-level video comprehension.
- Research uses free public sources (Reddit, Google Trends via pytrends, Gumroad discover pages). It is a signal, not certainty — always sanity-check an idea before spending real time on it.
- Nothing here spends money automatically. No paid API keys are used anywhere in this codebase.
