#!/usr/bin/env python3
"""Assemble the standalone player sheet.

Combines the static parts (build/parts/*) with the generated data
(build/skills.json, build/occupations.json) into a single self-contained
HTML file at the project root: coc7e-player-sheet.html.

No external assets: styles and data are inlined.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PARTS = HERE / "parts"
OUT = ROOT / "coc7e-player-sheet.html"

DATA_MARKER = "/*__COC_DATA__*/"


def main():
    skills = json.loads((HERE / "skills.json").read_text(encoding="utf-8"))
    occupations = json.loads((HERE / "occupations.json").read_text(encoding="utf-8"))
    data = {"skills": skills, "occupations": occupations}
    data_js = "window.COC_DATA = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n"

    head = (PARTS / "head.html").read_text(encoding="utf-8")
    body = (PARTS / "body.html").read_text(encoding="utf-8")
    app = (PARTS / "app.js").read_text(encoding="utf-8")

    html = head + "\n" + body + "\n<script>\n" + data_js + app + "\n</script>\n</body>\n</html>\n"
    html = html.replace(DATA_MARKER, DATA_MARKER)  # keep marker if present in a part
    OUT.write_text(html, encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()