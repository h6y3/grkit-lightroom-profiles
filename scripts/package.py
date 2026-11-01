"""Write dist/grkit-lightroom-profiles.zip from build/profiles.

usage: package.py REPO_DIR   (versions and revisions come from the environment set by build.sh)
Zip entries use a fixed timestamp and order, so an unchanged build gives a byte-identical zip.
"""
import os
import sys
import zipfile
from pathlib import Path

R = Path(sys.argv[1])
E = os.environ
SF, SFL = f"{E['SF_VERSION']} (git {E['SF_REV'][:7]})", f"{E['SFL_VERSION']} (git {E['SFL_REV'][:7]})"
LIC = R / "licenses"
TOP = "GRKit Film Profiles/"

README = f"""GRKit film looks as Lightroom / Camera Raw creative profiles ({{n}} profiles)

Unofficial. Built from the film recipes of GRKit (github.com/ahonn/GRKit, git {E['GRKIT_REV'][:7]}).
Not affiliated with GRKit, Adobe, Kodak, Fujifilm, or Ilford.

Install
- Lightroom Classic: Develop > Profile Browser > "+" > Import Profiles, select this zip or the .xmp files.
- Lightroom (cloud/desktop): File > Import Profiles & Presets.
- Camera Raw: Presets panel > "..." > Import Profiles & Presets.
They appear in three groups: "Film (spektrafilm)", "Film (Spectral Film LUT)" and "Film (t3mujinpack)".

Use
- Set exposure first. Each profile maps 18% gray to 18% gray, so a well-exposed image keeps its brightness.
- Selecting one replaces your current profile (Lightroom applies one profile at a time).
- The Amount slider runs 0-200. Start near 50-70; the film contrast is strong.
- B&W films (Tri-X, Tri-X Red Filter, Double-X, HP5) output neutral gray but leave Treatment set to Color.
- No grain or halation. Add grain with Lightroom's Effects > Grain.

How they were made
- Same film/print recipes as GRKit's effects/sources, rebaked for Lightroom:
  input and output ProPhoto RGB gamma 1.8, 32^3 table, embedded in the profile.
- spektrafilm {SF}: source white placed at native scale (+2.47 stops).
- Spectral Film LUT {SFL}: per-film exposure offset so 18% gray maps to 18% gray.
- t3mujinpack (git {E['T3M_REV'][:7]}): HP5 Plus 400 HaldCLUT (sRGB), converted to ProPhoto with a gain
  that maps 18% gray to 18% gray.

Licenses (see licenses/)
- spektrafilm looks: CC BY-SA 4.0, Andrea Volpato; LUT terms allow use and sharing, no resale.
- Spectral Film LUT looks: MIT, Jan Lohse.
- HP5 Plus 400: MIT, Joao Almeida.
Film names identify simulated materials and may be trademarks of their owners.
"""

xmps = sorted((R / "build/profiles").glob("*.xmp"))
entries = {TOP + p.name: p.read_bytes() for p in xmps}
for name in ("SPEKTRAFILM", "SPECTRAL_FILM_LUT", "T3MUJINPACK"):
    entries[f"{TOP}licenses/{name}_LICENSE.txt"] = (LIC / f"{name}_LICENSE.txt").read_bytes()
entries[TOP + "README.txt"] = README.format(n=len(xmps)).encode()

out = R / "dist/grkit-lightroom-profiles.zip"
out.parent.mkdir(exist_ok=True)
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    for name in sorted(entries | {TOP: b"", TOP + "licenses/": b""}):
        info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
        info.external_attr = (0o40755 if name.endswith("/") else 0o100644) << 16
        info.compress_type = zipfile.ZIP_DEFLATED
        z.writestr(info, entries.get(name, b""))
print(f"wrote {out.relative_to(R)} ({len(xmps)} profiles)")
