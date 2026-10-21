"""Convert a UniSHARP Gaussian PLY to a standard RGB point-cloud PLY.

UniSHARP stores the DC spherical-harmonic coefficients as ``f_dc_0..2``.
This script evaluates those coefficients and writes Blender-friendly ``red``,
``green`` and ``blue`` vertex properties.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np


SH_C0 = 0.28209479177387814
INPUT_DTYPE = np.dtype(
    [
        ("x", "<f4"),
        ("y", "<f4"),
        ("z", "<f4"),
        ("f_dc_0", "<f4"),
        ("f_dc_1", "<f4"),
        ("f_dc_2", "<f4"),
        ("opacity", "<f4"),
        ("scale_0", "<f4"),
        ("scale_1", "<f4"),
        ("scale_2", "<f4"),
        ("rot_0", "<f4"),
        ("rot_1", "<f4"),
        ("rot_2", "<f4"),
        ("rot_3", "<f4"),
    ]
)
OUTPUT_DTYPE = np.dtype(
    [
        ("x", "<f4"),
        ("y", "<f4"),
        ("z", "<f4"),
        ("red", "u1"),
        ("green", "u1"),
        ("blue", "u1"),
    ]
)


def read_header(path: Path) -> tuple[int, int]:
    vertex_count: int | None = None
    with path.open("rb") as stream:
        while True:
            line = stream.readline()
            if not line:
                raise ValueError("PLY header ended unexpectedly.")
            decoded = line.decode("ascii").strip()
            if decoded.startswith("element vertex "):
                vertex_count = int(decoded.rsplit(" ", 1)[1])
            if decoded == "end_header":
                break
        offset = stream.tell()
    if vertex_count is None:
        raise ValueError("PLY has no vertex element.")
    return vertex_count, offset


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--chunk-size", type=int, default=262_144)
    args = parser.parse_args()

    count, offset = read_header(args.input)
    source = np.memmap(args.input, dtype=INPUT_DTYPE, mode="r", offset=offset, shape=(count,))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    header = (
        "ply\n"
        "format binary_little_endian 1.0\n"
        "comment UniSHARP SH-DC colors converted to RGB\n"
        f"element vertex {count}\n"
        "property float x\n"
        "property float y\n"
        "property float z\n"
        "property uchar red\n"
        "property uchar green\n"
        "property uchar blue\n"
        "end_header\n"
    ).encode("ascii")
    with args.output.open("wb") as stream:
        stream.write(header)
        for start in range(0, count, args.chunk_size):
            stop = min(count, start + args.chunk_size)
            block = source[start:stop]
            converted = np.empty(stop - start, dtype=OUTPUT_DTYPE)
            converted["x"] = block["x"]
            converted["y"] = block["y"]
            converted["z"] = block["z"]
            dc = np.stack([block["f_dc_0"], block["f_dc_1"], block["f_dc_2"]], axis=1)
            rgb = np.clip(0.5 + SH_C0 * dc, 0.0, 1.0)
            converted["red"], converted["green"], converted["blue"] = (rgb * 255.0).round().astype(np.uint8).T
            converted.tofile(stream)
    print(f"Wrote {count:,} colored points to {args.output}")


if __name__ == "__main__":
    main()
