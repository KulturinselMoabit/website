#!/usr/bin/env python3
import json
import re
from pathlib import Path

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
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    for t in TARGETS:
        if t.exists():
            render_file(t, data)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
