# MAA Task Bar Hero
# Concept and direction by Marcus Xu.
# Built with Codex as a coding assistant.
# Shared for learning, experimentation, and automation research.

import ctypes
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import win32gui
import win32ui


_VISUAL_REGIONS = {}
_VISUAL_BATTLE_SEARCH_REGION_NAMES = ()
_VISUAL_PREVIEW_REGION_NAMES = ()
_VISUAL_REGION_COLORS = {}
_VISUAL_DETECTION_COLORS = {}
_VISUAL_MATCH_THRESHOLD = 0.80
_VISUAL_BOSS_WARNING_CONFIDENCE_THRESHOLD = 0.85
_VISUAL_CLEAR_MATCH_THRESHOLD = 0.85
_VISUAL_CLEAR_TEMPLATE_PATH = "templates/general/task_clear.png"
_VISUAL_USE_EXPANDED_ROI_RETRY = False
_VISUAL_EXPANDED_ROI_MARGIN_PX = 48
_VISUAL_EXPANDED_ROI_SCALE_FACTOR = 1.15
_VISUAL_EXPANDED_ROI_ONLY_ON_UI_WARNING = True
_VISUAL_RECOGNITION_MODE = "balanced"
_VISUAL_GET_UI_RETRY_STATE = lambda: (False, "UNKNOWN")
_VISUAL_GET_MOUSE_POSITION = lambda: (0, 0)
_VISUAL_WRITE_LOG = None
_VISUAL_SAFE_PRINT = print
_VISUAL_SAVE_DEBUG_SCREENSHOT = None
_VISUAL_GET_DEBUG_DIR = None
_VISUAL_LAST_CLEAR_DEBUG_LOG_TIME = 0
_VISUAL_LAST_WINDOW_LOOKUP_ERROR = None

_NAV_DIFFICULTY_TEMPLATES = {}
_NAV_CHAPTER_TEMPLATES = {}
_NAV_CHAPTER_ORDER = ()
_NAV_LEVEL_MATCH_THRESHOLD = 0.80
_NAV_LEVEL_STRONG_ACCEPT_THRESHOLD = 0.88
_NAV_LEVEL_DOT_GREEN_TEMPLATE = None
_NAV_LEVEL_DOT_GREEN_MATCH_THRESHOLD = 0.80
_NAV_LEVEL_DOT_MAX_VERTICAL_DISTANCE = 25
_NAV_DIFFICULTY_MATCH_THRESHOLD = 0.80
_NAV_CHAPTER_MATCH_THRESHOLD = 0.80
_NAV_CHAPTER_TAB_CANDIDATE_THRESHOLD = 0.80
_NAV_CHAPTER_TAB_CLUSTER_X_TOLERANCE = 32
_NAV_CHAPTER_TAB_CLUSTER_Y_TOLERANCE = 22
_NAV_CHAPTER_CANDIDATE_AMBIGUITY_MARGIN = 0.03
_NAV_CHAPTER_AMBIGUOUS_MIN_CONFIDENCE = 0.80
_NAV_CHAPTER_GEOMETRY_FALLBACK_ENABLED = True
_NAV_CHAPTER_GEOMETRY_MIN_CONFIDENCE = 0.78
_NAV_CHAPTER_GEOMETRY_REQUIRE_DYNAMIC_ANCHOR = True
_NAV_CHAPTER_GEOMETRY_TOLERANCE_PX = 18
_NAV_SELECTED_LEVEL_GREEN_PIXEL_MIN = 20
_NAV_SELECTED_LEVEL_GREEN_RATIO_MIN = 0.03
_NAV_SELECTED_LEVEL_GREEN_HSV_LOWER = (35, 40, 40)
_NAV_SELECTED_LEVEL_GREEN_HSV_UPPER = (95, 255, 255)
_NAV_LEVEL_Y_POSITION_TOLERANCE_PX = 5
_NAV_ROUTE_INVARIANT_ALLOW_SELECTED_EVIDENCE = True
_NAV_ROUTE_INVARIANT_LEVEL_CONFIDENCE_FLOOR = 0.88
_NAV_ROUTE_INVARIANT_GREEN_DOT_MIN_CONFIDENCE = 0.75
_NAV_ROUTE_INVARIANT_REQUIRE_LEVEL_Y_OK = True


@dataclass(frozen=True)
class DetectionSnapshot:
    detections: list
    boss_visible: bool
    boss_region: str | None
    boss_pixels: int
    boss_confidence: float
    clear_visible: bool
    clear_confidence: float
    clear_match_info: dict | None


def configure_visual_detection(
    *,
    regions,
    battle_search_region_names,
    preview_region_names,
    region_colors,
    detection_colors,
    match_threshold,
    boss_warning_confidence_threshold,
    clear_match_threshold,
    clear_template_path,
    use_expanded_roi_retry,
    expanded_roi_margin_px,
    expanded_roi_scale_factor,
    expanded_roi_only_on_ui_warning,
    recognition_mode,
    get_ui_retry_state,
    get_mouse_position,
    write_log,
    safe_print,
    save_debug_screenshot_callback,
    get_debug_dir,
):
    global _VISUAL_REGIONS
    global _VISUAL_BATTLE_SEARCH_REGION_NAMES
    global _VISUAL_PREVIEW_REGION_NAMES
    global _VISUAL_REGION_COLORS
    global _VISUAL_DETECTION_COLORS
    global _VISUAL_MATCH_THRESHOLD
    global _VISUAL_BOSS_WARNING_CONFIDENCE_THRESHOLD
    global _VISUAL_CLEAR_MATCH_THRESHOLD
    global _VISUAL_CLEAR_TEMPLATE_PATH
    global _VISUAL_USE_EXPANDED_ROI_RETRY
    global _VISUAL_EXPANDED_ROI_MARGIN_PX
    global _VISUAL_EXPANDED_ROI_SCALE_FACTOR
    global _VISUAL_EXPANDED_ROI_ONLY_ON_UI_WARNING
    global _VISUAL_RECOGNITION_MODE
    global _VISUAL_GET_UI_RETRY_STATE
    global _VISUAL_GET_MOUSE_POSITION
    global _VISUAL_WRITE_LOG
    global _VISUAL_SAFE_PRINT
    global _VISUAL_SAVE_DEBUG_SCREENSHOT
    global _VISUAL_GET_DEBUG_DIR

    _VISUAL_REGIONS = regions
    _VISUAL_BATTLE_SEARCH_REGION_NAMES = tuple(battle_search_region_names)
    _VISUAL_PREVIEW_REGION_NAMES = tuple(preview_region_names)
    _VISUAL_REGION_COLORS = region_colors
    _VISUAL_DETECTION_COLORS = detection_colors
    _VISUAL_MATCH_THRESHOLD = match_threshold
    _VISUAL_BOSS_WARNING_CONFIDENCE_THRESHOLD = boss_warning_confidence_threshold
    _VISUAL_CLEAR_MATCH_THRESHOLD = clear_match_threshold
    _VISUAL_CLEAR_TEMPLATE_PATH = clear_template_path
    _VISUAL_USE_EXPANDED_ROI_RETRY = use_expanded_roi_retry
    _VISUAL_EXPANDED_ROI_MARGIN_PX = expanded_roi_margin_px
    _VISUAL_EXPANDED_ROI_SCALE_FACTOR = expanded_roi_scale_factor
    _VISUAL_EXPANDED_ROI_ONLY_ON_UI_WARNING = expanded_roi_only_on_ui_warning
    _VISUAL_RECOGNITION_MODE = recognition_mode
    _VISUAL_GET_UI_RETRY_STATE = get_ui_retry_state
    _VISUAL_GET_MOUSE_POSITION = get_mouse_position
    _VISUAL_WRITE_LOG = write_log
    _VISUAL_SAFE_PRINT = safe_print
    _VISUAL_SAVE_DEBUG_SCREENSHOT = save_debug_screenshot_callback
    _VISUAL_GET_DEBUG_DIR = get_debug_dir


def configure_navigation_visual_observation(
    *,
    difficulty_templates,
    chapter_templates,
    chapter_order,
    level_match_threshold,
    level_strong_accept_threshold,
    level_dot_green_template,
    level_dot_green_match_threshold,
    level_dot_max_vertical_distance,
    difficulty_match_threshold,
    chapter_match_threshold,
    chapter_tab_candidate_threshold,
    chapter_tab_cluster_x_tolerance,
    chapter_tab_cluster_y_tolerance,
    chapter_candidate_ambiguity_margin,
    chapter_ambiguous_min_confidence,
    chapter_geometry_fallback_enabled,
    chapter_geometry_min_confidence,
    chapter_geometry_require_dynamic_anchor,
    chapter_geometry_tolerance_px,
    selected_level_green_pixel_min,
    selected_level_green_ratio_min,
    selected_level_green_hsv_lower,
    selected_level_green_hsv_upper,
    level_y_position_tolerance_px,
    route_invariant_allow_selected_evidence,
    route_invariant_level_confidence_floor,
    route_invariant_green_dot_min_confidence,
    route_invariant_require_level_y_ok,
):
    global _NAV_DIFFICULTY_TEMPLATES
    global _NAV_CHAPTER_TEMPLATES
    global _NAV_CHAPTER_ORDER
    global _NAV_LEVEL_MATCH_THRESHOLD
    global _NAV_LEVEL_STRONG_ACCEPT_THRESHOLD
    global _NAV_LEVEL_DOT_GREEN_TEMPLATE
    global _NAV_LEVEL_DOT_GREEN_MATCH_THRESHOLD
    global _NAV_LEVEL_DOT_MAX_VERTICAL_DISTANCE
    global _NAV_DIFFICULTY_MATCH_THRESHOLD
    global _NAV_CHAPTER_MATCH_THRESHOLD
    global _NAV_CHAPTER_TAB_CANDIDATE_THRESHOLD
    global _NAV_CHAPTER_TAB_CLUSTER_X_TOLERANCE
    global _NAV_CHAPTER_TAB_CLUSTER_Y_TOLERANCE
    global _NAV_CHAPTER_CANDIDATE_AMBIGUITY_MARGIN
    global _NAV_CHAPTER_AMBIGUOUS_MIN_CONFIDENCE
    global _NAV_CHAPTER_GEOMETRY_FALLBACK_ENABLED
    global _NAV_CHAPTER_GEOMETRY_MIN_CONFIDENCE
    global _NAV_CHAPTER_GEOMETRY_REQUIRE_DYNAMIC_ANCHOR
    global _NAV_CHAPTER_GEOMETRY_TOLERANCE_PX
    global _NAV_SELECTED_LEVEL_GREEN_PIXEL_MIN
    global _NAV_SELECTED_LEVEL_GREEN_RATIO_MIN
    global _NAV_SELECTED_LEVEL_GREEN_HSV_LOWER
    global _NAV_SELECTED_LEVEL_GREEN_HSV_UPPER
    global _NAV_LEVEL_Y_POSITION_TOLERANCE_PX
    global _NAV_ROUTE_INVARIANT_ALLOW_SELECTED_EVIDENCE
    global _NAV_ROUTE_INVARIANT_LEVEL_CONFIDENCE_FLOOR
    global _NAV_ROUTE_INVARIANT_GREEN_DOT_MIN_CONFIDENCE
    global _NAV_ROUTE_INVARIANT_REQUIRE_LEVEL_Y_OK

    _NAV_DIFFICULTY_TEMPLATES = difficulty_templates
    _NAV_CHAPTER_TEMPLATES = chapter_templates
    _NAV_CHAPTER_ORDER = tuple(chapter_order)
    _NAV_LEVEL_MATCH_THRESHOLD = level_match_threshold
    _NAV_LEVEL_STRONG_ACCEPT_THRESHOLD = level_strong_accept_threshold
    _NAV_LEVEL_DOT_GREEN_TEMPLATE = level_dot_green_template
    _NAV_LEVEL_DOT_GREEN_MATCH_THRESHOLD = level_dot_green_match_threshold
    _NAV_LEVEL_DOT_MAX_VERTICAL_DISTANCE = level_dot_max_vertical_distance
    _NAV_DIFFICULTY_MATCH_THRESHOLD = difficulty_match_threshold
    _NAV_CHAPTER_MATCH_THRESHOLD = chapter_match_threshold
    _NAV_CHAPTER_TAB_CANDIDATE_THRESHOLD = chapter_tab_candidate_threshold
    _NAV_CHAPTER_TAB_CLUSTER_X_TOLERANCE = chapter_tab_cluster_x_tolerance
    _NAV_CHAPTER_TAB_CLUSTER_Y_TOLERANCE = chapter_tab_cluster_y_tolerance
    _NAV_CHAPTER_CANDIDATE_AMBIGUITY_MARGIN = chapter_candidate_ambiguity_margin
    _NAV_CHAPTER_AMBIGUOUS_MIN_CONFIDENCE = chapter_ambiguous_min_confidence
    _NAV_CHAPTER_GEOMETRY_FALLBACK_ENABLED = chapter_geometry_fallback_enabled
    _NAV_CHAPTER_GEOMETRY_MIN_CONFIDENCE = chapter_geometry_min_confidence
    _NAV_CHAPTER_GEOMETRY_REQUIRE_DYNAMIC_ANCHOR = chapter_geometry_require_dynamic_anchor
    _NAV_CHAPTER_GEOMETRY_TOLERANCE_PX = chapter_geometry_tolerance_px
    _NAV_SELECTED_LEVEL_GREEN_PIXEL_MIN = selected_level_green_pixel_min
    _NAV_SELECTED_LEVEL_GREEN_RATIO_MIN = selected_level_green_ratio_min
    _NAV_SELECTED_LEVEL_GREEN_HSV_LOWER = tuple(selected_level_green_hsv_lower)
    _NAV_SELECTED_LEVEL_GREEN_HSV_UPPER = tuple(selected_level_green_hsv_upper)
    _NAV_LEVEL_Y_POSITION_TOLERANCE_PX = level_y_position_tolerance_px
    _NAV_ROUTE_INVARIANT_ALLOW_SELECTED_EVIDENCE = route_invariant_allow_selected_evidence
    _NAV_ROUTE_INVARIANT_LEVEL_CONFIDENCE_FLOOR = route_invariant_level_confidence_floor
    _NAV_ROUTE_INVARIANT_GREEN_DOT_MIN_CONFIDENCE = route_invariant_green_dot_min_confidence
    _NAV_ROUTE_INVARIANT_REQUIRE_LEVEL_Y_OK = route_invariant_require_level_y_ok


