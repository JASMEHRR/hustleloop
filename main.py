"""
Core loop: research -> (optional) YouTube analysis -> rank/dedupe ideas ->
write a daily ideas+design-prompts report -> (optional) also generate rough
files the old way -> (optional) publish those files -> log.

Every step is wrapped so a failure in one doesn't kill the run -- it's
recorded in the log and the loop continues with whatever it has. Nothing
is ever marked successful unless it actually succeeded (no silent
fake-success anywhere in this file).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))

from research.trend_scan import run_research
from youtube_analysis.watch import analyze_youtube_video, summarize
from generate.design_prompts import build_design_prompt
from generate.generators import generate, pick_format
from publish.gumroad import is_configured, publish_product

REPO_ROOT = os.path.dirname(__file__)
OUTPUT_DIR = os.path.join(REPO_ROOT, "output")
LOG_PATH = os.path.join(REPO_ROOT, "logs", "run_log.jsonl")


def log_run(entry: dict) -> None:
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    entry["timestamp"] = datetime.now(timezone.utc).isoformat()
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")


def _normalize_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def dedupe_ideas(ideas: list, top_n: int) -> list:
    """Drops near-duplicate titles (same normalized text), keeps rank order."""
    seen: set[str] = set()
    distinct = []
    for idea in ideas:
        key = _normalize_title(idea.title)
        if not key or key in seen:
            continue
        seen.add(key)
        distinct.append(idea)
        if len(distinct) >= top_n:
            break
    return distinct


def write_ideas_report(ideas: list, path: str) -> None:
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lines = [
        f"# HustleLoop daily ideas -- {date_str}",
        "",
        "10 researched product ideas with ready-to-paste design prompts. "
        "Paste a prompt into a Claude chat to generate the visual design as "
        "an artifact, review it, then upload the design yourself.",
        "",
    ]
    for i, idea in enumerate(ideas, start=1):
        lines.append(f"## {i}. {idea.title}")
        lines.append("")
        lines.append(f"**Why it surfaced:** {idea.source} -- {idea.reason}")
        lines.append("")
        lines.append("**Design prompt (paste into a Claude chat):**")
        lines.append("")
        lines.append("```")
        lines.append(build_design_prompt(idea))
        lines.append("```")
        lines.append("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the HustleLoop research/generate/publish loop.")
    parser.add_argument("--youtube", help="Optional YouTube URL to analyze as inspiration", default=None)
    parser.add_argument("--publish", action="store_true", help="Attempt to publish generated files to Gumroad (only with --also-generate-files)")
    parser.add_argument("--top-n", type=int, default=10, help="How many distinct ideas to include in the daily report")
    parser.add_argument("--also-generate-files", action="store_true", help="Also run the old rough file-generator path (SVG/PDF/PNG) as a secondary output")
    args = parser.parse_args()

    run_log: dict = {"steps": []}

    # 1. Research
    source_events: list[dict] = []
    ideas = run_research(source_events)
    run_log["steps"].append({"step": "research", "sources": source_events, "idea_count": len(ideas)})

    if not ideas:
        run_log["steps"].append({"step": "research", "warning": "no ideas found this run"})
        log_run(run_log)
        print("No ideas found this run. See logs/run_log.jsonl.")
        return 0

    # 2. Optional YouTube analysis -- feeds into context only, doesn't block the loop
    if args.youtube:
        try:
            analysis = analyze_youtube_video(args.youtube)
            youtube_summary = summarize(analysis)
            run_log["steps"].append({"step": "youtube_analysis", "status": "ok", "summary": youtube_summary})
        except Exception as e:  # noqa: BLE001
            run_log["steps"].append({"step": "youtube_analysis", "status": "error", "error": str(e)})

    # 3. Dedupe to top-N distinct ideas and write the daily report -- this is
    # the primary output now.
    distinct_ideas = dedupe_ideas(ideas, args.top_n)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    report_path = os.path.join(OUTPUT_DIR, f"{date_str}_ideas.md")
    write_ideas_report(distinct_ideas, report_path)
    run_log["steps"].append({
        "step": "ideas_report",
        "status": "ok",
        "path": report_path,
        "idea_count": len(distinct_ideas),
        "titles": [i.title for i in distinct_ideas],
    })

    # 4. Optional: old rough file-generator path, kept as a secondary output.
    generated_results = []
    if args.also_generate_files:
        IDEA_SCAN_CAP = 20
        skipped_titles: list[str] = []
        matched: list[tuple] = []
        for idea in ideas[:IDEA_SCAN_CAP]:
            fmt = pick_format(idea.title)
            if fmt == "generic":
                skipped_titles.append(idea.title)
                continue
            matched.append((idea, fmt))
            if len(matched) >= args.top_n:
                break

        if skipped_titles:
            run_log["steps"].append({
                "step": "idea_selection",
                "skipped": skipped_titles,
                "reason": "no matching finished-output format",
            })

        if not matched:
            run_log["steps"].append({
                "step": "generate",
                "status": "skipped_no_fit",
                "reason": f"none of the top {min(IDEA_SCAN_CAP, len(ideas))} ranked ideas matched a finished-output format",
            })
        else:
            for idea, fmt in matched:
                try:
                    result = generate(idea.title, OUTPUT_DIR, fmt)
                    result["source"] = idea.source
                    result["reason"] = idea.reason
                    generated_results.append(result)
                    run_log["steps"].append({"step": "generate", "status": "ok", **result})
                except Exception as e:  # noqa: BLE001
                    run_log["steps"].append({"step": "generate", "status": "error", "idea": idea.title, "error": str(e)})

    # 5. Optional publish -- only meaningful when --also-generate-files produced files.
    if args.publish:
        if not generated_results:
            run_log["steps"].append({"step": "publish", "status": "skipped", "reason": "no generated files this run (use --also-generate-files)"})
        elif not is_configured():
            run_log["steps"].append({"step": "publish", "status": "skipped", "reason": "GUMROAD_API_KEY not set"})
        else:
            for result in generated_results:
                for file_path in result["files"]:
                    pub = publish_product(
                        name=result["idea"],
                        price_cents=299,
                        file_path=file_path,
                        description=f"Generated from trend research. Source: {result['source']}. {result['reason']}",
                    )
                    run_log["steps"].append({"step": "publish", "file": file_path, **pub})

    log_run(run_log)
    print(json.dumps(run_log, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
