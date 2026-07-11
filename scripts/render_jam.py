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

RE_EVENT = re.compile(r"<!--\s*JAM_EVENT_JSONLD_START\s*-->(.*?)<!--\s*JAM_EVENT_JSONLD_END\s*-->", re.DOTALL)
RE_STARTPAGE = re.compile(r"<!--\s*JAM_STARTPAGE_BLOCK_START\s*-->(.*?)<!--\s*JAM_STARTPAGE_BLOCK_END\s*-->", re.DOTALL)
RE_JAM_H3 = re.compile(r"<!--\s*JAM_JAMPAGE_H3_START\s*-->(.*?)<!--\s*JAM_JAMPAGE_H3_END\s*-->", re.DOTALL)
RE_JAM_UL = re.compile(r"<!--\s*JAM_JAMPAGE_UL_START\s*-->(.*?)<!--\s*JAM_JAMPAGE_UL_END\s*-->", re.DOTALL)

WEEKDAY_DE_SHORT = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
MONTH_DE = [
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember"
]

def parse_start_iso(s: str) -> datetime:
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("Europe/Berlin"))
    return dt

def enrich(data: dict) -> dict:
    dt = parse_start_iso(data["jam_start_iso"])
    wd = WEEKDAY_DE_SHORT[dt.weekday()]
    month = MONTH_DE[dt.month - 1]

    out = dict(data)
    out["jam_time"] = dt.strftime("%H:%M")
    out["jam_date_short"] = dt.strftime("%d.%m.%Y")               # 19.02.2026
    out["jam_date_human"] = f"{wd} {dt.day}. {month} {dt.year}"   # Do 19. Februar 2026
    out["jam_date_human_short"] = f"{wd} {dt.day}. {month} {dt.year}"  # Startseite mit Jahr
    return out

def build_event_jsonld(d: dict) -> str:
    # Hinweis: Adresse im JSON-LD als strukturierte PostalAddress.
    # Wenn du willst, kann man jam_address später automatisch parsen; hier ist es fest auf Berlin/DE abgestimmt.
    return f"""<!-- JAM_EVENT_JSONLD_START -->
<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "Event",
  "name": "Jam Session – Kulturinsel Moabit",
  "description": "Offene Jam-Session der Kulturinsel Moabit mit spontaner Musik, kreativen Sounds und offenen Bühnenmomenten in der Kulturfabrik Moabit.",
  "image": "https://kulturinselmoabit.org/jamsession.jpg",
  "startDate": "{d["jam_start_iso"]}",
  "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
  "eventStatus": "https://schema.org/EventScheduled",
  "url": "{d.get("jam_url","https://kulturinselmoabit.org/jam/")}",
  "location": {{
    "@type": "Place",
    "name": "{d["jam_venue"]}",
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
    "url": "{d.get("jam_url","https://kulturinselmoabit.org/jam/")}"
  }}
}}
</script>
<!-- JAM_EVENT_JSONLD_END -->""".strip()

def build_startpage_block(d: dict) -> str:
    # 1:1 Template (nur Werte aktualisiert)
    return f"""<!-- JAM_STARTPAGE_BLOCK_START -->
    <div class="index-gallery__wide-text-top">
      <div class="index-gallery__wide-coming">COMING UP:</div>
      <div class="index-gallery__wide-date">{d["jam_date_human_short"]}</div>
    </div>

    <div class="index-gallery__wide-title">Jam Session</div>

    <div class="index-gallery__wide-sub">in der {d["jam_venue"]}</div>
<!-- JAM_STARTPAGE_BLOCK_END -->""".rstrip()

def build_jam_h3(d: dict) -> str:
    # 1:1 Template wie früher: alles in einer Zeile (keine Layout-Änderung)
    return f"""<!-- JAM_JAMPAGE_H3_START -->
        <h3>Nächster Termin {d["jam_date_human"]}, {d["jam_time"]}Uhr {d["jam_venue"]}</h3>
<!-- JAM_JAMPAGE_H3_END -->""".rstrip()

def build_jam_ul_details(d: dict) -> str:
    # 1:1 Template: gleiche UL/LI Struktur, nur Werte aktualisiert
    return f"""<!-- JAM_JAMPAGE_UL_START -->
          <li>🧭 <strong>Ort:</strong> {d["jam_venue"]}, {d["jam_address"]}</li>
          <li>🗓️ <strong>Datum:</strong> {d["jam_date_short"]}</li>
          <li>⏰ <strong>Uhrzeit:</strong> {d["jam_time"]} Uhr</li>
<!-- JAM_JAMPAGE_UL_END -->""".rstrip()

def sub_one(regex: re.Pattern, html: str, replacement: str, label: str) -> str:
    if not regex.search(html):
        raise RuntimeError(f"Block nicht gefunden: {label}")
    return regex.sub(replacement, html, count=1)

def process_index(html: str, d: dict) -> str:
    html = sub_one(RE_EVENT, html, build_event_jsonld(d), "JAM_EVENT_JSONLD (index)")
    html = sub_one(RE_STARTPAGE, html, build_startpage_block(d), "JAM_STARTPAGE_BLOCK (index)")
    return html

def process_jam(html: str, d: dict) -> str:
    html = sub_one(RE_EVENT, html, build_event_jsonld(d), "JAM_EVENT_JSONLD (jam)")
    html = sub_one(RE_JAM_H3, html, build_jam_h3(d), "JAM_JAMPAGE_H3 (jam)")
    html = sub_one(RE_JAM_UL, html, build_jam_ul_details(d), "JAM_JAMPAGE_UL (jam)")
    return html

def main() -> int:
    raw = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    d = enrich(raw)

    idx = TARGET_INDEX.read_text(encoding="utf-8")
    jam = TARGET_JAM.read_text(encoding="utf-8")

    TARGET_INDEX.write_text(process_index(idx, d), encoding="utf-8")
    TARGET_JAM.write_text(process_jam(jam, d), encoding="utf-8")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
