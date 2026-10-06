#!/usr/bin/env bash
# Build helpers for the CoC 7e player sheet.
# Usage: ./build/make.sh <step>
#   occ    - parse + normalize occupations -> build/occupations.json
#   parse  - only re-parse from the IH PDF   -> build/occupations_raw.json
#   norm   - only normalize                  -> build/occupations.json
#   sheet  - assemble ../coc7e-player-sheet.html
#   all    - occ then sheet
set -euo pipefail
cd "$(dirname "$0")"

step="${1:-occ}"

case "$step" in
    parse)
        python3 parse_occupations.py
        ;;
    norm)
        python3 normalize_occupations.py
        ;;
    occ)
        python3 parse_occupations.py
        python3 normalize_occupations.py
        ;;
    sheet)
        python3 build_sheet.py
        ;;
    all)
        python3 parse_occupations.py
        python3 normalize_occupations.py
        python3 build_sheet.py
        ;;
    *)
        echo "unknown step: $step" >&2
        exit 1
        ;;
esac