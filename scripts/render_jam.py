#!/usr/bin/env python3
import json
import re
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "data" / "jam.json"

TARGET_INDEX = ROOT / "index.html"
TARGET_JAM = ROOT / "jam" / "index.html"

# Blocks in HTML (must exist in both files exactly like in your HTML)
BLOCKS = {
    "event_jsonld": (
        re.compile(r"<!--\s*JAM_EVENT_JSONLD_START\s*-->(.*?)<!--\s*JAM_EVENT_JSONLD_END\s*-->",
                   re.DOTALL),
        "JAM_EVENT_JSONLD_START",
        "JAM_EVENT_JSONLD_END",
    ),
    "startpage": (
        re.compile(r"<!--\s*JAM_STARTPAGE_BLOCK_START\s*-->(.*?)<!--\s*JAM_STARTPAGE_BLOCK_END\s*-->",
                   re.DOTALL),
        "JAM_STARTPAGE_BLOCK_START",
        "JAM_STARTPAGE_BLOCK_END",
    ),
    "jampage": (
        re.compile(r"<!--\s*JAM_JAMPAGE_BLOCK_START\s*-->(.*?)<!--\s*JAM_JAMPAGE_BLOCK_END\s*-->",
                   re.DOTALL),
        "JAM_JAMPAGE_BLOCK_START",
        "JAM_JAMPAGE_BLOCK_END",
    ),
}

WEEKDAY_DE_SHORT = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
MONTH_DE = [
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember"
]

def parse_start_iso(s: str) -> datetime:
    # expects ISO 8601, ideally with timezone like 2026-02-19T19:00:00+01:00
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("Europe/Berlin"))
    return dt

def enrich(data: dict) -> dict:
    dt = parse_start_iso(data["jam_start_iso"])
    wd = WEEKDAY_DE_SHORT[dt.weekday()]
    month = MONTH_DE[dt.month - 1]

    data = dict(data)  # copy
    data["jam_time"] = dt.strftime("%H:%M")
    data["jam_date_short"] = dt.strftime("%d.%m.%Y")          # 19.02.2026
    data["jam_date_human"] = f"{wd} {dt.day}. {month} {dt.year}"       # Do 19. Februar 2026
    data["jam_date_human_short"] = f"{wd} {dt.day}. {month} {dt.year}" # keep year on startpage (as requested)

    return data

def build_event_jsonld(data: dict) -> str:
    # address: we keep the structured address fixed for now (Berlin example),
    # because your input is a single string. If you want, we can parse it.
    # We still keep jam_address in the visible HTML.
    # NOTE: No HTML comments inside JSON-LD content.
    return f"""<!-- JAM_EVENT_JSONLD_START -->
<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "Event",
  "name": "Jam Session – Kulturinsel Moabit",
  "description": "Offene Jam-Session der Kulturinsel Moabit mit spontaner Musik, kreativen Sounds und offenen Bühnenmomenten in der Kulturfabrik Moabit.",
  "image": "https://kulturinselmoabit.org/jamsession.jpg",
  "startDate": "{data['jam_start_iso']}",
  "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
  "eventStatus": "https://schema.org/EventScheduled",
  "url": "{data.get('jam_url','https://kulturinselmoabit.org/jam/')}",
  "location": {{
    "@type": "Place",
    "name": "{data['jam_venue']}",
    "address": {{
      "@type": "PostalAddress",
      "streetAddress": "Lehrter Str. 35",
      "postalCode": "10557",
      "addressLocality": "Berlin",
      "addressCountry": "DE"
    }}
  }},
  "organizer": {{
    "@type": "Organization",
    "name": "Kulturinsel Moabit",
    "url": "https://kulturinselmoabit.org/",
    "logo": "https://kulturinselmoabit.org/logo.svg"
  }},
  "offers": {{
    "@type": "Offer",
    "price": "0",
    "priceCurrency": "EUR",
    "availability": "https://schema.org/InStock",
    "url": "{data.get('jam_url','https://kulturinselmoabit.org/jam/')}"
  }}
}}
</script>
<!-- JAM_EVENT_JSONLD_END -->""".strip()

def build_startpage_block(data: dict) -> str:
    # This matches your current startpage structure inside .index-gallery__wide-text
    # (only this inner block is regenerated)
    return f"""<!-- JAM_STARTPAGE_BLOCK_START -->
<div class="index-gallery__wide-text-top">
  <div class="index-gallery__wide-coming">COMING UP:</div>
  <div class="index-gallery__wide-date">{data['jam_date_human_short']}</div>
</div>

<div class="index-gallery__wide-title">Jam Session</div>

<div class="index-gallery__wide-sub">in der {data['jam_venue']}</div>
<!-- JAM_STARTPAGE_BLOCK_END -->""".strip()

def build_jampage_block(data: dict) -> str:
    # Regenerates ONLY the h3 + ul, keeps the rest of the jam page untouched
    return f"""<!-- JAM_JAMPAGE_BLOCK_START -->
<h3>Nächster Termin {data['jam_date_human']}, {data['jam_time']}Uhr<br>{data['jam_venue']}</h3>

<ul>
  <li>🧭 <strong>Ort:</strong> {data['jam_venue']}, {data['jam_address']}</li>
  <li>🗓️ <strong>Datum:</strong> {data['jam_date_short']}</li>
  <li>⏰ <strong>Uhrzeit:</strong> {data['jam_time']} Uhr</li>
</ul>
<!-- JAM_JAMPAGE_BLOCK_END -->""".strip()

def replace_block(html: str, pattern: re.Pattern, replacement: str) -> str:
    if not pattern.search(html):
        raise RuntimeError("Block marker not found in file (pattern did not match).")
    return pattern.sub(replacement, html, count=1)

def process_file(path: Path, data: dict, is_index: bool) -> None:
    html = path.read_text(encoding="utf-8")

    # Always replace JSON-LD block (present in both HTMLs)
    pat_jsonld, _, _ = BLOCKS["event_jsonld"]
    html = replace_block(html, pat_jsonld, build_event_jsonld(data))

    if is_index:
        pat_start, _, _ = BLOCKS["startpage"]
        html = replace_block(html, pat_start, build_startpage_block(data))
    else:
        pat_jam, _, _ = BLOCKS["jampage"]
        html = replace_block(html, pat_jam, build_jampage_block(data))

    path.write_text(html, encoding="utf-8")

def main() -> int:
    raw = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    data = enrich(raw)

    process_file(TARGET_INDEX, data, is_index=True)
    process_file(TARGET_JAM, data, is_index=False)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
