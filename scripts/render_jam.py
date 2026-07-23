#!/usr/bin/env python3

import html
import json
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "data" / "jam.json"

TARGET_INDEX = ROOT / "index.html"
TARGET_JAM = ROOT / "jam" / "index.html"


RE_EVENT = re.compile(
    r"<!--\s*JAM_EVENT_JSONLD_START\s*-->"
    r"(.*?)"
    r"<!--\s*JAM_EVENT_JSONLD_END\s*-->",
    re.DOTALL,
)

RE_STARTPAGE = re.compile(
    r"<!--\s*JAM_STARTPAGE_BLOCK_START\s*-->"
    r"(.*?)"
    r"<!--\s*JAM_STARTPAGE_BLOCK_END\s*-->",
    re.DOTALL,
)

RE_JAM_H3 = re.compile(
    r"<!--\s*JAM_JAMPAGE_H3_START\s*-->"
    r"(.*?)"
    r"<!--\s*JAM_JAMPAGE_H3_END\s*-->",
    re.DOTALL,
)

RE_JAM_UL = re.compile(
    r"<!--\s*JAM_JAMPAGE_UL_START\s*-->"
    r"(.*?)"
    r"<!--\s*JAM_JAMPAGE_UL_END\s*-->",
    re.DOTALL,
)


WEEKDAY_DE_SHORT = [
    "Mo",
    "Di",
    "Mi",
    "Do",
    "Fr",
    "Sa",
    "So",
]

MONTH_DE = [
    "Januar",
    "Februar",
    "März",
    "April",
    "Mai",
    "Juni",
    "Juli",
    "August",
    "September",
    "Oktober",
    "November",
    "Dezember",
]


def parse_iso(value: str) -> datetime:
    """
    Liest einen ISO-Zeitstempel ein.

    Falls keine Zeitzone angegeben wurde, wird Europe/Berlin verwendet.
    """

    dt = datetime.fromisoformat(value)

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("Europe/Berlin"))

    return dt


def format_single_date(dt: datetime) -> str:
    """
    Beispiel:
    Do 19. März 2026
    """

    weekday = WEEKDAY_DE_SHORT[dt.weekday()]
    month = MONTH_DE[dt.month - 1]

    return f"{weekday} {dt.day}. {month} {dt.year}"


def format_date_range(start: datetime, end: datetime | None) -> str:
    """
    Erzeugt die Datumsdarstellung für die Startseite.

    Beispiele:

    Do 19. März 2026
    Sa 1.–So 2. August 2026
    Di 30. Juni–Mi 1. Juli 2026
    """

    if end is None or start.date() == end.date():
        return format_single_date(start)

    start_weekday = WEEKDAY_DE_SHORT[start.weekday()]
    end_weekday = WEEKDAY_DE_SHORT[end.weekday()]

    start_month = MONTH_DE[start.month - 1]
    end_month = MONTH_DE[end.month - 1]

    if start.year == end.year and start.month == end.month:
        return (
            f"{start_weekday} {start.day}.–"
            f"{end_weekday} {end.day}. {end_month} {end.year}"
        )

    if start.year == end.year:
        return (
            f"{start_weekday} {start.day}. {start_month}–"
            f"{end_weekday} {end.day}. {end_month} {end.year}"
        )

    return (
        f"{start_weekday} {start.day}. {start_month} {start.year}–"
        f"{end_weekday} {end.day}. {end_month} {end.year}"
    )


