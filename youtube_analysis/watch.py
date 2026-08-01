"""
YouTube "watching" module.

Honest framing (see README "Honest limits"): true human-level video
comprehension isn't something a free/local pipeline can do. What this
module actually does is the closest free approximation:

  1. Pull the transcript (what's said).
  2. Download the video and sample frames at intervals (what's shown).
  3. Produce a structured summary combining both.

If a vision model isn't configured, frame sampling is still saved to disk
so a human (or a later step) can review them -- it never silently drops
the visual half of the analysis.
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
from dataclasses import dataclass, field


@dataclass
class VideoAnalysis:
    url: str
    video_id: str
    transcript_text: str = ""
    transcript_available: bool = False
    frame_paths: list[str] = field(default_factory=list)
    frame_count: int = 0
    errors: list[str] = field(default_factory=list)


def _extract_video_id(url: str) -> str:
    match = re.search(r"(?:v=|youtu\.be/|shorts/)([A-Za-z0-9_-]{11})", url)
    if not match:
        raise ValueError(f"Could not extract a YouTube video ID from: {url}")
    return match.group(1)


def _fetch_transcript(video_id: str) -> tuple[str, bool]:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        segments = YouTubeTranscriptApi().fetch(video_id)
        text = " ".join(seg.text for seg in segments)
        return text, True
    except Exception:
        return "", False


def _download_and_sample_frames(url: str, out_dir: str, every_n_seconds: int = 15, max_frames: int = 12) -> list[str]:
    """
    Uses yt-dlp (free) to grab the video, then ffmpeg (assumed present on
    the runner, GitHub Actions ubuntu images ship it) to pull one frame
    every `every_n_seconds`, capped at `max_frames` so this stays fast and
    doesn't fill the disk on a scheduled run.
    """
    video_path = os.path.join(out_dir, "video.mp4")
    subprocess.run(
        ["yt-dlp", "-f", "worst[ext=mp4]/worst", "-o", video_path, url],
        check=True, capture_output=True, timeout=180,
    )
    frame_pattern = os.path.join(out_dir, "frame_%03d.jpg")
    subprocess.run(
        ["ffmpeg", "-i", video_path, "-vf", f"fps=1/{every_n_seconds}",
         "-frames:v", str(max_frames), frame_pattern, "-y"],
        check=True, capture_output=True, timeout=120,
    )
    frames = sorted(
        os.path.join(out_dir, f) for f in os.listdir(out_dir)
        if f.startswith("frame_") and f.endswith(".jpg")
    )
    return frames


def analyze_youtube_video(url: str, keep_frames: bool = False) -> VideoAnalysis:
    video_id = _extract_video_id(url)
    analysis = VideoAnalysis(url=url, video_id=video_id)

    transcript_text, ok = _fetch_transcript(video_id)
    analysis.transcript_text = transcript_text
    analysis.transcript_available = ok
    if not ok:
        analysis.errors.append("transcript_unavailable")

    tmp_dir = tempfile.mkdtemp(prefix="yt_frames_")
    try:
        frames = _download_and_sample_frames(url, tmp_dir)
        analysis.frame_paths = frames
        analysis.frame_count = len(frames)
    except Exception as e:  # noqa: BLE001 -- frame extraction is best-effort
        analysis.errors.append(f"frame_extraction_failed: {e}")

    return analysis


def summarize(analysis: VideoAnalysis) -> str:
    """
    Produces a plain-text summary combining transcript + frame evidence.
    Without a configured vision model this stays honest: it reports how
    many frames were captured and where, rather than pretending to
    describe their visual content.
    """
    lines = [f"Video: {analysis.url} (id={analysis.video_id})"]
    if analysis.transcript_available:
        preview = analysis.transcript_text[:600]
        lines.append(f"Transcript (first ~600 chars): {preview}...")
    else:
        lines.append("Transcript: unavailable for this video.")

    if analysis.frame_count:
        lines.append(f"Visual sampling: {analysis.frame_count} frames captured for review.")
    else:
        lines.append("Visual sampling: no frames captured.")

    if analysis.errors:
        lines.append(f"Errors during analysis: {analysis.errors}")

    return "\n".join(lines)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python watch.py <youtube_url>")
        sys.exit(1)
    result = analyze_youtube_video(sys.argv[1])
    print(summarize(result))
