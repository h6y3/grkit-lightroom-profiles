"""Convert the t3mujinpack HP5 Plus 400 HaldCLUT into a ProPhoto RGB (gamma 1.8) 32^3 .cube.

usage: bake_hp5_pp.py HALDCLUT_PNG OUT_DIR

The HaldCLUT maps display sRGB to display sRGB (it was made from a darktable style), so each
ProPhoto grid point goes ProPhoto -> sRGB (clipped) -> HaldCLUT -> ProPhoto. An input gain,
solved here by bisection, maps 18% gray to 18% gray like the other looks.
"""
import sys
from pathlib import Path

import colour
import numpy as np
from PIL import Image
from scipy.interpolate import RegularGridInterpolator

N = 32
PP = colour.RGB_COLOURSPACES["ProPhoto RGB"]
SRGB = colour.RGB_COLOURSPACES["sRGB"]

png, out = Path(sys.argv[1]), Path(sys.argv[2])
a = np.asarray(Image.open(png).convert("RGB"), dtype=np.float64) / 255
level = round((a.shape[0] * a.shape[1]) ** (1 / 3))
hald = a.reshape(level, level, level, 3).transpose(2, 1, 0, 3)  # [b][g][r] -> [r][g][b]
grid = (np.linspace(0, 1, level),) * 3
interp = RegularGridInterpolator(grid, hald)


def look(pp_enc, gain):
    lin = colour.RGB_to_RGB(pp_enc ** 1.8, PP, SRGB, chromatic_adaptation_transform="Bradford")
    srgb = colour.cctf_encoding(np.clip(lin * gain, 0, 1), function="sRGB")
    res = colour.cctf_decoding(interp(srgb.reshape(-1, 3)).reshape(srgb.shape), function="sRGB")
    pp = colour.RGB_to_RGB(res, SRGB, PP, chromatic_adaptation_transform="Bradford")
    return np.clip(pp, 0, 1) ** (1 / 1.8)


gray = np.full(3, 0.18 ** (1 / 1.8))
lo, hi = 0.25, 4.0
for _ in range(40):
    gain = (lo * hi) ** 0.5
    if look(gray, gain)[1] ** 1.8 > 0.18:
        hi = gain
    else:
        lo = gain

axis = np.linspace(0, 1, N)
r, g, b = np.meshgrid(axis, axis, axis, indexing="ij")
lut = look(np.stack([r, g, b], -1), gain)
rows = lut.transpose(2, 1, 0, 3).reshape(-1, 3)  # .cube order: red varies fastest
out.mkdir(parents=True, exist_ok=True)
body = "".join(f"{x:.6f} {y:.6f} {z:.6f}\n" for x, y, z in rows)
(out / "hp5-plus-400-mono-v1.cube").write_text(
    f'TITLE "hp5-plus-400-mono-v1"\nLUT_3D_SIZE {N}\nDOMAIN_MIN 0 0 0\nDOMAIN_MAX 1 1 1\n{body}'
)
print(f"hp5-plus-400-mono-v1.cube (input gain {gain:.4f})")
