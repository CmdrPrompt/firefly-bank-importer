#!/usr/bin/env bash
# Kör firefly-import upprepade gånger, en månad i taget, från <start> till <slut>.
#
# Användning:
#   scripts/import-months.sh <START ÅÅÅÅ-MM> <SLUT ÅÅÅÅ-MM> <sökväg> [extra flaggor...]
#
# Exempel:
#   scripts/import-months.sh 2025-01 2025-06 ./import-data
#   scripts/import-months.sh 2025-01 2025-06 ./import-data --dry-run

set -euo pipefail

if [ "$#" -lt 3 ]; then
    echo "Användning: $0 <START ÅÅÅÅ-MM> <SLUT ÅÅÅÅ-MM> <sökväg> [extra flaggor...]" >&2
    exit 1
fi

start="$1"
end="$2"
folder="$3"
shift 3
extra_args=("$@")

period_re='^[0-9]{4}-(0[1-9]|1[0-2])$'

for value in "$start" "$end"; do
    if ! [[ "$value" =~ $period_re ]]; then
        echo "Ogiltigt period-värde: '$value'. Ange formatet ÅÅÅÅ-MM (t.ex. 2025-06)." >&2
        exit 1
    fi
done

start_year="${start%-*}"
start_month="${start#*-}"
end_year="${end%-*}"
end_month="${end#*-}"

# Ta bort ev. inledande nolla så bash inte tolkar månaden som oktalt tal.
start_month=$((10#$start_month))
end_month=$((10#$end_month))

start_total=$((10#$start_year * 12 + start_month))
end_total=$((10#$end_year * 12 + end_month))

if [ "$start_total" -gt "$end_total" ]; then
    echo "Startmånad ($start) kan inte vara efter slutmånad ($end)." >&2
    exit 1
fi

for ((total = start_total; total <= end_total; total++)); do
    year=$((total / 12))
    month=$((total % 12))
    if [ "$month" -eq 0 ]; then
        year=$((year - 1))
        month=12
    fi
    period=$(printf "%04d-%02d" "$year" "$month")

    echo "=== Importerar period $period ==="
    uv run firefly-import "$folder" --period "$period" "${extra_args[@]}"
done

echo "Klart. Importerade perioder $start till $end."
