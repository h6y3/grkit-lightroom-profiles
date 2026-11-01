#!/usr/bin/env bash
# Follow GRKit, which owns the film formulas (effects/NOTICE.md, effects/sources/).
#   ./update.sh          report what changed in GRKit since the pinned commit
#   ./update.sh --apply  bump GRKIT_REV in pins.env and run build.sh
# Library commits follow GRKit's manifest, so bumping GRKit is the only update step.
# After --apply, review `git diff` (pins.env, dist/) and commit.
set -euo pipefail
cd "$(dirname "$0")"
source ./pins.env
D=.cache/grkit

[ -d $D/.git ] || git init -q $D
NEW=$(git ls-remote "$GRKIT_REPO" HEAD | cut -f1)
git -C $D fetch -q --depth 200 "$GRKIT_REPO" "$NEW" "$GRKIT_REV"

if [ "$NEW" = "$GRKIT_REV" ]; then
  echo "GRKit: up to date (${GRKIT_REV:0:7})"
else
  echo "GRKit: ${GRKIT_REV:0:7} -> ${NEW:0:7}  $GRKIT_REPO/compare/$GRKIT_REV...$NEW"
  if git -C $D diff --quiet "$GRKIT_REV" "$NEW" -- effects/NOTICE.md effects/sources; then
    echo "    No changes to effects/NOTICE.md or effects/sources; the profiles would not change."
  else
    echo "    GRKit effects changed:"
    git -C $D diff --stat "$GRKIT_REV" "$NEW" -- effects/NOTICE.md effects/sources | sed 's/^/    /'
  fi
  git -C $D diff "$GRKIT_REV" "$NEW" -- effects/sources/manifest.json | grep -E '^[-+] *"(revision|version)"' | sed 's/^/    /' || true
  # Fails if GRKit changed recipes or added/removed looks; port those into scripts/ before applying.
  git -C $D checkout -q --detach "$NEW"
  python3 -I scripts/grkit_sync.py check $D
fi

# Informational: library commits newer than the ones GRKit has adopted.
git -C $D checkout -q --detach "$NEW"
eval "$(python3 -I scripts/grkit_sync.py pins $D)"
for lib in SF SFL T3M; do
  repo=${lib}_REPO rev=${lib}_REV
  head=$(git ls-remote "${!repo}" HEAD | cut -f1)
  [ "$head" = "${!rev}" ] || echo "note: ${!repo} HEAD ${head:0:7} is newer than GRKit's pin ${!rev:0:7}"
done

if [ "$NEW" != "$GRKIT_REV" ]; then
  if [ "${1:-}" = --apply ]; then
    perl -pi -e "s/^GRKIT_REV=.*/GRKIT_REV=$NEW/" pins.env
    ./build.sh
  else
    echo "Run ./update.sh --apply to bump pins.env and rebuild."
  fi
fi
