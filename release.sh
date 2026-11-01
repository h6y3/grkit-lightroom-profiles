#!/usr/bin/env bash
# Publish dist/grkit-lightroom-profiles.zip as a GitHub Release of the current commit.
#   ./release.sh [TAG]   TAG defaults to today's date, YYYY.MM.DD
# Run ./build.sh first and commit its tracked outputs (pins.env, docs/looks.png).
set -euo pipefail
cd "$(dirname "$0")"
source ./pins.env
TAG=${1:-$(date +%Y.%m.%d)}
ZIP=dist/grkit-lightroom-profiles.zip

[ -f $ZIP ] || { echo "Missing $ZIP; run ./build.sh" >&2; exit 1; }
[ -z "$(git status --porcelain)" ] || { echo "Commit or stash changes first; the release must match a commit." >&2; exit 1; }
[ $ZIP -nt pins.env ] || { echo "$ZIP is older than pins.env; run ./build.sh" >&2; exit 1; }
git fetch -q origin
[ "$(git rev-parse HEAD)" = "$(git rev-parse '@{u}')" ] || { echo "Push this commit first." >&2; exit 1; }

eval "$(python3 -I scripts/grkit_sync.py pins .cache/grkit)"
SF_VERSION=$(venv-sf/bin/python -c "import importlib.metadata as m; print(m.version('spektrafilm'))")
SFL_VERSION=$(venv-sfl/bin/python -c "import importlib.metadata as m; print(m.version('spectral_film_lut'))")
COUNT=$(unzip -Z1 $ZIP | grep -c '\.xmp$')

gh release create "$TAG" $ZIP --target "$(git rev-parse HEAD)" --title "$TAG" --notes "$(cat <<EOF
$COUNT Lightroom / Camera Raw profiles built from GRKit's film recipes.

| Source | Commit |
|---|---|
| GRKit | [\`${GRKIT_REV:0:7}\`]($GRKIT_REPO/tree/$GRKIT_REV) |
| spektrafilm $SF_VERSION | [\`${SF_REV:0:7}\`]($SF_REPO/tree/$SF_REV) |
| Spectral Film LUT $SFL_VERSION | [\`${SFL_REV:0:7}\`]($SFL_REPO/tree/$SFL_REV) |
| t3mujinpack | [\`${T3M_REV:0:7}\`]($T3M_REPO/tree/$T3M_REV) |

Import: Lightroom Classic Develop > Profile Browser > "+" > Import Profiles, and select the zip.
EOF
)"
