"""Wrap a ProPhoto-RGB (gamma 1.8) 3D .cube LUT as a Lightroom / Camera Raw creative profile (.xmp).

The table format follows the Adobe DNG SDK (source/dng_big_table.cpp, version 1.7.1):
dng_rgb_table::PutStream binary -> 4-byte size + zlib (EncodeAsBinary) -> base85 (EncodeAsString).
"""
import hashlib
import re
import struct
import sys
import uuid
import zlib
from pathlib import Path

import numpy as np

# kEncodeTable from dng_big_table::EncodeAsString: Z85-like, with characters chosen to be safe in XMP.
_ENC = (
    "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    ".-:+=^!/*?`'|()[]{}@%$#"
)
_DEC = {c: i for i, c in enumerate(_ENC)}
assert len(_ENC) == 85 == len(_DEC) and not set(_ENC) & set('"<>&')

# dng_rgb_table enums: btt_RGBTable, kRGBTableVersion, primaries_ProPhoto, gamma_1_8, gamut_clip.
_TABLE_TYPE, _TABLE_VERSION, _PROPHOTO, _GAMMA_1_8, _GAMUT_CLIP = 1, 1, 2, 2, 0


def b85(data: bytes) -> str:
    # Little-endian groups of 4 bytes -> 5 digits, least significant first; a tail of k bytes -> k+1 digits.
    out = []
    for i in range(0, len(data), 4):
        chunk = data[i:i + 4]
        v = int.from_bytes(chunk.ljust(4, b"\0"), "little")
        for _ in range(len(chunk) + 1):
            out.append(_ENC[v % 85])
            v //= 85
    return "".join(out)


def unb85(text: str) -> bytes:
    out = bytearray()
    for i in range(0, len(text), 5):
        digits = text[i:i + 5]
        v = sum(_DEC[c] * 85 ** k for k, c in enumerate(digits))
        out += (v & 0xFFFFFFFF).to_bytes(4, "little")[:len(digits) - 1]
    return bytes(out)


def read_cube(path):
    n, rows = None, []
    for line in Path(path).read_text().splitlines():
        s = line.strip()
        if s.startswith("LUT_3D_SIZE"):
            n = int(s.split()[1])
        elif s and (s[0].isdigit() or s[0] in "-."):
            p = s.split()
            if len(p) == 3:
                rows.append([float(x) for x in p])
    a = np.array(rows).reshape(n, n, n, 3)  # [b][g][r] since red varies fastest
    return a.transpose(2, 1, 0, 3)          # -> [r][g][b]


def _identity(n):
    # Samples are stored as deltas from the identity ("nop") table.
    nop = np.array([(i * 0xFFFF + (n >> 1)) // (n - 1) for i in range(n)], dtype=np.int64)
    return np.stack(np.meshgrid(nop, nop, nop, indexing="ij"), -1)


def table_bytes(lut):  # lut[r][g][b] -> rgb in [0,1], ProPhoto / 1.8
    n = lut.shape[0]
    q = np.round(np.clip(lut, 0, 1) * 65535).astype(np.int64)
    d = (q - _identity(n)) & 0xFFFF
    body = struct.pack("<4I", _TABLE_TYPE, _TABLE_VERSION, 3, n) + d.astype("<u2").tobytes()
    # Amount slider range 0..2 (0-200%).
    return body + struct.pack("<3I2d", _PROPHOTO, _GAMMA_1_8, _GAMUT_CLIP, 0.0, 2.0)


def read_profile(path):
    """Decode the RGB table of a profile written by write_profile -> lut[r][g][b] in [0,1]."""
    text = Path(path).read_text(encoding="utf-8")
    fp = re.search(r'crs:RGBTable="(\w+)"', text).group(1)
    enc = re.search(rf'crs:Table_{fp}="([^"]+)"', text).group(1)
    packed = unb85(enc)
    raw = zlib.decompress(packed[4:])
    assert struct.unpack_from("<I", packed)[0] == len(raw)
    assert hashlib.md5(raw).hexdigest().upper() == fp
    kind, version, dims, n = struct.unpack_from("<4I", raw)
    assert (kind, version, dims) == (_TABLE_TYPE, _TABLE_VERSION, 3)
    d = np.frombuffer(raw, "<u2", n ** 3 * 3, 16).astype(np.int64).reshape(n, n, n, 3)
    return ((d + _identity(n)) & 0xFFFF) / 65535


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;")


def alt(tag, text):
    return (f"   <crs:{tag}>\n    <rdf:Alt>\n     <rdf:li xml:lang=\"x-default\">{esc(text)}</rdf:li>\n"
            f"    </rdf:Alt>\n   </crs:{tag}>\n")


def write_profile(lut, out, name, group, copyright_, mono=False):
    raw = table_bytes(lut)
    fp = hashlib.md5(raw).hexdigest().upper()
    enc = b85(struct.pack("<I", len(raw)) + zlib.compress(raw, 9))
    uid = uuid.uuid5(uuid.NAMESPACE_URL, "grkit-lr/" + name).hex.upper()
    xmp = f'''<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="Adobe XMP Core 7.0-c000 1.000000, 0000/00/00-00:00:00        ">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about=""
    xmlns:crs="http://ns.adobe.com/camera-raw-settings/1.0/"
   crs:PresetType="Look"
   crs:Cluster=""
   crs:UUID="{uid}"
   crs:SupportsAmount="True"
   crs:SupportsColor="True"
   crs:SupportsMonochrome="True"
   crs:SupportsHighDynamicRange="True"
   crs:SupportsNormalDynamicRange="True"
   crs:SupportsSceneReferred="True"
   crs:SupportsOutputReferred="True"
   crs:CameraModelRestriction=""
   crs:Copyright="{esc(copyright_)}"
   crs:ContactInfo=""
   crs:Version="15.0"
   crs:ProcessVersion="11.0"
   crs:ConvertToGrayscale="{'True' if mono else 'False'}"
   crs:RGBTable="{fp}"
   crs:Table_{fp}="{enc}"
   crs:HasSettings="True">
{alt("Name", name)}{alt("ShortName", name)}{alt("SortName", name)}{alt("Group", group)}  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>
'''
    Path(out).write_text(xmp, encoding="utf-8")
