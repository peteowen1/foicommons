#!/bin/bash
# Survey every agency log the harvest has marked COMPLETE (data/logs/harvest.log) into one file.
# Resumable: survey.py skips files already in the output, so rerun after the harvest finishes to pick up
# the remaining logs. Usage: ./scripts/survey_harvest.sh   (log: data/logs/survey_harvest.log)
cd /c/dev/foicommons
out=data/survey/survey_agencies.csv
grep -oE "\[[^]]+\] COMPLETE:" data/logs/harvest.log | sed -E 's/^\[([^]]+)\].*/\1/' | sort -u | while read -r slug; do
  m="data/manifest_${slug}.csv"
  [ -f "$m" ] || { echo "$(date +%T) no manifest for $slug"; continue; }
  echo "$(date +%T) [$slug] start"
  python -P scripts/survey.py "$m" "$out"
done
echo "$(date +%T) SURVEY DONE: $(($(wc -l < "$out") - 1)) files in $out"