def _write_log(message):
    if _VISUAL_WRITE_LOG is not None:
        _VISUAL_WRITE_LOG(message)


def get_last_window_lookup_error():
    return _VISUAL_LAST_WINDOW_LOOKUP_ERROR


def find_window_by_title_keyword(keyword: str):
    """
    Find a visible window whose title contains the keyword.
    Example keyword: "TaskBarHero"
    """
    global _VISUAL_LAST_WINDOW_LOOKUP_ERROR

    _VISUAL_LAST_WINDOW_LOOKUP_ERROR = None
    matched_windows = []
    callback_errors = []

    def enum_handler(hwnd, _):
        try:
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if keyword.lower() in str(title).lower():
                    matched_windows.append((hwnd, title))
        except Exception as e:
            callback_errors.append((hwnd, e))

            if len(callback_errors) <= 3:
                _write_log(
                    f"Window enumeration callback warning | "
                    f"keyword={keyword} | hwnd={hwnd} | "
                    f"error={type(e).__name__}: {e}"
                )

        return True

    try:
        win32gui.EnumWindows(enum_handler, None)
    except Exception as e:
        _VISUAL_LAST_WINDOW_LOOKUP_ERROR = (
            f"Window enumeration failed while looking for '{keyword}' | "
            f"error={type(e).__name__}: {e}"
        )
        _write_log(_VISUAL_LAST_WINDOW_LOOKUP_ERROR)
        return None, None

    if not matched_windows:
        if callback_errors:
            _VISUAL_LAST_WINDOW_LOOKUP_ERROR = (
                f"Window enumeration completed with {len(callback_errors)} callback "
                f"errors while looking for '{keyword}', and no matching window was found."
            )
            _write_log(_VISUAL_LAST_WINDOW_LOOKUP_ERROR)

        return None, None

    return matched_windows[0]


def capture_window(hwnd):
    """
    Capture only the target window.
    Returns image in OpenCV BGR format.
    """

    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    width = right - left
    height = bottom - top

    if width <= 0 or height <= 0:
        raise RuntimeError("Invalid window size. Is the game minimized?")

    hwnd_dc = win32gui.GetWindowDC(hwnd)
    mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
    save_dc = mfc_dc.CreateCompatibleDC()

    bitmap = win32ui.CreateBitmap()
    bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
    save_dc.SelectObject(bitmap)

    # Windows API PrintWindow through ctypes.
    # 2 = PW_RENDERFULLCONTENT, usually better for modern windows.
    result = ctypes.windll.user32.PrintWindow(
        hwnd,
        save_dc.GetSafeHdc(),
        2
    )

    bmpinfo = bitmap.GetInfo()
    bmpstr = bitmap.GetBitmapBits(True)

    img = np.frombuffer(bmpstr, dtype=np.uint8)
    img.shape = (bmpinfo["bmHeight"], bmpinfo["bmWidth"], 4)

    # Clean up Windows objects
    win32gui.DeleteObject(bitmap.GetHandle())
    save_dc.DeleteDC()
    mfc_dc.DeleteDC()
    win32gui.ReleaseDC(hwnd, hwnd_dc)

    if result != 1:
        raise RuntimeError(
            "PrintWindow failed. Make sure the game window is visible and not minimized."
        )

    # BGRA -> BGR for OpenCV
    img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

    return img


def save_debug_screenshot(img, folder="debug_screenshots", prefix="screenshot"):
    """
    Save a screenshot or crop with timestamp.
    """
    os.makedirs(folder, exist_ok=True)

    timestamp = int(time.time())
    filename = f"{folder}/{prefix}_{timestamp}.png"

    cv2.imwrite(filename, img)
    print(f"Saved: {filename}")


def get_template_candidates(path):
    exe_dir = Path(sys.executable).resolve().parent

    candidates = [
        Path(path),
        Path(__file__).resolve().parent / path,
        exe_dir / path,
        exe_dir / "_internal" / path,
    ]

    if hasattr(sys, "_MEIPASS"):
        candidates.insert(1, Path(sys._MEIPASS) / path)

    return candidates


def check_template_loadable(path):
    candidates = get_template_candidates(path)
    existing_paths = []

    for candidate in candidates:
        if not candidate.is_file():
            continue

        existing_paths.append(candidate)
        template = cv2.imread(str(candidate), cv2.IMREAD_COLOR)

        if template is not None:
            return {
                "status": "ok",
                "loaded_path": str(candidate),
                "expected_path": str(path),
                "checked_paths": [str(item) for item in candidates],
            }

    if existing_paths:
        return {
            "status": "load_failed",
            "expected_path": str(path),
            "checked_paths": [str(item) for item in candidates],
            "existing_paths": [str(item) for item in existing_paths],
        }

    return {
        "status": "missing",
        "expected_path": str(path),
        "checked_paths": [str(item) for item in candidates],
    }


def load_template(path):
    candidates = get_template_candidates(path)
    template = None
    checked_paths = []

    for candidate in candidates:
        checked_paths.append(str(candidate))

        # Only ask OpenCV to read it if the file path actually exists.
        if candidate.is_file():
            template = cv2.imread(str(candidate), cv2.IMREAD_COLOR)

            if template is not None:
                break

    if template is None:
        checked = "\n  ".join(checked_paths)
        raise FileNotFoundError(
            f"Could not load template: {path}\n"
            f"Checked paths:\n  {checked}"
        )

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


def save_visual_debug_artifacts(
    img,
    reason,
    roi=None,
    match_info=None,
    target_name=None,
    confidence=None,
    threshold=None,
):
    if _VISUAL_GET_DEBUG_DIR is None:
        return

    debug_dir = _VISUAL_GET_DEBUG_DIR()
    debug_dir.mkdir(parents=True, exist_ok=True)

    raw_path = debug_dir / "latest_raw_screenshot.png"
    annotated_path = debug_dir / "latest_annotated.png"

    cv2.imwrite(str(raw_path), img)

    annotation_available = roi is not None or match_info is not None or target_name is not None

    if annotation_available:
        annotated = img.copy()

        if roi is not None:
            clamped_roi = clamp_region(annotated, roi)

            if clamped_roi is not None:
                x1, y1, x2, y2 = clamped_roi
                cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 255), 2)
                cv2.putText(
                    annotated,
                    "ROI",
                    (x1 + 5, max(y1 + 22, 22)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 255),
                    2,
                    cv2.LINE_AA,
                )

        if match_info is not None:
            top_left = match_info.get("top_left_full")
            bottom_right = match_info.get("bottom_right_full")

            if top_left is not None and bottom_right is not None:
                cv2.rectangle(annotated, top_left, bottom_right, (0, 0, 255), 2)

        label_parts = []

        if target_name:
            label_parts.append(str(target_name))

        if confidence is not None:
            label_parts.append(f"best={confidence:.2f}")

        if threshold is not None:
            label_parts.append(f"threshold={threshold:.2f}")

        if reason:
            label_parts.append(str(reason))

        if label_parts:
            cv2.putText(
                annotated,
                " | ".join(label_parts)[:180],
                (25, 45),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 0, 255),
                2,
                cv2.LINE_AA,
            )

        cv2.imwrite(str(annotated_path), annotated)
        _write_log(
            f"Visual debug artifacts saved | reason={reason} | "
            f"raw={raw_path} | annotated={annotated_path}"
        )
    else:
        _write_log(
            f"Visual debug raw screenshot saved | reason={reason} | raw={raw_path}"
        )


def clamp_region(img, region):
    h, w = img.shape[:2]
    x1, y1, x2, y2 = region

    x1 = max(0, min(x1, w - 1))
    x2 = max(0, min(x2, w))
    y1 = max(0, min(y1, h - 1))
    y2 = max(0, min(y2, h))

    if x2 <= x1 or y2 <= y1:
        return None

    return x1, y1, x2, y2


def crop(img, region):
    clamped = clamp_region(img, region)

    if clamped is None:
        return None

    x1, y1, x2, y2 = clamped
    return img[y1:y2, x1:x2]


def regions_equal(region_a, region_b):
    if region_a is None or region_b is None:
        return False

    return tuple(region_a) == tuple(region_b)


def expand_region_for_retry(img, region):
    clamped = clamp_region(img, region)

    if clamped is None:
        return None

    x1, y1, x2, y2 = clamped
    width = x2 - x1
    height = y2 - y1
    scale_margin_x = int(width * max(0.0, _VISUAL_EXPANDED_ROI_SCALE_FACTOR - 1.0) / 2)
    scale_margin_y = int(height * max(0.0, _VISUAL_EXPANDED_ROI_SCALE_FACTOR - 1.0) / 2)
    margin_x = max(_VISUAL_EXPANDED_ROI_MARGIN_PX, scale_margin_x)
    margin_y = max(_VISUAL_EXPANDED_ROI_MARGIN_PX, scale_margin_y)

    return clamp_region(
        img,
        (
            x1 - margin_x,
            y1 - margin_y,
            x2 + margin_x,
            y2 + margin_y,
        )
    )


