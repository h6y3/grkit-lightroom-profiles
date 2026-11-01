"""Render a synthetic test chart through every profile into one contact sheet PNG.

usage: contact_sheet.py PROFILES_DIR OUT_PNG

The chart (ColorChecker 24 reference colors, a hue sweep and a gray ramp) is generated, so the
sheet carries no third-party image. Tables are decoded from the .xmp files, so the sheet shows
what Lightroom receives, applied at Amount 100 to a display-referred sRGB image. In Lightroom the
table sees raw-processed data, so this is a guide to each look, not an exact preview.
"""
import sys
from pathlib import Path

import colour
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.interpolate import RegularGridInterpolator

sys.path.insert(0, str(Path(__file__).parent))
from cube2profile import read_profile  # noqa: E402

W, H, LABEL, COLS, PAD = 360, 240, 28, 4, 8
PP = colour.RGB_COLOURSPACES["ProPhoto RGB"]
SRGB = colour.RGB_COLOURSPACES["sRGB"]


def chart():
    img = np.zeros((H, W, 3))
    cc = colour.CCS_COLOURCHECKERS["ColorChecker24 - After November 2014"]
    xyz = colour.xyY_to_XYZ(np.array(list(cc.data.values())))
    rgb = np.clip(colour.XYZ_to_RGB(xyz, SRGB, cc.illuminant, chromatic_adaptation_transform="Bradford"), 0, 1)
    ph, pw = 150 // 4, W // 6
    for i, c in enumerate(rgb):
        r, k = divmod(i, 6)
        img[r * ph:(r + 1) * ph, k * pw:(k + 1) * pw] = c
    hue = colour.HSV_to_RGB(np.stack([np.linspace(0, 1, W), np.full(W, 0.6), np.full(W, 0.85)], -1))
    img[150:195] = colour.cctf_decoding(hue, function="sRGB")
    img[195:] = colour.cctf_decoding(np.linspace(0, 1, W), function="sRGB")[:, None]
    return img  # linear sRGB


def apply(lin_srgb, lut):
    pp = colour.RGB_to_RGB(lin_srgb, SRGB, PP, chromatic_adaptation_transform="Bradford")
    enc = np.clip(pp, 0, 1) ** (1 / 1.8)
    grid = (np.linspace(0, 1, lut.shape[0]),) * 3
    out = RegularGridInterpolator(grid, lut)(enc.reshape(-1, 3)).reshape(enc.shape)
    lin = colour.RGB_to_RGB(out ** 1.8, PP, SRGB, chromatic_adaptation_transform="Bradford")
    return lin


def to_image(lin):
    return Image.fromarray(np.round(colour.cctf_encoding(np.clip(lin, 0, 1), function="sRGB") * 255).astype(np.uint8))


profiles, out = Path(sys.argv[1]), Path(sys.argv[2])
base = chart()
tiles = [("Original", base)] + [(p.stem, apply(base, read_profile(p))) for p in sorted(profiles.glob("*.xmp"))]
rows = -(-len(tiles) // COLS)
sheet = Image.new("RGB", (COLS * (W + PAD) + PAD, rows * (H + LABEL + PAD) + PAD), (24, 24, 24))
draw = ImageDraw.Draw(sheet)
font = ImageFont.load_default(size=18)
for i, (name, lin) in enumerate(tiles):
    r, c = divmod(i, COLS)
    x, y = PAD + c * (W + PAD), PAD + r * (H + LABEL + PAD)
    sheet.paste(to_image(lin), (x, y))
    draw.text((x + 2, y + H + 4), name, fill=(230, 230, 230), font=font)
out.parent.mkdir(parents=True, exist_ok=True)
sheet.save(out, optimize=True)
print(f"wrote {out} ({len(tiles) - 1} looks)")
