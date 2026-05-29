#!/usr/bin/env python3
"""
battery_report.py — Query Seq for pyInkDisplay battery history.

Pulls wake-cycle events from Seq, groups them into continuous battery sessions,
and prints drain per cycle plus an estimated total runtime projection.

Usage:
    python scripts/battery_report.py
    python scripts/battery_report.py --days 14
"""

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

SEQ_HOST = "192.168.1.50"
SEQ_API_KEY = "3FHO4tigPa4ScyhOHCcq"
SAST_OFFSET = timedelta(hours=2)

# How many events to fetch (each wake cycle = ~4 events; 500 covers ~3 months)
MAX_EVENTS = 500


@dataclass
class WakeCycle:
    time: datetime       # SAST
    power: str           # "battery" or "usb"
    battery_start: float
    battery_end: float | None  # published level after update (None if skipped)
    skipped: bool        # quiet hours — display not updated


def _fetch_events() -> list[dict]:
    cmd = (
        f"SEQ_IP=$(docker inspect seq --format "
        f"'{{{{range .NetworkSettings.Networks}}}}{{{{.IPAddress}}}}{{{{end}}}}') && "
        f"curl -s -H 'X-Seq-ApiKey: {SEQ_API_KEY}' "
        f"\"http://${{SEQ_IP}}:80/api/events?count={MAX_EVENTS}\""
    )
    result = subprocess.run(
        ["ssh", f"dwalsh@{SEQ_HOST}", cmd],
        capture_output=True, text=True, timeout=20,
    )
    if result.returncode != 0:
        print(f"SSH/curl failed: {result.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    return json.loads(result.stdout)


def _msg(event: dict) -> str:
    return "".join(t.get("Text", "") for t in event.get("MessageTemplateTokens", []))


def _props(event: dict) -> dict:
    return {p["Name"]: p["Value"] for p in event.get("Properties", [])}


def _parse_battery(text: str) -> float | None:
    # "battery: 86.5%" from Starting lines, or "battery level 79.01683%" from Published lines
    m = re.search(r"battery(?:[:\s]+level)?\s+([0-9]+(?:\.[0-9]+)?)", text, re.IGNORECASE)
    return float(m.group(1)) if m else None


def _utc_to_sast(ts_str: str) -> datetime:
    dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    return dt.astimezone(timezone(SAST_OFFSET))


def build_cycles(events: list[dict], since: datetime | None) -> list[WakeCycle]:
    """
    Walk events oldest-first, pairing each "Starting" event with the first
    "Published battery level" that follows it (before the next "Starting" event).
    The published event fires at shutdown, up to ~120 min after start.
    """
    all_events = list(reversed(events))  # oldest first

    # Collect all relevant timestamps without the `since` filter so we can
    # look ahead/behind across session boundaries.
    published_all: list[tuple[datetime, float]] = []
    quiet_hours_all: set[str] = set()
    starting_all: list[tuple[datetime, dict]] = []

    for e in all_events:
        msg = _msg(e)
        ts = _utc_to_sast(e["Timestamp"])
        if "Published battery level" in msg:
            pct = _parse_battery(msg)
            if pct is not None:
                published_all.append((ts, pct))
        if "Quiet hours active" in msg:
            quiet_hours_all.add(ts.strftime("%Y-%m-%d %H"))
        if "Starting |" in msg:
            starting_all.append((ts, e))

    cycles: list[WakeCycle] = []
    for i, (ts, e) in enumerate(starting_all):
        if since and ts < since:
            continue

        msg = _msg(e)
        power_m = re.search(r"power:\s*(\w+)", msg)
        batt_m = re.search(r"battery:\s*([0-9.]+)", msg)
        power = power_m.group(1) if power_m else "?"
        batt_start = float(batt_m.group(1)) if batt_m else 0.0

        # Next "Starting" event marks the upper bound for this cycle's shutdown
        next_start_ts = starting_all[i + 1][0] if i + 1 < len(starting_all) else None

        # Find the first "Published" event after this start and before the next start
        batt_end = None
        for pub_ts, pub_pct in published_all:
            if pub_ts < ts:
                continue
            if next_start_ts and pub_ts >= next_start_ts:
                break
            batt_end = pub_pct
            break

        skipped = ts.strftime("%Y-%m-%d %H") in quiet_hours_all

        cycles.append(WakeCycle(ts, power, batt_start, batt_end, skipped))

    return cycles


def print_report(cycles: list[WakeCycle]) -> None:
    if not cycles:
        print("No battery cycles found.")
        return

    # Split into sessions: consecutive battery cycles without a USB gap
    sessions: list[list[WakeCycle]] = []
    current: list[WakeCycle] = []
    for c in cycles:
        if c.power == "battery":
            current.append(c)
        else:
            if current:
                sessions.append(current)
                current = []
    if current:
        sessions.append(current)

    for i, session in enumerate(sessions, 1):
        start_ts = session[0].time
        end_ts = session[-1].time
        duration = end_ts - start_ts

        start_pct = session[0].battery_start
        # Use last published end, or last start as fallback
        last_with_end = next((c for c in reversed(session) if c.battery_end is not None), None)
        end_pct = last_with_end.battery_end if last_with_end else session[-1].battery_start
        total_drain = start_pct - end_pct

        print(f"\n{'═'*62}")
        print(f"  Battery session {i}  —  {start_ts.strftime('%a %d %b, %H:%M')} SAST")
        print(f"{'═'*62}")
        print(f"  Start: {start_pct:.1f}%   End: {end_pct:.1f}%   "
              f"Drain: {total_drain:.1f}%   Duration: {_fmt_duration(duration)}")
        print()
        print(f"  {'Time (SAST)':<18} {'Start%':>7} {'End%':>7} {'Drain':>7}  Note")
        print(f"  {'-'*18} {'-'*7} {'-'*7} {'-'*7}  {'-'*10}")

        drains = []
        for c in session:
            drain_str = ""
            note = "quiet hrs (skipped)" if c.skipped else ""
            if c.battery_end is not None:
                drain = c.battery_start - c.battery_end
                if drain < 0:
                    drain_str = "  noise"
                    note = note or "(sensor noise)"
                else:
                    drains.append(drain)
                    drain_str = f"-{drain:.1f}%"
            end_str = f"{c.battery_end:.1f}%" if c.battery_end is not None else "  —  "
            print(f"  {c.time.strftime('%a %d %b %H:%M'):<18} "
                  f"{c.battery_start:>6.1f}% {end_str:>7} {drain_str:>8}  {note}")

        if drains:
            avg_drain = sum(drains) / len(drains)
            print()
            print(f"  Avg drain per cycle: {avg_drain:.2f}%")
            if avg_drain > 0:
                cycles_remaining = end_pct / avg_drain
                mins_remaining = cycles_remaining * 120  # 120 min interval
                print(f"  Estimated remaining: {_fmt_duration(timedelta(minutes=mins_remaining))} "
                      f"({cycles_remaining:.0f} more cycles at current rate)")

    # Drain rate summary across all sessions
    all_drains = [
        c.battery_start - c.battery_end
        for s in sessions
        for c in s
        if c.battery_end is not None and c.battery_start > c.battery_end
    ]
    if len(all_drains) >= 3:
        overall_avg = sum(all_drains) / len(all_drains)
        est_full = 100.0 / overall_avg * 120
        print(f"\n{'─'*62}")
        print(f"  Overall avg drain: {overall_avg:.2f}% per 2h cycle")
        print(f"  Estimated full-charge runtime: {_fmt_duration(timedelta(minutes=est_full))}")
        print(f"{'─'*62}\n")


def _fmt_duration(d: timedelta) -> str:
    total_min = int(d.total_seconds() / 60)
    h, m = divmod(abs(total_min), 60)
    return f"{h}h {m:02d}m"


def main() -> None:
    parser = argparse.ArgumentParser(description="pyInkDisplay battery history from Seq")
    parser.add_argument("--days", type=int, default=7, help="How many days back to show (default 7)")
    args = parser.parse_args()

    since = datetime.now(tz=timezone(SAST_OFFSET)) - timedelta(days=args.days)
    print(f"Fetching battery history from Seq (last {args.days} days)…")

    events = _fetch_events()
    cycles = build_cycles(events, since=since)
    print_report(cycles)


if __name__ == "__main__":
    main()
