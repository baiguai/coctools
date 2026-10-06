#!/usr/bin/env python3
"""Normalize raw occupation entries (build/occupations_raw.json) into the
structured form used by the player sheet (build/occupations.json).

Each occupation becomes:
  {
    "name": "Accountant",
    "era": "",                       # classic | lovecraftian | modern | ""
    "formula": {"edu": 4, "add": [], "choose": []},
    "credit": [30, 70],
    "credit_note": "",
    "skills": [ token, ... ]
  }

Skill tokens:
  {"t": "skill", "id": "accounting"}
  {"t": "pick",  "n": 1, "from": ["charm","fasttalk",...], "label": "one interpersonal"}
  {"t": "any",   "n": 2, "label": "any two other"}
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent

# id -> (display label, base value). dodge/ownlang handled specially by the sheet.
SKILLS = {
    "accounting": ("Accounting", 5),
    "anthropology": ("Anthropology", 1),
    "appraise": ("Appraise", 5),
    "archaeology": ("Archaeology", 1),
    "art": ("Art/Craft", 5),
    "charm": ("Charm", 15),
    "climb": ("Climb", 20),
    "computer": ("Computer Use", 5),
    "credit": ("Credit Rating", 0),
    "cthulhu": ("Cthulhu Mythos", 0),
    "demolitions": ("Demolitions", 1),
    "disguise": ("Disguise", 5),
    "diving": ("Diving", 1),
    "dodge": ("Dodge", None),
    "drive": ("Drive Auto", 20),
    "elecrepair": ("Electrical Repair", 10),
    "fasttalk": ("Fast Talk", 5),
    "fighting": ("Fighting", 25),
    "firearms": ("Firearms", 20),
    "firstaid": ("First Aid", 30),
    "history": ("History", 5),
    "intimidate": ("Intimidate", 15),
    "jump": ("Jump", 20),
    "language": ("Language (Other)", 1),
    "ownlang": ("Language (Own)", None),
    "law": ("Law", 5),
    "library": ("Library Use", 20),
    "listen": ("Listen", 20),
    "locksmith": ("Locksmith", 1),
    "mechanical": ("Mechanical Repair", 10),
    "medicine": ("Medicine", 1),
    "naturalworld": ("Natural World", 10),
    "navigate": ("Navigate", 10),
    "occult": ("Occult", 5),
    "operateheavy": ("Operate Heavy Machinery", 1),
    "persuade": ("Persuade", 10),
    "pilot": ("Pilot", 1),
    "psychoanalysis": ("Psychoanalysis", 1),
    "psychology": ("Psychology", 10),
    "ride": ("Ride", 5),
    "science": ("Science", 1),
    "sleight": ("Sleight of Hand", 10),
    "spot": ("Spot Hidden", 25),
    "stealth": ("Stealth", 20),
    "survival": ("Survival", 10),
    "swim": ("Swim", 20),
    "throw": ("Throw", 20),
    "track": ("Track", 10),
    "hypnosis": ("Hypnosis", 1),
    "artillery": ("Artillery", 1),
    "electronics": ("Electronics", 1),
}

ALIASES = [
    (r"credit rating", "credit"),
    (r"cthulhu mythos", "cthulhu"),
    (r"operate heavy machin", "operateheavy"),
    (r"own language|language\s*\(own\)", "ownlang"),
    (r"^language\b|language\s*\(other\)|(other|foreign) language", "language"),
    (r"library use", "library"),
    (r"drive auto", "drive"),
    (r"electrical repair", "elecrepair"),
    (r"mechanical repair", "mechanical"),
    (r"operate heavy machinery", "operateheavy"),
    (r"first aid", "firstaid"),
    (r"natural world", "naturalworld"),
    (r"spot hidden", "spot"),
    (r"sleight of hand", "sleight"),
    (r"computer use", "computer"),
    (r"art/craft|^art\b|^craft\b|^art\s*\(", "art"),
    (r"electronics", "electronics"),
    (r"science|geology|biology|chemistry|pharmacy|forensics|physics|astronomy|zoology|mathematics", "science"),
    (r"pilot", "pilot"),
    (r"ride", "ride"),
    (r"psychoanalysis", "psychoanalysis"),
    (r"psychology", "psychology"),
    (r"hypnosis", "hypnosis"),
    (r"demolitions", "demolitions"),
    (r"artillery", "artillery"),
    (r"diving", "diving"),
    (r"dodge", "dodge"),
    (r"fighting", "fighting"),
    (r"firearms", "firearms"),
    (r"persuade", "persuade"),
    (r"intimidate", "intimidate"),
    (r"fast talk", "fasttalk"),
    (r"charm", "charm"),
    (r"disguise", "disguise"),
    (r"locksmith", "locksmith"),
    (r"listen", "listen"),
    (r"stealth", "stealth"),
    (r"survival", "survival"),
    (r"navigate", "navigate"),
    (r"occult", "occult"),
    (r"medicine", "medicine"),
    (r"climb", "climb"),
    (r"jump", "jump"),
    (r"swim", "swim"),
    (r"throw", "throw"),
    (r"track", "track"),
    (r"appraise", "appraise"),
    (r"archaeology", "archaeology"),
    (r"anthropology", "anthropology"),
    (r"accounting", "accounting"),
    (r"history", "history"),
    (r"\blaw\b", "law"),
]
NUMBERS = {"one": 1, "two": 2, "three": 3, "four": 4, "a": 1, "an": 1}


def base_id(text):
    t = text.lower().strip()
    for pat, sid in ALIASES:
        if re.search(pat, t):
            return sid
    return None


def split_top(s):
    parts, depth, cur = [], 0, []
    for ch in s:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        if ch == "," and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    parts.append("".join(cur))
    return [p.strip() for p in parts if p.strip()]


def top_or_split(s):
    parts, depth, cur = [], 0, []
    for ch in s:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        if ch in "/" and depth == 0:
            parts.append("".join(cur))
            cur = []
        elif s[0:0] == "" and depth == 0 and "".join(cur).lower().endswith(" or "):
            parts.append("".join(cur)[:-4])
            cur = []
        else:
            cur.append(ch)
    parts.append("".join(cur))
    return [p.strip() for p in parts if p.strip()]


def clean_segment(seg):
    seg = re.sub(r"\s+", " ", seg).strip()
    seg = re.sub(r"([A-Za-z])-\s+([a-z])", r"\1\2", seg)   # de-hyphenate line breaks
    seg = re.sub(r"[.;]+$", "", seg).strip()
    seg = re.sub(r"^and\s+", "", seg, flags=re.I)
    seg = re.sub(r"\s+as (a )?personal or era specialt.*$", "", seg, flags=re.I)
    seg = re.sub(r"\s+as (a )?personal or era.*$", "", seg, flags=re.I)
    seg = re.sub(r"^[-–—\s]+", "", seg).strip()
    return seg.strip()


IGNORE = {
    "and", "era", "however", "as a result", "testing", "miners", "lawyers",
    "magazine", "or personal specialties", "or era trade specialties",
    "or personal", "see alienist", "see above",
}


def count_word(seg):
    m = re.search(r"\b(one|two|three|four|a|an|\d+)\b", seg.lower())
    if not m:
        return 1
    tok = m.group(1)
    return int(tok) if tok.isdigit() else NUMBERS.get(tok, 1)


def parse_segment(seg):
    seg = clean_segment(seg)
    low = seg.lower()
    if not seg or low in IGNORE:
        return None
    if len(seg) < 3 or (seg.startswith("(") and not base_id(seg)):
        return None

    # "Language (Own or Other)"
    if "language" in low and "own" in low and "other" in low:
        return {"t": "pick", "n": 1, "from": ["ownlang", "language"], "label": seg}

    # "three fields of study and any two other skills..."
    if "fields of study" in low or (" and " in low and low.count("any") >= 1 and "other" in low):
        toks = []
        for part in re.split(r"\s+and\s+", seg):
            if "field" in part.lower():
                n = count_word(part)
                toks.append({"t": "any", "n": n, "label": part.strip()})
            elif "any" in part.lower() or "other" in part.lower():
                tok = parse_segment(part)
                if tok:
                    toks.append(tok)
        if toks:
            return toks

    # "any N other ..." / "N other skills ..." (but not "Other Language")
    if ("other" in low and ("skill" in low or "specialt" in low or "topic" in low
                            or re.search(r"other\s*$", low))) or low.startswith("any "):
        n = count_word(seg)
        return {"t": "any", "n": n, "label": seg}

    # "N interpersonal skills (...)"
    if "interpersonal" in low:
        n = count_word(seg)
        return {"t": "pick", "n": n,
                "from": ["charm", "fasttalk", "intimidate", "persuade"],
                "label": seg}

    # "two of First Aid/Mechanical Repair/Language (Other)"
    m = re.match(r"^(one|two|three|four|a|an|\d+)\s+of\s+(.*)$", low)
    if m:
        n = int(m.group(1)) if m.group(1).isdigit() else NUMBERS.get(m.group(1), 1)
        opts = [base_id(p) for p in re.split(r"[/,]", seg[m.end(1) - 1:]) if base_id(p)]
        opts = [o for o in opts if o]
        if opts:
            return {"t": "pick", "n": n, "from": opts, "label": seg}

    # top-level "or" / "/" choices -- but not compound names like Art/Craft
    if not re.match(r"^art\s*/\s*craft", low):
        opts = []
        for part in re.split(r"\s+or\s+|/", seg):
            sid = base_id(part)
            if sid and sid not in opts:
                opts.append(sid)
        if len(opts) > 1 and re.search(r"\s+or\s+|/", seg):
            n = count_word(seg) if re.match(r"^(one|two|a|an)\b", low) else 1
            if re.search(r"\s+or\s+", seg) is None and " of " not in low and n > 1:
                n = 1
            return {"t": "pick", "n": n, "from": opts, "label": seg}

    sid = base_id(seg)
    if sid:
        return {"t": "skill", "id": sid}
    return None


def parse_formula(points):
    s = re.sub(r"[xX×]\s*(?=\d)", "*", points)   # only multiplication signs
    s = re.sub(r"\s+", "", s).upper()
    m = re.search(r"EDU\*(\d+)", s)
    edu = int(m.group(1)) if m else 4
    add, choose = [], []
    groups = re.findall(r"\(([^)]*)\)", s)
    for group in groups:
        stats = [m.group(1) for m in re.finditer(r"(STR|DEX|APP|POW|INT|CON|SIZ)\*2", group)]
        if "OR" in group:
            choose.extend(stats)          # pick one of these
        else:
            add.extend(stats)             # all of these
    if not groups:
        for mm in re.finditer(r"\+(STR|DEX|APP|POW|INT|CON|SIZ)\*2", s[s.find("EDU"):]):
            add.append(mm.group(1))
    return {"edu": edu, "add": add, "choose": choose}


def parse_credit(cr):
    m = re.search(r"(\d+)\s*[–\-]\s*(\d+)", cr)
    lo, hi = (int(m.group(1)), int(m.group(2))) if m else (0, 0)
    note = re.sub(r"^\s*\d+\s*[–\-]\s*\d+\s*", "", cr).strip(" .")
    return [lo, hi], note


ERAS = {"classic": "classic", "modern": "modern", "lovecraftian": "lovecraftian"}


def normalize(entries):
    out = []
    seen = set()
    for e in entries:
        name = e["name"].strip()
        if "skills:" in name.lower() or not name[:1].isupper():
            continue                       # parser artifact
        era = ""
        for tag, val in ERAS.items():
            if f"[{tag}]".lower() in name.lower():
                era = val
                name = re.sub(rf"\s*\[{tag}\]\s*", "", name, flags=re.I).strip()
        skills = []
        for seg in split_top(e.get("skills") or ""):
            tok = parse_segment(seg)
            if isinstance(tok, list):
                skills.extend(tok)
            elif tok:
                skills.append(tok)
        credit, note = parse_credit(e.get("cr") or "")
        if (name, e.get("points")) in seen:
            continue
        seen.add((name, e.get("points")))
        out.append({
            "name": name,
            "era": era,
            "formula": parse_formula(e.get("points") or ""),
            "credit": credit,
            "credit_note": note,
            "skills": skills,
        })
    return out


def main():
    raw = json.loads((HERE / "occupations_raw.json").read_text(encoding="utf-8"))
    data = normalize(raw)
    (HERE / "occupations.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    (HERE / "skills.json").write_text(
        json.dumps(
            [{"id": k, "label": v[0], "base": v[1]} for k, v in SKILLS.items()],
            ensure_ascii=False, indent=1,
        ),
        encoding="utf-8",
    )
    print(f"{len(data)} occupations -> occupations.json; {len(SKILLS)} skills -> skills.json")


if __name__ == "__main__":
    main()