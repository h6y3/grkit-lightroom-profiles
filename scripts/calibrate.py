"""Find, per effect, the exposure setting that maps 18% gray in to 18% gray out.

usage: calibrate.py sf|sfl EFFECT_ID WORKDIR
Prints: EFFECT_ID VALUE GRAY_OUT_STOPS
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
from scipy.interpolate import RegularGridInterpolator

S = Path(__file__).resolve().parent.parent
kind, eid, work = sys.argv[1], sys.argv[2], Path(sys.argv[3]).resolve()
work.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(S / "scripts"))
from cube2profile import read_cube  # noqa: E402

E_GRAY = 0.18 ** (1 / 1.8)


def gray_out(v):
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", MPLBACKEND="Agg")
    if kind == "sf":
        env.update(SF_ONLY=eid, SF_STOPS=json.dumps({eid: v}))
        cmd = [str(S / "venv-sf/bin/python"), "-I", str(S / "scripts/bake_sf_pp.py"), str(work)]
        cwd = work
    else:
        env.update(SFL_ONLY=eid, SFL_EXP=json.dumps({eid: v}))
        cmd = [str(S / "venv-sfl/bin/python"), "-I", str(S / "scripts/bake_sfl_pp.py"), str(work)]
        cwd = work
    subprocess.run(cmd, env=env, cwd=cwd, check=True, capture_output=True)
    lut = read_cube(work / f"{eid}.cube")
    if kind == "sfl":  # linear Rec.2020 output; gray is neutral so luminance ~ G
        lin = float(RegularGridInterpolator((np.linspace(0, 1, 32),) * 3, lut[..., 1])([[E_GRAY] * 3])[0])
    else:
        enc = float(RegularGridInterpolator((np.linspace(0, 1, 32),) * 3, lut[..., 1])([[E_GRAY] * 3])[0])
        lin = enc ** 1.8
    return np.log2(max(lin, 1e-6) / 0.18)


# sf: value = stops_above_midgray (native 2.47); higher -> brighter.
# sfl: value = exp_comp in stops (native 0); higher -> brighter.
lo, hi = (-3.0, 5.0) if kind == "sf" else (-4.0, 4.0)
glo, ghi = gray_out(lo), gray_out(hi)
for _ in range(9):
    mid = (lo + hi) / 2
    g = gray_out(mid)
    if abs(g) < 0.03:
        break
    if g > 0:
        hi = mid
    else:
        lo = mid
print(eid, round(mid, 4), round(g, 3), round(glo, 2), round(ghi, 2), flush=True)
