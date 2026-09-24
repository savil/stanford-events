"""CLI: scrape Localist + HCI Seminar + HAI, write out/events.json and the by-day page."""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from collections import Counter
from pathlib import Path

from . import hai, hci_seminar, localist
from .normalize import dedupe, filter_window
from .preview import render_html, render_markdown

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "out"


def _run_source(name: str, fn, errors: list[dict]) -> list:
    try:
        events = fn()
        return events
    except Exception as exc:  # per-source failures OK
        errors.append(
            {
                "source": name,
                "error": f"{type(exc).__name__}: {exc}",
                "traceback": traceback.format_exc(limit=5),
            }
        )
        return []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scrape Stanford events into out/")
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help="Output directory (default: ./out)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Include events from today through +N days PT (default 30)",
    )
    args = parser.parse_args(argv)

    out_dir: Path = args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    errors: list[dict] = []
    all_events = []

    print("Fetching Localist…", flush=True)
    all_events.extend(_run_source("localist", lambda: localist.fetch_events(days=args.days), errors))

    print("Fetching HCI Seminar…", flush=True)
    all_events.extend(_run_source("hci_seminar", hci_seminar.fetch_events, errors))

    print("Fetching HAI…", flush=True)
    all_events.extend(_run_source("hai", hai.fetch_events, errors))

    windowed = filter_window(all_events, days=args.days)
    final = dedupe(windowed)

    counts = Counter(e["source_name"] for e in final)
    # Also collapse Bing into a report-friendly localist bucket note
    by_module = Counter()
    for e in final:
        sn = e["source_name"]
        if "Localist" in sn or sn.startswith("Bing"):
            by_module["localist"] += 1
        elif "HCI" in sn:
            by_module["hci_seminar"] += 1
        elif "HAI" in sn:
            by_module["hai"] += 1
        else:
            by_module["other"] += 1

    events_path = out_dir / "events.json"
    errors_path = out_dir / "errors.json"
    md_path = out_dir / "sample-preview.md"
    html_path = out_dir / "index.html"

    errors_path.write_text(json.dumps(errors, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    # Every source failed: keep the last good listing on disk and fail the job
    # so the Action does not commit an empty calendar.
    if not final and errors:
        print(f"Wrote {errors_path} ({len(errors)} errors)", flush=True)
        print("Errors:", file=sys.stderr)
        for err in errors:
            print(f"  - {err['source']}: {err['error']}", file=sys.stderr)
        print("All sources failed; left the previous listing in place.", file=sys.stderr)
        return 1

    events_path.write_text(json.dumps(final, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(final), encoding="utf-8")
    html_path.write_text(
        render_html(final, errors=errors, days=args.days),
        encoding="utf-8",
    )

    print(f"Wrote {events_path} ({len(final)} events)", flush=True)
    print(f"Wrote {errors_path} ({len(errors)} errors)", flush=True)
    print(f"Wrote {md_path}", flush=True)
    print(f"Wrote {html_path}", flush=True)
    print("Counts by source_name:", dict(counts), flush=True)
    print("Counts by module:", dict(by_module), flush=True)
    aud_counts = Counter(e.get("audience", "unknown") for e in final)
    print("Counts by audience:", dict(aud_counts), flush=True)
    by_src_aud: dict[str, Counter] = {}
    for e in final:
        by_src_aud.setdefault(e["source_name"], Counter())[e.get("audience", "unknown")] += 1
    print("Audience by source_name:", {k: dict(v) for k, v in by_src_aud.items()}, flush=True)
    merged_across = sum(1 for e in final if e.get("also_sources"))
    print(f"Cross-source collapses: {merged_across}", flush=True)
    if errors:
        print("Errors:", file=sys.stderr)
        for err in errors:
            print(f"  - {err['source']}: {err['error']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
