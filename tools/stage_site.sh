#!/usr/bin/env bash
# =============================================================================
# Stage the public site into a dist/ directory for upload to the static
# object-storage origins (AWS S3, Azure Blob static website).
#
# The output is the same file set the GCP nginx container serves: the rsync
# filter in tools/site-publish.filter mirrors nginx.conf's block rules and the
# Dockerfile strip list. Run AFTER tools/build_search_index.py so the freshly
# built search-index.json is included.
#
# Usage:  tools/stage_site.sh [DIST_DIR]   (default: ./dist)
# =============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST="${1:-$ROOT/dist}"

rm -rf "$DIST"
mkdir -p "$DIST"

rsync -a \
  --filter="merge $ROOT/tools/site-publish.filter" \
  "$ROOT/." "$DIST/"

count=$(find "$DIST" -type f | wc -l | tr -d ' ')
echo "Staged $count files into $DIST"

# Fail loudly if a sensitive pattern slipped through - the publish step uploads
# this directory verbatim, so a leak here is a public leak.
if find "$DIST" \( -name '.env*' -o -name '*.pem' -o -name '*.key' -o -name '*.crt' -o -name '*.py' \) -print -quit | grep -q .; then
  echo "ERROR: sensitive file(s) present in staged dist/ - refusing to publish." >&2
  find "$DIST" \( -name '.env*' -o -name '*.pem' -o -name '*.key' -o -name '*.crt' -o -name '*.py' \) >&2
  exit 1
fi

# Sanity floor: a healthy build is hundreds of HTML pages + assets. A near-empty
# dist/ means something upstream broke; don't publish a hollow site.
if [ "$count" -lt 100 ]; then
  echo "ERROR: only $count files staged - expected hundreds. Aborting." >&2
  exit 1
fi
