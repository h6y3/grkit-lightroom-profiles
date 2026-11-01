#!/usr/bin/env bash
# Rebuild the Lightroom profiles from the GRKit commit in pins.env and the library commits GRKit's
# manifest names: bake ProPhoto LUTs -> wrap as profiles -> check mid gray -> contact sheet -> zip.
# Requires: uv, git, curl. uv fetches Python 3.13 if missing. Takes about a minute after the first run.
set -euo pipefail
cd "$(dirname "$0")"
R=$PWD
source ./pins.env
export QT_QPA_PLATFORM=offscreen MPLBACKEND=Agg
CACHE=$R/.cache
mkdir -p "$CACHE"

# A venv is rebuilt whenever its pinned commit changes.
venv() {
  local dir=$R/$1 spec="git+$2@$3"
  [ "$(cat "$dir/.pin" 2>/dev/null)" = "$spec" ] && return
  echo "Installing $spec"
  rm -rf "$dir"
  uv venv -q -p 3.13 "$dir"
  VIRTUAL_ENV=$dir uv pip install -q "$spec"
  echo "$spec" > "$dir/.pin"
}

# Check out one commit of a git repo into the cache, fetching only that commit.
checkout() {
  local dir=$CACHE/$1
  [ -d "$dir/.git" ] || git init -q "$dir"
  if [ "$(git -C "$dir" rev-parse -q --verify HEAD 2>/dev/null)" != "$3" ]; then
    git -C "$dir" fetch -q --depth 1 "$2" "$3"
    git -C "$dir" checkout -q --detach FETCH_HEAD
  fi
}

checkout grkit "$GRKIT_REPO" "$GRKIT_REV"
eval "$(python3 -I scripts/grkit_sync.py pins "$CACHE/grkit")"
python3 -I scripts/grkit_sync.py check "$CACHE/grkit"
venv venv-sf "$SF_REPO" "$SF_REV"
venv venv-sfl "$SFL_REPO" "$SFL_REV"
HP5=$CACHE/hp5-$T3M_REV.png
[ -f "$HP5" ] || curl -fsSL -o "$HP5" "$T3M_URL"

export SF_VERSION=$(venv-sf/bin/python -c "import importlib.metadata as m; print(m.version('spektrafilm'))")
export SFL_VERSION=$(venv-sfl/bin/python -c "import importlib.metadata as m; print(m.version('spectral_film_lut'))")
export SF_REV SFL_REV GRKIT_REV T3M_REV

# Exposure: spektrafilm source white at +2.47 stops (gain 1.0; the 0.3.4 default is ~1.5 stops bright
# for ProPhoto input). Spectral Film LUT offsets came from scripts/calibrate.py (18% gray -> 18% gray).
SF_FILMS="portra-400-endura-v1 gold-200-premier-v1 ektar-100-edge-v1 pro-400h-crystal-v1 xtra-400-crystal-v1
vision3-250d-2383-v1 vision3-500t-supra-v1 portra-800-push2-v1 kodachrome-64-v1 velvia-100-v1 ektachrome-e100-v1"
export SF_STOPS=$(python3 -c "import json,sys;print(json.dumps({k:'2.47' for k in sys.argv[1:]}))" $SF_FILMS)
export SFL_EXP='{"trix-400-mono-v1":0.8125,"red-filter-mono-v1":0.4688,"aerocolor-iv-v1":0.0938,
"eterna-500t-3523xd-v1":0.0625,"instax-v1":-0.5625,"double-x-5222-mono-v1":0.5312}'

rm -rf build && mkdir -p build/pp/sf build/pp/sfl build/pp/t3m build/profiles
venv-sf/bin/python -I scripts/bake_sf_pp.py "$R/build/pp/sf"
(cd build/pp/sfl && "$R/venv-sfl/bin/python" -I "$R/scripts/bake_sfl_pp.py" "$R/build/pp/sfl")
venv-sfl/bin/python -I scripts/bake_hp5_pp.py "$HP5" "$R/build/pp/t3m"
venv-sfl/bin/python -I scripts/make_profiles.py "$R/build/pp" "$R/build/profiles"
venv-sfl/bin/python -I scripts/check_gray.py "$R/build/pp"
venv-sfl/bin/python -I scripts/contact_sheet.py "$R/build/profiles" "$R/docs/looks.png"
python3 -I scripts/package.py "$R"
echo "Done: dist/grkit-lightroom-profiles.zip. Publish with ./release.sh"
