#!/usr/bin/env python3
import json
import re
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "data" / "jam.json"
TARGETS = [
    ROOT / "index.html",
    ROOT / "jam" / "index.html",
]

BLOCK_RE = re.compile(
    r"<!--\s*JAM_BLOCK_START\s*-->(.*?)<!--\s*JAM_BLOCK_END\s*-->",
    re.DOTALL,
)

WEEKDAY_DE_SHORT = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
MONTH_DE = [
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember"
]

def enrich_data(data):
    dt = datetime.fromisoformat(data["jam_start_iso"])
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("Europe/Berlin"))

    weekday = WEEKDAY_DE_SHORT[dt.weekday()]
    month_name = MONTH_DE[dt.month - 1]

    data["jam_time"] = dt.strftime("%H:%M")
    data["jam_date_human"] = f"{weekday} {dt.day}. {month_name} {dt.year}"
    data["jam_date_human_short"] = f"{weekday} {dt.day}. {month_name}"
    data["jam_date_short"] = dt.strftime("%d.%m.%Y")

    return data

def render_block(data):
    return f"""
<h3>
  Nächster Termin {data['jam_date_human']}, {data['jam_time']}Uhr<br>
  {data['jam_venue']}
</h3>
""".strip()

def render_file(path, data):
    content = path.read_text(encoding="utf-8")

    def replace_block(match):
        return f"<!-- JAM_BLOCK_START -->\n{render_block(data)}\n<!-- JAM_BLOCK_END -->"

    content = BLOCK_RE.sub(replace_block, content)
    path.write_text(content, encoding="utf-8")

def main():
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    data = enrich_data(data)

    for t in TARGETS:
        if t.exists():
            render_file(t, data)

if __name__ == "__main__":
    main()