def enrich_event(data: dict) -> dict:
    """
    Ergänzt die Ereignisdaten um automatisch erzeugte Datumsformate.
    """

    required_fields = [
        "title",
        "start_iso",
        "venue",
        "address",
        "url",
    ]

    for field in required_fields:
        if not data.get(field):
            raise ValueError(
                f"Pflichtfeld fehlt oder ist leer: {field}"
            )

    start = parse_iso(data["start_iso"])

    end = None
    if data.get("end_iso"):
        end = parse_iso(data["end_iso"])

        if end < start:
            raise ValueError(
                f'end_iso liegt vor start_iso beim Event "{data["title"]}".'
            )

    out = dict(data)

    out["start"] = start
    out["end"] = end

    out["time"] = start.strftime("%H:%M")
    out["date_short"] = start.strftime("%d.%m.%Y")
    out["date_human"] = format_single_date(start)
    out["date_display"] = format_date_range(start, end)

    return out


def build_event_jsonld(event: dict) -> str:
    """
    Erzeugt ein vollständiges Schema.org-Event.

    json.dumps verhindert ungültiges JSON bei Anführungszeichen,
    Umlauten oder Sonderzeichen.
    """

    jsonld = {
        "@context": "https://schema.org",
        "@type": "Event",
        "name": event["title"],
        "description": event.get("description", ""),
        "startDate": event["start_iso"],
        "eventAttendanceMode":
            "https://schema.org/OfflineEventAttendanceMode",
        "eventStatus":
            "https://schema.org/EventScheduled",
        "url": event["url"],
        "location": {
            "@type": "Place",
            "name": event["venue"],
            "address": {
                "@type": "PostalAddress",
                "streetAddress": event.get(
                    "street_address",
                    event["address"],
                ),
                "postalCode": event.get("postal_code", ""),
                "addressLocality": event.get(
                    "locality",
                    "Berlin",
                ),
                "addressCountry": event.get(
                    "country",
                    "DE",
                ),
            },
        },
        "organizer": {
            "@type": "Organization",
            "name": "Kulturinsel Moabit",
            "url": "https://kulturinselmoabit.org/",
            "logo": "https://kulturinselmoabit.org/logo.svg",
        },
        "offers": {
            "@type": "Offer",
            "price": "0",
            "priceCurrency": "EUR",
            "availability":
                "https://schema.org/InStock",
            "url": event["url"],
        },
    }

    if event.get("end_iso"):
        jsonld["endDate"] = event["end_iso"]

    if event.get("image"):
        jsonld["image"] = event["image"]

    json_text = json.dumps(
        jsonld,
        ensure_ascii=False,
        indent=2,
    )

    return f"""<!-- JAM_EVENT_JSONLD_START -->
<script type="application/ld+json">
{json_text}
</script>
<!-- JAM_EVENT_JSONLD_END -->""".strip()


def build_startpage_block(event: dict) -> str:
    """
    Behält die bisherige HTML-Struktur der Startseite bei.
    """

    title = html.escape(event["title"])
    subtitle = html.escape(event.get("subtitle", ""))
    date_display = html.escape(event["date_display"])

    return f"""<!-- JAM_STARTPAGE_BLOCK_START -->
    <div class="index-gallery__wide-text-top">
      <div class="index-gallery__wide-coming">COMING UP:</div>
      <div class="index-gallery__wide-date">{date_display}</div>
    </div>

    <div class="index-gallery__wide-title">{title}</div>

    <div class="index-gallery__wide-sub">{subtitle}</div>
<!-- JAM_STARTPAGE_BLOCK_END -->""".rstrip()


def build_jam_h3(jam: dict) -> str:
    """
    Erzeugt ausschließlich die Terminüberschrift der Jam-Seite.
    """

    date_human = html.escape(jam["date_human"])
    time = html.escape(jam["time"])
    venue = html.escape(jam["venue"])

    return f"""<!-- JAM_JAMPAGE_H3_START -->
        <h3>Nächster Termin {date_human}, {time} Uhr {venue}</h3>
<!-- JAM_JAMPAGE_H3_END -->""".rstrip()


