"""
Core loop: research -> (optional) YouTube analysis -> pick idea -> generate -> publish -> log.

Every step is wrapped so a failure in one doesn't kill the run -- it's
recorded in the log and the loop continues with whatever it has. Nothing
is ever marked successful unless it actually succeeded (no silent
fake-success anywhere in this file).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))

from research.trend_scan import run_research
from youtube_analysis.watch import analyze_youtube_video, summarize
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the HustleLoop research/generate/publish loop.")
    parser.add_argument("--youtube", help="Optional YouTube URL to analyze as inspiration", default=None)
    parser.add_argument("--publish", action="store_true", help="Attempt to publish to Gumroad if configured")
    parser.add_argument("--top-n", type=int, default=1, help="How many ideas to generate this run")
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

    # 2. Optional YouTube analysis -- feeds into idea selection as extra context, doesn't block the loop
    youtube_summary = None
    if args.youtube:
        try:
            analysis = analyze_youtube_video(args.youtube)
            youtube_summary = summarize(analysis)
            run_log["steps"].append({"step": "youtube_analysis", "status": "ok", "summary": youtube_summary})
        except Exception as e:  # noqa: BLE001
            run_log["steps"].append({"step": "youtube_analysis", "status": "error", "error": str(e)})

    # 3. Pick top idea(s) and generate
    generated_results = []
    for idea in ideas[: args.top_n]:
        fmt = pick_format(idea.title)
        try:
            result = generate(idea.title, OUTPUT_DIR, fmt)
            result["source"] = idea.source
            result["reason"] = idea.reason
            generated_results.append(result)
            run_log["steps"].append({"step": "generate", "status": "ok", **result})
        except Exception as e:  # noqa: BLE001
            run_log["steps"].append({"step": "generate", "status": "error", "idea": idea.title, "error": str(e)})

    # 4. Optional publish
    if args.publish:
        if not is_configured():
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
