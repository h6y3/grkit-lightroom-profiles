# Adapted from GRKit effects/sources/bake_spectral_film_lut.py (MIT, github.com/ahonn/GRKit).
# Changes: ProPhoto RGB in/out, 32^3, per-film exposure overrides via env.
"""Bake GRKit's Spectral Film LUT recipes for Lightroom.

usage: bake_sfl_pp.py OUT_DIR   (spectral_film_lut at the commit GRKit's manifest pins, Python 3.13)

Writes OUT_DIR/<effect-id>.cube: ProPhoto RGB in, linear Rec.2020 out, 32^3. make_profiles.py
converts the output to ProPhoto gamma 1.8. RECIPES must match GRKit's (grkit_sync.py checks it).
It calls the library without its GUI and passes the GUI default for each setting, except the
color spaces and exposure. Instant films have no print stock; their projection balances mid gray.
A Wratten filter multiplies the film sensitivity by the filter transmission. The library then
normalizes exposure on mid gray, as a meter behind the filter does.
Env: SFL_EXP (JSON effect-id -> exposure compensation in stops), SFL_ONLY (comma-separated ids).
"""

import copy
import json
import os
import sys
from pathlib import Path

from spectral_film_lut.film_loader import load_filmstocks
from spectral_film_lut.utils import create_lut
from spectral_film_lut.wratten_filters import WRATTEN

EXP = json.loads(os.environ.get("SFL_EXP", "{}"))
ONLY = os.environ.get("SFL_ONLY")

# effect ID -> (negative or instant film, print stock or None, slide white-balance mode,
# Wratten filter or None)
RECIPES = {
    "trix-400-mono-v1": ("Kodak Tri-X 400", "Kodak Polymax Fine-Art Paper Grade 2", 0, None),
    "red-filter-mono-v1": ("Kodak Tri-X 400", "Kodak Polymax Fine-Art Paper Grade 2", 0, "25"),
    "aerocolor-iv-v1": ("Kodak Aerocolor IV 2460", "Kodak Portra Endura Paper", 0, None),
    "eterna-500t-3523xd-v1": ("Fuji Eterna 500", "Fuji Eterna-CP 3523XD", 0, None),
    "instax-v1": ("Fuji Instax color", None, 1, None),
    "double-x-5222-mono-v1": ("Kodak 5222 Dev 12", "Kodak Polymax Fine-Art Paper Grade 3", 0, None),
}


def bake(
    stocks, effect_id: str, film: str, paper: str | None, balance: int, wratten: str | None
) -> None:
    """Write <effect-id>.cube in the working directory. The file title is the effect ID."""
    negative = stocks[film]
    if wratten:
        negative = copy.deepcopy(negative)
        negative.sensitivity = negative.sensitivity * WRATTEN[wratten].reshape(-1, 1)
    create_lut(
        negative,
        stocks[paper] if paper else None,
        name=effect_id,
        lut_size=32,
        cube=True,
        input_colorspace="ProPhoto RGB",
        output_gamut="Rec. 2020",
        gamma_func="Linear",
        projector_kelvin=6500,
        exp_comp=EXP.get(effect_id, 0.0),
        white_clip=False,
        white_balance=balance,
        exp_kelvin=6500,
        mode="full",
        color_masking=negative.color_masking,
        apd_intermediate=True,
        reference_negative=stocks["Kodak Vision3 250D 5207"],
        upsampling_method="SFL upsampling",
    )


if __name__ == "__main__":
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    stocks = load_filmstocks(lambda *args: None)
    os.chdir(out)
    for effect_id, (film, paper, balance, wratten) in RECIPES.items():
        if ONLY and effect_id not in ONLY.split(","): continue
        bake(stocks, effect_id, film, paper, balance, wratten)
        print(f"{effect_id}.cube")
