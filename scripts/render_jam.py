#!/usr/bin/env python3
import json
import re
from pathlib import Path
from datetime import datetime

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "data" / "jam.json"
TARGETS = [
    ROOT / "index.html",
    ROOT / "jam" / "index.html",
]

MARKER_RE = re.compile(
    r"(<!--\s*JAM:(?P<key>[a-zA-Z0-9_]+)\s*-->)(.*?)(<!--\s*/JAM:(?P=key)\s*-->)",
    re.DOTALL,
)

WEEKDAY_DE_SHORT = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
MONTH_DE = [
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember"
]

def parse_iso(dt_str: str) -> datetime:
    # Python: "2025-12-18T19:00:00+01:00" → aware datetime
    dt = datetime.fromisoformat(dt_str)

    # Falls tz fehlt, setze Europe/Berlin (best-effort)
    if dt.tzinfo is None and ZoneInfo is not None:
        dt = dt.replace(tzinfo=ZoneInfo("Europe/Berlin"))
    return dt

def enrich_data(data: dict) -> dict:
    dt = parse_iso(data["jam_start_iso"])
    weekday = WEEKDAY_DE_SHORT[dt.weekday()]
    month_name = MONTH_DE[dt.month - 1]

    # abgeleitete Felder (werden in HTML per Marker genutzt)
    derived = dict(data)
    derived["jam_time"] = dt.strftime("%H:%M")
    derived["jam_date_iso"] = dt.strftime("%Y-%m-%d")
    derived["jam_date_short"] = dt.strftime("%d.%m.%Y")

    # "Do 18. Dezember 2025"
    derived["jam_date_human"] = f"{weekday} {dt.day}. {month_name} {dt.year}"
    # "Do 18. Dezember" (für Startseite, kürzer)
    derived["jam_date_human_short"] = f"{weekday} {dt.day}. {month_name}"

    return derived

def render_file(path: Path, data: dict) -> bool:
    original = path.read_text(encoding="utf-8")

    def repl(m: re.Match) -> str:
        key = m.group("key")
        if key not in data:
            return m.group(0)
        return f"{m.group(1)}{data[key]}{m.group(4)}"

    out = MARKER_RE.sub(repl, original)
    if out != original:
        path.write_text(out, encoding="utf-8")
        return True
    return False

def main() -> int:
    raw = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    data = enrich_data(raw)

    for t in TARGETS:
        if t.exists():
            render_file(t, data)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
