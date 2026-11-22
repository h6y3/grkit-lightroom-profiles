"""Convert display-sRGB looks into ProPhoto RGB (gamma 1.8) 32^3 .cube files.

usage: bake_display_pp.py OUT_DIR EFFECT_ID=SOURCE [EFFECT_ID=SOURCE ...]

SOURCE is a HaldCLUT .png (t3mujinpack, made from a darktable style) or a .cube (the G'MIC Film
LUTs Collection). Both map display sRGB to display sRGB, so each ProPhoto grid point goes
ProPhoto -> sRGB (clipped) -> look -> ProPhoto. An input gain, solved here by bisection, maps
18% gray to 18% gray like the other looks.
"""
import sys
from pathlib import Path

import colour
import numpy as np
from PIL import Image
from scipy.interpolate import RegularGridInterpolator

sys.path.insert(0, str(Path(__file__).parent))
from cube2profile import read_cube  # noqa: E402

N = 32
PP = colour.RGB_COLOURSPACES["ProPhoto RGB"]
SRGB = colour.RGB_COLOURSPACES["sRGB"]


def load(src: Path):
    if src.suffix == ".cube":
        return read_cube(src)
    a = np.asarray(Image.open(src).convert("RGB"), dtype=np.float64) / 255
    level = round((a.shape[0] * a.shape[1]) ** (1 / 3))
    return a.reshape(level, level, level, 3).transpose(2, 1, 0, 3)  # [b][g][r] -> [r][g][b]


def bake(table):
    interp = RegularGridInterpolator((np.linspace(0, 1, table.shape[0]),) * 3, table)

    def look(pp_enc, gain):
        lin = colour.RGB_to_RGB(pp_enc ** 1.8, PP, SRGB, chromatic_adaptation_transform="Bradford")
        srgb = colour.cctf_encoding(np.clip(lin * gain, 0, 1), function="sRGB")
        res = colour.cctf_decoding(np.clip(interp(srgb.reshape(-1, 3)), 0, 1).reshape(srgb.shape), function="sRGB")
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
    return look(np.stack([r, g, b], -1), gain), gain


out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
for arg in sys.argv[2:]:
    eid, src = arg.split("=", 1)
    lut, gain = bake(load(Path(src)))
    rows = lut.transpose(2, 1, 0, 3).reshape(-1, 3)  # .cube order: red varies fastest
    body = "".join(f"{x:.6f} {y:.6f} {z:.6f}\n" for x, y, z in rows)
    (out / f"{eid}.cube").write_text(f'TITLE "{eid}"\nLUT_3D_SIZE {N}\nDOMAIN_MIN 0 0 0\nDOMAIN_MAX 1 1 1\n{body}')
    print(f"{eid}.cube (input gain {gain:.4f})")
