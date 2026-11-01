"""Fail if any baked ProPhoto LUT moves 18% gray more than TOLERANCE stops away from 18% gray.

usage: check_gray.py BUILD_PP_DIR   (sf/ and t3m/ cubes in ProPhoto gamma 1.8, sfl/ cubes in linear Rec.2020)
An upstream update that trips this needs new exposure offsets from scripts/calibrate.py.
"""
import sys
from pathlib import Path

import numpy as np
from scipy.interpolate import RegularGridInterpolator

sys.path.insert(0, str(Path(__file__).parent))
from cube2profile import read_cube  # noqa: E402

TOLERANCE = 0.25
E_GRAY = 0.18 ** (1 / 1.8)

bad = []
for kind in ("sf", "sfl", "t3m"):
    for cube in sorted((Path(sys.argv[1]) / kind).glob("*.cube")):
        lut = read_cube(cube)
        grid = (np.linspace(0, 1, lut.shape[0]),) * 3
        g = float(RegularGridInterpolator(grid, lut[..., 1])([[E_GRAY] * 3])[0])
        lin = g if kind == "sfl" else g ** 1.8
        stops = float(np.log2(max(lin, 1e-6) / 0.18))
        flag = abs(stops) > TOLERANCE
        print(f"gray {kind:3} {cube.stem:24} {stops:+.3f} stops{'  OUT OF TOLERANCE' if flag else ''}")
        if flag:
            bad.append(cube.stem)
if bad:
    sys.exit(f"Mid gray off by more than {TOLERANCE} stops for: {', '.join(bad)}. Recalibrate with scripts/calibrate.py.")
