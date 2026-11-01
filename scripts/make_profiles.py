"""Wrap every baked LUT as a named Lightroom profile, then decode each profile to check it.

usage: make_profiles.py BUILD_PP_DIR OUT_DIR
Expects sf/ and t3m/ cubes in ProPhoto gamma 1.8 and sfl/ cubes in linear Rec.2020.
"""
import os
import sys
from pathlib import Path

import colour
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from cube2profile import read_cube, read_profile, write_profile  # noqa: E402

S = Path(sys.argv[1])
OUT = Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)

NAMES = {
    "portra-400-endura-v1": "Portra 400",
    "gold-200-premier-v1": "Gold 200",
    "ektar-100-edge-v1": "Ektar 100",
    "pro-400h-crystal-v1": "Pro 400H",
    "xtra-400-crystal-v1": "Superia X-TRA 400",
    "vision3-250d-2383-v1": "Vision3 250D",
    "vision3-500t-supra-v1": "Vision3 500T",
    "portra-800-push2-v1": "Portra 800 +2",
    "kodachrome-64-v1": "Kodachrome 64",
    "velvia-100-v1": "Velvia 100",
    "ektachrome-e100-v1": "Ektachrome E100",
    "trix-400-mono-v1": "Tri-X 400",
    "red-filter-mono-v1": "Tri-X 400 Red Filter",
    "aerocolor-iv-v1": "Aerocolor IV",
    "eterna-500t-3523xd-v1": "Eterna 500T",
    "instax-v1": "Instax",
    "double-x-5222-mono-v1": "Double-X 5222",
    "hp5-plus-400-mono-v1": "HP5 Plus 400",
}
SOURCES = {  # build subdirectory -> (profile group, copyright line)
    "sf": ("Film (spektrafilm)",
           f"LUT by spektrafilm {os.environ['SF_VERSION']}, Andrea Volpato, CC BY-SA 4.0. Free to use and share; no resale."),
    "sfl": ("Film (Spectral Film LUT)",
            f"LUT by Spectral Film LUT {os.environ['SFL_VERSION']}, Jan Lohse, MIT License."),
    "t3m": ("Film (t3mujinpack)", "Look from t3mujinpack, Joao Almeida, MIT License."),
}

PP = colour.RGB_COLOURSPACES["ProPhoto RGB"]
R2020 = colour.RGB_COLOURSPACES["ITU-R BT.2020"]


def rec2020lin_to_prophoto18(a):
    lin = colour.RGB_to_RGB(a, R2020, PP, chromatic_adaptation_transform="Bradford")
    return np.clip(lin, 0, 1) ** (1 / 1.8)


for kind, (group, notice) in SOURCES.items():
    for cube in sorted((S / kind).glob("*.cube")):
        lut = read_cube(cube)
        if kind == "sfl":
            lut = rec2020lin_to_prophoto18(lut)
        out = OUT / f"{NAMES[cube.stem]}.xmp"
        write_profile(lut, out, NAMES[cube.stem], group, notice)
        err = float(np.abs(read_profile(out) - np.clip(lut, 0, 1)).max())
        assert err <= 0.5 / 65535 + 1e-12, f"{out.name}: decoded table differs by {err}"
        print(f"{kind:3} {cube.stem:24} -> {out.name}")