def get_expanded_roi_retry_reason():
    if not _VISUAL_USE_EXPANDED_ROI_RETRY:
        return None

    ui_retry_suggested, ui_health_status = _VISUAL_GET_UI_RETRY_STATE()
    reasons = []

    if _VISUAL_RECOGNITION_MODE == "aggressive":
        reasons.append("recognition_mode=aggressive")

    if ui_retry_suggested:
        reasons.append(f"ui_health={ui_health_status}")

    if not _VISUAL_EXPANDED_ROI_ONLY_ON_UI_WARNING:
        reasons.append("config=always")

    if not reasons:
        return None

    return ",".join(reasons)


def expanded_roi_retry_enabled():
    return get_expanded_roi_retry_reason() is not None


def log_expanded_roi_retry_start(label, template_path, original_roi, expanded_roi, reason):
    _write_log(
        f"ROI retry start | target={label} | template={template_path} | "
        f"original_roi={original_roi} | expanded_roi={expanded_roi} | reason={reason}"
    )


def log_expanded_roi_retry_result(label, found, confidence, threshold):
    status = "found candidate" if found else "failed"
    _write_log(
        f"ROI retry {status} | target={label} | "
        f"best_confidence={confidence:.2f} | threshold={threshold:.2f}"
    )


def detect_all_chests(img, blue_template, brown_template):
    """
    Search battle_top and battle_bottom for blue/brown chest templates.

    Returns detections in full-window coordinates.
    """
    all_detections = []

    for region_name in _VISUAL_BATTLE_SEARCH_REGION_NAMES:
        region = _VISUAL_REGIONS[region_name]
        clamped = clamp_region(img, region)

        if clamped is None:
            continue

        x1, y1, x2, y2 = clamped
        region_img = img[y1:y2, x1:x2]

        detections = detect_chests_in_region(
            region_img,
            blue_template,
            brown_template,
            threshold=_VISUAL_MATCH_THRESHOLD,
        )

        for det in detections:
            local_x1, local_y1 = det["top_left"]
            local_x2, local_y2 = det["bottom_right"]
            local_cx, local_cy = det["center"]

            full_det = det.copy()
            full_det["region_name"] = region_name
            full_det["top_left_full"] = (x1 + local_x1, y1 + local_y1)
            full_det["bottom_right_full"] = (x1 + local_x2, y1 + local_y2)
            full_det["center_full"] = (x1 + local_cx, y1 + local_cy)

            all_detections.append(full_det)

    return all_detections


