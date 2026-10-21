"""Depth-to-mesh math shared by the Blender exporter and regression tests."""
import numpy as np


def depth_mesh(depth, mask, intrinsics, edge_threshold=0.04, scale=1.0):
    depth = np.asarray(depth, dtype=np.float32)
    h, w = depth.shape
    if h < 2 or w < 2 or scale <= 0 or edge_threshold <= 0:
        raise ValueError('Invalid mesh dimensions, scale, or edge threshold.')
    mask = np.asarray(mask, dtype=bool) & np.isfinite(depth) & (depth > 0)
    k = np.asarray(intrinsics, dtype=np.float64)
    if k.shape != (3, 3) or not np.isfinite(k).all() or min(k[0, 0], k[1, 1]) <= 0:
        raise ValueError('Expected valid normalized pinhole intrinsics.')
    yy, xx = np.mgrid[:h, :w]
    z = np.where(mask, depth * scale, 0)
    u, v = (xx + 0.5) / w, (yy + 0.5) / h
    points = np.stack([(u-k[0, 2])/k[0, 0]*z, (v-k[1, 2])/k[1, 1]*z, z], -1).reshape(-1, 3)
    ids = np.arange(h*w, dtype=np.int32).reshape(h, w)
    tl, tr, bl, br = ids[:-1, :-1], ids[:-1, 1:], ids[1:, :-1], ids[1:, 1:]
    faces = np.concatenate([np.stack([tl, bl, tr], -1).reshape(-1, 3),
                            np.stack([tr, bl, br], -1).reshape(-1, 3)])
    dz = z.ravel()[faces]
    keep = mask.ravel()[faces].all(1) & ((dz.max(1)-dz.min(1)) <= edge_threshold*np.maximum(dz.min(1), 1e-8))
    faces = faces[keep]
    if not len(faces):
        raise ValueError('No mesh faces remain. Check the depth map or increase the edge threshold.')
    used = np.unique(faces)
    remap = np.full(h*w, -1, dtype=np.int32)
    remap[used] = np.arange(len(used), dtype=np.int32)
    uv = np.stack([u.ravel()[used], 1-v.ravel()[used]], -1)
    return points[used].astype(np.float32), remap[faces], uv.astype(np.float32)


def inverse_depth_preview(depth, mask):
    valid = np.asarray(mask, bool) & np.isfinite(depth) & (depth > 0)
    if not valid.any():
        raise ValueError('The model did not produce any valid depth pixels.')
    inv = np.zeros_like(depth, dtype=np.float32)
    inv[valid] = 1 / depth[valid]
    lo, hi = np.percentile(inv[valid], [1, 99])
    view = np.zeros_like(inv)
    view[valid] = np.clip((inv[valid]-lo)/max(hi-lo, 1e-8), 0, 1) if hi > lo else 1
    return view, valid
