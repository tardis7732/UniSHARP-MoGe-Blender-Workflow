"""Keep source proportions, or center-crop to an explicitly requested frame."""
from PIL import Image, ImageOps


def original_height(image_path, width):
    with Image.open(image_path) as image:
        image = ImageOps.exif_transpose(image)
        return max(2, round(int(width)*image.height/image.width))


def prepare_photo(image_path, width, height=None):
    with Image.open(image_path) as source:
        image = ImageOps.exif_transpose(source).convert('RGB')
    width = int(width)
    locked = height is None
    height = max(2, round(width*image.height/image.width)) if locked else int(height)
    if not 256 <= width <= 4096 or not 128 <= height <= 8192:
        raise ValueError('Width must be 256..4096 and height 128..8192.')
    if not 0.5 <= width/height <= 2:
        raise ValueError('MoGe expects an aspect ratio between 1:2 and 2:1.')
    if not locked:
        # Crop the original at its native resolution, keeping texture detail.
        ratio = width/height
        if image.width/image.height > ratio:
            crop_width = max(1, round(image.height*ratio))
            left = (image.width-crop_width)//2
            image = image.crop((left, 0, left+crop_width, image.height))
        else:
            crop_height = max(1, round(image.width/ratio))
            top = (image.height-crop_height)//2
            image = image.crop((0, top, image.width, top+crop_height))
    return image, image.resize((width, height), Image.Resampling.LANCZOS)