def draw_regions(img):
    debug = img.copy()
    h, w = debug.shape[:2]
    mouse_x, mouse_y = _VISUAL_GET_MOUSE_POSITION()

    for name in _VISUAL_PREVIEW_REGION_NAMES:
        region = _VISUAL_REGIONS[name]
        clamped = clamp_region(debug, region)

        if clamped is None:
            continue

        x1, y1, x2, y2 = clamped
        color = _VISUAL_REGION_COLORS.get(name, (0, 255, 0))

        cv2.rectangle(debug, (x1, y1), (x2, y2), color, 2)

        cv2.putText(
            debug,
            name,
            (x1 + 5, max(y1 + 22, 22)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.75,
            color,
            2,
            cv2.LINE_AA,
        )

        coord_text = f"({x1},{y1})-({x2},{y2})"

        cv2.putText(
            debug,
            coord_text,
            (x1 + 5, min(y2 - 8, h - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            color,
            2,
            cv2.LINE_AA,
        )

    # Mouse crosshair
    cv2.line(debug, (mouse_x, 0), (mouse_x, h), (255, 255, 255), 1)
    cv2.line(debug, (0, mouse_y), (w, mouse_y), (255, 255, 255), 1)

    cv2.putText(
        debug,
        f"mouse: x={mouse_x}, y={mouse_y}",
        (25, 45),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.1,
        (255, 255, 255),
        3,
        cv2.LINE_AA,
    )

    cv2.putText(
        debug,
        f"capture size: {w} x {h}",
        (25, 85),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )

    return debug


def draw_detections(debug_img, detections):
    """
    Draw detected blue/brown chest boxes.
    """
    for det in detections:
        chest_type = det["type"]
        confidence = det["confidence"]
        region_name = det["region_name"]

        x1, y1 = det["top_left_full"]
        x2, y2 = det["bottom_right_full"]
        cx, cy = det["center_full"]

        color = _VISUAL_DETECTION_COLORS.get(chest_type, (255, 255, 255))

        cv2.rectangle(debug_img, (x1, y1), (x2, y2), color, 3)
        cv2.circle(debug_img, (cx, cy), 5, color, -1)

        label = f"{chest_type} {confidence:.2f} {region_name}"

        cv2.putText(
            debug_img,
            label,
            (x1, max(y1 - 8, 20)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            color,
            2,
            cv2.LINE_AA,
        )

    return debug_img


def save_all_regions(img):
    if _VISUAL_SAVE_DEBUG_SCREENSHOT is not None:
        _VISUAL_SAVE_DEBUG_SCREENSHOT(img, folder="debug_screenshots/full", prefix="full")

    for name, region in _VISUAL_REGIONS.items():
        cropped = crop(img, region)

        if cropped is not None and _VISUAL_SAVE_DEBUG_SCREENSHOT is not None:
            _VISUAL_SAVE_DEBUG_SCREENSHOT(
                cropped,
                folder=f"debug_screenshots/{name}",
                prefix=name
            )


def print_detection_summary(detections):
    if not detections:
        _VISUAL_SAFE_PRINT("No chest detected.".ljust(160), end="\r")
        return

    parts = []

    for det in detections:
        parts.append(
            f"{det['type']} {det['confidence']:.2f} "
            f"at {det['center_full']} in {det['region_name']}"
        )

    msg = " | ".join(parts)
    _VISUAL_SAFE_PRINT(msg[:160].ljust(160), end="\r")


def detect_blue_log(img):
    """
    Search log_top and log_bottom for blue log text.
    """
    log_regions = ["log_top", "log_bottom"]

    best_pixels = 0
    best_region = None

    for region_name in log_regions:
        region_img = crop(img, _VISUAL_REGIONS[region_name])

        if region_img is None:
            continue

        detected, blue_pixels = detect_blue_text_pixels(
            region_img,
            min_blue_pixels=80
        )

        if blue_pixels > best_pixels:
            best_pixels = blue_pixels
            best_region = region_name

        if detected:
            return True, region_name, blue_pixels

    return False, best_region, best_pixels


def find_template_in_region(img, template_path, region_name, threshold):
    """
    Find a template inside a named REGIONS area.

    Returns:
        found: bool
        center_full: (x, y) or None
        confidence: float
        match_info: dict or None
    """
    template = load_template(template_path)

    if template is None:
        _write_log(f"TEMPLATE LOAD FAILED: {template_path}")
        return False, None, 0.0, None

    if region_name not in _VISUAL_REGIONS:
        _write_log(f"REGION NOT FOUND: {region_name}")
        return False, None, 0.0, None

    region = _VISUAL_REGIONS[region_name]
    region_img = crop(img, region)

    if region_img is None:
        _write_log(f"REGION CROP FAILED: {region_name}")
        return False, None, 0.0, None

    match = match_template(region_img, template)
    confidence = match["confidence"]

    x1, y1, _, _ = region

    center_x, center_y = match["center"]
    top_left_x, top_left_y = match["top_left"]
    bottom_right_x, bottom_right_y = match["bottom_right"]

    match_info = {
        "center_full": (x1 + center_x, y1 + center_y),
        "top_left_full": (x1 + top_left_x, y1 + top_left_y),
        "bottom_right_full": (x1 + bottom_right_x, y1 + bottom_right_y),
        "size": match["size"],
        "confidence": confidence,
        "template_path": template_path,
        "region_name": region_name,
    }

    found = confidence >= threshold

    return found, match_info["center_full"], confidence, match_info


def find_template_in_box(img, template_path, region, threshold, label="custom_region"):
    """
    Find a template inside an explicit full-window rectangle.
    """
    template = load_template(template_path)
    region_img = crop(img, region)

    if region_img is None:
        _write_log(f"REGION CROP FAILED: {label}")
        return False, None, 0.0, None

    match = match_template(region_img, template)
    confidence = match["confidence"]

    x1, y1, _, _ = clamp_region(img, region)
    center_x, center_y = match["center"]
    top_left_x, top_left_y = match["top_left"]
    bottom_right_x, bottom_right_y = match["bottom_right"]

    match_info = {
        "center_full": (x1 + center_x, y1 + center_y),
        "top_left_full": (x1 + top_left_x, y1 + top_left_y),
        "bottom_right_full": (x1 + bottom_right_x, y1 + bottom_right_y),
        "size": match["size"],
        "confidence": confidence,
        "template_path": template_path,
        "region_name": label,
    }

    found = confidence >= threshold

    if not found:
        retry_reason = get_expanded_roi_retry_reason()

        if retry_reason is not None:
            expanded_region = expand_region_for_retry(img, region)
            original_region = clamp_region(img, region)

            if (
                expanded_region is not None
                and original_region is not None
                and not regions_equal(expanded_region, original_region)
            ):
                log_expanded_roi_retry_start(
                    label,
                    template_path,
                    original_region,
                    expanded_region,
                    retry_reason,
                )
                expanded_img = crop(img, expanded_region)

                if expanded_img is not None:
                    expanded_match = match_template(expanded_img, template)
                    expanded_confidence = expanded_match["confidence"]
                    ex1, ey1, _, _ = expanded_region
                    ex_center_x, ex_center_y = expanded_match["center"]
                    ex_top_left_x, ex_top_left_y = expanded_match["top_left"]
                    ex_bottom_right_x, ex_bottom_right_y = expanded_match["bottom_right"]
                    expanded_match_info = {
                        "center_full": (ex1 + ex_center_x, ey1 + ex_center_y),
                        "top_left_full": (ex1 + ex_top_left_x, ey1 + ex_top_left_y),
                        "bottom_right_full": (ex1 + ex_bottom_right_x, ey1 + ex_bottom_right_y),
                        "size": expanded_match["size"],
                        "confidence": expanded_confidence,
                        "template_path": template_path,
                        "region_name": label,
                        "roi_expanded": True,
                        "original_roi": original_region,
                        "expanded_roi": expanded_region,
                        "retry_reason": retry_reason,
                    }
                    expanded_found = expanded_confidence >= threshold
                    log_expanded_roi_retry_result(
                        label,
                        expanded_found,
                        expanded_confidence,
                        threshold,
                    )

                    if expanded_confidence > confidence:
                        return (
                            expanded_found,
                            expanded_match_info["center_full"],
                            expanded_confidence,
                            expanded_match_info,
                        )

    return found, match_info["center_full"], confidence, match_info


def find_template_candidates_in_box(
    img,
    template_path,
    region,
    threshold,
    label="custom_region",
    max_candidates=8,
):
    """
    Find multiple visually distinct template candidates inside one rectangle.
    """
    template = load_template(template_path)
    region_img = crop(img, region)

    if region_img is None:
        _write_log(f"REGION CROP FAILED: {label}")
        return []

    search_h, search_w = region_img.shape[:2]
    template_h, template_w = template.shape[:2]

    if template_h > search_h or template_w > search_w:
        return []

    result = cv2.matchTemplate(region_img, template, cv2.TM_CCOEFF_NORMED)
    result = result.copy()

    x1, y1, _, _ = clamp_region(img, region)
    suppress_radius = max(24, min(template_w, template_h))
    candidates = []

    while len(candidates) < max_candidates:
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        if max_val < threshold:
            break

        local_x, local_y = max_loc
        center_full = (
            x1 + local_x + template_w // 2,
            y1 + local_y + template_h // 2,
        )

        candidates.append({
            "center_full": center_full,
            "top_left_full": (x1 + local_x, y1 + local_y),
            "bottom_right_full": (x1 + local_x + template_w, y1 + local_y + template_h),
            "size": (template_w, template_h),
            "confidence": float(max_val),
            "template_path": template_path,
            "region_name": label,
        })

        mask_x1 = max(0, local_x - suppress_radius)
        mask_y1 = max(0, local_y - suppress_radius)
        mask_x2 = min(result.shape[1], local_x + suppress_radius + 1)
        mask_y2 = min(result.shape[0], local_y + suppress_radius + 1)
        result[mask_y1:mask_y2, mask_x1:mask_x2] = -1.0

    if not candidates:
        retry_reason = get_expanded_roi_retry_reason()

        if retry_reason is not None:
            expanded_region = expand_region_for_retry(img, region)
            original_region = clamp_region(img, region)

            if (
                expanded_region is not None
                and original_region is not None
                and not regions_equal(expanded_region, original_region)
            ):
                log_expanded_roi_retry_start(
                    label,
                    template_path,
                    original_region,
                    expanded_region,
                    retry_reason,
                )
                expanded_img = crop(img, expanded_region)

                if expanded_img is not None:
                    search_h, search_w = expanded_img.shape[:2]

                    if template_h <= search_h and template_w <= search_w:
                        result = cv2.matchTemplate(expanded_img, template, cv2.TM_CCOEFF_NORMED)
                        result = result.copy()
                        x1, y1, _, _ = expanded_region

                        while len(candidates) < max_candidates:
                            _, max_val, _, max_loc = cv2.minMaxLoc(result)

                            if max_val < threshold:
                                break

                            local_x, local_y = max_loc
                            center_full = (
                                x1 + local_x + template_w // 2,
                                y1 + local_y + template_h // 2,
                            )

                            candidates.append({
                                "center_full": center_full,
                                "top_left_full": (x1 + local_x, y1 + local_y),
                                "bottom_right_full": (
                                    x1 + local_x + template_w,
                                    y1 + local_y + template_h,
                                ),
                                "size": (template_w, template_h),
                                "confidence": float(max_val),
                                "template_path": template_path,
                                "region_name": label,
                                "roi_expanded": True,
                                "original_roi": original_region,
                                "expanded_roi": expanded_region,
                                "retry_reason": retry_reason,
                            })

                            mask_x1 = max(0, local_x - suppress_radius)
                            mask_y1 = max(0, local_y - suppress_radius)
                            mask_x2 = min(result.shape[1], local_x + suppress_radius + 1)
                            mask_y2 = min(result.shape[0], local_y + suppress_radius + 1)
                            result[mask_y1:mask_y2, mask_x1:mask_x2] = -1.0

                        best_confidence = max(
                            (candidate["confidence"] for candidate in candidates),
                            default=0.0,
                        )
                        log_expanded_roi_retry_result(
                            label,
                            bool(candidates),
                            best_confidence,
                            threshold,
                        )

    return candidates


def detect_current_stash_page(img, stash_tab_templates, region, threshold):
    best = {
        "stash": None,
        "center": None,
        "confidence": 0.0,
        "match_info": None,
    }

    for stash_name, template_path in stash_tab_templates.items():
        _, center, confidence, match_info = find_template_in_box(
            img,
            template_path,
            region,
            threshold,
            label=f"stash_tab_{stash_name}",
        )

        if confidence > best["confidence"]:
            best = {
                "stash": stash_name,
                "center": center,
                "confidence": confidence,
                "match_info": match_info,
                "template_path": template_path,
            }

    best["detected"] = best["confidence"] >= threshold and best["stash"] is not None
    best["threshold"] = threshold
    return best


def find_storage_anchor(img, anchor_template_path, region, threshold, label="storage_anchor"):
    found, center, confidence, match_info = find_template_in_box(
        img,
        anchor_template_path,
        region,
        threshold,
        label=label,
    )
    return {
        "found": found,
        "center": center,
        "confidence": confidence,
        "match_info": match_info,
        "threshold": threshold,
        "template_path": anchor_template_path,
        "label": label,
    }


def build_stash_last_slot_region(anchor_center, offset_x, offset_y, width, height):
    if anchor_center is None:
        return None

    center_x = int(round(anchor_center[0] + offset_x))
    center_y = int(round(anchor_center[1] + offset_y))
    half_w = int(round(width / 2))
    half_h = int(round(height / 2))
    return (
        center_x - half_w,
        center_y - half_h,
        center_x - half_w + int(width),
        center_y - half_h + int(height),
    )


def build_storage_grid_slot_regions(
    anchor_center,
    offset_x,
    offset_y,
    slot_width,
    slot_height,
    gap_x,
    gap_y,
    rows,
    cols,
):
    if anchor_center is None:
        return []

    first_center_x = int(round(anchor_center[0] + offset_x))
    first_center_y = int(round(anchor_center[1] + offset_y))
    pitch_x = int(slot_width + gap_x)
    pitch_y = int(slot_height + gap_y)
    half_w = int(round(slot_width / 2))
    half_h = int(round(slot_height / 2))
    slots = []

    for row in range(rows):
        for col in range(cols):
            center_x = first_center_x + col * pitch_x
            center_y = first_center_y + row * pitch_y
            slots.append({
                "index": row * cols + col + 1,
                "row": row + 1,
                "col": col + 1,
                "center": (center_x, center_y),
                "region": (
                    center_x - half_w,
                    center_y - half_h,
                    center_x - half_w + int(slot_width),
                    center_y - half_h + int(slot_height),
                ),
            })

    return slots


def save_stash_last_slot_debug_crop(img, region, status, confidence, threshold):
    if _VISUAL_GET_DEBUG_DIR is None:
        return None

    debug_dir = _VISUAL_GET_DEBUG_DIR()
    debug_dir.mkdir(parents=True, exist_ok=True)
    crop_img = crop(img, region)

    if crop_img is None:
        return None

    path = debug_dir / "stash_last_slot_debug.png"
    cv2.imwrite(str(path), crop_img)
    _write_log(
        f"Stash last-slot debug crop saved | path={path} | "
        f"status={status} | confidence={confidence:.2f} | threshold={threshold:.2f}"
    )
    return path


def save_stash_last_slot_diagnostics(
    img,
    region,
    anchor_center,
    anchor_match_info,
    anchor_label,
    status,
    confidence,
    threshold,
    reason,
):
    if _VISUAL_GET_DEBUG_DIR is None:
        return None, None

    debug_dir = _VISUAL_GET_DEBUG_DIR()
    debug_dir.mkdir(parents=True, exist_ok=True)
    crop_img = crop(img, region)
    crop_path = None

    if crop_img is not None:
        crop_path = debug_dir / "stash_last_slot_crop.png"
        cv2.imwrite(str(crop_path), crop_img)

    annotated_path = debug_dir / "stash_last_slot_annotated.png"
    annotated = img.copy()

    if anchor_match_info is not None:
        top_left = anchor_match_info.get("top_left_full")
        bottom_right = anchor_match_info.get("bottom_right_full")

        if top_left is not None and bottom_right is not None:
            cv2.rectangle(annotated, top_left, bottom_right, (255, 0, 255), 2)

    if anchor_center is not None:
        anchor_x, anchor_y = int(anchor_center[0]), int(anchor_center[1])
        cv2.drawMarker(
            annotated,
            (anchor_x, anchor_y),
            (255, 0, 255),
            markerType=cv2.MARKER_CROSS,
            markerSize=22,
            thickness=2,
        )
        cv2.putText(
            annotated,
            anchor_label or "storage_anchor",
            (anchor_x + 8, max(18, anchor_y - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 0, 255),
            2,
            cv2.LINE_AA,
        )

    if region is not None:
        x1, y1, x2, y2 = region
        color = {
            "blank": (0, 255, 0),
            "occupied": (0, 0, 255),
            "uncertain": (0, 255, 255),
        }.get(status, (255, 255, 255))
        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
        label = (
            f"49th slot {status} "
            f"conf={confidence:.2f}/{threshold:.2f}"
        )
        cv2.putText(
            annotated,
            label,
            (x1, max(18, y1 - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            color,
            2,
            cv2.LINE_AA,
        )

    cv2.imwrite(str(annotated_path), annotated)
    _write_log(
        f"Stash last-slot diagnostics saved | crop={crop_path} | "
        f"annotated={annotated_path} | status={status} | "
        f"confidence={confidence:.2f} | threshold={threshold:.2f} | reason={reason}"
    )
    return crop_path, annotated_path


def save_stash_grid_diagnostics(
    img,
    anchor_center,
    anchor_match_info,
    slots,
    status,
    blank_count,
    occupied_count,
    uncertain_count,
    best_blank_confidence,
    blank_threshold,
    reason,
):
    if _VISUAL_GET_DEBUG_DIR is None:
        return None

    debug_dir = _VISUAL_GET_DEBUG_DIR()
    debug_dir.mkdir(parents=True, exist_ok=True)
    annotated_path = debug_dir / "stash_grid_annotated.png"
    annotated = img.copy()

    if anchor_match_info is not None:
        top_left = anchor_match_info.get("top_left_full")
        bottom_right = anchor_match_info.get("bottom_right_full")

        if top_left is not None and bottom_right is not None:
            cv2.rectangle(annotated, top_left, bottom_right, (255, 0, 255), 2)

    if anchor_center is not None:
        anchor_x, anchor_y = int(anchor_center[0]), int(anchor_center[1])
        cv2.drawMarker(
            annotated,
            (anchor_x, anchor_y),
            (255, 0, 255),
            markerType=cv2.MARKER_CROSS,
            markerSize=22,
            thickness=2,
        )
        cv2.putText(
            annotated,
            "stash_sort",
            (anchor_x + 8, max(18, anchor_y - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 0, 255),
            2,
            cv2.LINE_AA,
        )

    for slot in slots:
        region = slot.get("region")

        if region is None:
            continue

        x1, y1, x2, y2 = region
        slot_status = slot.get("status")
        color = {
            "blank": (0, 255, 0),
            "occupied": (0, 0, 255),
            "uncertain": (0, 255, 255),
            "invalid": (128, 128, 128),
        }.get(slot_status, (255, 255, 255))
        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 1)

        if slot_status == "blank":
            cv2.putText(
                annotated,
                str(slot.get("index")),
                (x1 + 2, min(y2 - 3, y1 + 14)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.38,
                color,
                1,
                cv2.LINE_AA,
            )

    summary_lines = [
        f"storage_grid {status}",
        f"blank={blank_count} occupied={occupied_count} uncertain={uncertain_count}",
        f"best_blank={best_blank_confidence:.2f}/{blank_threshold:.2f}",
        f"reason={reason}",
    ]
    y = 28

    for line in summary_lines:
        cv2.putText(
            annotated,
            line,
            (12, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.58,
            (0, 0, 0),
            3,
            cv2.LINE_AA,
        )
        cv2.putText(
            annotated,
            line,
            (12, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.58,
            (0, 255, 255),
            1,
            cv2.LINE_AA,
        )
        y += 24

    cv2.imwrite(str(annotated_path), annotated)
    _write_log(
        f"Stash grid diagnostics saved | annotated={annotated_path} | "
        f"status={status} | blank_count={blank_count} | "
        f"occupied_count={occupied_count} | uncertain_count={uncertain_count} | "
        f"best_blank_confidence={best_blank_confidence:.2f} | reason={reason}"
    )
    return annotated_path


def crop_center_region(img, width, height):
    if img is None or img.size == 0:
        return None

    h, w = img.shape[:2]
    crop_w = min(int(width), w)
    crop_h = min(int(height), h)

    if crop_w <= 0 or crop_h <= 0:
        return None

    x1 = max(0, (w - crop_w) // 2)
    y1 = max(0, (h - crop_h) // 2)
    return img[y1:y1 + crop_h, x1:x1 + crop_w]


def classify_storage_slot_content(slot_img, blank_template, blank_threshold, uncertain_margin):
    evidence = {
        "status": "uncertain",
        "confidence": 0.0,
        "template_confidence": 0.0,
        "visual_blank": False,
        "visual_occupied": False,
        "reason": "unclassified",
        "features": {},
    }

    if slot_img is None or slot_img.size == 0:
        evidence["reason"] = "slot_crop_empty"
        return evidence

    slot_h, slot_w = slot_img.shape[:2]
    template_h, template_w = blank_template.shape[:2]
    template_confidence = None

    if template_h <= slot_h and template_w <= slot_w:
        match = match_template(slot_img, blank_template)
        template_confidence = match["confidence"]
        evidence["confidence"] = template_confidence
        evidence["template_confidence"] = template_confidence
    else:
        evidence["reason"] = (
            f"blank_template_larger_than_slot_roi:"
            f"template=({template_w}x{template_h}) slot=({slot_w}x{slot_h})"
        )

    inner_size = min(30, max(8, min(slot_w, slot_h) - 8))
    inner = crop_center_region(slot_img, inner_size, inner_size)

    if inner is None or inner.size == 0:
        evidence["reason"] = "inner_slot_crop_empty"
        return evidence

    hsv = cv2.cvtColor(inner, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(inner, cv2.COLOR_BGR2GRAY)
    saturation = hsv[:, :, 1]
    brightness = hsv[:, :, 2]
    pixel_count = max(1, inner.shape[0] * inner.shape[1])

    mean_brightness = float(np.mean(brightness))
    mean_saturation = float(np.mean(saturation))
    gray_std = float(np.std(gray))
    colored_ratio = float(np.count_nonzero((saturation > 45) & (brightness > 45)) / pixel_count)
    bright_ratio = float(np.count_nonzero(brightness > 105) / pixel_count)
    very_bright_ratio = float(np.count_nonzero(brightness > 145) / pixel_count)
    edges = cv2.Canny(gray, 35, 110)
    edge_density = float(np.count_nonzero(edges) / pixel_count)

    evidence["features"] = {
        "inner_size": inner.shape[:2],
        "mean_brightness": mean_brightness,
        "mean_saturation": mean_saturation,
        "gray_std": gray_std,
        "colored_ratio": colored_ratio,
        "bright_ratio": bright_ratio,
        "very_bright_ratio": very_bright_ratio,
        "edge_density": edge_density,
    }

    blank_by_template = (
        template_confidence is not None
        and template_confidence >= blank_threshold
    )
    visual_occupied = (
        colored_ratio >= 0.13
        or bright_ratio >= 0.18
        or very_bright_ratio >= 0.08
        or edge_density >= 0.15
        or gray_std >= 38.0
    )
    visual_blank = (
        mean_brightness <= 95.0
        and mean_saturation <= 55.0
        and colored_ratio <= 0.09
        and bright_ratio <= 0.14
        and very_bright_ratio <= 0.05
        and edge_density <= 0.12
        and gray_std <= 35.0
    )

    evidence["visual_blank"] = visual_blank
    evidence["visual_occupied"] = visual_occupied

    if blank_by_template or (visual_blank and not visual_occupied):
        evidence["status"] = "blank"
        evidence["reason"] = (
            "blank_template_matched_slot_roi"
            if blank_by_template
            else "inner_slot_visual_features_look_blank"
        )
    elif visual_occupied:
        evidence["status"] = "occupied"
        evidence["reason"] = "inner_slot_visual_features_show_item"
    else:
        evidence["status"] = "uncertain"
        evidence["reason"] = "slot_visual_features_uncertain"

    return evidence


def check_stash_grid_space(
    img,
    blank_template_path,
    anchor_template_path,
    search_region,
    anchor_threshold,
    blank_threshold,
    uncertain_margin,
    grid_offset_x,
    grid_offset_y,
    slot_width,
    slot_height,
    gap_x,
    gap_y,
    rows,
    cols,
    save_debug=False,
    force_debug_on_failure=False,
):
    anchor = find_storage_anchor(
        img,
        anchor_template_path,
        search_region,
        anchor_threshold,
        label="stash_sort",
    )
    evidence = {
        "status": "uncertain",
        "has_space": None,
        "blank_count": 0,
        "occupied_count": 0,
        "uncertain_count": 0,
        "best_blank_confidence": 0.0,
        "threshold": blank_threshold,
        "uncertain_margin": uncertain_margin,
        "anchor": anchor,
        "slots": [],
        "grid_first_slot_center": None,
        "grid_geometry": {
            "offset": (grid_offset_x, grid_offset_y),
            "slot_size": (slot_width, slot_height),
            "gap": (gap_x, gap_y),
            "rows": rows,
            "cols": cols,
        },
        "debug_grid_annotated_path": None,
        "reason": None,
    }
    _write_log(
        f"Stash grid anchor check | label={anchor.get('label')} | "
        f"found={anchor.get('found')} | center={anchor.get('center')} | "
        f"confidence={anchor.get('confidence', 0.0):.2f} | "
        f"threshold={anchor_threshold:.2f} | template={anchor_template_path}"
    )

    if not anchor["found"]:
        evidence["reason"] = "stash_sort_not_found"
        return evidence

    if rows <= 0 or cols <= 0 or slot_width <= 0 or slot_height <= 0:
        evidence["reason"] = "invalid_grid_geometry"
        return evidence

    raw_slots = build_storage_grid_slot_regions(
        anchor["center"],
        grid_offset_x,
        grid_offset_y,
        slot_width,
        slot_height,
        gap_x,
        gap_y,
        rows,
        cols,
    )

    if raw_slots:
        evidence["grid_first_slot_center"] = raw_slots[0]["center"]

    _write_log(
        f"Stash grid calculated | anchor_center={anchor.get('center')} | "
        f"first_slot_center={evidence['grid_first_slot_center']} | "
        f"offset=({grid_offset_x}, {grid_offset_y}) | "
        f"slot=({slot_width}x{slot_height}) | gap=({gap_x},{gap_y}) | "
        f"rows={rows} | cols={cols}"
    )

    blank_template = load_template(blank_template_path)

    for raw_slot in raw_slots:
        slot = dict(raw_slot)
        slot_region = clamp_region(img, raw_slot["region"])
        slot["region"] = slot_region
        slot["confidence"] = 0.0
        slot["template_confidence"] = 0.0
        slot["features"] = {}

        if slot_region is None:
            slot["status"] = "invalid"
            slot["reason"] = "slot_region_out_of_bounds"
            evidence["uncertain_count"] += 1
            evidence["slots"].append(slot)
            continue

        slot_img = crop(img, slot_region)

        if slot_img is None or slot_img.size == 0:
            slot["status"] = "invalid"
            slot["reason"] = "slot_crop_failed"
            evidence["uncertain_count"] += 1
            evidence["slots"].append(slot)
            continue

        slot_evidence = classify_storage_slot_content(
            slot_img,
            blank_template,
            blank_threshold,
            uncertain_margin,
        )
        confidence = slot_evidence["confidence"]
        slot["confidence"] = confidence
        slot["template_confidence"] = slot_evidence["template_confidence"]
        slot["features"] = slot_evidence["features"]
        slot["reason"] = slot_evidence["reason"]
        slot["visual_blank"] = slot_evidence["visual_blank"]
        slot["visual_occupied"] = slot_evidence["visual_occupied"]
        slot["status"] = slot_evidence["status"]
        evidence["best_blank_confidence"] = max(evidence["best_blank_confidence"], confidence)

        if slot["status"] == "blank":
            slot["status"] = "blank"
            evidence["blank_count"] += 1
        elif slot["status"] == "occupied":
            evidence["occupied_count"] += 1
        else:
            slot["status"] = "uncertain"
            evidence["uncertain_count"] += 1

        evidence["slots"].append(slot)

    if evidence["blank_count"] > 0:
        evidence["status"] = "available"
        evidence["has_space"] = True
        evidence["reason"] = "blank_slot_found_in_storage_grid"
    elif evidence["uncertain_count"] == 0 and evidence["occupied_count"] == rows * cols:
        evidence["status"] = "full"
        evidence["has_space"] = False
        evidence["reason"] = "no_blank_slots_found_in_storage_grid"
    else:
        evidence["status"] = "uncertain"
        evidence["has_space"] = None
        evidence["reason"] = "storage_grid_has_uncertain_slots"

    _write_log(
        f"Stash grid blank scan | status={evidence['status']} | "
        f"blank_count={evidence['blank_count']} | "
        f"occupied_count={evidence['occupied_count']} | "
        f"uncertain_count={evidence['uncertain_count']} | "
        f"best_blank_confidence={evidence['best_blank_confidence']:.2f} | "
        f"blank_threshold={blank_threshold:.2f} | "
        f"uncertain_margin={uncertain_margin:.2f} | "
        f"classifier=template_or_inner_visual_features | reason={evidence['reason']}"
    )

    if save_debug or (force_debug_on_failure and evidence["status"] != "available"):
        evidence["debug_grid_annotated_path"] = save_stash_grid_diagnostics(
            img,
            anchor.get("center"),
            anchor.get("match_info"),
            evidence["slots"],
            evidence["status"],
            evidence["blank_count"],
            evidence["occupied_count"],
            evidence["uncertain_count"],
            evidence["best_blank_confidence"],
            blank_threshold,
            evidence["reason"],
        )

    return evidence


def check_stash_last_slot_blank(
    img,
    blank_template_path,
    anchor_template_path,
    search_region,
    anchor_threshold,
    blank_threshold,
    uncertain_margin,
    offset_x,
    offset_y,
    slot_width,
    slot_height,
    save_debug=False,
    anchor_label="storage_anchor",
    fallback_anchor_template_path=None,
    fallback_anchor_label="storage_anchor_fallback",
):
    anchor = find_storage_anchor(
        img,
        anchor_template_path,
        search_region,
        anchor_threshold,
        label=anchor_label,
    )

    evidence = {
        "status": "uncertain",
        "is_blank": None,
        "confidence": 0.0,
        "threshold": blank_threshold,
        "uncertain_margin": uncertain_margin,
        "slot_region": None,
        "anchor": anchor,
        "debug_crop_path": None,
        "debug_annotated_path": None,
        "reason": None,
    }

    _write_log(
        f"Stash storage anchor check | label={anchor.get('label')} | "
        f"found={anchor.get('found')} | "
        f"center={anchor.get('center')} | confidence={anchor.get('confidence', 0.0):.2f} | "
        f"threshold={anchor_threshold:.2f} | template={anchor_template_path}"
    )

    if not anchor["found"] and fallback_anchor_template_path:
        _write_log(
            f"Primary stash anchor not found; trying fallback anchor | "
            f"primary={anchor_template_path} | fallback={fallback_anchor_template_path}"
        )
        fallback_anchor = find_storage_anchor(
            img,
            fallback_anchor_template_path,
            search_region,
            anchor_threshold,
            label=fallback_anchor_label,
        )
        _write_log(
            f"Fallback stash anchor check | label={fallback_anchor.get('label')} | "
            f"found={fallback_anchor.get('found')} | "
            f"center={fallback_anchor.get('center')} | "
            f"confidence={fallback_anchor.get('confidence', 0.0):.2f} | "
            f"threshold={anchor_threshold:.2f} | template={fallback_anchor_template_path}"
        )

        if fallback_anchor["found"]:
            anchor = fallback_anchor
            evidence["anchor"] = anchor

    if not anchor["found"]:
        evidence["reason"] = f"{anchor_label}_not_found"
        return evidence

    slot_region = build_stash_last_slot_region(
        anchor["center"],
        offset_x,
        offset_y,
        slot_width,
        slot_height,
    )
    slot_region = clamp_region(img, slot_region)
    evidence["slot_region"] = slot_region
    _write_log(
        f"Stash 49th-slot ROI calculated | anchor_center={anchor.get('center')} | "
        f"anchor_label={anchor.get('label')} | "
        f"offset=({offset_x}, {offset_y}) | size=({slot_width}x{slot_height}) | "
        f"roi={slot_region}"
    )

    if slot_region is None:
        evidence["reason"] = "last_slot_region_out_of_bounds"
        return evidence

    slot_img = crop(img, slot_region)

    if slot_img is None or slot_img.size == 0:
        evidence["reason"] = "last_slot_crop_failed"
        return evidence

    blank_template = load_template(blank_template_path)
    template_h, template_w = blank_template.shape[:2]
    slot_h, slot_w = slot_img.shape[:2]

    if template_h > slot_h or template_w > slot_w:
        evidence["reason"] = (
            f"blank_template_larger_than_slot_roi:"
            f"template=({template_w}x{template_h}) slot=({slot_w}x{slot_h})"
        )
        evidence["debug_crop_path"] = save_stash_last_slot_debug_crop(
            img,
            slot_region,
            evidence["status"],
            evidence["confidence"],
            blank_threshold,
        )
        if save_debug:
            crop_path, annotated_path = save_stash_last_slot_diagnostics(
                img,
                slot_region,
                anchor.get("center"),
                anchor.get("match_info"),
                anchor.get("label"),
                evidence["status"],
                evidence["confidence"],
                blank_threshold,
                evidence["reason"],
            )
            evidence["debug_crop_path"] = crop_path or evidence["debug_crop_path"]
            evidence["debug_annotated_path"] = annotated_path
        return evidence

    match = match_template(slot_img, blank_template)
    confidence = match["confidence"]
    evidence["confidence"] = confidence
    occupied_threshold = max(0.0, blank_threshold - uncertain_margin)

    if confidence >= blank_threshold:
        evidence["status"] = "blank"
        evidence["is_blank"] = True
        evidence["reason"] = "blank_template_matched_last_slot_roi"
    elif confidence <= occupied_threshold:
        evidence["status"] = "occupied"
        evidence["is_blank"] = False
        evidence["reason"] = "blank_template_did_not_match_last_slot_roi"
    else:
        evidence["status"] = "uncertain"
        evidence["is_blank"] = None
        evidence["reason"] = "blank_match_in_uncertain_band"
        evidence["debug_crop_path"] = save_stash_last_slot_debug_crop(
            img,
            slot_region,
            evidence["status"],
            confidence,
            blank_threshold,
        )

    _write_log(
        f"Stash 49th-slot blank check | roi={slot_region} | "
        f"blank_confidence={confidence:.2f} | blank_threshold={blank_threshold:.2f} | "
        f"uncertain_margin={uncertain_margin:.2f} | status={evidence['status']} | "
        f"reason={evidence['reason']}"
    )

    if save_debug:
        crop_path, annotated_path = save_stash_last_slot_diagnostics(
            img,
            slot_region,
            anchor.get("center"),
            anchor.get("match_info"),
            anchor.get("label"),
            evidence["status"],
            confidence,
            blank_threshold,
            evidence["reason"],
        )
        evidence["debug_crop_path"] = crop_path or evidence["debug_crop_path"]
        evidence["debug_annotated_path"] = annotated_path

    return evidence


def detect_boss_warning(img, boss_warning_template):
    """
    Search battle_top and battle_bottom for the red boss WARNING effect.
    Uses BOTH red-pixel check and WARNING text template match.
    """
    battle_regions = ["battle_top", "battle_bottom"]

    best_result = {
        "detected": False,
        "region": None,
        "red_pixels": 0,
        "confidence": 0.0,
    }

    for region_name in battle_regions:
        region_img = crop(img, _VISUAL_REGIONS[region_name])

        if region_img is None:
            continue

        red_detected, red_pixels = detect_boss_warning_pixels(
            region_img,
            min_red_pixels=3000
        )

        warning_match = match_template(region_img, boss_warning_template)
        confidence = warning_match["confidence"]
        detected = red_detected and confidence >= _VISUAL_BOSS_WARNING_CONFIDENCE_THRESHOLD

        if confidence > best_result["confidence"]:
            best_result = {
                "detected": detected,
                "region": region_name,
                "red_pixels": red_pixels,
                "confidence": confidence,
                "match": warning_match,
            }

        if detected:
            return True, region_name, red_pixels, confidence

    return (
        best_result["detected"],
        best_result["region"],
        best_result["red_pixels"],
        best_result["confidence"],
    )


def detect_clear_screen(img, clear_template):
    """
    Detect the task CLEAR sign in the existing battle search regions.
    """
    global _VISUAL_LAST_CLEAR_DEBUG_LOG_TIME

    best_confidence = 0.0
    best_region_name = None
    best_match_info = None

    for region_name in _VISUAL_BATTLE_SEARCH_REGION_NAMES:
        region = _VISUAL_REGIONS[region_name]
        clamped = clamp_region(img, region)

        if clamped is None:
            continue

        x1, y1, x2, y2 = clamped
        region_img = img[y1:y2, x1:x2]
        match = match_template(region_img, clear_template)
        confidence = match["confidence"]

        if confidence > best_confidence:
            best_confidence = confidence
            best_region_name = region_name
            best_match_info = {
                "center_full": (x1 + match["center"][0], y1 + match["center"][1]),
                "top_left_full": (x1 + match["top_left"][0], y1 + match["top_left"][1]),
                "bottom_right_full": (x1 + match["bottom_right"][0], y1 + match["bottom_right"][1]),
                "size": match["size"],
                "confidence": confidence,
                "region_name": region_name,
                "template_path": _VISUAL_CLEAR_TEMPLATE_PATH,
            }

    clear_visible = best_confidence >= _VISUAL_CLEAR_MATCH_THRESHOLD

    current_time = time.time()
    if (
        best_confidence >= 0.50
        and current_time - _VISUAL_LAST_CLEAR_DEBUG_LOG_TIME >= 1.0
    ):
        _VISUAL_LAST_CLEAR_DEBUG_LOG_TIME = current_time
        _write_log(
            f"CLEAR match debug | "
            f"best_confidence={best_confidence:.2f} | "
            f"region={best_region_name} | "
            f"passed_threshold={clear_visible} | "
            f"threshold={_VISUAL_CLEAR_MATCH_THRESHOLD:.2f}"
        )

    return clear_visible, best_confidence, best_match_info


def collect_detection_snapshot(
    img,
    blue_template,
    brown_template,
    boss_warning_template,
    clear_template,
):
    detections = detect_all_chests(img, blue_template, brown_template)
    boss_visible, boss_region, boss_pixels, boss_confidence = detect_boss_warning(
        img,
        boss_warning_template,
    )
    clear_visible, clear_confidence, clear_match_info = detect_clear_screen(
        img,
        clear_template,
    )

    return DetectionSnapshot(
        detections=detections,
        boss_visible=boss_visible,
        boss_region=boss_region,
        boss_pixels=boss_pixels,
        boss_confidence=boss_confidence,
        clear_visible=clear_visible,
        clear_confidence=clear_confidence,
        clear_match_info=clear_match_info,
    )


def detect_level_in_map(
    img,
    level_template,
    threshold=None,
    route=None,
    context="level_search",
):
    """
    Detect target level text/template inside the map panel.

    Returns:
        found: bool
        info: dict or None
        confidence: float

    info contains:
        center_full
        top_left_full
        bottom_right_full
        size
    """
    if threshold is None:
        threshold = _NAV_LEVEL_MATCH_THRESHOLD

    search_region = _VISUAL_REGIONS["map_panel"]
    map_img = crop(img, search_region)

    if map_img is None:
        return False, None, 0.0

    match = match_template(map_img, level_template)
    confidence = match["confidence"]

    map_x1, map_y1, _, _ = clamp_region(img, search_region)

    center_x, center_y = match["center"]
    top_left_x, top_left_y = match["top_left"]
    bottom_right_x, bottom_right_y = match["bottom_right"]

    info = {
        "center_full": (
            map_x1 + center_x,
            map_y1 + center_y
        ),
        "top_left_full": (
            map_x1 + top_left_x,
            map_y1 + top_left_y
        ),
        "bottom_right_full": (
            map_x1 + bottom_right_x,
            map_y1 + bottom_right_y
        ),
        "size": match["size"],
        "confidence": confidence,
    }

    if confidence < threshold:
        retry_reason = get_expanded_roi_retry_reason()

        if retry_reason is not None:
            expanded_region = expand_region_for_retry(img, search_region)
            target_name = route.get("level") if route else "level"
            template_name = route.get("level_template", "level_template") if route else "level_template"

            if expanded_region is not None and not regions_equal(expanded_region, search_region):
                log_expanded_roi_retry_start(
                    f"level:{target_name}:{context}",
                    template_name,
                    search_region,
                    expanded_region,
                    retry_reason,
                )
                expanded_img = crop(img, expanded_region)

                if expanded_img is not None:
                    expanded_match = match_template(expanded_img, level_template)
                    expanded_confidence = expanded_match["confidence"]
                    ex1, ey1, _, _ = expanded_region
                    ex_center_x, ex_center_y = expanded_match["center"]
                    ex_top_left_x, ex_top_left_y = expanded_match["top_left"]
                    ex_bottom_right_x, ex_bottom_right_y = expanded_match["bottom_right"]
                    expanded_info = {
                        "center_full": (ex1 + ex_center_x, ey1 + ex_center_y),
                        "top_left_full": (ex1 + ex_top_left_x, ey1 + ex_top_left_y),
                        "bottom_right_full": (ex1 + ex_bottom_right_x, ey1 + ex_bottom_right_y),
                        "size": expanded_match["size"],
                        "confidence": expanded_confidence,
                        "roi_expanded": True,
                        "original_roi": search_region,
                        "expanded_roi": expanded_region,
                        "retry_reason": retry_reason,
                    }
                    expanded_found = expanded_confidence >= threshold
                    log_expanded_roi_retry_result(
                        f"level:{target_name}:{context}",
                        expanded_found,
                        expanded_confidence,
                        threshold,
                    )

                    if expanded_confidence > confidence:
                        return expanded_found, expanded_info, expanded_confidence

        return False, info, confidence

    return True, info, confidence


def find_level_dot_left_of_text(img, match_info, dot_template, threshold, dot_name="dot"):
    """
    Search for a dot state, white or green, immediately to the left of detected level text.
    """
    text_left, text_top = match_info["top_left_full"]
    text_right, text_bottom = match_info["bottom_right_full"]
    text_w, text_h = match_info["size"]
    _, text_center_y = match_info["center_full"]

    map_x1, map_y1, map_x2, map_y2 = _VISUAL_REGIONS["map_panel"]

    search_x1 = max(map_x1, text_left - int(1.8 * text_w))
    search_x2 = max(map_x1, text_left - 2)

    search_y1 = max(map_y1, text_top - int(2.8 * text_h))
    search_y2 = min(map_y2, text_bottom + int(2.8 * text_h))

    if search_x2 <= search_x1 or search_y2 <= search_y1:
        return False, None, 0.0

    search_img = crop(img, (search_x1, search_y1, search_x2, search_y2))

    if search_img is None:
        return False, None, 0.0

    search_h, search_w = search_img.shape[:2]
    template_h, template_w = dot_template.shape[:2]

    if template_h > search_h or template_w > search_w:
        return False, None, 0.0

    result = cv2.matchTemplate(search_img, dot_template, cv2.TM_CCOEFF_NORMED)
    result = result.copy()
    suppress_radius = max(8, min(template_w, template_h))
    candidates = []
    best_any_center = None
    best_any_conf = 0.0

    for _ in range(8):
        _, confidence, _, max_loc = cv2.minMaxLoc(result)

        if confidence <= 0:
            break

        local_x, local_y = max_loc
        dot_center_full = (
            search_x1 + local_x + template_w // 2,
            search_y1 + local_y + template_h // 2,
        )
        vertical_distance = abs(dot_center_full[1] - text_center_y)

        if confidence > best_any_conf:
            best_any_conf = float(confidence)
            best_any_center = dot_center_full

        if confidence >= threshold and vertical_distance <= _NAV_LEVEL_DOT_MAX_VERTICAL_DISTANCE:
            candidates.append({
                "center": dot_center_full,
                "confidence": float(confidence),
                "vertical_distance": vertical_distance,
            })

        mask_x1 = max(0, local_x - suppress_radius)
        mask_y1 = max(0, local_y - suppress_radius)
        mask_x2 = min(result.shape[1], local_x + suppress_radius + 1)
        mask_y2 = min(result.shape[0], local_y + suppress_radius + 1)
        result[mask_y1:mask_y2, mask_x1:mask_x2] = -1.0

        if confidence < threshold:
            break

    if candidates:
        best_candidate = min(
            candidates,
            key=lambda item: (item["vertical_distance"], -item["confidence"])
        )
        dot_center_full = best_candidate["center"]
        confidence = best_candidate["confidence"]
        vertical_distance = best_candidate["vertical_distance"]
    else:
        dot_center_full = best_any_center
        confidence = best_any_conf
        vertical_distance = (
            abs(dot_center_full[1] - text_center_y)
            if dot_center_full is not None
            else None
        )

    _write_log(
        f"DOT SEARCH DEBUG | type={dot_name} | "
        f"text_box=({text_left},{text_top})-({text_right},{text_bottom}) | "
        f"search_box=({search_x1},{search_y1})-({search_x2},{search_y2}) | "
        f"best_dot={dot_center_full} | "
        f"confidence={confidence:.2f} | threshold={threshold:.2f} | "
        f"text_center_y={text_center_y} | vertical_distance={vertical_distance} | "
        f"aligned_candidates={len(candidates)}"
    )

    if not candidates:
        return False, dot_center_full, confidence

    return True, dot_center_full, confidence


def check_selected_level_green_text(img, match_info):
    text_left, text_top = match_info["top_left_full"]
    text_right, text_bottom = match_info["bottom_right_full"]
    padding = 6

    region = clamp_region(
        img,
        (
            text_left - padding,
            text_top - padding,
            text_right + padding,
            text_bottom + padding,
        )
    )

    if region is None:
        return False, 0, 0.0

    crop_img = crop(img, region)

    if crop_img is None or crop_img.size == 0:
        return False, 0, 0.0

    hsv = cv2.cvtColor(crop_img, cv2.COLOR_BGR2HSV)
    lower = tuple(_NAV_SELECTED_LEVEL_GREEN_HSV_LOWER)
    upper = tuple(_NAV_SELECTED_LEVEL_GREEN_HSV_UPPER)
    mask = cv2.inRange(hsv, lower, upper)
    green_pixel_count = int(cv2.countNonZero(mask))
    total_pixels = int(mask.size)
    green_ratio = green_pixel_count / total_pixels if total_pixels else 0.0
    selected = (
        green_pixel_count >= _NAV_SELECTED_LEVEL_GREEN_PIXEL_MIN
        or green_ratio >= _NAV_SELECTED_LEVEL_GREEN_RATIO_MIN
    )

    return selected, green_pixel_count, green_ratio


def verify_current_level_selected_by_green_text(img, match_info, route, confidence, threshold):
    selected, green_pixel_count, green_ratio = check_selected_level_green_text(img, match_info)

    if selected:
        _write_log(
            f"NAV current level already selected by green text; skipping click/scroll | "
            f"route={route['level']} | level_confidence={confidence:.2f} | "
            f"threshold={threshold:.2f} | green_pixel_count={green_pixel_count} | "
            f"green_ratio={green_ratio:.3f}"
        )
        return True

    _write_log(
        f"NAV near match rejected; green text not detected | "
        f"route={route['level']} | level_confidence={confidence:.2f} | "
        f"threshold={threshold:.2f} | green_pixel_count={green_pixel_count} | "
        f"green_ratio={green_ratio:.3f}"
    )
    return False


def level_match_passes_expected_y(route, match_info, context):
    center_x, center_y = match_info["center_full"]
    expected_y_min = route.get("expected_y_min", None)
    expected_y_max = route.get("expected_y_max", None)

    if expected_y_min is not None and center_y < expected_y_min:
        delta = expected_y_min - center_y

        if delta <= _NAV_LEVEL_Y_POSITION_TOLERANCE_PX:
            _write_log(
                f"NAV Y position outside strict range but within tolerance; continuing with verification | "
                f"route={route['level']} | context={context} | "
                f"center_y={center_y} | expected_y_min={expected_y_min} | "
                f"delta={delta} | tolerance={_NAV_LEVEL_Y_POSITION_TOLERANCE_PX} | "
                f"confidence={match_info['confidence']:.2f}"
            )
            return True

        _write_log(
            f"NAV rejected level {route['level']} by Y position | "
            f"context={context} | "
            f"center_y={center_y} < expected_y_min={expected_y_min} | "
            f"delta={delta} | tolerance={_NAV_LEVEL_Y_POSITION_TOLERANCE_PX} | "
            f"confidence={match_info['confidence']:.2f}"
        )
        return False

    if expected_y_max is not None and center_y > expected_y_max:
        delta = center_y - expected_y_max

        if delta <= _NAV_LEVEL_Y_POSITION_TOLERANCE_PX:
            _write_log(
                f"NAV Y position outside strict range but within tolerance; continuing with verification | "
                f"route={route['level']} | context={context} | "
                f"center_y={center_y} | expected_y_max={expected_y_max} | "
                f"delta={delta} | tolerance={_NAV_LEVEL_Y_POSITION_TOLERANCE_PX} | "
                f"confidence={match_info['confidence']:.2f}"
            )
            return True

        _write_log(
            f"NAV rejected level {route['level']} by Y position | "
            f"context={context} | "
            f"center_y={center_y} > expected_y_max={expected_y_max} | "
            f"delta={delta} | tolerance={_NAV_LEVEL_Y_POSITION_TOLERANCE_PX} | "
            f"confidence={match_info['confidence']:.2f}"
        )
        return False

    return True


def find_best_difficulty_anchor(img):
    """
    Find the currently visible difficulty dropdown anchor inside map_panel.
    """
    best_name = None
    best_center = None
    best_confidence = 0.0
    best_info = None

    for diff_name, diff_templates in _NAV_DIFFICULTY_TEMPLATES.items():
        _, center, confidence, match_info = find_template_in_box(
            img,
            diff_templates["anchor"],
            _VISUAL_REGIONS["map_panel"],
            _NAV_DIFFICULTY_MATCH_THRESHOLD,
            label=f"difficulty_anchor_{diff_name}"
        )

        if confidence > best_confidence:
            best_name = diff_name
            best_center = center
            best_confidence = confidence
            best_info = match_info

    return best_name, best_center, best_confidence, best_info


def chapter_order_index(chapter):
    try:
        return _NAV_CHAPTER_ORDER.index(chapter)
    except ValueError:
        return None


def unique_points_by_x(points, tolerance=None):
    if tolerance is None:
        tolerance = _NAV_CHAPTER_TAB_CLUSTER_X_TOLERANCE

    unique = []

    for point in sorted(points, key=lambda item: item["center"][0]):
        if any(abs(point["center"][0] - existing["center"][0]) <= tolerance for existing in unique):
            continue

        unique.append(point)

    return unique


def point_inside_region(point, region):
    if point is None:
        return False

    x, y = point
    x1, y1, x2, y2 = region
    return x1 <= x <= x2 and y1 <= y <= y2


def build_chapter_geometry(
    selected_center=None,
    selected_confidence=0.0,
    template_identity=None,
    resolved_candidates=None,
):
    if not _NAV_CHAPTER_GEOMETRY_FALLBACK_ENABLED:
        return None

    resolved_candidates = resolved_candidates or []
    candidate_points = [
        {
            "center": item.get("center"),
            "chapter": item.get("chapter"),
            "confidence": item.get("confidence", 0.0),
            "source": "tab_candidate",
        }
        for item in resolved_candidates
        if item.get("center") is not None
        and item.get("confidence", 0.0) >= _NAV_CHAPTER_GEOMETRY_MIN_CONFIDENCE
    ]

    selected_point = None

    if selected_center is not None and selected_confidence >= _NAV_CHAPTER_GEOMETRY_MIN_CONFIDENCE:
        selected_point = {
            "center": selected_center,
            "chapter": template_identity,
            "confidence": selected_confidence,
            "source": "selected_template",
        }

    centers = {}
    source = None

    if selected_point is not None and len(candidate_points) >= 2:
        row_points = unique_points_by_x(candidate_points + [selected_point])

        if len(row_points) >= len(_NAV_CHAPTER_ORDER):
            row_points = sorted(row_points, key=lambda item: item["center"][0])[:len(_NAV_CHAPTER_ORDER)]
            centers = {
                chapter: row_points[index]["center"]
                for index, chapter in enumerate(_NAV_CHAPTER_ORDER)
            }
            source = "dynamic_tab_row_with_selected_center"

    if not centers and len(candidate_points) >= len(_NAV_CHAPTER_ORDER):
        row_points = unique_points_by_x(candidate_points)

        if len(row_points) >= len(_NAV_CHAPTER_ORDER):
            row_points = sorted(row_points, key=lambda item: item["center"][0])[:len(_NAV_CHAPTER_ORDER)]
            centers = {
                chapter: row_points[index]["center"]
                for index, chapter in enumerate(_NAV_CHAPTER_ORDER)
            }
            source = "dynamic_tab_row_candidates"

    if not centers and selected_point is not None and template_identity in _NAV_CHAPTER_ORDER:
        _write_log(
            f"Chapter geometry self-anchor skipped | "
            f"template_identity={template_identity} | "
            f"selected_center={selected_center} | "
            f"confidence={selected_confidence:.2f}"
        )

    if not centers:
        if _NAV_CHAPTER_GEOMETRY_REQUIRE_DYNAMIC_ANCHOR:
            return None

        return None

    map_region = _VISUAL_REGIONS["map_panel"]

    for chapter, center in centers.items():
        if not point_inside_region(center, map_region):
            _write_log(
                f"Chapter geometry calibration rejected | "
                f"reason=center_outside_map_panel | chapter={chapter} | center={center} | "
                f"centers={centers} | source={source}"
            )
            return None

    geometry = {
        "centers": centers,
        "source": source,
        "selected_center": selected_center,
        "selected_confidence": selected_confidence,
        "template_identity": template_identity,
        "candidate_count": len(candidate_points),
    }

    _write_log(
        f"Chapter geometry calibration | source={source} | "
        f"template_identity={template_identity} | selected_center={selected_center} | "
        f"confidence={selected_confidence:.2f} | centers={centers} | "
        f"candidate_count={len(candidate_points)}"
    )
    return geometry


def classify_chapter_by_geometry(point, confidence, geometry):
    if (
        not _NAV_CHAPTER_GEOMETRY_FALLBACK_ENABLED
        or geometry is None
        or point is None
        or confidence < _NAV_CHAPTER_GEOMETRY_MIN_CONFIDENCE
    ):
        return None, None

    best_chapter = None
    best_distance = None

    for chapter, center in geometry["centers"].items():
        distance = abs(point[0] - center[0])

        if best_distance is None or distance < best_distance:
            best_chapter = chapter
            best_distance = distance

    if best_distance is None or best_distance > _NAV_CHAPTER_GEOMETRY_TOLERANCE_PX:
        return None, best_distance

    return best_chapter, best_distance


def apply_chapter_geometry_identity(template_identity, selected_center, confidence, geometry):
    geometry_identity, distance = classify_chapter_by_geometry(
        selected_center,
        confidence,
        geometry,
    )

    if geometry_identity is None:
        return template_identity, False, distance

    if template_identity != geometry_identity:
        _write_log(
            f"Chapter identity conflict | template_identity={template_identity} | "
            f"geometry_identity={geometry_identity} | selected_center={selected_center} | "
            f"confidence={confidence:.2f} | distance={distance} | "
            f"centers={geometry.get('centers')} | source={geometry.get('source')}"
        )
        return geometry_identity, True, distance

    return template_identity, False, distance


def collect_chapter_tab_candidates(img):
    clusters = []

    for chapter, templates in _NAV_CHAPTER_TEMPLATES.items():
        candidates = find_template_candidates_in_box(
            img,
            templates["normal"],
            _VISUAL_REGIONS["map_panel"],
            _NAV_CHAPTER_TAB_CANDIDATE_THRESHOLD,
            label=f"{chapter}_normal_candidates",
            max_candidates=6,
        )

        for candidate in candidates:
            cx, cy = candidate["center_full"]
            matched_cluster = None

            for cluster in clusters:
                cluster_x, cluster_y = cluster["center"]

                if (
                    abs(cx - cluster_x) <= _NAV_CHAPTER_TAB_CLUSTER_X_TOLERANCE
                    and abs(cy - cluster_y) <= _NAV_CHAPTER_TAB_CLUSTER_Y_TOLERANCE
                ):
                    matched_cluster = cluster
                    break

            if matched_cluster is None:
                matched_cluster = {
                    "center": candidate["center_full"],
                    "scores": {},
                    "candidates": {},
                }
                clusters.append(matched_cluster)

            previous_score = matched_cluster["scores"].get(chapter, -1.0)

            if candidate["confidence"] > previous_score:
                matched_cluster["scores"][chapter] = candidate["confidence"]
                matched_cluster["candidates"][chapter] = candidate

    resolved = []

    for cluster in clusters:
        if not cluster["scores"]:
            continue

        best_chapter = max(cluster["scores"], key=cluster["scores"].get)
        best_confidence = cluster["scores"][best_chapter]
        best_candidate = cluster["candidates"][best_chapter]

        resolved.append({
            "chapter": best_chapter,
            "center": best_candidate["center_full"],
            "confidence": best_confidence,
            "scores": cluster["scores"],
        })

    resolved.sort(key=lambda item: item["center"][0])
    return resolved


def summarize_chapter_candidates(resolved):
    return " | ".join(
        f"{item['chapter']}@{item['center']}:{item['confidence']:.2f}"
        for item in resolved
    )


def find_current_chapter(img):
    """
    Identify the selected chapter by comparing selected-tab templates inside
    the visible map panel.
    """
    best_chapter = None
    best_center = None
    best_confidence = 0.0
    best_info = None

    for chapter, templates in _NAV_CHAPTER_TEMPLATES.items():
        _, center, confidence, match_info = find_template_in_box(
            img,
            templates["selected"],
            _VISUAL_REGIONS["map_panel"],
            _NAV_CHAPTER_MATCH_THRESHOLD,
            label=f"selected_{chapter}"
        )

        if confidence > best_confidence:
            best_chapter = chapter
            best_center = center
            best_confidence = confidence
            best_info = match_info

    resolved = collect_chapter_tab_candidates(img)
    geometry = build_chapter_geometry(
        selected_center=best_center,
        selected_confidence=best_confidence,
        template_identity=best_chapter,
        resolved_candidates=resolved,
    )
    resolved_chapter, geometry_used, geometry_distance = apply_chapter_geometry_identity(
        best_chapter,
        best_center,
        best_confidence,
        geometry,
    )

    if best_info is not None:
        best_info["template_identity"] = best_chapter
        best_info["geometry_identity"] = resolved_chapter if geometry_used else None
        best_info["geometry_used"] = geometry_used
        best_info["geometry_distance"] = geometry_distance
        best_info["chapter_geometry"] = geometry

    return resolved_chapter, best_center, best_confidence, best_info


def find_chapter_tab_candidate(img, target_chapter):
    """
    Resolve chapter tabs by clustering all normal-tab template candidates.
    The chosen target must be the strongest chapter identity in its cluster.
    """
    resolved = collect_chapter_tab_candidates(img)
    summary = summarize_chapter_candidates(resolved)
    _write_log(f"Chapter tab candidates | target={target_chapter} | {summary}")

    for item in resolved:
        if item["chapter"] == target_chapter and item["confidence"] >= _NAV_CHAPTER_AMBIGUOUS_MIN_CONFIDENCE:
            sorted_scores = sorted(
                item["scores"].items(),
                key=lambda score_item: score_item[1],
                reverse=True,
            )

            if len(sorted_scores) >= 2:
                best_chapter, best_score = sorted_scores[0]
                second_chapter, second_score = sorted_scores[1]

                if best_score - second_score <= _NAV_CHAPTER_CANDIDATE_AMBIGUITY_MARGIN:
                    _write_log(
                        f"Chapter candidate ambiguous | "
                        f"target={target_chapter} | best={best_chapter}:{best_score:.2f} | "
                        f"second={second_chapter}:{second_score:.2f} | "
                        f"margin={_NAV_CHAPTER_CANDIDATE_AMBIGUITY_MARGIN:.2f} | "
                        f"candidate_confidence={item['confidence']:.2f} | "
                        f"ambiguous_min_confidence={_NAV_CHAPTER_AMBIGUOUS_MIN_CONFIDENCE:.2f}"
                    )
                    save_visual_debug_artifacts(
                        img,
                        reason=f"chapter_candidate_ambiguous:{target_chapter}",
                        roi=_VISUAL_REGIONS["map_panel"],
                        target_name=target_chapter,
                        confidence=best_score,
                        threshold=_NAV_CHAPTER_MATCH_THRESHOLD,
                    )
                    return False, item["center"], item["confidence"], {
                        "resolved": resolved,
                        "ambiguous": True,
                        "target_candidate": item,
                        "sorted_scores": sorted_scores,
                        "best_chapter": best_chapter,
                        "best_score": best_score,
                        "second_chapter": second_chapter,
                        "second_score": second_score,
                    }

            if item["confidence"] >= _NAV_CHAPTER_MATCH_THRESHOLD:
                return True, item["center"], item["confidence"], item

    best_confidence = max((item["confidence"] for item in resolved), default=0.0)
    save_visual_debug_artifacts(
        img,
        reason=f"chapter_visual_state_ambiguous:{target_chapter}",
        roi=_VISUAL_REGIONS["map_panel"],
        target_name=target_chapter,
        confidence=best_confidence,
        threshold=_NAV_CHAPTER_MATCH_THRESHOLD,
    )
    return False, None, 0.0, {"resolved": resolved}


def empty_route_target_observation():
    return {
        "difficulty": None,
        "difficulty_confidence": 0.0,
        "chapter": None,
        "chapter_confidence": 0.0,
        "level_match_found": False,
        "level_selected": False,
        "level_strict_selected": False,
        "level_selected_evidence_passed": False,
        "level_confidence": 0.0,
        "level_route_threshold": 0.0,
        "level_center": None,
        "level_y_ok": False,
        "green_text_selected": False,
        "green_dot_selected": False,
        "green_dot_confidence": 0.0,
    }


def observe_route_target_state_from_image(img, route):
    observed = empty_route_target_observation()

    difficulty_name, _, difficulty_conf, _ = find_best_difficulty_anchor(img)
    chapter_name, _, chapter_conf, _ = find_current_chapter(img)

    observed["difficulty"] = difficulty_name
    observed["difficulty_confidence"] = difficulty_conf
    observed["chapter"] = chapter_name
    observed["chapter_confidence"] = chapter_conf

    level_template = load_template(route.get("level_template"))

    if level_template is None:
        observed["level_error"] = f"could not load template {route.get('level_template')}"
        return observed

    threshold = max(
        _NAV_LEVEL_STRONG_ACCEPT_THRESHOLD,
        route.get("level_match_threshold", _NAV_LEVEL_MATCH_THRESHOLD),
    )
    observed["level_route_threshold"] = threshold

    found, match_info, confidence = detect_level_in_map(
        img,
        level_template,
        threshold=threshold,
        route=route,
        context="target_invariant",
    )

    observed["level_match_found"] = found
    observed["level_confidence"] = confidence

    if match_info is not None:
        observed["level_center"] = match_info.get("center_full")
        observed["level_y_ok"] = level_match_passes_expected_y(
            route,
            match_info,
            "target_invariant",
        )

        green_text_selected, green_pixel_count, green_ratio = check_selected_level_green_text(
            img,
            match_info,
        )
        observed["green_text_selected"] = green_text_selected
        observed["green_pixel_count"] = green_pixel_count
        observed["green_ratio"] = green_ratio

        green_template = load_template(_NAV_LEVEL_DOT_GREEN_TEMPLATE)

        if green_template is not None:
            green_found, green_center, green_conf = find_level_dot_left_of_text(
                img,
                match_info,
                green_template,
                _NAV_LEVEL_DOT_GREEN_MATCH_THRESHOLD,
                dot_name="green_invariant",
            )
            observed["green_dot_selected"] = green_found
            observed["green_dot_center"] = green_center
            observed["green_dot_confidence"] = green_conf

    observed["level_strict_selected"] = (
        observed["level_match_found"]
        and observed["level_y_ok"]
        and (
            observed["green_text_selected"]
            or observed["green_dot_selected"]
        )
    )
    observed["level_selected_evidence_passed"] = route_invariant_selected_evidence_passes(
        route,
        observed,
    )
    observed["level_selected"] = (
        observed["level_strict_selected"]
        or observed["level_selected_evidence_passed"]
    )

    return observed


def route_target_identity_matches(route, observed):
    return (
        observed.get("difficulty") == route.get("difficulty")
        and observed.get("chapter") == route.get("chapter")
    )


def route_invariant_selected_evidence_passes(route, observed):
    if not _NAV_ROUTE_INVARIANT_ALLOW_SELECTED_EVIDENCE:
        return False

    level_confidence = observed.get("level_confidence", 0.0) or 0.0

    if level_confidence < _NAV_ROUTE_INVARIANT_LEVEL_CONFIDENCE_FLOOR:
        return False

    if _NAV_ROUTE_INVARIANT_REQUIRE_LEVEL_Y_OK and not observed.get("level_y_ok"):
        return False

    green_text_selected = bool(observed.get("green_text_selected"))
    green_dot_selected = bool(observed.get("green_dot_selected"))
    green_dot_confidence = observed.get("green_dot_confidence", 0.0) or 0.0
    aligned_green_dot_selected = (
        green_dot_selected
        and green_dot_confidence >= _NAV_ROUTE_INVARIANT_GREEN_DOT_MIN_CONFIDENCE
    )

    return green_text_selected or aligned_green_dot_selected


def route_target_invariant_passes(route, observed):
    return (
        route_target_identity_matches(route, observed)
        and observed.get("level_selected")
    )


def route_target_invariant_confidence_is_strong(observed):
    return (
        observed.get("difficulty_confidence", 0.0) >= _NAV_DIFFICULTY_MATCH_THRESHOLD
        and observed.get("chapter_confidence", 0.0) >= _NAV_CHAPTER_MATCH_THRESHOLD
    )
