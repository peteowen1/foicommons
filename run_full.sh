#!/bin/bash
# Full archive run: harvest every log already in the registry, then a second discovery pass for agencies
# with no log found yet, reassemble the registry, and harvest the newly found logs. Resumable: just run it again.
cd /c/dev/foicommons
Rscript R/run_all.R
Rscript R/discover_fallback.R
Rscript R/build_registry.R
Rscript R/run_all.R
