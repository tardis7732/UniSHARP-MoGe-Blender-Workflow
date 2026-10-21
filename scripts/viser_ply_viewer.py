"""Serve a standard 3D Gaussian Splat PLY in a local Viser WebGL viewer."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from plyfile import PlyData
import viser
from viser import transforms as tf


SH_C0 = 0.28209479177387814


def load_gaussian_ply(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    vertex = PlyData.read(path)["vertex"]
    required = {"x", "y", "z", "f_dc_0", "f_dc_1", "f_dc_2", "opacity", "scale_0", "scale_1", "scale_2", "rot_0", "rot_1", "rot_2", "rot_3"}
    missing = required.difference(vertex.data.dtype.names or ())
    if missing:
        raise ValueError(f"PLY is not a standard Gaussian Splat file; missing: {sorted(missing)}")
    centers = np.stack([vertex["x"], vertex["y"], vertex["z"]], axis=1).astype(np.float32)
    centers -= centers.mean(axis=0, keepdims=True)
    scales = np.exp(np.stack([vertex["scale_0"], vertex["scale_1"], vertex["scale_2"]], axis=1)).astype(np.float32)
    wxyz = np.stack([vertex["rot_0"], vertex["rot_1"], vertex["rot_2"], vertex["rot_3"]], axis=1).astype(np.float32)
    wxyz /= np.linalg.norm(wxyz, axis=1, keepdims=True).clip(min=1e-8)
    rotations = tf.SO3(wxyz).as_matrix().astype(np.float32)
    covariances = np.einsum("nij,njk,nlk->nil", rotations, np.eye(3, dtype=np.float32)[None] * scales[:, None] ** 2, rotations).astype(np.float32)
    rgbs = np.clip(0.5 + SH_C0 * np.stack([vertex["f_dc_0"], vertex["f_dc_1"], vertex["f_dc_2"]], axis=1), 0.0, 1.0).astype(np.float32)
    opacities = (1.0 / (1.0 + np.exp(-vertex["opacity"][:, None]))).astype(np.float32)
    return centers, covariances, rgbs, opacities


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ply", type=Path)
    parser.add_argument("--port", type=int, default=8081)
    args = parser.parse_args()
    centers, covariances, rgbs, opacities = load_gaussian_ply(args.ply)
    server = viser.ViserServer(host="127.0.0.1", port=args.port, label=f"UniSHARP PLY: {args.ply.name}", verbose=False)
    server.scene.add_gaussian_splats(
        "/gaussians",
        centers=centers,
        covariances=covariances,
        rgbs=rgbs,
        opacities=opacities,
    )
    spread = float(np.percentile(np.linalg.norm(centers, axis=1), 90))
    server.initial_camera.position = (max(spread * 1.8, 1.0), -max(spread * 1.8, 1.0), max(spread * 0.8, 0.5))
    server.initial_camera.look_at = (0.0, 0.0, 0.0)
    server.initial_camera.up = (0.0, 0.0, 1.0)
    print(f"Viser PLY viewer ready at http://127.0.0.1:{args.port}", flush=True)
    server.sleep_forever()


if __name__ == "__main__":
    main()
