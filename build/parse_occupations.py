#!/usr/bin/env python3
"""Extract structured occupation data (points formula, credit rating, skills)
from the Call of Cthulhu 7e Investigator's Handbook PDF (Chapter Four, pp. 66-93).

Approach: two passes over the PDF.
  1. pdftotext -raw   -> linear reading order of both columns.
  2. pdftohtml -xml   -> font-aware text; real occupation headings use the
                         Cristoforo-Cthulhu typeface. That list becomes the
                         canonical entry-boundary list for pass 1.

Run via build/make.sh. Writes build/occupations.json.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PDF = HERE / "co7eh-ih.pdf"
RAW = HERE / "ih_occupations.txt"
XML = HERE / "ih_occupations.xml"
OUT = HERE / "occupations_raw.json"

CRISTOFORO = "Cristoforo"
RUNNING_HEADS = {"investigator's handbook", "chapter 4: occupations"}


def ensure_extracted():
    if not RAW.exists():
        subprocess.run(
            ["pdftotext", "-raw", "-f", "66", "-l", "93", str(PDF), str(RAW)],
            check=True,
        )
    if not XML.exists():
        subprocess.run(
            ["pdftohtml", "-xml", "-f", "66", "-l", "93", "-i", "-stdout", str(PDF)],
            stdout=open(XML, "w"),
            check=True,
        )


def cristoforo_headings():
    """Ordered list of occupation headings by their distinctive typeface.

    Groups styled text runs that belong to the same visual line (page + top)
    and returns {normalized: canonical} plus the canonical list in reading order.
    """
    text = XML.read_text(encoding="utf-8", errors="replace")
    fonts = {}
    for m in re.finditer(r'<fontspec id="(\d+)" size="(\d+)" family="([^"]+)"', text):
        fonts[m.group(1)] = (int(m.group(2)), m.group(3))

    runs = []  # (page, top, left, text)
    page = 0
    for chunk in re.split(r'<page number="(\d+)"', text)[1:]:
        if chunk.strip().isdigit() and len(chunk) < 8:
            page = int(chunk.strip())
            continue
        for m in re.finditer(
            r'<text top="(\d+)" left="(\d+)" width="\d+" height="\d+" font="(\d+)">(.*?)</text>',
            chunk, re.S,
        ):
            top, left, fontid = int(m.group(1)), int(m.group(2)), m.group(3)
            fam = fonts.get(fontid, ("", ""))[1]
            if not fam or CRISTOFORO not in fam or top > 1100:
                continue
            content = re.sub(r"<[^>]+>", "", m.group(4)).replace("\u00a0", " ").strip()
            if content:
                runs.append((page, top, left, content))

    # group runs sharing a visual line
    lines = []
    for page, top, left, content in runs:
        if lines and lines[-1][0] == page and abs(lines[-1][1] - top) <= 4:
            lines[-1][3].append((left, content))
        else:
            lines.append([page, top, left, [(left, content)]])
    headings = []
    for page, top, left, parts in lines:
        parts.sort()
        name = " ".join(c for _, c in parts)
        name = re.sub(r"\s+", " ", name).strip()
        headings.append(name)

    section_titles = {
        "list of occupations", "sample occupations", "creating occupations", "key:",
    }
    out = []
    for h in headings:
        if h.lower().rstrip(":") in {s.rstrip(":") for s in section_titles}:
            continue
        out.append(h)
    return out


def split_colon(stripped):
    idx = stripped.find(":")
    if idx < 0:
        return None
    return stripped[idx + 1:].strip()


EXEMPT = {"and", "or", "of", "the"}


def looks_like_heading(line):
    raw = line.strip()
    if not raw or len(raw) > 55 or raw.endswith((".", ",", ";", ":", "-")):
        return False
    if not raw[0].isupper():
        return False
    words = [w for w in re.split(r"[^A-Za-z]+", raw) if w]
    if not words:
        return False
    for w in words:
        if w.lower() in EXEMPT or w.isdigit() or w.isupper() or w[0].isupper():
            continue
        return False
    return True


def main():
    if not PDF.exists():
        sys.exit(
            f"Missing {PDF.name}. Place the Investigator's Handbook PDF in {HERE}\n"
            "(run `ln -s /path/to/ih.pdf build/co7eh-ih.pdf`)."
        )
    ensure_extracted()
    heads = cristoforo_headings()
    head_set = {re.sub(r"\s+", "", h).lower(): h for h in heads}
    lines = [ln.rstrip() for ln in RAW.read_text(encoding="utf-8").splitlines()]

    entries = []
    pending = None       # name of the pending (cristoforo) entry
    cur = None
    field = None         # points | cr | contacts | skills

    def close():
        nonlocal cur, field
        if cur is not None and cur["points"]:
            entries.append(cur)
        cur = None
        field = None

    def new_entry(name):
        nonlocal cur, field, pending
        close()
        cur = {"name": name, "points": "", "cr": "", "contacts": "", "skills": ""}
        pending = None
        field = None

    n = len(lines)
    i = 0
    while i < n:
        stripped = lines[i].strip()
        i += 1
        if not stripped:
            continue
        if stripped in RUNNING_HEADS or re.fullmatch(r"\d+", stripped):
            continue

        norm = re.sub(r"\s+", "", stripped).lower()

        # a cristoforo-typeface heading?
        headkey = re.sub(r"\s+", "", stripped).lower()
        if headkey in head_set:
            close()                       # stop collecting the previous entry
            pending = head_set[headkey]
            continue

        # sub-heading followed immediately by its own points field
        if norm.startswith("occupationskillpoints"):
            # previous meaningful line (the one before this points line)
            prev = None
            j = i - 2
            while j >= 0:
                pl = lines[j].strip()
                if not pl or pl in RUNNING_HEADS or re.fullmatch(r"\d+", pl):
                    j -= 1
                    continue
                prev = pl
                break
            if prev is not None and looks_like_heading(prev) and prev != pending:
                name = prev                      # sub-heading (Stage Actor, Assassin, ...)
            else:
                name = pending
                if name is None:
                    # scan further back for the nearest heading-ish line
                    for k in range(j - 1, max(-1, j - 25), -1):
                        if looks_like_heading(lines[k].strip()):
                            name = lines[k].strip()
                            break
            if name is None:
                continue
            close()
            cur = {"name": name, "points": "", "cr": "", "contacts": "", "skills": ""}
            pending = None
            cur["points"] = split_colon(stripped)
            if cur["points"] is None:
                continue
            field = "points"
            continue
        if cur is None:
            continue
        field_started = False
        if norm.startswith("creditrating"):
            v = split_colon(stripped)
            if v is not None:
                cur["cr"] = v
                field = "cr"
                field_started = True
        elif norm.startswith("suggestedcontacts"):
            v = split_colon(stripped)
            if v is not None:
                cur["contacts"] = v
                field = "contacts"
                field_started = True
        elif norm.startswith("skillspoints"):
            v = split_colon(stripped)
            if v is not None:
                cur["skillpoints"] = v
                field = "skillpoints"
                field_started = True
        elif norm.startswith("skills"):
            v = split_colon(stripped)
            if v is not None:
                cur["skills"] = v
                field = "skills"
                field_started = True
        if field_started:
            continue
        if norm.startswith("also,seegangster") or norm.startswith("note:withthekeeper"):
            continue
        if field in ("points", "cr", "contacts", "skills", "skillpoints"):
            if cur[field] is None:
                cur[field] = ""
            nxt = lines[i].strip() if i < n else ""
            if field in ("contacts", "skills") and re.sub(r"\s+", "", nxt).lower().startswith(
                "occupationskillpoints"
            ):
                continue  # this line is the next entry's sub-heading
            cur[field] = (cur[field] + " " + stripped).strip()

    close()

    formula_re = re.compile(r"EDU", re.I)
    clean = []
    seen = set()
    for e in entries:
        pts = (e["points"] or "").strip()
        if not formula_re.search(pts):
            continue                      # legend / front-matter blurb
        key = (e["name"], pts)
        if key in seen:
            continue
        seen.add(key)
        clean.append(e)
    entries = clean

    OUT.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(entries)} occupations -> {OUT}")


if __name__ == "__main__":
    main()