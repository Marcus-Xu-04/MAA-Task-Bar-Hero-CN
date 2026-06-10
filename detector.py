# MAA Task Bar Hero
# Concept and direction by Marcus Xu.
# Built with Codex as a coding assistant.
# Shared for learning, experimentation, and automation research.

import cv2
import numpy as np
from pathlib import Path
import sys

def load_template(path):
    candidates = [
        Path(path),
        Path(__file__).resolve().parent / path,
        Path(sys.executable).resolve().parent / path,
    ]

    if hasattr(sys, "_MEIPASS"):
        candidates.insert(1, Path(sys._MEIPASS) / path)

    template = None

    for candidate in candidates:
            # Only ask OpenCV to read it if the file path actually exists
            if candidate.is_file():
                template = cv2.imread(str(candidate), cv2.IMREAD_COLOR)

                if template is not None:
                    break

    if template is None:
        raise FileNotFoundError(f"Could not load template: {path}")

    return template


def match_template(search_img, template):
    """
    Search for one template inside one image region.
    """
    search_h, search_w = search_img.shape[:2]
    template_h, template_w = template.shape[:2]

    if template_h > search_h or template_w > search_w:
        return {
            "confidence": 0.0,
            "top_left": (0, 0),
            "bottom_right": (template_w, template_h),
            "center": (template_w // 2, template_h // 2),
            "size": (template_w, template_h),
        }

    result = cv2.matchTemplate(search_img, template, cv2.TM_CCOEFF_NORMED)

    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

    top_left = max_loc
    bottom_right = (max_loc[0] + template_w, max_loc[1] + template_h)
    center = (
        max_loc[0] + template_w // 2,
        max_loc[1] + template_h // 2,
    )

    return {
        "confidence": float(max_val),
        "top_left": top_left,
        "bottom_right": bottom_right,
        "center": center,
        "size": (template_w, template_h),
    }


def detect_chests_in_region(region_img, blue_template=None, brown_template=None, threshold=0.80):
    """
    Detect blue/brown chests inside one cropped battle region.
    Allows either template to be missing.
    """
    detections = []

    if blue_template is not None:
        blue = match_template(region_img, blue_template)

        if blue["confidence"] >= threshold:
            detections.append({
                "type": "blue",
                **blue,
            })

    if brown_template is not None:
        brown = match_template(region_img, brown_template)

        if brown["confidence"] >= threshold:
            detections.append({
                "type": "brown",
                **brown,
            })

    return detections

def detect_boss_warning_pixels(region_img, min_red_pixels=3000):
    """
    Detect the big red WARNING boss flash.
    OpenCV image format is BGR.
    """

    b = region_img[:, :, 0]
    g = region_img[:, :, 1]
    r = region_img[:, :, 2]

    red_mask = (
        (r > 150) &
        (g < 110) &
        (b < 110)
    )

    red_pixels = int(np.count_nonzero(red_mask))

    return red_pixels >= min_red_pixels, red_pixels

def detect_blue_text_pixels(region_img, min_blue_pixels=80):
    """
    Detect blue-colored text inside a cropped log region.
    OpenCV image format is BGR.
    """

    b = region_img[:, :, 0]
    g = region_img[:, :, 1]
    r = region_img[:, :, 2]

    blue_mask = (
        (b > 120) &
        (g > 60) &
        (g < 200) &
        (r < 130)
    )

    blue_pixels = int(np.count_nonzero(blue_mask))

    return blue_pixels >= min_blue_pixels, blue_pixels
