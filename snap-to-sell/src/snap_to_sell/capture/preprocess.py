"""Capture / pre-process.

Normalises a phone photo before recognition: EXIF auto-orient, downscale very large images,
mild CLAHE contrast to reduce glare/exposure variation. Writes a sibling '<stem>.norm.<ext>'
and returns its path. Falls back to a passthrough if OpenCV/Pillow are unavailable so the
pipeline never breaks.
"""
import os

MAX_SIDE = 1024  # downscale so hosted-API image tokens stay small


def preprocess(image_path: str) -> str:
    try:
        import cv2
        import numpy as np
    except Exception:
        return image_path  # fallback: passthrough

    img = cv2.imread(image_path)
    if img is None:
        return image_path

    # downscale
    h, w = img.shape[:2]
    scale = MAX_SIDE / float(max(h, w))
    if scale < 1.0:
        img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)

    # mild glare/exposure normalisation via CLAHE on the luminance channel
    try:
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        lab = cv2.merge((clahe.apply(l), a, b))
        img = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
    except Exception:
        pass

    stem, ext = os.path.splitext(image_path)
    out = f"{stem}.norm{ext or '.jpg'}"
    cv2.imwrite(out, img)
    return out
