"""Run official, non-quantized MoGe-3 weights in the separate MoGe environment."""
import argparse
import json
from pathlib import Path
import time

import numpy as np
from PIL import Image, ImageOps
import torch
from moge.model.v3 import MoGeModel
from moge_geometry import inverse_depth_preview


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--input', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--model', choices=['Ruicheng/moge-3-vitl', 'Ruicheng/moge-3-vitg'], default='Ruicheng/moge-3-vitl')
    p.add_argument('--checkpoint')
    p.add_argument('--width', type=int, default=1536)
    p.add_argument('--tokens', type=int, default=1200)
    p.add_argument('--camera-json')
    a = p.parse_args()
    if not torch.cuda.is_available():
        raise RuntimeError('MoGe-3 requires a CUDA GPU in this workflow.')
    if not 256 <= a.width <= 4096 or not 1200 <= a.tokens <= 3600:
        raise ValueError('Width must be 256..4096; tokens must be 1200..3600.')
    out = Path(a.output).resolve(); out.mkdir(parents=True, exist_ok=True)
    im = ImageOps.exif_transpose(Image.open(a.input)).convert('RGB')
    if not 0.5 <= im.width/im.height <= 2:
        raise ValueError('MoGe expects an ordinary photo with aspect ratio between 1:2 and 2:1.')
    im.save(out/'texture.png')
    width = min(a.width, im.width)
    sample = im.resize((width, max(2, round(im.height*width/im.width))), Image.Resampling.LANCZOS)
    fov = None
    if a.camera_json:
        ref = json.loads(Path(a.camera_json).read_text(encoding='utf-8'))
        if abs(im.width/im.height - ref['aspect']) > 0.01:
            raise ValueError('Reference camera aspect ratio does not match this image. Use the original photo.')
        fov = float(np.degrees(2*np.arctan(ref['sensor_width']/(2*ref['lens']))))
    print('Loading', a.model, flush=True)
    model = MoGeModel.from_pretrained(a.checkpoint or a.model).to('cuda').eval()
    x = torch.from_numpy(np.asarray(sample, dtype=np.float32)/255).permute(2, 0, 1).to('cuda')
    started = time.monotonic()
    with torch.inference_mode():
        result = model.infer(x, num_tokens=a.tokens, refine_steps=3, fov_x=fov, use_fp16=True)
    result = {k: v.detach().cpu().numpy() for k, v in result.items()}
    depth = result['depth'].astype(np.float32)
    view, valid = inverse_depth_preview(depth, result['mask'])
    np.savez_compressed(out/'depth_data.npz', depth=depth, mask=valid, intrinsics=result['intrinsics'])
    Image.fromarray(np.uint16(view*65535+0.5)).save(out/'source_depth_16bit.png')
    Image.fromarray(np.uint8(view*255+0.5)).save(out/'source_depth_preview.png')
    Image.fromarray(np.where(valid, depth, 0).astype(np.float32)).save(out/'source_depth_Z_float32.tif')
    Image.fromarray(valid.astype(np.uint8)*255).save(out/'source_depth_mask.png')
    (out/'model_info.json').write_text(json.dumps({
        'model': a.model, 'quantized': False, 'inference_fp16': True,
        'tokens': a.tokens, 'refine_steps': 3, 'resolution': list(sample.size),
        'fov_override': fov, 'intrinsics': result['intrinsics'].tolist(),
        'seconds': time.monotonic()-started,
        'png': 'Normalized inverse depth: near white, far black. Invalid pixels black.',
        'tiff': 'Raw model camera Z; invalid pixels zero. Not median-aligned to reference scene.'
    }, indent=2), encoding='utf-8')
    print('MoGe inference complete', flush=True)


if __name__ == '__main__':
    main()
