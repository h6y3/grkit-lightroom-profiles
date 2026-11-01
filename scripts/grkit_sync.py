"""Keep this repo in step with a GRKit checkout (effects/NOTICE.md, effects/sources/manifest.json).

usage: grkit_sync.py pins GRKIT_DIR    print shell assignments for the library pins in GRKit's manifest
       grkit_sync.py check GRKIT_DIR   exit 1 if GRKit's recipes or catalog differ from ours
"""
import ast
import json
import sys
from pathlib import Path
from urllib.parse import quote

S = Path(__file__).resolve().parent
mode, grkit = sys.argv[1], Path(sys.argv[2])
SRC = grkit / "effects/sources"
manifest = json.loads((SRC / "manifest.json").read_text())
gens = manifest["generators"]


def assigned(path: Path, name: str):
    for node in ast.parse(path.read_text()).body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == name for t in node.targets):
            return ast.literal_eval(node.value)
    return None


if mode == "pins":
    for var, key in (("SF", "spektrafilm"), ("SFL", "spectral_film_lut"), ("T3M", "t3mujinpack")):
        print(f"{var}_REPO={gens[key]['repository']}")
        print(f"{var}_REV={gens[key]['revision']}")
    (hp5,) = [v["upstream"] for k, v in manifest["luts"].items() if v["generator"] == "t3mujinpack"]
    t3m = gens["t3mujinpack"]
    raw = t3m["repository"].replace("github.com", "raw.githubusercontent.com")
    print(f"T3M_URL='{raw}/{t3m['revision']}/{quote(hp5)}'")
    sys.exit()

problems = []
pairs = (
    ("bake_spektrafilm.py", "bake_sf_pp.py", ("RECIPES", "SCAN_LEVELS")),
    ("bake_spectral_film_lut.py", "bake_sfl_pp.py", ("RECIPES",)),
)
for theirs, ours, names in pairs:
    for name in names:
        a, b = assigned(SRC / theirs, name), assigned(S / ours, name)
        if a != b:
            problems.append(f"{name} in GRKit {theirs} differs from scripts/{ours}:\n  GRKit: {a}\n  ours:  {b}")

catalog = {Path(k).stem for k in manifest["luts"]}
named = set(assigned(S / "make_profiles.py", "NAMES"))
if catalog != named:
    problems.append(
        f"GRKit catalog vs make_profiles.py NAMES: missing {sorted(catalog - named)}, extra {sorted(named - catalog)}"
    )

if problems:
    sys.exit("GRKit has changed in ways that need porting by hand:\n" + "\n".join(problems))
print(f"GRKit recipes and catalog match ({len(catalog)} looks)")
