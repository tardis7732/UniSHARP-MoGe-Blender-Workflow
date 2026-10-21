"""Convert premultiplied EXR pixels read by Blender into depth PNG/TIFF files."""
import argparse
from pathlib import Path
import numpy as np
from PIL import Image
from moge_geometry import inverse_depth_preview

p = argparse.ArgumentParser()
p.add_argument('folder')
a = p.parse_args()
out = Path(a.folder)
rgba = np.load(out/'camera_depth_rgba.npy')
alpha = np.clip(rgba[..., 3], 0, 1)
z = rgba[..., 0]/np.maximum(alpha, 1e-8)
view, valid = inverse_depth_preview(z, alpha > .01)
view *= alpha
Image.fromarray(np.uint16(view*65535+.5)).save(out/'camera_depth_16bit.png')
Image.fromarray(np.uint8(view*255+.5)).save(out/'camera_depth_preview.png')
Image.fromarray(np.where(valid, z, 0).astype(np.float32)).save(out/'camera_depth_Z_float32.tif')
Image.fromarray(np.uint8(alpha*255+.5)).save(out/'camera_depth_mask.png')
# This intermediate belongs exclusively to this conversion run.
(out/'camera_depth_rgba.npy').unlink()
