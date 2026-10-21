"""Write UniSHARP Gaussians as a standard vertex-only 3DGS PLY for UE plugins."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from export_colored_ply import INPUT_DTYPE, read_header


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="UniSHARP Gaussian PLY")
    parser.add_argument("output", type=Path, help="Standard vertex-only 3DGS PLY")
    parser.add_argument("--chunk-size", type=int, default=262_144)
    args = parser.parse_args()

    count, offset = read_header(args.input)
    source = np.memmap(args.input, dtype=INPUT_DTYPE, mode="r", offset=offset, shape=(count,))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    header = (
        "ply\n"
        "format binary_little_endian 1.0\n"
        "comment Standard 3D Gaussian Splat PLY exported from UniSHARP\n"
        f"element vertex {count}\n"
        "property float x\nproperty float y\nproperty float z\n"
        "property float f_dc_0\nproperty float f_dc_1\nproperty float f_dc_2\n"
        "property float opacity\n"
        "property float scale_0\nproperty float scale_1\nproperty float scale_2\n"
        "property float rot_0\nproperty float rot_1\nproperty float rot_2\nproperty float rot_3\n"
        "end_header\n"
    ).encode("ascii")
    with args.output.open("wb") as stream:
        stream.write(header)
        for start in range(0, count, args.chunk_size):
            stop = min(start + args.chunk_size, count)
            stream.write(source[start:stop].tobytes())
    print(f"Saved UE standard Gaussian PLY: {args.output}")


if __name__ == "__main__":
    main()