def build_jam_ul_details(jam: dict) -> str:
    """
    Erzeugt ausschließlich die Detail-Liste der Jam-Seite.
    """

    venue = html.escape(jam["venue"])
    address = html.escape(jam["address"])
    date_short = html.escape(jam["date_short"])
    time = html.escape(jam["time"])

    return f"""<!-- JAM_JAMPAGE_UL_START -->
          <li>🧭 <strong>Ort:</strong> {venue}, {address}</li>
          <li>🗓️ <strong>Datum:</strong> {date_short}</li>
          <li>⏰ <strong>Uhrzeit:</strong> {time} Uhr</li>
<!-- JAM_JAMPAGE_UL_END -->""".rstrip()


def sub_one(
    regex: re.Pattern,
    source: str,
    replacement: str,
    label: str,
) -> str:
    """
    Ersetzt genau einen markierten Block.
    """

    matches = regex.findall(source)

    if not matches:
        raise RuntimeError(
            f"Block nicht gefunden: {label}"
        )

    if len(matches) > 1:
        raise RuntimeError(
            f"Block mehrfach gefunden: {label}"
        )

    return regex.sub(
        lambda _: replacement,
        source,
        count=1,
    )


def process_index(
    source: str,
    coming_up: dict,
) -> str:
    """
    Auf der Startseite werden JSON-LD und Coming-Up-Block
    aus dem ausgewählten Event erzeugt.
    """

    source = sub_one(
        RE_EVENT,
        source,
        build_event_jsonld(coming_up),
        "JAM_EVENT_JSONLD (index)",
    )

    source = sub_one(
        RE_STARTPAGE,
        source,
        build_startpage_block(coming_up),
        "JAM_STARTPAGE_BLOCK (index)",
    )

    return source


def process_jam(
    source: str,
    jam: dict,
) -> str:
    """
    Die Jam-Seite wird unabhängig von der Startseiten-Auswahl
    immer aus dem Event 'jam' erzeugt.
    """

    source = sub_one(
        RE_EVENT,
        source,
        build_event_jsonld(jam),
        "JAM_EVENT_JSONLD (jam)",
    )

    source = sub_one(
        RE_JAM_H3,
        source,
        build_jam_h3(jam),
        "JAM_JAMPAGE_H3 (jam)",
    )

    source = sub_one(
        RE_JAM_UL,
        source,
        build_jam_ul_details(jam),
        "JAM_JAMPAGE_UL (jam)",
    )

    return source


def load_events() -> tuple[dict, dict]:
    """
    Lädt die Datei und gibt zurück:

    1. das ausgewählte Coming-Up-Event
    2. das Jam-Event
    """

    raw = json.loads(
        DATA_FILE.read_text(encoding="utf-8")
    )

    selected_key = raw.get("coming_up")

    if not selected_key:
        raise ValueError(
            'In jam.json fehlt das Feld "coming_up".'
        )

    if selected_key not in raw:
        raise ValueError(
            f'Das ausgewählte Event "{selected_key}" '
            "ist in jam.json nicht vorhanden."
        )

    if "jam" not in raw:
        raise ValueError(
            'In jam.json fehlt der Event-Block "jam".'
        )

    coming_up = enrich_event(raw[selected_key])
    jam = enrich_event(raw["jam"])

    return coming_up, jam


def main() -> int:
    coming_up, jam = load_events()

    index_source = TARGET_INDEX.read_text(
        encoding="utf-8"
    )

    jam_source = TARGET_JAM.read_text(
        encoding="utf-8"
    )

    index_result = process_index(
        index_source,
        coming_up,
    )

    jam_result = process_jam(
        jam_source,
        jam,
    )

    TARGET_INDEX.write_text(
        index_result,
        encoding="utf-8",
    )

    TARGET_JAM.write_text(
        jam_result,
        encoding="utf-8",
    )

    print(
        f'Coming Up aktualisiert: "{coming_up["title"]}" '
        f'– {coming_up["date_display"]}'
    )

    print(
        f'Jam-Seite aktualisiert: '
        f'{jam["date_human"]}, {jam["time"]} Uhr'
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())#!/usr/bin/env python3 
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
