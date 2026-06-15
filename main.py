# MAA Task Bar Hero
# Concept and direction by Marcus Xu.
# Built with Codex as a coding assistant.
# Shared for learning, experimentation, and automation research.

import time
from route_config import MAP_SCROLL_CHUNK_REPEAT, ROUTE
import winsound
from datetime import datetime
import cv2
from capture import find_window_by_title_keyword, capture_window, save_debug_screenshot
from detector import check_template_loadable, load_template, detect_chests_in_region, detect_boss_warning_pixels, match_template, detect_blue_text_pixels
from route_config import (
    ROUTE,
    AVAILABLE_LEVELS,
    ENABLE_ROUTE_NAVIGATION,
    MAP_SCROLL_CHUNK_REPEAT,
    MAP_SCROLL_CHUNKS_PER_DIRECTION,
    NAV_CLICK_DELAY_SECONDS,
    LEVEL_MATCH_THRESHOLD,
    LEVEL_DOT_WHITE_TEMPLATE,
    LEVEL_DOT_GREEN_TEMPLATE,
    LEVEL_DOT_WHITE_MATCH_THRESHOLD,
    LEVEL_DOT_GREEN_MATCH_THRESHOLD,
    DIFFICULTY_TEMPLATES,
    CHAPTER_TEMPLATES,
    DIFFICULTY_MATCH_THRESHOLD,
    CHAPTER_MATCH_THRESHOLD,
    CHEST_TIER_BREAKPOINTS,
    get_chest_tier_for_route,
)
import pyautogui
import win32gui
import json
import os
import sys
import traceback
import ctypes
import win32con
import win32api
from config import (
    CONFIG_FILE_NAME,
    get_base_dir,
    get_config,
    get_effective_thresholds,
    get_recognition_mode,
    get_threshold,
)

INVISIBLE_UNICODE_TRANSLATION = {
    ord("\u200b"): None,
    ord("\u200c"): None,
    ord("\u200d"): None,
    ord("\ufeff"): None,
}
unicode_sanitization_logged = False


def configure_console_encoding():
    for stream in (getattr(sys, "stdout", None), getattr(sys, "stderr", None)):
        if stream is None or not hasattr(stream, "reconfigure"):
            continue

        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def sanitize_text_for_output(value):
    global unicode_sanitization_logged

    text = str(value)
    sanitized = text.translate(INVISIBLE_UNICODE_TRANSLATION)

    if sanitized != text and not unicode_sanitization_logged:
        unicode_sanitization_logged = True
        safe_print("Sanitized invisible Unicode characters from log output")

    return sanitized


def safe_print(*args, **kwargs):
    sanitized_args = [sanitize_text_for_output(arg) for arg in args]

    try:
        print(*sanitized_args, **kwargs)
    except UnicodeEncodeError:
        fallback_args = [
            str(arg).encode("utf-8", errors="replace").decode("utf-8", errors="replace")
            for arg in sanitized_args
        ]

        try:
            print(*fallback_args, **kwargs)
        except UnicodeEncodeError:
            encoding = getattr(getattr(sys, "stdout", None), "encoding", None) or "utf-8"
            encoded_args = [
                str(arg).encode(encoding, errors="replace").decode(encoding, errors="replace")
                for arg in fallback_args
            ]
            print(*encoded_args, **kwargs)


configure_console_encoding()


def env_flag(name, default=False):
    value = os.environ.get(name)

    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "on"}


def config_bool(name, default):
    value = get_config().get(name, default)

    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}

    return bool(value)


def config_positive_int(name, default):
    value = get_config().get(name, default)

    try:
        value = int(value)
    except (TypeError, ValueError):
        return default

    return value if value > 0 else default


def config_non_negative_int(name, default):
    value = get_config().get(name, default)

    try:
        value = int(value)
    except (TypeError, ValueError):
        return default

    return value if value >= 0 else default


def config_int(name, default):
    value = get_config().get(name, default)

    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def config_optional_non_negative_int(name, default=None):
    value = get_config().get(name, default)

    if value is None:
        return default

    try:
        value = int(value)
    except (TypeError, ValueError):
        return default

    return value if value >= 0 else default


def config_non_negative_float(name, default):
    value = get_config().get(name, default)

    try:
        value = float(value)
    except (TypeError, ValueError):
        return default

    return value if value >= 0 else default


def config_hsv_triplet(name, default):
    value = get_config().get(name, default)

    if not isinstance(value, (list, tuple)) or len(value) != 3:
        return tuple(default)

    try:
        return tuple(max(0, min(255, int(component))) for component in value)
    except (TypeError, ValueError):
        return tuple(default)


def config_choice(name, default, allowed):
    value = str(get_config().get(name, default)).strip().lower()
    return value if value in allowed else default


def get_mouse_parking_strategy():
    value = str(
        get_config().get("mouse_parking_strategy", "static_client_point")
    ).strip().lower()

    if value in {"map_anchor", "anchor_map", "visual_anchor", "difficulty_anchor"}:
        return "static_client_point"

    if value in {"static_client_point", "default"}:
        return value

    return "static_client_point"


def coerce_non_negative_int(value, default):
    try:
        value = int(value)
    except (TypeError, ValueError):
        return default

    return value if value >= 0 else default


def maybe_save_debug_screenshot(img, folder, prefix):
    if not SAVE_DEBUG_SCREENSHOTS:
        return None

    return save_debug_screenshot(img, folder=folder, prefix=prefix)


def get_debug_dir():
    return get_base_dir() / "debug"


def save_visual_debug_artifacts(
    img,
    reason,
    roi=None,
    match_info=None,
    target_name=None,
    confidence=None,
    threshold=None,
):
    debug_dir = get_debug_dir()
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
        write_log(
            f"Visual debug artifacts saved | reason={reason} | "
            f"raw={raw_path} | annotated={annotated_path}"
        )
    else:
        write_log(
            f"Visual debug raw screenshot saved | reason={reason} | raw={raw_path}"
        )


##Parameters For Test Purpose##
WINDOW_KEYWORD = "TaskBarHero"
USE_BACKGROUND_INPUT = os.environ.get("MAATBH_INPUT_MODE", "foreground").lower() == "background"    
ENABLE_CLICKING = False
AUTO_OPEN_CONFIRMED_BLUE_CHEST = env_flag("MAATBH_AUTO_OPEN_BLUE", True)
SHOW_PREVIEW = env_flag("MAATBH_SHOW_PREVIEW", False)
NAVIGATE_ON_START = env_flag("MAATBH_NAVIGATE_ON_START", True)
STARTUP_NAV_RETRY_SECONDS = 5.0
MANUAL_NAV_COOLDOWN_SECONDS = 2.0
RECOGNITION_MODE = get_recognition_mode()
EFFECTIVE_RECOGNITION_THRESHOLDS = get_effective_thresholds()
CHAPTER_TAB_CANDIDATE_THRESHOLD = get_threshold("chapter_tab_candidate", 0.80)
CHAPTER_TAB_CLUSTER_X_TOLERANCE = 32
CHAPTER_TAB_CLUSTER_Y_TOLERANCE = 22
CLEAR_TEMPLATE_PATH = "templates/general/task_clear.png"
LEVEL_DOT_MAX_VERTICAL_DISTANCE = 25
CHAPTER_CANDIDATE_AMBIGUITY_MARGIN = 0.03
CHAPTER_AMBIGUOUS_CLICK_VERIFY_ENABLED = config_bool(
    "chapter_ambiguous_click_verify_enabled",
    True
)
CHAPTER_AMBIGUOUS_CLICK_MAX_ATTEMPTS = config_positive_int(
    "chapter_ambiguous_click_max_attempts",
    1
)
CHAPTER_AMBIGUOUS_MIN_CONFIDENCE = config_non_negative_float(
    "chapter_ambiguous_min_confidence",
    CHAPTER_TAB_CANDIDATE_THRESHOLD
)
CHAPTER_GEOMETRY_FALLBACK_ENABLED = config_bool("chapter_geometry_fallback_enabled", True)
CHAPTER_TAB_SPACING_PX = config_positive_int("chapter_tab_spacing_px", 64)
CHAPTER_GEOMETRY_TOLERANCE_PX = config_non_negative_int("chapter_geometry_tolerance_px", 18)
CHAPTER_GEOMETRY_MIN_CONFIDENCE = config_non_negative_float(
    "chapter_geometry_min_confidence",
    0.78,
)
CHAPTER_GEOMETRY_REQUIRE_DYNAMIC_ANCHOR = config_bool(
    "chapter_geometry_require_dynamic_anchor",
    True,
)
MOUSE_PARKING_ENABLED = config_bool("mouse_parking_enabled", True)
MOUSE_PARKING_X = config_optional_non_negative_int("mouse_parking_x", None)
MOUSE_PARKING_Y = config_optional_non_negative_int("mouse_parking_y", None)
MOUSE_PARKING_WAIT_SECONDS = config_non_negative_float("mouse_parking_wait_seconds", 0.15)
MOUSE_PARKING_BEFORE_CHAPTER_DETECTION = config_bool(
    "mouse_parking_before_chapter_detection",
    True
)
MOUSE_PARKING_BEFORE_DIFFICULTY_DETECTION = config_bool(
    "mouse_parking_before_difficulty_detection",
    True
)
MOUSE_PARKING_BEFORE_LEVEL_DETECTION = config_bool(
    "mouse_parking_before_level_detection",
    False
)
MOUSE_PARKING_MODE = config_choice(
    "mouse_parking_mode",
    "recovery_only",
    {"disabled", "recovery_only", "normal"},
)
MOUSE_PARKING_STRATEGY = get_mouse_parking_strategy()
MOUSE_PARKING_STATIC_X = config_non_negative_int("mouse_parking_static_x", 320)
MOUSE_PARKING_STATIC_Y = config_non_negative_int("mouse_parking_static_y", 120)
MOUSE_PARKING_FAIL_SAFE_RELOCATE_ENABLED = config_bool(
    "mouse_parking_fail_safe_relocate_enabled",
    True,
)
MOUSE_PARKING_FAIL_SAFE_MIN_SCREEN_MARGIN_PX = config_non_negative_int(
    "mouse_parking_fail_safe_min_screen_margin_px",
    60,
)
MOUSE_PARKING_FALLBACK_STATIC_X = config_non_negative_int("mouse_parking_fallback_static_x", 320)
MOUSE_PARKING_FALLBACK_STATIC_Y = config_non_negative_int("mouse_parking_fallback_static_y", 220)
MOUSE_PARKING_FALLBACK_STRATEGY = config_choice(
    "mouse_parking_fallback_strategy",
    "monitor_safe_point",
    {"monitor_safe_point", "window_safe_point"},
)
MOUSE_FAIL_SAFE_MARGIN_PX = config_non_negative_int("mouse_fail_safe_margin_px", 40)
MOUSE_MOVEMENT_FAIL_SAFE_POLICY = config_choice(
    "mouse_movement_fail_safe_policy",
    "return_failure",
    {"return_failure"},
)
COORDINATE_SCALING_ENABLED = config_bool("coordinate_scaling_enabled", True)
COORDINATE_SCALING_AUTO_DETECT = config_bool("coordinate_scaling_auto_detect", True)
COORDINATE_SCALING_TOLERANCE = config_non_negative_float("coordinate_scaling_tolerance", 0.05)
PAUSE_ON_SEVERE_COORDINATE_MISMATCH = config_bool("pause_on_severe_coordinate_mismatch", False)
DIFFICULTY_DROPDOWN_GEOMETRY_FALLBACK_ENABLED = config_bool(
    "difficulty_dropdown_geometry_fallback_enabled",
    True,
)
DIFFICULTY_DROPDOWN_ROW_SPACING_PX = config_non_negative_int(
    "difficulty_dropdown_row_spacing_px",
    43,
)
DIFFICULTY_DROPDOWN_FIRST_ROW_OFFSET_Y = config_non_negative_int(
    "difficulty_dropdown_first_row_offset_y",
    42,
)
DIFFICULTY_DROPDOWN_OPTION_X_OFFSET = config_int(
    "difficulty_dropdown_option_x_offset",
    0,
)
DIFFICULTY_DROPDOWN_GEOMETRY_VERIFY_AFTER_CLICK = config_bool(
    "difficulty_dropdown_geometry_verify_after_click",
    True,
)
SAME_TIER_SUBSTITUTION_ENABLED = config_bool("same_tier_substitution_enabled", True)
SAME_TIER_SUBSTITUTION_MAX_CANDIDATES = config_positive_int(
    "same_tier_substitution_max_candidates",
    3,
)
SAME_TIER_SUBSTITUTION_PREFER_FARM_PLAN_ROUTES = config_bool(
    "same_tier_substitution_prefer_farm_plan_routes",
    True,
)
SAME_TIER_SUBSTITUTION_ALLOW_CROSS_DIFFICULTY = config_bool(
    "same_tier_substitution_allow_cross_difficulty",
    True,
)
DYNAMIC_SCROLL_FOCUS_ENABLED = config_bool("dynamic_scroll_focus_enabled", True)
DYNAMIC_SCROLL_FOCUS_MIN_ANCHOR_CONFIDENCE = config_non_negative_float(
    "dynamic_scroll_focus_min_anchor_confidence",
    0.78,
)
DYNAMIC_SCROLL_FOCUS_Y = config_non_negative_int("dynamic_scroll_focus_y", 520)
DYNAMIC_SCROLL_FOCUS_EDGE_MARGIN_PX = config_non_negative_int(
    "dynamic_scroll_focus_edge_margin_px",
    40,
)
NAVIGATION_FAILURE_POLICY = config_choice(
    "navigation_failure_policy",
    "skip_route",
    {"skip_route", "pause"},
)
MAX_CONSECUTIVE_NAVIGATION_SKIPS = config_positive_int(
    "max_consecutive_navigation_skips",
    3,
)
SHOW_NAVIGATION_FAILURE_WARNING = config_bool("show_navigation_failure_warning", True)


# Adjust these if your current boxes are different.
# Format: (x1, y1, x2, y2)
REGIONS = {
    # Fixed panels
    "hero_panel": (0, 220, 640, 680),
    "map_panel": (340, 250, 970, 680),

    # Moving battle/search bands
    "battle_top": (0, 0, 975, 172),
    "battle_bottom": (0, 725, 970, 850),

    # Moving log bands
    "log_top": (0, 180, 970, 200),
    "log_bottom": (0, 690, 970, 715),
}

BATTLE_SEARCH_REGION_NAMES = [
    "battle_top",
    "battle_bottom",
]

REGION_COLORS = {
    "hero_panel": (0, 255, 0),          # green
    "map_panel": (0, 255, 0),           # green

    "battle_top": (255, 255, 0),        # cyan-ish in BGR
    "battle_bottom": (255, 255, 0),     # cyan-ish in BGR

    "log_top": (0, 165, 255),           # orange
    "log_bottom": (0, 165, 255),        # orange
}

REGIONS.update({
    # Route navigation searches inside the existing map panel. These aliases
    # are for matcher code only and are hidden from the preview overlay.
    "top_ui_area": REGIONS["map_panel"],
    "map_ui_area": REGIONS["map_panel"],

    # Backward-compatible aliases
    "difficulty_area": REGIONS["map_panel"],
    "difficulty_dropdown_area": REGIONS["map_panel"],
    "chapter_tabs_area": REGIONS["map_panel"],
})

PREVIEW_REGION_NAMES = {
    "hero_panel",
    "map_panel",
    "battle_top",
    "battle_bottom",
    "log_top",
    "log_bottom",
}

DETECTION_COLORS = {
    "blue": (255, 120, 0),      # blue-ish in BGR
    "brown": (0, 180, 255),     # orange/brown-ish in BGR
}


##GLOBAL VARIABLES##
STATE_FREEZE_AFTER_SWITCH = "freeze_after_switch"
STATE_STARTUP_NAVIGATION = "startup_navigation"
STATE_NAVIGATION_FAILED = "navigation_failed"
STATE_LOOK_FOR_BOSS = "look_for_boss"
STATE_LOOK_FOR_BLUE_DROP = "look_for_blue_drop"

bot_state = STATE_LOOK_FOR_BOSS
freeze_start_time = time.time()
FREEZE_SECONDS_AFTER_SWITCH = 5
POST_BOSS_DROP_WINDOW_SECONDS = 45
ORPHAN_BLUE_RECOVERY_SECONDS = 8
RECOVERY_REWARD_HANDLED = "reward_handled"

boss_seen_this_route = False
blue_drop_handled_this_route = False

MATCH_THRESHOLD = get_threshold("chest_match", 0.80)
BOSS_WARNING_CONFIDENCE_THRESHOLD = get_threshold("boss_warning", 0.85)
CLEAR_MATCH_THRESHOLD = get_threshold("clear_match", 0.85)
DIFFICULTY_MATCH_THRESHOLD = get_threshold("difficulty", DIFFICULTY_MATCH_THRESHOLD)
CHAPTER_MATCH_THRESHOLD = get_threshold("chapter_match", CHAPTER_MATCH_THRESHOLD)
LEVEL_DOT_WHITE_MATCH_THRESHOLD = get_threshold("level_dot_white", LEVEL_DOT_WHITE_MATCH_THRESHOLD)
LEVEL_DOT_GREEN_MATCH_THRESHOLD = get_threshold("level_dot_green", LEVEL_DOT_GREEN_MATCH_THRESHOLD)
LEVEL_STRONG_ACCEPT_THRESHOLD = max(0.88, get_threshold("current_level_detection", LEVEL_MATCH_THRESHOLD))
LEVEL_CAUTIOUS_ACCEPT_THRESHOLD = get_threshold("level_cautious_accept", None)
LEVEL_IGNORE_BELOW_THRESHOLD = get_threshold("level_ignore_below", None)
DEFAULT_MAX_TRIALS_IF_NO_CHEST = config_positive_int("default_max_trials_if_no_chest", 5)
DEFAULT_NO_CHEST_RETRIES = get_config().get(
    "default_no_chest_retries",
    max(0, DEFAULT_MAX_TRIALS_IF_NO_CHEST - 1)
)
POST_CLEAR_REWARD_WAIT_SECONDS = config_non_negative_float("post_clear_reward_wait_seconds", 3.0)
SAVE_DEBUG_SCREENSHOTS = config_bool("save_debug_screenshots", False)
MAX_ROUTE_NAVIGATION_RETRIES = config_non_negative_int("max_route_navigation_retries", 2)
NAVIGATION_RECOVERY_MAX_ATTEMPTS = config_positive_int("navigation_recovery_max_attempts", 2)
USE_FAST_BOUNDARY_SCROLL = config_bool("use_fast_boundary_scroll", True)
FAST_SCROLL_REPEAT = config_positive_int(
    "fast_scroll_repeat",
    MAP_SCROLL_CHUNK_REPEAT * MAP_SCROLL_CHUNKS_PER_DIRECTION
)
FAST_SCROLL_USE_BURST = config_bool("fast_scroll_use_burst", True)
FAST_SCROLL_BURST_COUNT = config_positive_int("fast_scroll_burst_count", 4)
FAST_SCROLL_PAUSE = config_non_negative_float("fast_scroll_pause", 0.25)
USE_EXPANDED_ROI_RETRY = config_bool("use_expanded_roi_retry", True)
EXPANDED_ROI_MARGIN_PX = config_non_negative_int("expanded_roi_margin_px", 48)
EXPANDED_ROI_SCALE_FACTOR = max(
    1.0,
    config_non_negative_float("expanded_roi_scale_factor", 1.15)
)
EXPANDED_ROI_ONLY_ON_UI_WARNING = config_bool("expanded_roi_only_on_ui_warning", True)
LEVEL_Y_POSITION_TOLERANCE_PX = config_non_negative_int("level_y_position_tolerance_px", 5)
ROUTE_INVARIANT_ALLOW_SELECTED_EVIDENCE = config_bool(
    "route_invariant_allow_selected_evidence",
    True,
)
ROUTE_INVARIANT_LEVEL_CONFIDENCE_FLOOR = config_non_negative_float(
    "route_invariant_level_confidence_floor",
    0.88,
)
ROUTE_INVARIANT_GREEN_DOT_MIN_CONFIDENCE = config_non_negative_float(
    "route_invariant_green_dot_min_confidence",
    0.75,
)
ROUTE_INVARIANT_REQUIRE_LEVEL_Y_OK = config_bool(
    "route_invariant_require_level_y_ok",
    True,
)
LEVEL_NEAR_MATCH_MARGIN = config_non_negative_float("level_near_match_margin", 0.10)
SELECTED_LEVEL_GREEN_PIXEL_MIN = config_non_negative_int("selected_level_green_pixel_min", 20)
SELECTED_LEVEL_GREEN_RATIO_MIN = config_non_negative_float("selected_level_green_ratio_min", 0.03)
SELECTED_LEVEL_GREEN_HSV_LOWER = config_hsv_triplet("selected_level_green_hsv_lower", [35, 40, 40])
SELECTED_LEVEL_GREEN_HSV_UPPER = config_hsv_triplet("selected_level_green_hsv_upper", [95, 255, 255])
ASSUME_MAILBOX_AFTER_MAX_TRIALS = config_bool("assume_mailbox_after_max_trials", True)
STOP_IF_BLUE_CHEST_FOUND = config_bool("stop_if_blue_chest_found", True)
BLUE_ALERT_COOLDOWN_SECONDS = 10
BROWN_LOG_COOLDOWN_SECONDS = 10
NO_CHEST_RESET_SECONDS = 2
last_boss_log_time = 0
BOSS_LOG_COOLDOWN_SECONDS = 5
last_manual_nav_time = 0

last_blue_log_seen_after_boss = 0
last_blue_chest_seen_after_boss = 0
orphan_blue_chest_first_seen = 0
no_chest_trial_count = 0
clear_handled_this_trial = False
last_clear_seen_time = 0
last_clear_debug_log_time = 0
post_clear_wait_started_at = 0
post_clear_best_conf = 0.0
chapter_ambiguous_click_attempts = {}
chapter_ambiguous_attempt_scope_id = 0
chapter_geometry_click_attempts = {}
CHAPTER_ORDER = ["chapter_1", "chapter_2", "chapter_3"]
skipped_routes_this_session = []
coordinate_scaling_status = None
consecutive_navigation_skips = 0
ENABLE_BEEP = env_flag("MAATBH_ENABLE_BEEP", False)
LOG_FILE_NAME = "detection_log.txt"
LOG_FILE = get_base_dir() / LOG_FILE_NAME
HEARTBEAT_LOG_INTERVAL_SECONDS = 30.0
ui_diagnostics_health_status = "UNKNOWN"
ui_diagnostics_suggests_roi_retry = False

mouse_x = 0
mouse_y = 0
last_blue_alert_time = 0
last_brown_log_time = 0
last_seen_chest_time = 0
last_state = "none"
current_route_index = 0
route_start_time = time.time()
route_navigation_retry_count = 0
route_navigation_retry_key = None
reward_navigation_interruption = None
current_cycle_number = 1
active_same_tier_substitute_route = None

last_route_status_print_time = 0
ROUTE_STATUS_PRINT_INTERVAL = 1.0
GAME_HWND = None
last_bot_status_signature = None
last_heartbeat_log_time = 0
last_frame_signature = None
last_frame_change_time = time.time()
last_frame_stale_warning_time = 0

last_blue_reward_signature = None
last_blue_reward_handled_time = 0
last_route_level_selection_evidence = None
# def print_route_status(chest_state):
#     global last_route_status_print_time

#     current_time = time.time()

#     if current_time - last_route_status_print_time < ROUTE_STATUS_PRINT_INTERVAL:
#         return

#     last_route_status_print_time = current_time

#     route = get_current_route()
#     elapsed, remaining, total = get_route_timing()

#     if remaining <= 0:
#         action = "READY TO SWITCH"
#     else:
#         action = "WAITING"

#     msg = (
#         f"Route {current_route_index + 1}/{len(ROUTE)} | "
#         f"{route['difficulty']} {route['chapter']} {route['level']} | "
#         f"Timer {format_seconds(elapsed)}/{format_seconds(total)} | "
#         f"Remaining {format_seconds(remaining)} | "
#         f"Chest {chest_state} | "
#         f"{action}"
#     )

#     print(msg.ljust(180), end="\r")


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def write_log(message):
    line = sanitize_text_for_output(f"[{now_str()}] {message}")
    safe_print("\n" + line)

    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except (OSError, PermissionError) as e:
        try:
            fallback_dir = get_base_dir() / "debug"
            fallback_dir.mkdir(parents=True, exist_ok=True)
            fallback_path = fallback_dir / "log_write_fallback.txt"
            with open(fallback_path, "a", encoding="utf-8", errors="replace") as f:
                f.write(
                    f"[{now_str()}] detection_log write failed: {type(e).__name__}: {e}\n"
                )
                f.write(line + "\n")
        except Exception:
            pass


def get_runtime_mode():
    return "exe" if getattr(sys, "frozen", False) else "source"


def get_config_path():
    return get_base_dir() / CONFIG_FILE_NAME


def get_farm_plan_path():
    return get_base_dir() / "farm_plan.json"


def safe_window_rect(hwnd):
    try:
        return win32gui.GetWindowRect(hwnd)
    except Exception as e:
        write_log(f"UI diagnostics unavailable: window rect failed | error={e}")
        return None


def safe_client_rect(hwnd):
    try:
        return win32gui.GetClientRect(hwnd)
    except Exception as e:
        write_log(f"UI diagnostics unavailable: client rect failed | error={e}")
        return None


def safe_client_origin(hwnd):
    try:
        return win32gui.ClientToScreen(hwnd, (0, 0))
    except Exception as e:
        write_log(f"UI diagnostics unavailable: client origin failed | error={e}")
        return None


def rect_size(rect):
    if rect is None:
        return None

    left, top, right, bottom = rect
    return right - left, bottom - top


def format_diag_value(value):
    return "unavailable" if value is None else str(value)


def get_dpi_diagnostics(hwnd):
    diagnostics = {
        "dpi_awareness_attempted": False,
        "process_dpi_awareness": None,
        "process_dpi_aware": None,
        "window_dpi": None,
        "monitor_dpi": None,
        "errors": [],
    }

    try:
        awareness = ctypes.c_int()
        result = ctypes.windll.shcore.GetProcessDpiAwareness(
            0,
            ctypes.byref(awareness)
        )
        diagnostics["process_dpi_awareness"] = (
            f"{awareness.value} (result={result})"
        )
    except Exception as e:
        diagnostics["errors"].append(f"GetProcessDpiAwareness unavailable: {e}")

    try:
        diagnostics["process_dpi_aware"] = bool(ctypes.windll.user32.GetProcessDPIAware())
    except Exception as e:
        diagnostics["errors"].append(f"GetProcessDPIAware unavailable: {e}")

    try:
        diagnostics["window_dpi"] = ctypes.windll.user32.GetDpiForWindow(hwnd)
    except Exception as e:
        diagnostics["errors"].append(f"GetDpiForWindow unavailable: {e}")

    try:
        monitor = win32api.MonitorFromWindow(hwnd, win32con.MONITOR_DEFAULTTONEAREST)
        dpi_x = ctypes.c_uint()
        dpi_y = ctypes.c_uint()
        result = ctypes.windll.shcore.GetDpiForMonitor(
            int(monitor),
            0,
            ctypes.byref(dpi_x),
            ctypes.byref(dpi_y),
        )
        diagnostics["monitor_dpi"] = f"({dpi_x.value}, {dpi_y.value}) (result={result})"
    except Exception as e:
        diagnostics["errors"].append(f"GetDpiForMonitor unavailable: {e}")

    return diagnostics


def get_monitor_diagnostics(hwnd, window_rect):
    diagnostics = {
        "screen_size": None,
        "monitor_count": None,
        "window_monitor": None,
        "negative_window_coords": False,
        "secondary_monitor_inferred": None,
        "errors": [],
    }

    try:
        screen_size = pyautogui.size()
        diagnostics["screen_size"] = (screen_size.width, screen_size.height)
    except Exception as e:
        diagnostics["errors"].append(f"pyautogui.size unavailable: {e}")

    try:
        monitors = win32api.EnumDisplayMonitors()
        diagnostics["monitor_count"] = len(monitors)
    except Exception as e:
        monitors = []
        diagnostics["errors"].append(f"EnumDisplayMonitors unavailable: {e}")

    if window_rect is not None:
        left, top, _, _ = window_rect
        diagnostics["negative_window_coords"] = left < 0 or top < 0

    try:
        monitor = win32api.MonitorFromWindow(hwnd, win32con.MONITOR_DEFAULTTONEAREST)
        monitor_info = win32api.GetMonitorInfo(monitor)
        diagnostics["window_monitor"] = {
            "device": monitor_info.get("Device"),
            "monitor": monitor_info.get("Monitor"),
            "work": monitor_info.get("Work"),
            "primary": bool(monitor_info.get("Flags", 0) & 1),
        }
        diagnostics["secondary_monitor_inferred"] = not diagnostics["window_monitor"]["primary"]
    except Exception as e:
        diagnostics["errors"].append(f"MonitorFromWindow/GetMonitorInfo unavailable: {e}")

    if diagnostics["secondary_monitor_inferred"] is None and diagnostics["monitor_count"] is not None:
        diagnostics["secondary_monitor_inferred"] = diagnostics["monitor_count"] > 1 and diagnostics["negative_window_coords"]

    return diagnostics


def get_screenshot_diagnostics(hwnd, window_size, client_size):
    diagnostics = {
        "screenshot_size": None,
        "screenshot_shape": None,
        "mean_brightness": None,
        "warnings": [],
        "error": None,
    }

    try:
        img = capture_window(hwnd)
    except Exception as e:
        diagnostics["error"] = str(e)
        return diagnostics

    if img is None:
        diagnostics["error"] = "capture_window returned None"
        return diagnostics

    height, width = img.shape[:2]
    diagnostics["screenshot_size"] = (width, height)
    diagnostics["screenshot_shape"] = img.shape

    mean_bgr = cv2.mean(img)[:3]
    diagnostics["mean_brightness"] = round(sum(mean_bgr) / 3, 2)

    if width <= 0 or height <= 0:
        diagnostics["warnings"].append("screenshot size is zero")

    if width < 100 or height < 100:
        diagnostics["warnings"].append("screenshot is unexpectedly small")

    if diagnostics["mean_brightness"] <= 1.0:
        diagnostics["warnings"].append("screenshot appears nearly black")

    if window_size is not None:
        window_width, window_height = window_size

        if abs(width - window_width) > 8 or abs(height - window_height) > 8:
            diagnostics["warnings"].append(
                f"screenshot size differs from window size {window_size}"
            )

    if client_size is not None:
        client_width, client_height = client_size

        if width < client_width - 8 or height < client_height - 8:
            diagnostics["warnings"].append(
                f"screenshot smaller than client size {client_size}"
            )

    return diagnostics


def safe_ratio(numerator, denominator):
    if numerator is None or denominator is None or denominator == 0:
        return None

    return round(numerator / denominator, 3)


def parse_dpi_pair(value):
    if value is None:
        return None

    if isinstance(value, tuple) and len(value) >= 2:
        return value[0], value[1]

    if isinstance(value, str) and value.startswith("("):
        try:
            pair_text = value.split(")", 1)[0].strip("(")
            x_text, y_text = pair_text.split(",", 1)
            return int(x_text.strip()), int(y_text.strip())
        except (ValueError, IndexError):
            return None

    return None


def build_ui_health_classification(
    window_size,
    client_size,
    screenshot_info,
    monitor_info,
    dpi_info,
):
    screenshot_size = screenshot_info.get("screenshot_size")
    ratios = {
        "screenshot_width_to_client_width": None,
        "screenshot_height_to_client_height": None,
        "screenshot_width_to_window_width": None,
        "screenshot_height_to_window_height": None,
    }

    if screenshot_size is not None:
        screenshot_width, screenshot_height = screenshot_size

        if client_size is not None:
            client_width, client_height = client_size
            ratios["screenshot_width_to_client_width"] = safe_ratio(
                screenshot_width,
                client_width,
            )
            ratios["screenshot_height_to_client_height"] = safe_ratio(
                screenshot_height,
                client_height,
            )

        if window_size is not None:
            window_width, window_height = window_size
            ratios["screenshot_width_to_window_width"] = safe_ratio(
                screenshot_width,
                window_width,
            )
            ratios["screenshot_height_to_window_height"] = safe_ratio(
                screenshot_height,
                window_height,
            )

    warnings = list(screenshot_info.get("warnings", []))
    error = screenshot_info.get("error")
    mean_brightness = screenshot_info.get("mean_brightness")
    window_dpi = dpi_info.get("window_dpi")
    monitor_dpi = parse_dpi_pair(dpi_info.get("monitor_dpi"))
    scaled_dpi = isinstance(window_dpi, int) and window_dpi not in (0, 96)

    if monitor_dpi is not None and monitor_dpi != (96, 96):
        scaled_dpi = True

    window_ratio_bad = False
    window_width_ratio = ratios["screenshot_width_to_window_width"]
    window_height_ratio = ratios["screenshot_height_to_window_height"]

    if window_width_ratio is not None and abs(window_width_ratio - 1.0) > 0.15:
        window_ratio_bad = True

    if window_height_ratio is not None and abs(window_height_ratio - 1.0) > 0.15:
        window_ratio_bad = True

    client_ratio_suspicious = False
    client_width_ratio = ratios["screenshot_width_to_client_width"]
    client_height_ratio = ratios["screenshot_height_to_client_height"]

    if client_width_ratio is not None and not 0.85 <= client_width_ratio <= 1.25:
        client_ratio_suspicious = True

    if client_height_ratio is not None and not 0.85 <= client_height_ratio <= 1.45:
        client_ratio_suspicious = True

    if error:
        status = "LIKELY_CAPTURE_MISMATCH"
        reason = f"startup screenshot capture failed: {error}"
    elif any("zero" in warning or "small" in warning or "black" in warning for warning in warnings):
        status = "LIKELY_CAPTURE_MISMATCH"
        reason = "; ".join(warnings)
    elif window_ratio_bad:
        if scaled_dpi:
            status = "LIKELY_DPI_SCALE_MISMATCH"
            reason = "screenshot/window size ratios are outside tolerance while DPI suggests scaling"
        else:
            status = "LIKELY_CAPTURE_MISMATCH"
            reason = "screenshot/window size ratios are outside tolerance"
    elif client_ratio_suspicious:
        status = "WARNING"
        reason = "screenshot/client size ratios are unusual; window borders can explain mild differences"
    elif scaled_dpi:
        status = "WARNING"
        reason = "DPI suggests Windows scaling, but capture/window sizes are within tolerance"
    elif monitor_info.get("negative_window_coords") or monitor_info.get("secondary_monitor_inferred"):
        status = "LIKELY_MULTI_MONITOR_COORDINATE_CASE"
        reason = "window appears to be on a secondary or negative-coordinate monitor; dimensions look usable"
    elif screenshot_size is None or window_size is None:
        status = "UNKNOWN"
        reason = "not enough screenshot/window data to classify"
    elif mean_brightness is None:
        status = "UNKNOWN"
        reason = "not enough brightness data to classify"
    else:
        status = "OK"
        reason = "screenshot/window sizes are within tolerance"

    notes = []

    if warnings:
        notes.extend(warnings)

    if scaled_dpi:
        notes.append(
            f"scaled_dpi_detected window_dpi={format_diag_value(window_dpi)} "
            f"monitor_dpi={format_diag_value(dpi_info.get('monitor_dpi'))}"
        )

    if monitor_info.get("negative_window_coords"):
        notes.append("negative window coordinates detected")

    if monitor_info.get("secondary_monitor_inferred"):
        notes.append("secondary monitor inferred")

    return {
        "status": status,
        "reason": reason,
        "ratios": ratios,
        "notes": notes,
    }


def write_ui_diagnostics_file(lines):
    try:
        debug_dir = get_debug_dir()
        debug_dir.mkdir(parents=True, exist_ok=True)
        diagnostics_path = debug_dir / "ui_diagnostics.txt"

        with open(diagnostics_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
            f.write("\n")

        write_log(f"UI diagnostics file written | path={diagnostics_path}")
    except Exception as e:
        write_log(f"UI diagnostics file write failed | error={e}")


def log_ui_coordinate_diagnostics(hwnd, title):
    global ui_diagnostics_health_status
    global ui_diagnostics_suggests_roi_retry

    window_rect = safe_window_rect(hwnd)
    client_rect = safe_client_rect(hwnd)
    client_origin = safe_client_origin(hwnd)
    window_size = rect_size(window_rect)
    client_size = rect_size(client_rect)
    monitor_info = get_monitor_diagnostics(hwnd, window_rect)
    dpi_info = get_dpi_diagnostics(hwnd)
    screenshot_info = get_screenshot_diagnostics(hwnd, window_size, client_size)
    scaling_info = update_coordinate_scaling_status(
        hwnd,
        screenshot_size=screenshot_info.get("screenshot_size"),
        client_size=client_size,
        reason="startup_ui_diagnostics",
    )
    health_info = build_ui_health_classification(
        window_size,
        client_size,
        screenshot_info,
        monitor_info,
        dpi_info,
    )
    health_ratios = health_info["ratios"]
    ui_diagnostics_health_status = health_info["status"]
    ui_diagnostics_suggests_roi_retry = health_info["status"] in {
        "WARNING",
        "LIKELY_DPI_SCALE_MISMATCH",
        "LIKELY_CAPTURE_MISMATCH",
        "LIKELY_MULTI_MONITOR_COORDINATE_CASE",
    }

    lines = [
        "MAA-TBH UI/coordinate diagnostics",
        f"timestamp={now_str()}",
        f"mode={get_runtime_mode()}",
        f"base_dir={get_base_dir()}",
        f"debug_dir={get_debug_dir()}",
        f"log_path={LOG_FILE}",
        f"window_handle={hwnd}",
        f"window_title={title}",
        f"window_rect={format_diag_value(window_rect)}",
        f"window_size={format_diag_value(window_size)}",
        f"client_rect={format_diag_value(client_rect)}",
        f"client_size={format_diag_value(client_size)}",
        f"client_origin_screen={format_diag_value(client_origin)}",
        f"screen_size={format_diag_value(monitor_info['screen_size'])}",
        f"monitor_count={format_diag_value(monitor_info['monitor_count'])}",
        f"window_monitor={format_diag_value(monitor_info['window_monitor'])}",
        f"negative_window_coords={monitor_info['negative_window_coords']}",
        f"secondary_monitor_inferred={format_diag_value(monitor_info['secondary_monitor_inferred'])}",
        f"dpi_awareness_attempted={dpi_info['dpi_awareness_attempted']}",
        f"process_dpi_awareness={format_diag_value(dpi_info['process_dpi_awareness'])}",
        f"process_dpi_aware={format_diag_value(dpi_info['process_dpi_aware'])}",
        f"window_dpi={format_diag_value(dpi_info['window_dpi'])}",
        f"monitor_dpi={format_diag_value(dpi_info['monitor_dpi'])}",
        f"screenshot_size={format_diag_value(screenshot_info['screenshot_size'])}",
        f"screenshot_shape={format_diag_value(screenshot_info['screenshot_shape'])}",
        f"screenshot_mean_brightness={format_diag_value(screenshot_info['mean_brightness'])}",
        f"coordinate_scaling_active={format_diag_value(scaling_info.get('active'))}",
        f"coordinate_scaling_reason={format_diag_value(scaling_info.get('reason'))}",
        f"coordinate_scaling_scale_x={format_diag_value(scaling_info.get('scale_x'))}",
        f"coordinate_scaling_scale_y={format_diag_value(scaling_info.get('scale_y'))}",
        f"health_status={health_info['status']}",
        f"health_reason={health_info['reason']}",
        (
            "ratio_screenshot_width_to_client_width="
            f"{format_diag_value(health_ratios['screenshot_width_to_client_width'])}"
        ),
        (
            "ratio_screenshot_height_to_client_height="
            f"{format_diag_value(health_ratios['screenshot_height_to_client_height'])}"
        ),
        (
            "ratio_screenshot_width_to_window_width="
            f"{format_diag_value(health_ratios['screenshot_width_to_window_width'])}"
        ),
        (
            "ratio_screenshot_height_to_window_height="
            f"{format_diag_value(health_ratios['screenshot_height_to_window_height'])}"
        ),
    ]

    if screenshot_info["error"]:
        lines.append(f"screenshot_error={screenshot_info['error']}")

    for warning in screenshot_info["warnings"]:
        lines.append(f"screenshot_warning={warning}")

    for error in monitor_info["errors"]:
        lines.append(f"monitor_info_note={error}")

    for error in dpi_info["errors"]:
        lines.append(f"dpi_info_note={error}")

    for note in health_info["notes"]:
        lines.append(f"health_note={note}")

    write_log(
        "UI diagnostics summary | "
        f"screen_size={format_diag_value(monitor_info['screen_size'])} | "
        f"window_rect={format_diag_value(window_rect)} | "
        f"client_size={format_diag_value(client_size)} | "
        f"screenshot_size={format_diag_value(screenshot_info['screenshot_size'])} | "
        f"window_dpi={format_diag_value(dpi_info['window_dpi'])} | "
        f"negative_window_coords={monitor_info['negative_window_coords']} | "
        f"secondary_monitor_inferred={format_diag_value(monitor_info['secondary_monitor_inferred'])}"
    )
    log_coordinate_scaling_status(scaling_info)

    if monitor_info["negative_window_coords"]:
        write_log(
            "Mouse parking strategy=static_client_point recommended for negative-coordinate monitor setup | "
            f"configured_strategy={MOUSE_PARKING_STRATEGY} | "
            f"fallback={MOUSE_PARKING_FALLBACK_STRATEGY} | "
            f"fail_safe_margin_px={MOUSE_FAIL_SAFE_MARGIN_PX}"
        )

    write_log(
        "UI diagnostics health | "
        f"status={health_info['status']} | "
        f"reason={health_info['reason']} | "
        "ratios="
        f"sw/cw={format_diag_value(health_ratios['screenshot_width_to_client_width'])}, "
        f"sh/ch={format_diag_value(health_ratios['screenshot_height_to_client_height'])}, "
        f"sw/ww={format_diag_value(health_ratios['screenshot_width_to_window_width'])}, "
        f"sh/wh={format_diag_value(health_ratios['screenshot_height_to_window_height'])}"
    )
    write_log(
        "Expanded ROI retry status | "
        f"configured={USE_EXPANDED_ROI_RETRY} | "
        f"active_reason={format_diag_value(get_expanded_roi_retry_reason())} | "
        f"only_on_ui_warning={EXPANDED_ROI_ONLY_ON_UI_WARNING} | "
        f"margin_px={EXPANDED_ROI_MARGIN_PX} | "
        f"scale_factor={EXPANDED_ROI_SCALE_FACTOR:.2f} | "
        f"level_y_tolerance_px={LEVEL_Y_POSITION_TOLERANCE_PX}"
    )

    for warning in screenshot_info["warnings"]:
        write_log(f"UI diagnostics warning | {warning}")

    if screenshot_info["error"]:
        write_log(f"UI diagnostics warning | screenshot capture failed | error={screenshot_info['error']}")

    write_ui_diagnostics_file(lines)


def log_app_start_boundary():
    write_log(
        "\n"
        "############################################################\n"
        "#################### MAA-TBH APP START ####################\n"
        f"timestamp={now_str()}\n"
        f"mode={get_runtime_mode()}\n"
        f"base_dir={get_base_dir()}\n"
        f"log_path={LOG_FILE}\n"
        f"debug_path={get_debug_dir()}\n"
        f"config_path={get_config_path()}\n"
        f"farm_plan_path={get_farm_plan_path()}\n"
        "############################################################"
    )


def log_console_encoding_status():
    stdout = getattr(sys, "stdout", None)
    stderr = getattr(sys, "stderr", None)
    write_log(
        "Console encoding status | "
        f"stdout={getattr(stdout, 'encoding', None)} | "
        f"stderr={getattr(stderr, 'encoding', None)} | "
        f"PYTHONIOENCODING={os.environ.get('PYTHONIOENCODING')}"
    )


def format_effective_thresholds_for_log():
    keys = [
        "difficulty_anchor_accept",
        "difficulty_tab_accept",
        "chapter_candidate_click",
        "chapter_verify_accept",
        "level_strong_accept",
        "level_cautious_accept",
        "level_ignore_below",
        "white_dot_accept",
        "green_dot_after_click_accept",
        "clear_accept",
        "boss_warning_accept",
        "blue_chest_accept",
        "blue_chest_with_log_accept",
        "brown_chest_accept",
        "chest_match",
        "chapter_tab_candidate",
        "chapter_match",
        "difficulty",
        "level_dot_white",
        "level_dot_green",
        "boss_warning",
        "clear_match",
    ]

    parts = []

    for key in keys:
        value = EFFECTIVE_RECOGNITION_THRESHOLDS.get(key)

        if value is None:
            continue

        try:
            parts.append(f"{key}={float(value):.2f}")
        except (TypeError, ValueError):
            parts.append(f"{key}={value}")

    return ", ".join(parts)


def log_recognition_profile_startup():
    write_log(
        "Recognition profile active | "
        f"mode={RECOGNITION_MODE} | "
        f"effective_thresholds={format_effective_thresholds_for_log()}"
    )

    if RECOGNITION_MODE == "aggressive":
        write_log(
            "Aggressive Recognition Mode may improve matching on scaled displays "
            "or weak templates, but can increase the chance of wrong chapter/level "
            "selection. Use for testing and export a Debug ZIP if behavior is incorrect."
        )

    write_log(
        "Recognition safety | "
        f"level_strong_accept={LEVEL_STRONG_ACCEPT_THRESHOLD:.2f} | "
        f"chapter_ambiguous_click_verify_enabled={CHAPTER_AMBIGUOUS_CLICK_VERIFY_ENABLED} | "
        f"chapter_ambiguous_click_max_attempts={CHAPTER_AMBIGUOUS_CLICK_MAX_ATTEMPTS} | "
        f"chapter_ambiguous_min_confidence={CHAPTER_AMBIGUOUS_MIN_CONFIDENCE:.2f} | "
        f"route_invariant_allow_selected_evidence={ROUTE_INVARIANT_ALLOW_SELECTED_EVIDENCE} | "
        f"route_invariant_level_confidence_floor={ROUTE_INVARIANT_LEVEL_CONFIDENCE_FLOOR:.2f} | "
        f"route_invariant_green_dot_min_confidence={ROUTE_INVARIANT_GREEN_DOT_MIN_CONFIDENCE:.2f} | "
        f"route_invariant_require_level_y_ok={ROUTE_INVARIANT_REQUIRE_LEVEL_Y_OK} | "
        f"mouse_parking_enabled={MOUSE_PARKING_ENABLED} | "
        f"mouse_parking_wait={MOUSE_PARKING_WAIT_SECONDS:.2f}s | "
        f"mouse_parking_chapter={MOUSE_PARKING_BEFORE_CHAPTER_DETECTION} | "
        f"mouse_parking_difficulty={MOUSE_PARKING_BEFORE_DIFFICULTY_DETECTION} | "
        f"mouse_parking_level={MOUSE_PARKING_BEFORE_LEVEL_DETECTION} | "
        f"mouse_parking_mode={MOUSE_PARKING_MODE} | "
        f"mouse_parking_strategy={MOUSE_PARKING_STRATEGY} | "
        f"mouse_parking_fallback_strategy={MOUSE_PARKING_FALLBACK_STRATEGY} | "
        f"mouse_parking_fail_safe_relocate_enabled={MOUSE_PARKING_FAIL_SAFE_RELOCATE_ENABLED} | "
        f"mouse_parking_fail_safe_min_screen_margin_px={MOUSE_PARKING_FAIL_SAFE_MIN_SCREEN_MARGIN_PX} | "
        f"mouse_parking_fallback_static=({MOUSE_PARKING_FALLBACK_STATIC_X},{MOUSE_PARKING_FALLBACK_STATIC_Y}) | "
        f"mouse_fail_safe_margin_px={MOUSE_FAIL_SAFE_MARGIN_PX} | "
        f"mouse_movement_fail_safe_policy={MOUSE_MOVEMENT_FAIL_SAFE_POLICY} | "
        f"navigation_failure_policy={NAVIGATION_FAILURE_POLICY} | "
        f"max_consecutive_navigation_skips={MAX_CONSECUTIVE_NAVIGATION_SKIPS} | "
        "post-click level verification remains enabled | "
        "reward/chest safety logic unchanged"
    )


def add_template_spec(specs, seen_paths, name, path):
    if not path:
        return

    if path in seen_paths:
        return

    seen_paths.add(path)
    specs.append({
        "name": name,
        "path": path,
    })


def get_startup_template_specs():
    specs = []
    seen_paths = set()

    add_template_spec(specs, seen_paths, "general:blue_chest", "templates/general/chest_blue.png")
    add_template_spec(specs, seen_paths, "general:brown_chest", "templates/general/chest_brown.png")
    add_template_spec(specs, seen_paths, "general:boss_warning_text", "templates/general/boss_warning_text.png")
    add_template_spec(specs, seen_paths, "general:task_clear", CLEAR_TEMPLATE_PATH)
    add_template_spec(specs, seen_paths, "general:level_dot_white", LEVEL_DOT_WHITE_TEMPLATE)
    add_template_spec(specs, seen_paths, "general:level_dot_green", LEVEL_DOT_GREEN_TEMPLATE)
    add_template_spec(specs, seen_paths, "general:backpack_to_storage_button", "templates/general/backpack_to_storage_button.png")

    for difficulty, templates in DIFFICULTY_TEMPLATES.items():
        for role, path in templates.items():
            add_template_spec(
                specs,
                seen_paths,
                f"difficulty:{difficulty}:{role}",
                path
            )

    for chapter, templates in CHAPTER_TEMPLATES.items():
        for role, path in templates.items():
            add_template_spec(
                specs,
                seen_paths,
                f"chapter:{chapter}:{role}",
                path
            )

    for index, route in enumerate(ROUTE, start=1):
        route_name = route.get("name", f"Route {index}")
        level = route.get("level", "unknown_level")
        add_template_spec(
            specs,
            seen_paths,
            f"route:{route_name}:{level}",
            route.get("level_template")
        )

    return specs


def log_startup_template_check():
    specs = get_startup_template_specs()
    ok_count = 0
    missing = []
    load_failed = []

    for spec in specs:
        result = check_template_loadable(spec["path"])
        status = result["status"]

        if status == "ok":
            ok_count += 1
            continue

        issue = {
            "name": spec["name"],
            "path": spec["path"],
            "result": result,
        }

        if status == "missing":
            missing.append(issue)
        else:
            load_failed.append(issue)

    write_log(
        "TEMPLATE CHECK SUMMARY | "
        f"total={len(specs)} | "
        f"ok={ok_count} | "
        f"missing={len(missing)} | "
        f"failed_to_load={len(load_failed)}"
    )

    for issue in missing:
        result = issue["result"]
        write_log(
            "TEMPLATE CHECK ISSUE | "
            f"name={issue['name']} | "
            f"expected_path={result['expected_path']} | "
            "reason=missing file | "
            f"checked_paths={'; '.join(result['checked_paths'])}"
        )

    for issue in load_failed:
        result = issue["result"]
        write_log(
            "TEMPLATE CHECK ISSUE | "
            f"name={issue['name']} | "
            f"expected_path={result['expected_path']} | "
            "reason=load failed | "
            f"existing_paths={'; '.join(result.get('existing_paths', []))}"
        )


def log_chest_tier_breakpoint_validation():
    table_summary = ", ".join(
        (
            f"{item['chest_tier']}级={item['difficulty']} "
            f"{item['chapter']} {item['level']}"
        )
        for item in CHEST_TIER_BREAKPOINTS
    )
    write_log(f"Chest tier breakpoint table | {table_summary}")

    sample_routes = [
        ("normal", "chapter_1", "1-1"),
        ("normal", "chapter_1", "1-4"),
        ("normal", "chapter_1", "1-8"),
        ("normal", "chapter_2", "2-3"),
        ("normal", "chapter_2", "2-8"),
        ("normal", "chapter_3", "3-8"),
        ("nightmare", "chapter_1", "1-9"),
        ("nightmare", "chapter_3", "3-5"),
        ("hell", "chapter_1", "1-1"),
        ("hell", "chapter_2", "2-5"),
        ("torment", "chapter_1", "1-3"),
    ]

    for difficulty, chapter, level in sample_routes:
        tier = get_chest_tier_for_route(difficulty, chapter, level)
        tier_label = "base" if tier is None else f"{tier}级"
        write_log(
            f"Chest tier sample check | "
            f"route={difficulty} {chapter} {level} | tier={tier_label}"
        )


def route_marker_line(route_index, route, cycle_number=None):
    if cycle_number is None:
        cycle_number = current_cycle_number

    return (
        f"cycle={cycle_number} | "
        f"route_index={route_index + 1}/{len(ROUTE)} | "
        f"{route['name']} | {route['difficulty']} | "
        f"{route['chapter']} | {route['level']}"
    )


def log_session_start_marker(input_mode):
    write_log(
        "============================================================\n"
        f"[SESSION START] {now_str()} | routes={len(ROUTE)} | input_mode={input_mode}\n"
        "============================================================"
    )


def log_cycle_start_marker():
    write_log(
        "------------------------------------------------------------\n"
        f"[CYCLE {current_cycle_number} START] full route-list loop begins | routes={len(ROUTE)}\n"
        "------------------------------------------------------------"
    )


def log_cycle_wrap_marker(completed_cycle):
    write_log(
        "------------------------------------------------------------\n"
        f"[CYCLE {completed_cycle} END] completed full route-list loop\n"
        f"[CYCLE {current_cycle_number} START] full route-list loop begins | routes={len(ROUTE)}\n"
        "------------------------------------------------------------"
    )


def log_route_start_marker(route_index, route):
    no_chest_retries, total_clears, source = get_no_chest_policy_for_current_route()
    write_log(
        "================ ROUTE START =================\n"
        f"{route_marker_line(route_index, route)}\n"
        f"no_chest_retries={no_chest_retries} | "
        f"total_no_chest_clears={total_clears} | source={source}\n"
        "=============================================="
    )


def log_detector_retry_marker(reason):
    route = get_current_route()
    _, total_clears, _ = get_no_chest_policy_for_current_route()
    write_log(
        "================ DETECTOR RETRY ==============\n"
        f"{route_marker_line(current_route_index, route)}\n"
        f"reason={reason} | count={no_chest_trial_count}/{total_clears}\n"
        "no route navigation; resetting detector state only\n"
        "=============================================="
    )


def log_route_advance_marker(
    previous_index,
    previous_route,
    next_index,
    next_route,
    reason,
    previous_cycle=None,
    next_cycle=None,
):
    write_log(
        "================ ROUTE ADVANCE ===============\n"
        f"from: {route_marker_line(previous_index, previous_route, previous_cycle)}\n"
        f"to:   {route_marker_line(next_index, next_route, next_cycle)}\n"
        f"reason={reason}\n"
        "=============================================="
    )


def log_navigation_failed_marker(reason):
    route = get_current_route()
    write_log(
        "================ NAVIGATION FAILED ===========\n"
        f"{route_marker_line(current_route_index, route)}\n"
        f"reason={reason}\n"
        "bot paused; no more scroll search\n"
        "=============================================="
    )


def alert_blue_chest(detection):
    global last_blue_alert_time

    current_time = time.time()

    if current_time - last_blue_alert_time < BLUE_ALERT_COOLDOWN_SECONDS:
        return

    last_blue_alert_time = current_time

    msg = (
        f"BLUE chest detected | "
        f"confidence={detection['confidence']:.2f} | "
        f"location={detection['center_full']} | "
        f"region={detection['region_name']}"
    )

    write_log(msg)

    if ENABLE_BEEP:
        winsound.Beep(1200, 300)
        winsound.Beep(1500, 300)


def log_brown_chest(detection):
    global last_brown_log_time

    current_time = time.time()

    if current_time - last_brown_log_time < BROWN_LOG_COOLDOWN_SECONDS:
        return

    last_brown_log_time = current_time

    msg = (
        f"Brown chest detected, leave it | "
        f"confidence={detection['confidence']:.2f} | "
        f"location={detection['center_full']} | "
        f"region={detection['region_name']}"
    )

    write_log(msg)


def handle_chest_events(detections):
    """
    Convert raw detections into useful events.

    Behavior:
    - Blue chest: alert once when it first appears.
    - Brown chest: log once when it first appears.
    - No chest: reset after a short delay.
    """
    global last_seen_chest_time, last_state

    current_time = time.time()

    blue_detections = [d for d in detections if d["type"] == "blue"]
    brown_detections = [d for d in detections if d["type"] == "brown"]

    if blue_detections:
        best_blue = max(blue_detections, key=lambda d: d["confidence"])

        last_seen_chest_time = current_time

        if last_state != "blue":
            last_state = "blue"
            alert_blue_chest(best_blue)

        return "blue"

    if brown_detections:
        best_brown = max(brown_detections, key=lambda d: d["confidence"])

        last_seen_chest_time = current_time

        if last_state != "brown":
            last_state = "brown"
            log_brown_chest(best_brown)

        return "brown"

    # No detections
    if last_state != "none":
        if current_time - last_seen_chest_time >= NO_CHEST_RESET_SECONDS:
            write_log("Chest disappeared / reset.")
            last_state = "none"

    return "none"

def mouse_callback(event, x, y, flags, param):
    global mouse_x, mouse_y

    mouse_x = x
    mouse_y = y

    if event == cv2.EVENT_LBUTTONDOWN:
        safe_print(f"\nLeft click at: x={x}, y={y}")

    elif event == cv2.EVENT_RBUTTONDOWN:
        safe_print(f"\nRight click at: x={x}, y={y}")


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
    scale_margin_x = int(width * max(0.0, EXPANDED_ROI_SCALE_FACTOR - 1.0) / 2)
    scale_margin_y = int(height * max(0.0, EXPANDED_ROI_SCALE_FACTOR - 1.0) / 2)
    margin_x = max(EXPANDED_ROI_MARGIN_PX, scale_margin_x)
    margin_y = max(EXPANDED_ROI_MARGIN_PX, scale_margin_y)

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
    if not USE_EXPANDED_ROI_RETRY:
        return None

    reasons = []

    if RECOGNITION_MODE == "aggressive":
        reasons.append("recognition_mode=aggressive")

    if ui_diagnostics_suggests_roi_retry:
        reasons.append(f"ui_health={ui_diagnostics_health_status}")

    if not EXPANDED_ROI_ONLY_ON_UI_WARNING:
        reasons.append("config=always")

    if not reasons:
        return None

    return ",".join(reasons)


def expanded_roi_retry_enabled():
    return get_expanded_roi_retry_reason() is not None


def log_expanded_roi_retry_start(label, template_path, original_roi, expanded_roi, reason):
    write_log(
        f"ROI retry start | target={label} | template={template_path} | "
        f"original_roi={original_roi} | expanded_roi={expanded_roi} | reason={reason}"
    )


def log_expanded_roi_retry_result(label, found, confidence, threshold):
    status = "found candidate" if found else "failed"
    write_log(
        f"ROI retry {status} | target={label} | "
        f"best_confidence={confidence:.2f} | threshold={threshold:.2f}"
    )


def detect_all_chests(img, blue_template, brown_template):
    """
    Search battle_top and battle_bottom for blue/brown chest templates.

    Returns detections in full-window coordinates.
    """
    all_detections = []

    for region_name in BATTLE_SEARCH_REGION_NAMES:
        region = REGIONS[region_name]
        clamped = clamp_region(img, region)

        if clamped is None:
            continue

        x1, y1, x2, y2 = clamped
        region_img = img[y1:y2, x1:x2]

        detections = detect_chests_in_region(
            region_img,
            blue_template,
            brown_template,
            threshold=MATCH_THRESHOLD,
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

    for name in PREVIEW_REGION_NAMES:
        region = REGIONS[name]
        clamped = clamp_region(debug, region)

        if clamped is None:
            continue

        x1, y1, x2, y2 = clamped
        color = REGION_COLORS.get(name, (0, 255, 0))

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

        color = DETECTION_COLORS.get(chest_type, (255, 255, 255))

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
    maybe_save_debug_screenshot(img, folder="debug_screenshots/full", prefix="full")

    for name, region in REGIONS.items():
        cropped = crop(img, region)

        if cropped is not None:
            maybe_save_debug_screenshot(
                cropped,
                folder=f"debug_screenshots/{name}",
                prefix=name
            )


def print_detection_summary(detections):
    if not detections:
        safe_print("No chest detected.".ljust(160), end="\r")
        return

    parts = []

    for det in detections:
        parts.append(
            f"{det['type']} {det['confidence']:.2f} "
            f"at {det['center_full']} in {det['region_name']}"
        )

    msg = " | ".join(parts)
    safe_print(msg[:160].ljust(160), end="\r")

def detect_blue_log(img):
    """
    Search log_top and log_bottom for blue log text.
    """
    log_regions = ["log_top", "log_bottom"]

    best_pixels = 0
    best_region = None

    for region_name in log_regions:
        region_img = crop(img, REGIONS[region_name])

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

def get_no_chest_policy_for_current_route():
    route = get_current_route()

    if "no_chest_retries" in route:
        retries = coerce_non_negative_int(route.get("no_chest_retries"), DEFAULT_NO_CHEST_RETRIES)
        return retries, retries + 1, "no_chest_retries"

    if "max_trials_if_no_chest" in route:
        old_total_clears = coerce_non_negative_int(
            route.get("max_trials_if_no_chest"),
            DEFAULT_MAX_TRIALS_IF_NO_CHEST
        )
        total_clears = max(1, old_total_clears)
        return max(0, total_clears - 1), total_clears, "max_trials_if_no_chest"

    retries = coerce_non_negative_int(DEFAULT_NO_CHEST_RETRIES, max(0, DEFAULT_MAX_TRIALS_IF_NO_CHEST - 1))
    return retries, retries + 1, "default_no_chest_retries"


def get_max_trials_for_current_route():
    _, total_clears, _ = get_no_chest_policy_for_current_route()
    return total_clears


def log_current_route_no_chest_policy(prefix):
    route = get_current_route()
    retries, total_clears, source = get_no_chest_policy_for_current_route()

    write_log(
        f"{prefix} route no-chest policy | "
        f"route={route['name']} | difficulty={route['difficulty']} | "
        f"chapter={route['chapter']} | level={route['level']} | "
        f"no_chest_retries={retries} | total_no_chest_clears={total_clears} | "
        f"source={source}"
    )


def reset_no_chest_trial_count(reason):
    global no_chest_trial_count

    if no_chest_trial_count != 0:
        write_log(
            f"Reset no-chest trial count | "
            f"previous={no_chest_trial_count} | reason={reason}"
        )

    no_chest_trial_count = 0


def reset_route_detection_memory():
    """
    Reset route-specific state so old boss/chest/log detections
    cannot carry into the next route.
    """
    global boss_seen_this_route
    global blue_drop_handled_this_route
    global last_blue_log_seen_after_boss
    global last_blue_chest_seen_after_boss
    global orphan_blue_chest_first_seen
    global clear_handled_this_trial
    global last_clear_seen_time
    global post_clear_wait_started_at
    global post_clear_best_conf

    boss_seen_this_route = False
    blue_drop_handled_this_route = False

    last_blue_log_seen_after_boss = 0
    last_blue_chest_seen_after_boss = 0
    orphan_blue_chest_first_seen = 0
    clear_handled_this_trial = False
    last_clear_seen_time = 0
    post_clear_wait_started_at = 0
    post_clear_best_conf = 0.0

def handle_confirmed_blue_drop(detections, reason, details, allow_pre_boss=False):
    """
    Shared action once a blue drop is confirmed by normal or recovery logic.
    """
    global bot_state
    global blue_drop_handled_this_route

    if not boss_seen_this_route and not allow_pre_boss:
        write_log(
            f"Blue chest visible before boss warning without reward priority confirmation | "
            f"reason={reason} | {details}"
        )
        return {
            "state": bot_state,
            "boss_visible": False,
            "blue_chest_visible": True,
            "blue_log_visible": False,
            "message": "Blue chest visible; waiting for confirmation"
        }

    if not boss_seen_this_route and allow_pre_boss:
        write_log(
            "Boss warning not detected, but confirmed blue reward appeared; "
            f"treating as missed boss-warning reward | "
            f"reason={reason} | {details}"
        )
        write_log("Confirmed orphan reward; opening before route advance.")
    elif boss_seen_this_route:
        write_log(
            f"Confirmed post-boss blue reward; opening before route advance | "
            f"reason={reason} | {details}"
        )

    if post_clear_wait_started_at > 0:
        write_log(
            f"Late blue reward detected after CLEAR; opening before route advance | "
            f"reason={reason} | {details}"
        )

    write_log(f"CONFIRMED BLUE DROP | reason={reason} | {details}")

    if ENABLE_BEEP:
        winsound.Beep(1600, 250)
        winsound.Beep(1900, 250)
        winsound.Beep(2200, 250)

    if ENABLE_CLICKING or AUTO_OPEN_CONFIRMED_BLUE_CHEST:
        write_log("Blue drop confirmed. Opening blue chest before route advance.")
        time.sleep(1.0)

        click_success = click_blue_chest_once(GAME_HWND, detections)

        if not click_success:
            write_log(
                "Blue chest click failed; route will not advance. "
                "Pausing before any route transition."
            )
            bot_state = STATE_NAVIGATION_FAILED
            log_navigation_failed_marker("blue_chest_click_failed")
            return {
                "state": bot_state,
                "boss_visible": False,
                "blue_chest_visible": True,
                "blue_log_visible": False,
                "message": "Blue chest click failed; bot paused"
            }

        blue_drop_handled_this_route = True
        write_log("Blue chest click completed.")
        try_move_backpack_to_storage_after_blue_chest()
    else:
        blue_drop_handled_this_route = True
        write_log("DRY RUN: would click blue chest once.")

    if STOP_IF_BLUE_CHEST_FOUND:
        reset_no_chest_trial_count("confirmed_blue_drop")

    advance_route(do_navigation=True, reason="blue_drop_confirmed")

    return {
        "state": bot_state,
        "boss_visible": False,
        "blue_chest_visible": False,
        "blue_log_visible": False,
        "message": "Advanced route; freeze started"
    }

def retry_current_route(do_navigation=True):
    """
    Retry the current route without resetting the no-chest trial count.
    """
    global route_start_time
    global bot_state
    global freeze_start_time

    route = get_current_route()
    route_start_time = time.time()

    write_log(
        f"Retrying same level | route={route['name']} | "
        f"{route['difficulty']} | {route['chapter']} | {route['level']} | "
        f"no_chest_clears={no_chest_trial_count}/{get_max_trials_for_current_route()}"
    )

    reset_route_detection_memory()

    nav_success = True

    if do_navigation:
        time.sleep(1.0)
        nav_success = navigate_to_current_route_if_enabled()

        if not nav_success:
            if record_route_navigation_failure("retry_current_route_failed"):
                bot_state = STATE_STARTUP_NAVIGATION
                write_log(
                    "Retry navigation failed. Entering navigation retry state "
                    "and ignoring detection decisions."
                )
            return

    bot_state = STATE_FREEZE_AFTER_SWITCH
    freeze_start_time = time.time()
    reset_route_navigation_retries("retry_current_route_success")

    write_log("Retry navigation completed. Entering freeze window.")


def retry_detector_cycle_current_route():
    """
    Retry detection on the currently selected level without map navigation.
    """
    global route_start_time
    global bot_state
    global freeze_start_time

    route = get_current_route()
    route_start_time = time.time()

    log_detector_retry_marker("no_chest_below_limit")
    reset_route_detection_memory()

    bot_state = STATE_FREEZE_AFTER_SWITCH
    freeze_start_time = time.time()

    write_log(
        f"No-chest below limit; retrying detector cycle on same selected level | "
        f"route={route['name']} | {route['difficulty']} | {route['chapter']} | "
        f"{route['level']} | no_chest_clears={no_chest_trial_count}/{get_max_trials_for_current_route()}"
    )
    write_log("No route navigation will be performed for this retry.")
    write_log("Detector cycle reset. Entering freeze window before looking for boss warning.")


def handle_clear_no_chest_trial(clear_conf):
    """
    Handle CLEAR as a fallback signal that the level ended without blue chest.
    """
    global no_chest_trial_count
    global clear_handled_this_trial

    if clear_handled_this_trial:
        return {
            "state": bot_state,
            "boss_visible": False,
            "blue_chest_visible": False,
            "blue_log_visible": False,
            "message": "CLEAR already handled for this trial"
        }

    clear_handled_this_trial = True
    no_chest_trial_count += 1

    no_chest_retries, max_trials, policy_source = get_no_chest_policy_for_current_route()
    route = get_current_route()

    write_log(
        f"CLEAR detected | confidence={clear_conf:.2f} | "
        f"route={route['name']} | no blue drop confirmed"
    )
    write_log(
        f"No-chest trial counted | "
        f"count={no_chest_trial_count}/{max_trials} | "
        f"no_chest_retries={no_chest_retries} | "
        f"total_allowed_no_chest_clears={max_trials} | "
        f"source={policy_source} | route={route['level']}"
    )

    if no_chest_trial_count < max_trials:
        write_log(
            f"No-chest trial below limit. Retrying detector cycle on same selected level | "
            f"count={no_chest_trial_count}/{max_trials} | "
            f"retries_allowed={no_chest_retries}"
        )
        retry_detector_cycle_current_route()

        return {
            "state": bot_state,
            "boss_visible": False,
            "blue_chest_visible": False,
            "blue_log_visible": False,
            "message": "No-chest CLEAR counted; retrying detector cycle"
        }

    write_log(
        f"Max no-chest trials reached | "
        f"count={no_chest_trial_count}/{max_trials} | "
        f"no_chest_retries={no_chest_retries} | route={route['level']}"
    )

    if ASSUME_MAILBOX_AFTER_MAX_TRIALS:
        write_log("Mailbox fallback assumed after max no-chest trials. Mailbox will not be opened.")

    reset_no_chest_trial_count("max_no_chest_trials_reached")
    write_log("Advancing to next level after max no-chest trials.")
    advance_route(do_navigation=True, reason="max_no_chest_trials_reached")

    return {
        "state": bot_state,
        "boss_visible": False,
        "blue_chest_visible": False,
        "blue_log_visible": False,
        "message": "Max no-chest trials reached; advanced route"
    }


def handle_bot_state(
    img,
    detections,
    boss_visible,
    boss_region,
    boss_pixels,
    boss_conf,
    clear_visible=False,
    clear_conf=0.0,
):
    """
    Gated bot state machine.

    State 1: FREEZE_AFTER_SWITCH
        Ignore all trigger actions for safety.

    State 2: LOOK_FOR_BOSS
        Only boss warning can advance the state.

    State 3: LOOK_FOR_BLUE_DROP
        Boss detector is ignored.
        Blue chest + blue log are remembered inside a safe post-boss window.
    """
    global bot_state
    global freeze_start_time
    global boss_seen_this_route
    global blue_drop_handled_this_route
    global last_blue_log_seen_after_boss
    global last_blue_chest_seen_after_boss
    global orphan_blue_chest_first_seen
    global clear_handled_this_trial
    global last_clear_seen_time
    global post_clear_wait_started_at
    global post_clear_best_conf

    current_time = time.time()
    blue_detections = [d for d in detections if d["type"] == "blue"]
    blue_chest_visible = bool(blue_detections)
    best_blue_confidence = (
        max((d["confidence"] for d in blue_detections), default=0.0)
    )
    blue_log_visible, blue_log_region, blue_log_pixels = detect_blue_log(img)

    if (
        blue_chest_visible
        and blue_log_visible
        and not blue_drop_handled_this_route
        and bot_state != STATE_FREEZE_AFTER_SWITCH
    ):
        if post_clear_wait_started_at > 0:
            priority_reason = "late_blue_reward_after_clear"
        elif not boss_seen_this_route:
            priority_reason = "orphan_blue_chest_and_log"
        else:
            priority_reason = "reward_priority_before_state_transition"

        write_log(
            f"Reward priority triggered before route advance | "
            f"state={bot_state} | reason={priority_reason} | "
            f"blue_confidence={best_blue_confidence:.2f} | "
            f"log_region={blue_log_region} | blue_pixels={blue_log_pixels}"
        )

        return handle_confirmed_blue_drop(
            detections,
            priority_reason,
            f"blue_confidence={best_blue_confidence:.2f} | "
            f"log_region={blue_log_region} | blue_pixels={blue_log_pixels}",
            allow_pre_boss=True
        )

    # State 1: Freeze after switching route
    if bot_state == STATE_FREEZE_AFTER_SWITCH:
        freeze_elapsed = current_time - freeze_start_time
        freeze_remaining = FREEZE_SECONDS_AFTER_SWITCH - freeze_elapsed

        if freeze_remaining <= 0:
            bot_state = STATE_LOOK_FOR_BOSS
            write_log("Freeze ended. Now looking for boss warning.")

            return {
                "state": bot_state,
                "boss_visible": False,
                "blue_chest_visible": False,
                "blue_log_visible": False,
                "message": "Looking for boss warning"
            }

    # State 2: Look for boss only
    if bot_state == STATE_LOOK_FOR_BOSS:
        if blue_chest_visible:
            if orphan_blue_chest_first_seen == 0:
                orphan_blue_chest_first_seen = current_time
                write_log(
                    f"Orphan blue chest visible before boss confirmation; "
                    f"reward recovery uncertain without blue log | "
                    f"blue_confidence={best_blue_confidence:.2f}"
                )
        else:
            orphan_blue_chest_first_seen = 0

        if boss_visible:
            boss_seen_this_route = True
            bot_state = STATE_LOOK_FOR_BLUE_DROP
            orphan_blue_chest_first_seen = 0

            # Clear blue memory when boss is first confirmed.
            last_blue_log_seen_after_boss = 0
            last_blue_chest_seen_after_boss = 0

            write_log(
                f"Boss warning confirmed | "
                f"region={boss_region} | "
                f"red_pixels={boss_pixels} | "
                f"confidence={boss_conf:.2f}. "
                f"Blue-drop detector armed."
            )

            return {
                "state": bot_state,
                "boss_visible": True,
                "blue_chest_visible": False,
                "blue_log_visible": False,
                "message": "Boss confirmed; blue-drop detector armed"
            }

        return {
            "state": bot_state,
            "boss_visible": boss_visible,
            "blue_chest_visible": blue_chest_visible,
            "blue_log_visible": blue_log_visible,
            "message": (
                "Looking for boss warning"
                if not blue_chest_visible
                else "Orphan blue chest visible; waiting for confirmation"
            )
        }

    # State 3: Look for blue drop only
    if bot_state == STATE_LOOK_FOR_BLUE_DROP:
        if blue_chest_visible:
            last_blue_chest_seen_after_boss = current_time

        if blue_log_visible:
            last_blue_log_seen_after_boss = current_time

        blue_chest_recent = (
            last_blue_chest_seen_after_boss > 0 and
            current_time - last_blue_chest_seen_after_boss <= POST_BOSS_DROP_WINDOW_SECONDS
        )

        blue_log_recent = (
            last_blue_log_seen_after_boss > 0 and
            current_time - last_blue_log_seen_after_boss <= POST_BOSS_DROP_WINDOW_SECONDS
        )

        if (
            boss_seen_this_route
            and blue_chest_recent
            and blue_log_recent
            and not blue_drop_handled_this_route
        ):
            return handle_confirmed_blue_drop(
                detections,
                "post_boss_blue_chest_and_log",
                f"blue_chest_recent={blue_chest_recent} | "
                f"blue_log_recent={blue_log_recent} | "
                f"log_region={blue_log_region} | "
                f"blue_pixels={blue_log_pixels}"
            )

        if clear_visible:
            last_clear_seen_time = current_time
            post_clear_best_conf = max(post_clear_best_conf, clear_conf)

            if blue_drop_handled_this_route:
                if not clear_handled_this_trial:
                    clear_handled_this_trial = True
                    write_log(
                        f"CLEAR ignored because blue drop was already handled | "
                        f"confidence={clear_conf:.2f}"
                    )
            else:
                if post_clear_wait_started_at == 0:
                    post_clear_wait_started_at = current_time
                    post_clear_best_conf = clear_conf
                    write_log(
                        f"CLEAR detected; waiting for late blue reward | "
                        f"confidence={clear_conf:.2f} | "
                        f"wait_seconds={POST_CLEAR_REWARD_WAIT_SECONDS:.1f}"
                    )

        if post_clear_wait_started_at > 0 and not blue_drop_handled_this_route:
            post_clear_elapsed = current_time - post_clear_wait_started_at

            if post_clear_elapsed >= POST_CLEAR_REWARD_WAIT_SECONDS:
                return handle_clear_no_chest_trial(post_clear_best_conf)

        return {
            "state": bot_state,
            "boss_visible": False,
            "blue_chest_visible": blue_chest_visible,
            "blue_log_visible": blue_log_visible,
            "message": (
                f"Looking for blue drop | "
                f"chest_recent={blue_chest_recent} | "
                f"log_recent={blue_log_recent} | "
                f"post_clear_wait={post_clear_wait_started_at > 0}"
            )
        }

    return {
        "state": bot_state,
        "boss_visible": False,
        "blue_chest_visible": False,
        "blue_log_visible": False,
        "message": "Unknown state"
    }

def try_move_backpack_to_storage_after_blue_chest():
    move_to_storage_enabled = env_flag(
        "MAATBH_MOVE_TO_STORAGE",
        config_bool("move_backpack_to_storage_after_blue_chest", False)
    )

    if not move_to_storage_enabled:
        write_log("Storage transfer disabled by GUI/config; skipping.")
        return False

    wait_seconds = config_non_negative_float("post_blue_chest_storage_wait_seconds", 0.8)
    threshold = config_non_negative_float("backpack_to_storage_match_threshold", 0.80)
    post_click_wait = config_non_negative_float("post_storage_click_wait_seconds", 0.8)

    time.sleep(wait_seconds)

    template_path = "templates/general/backpack_to_storage_button.png"

    try:
        template = load_template(template_path)
    except FileNotFoundError as e:
        write_log(
            f"Storage transfer skipped: template missing | "
            f"path={template_path} | error={e}"
        )
        return False

    if template is None:
        write_log(f"Storage transfer skipped: template failed to load: {template_path}")
        return False

    screenshot = capture_window(GAME_HWND)

    if screenshot is None:
        write_log("Storage transfer skipped: screenshot failed.")
        return False

    # The storage/backpack button appears in the hero panel, not battle_bottom.
    x1, y1, x2, y2 = REGIONS.get("hero_panel", (0, 220, 640, 680))
    region_img = crop(screenshot, (x1, y1, x2, y2))

    if region_img is None:
        write_log("Storage transfer skipped: hero_panel crop failed.")
        return False

    match = match_template(region_img, template)
    confidence = match["confidence"]

    write_log(
        f"Storage button search | region=hero_panel | "
        f"confidence={confidence:.2f} | threshold={threshold:.2f}"
    )

    if confidence < threshold:
        write_log(
            f"Storage button not found; skipping | "
            f"region=hero_panel | confidence={confidence:.2f} | threshold={threshold:.2f}"
        )
        return False

    center_x, center_y = match["center"]
    local_x = x1 + center_x
    local_y = y1 + center_y

    write_log(
        f"Storage button found | region=hero_panel | "
        f"confidence={confidence:.2f} | center=({local_x}, {local_y})"
    )

    click_window_point(GAME_HWND, local_x, local_y, label="backpack_to_storage")
    time.sleep(post_click_wait)

    write_log("Backpack-to-storage click completed.")
    return True

def click_blue_chest_once(hwnd, detections):
    """
    Click the highest-confidence blue chest safely.

    Safety logic:
    - Blue chest is expected to be left of brown chest.
    - Click target is placed inside the left-middle part of the blue chest.
    - If a brown chest is detected to the right, make sure the click point is
      clearly left of the brown chest's left edge.
    """
    blue_detections = [d for d in detections if d["type"] == "blue"]

    if not blue_detections:
        write_log("CLICK FAILED: no blue chest detection available.")
        return False

    best_blue = max(blue_detections, key=lambda d: d["confidence"])

    blue_center_x, blue_center_y = best_blue["center_full"]
    blue_w, blue_h = best_blue["size"]

    blue_left = blue_center_x - blue_w // 2
    blue_right = blue_center_x + blue_w // 2
    blue_top = blue_center_y - blue_h // 2
    blue_bottom = blue_center_y + blue_h // 2

    # Dynamic margin based on actual detected chest size.
    safety_margin = max(4, int(0.12 * blue_w))

    # Since blue is always left of brown, click slightly left of blue center.
    # This keeps the click away from the brown chest.
    local_x = int(blue_left + 0.38 * blue_w)
    local_y = int(blue_top + 0.50 * blue_h)

    # Optional small upward bias if the clickable part is visually higher.
    local_y -= int(0.08 * blue_h)

    brown_detections = [d for d in detections if d["type"] == "brown"]

    nearest_brown_on_right = None
    nearest_brown_left = None

    for brown in brown_detections:
        brown_center_x, brown_center_y = brown["center_full"]
        brown_w, brown_h = brown["size"]

        brown_left = brown_center_x - brown_w // 2

        # Only care about brown chests to the right of the blue chest.
        if brown_center_x > blue_center_x:
            if nearest_brown_left is None or brown_left < nearest_brown_left:
                nearest_brown_left = brown_left
                nearest_brown_on_right = brown

    if nearest_brown_on_right is not None:
        brown_center_x, brown_center_y = nearest_brown_on_right["center_full"]
        brown_w, brown_h = nearest_brown_on_right["size"]

        brown_left = brown_center_x - brown_w // 2

        # The click point must be safely left of the brown chest's left edge.
        max_safe_x = brown_left - safety_margin

        if local_x >= max_safe_x:
            old_x = local_x
            local_x = max(blue_left + safety_margin, max_safe_x)

            write_log(
                f"Adjusted blue click away from brown chest | "
                f"old_x={old_x} | new_x={local_x} | "
                f"brown_left={brown_left} | margin={safety_margin}"
            )

        # If even the adjusted point is outside/unsafe, skip the click.
        if local_x < blue_left or local_x > blue_right:
            write_log(
                f"CLICK BLOCKED: no safe blue click point | "
                f"blue_box=({blue_left},{blue_top})-({blue_right},{blue_bottom}) | "
                f"brown_left={brown_left} | target=({local_x},{local_y})"
            )
            return False

    mouse_before_x, mouse_before_y = pyautogui.position()

    window_rect = win32gui.GetWindowRect(hwnd)
    client_origin = safe_client_origin(hwnd)
    client_x, client_y, screen_x, screen_y, scaling_status = screenshot_local_to_click_coordinates(
        hwnd,
        local_x,
        local_y,
        label="blue_chest",
    )

    write_log(
        f"Clicking blue chest | "
        f"mouse_before=({mouse_before_x}, {mouse_before_y}) | "
        f"screenshot_local=({local_x}, {local_y}) | "
        f"client=({client_x}, {client_y}) | "
        f"screen=({screen_x}, {screen_y}) | "
        f"scaling_active={scaling_status.get('active')} | "
        f"window_rect={window_rect} | "
        f"client_origin={format_diag_value(client_origin)} | "
        f"blue_box=({blue_left},{blue_top})-({blue_right},{blue_bottom}) | "
        f"confidence={best_blue['confidence']:.2f}"
    )

    try:
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.2)
    except Exception as e:
        write_log(f"Window focus warning: {e}")

    if not safe_pyautogui_move_to(
        screen_x,
        screen_y,
        label="blue_chest",
        duration=0.15,
    ):
        return False

    if not safe_pyautogui_click(screen_x, screen_y, label="blue_chest_1"):
        return False
    time.sleep(0.35)

    if not safe_pyautogui_click(screen_x, screen_y, label="blue_chest_2"):
        return False
    time.sleep(0.2)

    if not safe_pyautogui_click(screen_x, screen_y, label="blue_chest_3"):
        return False

    return True

def print_bot_status_on_change(bot_info):
    """
    Print bot status only when important state values change.
    Ignores countdown/message changes to avoid freeze spam.
    """
    global last_bot_status_signature

    signature = (
        bot_info["state"],
        bot_info["boss_visible"],
        bot_info["blue_chest_visible"],
        bot_info["blue_log_visible"],
    )

    if signature == last_bot_status_signature:
        return

    last_bot_status_signature = signature

    safe_print(
        "\n"
        f"Bot state: {bot_info['state']} | "
        f"Boss: {bot_info['boss_visible']} | "
        f"Blue chest: {bot_info['blue_chest_visible']} | "
        f"Blue log: {bot_info['blue_log_visible']} | "
        f"{bot_info['message']}"
    )


def maybe_log_heartbeat(current_time, bot_info):
    global last_heartbeat_log_time

    if current_time - last_heartbeat_log_time < HEARTBEAT_LOG_INTERVAL_SECONDS:
        return

    last_heartbeat_log_time = current_time
    route = get_current_route()
    _, max_trials, _ = get_no_chest_policy_for_current_route()

    write_log(
        "HEARTBEAT | "
        f"state={bot_info['state']} | "
        f"route={current_route_index + 1}/{len(ROUTE)} | "
        f"target={route['difficulty']} | {route['chapter']} | {route['level']} | "
        f"no_chest_count={no_chest_trial_count}/{max_trials}"
    )


def detect_level_in_map(
    img,
    level_template,
    threshold=LEVEL_MATCH_THRESHOLD,
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
    search_region = REGIONS["map_panel"]
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

def make_lparam(x, y):
    """
    Pack x, y into a Win32 LPARAM.
    """
    return (y << 16) | (x & 0xFFFF)


def local_to_screen(hwnd, local_x, local_y):
    """
    Convert captured-window local coordinates to screen coordinates.
    This matches your existing pyautogui click behavior.
    """
    window_left, window_top, _, _ = win32gui.GetWindowRect(hwnd)
    return window_left + local_x, window_top + local_y


def local_to_client(hwnd, local_x, local_y):
    """
    Convert captured-window local coordinates into client coordinates
    for Win32 mouse messages.
    """
    screen_x, screen_y = local_to_screen(hwnd, local_x, local_y)
    client_x, client_y = win32gui.ScreenToClient(hwnd, (screen_x, screen_y))
    return client_x, client_y, screen_x, screen_y


def get_client_screen_point(hwnd, client_x, client_y):
    try:
        screen_x, screen_y = win32gui.ClientToScreen(hwnd, (int(client_x), int(client_y)))
        return screen_x, screen_y
    except Exception:
        window_left, window_top, _, _ = win32gui.GetWindowRect(hwnd)
        return window_left + int(client_x), window_top + int(client_y)


def rect_width_height(rect):
    if rect is None:
        return None

    return max(0, rect[2] - rect[0]), max(0, rect[3] - rect[1])


def build_coordinate_scaling_status(hwnd, screenshot_size=None, client_size=None, reason="runtime"):
    if not COORDINATE_SCALING_ENABLED:
        return {
            "enabled": False,
            "active": False,
            "reason": "disabled",
            "hwnd": hwnd,
        }

    if not COORDINATE_SCALING_AUTO_DETECT:
        return {
            "enabled": True,
            "active": False,
            "reason": "auto_detect_disabled",
            "hwnd": hwnd,
        }

    if client_size is None:
        client_size = rect_width_height(safe_client_rect(hwnd))

    if screenshot_size is None:
        try:
            img = capture_window(hwnd)
            height, width = img.shape[:2]
            screenshot_size = (width, height)
        except Exception as e:
            write_log(
                f"Coordinate scaling warning | reason=screenshot_unavailable | "
                f"context={reason} | error={e}"
            )
            return {
                "enabled": True,
                "active": False,
                "reason": "screenshot_unavailable",
                "hwnd": hwnd,
            }

    if not client_size or not screenshot_size:
        return {
            "enabled": True,
            "active": False,
            "reason": "missing_size",
            "hwnd": hwnd,
            "client_size": client_size,
            "screenshot_size": screenshot_size,
        }

    screenshot_width, screenshot_height = screenshot_size
    client_width, client_height = client_size

    if screenshot_width <= 0 or screenshot_height <= 0 or client_width <= 0 or client_height <= 0:
        return {
            "enabled": True,
            "active": False,
            "reason": "invalid_size",
            "hwnd": hwnd,
            "client_size": client_size,
            "screenshot_size": screenshot_size,
        }

    scale_x = client_width / screenshot_width
    scale_y = client_height / screenshot_height
    mismatch = (
        abs(scale_x - 1.0) > COORDINATE_SCALING_TOLERANCE
        or abs(scale_y - 1.0) > COORDINATE_SCALING_TOLERANCE
    )

    return {
        "enabled": True,
        "active": mismatch,
        "reason": "mismatch_detected" if mismatch else "within_tolerance",
        "hwnd": hwnd,
        "client_size": client_size,
        "screenshot_size": screenshot_size,
        "scale_x": scale_x,
        "scale_y": scale_y,
        "tolerance": COORDINATE_SCALING_TOLERANCE,
    }


def update_coordinate_scaling_status(hwnd, screenshot_size=None, client_size=None, reason="runtime"):
    global coordinate_scaling_status
    coordinate_scaling_status = build_coordinate_scaling_status(
        hwnd,
        screenshot_size=screenshot_size,
        client_size=client_size,
        reason=reason,
    )
    return coordinate_scaling_status


def get_coordinate_scaling_status(hwnd):
    global coordinate_scaling_status

    if coordinate_scaling_status is None or coordinate_scaling_status.get("hwnd") != hwnd:
        coordinate_scaling_status = build_coordinate_scaling_status(hwnd, reason="click")

    return coordinate_scaling_status


def log_coordinate_scaling_status(status):
    status = status or {}
    write_log(
        "Coordinate scaling status | "
        f"enabled={status.get('enabled', COORDINATE_SCALING_ENABLED)} | "
        f"auto_detect={COORDINATE_SCALING_AUTO_DETECT} | "
        f"active={status.get('active')} | "
        f"reason={status.get('reason')} | "
        f"screenshot_size={format_diag_value(status.get('screenshot_size'))} | "
        f"client_size={format_diag_value(status.get('client_size'))} | "
        f"scale_x={status.get('scale_x')} | "
        f"scale_y={status.get('scale_y')} | "
        f"tolerance={COORDINATE_SCALING_TOLERANCE} | "
        f"pause_on_severe_mismatch={PAUSE_ON_SEVERE_COORDINATE_MISMATCH}"
    )


def screenshot_local_to_click_coordinates(hwnd, local_x, local_y, label=""):
    status = get_coordinate_scaling_status(hwnd)

    if not status.get("active"):
        client_x, client_y, screen_x, screen_y = local_to_client(hwnd, local_x, local_y)
        return client_x, client_y, screen_x, screen_y, status

    scale_x = status.get("scale_x", 1.0)
    scale_y = status.get("scale_y", 1.0)
    client_x = int(round(local_x * scale_x))
    client_y = int(round(local_y * scale_y))
    screen_x, screen_y = get_client_screen_point(hwnd, client_x, client_y)

    write_log(
        f"Coordinate scaling applied | label={label} | "
        f"screenshot_local=({local_x}, {local_y}) | "
        f"client_local=({client_x}, {client_y}) | "
        f"screen=({screen_x}, {screen_y}) | "
        f"scale_x={scale_x:.4f} | scale_y={scale_y:.4f}"
    )

    return client_x, client_y, screen_x, screen_y, status


def get_virtual_screen_rect():
    try:
        left = win32api.GetSystemMetrics(76)  # SM_XVIRTUALSCREEN
        top = win32api.GetSystemMetrics(77)  # SM_YVIRTUALSCREEN
        width = win32api.GetSystemMetrics(78)  # SM_CXVIRTUALSCREEN
        height = win32api.GetSystemMetrics(79)  # SM_CYVIRTUALSCREEN

        if width > 0 and height > 0:
            return left, top, left + width, top + height
    except Exception:
        pass

    try:
        width, height = pyautogui.size()
        return 0, 0, width, height
    except Exception:
        return None


def get_monitor_rect_for_point(screen_x, screen_y):
    try:
        monitor = win32api.MonitorFromPoint(
            (int(screen_x), int(screen_y)),
            win32con.MONITOR_DEFAULTTONEAREST,
        )
        info = win32api.GetMonitorInfo(monitor)
        return info.get("Work") or info.get("Monitor")
    except Exception:
        return get_virtual_screen_rect()


def get_monitor_rect_for_window(hwnd):
    try:
        monitor = win32api.MonitorFromWindow(
            hwnd,
            win32con.MONITOR_DEFAULTTONEAREST,
        )
        info = win32api.GetMonitorInfo(monitor)
        return info.get("Work") or info.get("Monitor")
    except Exception:
        rect = safe_window_rect(hwnd)

        if rect is None:
            return get_virtual_screen_rect()

        left, top, right, bottom = rect
        return get_monitor_rect_for_point(
            (left + right) // 2,
            (top + bottom) // 2,
        )


def is_screen_point_fail_safe_risky(screen_x, screen_y, margin=None):
    monitor_rect = get_monitor_rect_for_point(screen_x, screen_y)

    if monitor_rect is None:
        return False

    left, top, right, bottom = monitor_rect
    margin = MOUSE_FAIL_SAFE_MARGIN_PX if margin is None else margin

    if screen_x < left or screen_x >= right or screen_y < top or screen_y >= bottom:
        return True

    return (
        screen_x <= left + margin
        or screen_x >= right - margin
        or screen_y <= top + margin
        or screen_y >= bottom - margin
    )


def clamp_screen_point_to_safe_monitor_area(screen_x, screen_y, hwnd=None):
    monitor_rect = (
        get_monitor_rect_for_window(hwnd)
        if hwnd is not None
        else get_monitor_rect_for_point(screen_x, screen_y)
    )

    if monitor_rect is None:
        return int(screen_x), int(screen_y), None

    left, top, right, bottom = monitor_rect
    margin = MOUSE_FAIL_SAFE_MARGIN_PX

    if right - left <= margin * 2:
        safe_x = (left + right) // 2
    else:
        safe_x = max(left + margin, min(int(screen_x), right - margin - 1))

    if bottom - top <= margin * 2:
        safe_y = (top + bottom) // 2
    else:
        safe_y = max(top + margin, min(int(screen_y), bottom - margin - 1))

    return safe_x, safe_y, monitor_rect


def safe_pyautogui_move_to(screen_x, screen_y, label="mouse_move", duration=0.05):
    if is_screen_point_fail_safe_risky(screen_x, screen_y):
        write_log(
            f"Mouse movement failed safely | label={label} | "
            f"reason=fail_safe_risky_point | screen=({screen_x}, {screen_y}) | "
            f"margin={MOUSE_FAIL_SAFE_MARGIN_PX}"
        )
        return False

    try:
        pyautogui.moveTo(screen_x, screen_y, duration=duration)
        return True
    except pyautogui.FailSafeException:
        write_log(
            f"Mouse movement failed safely | label={label} | "
            "reason=pyautogui_failsafe"
        )
        return False
    except Exception as e:
        write_log(
            f"Mouse movement failed safely | label={label} | "
            f"reason={e}"
        )
        return False


def safe_pyautogui_click(screen_x, screen_y, label="mouse_click"):
    if is_screen_point_fail_safe_risky(screen_x, screen_y):
        write_log(
            f"Mouse click failed safely | label={label} | "
            f"reason=fail_safe_risky_point | screen=({screen_x}, {screen_y}) | "
            f"margin={MOUSE_FAIL_SAFE_MARGIN_PX}"
        )
        return False

    try:
        pyautogui.click(screen_x, screen_y)
        return True
    except pyautogui.FailSafeException:
        write_log(
            f"Mouse movement failed safely | label={label} | "
            "reason=pyautogui_failsafe"
        )
        return False
    except Exception as e:
        write_log(
            f"Mouse click failed safely | label={label} | "
            f"reason={e}"
        )
        return False


def safe_pyautogui_scroll(amount, label="mouse_scroll"):
    try:
        pyautogui.scroll(amount)
        return True
    except pyautogui.FailSafeException:
        write_log(
            f"Mouse movement failed safely | label={label} | "
            "reason=pyautogui_failsafe"
        )
        return False
    except Exception as e:
        write_log(
            f"Mouse scroll failed safely | label={label} | "
            f"reason={e}"
        )
        return False


def screen_to_local(hwnd, screen_x, screen_y):
    window_rect = safe_window_rect(hwnd)

    if window_rect is None:
        return int(screen_x), int(screen_y)

    window_left, window_top, _, _ = window_rect
    return int(screen_x - window_left), int(screen_y - window_top)


def get_client_local_bounds(hwnd, window_rect):
    client_rect = safe_client_rect(hwnd)
    client_origin = safe_client_origin(hwnd)

    if client_rect is None or client_origin is None:
        _left, _top, right, bottom = window_rect
        return 1, 1, max(1, right - window_rect[0] - 2), max(1, bottom - window_rect[1] - 2)

    window_left, window_top, _, _ = window_rect
    client_left, client_top = client_origin
    client_x1 = max(1, client_left - window_left)
    client_y1 = max(1, client_top - window_top)
    client_width = max(1, client_rect[2] - client_rect[0])
    client_height = max(1, client_rect[3] - client_rect[1])
    return (
        client_x1,
        client_y1,
        client_x1 + client_width - 2,
        client_y1 + client_height - 2,
    )


def build_parking_point_from_local(hwnd, local_x, local_y, source, confidence=None, path=None):
    screen_x, screen_y = local_to_screen(hwnd, local_x, local_y)

    if is_screen_point_fail_safe_risky(
        screen_x,
        screen_y,
        margin=MOUSE_PARKING_FAIL_SAFE_MIN_SCREEN_MARGIN_PX,
    ):
        write_log(
            f"Mouse parking candidate unsafe near fail-safe edge | "
            f"source={source} | local=({local_x}, {local_y}) | "
            f"screen=({screen_x}, {screen_y}) | "
            f"margin={MOUSE_PARKING_FAIL_SAFE_MIN_SCREEN_MARGIN_PX}"
        )
        return None

    point = {
        "local": (int(local_x), int(local_y)),
        "screen": (int(screen_x), int(screen_y)),
        "source": source,
        "confidence": confidence,
    }

    if path is not None:
        point["path"] = path

    return point


def make_clamped_client_point(local_x, local_y, client_x1, client_y1, client_x2, client_y2):
    return (
        max(client_x1, min(int(local_x), client_x2)),
        max(client_y1, min(int(local_y), client_y2)),
    )


def get_client_centerish_parking_candidates(client_x1, client_y1, client_x2, client_y2):
    width = max(1, client_x2 - client_x1)
    height = max(1, client_y2 - client_y1)

    return [
        (
            client_x1 + int(width * 0.35),
            client_y1 + int(height * 0.35),
            "client_centerish_upper",
        ),
        (
            client_x1 + int(width * 0.50),
            client_y1 + int(height * 0.45),
            "client_centerish",
        ),
        (
            client_x1 + int(width * 0.65),
            client_y1 + int(height * 0.35),
            "client_centerish_right",
        ),
    ]


def choose_safe_mouse_parking_candidate(hwnd, candidates, client_bounds):
    client_x1, client_y1, client_x2, client_y2 = client_bounds

    for local_x, local_y, source in candidates:
        local_x, local_y = make_clamped_client_point(
            local_x,
            local_y,
            client_x1,
            client_y1,
            client_x2,
            client_y2,
        )
        parking_point = build_parking_point_from_local(
            hwnd,
            local_x,
            local_y,
            source,
        )

        if parking_point is None:
            continue

        if source not in {"manual", "static_client_point"}:
            write_log(
                f"Mouse parking relocated away from fail-safe edge | "
                f"source={source} | local={parking_point['local']} | "
                f"screen={parking_point['screen']} | "
                f"margin={MOUSE_PARKING_FAIL_SAFE_MIN_SCREEN_MARGIN_PX}"
            )

        return parking_point

    write_log(
        f"Mouse parking skipped; no safe parking candidate | "
        f"candidate_count={len(candidates)} | "
        f"margin={MOUSE_PARKING_FAIL_SAFE_MIN_SCREEN_MARGIN_PX}"
    )
    return None


def get_monitor_safe_parking_point(hwnd, reason):
    window_rect = safe_window_rect(hwnd)

    if window_rect is None:
        return None

    x1, y1, x2, y2 = REGIONS["map_panel"]
    local_x = int(x1 + 0.50 * (x2 - x1))
    local_y = int(y1 + 0.50 * (y2 - y1))
    screen_x, screen_y = local_to_screen(hwnd, local_x, local_y)

    clamped_x, clamped_y, monitor_rect = clamp_screen_point_to_safe_monitor_area(
        screen_x,
        screen_y,
        hwnd=hwnd,
    )
    local_x, local_y = screen_to_local(hwnd, clamped_x, clamped_y)

    write_log(
        f"Mouse parking using monitor-safe fallback | reason={reason} | "
        f"original_screen=({screen_x}, {screen_y}) | "
        f"clamped_screen=({clamped_x}, {clamped_y}) | "
        f"monitor_rect={format_diag_value(monitor_rect)}"
    )

    return {
        "local": (int(local_x), int(local_y)),
        "screen": (int(clamped_x), int(clamped_y)),
        "source": "monitor_safe_point",
        "confidence": None,
    }


def get_default_mouse_parking_point(hwnd):
    window_rect = safe_window_rect(hwnd)

    if window_rect is None:
        return None

    window_left, window_top, window_right, window_bottom = window_rect
    width = window_right - window_left
    height = window_bottom - window_top
    client_x1, client_y1, client_x2, client_y2 = get_client_local_bounds(
        hwnd,
        window_rect,
    )

    if width <= 1 or height <= 1:
        return None

    client_bounds = (client_x1, client_y1, client_x2, client_y2)
    candidates = []

    if MOUSE_PARKING_X is not None and MOUSE_PARKING_Y is not None:
        candidates.append((MOUSE_PARKING_X, MOUSE_PARKING_Y, "manual"))
    else:
        candidates.append((MOUSE_PARKING_STATIC_X, MOUSE_PARKING_STATIC_Y, "static_client_point"))

    if MOUSE_PARKING_FAIL_SAFE_RELOCATE_ENABLED:
        candidates.append((
            MOUSE_PARKING_FALLBACK_STATIC_X,
            MOUSE_PARKING_FALLBACK_STATIC_Y,
            "fallback_static_client_point",
        ))
        candidates.extend(get_client_centerish_parking_candidates(*client_bounds))

    return choose_safe_mouse_parking_candidate(
        hwnd,
        candidates,
        client_bounds,
    )


def park_mouse_before_recognition(reason, hwnd=None, enabled=True, recovery_fallback=False):
    if not enabled:
        write_log(f"Mouse parking skipped | reason={reason} | why=recognition_path_disabled")
        return False

    if not MOUSE_PARKING_ENABLED:
        write_log(f"Mouse parking skipped | reason={reason} | why=disabled")
        return False

    if MOUSE_PARKING_MODE == "disabled":
        write_log(f"Mouse parking skipped | reason={reason} | why=mode_disabled")
        return False

    if MOUSE_PARKING_MODE == "recovery_only" and not recovery_fallback:
        write_log(
            f"Mouse parking skipped in normal flow | reason={reason} | "
            "Mouse parking allowed only in recovery fallback"
        )
        return False

    if recovery_fallback:
        write_log(f"Mouse parking allowed only in recovery fallback | reason={reason}")

    if hwnd is None:
        hwnd = GAME_HWND

    if hwnd is None:
        write_log(f"Mouse parking skipped | reason={reason} | why=no_window")
        return False

    raw_strategy = str(
        get_config().get("mouse_parking_strategy", "static_client_point")
    ).strip().lower()

    if raw_strategy in {"map_anchor", "anchor_map", "visual_anchor", "difficulty_anchor"}:
        write_log(
            f"Mouse parking skipped visual-anchor strategy disabled | "
            f"reason={reason} | configured_strategy={raw_strategy} | "
            "using=static_client_point"
        )

    parking_point = get_default_mouse_parking_point(hwnd)

    if parking_point is None:
        write_log(f"Mouse parking skipped | reason={reason} | why=no_safe_point")
        return False

    local_x, local_y = parking_point["local"]
    screen_x, screen_y = parking_point["screen"]
    source = parking_point["source"]
    confidence = parking_point.get("confidence")

    if source == "static_client_point":
        write_log(
            f"Mouse parking using static client point | reason={reason} | "
            f"local=({local_x}, {local_y}) | screen=({screen_x}, {screen_y}) | "
            f"configured=({MOUSE_PARKING_STATIC_X}, {MOUSE_PARKING_STATIC_Y})"
        )
    elif source == "fallback_static_client_point":
        write_log(
            f"Mouse parking using fallback static client point | reason={reason} | "
            f"local=({local_x}, {local_y}) | screen=({screen_x}, {screen_y}) | "
            f"configured=({MOUSE_PARKING_FALLBACK_STATIC_X}, {MOUSE_PARKING_FALLBACK_STATIC_Y})"
        )
    elif source.startswith("client_centerish"):
        write_log(
            f"Mouse parking using center-ish client point | reason={reason} | "
            f"local=({local_x}, {local_y}) | screen=({screen_x}, {screen_y}) | "
            f"source={source}"
        )
    elif source == "manual":
        write_log(
            f"Mouse parking using configured client point | reason={reason} | "
            f"local=({local_x}, {local_y}) | screen=({screen_x}, {screen_y})"
        )

    write_log(
        f"Mouse parking before recognition | reason={reason} | "
        f"local=({local_x}, {local_y}) | screen=({screen_x}, {screen_y}) | "
        f"source={source} | wait={MOUSE_PARKING_WAIT_SECONDS:.2f}"
    )

    if not safe_pyautogui_move_to(
        screen_x,
        screen_y,
        label=f"mouse_parking:{reason}",
        duration=0.05,
    ):
        write_log(f"Mouse parking skipped | reason={reason} | why=move_failed_safe")
        return False

    time.sleep(MOUSE_PARKING_WAIT_SECONDS)
    return True


def background_click_window_point(hwnd, local_x, local_y, label="", coordinate_space="screenshot"):
    """
    Send a background click to the game window without moving the real mouse.
    """
    if coordinate_space == "screenshot":
        client_x, client_y, screen_x, screen_y, scaling_status = screenshot_local_to_click_coordinates(
            hwnd,
            local_x,
            local_y,
            label=label,
        )
    else:
        client_x, client_y, screen_x, screen_y = local_to_client(hwnd, local_x, local_y)
        scaling_status = {"active": False, "reason": f"{coordinate_space}_coordinate_space"}

    window_rect = safe_window_rect(hwnd)
    client_origin = safe_client_origin(hwnd)
    lparam = make_lparam(client_x, client_y)

    write_log(
        f"Background click | label={label} | "
        f"coordinate_space={coordinate_space} | "
        f"local=({local_x}, {local_y}) | "
        f"client=({client_x}, {client_y}) | "
        f"screen=({screen_x}, {screen_y}) | "
        f"scaling_active={scaling_status.get('active')} | "
        f"window_rect={format_diag_value(window_rect)} | "
        f"client_origin={format_diag_value(client_origin)}"
    )

    win32gui.PostMessage(hwnd, win32con.WM_MOUSEMOVE, 0, lparam)
    time.sleep(0.05)

    win32gui.PostMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lparam)
    time.sleep(0.08)

    win32gui.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, lparam)
    time.sleep(NAV_CLICK_DELAY_SECONDS)

    return True


def background_scroll_window_point(hwnd, local_x, local_y, direction, repeat, coordinate_space="legacy_local", source="static"):
    """
    Send background mouse wheel messages to the game window.
    Does not move the real mouse.
    """
    if coordinate_space == "screenshot":
        client_x, client_y, screen_x, screen_y, scaling_status = screenshot_local_to_click_coordinates(
            hwnd,
            local_x,
            local_y,
            label=f"scroll_map_{direction}",
        )
    else:
        client_x, client_y, screen_x, screen_y = local_to_client(hwnd, local_x, local_y)
        scaling_status = {"active": False, "reason": f"{coordinate_space}_coordinate_space"}

    if direction == "up":
        wheel_delta = 120
    else:
        wheel_delta = -120

    # WM_MOUSEWHEEL uses screen coordinates in lParam.
    lparam = make_lparam(screen_x, screen_y)

    # High word of wParam is wheel delta.
    wparam = (wheel_delta & 0xFFFF) << 16

    write_log(
        f"Background scroll | direction={direction} | "
        f"source={source} | coordinate_space={coordinate_space} | "
        f"local=({local_x}, {local_y}) | "
        f"client=({client_x}, {client_y}) | "
        f"screen=({screen_x}, {screen_y}) | "
        f"scaling_active={scaling_status.get('active')} | repeat={repeat}"
    )

    for _ in range(repeat):
        win32gui.PostMessage(hwnd, win32con.WM_MOUSEWHEEL, wparam, lparam)
        time.sleep(0.04)

    time.sleep(0.5)
    return True


def legacy_static_map_scroll_focus():
    x1, y1, x2, y2 = REGIONS["map_panel"]
    map_w = x2 - x1
    map_h = y2 - y1
    return int(x1 + 0.65 * map_w), int(y1 + 0.50 * map_h)


def clamp_point_to_image(point, img, margin):
    if img is None:
        return point

    height, width = img.shape[:2]

    if width <= 0 or height <= 0:
        return point

    max_x = max(margin, width - margin - 1)
    max_y = max(margin, height - margin - 1)
    x = min(max(int(point[0]), margin), max_x)
    y = min(max(int(point[1]), margin), max_y)
    return x, y


def build_dynamic_scroll_focus_from_level(img, route):
    if route is None:
        return None

    try:
        template = load_template(route["level_template"])
    except Exception:
        template = None

    if template is None:
        return None

    map_img = crop(img, REGIONS["map_panel"])

    if map_img is None:
        return None

    match = match_template(map_img, template)
    confidence = match["confidence"]

    if confidence < DYNAMIC_SCROLL_FOCUS_MIN_ANCHOR_CONFIDENCE:
        return None

    map_x1, _, _, _ = clamp_region(img, REGIONS["map_panel"])
    center_x, _center_y = match["center"]
    return {
        "point": (map_x1 + center_x, DYNAMIC_SCROLL_FOCUS_Y),
        "source": "visible_level_template",
        "confidence": confidence,
        "coordinate_space": "screenshot",
    }


def choose_map_scroll_focus(hwnd, route=None):
    fallback_x, fallback_y = legacy_static_map_scroll_focus()
    fallback = {
        "point": (fallback_x, fallback_y),
        "source": "static_map_panel",
        "confidence": None,
        "coordinate_space": "legacy_local",
    }

    if not DYNAMIC_SCROLL_FOCUS_ENABLED:
        write_log(
            f"Dynamic scroll focus fallback | reason=disabled | "
            f"selected_local=({fallback_x}, {fallback_y}) | source=static_map_panel"
        )
        return fallback

    try:
        img = capture_window(hwnd)
    except Exception as e:
        write_log(f"Dynamic scroll focus unavailable | reason=capture_failed | error={e}")
        write_log(
            f"Dynamic scroll focus fallback | reason=capture_failed | "
            f"selected_local=({fallback_x}, {fallback_y}) | source=static_map_panel"
        )
        return fallback

    selected = None

    try:
        _difficulty_name, anchor_center, anchor_confidence, _ = find_best_difficulty_anchor(img)

        if anchor_center is not None and anchor_confidence >= DYNAMIC_SCROLL_FOCUS_MIN_ANCHOR_CONFIDENCE:
            selected = {
                "point": (anchor_center[0], DYNAMIC_SCROLL_FOCUS_Y),
                "source": "difficulty_anchor",
                "confidence": anchor_confidence,
                "coordinate_space": "screenshot",
            }
    except Exception as e:
        write_log(f"Dynamic scroll focus unavailable | source=difficulty_anchor | error={e}")

    if selected is None:
        try:
            chapter_candidates = [
                item
                for item in collect_chapter_tab_candidates(img)
                if item.get("confidence", 0.0) >= DYNAMIC_SCROLL_FOCUS_MIN_ANCHOR_CONFIDENCE
            ]

            if chapter_candidates:
                avg_x = int(round(sum(item["center"][0] for item in chapter_candidates) / len(chapter_candidates)))
                selected = {
                    "point": (avg_x, DYNAMIC_SCROLL_FOCUS_Y),
                    "source": "chapter_tab_geometry",
                    "confidence": max(item["confidence"] for item in chapter_candidates),
                    "coordinate_space": "screenshot",
                }
        except Exception as e:
            write_log(f"Dynamic scroll focus unavailable | source=chapter_tab_geometry | error={e}")

    if selected is None:
        selected = build_dynamic_scroll_focus_from_level(img, route)

    if selected is None:
        write_log(
            f"Dynamic scroll focus fallback | reason=no_dynamic_anchor | "
            f"selected_local=({fallback_x}, {fallback_y}) | source=static_map_panel"
        )
        return fallback

    margin = DYNAMIC_SCROLL_FOCUS_EDGE_MARGIN_PX
    unclamped = selected["point"]
    selected["point"] = clamp_point_to_image(selected["point"], img, margin)

    if selected["point"] != unclamped:
        write_log(
            f"Dynamic scroll focus fallback | reason=clamped_away_from_edge | "
            f"source={selected['source']} | original_local={unclamped} | "
            f"selected_local={selected['point']} | edge_margin={margin}"
        )

    return selected


def resolve_map_scroll_focus(hwnd, route=None, label="scroll"):
    focus = choose_map_scroll_focus(hwnd, route=route)
    local_x, local_y = focus["point"]
    coordinate_space = focus.get("coordinate_space", "legacy_local")

    if coordinate_space == "screenshot":
        client_x, client_y, screen_x, screen_y, scaling_status = screenshot_local_to_click_coordinates(
            hwnd,
            local_x,
            local_y,
            label=label,
        )
    else:
        client_x, client_y, screen_x, screen_y = local_to_client(hwnd, local_x, local_y)
        scaling_status = {"active": False, "reason": f"{coordinate_space}_coordinate_space"}

    write_log(
        f"Dynamic scroll focus selected | "
        f"source={focus.get('source')} | "
        f"anchor_confidence={format_diag_value(focus.get('confidence'))} | "
        f"selected_local=({local_x}, {local_y}) | "
        f"selected_screen=({screen_x}, {screen_y}) | "
        f"coordinate_space={coordinate_space} | "
        f"scaling_active={scaling_status.get('active')}"
    )

    return {
        "local_x": local_x,
        "local_y": local_y,
        "client_x": client_x,
        "client_y": client_y,
        "screen_x": screen_x,
        "screen_y": screen_y,
        "coordinate_space": coordinate_space,
        "source": focus.get("source"),
        "scaling_active": scaling_status.get("active"),
    }


def resolve_legacy_map_scroll_focus(hwnd, reason, label="scroll"):
    local_x, local_y = legacy_static_map_scroll_focus()
    client_x, client_y, screen_x, screen_y = local_to_client(hwnd, local_x, local_y)

    write_log(
        f"Dynamic scroll focus fallback | reason={reason} | "
        f"selected_local=({local_x}, {local_y}) | "
        f"selected_screen=({screen_x}, {screen_y}) | source=static_map_panel"
    )

    return {
        "local_x": local_x,
        "local_y": local_y,
        "client_x": client_x,
        "client_y": client_y,
        "screen_x": screen_x,
        "screen_y": screen_y,
        "coordinate_space": "legacy_local",
        "source": "static_map_panel",
        "scaling_active": False,
    }


def click_window_point(hwnd, local_x, local_y, label="", coordinate_space="screenshot"):
    """
    Click a point using local captured-window coordinates.
    Uses either real mouse or background window message depending on settings.
    """
    if USE_BACKGROUND_INPUT:
        return background_click_window_point(
            hwnd,
            local_x,
            local_y,
            label=label,
            coordinate_space=coordinate_space,
        )

    window_rect = win32gui.GetWindowRect(hwnd)
    client_origin = safe_client_origin(hwnd)

    if coordinate_space == "screenshot":
        client_x, client_y, screen_x, screen_y, scaling_status = screenshot_local_to_click_coordinates(
            hwnd,
            local_x,
            local_y,
            label=label,
        )
    else:
        client_x, client_y, screen_x, screen_y = local_to_client(hwnd, local_x, local_y)
        scaling_status = {"active": False, "reason": f"{coordinate_space}_coordinate_space"}

    write_log(
        f"Click window point | label={label} | "
        f"coordinate_space={coordinate_space} | "
        f"local=({local_x}, {local_y}) | "
        f"client=({client_x}, {client_y}) | "
        f"screen=({screen_x}, {screen_y}) | "
        f"scaling_active={scaling_status.get('active')} | "
        f"window_rect={window_rect} | "
        f"client_origin={format_diag_value(client_origin)}"
    )

    try:
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.2)
    except Exception as e:
        write_log(f"Window focus warning: {e}")

    if not safe_pyautogui_move_to(
        screen_x,
        screen_y,
        label=label,
        duration=0.12,
    ):
        return False

    if not safe_pyautogui_click(screen_x, screen_y, label=label):
        return False

    time.sleep(NAV_CLICK_DELAY_SECONDS)
    return True
    
def scroll_map(hwnd, direction, repeat=None, route=None):
    """
    Scroll inside the map panel from a dynamic safe point.

    direction: 'up' or 'down'
    repeat: number of wheel scroll pulses
    """
    if repeat is None:
        repeat = MAP_SCROLL_CHUNK_REPEAT

    focus = resolve_map_scroll_focus(
        hwnd,
        route=route,
        label=f"scroll_map_{direction}",
    )
    local_x = focus["local_x"]
    local_y = focus["local_y"]
    screen_x = focus["screen_x"]
    screen_y = focus["screen_y"]

    if USE_BACKGROUND_INPUT:
        return background_scroll_window_point(
            hwnd,
            local_x,
            local_y,
            direction=direction,
            repeat=repeat,
            coordinate_space=focus["coordinate_space"],
            source=focus["source"],
        )

    try:
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.2)
    except Exception as e:
        write_log(f"Window focus warning before scroll: {e}")

    move_ok = safe_pyautogui_move_to(
        screen_x,
        screen_y,
        label=f"scroll_map_{direction}",
        duration=0.15,
    )

    if not move_ok and focus["source"] != "static_map_panel":
        focus = resolve_legacy_map_scroll_focus(
            hwnd,
            reason=f"dynamic_move_failed:{focus['source']}",
            label=f"scroll_map_{direction}",
        )
        local_x = focus["local_x"]
        local_y = focus["local_y"]
        screen_x = focus["screen_x"]
        screen_y = focus["screen_y"]
        move_ok = safe_pyautogui_move_to(
            screen_x,
            screen_y,
            label=f"scroll_map_{direction}_fallback",
            duration=0.15,
        )

    if not move_ok:
        return False

    time.sleep(0.1)

    # Focus map panel before scrolling.
    click_ok = safe_pyautogui_click(
        screen_x,
        screen_y,
        label=f"scroll_map_focus_{direction}",
    )

    if not click_ok and focus["source"] != "static_map_panel":
        focus = resolve_legacy_map_scroll_focus(
            hwnd,
            reason=f"dynamic_focus_click_failed:{focus['source']}",
            label=f"scroll_map_{direction}",
        )
        local_x = focus["local_x"]
        local_y = focus["local_y"]
        screen_x = focus["screen_x"]
        screen_y = focus["screen_y"]
        click_ok = safe_pyautogui_click(
            screen_x,
            screen_y,
            label=f"scroll_map_focus_{direction}_fallback",
        )

    if not click_ok:
        return False

    time.sleep(0.15)

    if direction == "up":
        amount = 8
    else:
        amount = -8

    for _ in range(repeat):
        if not safe_pyautogui_scroll(amount, label=f"scroll_map_{direction}"):
            return False

        time.sleep(0.04)

    write_log(
        f"Scrolled map {direction} | "
        f"scroll_source={focus['source']} | "
        f"scroll_point_local=({local_x}, {local_y}) | "
        f"scroll_point_screen=({screen_x}, {screen_y}) | "
        f"scaling_active={focus['scaling_active']} | "
        f"repeat={repeat}"
    )

    time.sleep(0.5)
    return True


def fast_scroll_map_boundary(hwnd, direction, repeat, route=None):
    """
    Fast boundary scroll used by level search only.
    Keeps scroll_map unchanged as the reliable slow fallback.
    """
    if not FAST_SCROLL_USE_BURST:
        start_time = time.time()
        ok = scroll_map(hwnd, direction, repeat=repeat)
        elapsed = time.time() - start_time
        write_log(
            f"NAV fast scroll boundary complete | direction={direction} | "
            f"method=slow_fallback | repeat={repeat} | elapsed={elapsed:.2f}s"
        )
        return ok

    focus = resolve_map_scroll_focus(
        hwnd,
        route=route,
        label=f"fast_scroll_{direction}",
    )
    local_x = focus["local_x"]
    local_y = focus["local_y"]
    screen_x = focus["screen_x"]
    screen_y = focus["screen_y"]

    start_time = time.time()
    burst_count = max(1, FAST_SCROLL_BURST_COUNT)
    burst_units = max(1, repeat // burst_count)
    remainder = max(0, repeat - (burst_units * burst_count))

    if direction == "up":
        wheel_unit = 120
        pyautogui_unit = 8
    else:
        wheel_unit = -120
        pyautogui_unit = -8

    try:
        if USE_BACKGROUND_INPUT:
            lparam = make_lparam(screen_x, screen_y)

            for index in range(burst_count):
                units = burst_units + (remainder if index == burst_count - 1 else 0)
                wheel_delta = wheel_unit * units
                wparam = (wheel_delta & 0xFFFF) << 16
                win32gui.PostMessage(hwnd, win32con.WM_MOUSEWHEEL, wparam, lparam)
                time.sleep(0.01)

            method = "background_burst"
        else:
            try:
                win32gui.SetForegroundWindow(hwnd)
                time.sleep(0.05)
            except Exception as e:
                write_log(f"Window focus warning before fast scroll: {e}")

            move_ok = safe_pyautogui_move_to(
                screen_x,
                screen_y,
                label=f"fast_scroll_{direction}",
                duration=0.02,
            )

            if not move_ok and focus["source"] != "static_map_panel":
                focus = resolve_legacy_map_scroll_focus(
                    hwnd,
                    reason=f"dynamic_fast_move_failed:{focus['source']}",
                    label=f"fast_scroll_{direction}",
                )
                local_x = focus["local_x"]
                local_y = focus["local_y"]
                screen_x = focus["screen_x"]
                screen_y = focus["screen_y"]
                move_ok = safe_pyautogui_move_to(
                    screen_x,
                    screen_y,
                    label=f"fast_scroll_{direction}_fallback",
                    duration=0.02,
                )

            if not move_ok:
                return False

            click_ok = safe_pyautogui_click(
                screen_x,
                screen_y,
                label=f"fast_scroll_focus_{direction}",
            )

            if not click_ok and focus["source"] != "static_map_panel":
                focus = resolve_legacy_map_scroll_focus(
                    hwnd,
                    reason=f"dynamic_fast_focus_click_failed:{focus['source']}",
                    label=f"fast_scroll_{direction}",
                )
                local_x = focus["local_x"]
                local_y = focus["local_y"]
                screen_x = focus["screen_x"]
                screen_y = focus["screen_y"]
                click_ok = safe_pyautogui_click(
                    screen_x,
                    screen_y,
                    label=f"fast_scroll_focus_{direction}_fallback",
                )

            if not click_ok:
                return False
            time.sleep(0.03)

            for index in range(burst_count):
                units = burst_units + (remainder if index == burst_count - 1 else 0)
                if not safe_pyautogui_scroll(
                    pyautogui_unit * units,
                    label=f"fast_scroll_{direction}",
                ):
                    return False
                time.sleep(0.01)

            method = "foreground_burst"

    except pyautogui.FailSafeException:
        write_log(
            "FAST SCROLL ABORTED: PyAutoGUI fail-safe triggered. "
            "Move mouse away from screen corners."
        )
        return False

    elapsed = time.time() - start_time
    write_log(
        f"NAV fast scroll boundary complete | direction={direction} | "
        f"method={method} | repeat={repeat} | bursts={burst_count} | "
        f"scroll_source={focus['source']} | "
        f"scroll_point_local=({local_x}, {local_y}) | "
        f"scroll_point_screen=({screen_x}, {screen_y}) | "
        f"scaling_active={focus['scaling_active']} | elapsed={elapsed:.2f}s"
    )

    return True


def find_level_dot_left_of_text(img, match_info, dot_template, threshold, dot_name="dot"):
    """
    Search for a dot state, white or green, immediately to the left of detected level text.
    """
    text_left, text_top = match_info["top_left_full"]
    text_right, text_bottom = match_info["bottom_right_full"]
    text_w, text_h = match_info["size"]
    _, text_center_y = match_info["center_full"]

    map_x1, map_y1, map_x2, map_y2 = REGIONS["map_panel"]

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

        if confidence >= threshold and vertical_distance <= LEVEL_DOT_MAX_VERTICAL_DISTANCE:
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

    write_log(
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

# def find_level_dot_left_of_text(img, match_info, dot_template):
#     """
#     Search for the white level dot in a constrained box to the LEFT of
#     the detected level text.

#     Returns:
#         found: bool
#         dot_center_full: (x, y) or None
#         confidence: float
#     """
#     text_left, text_top = match_info["top_left_full"]
#     text_right, text_bottom = match_info["bottom_right_full"]
#     text_w, text_h = match_info["size"]

#     map_x1, map_y1, map_x2, map_y2 = REGIONS["map_panel"]

#     # Search only to the left of the level label.
#     # Make this box generous but still constrained.
#     search_x1 = max(map_x1, text_left - int(4.0 * text_w))
#     search_x2 = max(map_x1, text_left - 2)

#     search_y1 = max(map_y1, text_top - int(2.0 * text_h))
#     search_y2 = min(map_y2, text_bottom + int(2.0 * text_h))

#     if search_x2 <= search_x1 or search_y2 <= search_y1:
#         return False, None, 0.0

#     search_img = crop(img, (search_x1, search_y1, search_x2, search_y2))

#     if search_img is None:
#         return False, None, 0.0

#     match = match_template(search_img, dot_template)
#     confidence = match["confidence"]

#     if confidence < LEVEL_DOT_MATCH_THRESHOLD:
#         return False, None, confidence

#     dot_center_x, dot_center_y = match["center"]

#     dot_center_full = (
#         search_x1 + dot_center_x,
#         search_y1 + dot_center_y
#     )

#     return True, dot_center_full, confidence

def click_or_verify_level_dot(hwnd, match_info, route):
    """
    Verify target level selection using green dot.
    If not already selected, find white dot, click it, then verify green dot.
    """
    global last_route_level_selection_evidence
    white_template = load_template(LEVEL_DOT_WHITE_TEMPLATE)
    green_template = load_template(LEVEL_DOT_GREEN_TEMPLATE)

    if white_template is None:
        write_log(f"NAV FAILED: could not load white dot template: {LEVEL_DOT_WHITE_TEMPLATE}")
        return False

    if green_template is None:
        write_log(f"NAV FAILED: could not load green dot template: {LEVEL_DOT_GREEN_TEMPLATE}")
        return False

    img = capture_window(hwnd)

    green_found, green_center, green_conf = find_level_dot_left_of_text(
        img,
        match_info,
        green_template,
        LEVEL_DOT_GREEN_MATCH_THRESHOLD,
        dot_name="green"
    )

    if green_found:
        write_log(
            f"NAV verified: level already selected | "
            f"route={route['level']} | green_dot={green_center} | confidence={green_conf:.2f}"
        )
        last_route_level_selection_evidence = {
            "route_identity": (
                route.get("difficulty"),
                route.get("chapter"),
                route.get("level"),
            ),
            "timestamp": time.time(),
            "source": "green_dot_already_selected",
            "green_center": green_center,
            "green_confidence": green_conf,
        }
        return True

    white_found, white_center, white_conf = find_level_dot_left_of_text(
        img,
        match_info,
        white_template,
        LEVEL_DOT_WHITE_MATCH_THRESHOLD,
        dot_name="white"
    )

    if not white_found:
        write_log(
            f"NAV DOT FAILED: neither green nor white dot found for level {route['level']} | "
            f"green_conf={green_conf:.2f} | white_conf={white_conf:.2f}"
        )
        return False

    write_log(
        f"Found selectable white dot | "
        f"route={route['level']} | dot_center={white_center} | confidence={white_conf:.2f}"
    )

    if ENABLE_ROUTE_NAVIGATION:
        click_ok = click_window_point(
            hwnd,
            white_center[0],
            white_center[1],
            label=f"level_dot_{route['level']}",
        )

        if not click_ok:
            write_log(
                f"NAV DOT FAILED: click failed safely | route={route['level']} | "
                f"dot_center={white_center}"
            )
            return False

        time.sleep(0.8)

        img_after = capture_window(hwnd)

        green_found_after, green_center_after, green_conf_after = find_level_dot_left_of_text(
            img_after,
            match_info,
            green_template,
            LEVEL_DOT_GREEN_MATCH_THRESHOLD,
            dot_name="green_after_click"
        )

        if green_found_after:
            write_log(
                f"NAV verified after click: level selected | "
                f"route={route['level']} | green_dot={green_center_after} | confidence={green_conf_after:.2f}"
            )
            last_route_level_selection_evidence = {
                "route_identity": (
                    route.get("difficulty"),
                    route.get("chapter"),
                    route.get("level"),
                ),
                "timestamp": time.time(),
                "source": "green_dot_after_click",
                "green_center": green_center_after,
                "green_confidence": green_conf_after,
            }
            return True

        write_log(
            f"NAV WARNING: clicked white dot but green verification failed | "
            f"route={route['level']} | green_conf_after={green_conf_after:.2f}"
        )
        save_visual_debug_artifacts(
            img_after,
            reason=f"selected_level_verification_failed:{route['level']}",
            roi=REGIONS["map_panel"],
            target_name=LEVEL_DOT_GREEN_TEMPLATE,
            confidence=green_conf_after,
            threshold=LEVEL_DOT_GREEN_MATCH_THRESHOLD,
        )
        return False

    else:
        write_log(
            f"DRY RUN NAV: would click white dot for level {route['level']} "
            f"at local={white_center}"
        )
        return True

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
    lower = tuple(SELECTED_LEVEL_GREEN_HSV_LOWER)
    upper = tuple(SELECTED_LEVEL_GREEN_HSV_UPPER)
    mask = cv2.inRange(hsv, lower, upper)
    green_pixel_count = int(cv2.countNonZero(mask))
    total_pixels = int(mask.size)
    green_ratio = green_pixel_count / total_pixels if total_pixels else 0.0
    selected = (
        green_pixel_count >= SELECTED_LEVEL_GREEN_PIXEL_MIN
        or green_ratio >= SELECTED_LEVEL_GREEN_RATIO_MIN
    )

    return selected, green_pixel_count, green_ratio


def verify_current_level_selected_by_green_text(img, match_info, route, confidence, threshold):
    selected, green_pixel_count, green_ratio = check_selected_level_green_text(img, match_info)

    if selected:
        write_log(
            f"NAV current level already selected by green text; skipping click/scroll | "
            f"route={route['level']} | level_confidence={confidence:.2f} | "
            f"threshold={threshold:.2f} | green_pixel_count={green_pixel_count} | "
            f"green_ratio={green_ratio:.3f}"
        )
        return True

    write_log(
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

        if delta <= LEVEL_Y_POSITION_TOLERANCE_PX:
            write_log(
                f"NAV Y position outside strict range but within tolerance; continuing with verification | "
                f"route={route['level']} | context={context} | "
                f"center_y={center_y} | expected_y_min={expected_y_min} | "
                f"delta={delta} | tolerance={LEVEL_Y_POSITION_TOLERANCE_PX} | "
                f"confidence={match_info['confidence']:.2f}"
            )
            return True

        write_log(
            f"NAV rejected level {route['level']} by Y position | "
            f"context={context} | "
            f"center_y={center_y} < expected_y_min={expected_y_min} | "
            f"delta={delta} | tolerance={LEVEL_Y_POSITION_TOLERANCE_PX} | "
            f"confidence={match_info['confidence']:.2f}"
        )
        return False

    if expected_y_max is not None and center_y > expected_y_max:
        delta = center_y - expected_y_max

        if delta <= LEVEL_Y_POSITION_TOLERANCE_PX:
            write_log(
                f"NAV Y position outside strict range but within tolerance; continuing with verification | "
                f"route={route['level']} | context={context} | "
                f"center_y={center_y} | expected_y_max={expected_y_max} | "
                f"delta={delta} | tolerance={LEVEL_Y_POSITION_TOLERANCE_PX} | "
                f"confidence={match_info['confidence']:.2f}"
            )
            return True

        write_log(
            f"NAV rejected level {route['level']} by Y position | "
            f"context={context} | "
            f"center_y={center_y} > expected_y_max={expected_y_max} | "
            f"delta={delta} | tolerance={LEVEL_Y_POSITION_TOLERANCE_PX} | "
            f"confidence={match_info['confidence']:.2f}"
        )
        return False

    return True

def try_current_visible_level(hwnd, route, level_template, threshold, context):
    """
    Check the current map view before scrolling.
    Returns True/False when the target is visible, None when not visible.
    """
    if MOUSE_PARKING_BEFORE_LEVEL_DETECTION:
        park_mouse_before_recognition(
            f"level_detection:{route['level']}:{context}",
            hwnd,
        )
    img = capture_window(hwnd)

    found, match_info, confidence = detect_level_in_map(
        img,
        level_template,
        threshold=threshold,
        route=route,
        context=context,
    )

    if (
        not found
        and context == "before_scroll"
        and threshold - confidence <= LEVEL_NEAR_MATCH_MARGIN
    ):
        write_log(
            f"NAV near level match; retrying current view before scroll | "
            f"route={route['level']} | confidence={confidence:.2f} | "
            f"threshold={threshold:.2f} | margin={LEVEL_NEAR_MATCH_MARGIN:.2f}"
        )
        time.sleep(0.5)
        if MOUSE_PARKING_BEFORE_LEVEL_DETECTION:
            park_mouse_before_recognition(
                f"level_detection:{route['level']}:{context}_retry",
                hwnd,
            )
        img = capture_window(hwnd)
        found, match_info, confidence = detect_level_in_map(
            img,
            level_template,
            threshold=threshold,
            route=route,
            context=f"{context}_retry",
        )

    if not found:
        if (
            LEVEL_CAUTIOUS_ACCEPT_THRESHOLD is not None
            and confidence >= LEVEL_CAUTIOUS_ACCEPT_THRESHOLD
        ):
            write_log(
                f"NAV cautious level candidate detected | "
                f"route={route['level']} | context={context} | "
                f"confidence={confidence:.2f} | "
                f"cautious_threshold={LEVEL_CAUTIOUS_ACCEPT_THRESHOLD:.2f} | "
                f"strong_threshold={threshold:.2f} | "
                "not accepting direct execution without verification"
            )

        if (
            context == "before_scroll"
            and match_info is not None
            and threshold - confidence <= LEVEL_NEAR_MATCH_MARGIN
            and level_match_passes_expected_y(route, match_info, context)
            and verify_current_level_selected_by_green_text(
                img,
                match_info,
                route,
                confidence,
                threshold
            )
        ):
            return True

        write_log(
            f"NAV current view: level not visible | "
            f"route={route['level']} | context={context} | "
            f"best_confidence={confidence:.2f} | threshold={threshold:.2f}"
        )
        save_visual_debug_artifacts(
            img,
            reason=f"level_not_found_current_view:{context}",
            roi=REGIONS["map_panel"],
            match_info=match_info,
            target_name=route.get("level_template", route.get("level")),
            confidence=confidence,
            threshold=threshold,
        )
        return None

    if not level_match_passes_expected_y(route, match_info, context):
        return None

    write_log(
        f"NAV found level {route['level']} on current view | "
        f"context={context} | confidence={confidence:.2f} | "
        f"threshold={threshold:.2f} | center={match_info['center_full']} | "
        f"box={match_info['top_left_full']}-{match_info['bottom_right_full']}"
    )

    return click_or_verify_level_dot(hwnd, match_info, route)

def format_seconds(seconds):
    seconds = max(0, int(seconds))
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes:02d}:{secs:02d}"


def get_current_route():
    if active_same_tier_substitute_route is not None:
        return active_same_tier_substitute_route

    return ROUTE[current_route_index]


def clear_active_same_tier_substitute(reason):
    global active_same_tier_substitute_route

    if active_same_tier_substitute_route is None:
        return

    write_log(
        f"Same-tier substitution active route cleared | "
        f"reason={reason} | substitute={route_target_label(active_same_tier_substitute_route)}"
    )
    active_same_tier_substitute_route = None


def set_active_same_tier_substitute(route, original_route, reason):
    global active_same_tier_substitute_route

    active_same_tier_substitute_route = route.copy()
    write_log(
        f"Same-tier substitution active route set | "
        f"reason={reason} | original={route_target_label(original_route)} | "
        f"substitute={route_target_label(active_same_tier_substitute_route)}"
    )


def get_route_navigation_key(route=None):
    if route is None:
        route = get_current_route()

    return (
        current_route_index,
        route.get("difficulty"),
        route.get("chapter"),
        route.get("level"),
    )


def route_target_label(route):
    return f"{route.get('difficulty')} {route.get('chapter')} {route.get('level')}"


def route_identity(route):
    return (
        route.get("difficulty"),
        route.get("chapter"),
        route.get("level"),
    )


def route_level_number(route):
    try:
        return int(str(route.get("level", "0-0")).split("-")[1])
    except (IndexError, TypeError, ValueError):
        return 0


def route_chapter_number(route):
    try:
        return int(str(route.get("chapter", "chapter_0")).split("_")[1])
    except (IndexError, TypeError, ValueError):
        return 0


def same_tier_route_copy(candidate, original_route, source):
    route = candidate.copy()
    route["name"] = (
        f"Same-tier substitute for {original_route.get('name', 'route')}: "
        f"{route.get('difficulty')} {route.get('level')}"
    )

    for key in ("no_chest_retries", "max_trials_if_no_chest"):
        if key in original_route and key not in route:
            route[key] = original_route[key]

    route["_same_tier_substitute"] = True
    route["_same_tier_source"] = source
    return route


def same_tier_priority_sort_key(candidate, original_route):
    return (
        abs(route_level_number(candidate) - route_level_number(original_route)),
        route_chapter_number(candidate),
        route_level_number(candidate),
        str(candidate.get("difficulty", "")),
    )


def detect_same_tier_unavailable_difficulty(original_route, failure_reason, observed, original_tier):
    target_difficulty = original_route.get("difficulty")
    observed_difficulty = (observed or {}).get("difficulty")
    observed_confidence = float((observed or {}).get("difficulty_confidence") or 0.0)

    if not target_difficulty:
        return None

    reason_text = str(failure_reason or "")
    difficulty_related = (
        "difficulty" in reason_text
        or reason_text.startswith("target_invariant_failed")
    )

    if not difficulty_related:
        return None

    if observed_difficulty == target_difficulty:
        return None

    write_log(
        f"Same-tier substitution unavailable difficulty detected | "
        f"original={route_target_label(original_route)} | "
        f"original_tier={original_tier} | "
        f"unavailable_difficulty={target_difficulty} | "
        f"observed_difficulty={observed_difficulty} | "
        f"observed_confidence={observed_confidence:.2f} | "
        f"failure_reason={failure_reason}"
    )
    return target_difficulty


def build_same_tier_substitution_candidates(original_route, unavailable_difficulty=None):
    original_tier = get_chest_tier_for_route(
        original_route.get("difficulty"),
        original_route.get("chapter"),
        original_route.get("level"),
    )

    if original_tier is None:
        return original_tier, [], []

    original_id = route_identity(original_route)
    seen = {original_id}
    candidates = []
    unavailable_skips = []

    def known_same_tier_routes():
        known = []

        for level in AVAILABLE_LEVELS:
            if not level.get("enabled", True):
                continue
            tier = get_chest_tier_for_route(
                level.get("difficulty"),
                level.get("chapter"),
                level.get("level"),
            )
            if tier == original_tier:
                known.append(level)

        return known

    def farm_plan_same_tier_routes():
        planned = []

        for route in ROUTE:
            tier = get_chest_tier_for_route(
                route.get("difficulty"),
                route.get("chapter"),
                route.get("level"),
            )
            if tier == original_tier:
                planned.append(route)

        return planned

    def add_candidate(route, reason, source):
        identity = route_identity(route)

        if identity in seen:
            return

        if unavailable_difficulty and route.get("difficulty") == unavailable_difficulty:
            skipped = {
                "candidate": identity,
                "candidate_tier": original_tier,
                "priority_reason": reason,
                "unavailable_difficulty": unavailable_difficulty,
            }
            unavailable_skips.append(skipped)
            seen.add(identity)
            write_log(
                f"Same-tier substitution candidate skipped due to unavailable difficulty | "
                f"original={route_target_label(original_route)} | "
                f"original_tier={original_tier} | "
                f"unavailable_difficulty={unavailable_difficulty} | "
                f"candidate={route_target_label(route)} | "
                f"candidate_tier={original_tier} | "
                f"priority_reason={reason}"
            )
            return

        if not SAME_TIER_SUBSTITUTION_ALLOW_CROSS_DIFFICULTY and route.get("difficulty") != original_route.get("difficulty"):
            return

        seen.add(identity)
        candidates.append({
            "route": same_tier_route_copy(route, original_route, source),
            "reason": reason,
            "tier": original_tier,
        })

    known_routes = known_same_tier_routes()

    same_chapter = [
        route for route in known_routes
        if route.get("difficulty") == original_route.get("difficulty")
        and route.get("chapter") == original_route.get("chapter")
    ]
    for route in sorted(same_chapter, key=lambda item: same_tier_priority_sort_key(item, original_route)):
        add_candidate(route, "same_difficulty_same_chapter_nearest_level", "available_levels")

    same_difficulty_other_chapter = [
        route for route in known_routes
        if route.get("difficulty") == original_route.get("difficulty")
        and route.get("chapter") != original_route.get("chapter")
    ]
    for route in sorted(same_difficulty_other_chapter, key=lambda item: same_tier_priority_sort_key(item, original_route)):
        add_candidate(route, "same_difficulty_other_chapter", "available_levels")

    if SAME_TIER_SUBSTITUTION_PREFER_FARM_PLAN_ROUTES:
        for route in farm_plan_same_tier_routes():
            add_candidate(route, "farm_plan_same_tier", "farm_plan")

    for route in sorted(known_routes, key=lambda item: same_tier_priority_sort_key(item, original_route)):
        if route.get("difficulty") != original_route.get("difficulty"):
            reason = "cross_difficulty_same_tier"
        else:
            reason = "other_known_same_tier"
        add_candidate(route, reason, "available_levels")

    return original_tier, candidates[:SAME_TIER_SUBSTITUTION_MAX_CANDIDATES], unavailable_skips


def navigate_to_candidate_route_with_recovery(candidate_route, context):
    selected = select_difficulty_and_chapter(GAME_HWND, candidate_route)

    if not selected:
        write_log(
            f"Same-tier substitution candidate difficulty/chapter selection failed | "
            f"context={context} | candidate={route_target_label(candidate_route)}"
        )
        recovered = recover_navigation_hierarchy(
            GAME_HWND,
            candidate_route,
            reason=f"same_tier_substitution_{context}_difficulty_or_chapter_failed",
        )

        if recovered == RECOVERY_REWARD_HANDLED:
            consume_reward_navigation_interruption("same_tier_substitution")
            return True, {"reward_handled": True}

        if not recovered:
            _, observed = check_route_target_invariant(
                GAME_HWND,
                candidate_route,
                f"same_tier_substitution_{context}_recovery_failed",
            )
            return False, observed

    level_ok = find_and_click_level_by_template(GAME_HWND, candidate_route)

    if not level_ok:
        write_log(
            f"Same-tier substitution candidate level selection failed; starting recovery | "
            f"context={context} | candidate={route_target_label(candidate_route)}"
        )
        level_ok = recover_navigation_hierarchy(
            GAME_HWND,
            candidate_route,
            reason=f"same_tier_substitution_{context}_level_failed",
        )

    if level_ok == RECOVERY_REWARD_HANDLED:
        consume_reward_navigation_interruption("same_tier_substitution")
        return True, {"reward_handled": True}

    if not level_ok:
        _, observed = check_route_target_invariant(
            GAME_HWND,
            candidate_route,
            f"same_tier_substitution_{context}_level_recovery_failed",
        )
        return False, observed

    invariant_ok, observed = check_route_target_invariant(
        GAME_HWND,
        candidate_route,
        f"same_tier_substitution_{context}_final_invariant",
    )
    return invariant_ok, observed


def try_same_tier_substitution_before_skip(original_route, failure_reason, observed):
    if not SAME_TIER_SUBSTITUTION_ENABLED:
        write_log(
            f"Same-tier substitution disabled | "
            f"original={route_target_label(original_route)} | reason={failure_reason}"
        )
        observed["same_tier_substitution"] = {"status": "disabled"}
        return False

    original_tier = get_chest_tier_for_route(
        original_route.get("difficulty"),
        original_route.get("chapter"),
        original_route.get("level"),
    )
    unavailable_difficulty = detect_same_tier_unavailable_difficulty(
        original_route,
        failure_reason,
        observed,
        original_tier,
    )
    original_tier, candidates, unavailable_skips = build_same_tier_substitution_candidates(
        original_route,
        unavailable_difficulty=unavailable_difficulty,
    )
    observed["same_tier_substitution"] = {
        "status": "started",
        "original_tier": original_tier,
        "candidate_count": len(candidates),
        "unavailable_difficulty": unavailable_difficulty,
        "unavailable_difficulty_skipped_count": len(unavailable_skips),
    }

    write_log(
        f"Same-tier substitution start | "
        f"original={route_target_label(original_route)} | "
        f"original_tier={original_tier} | reason={failure_reason} | "
        f"max_candidates={SAME_TIER_SUBSTITUTION_MAX_CANDIDATES} | "
        f"unavailable_difficulty={unavailable_difficulty}"
    )

    if original_tier is None or not candidates:
        if unavailable_difficulty and unavailable_skips:
            write_log(
                f"Same-tier substitution skipped; no candidates after unavailable difficulty filter | "
                f"original={route_target_label(original_route)} | "
                f"original_tier={original_tier} | "
                f"unavailable_difficulty={unavailable_difficulty} | "
                f"skipped_candidates={len(unavailable_skips)}"
            )

        write_log(
            f"Same-tier substitution exhausted | "
            f"original={route_target_label(original_route)} | "
            f"original_tier={original_tier} | reason=no_known_same_tier_candidate"
        )
        observed["same_tier_substitution"]["status"] = (
            "no_candidate_after_unavailable_difficulty_filter"
            if unavailable_difficulty and unavailable_skips
            else "no_candidate"
        )
        observed["same_tier_substitution"]["unavailable_difficulty_skips"] = unavailable_skips
        return False

    failed_candidates = []

    for attempt_index, entry in enumerate(candidates, start=1):
        candidate = entry["route"]
        candidate_tier = entry["tier"]
        priority_reason = entry["reason"]

        write_log(
            f"Same-tier substitution candidate | "
            f"attempt={attempt_index}/{len(candidates)} | "
            f"original={route_target_label(original_route)} | "
            f"original_tier={original_tier} | "
            f"candidate={route_target_label(candidate)} | "
            f"candidate_tier={candidate_tier} | "
            f"priority_reason={priority_reason}"
        )

        ok, candidate_observed = navigate_to_candidate_route_with_recovery(
            candidate,
            f"attempt_{attempt_index}",
        )

        if ok:
            if isinstance(candidate_observed, dict) and candidate_observed.get("reward_handled"):
                write_log(
                    f"Same-tier substitution stopped by reward priority | "
                    f"attempt={attempt_index}/{len(candidates)} | "
                    f"candidate={route_target_label(candidate)}"
                )
                observed["same_tier_substitution"] = {
                    "status": "reward_handled",
                    "original_tier": original_tier,
                    "candidate": route_identity(candidate),
                    "attempt": attempt_index,
                }
                return True

            set_active_same_tier_substitute(
                candidate,
                original_route,
                f"same_tier_substitution_attempt_{attempt_index}",
            )
            reset_consecutive_navigation_skips("same_tier_substitution_success")
            reset_route_navigation_retries("same_tier_substitution_success")
            reset_no_chest_trial_count("same_tier_substitution_success")
            reset_route_detection_memory()
            write_log(
                f"Same-tier substitution succeeded | "
                f"attempt={attempt_index}/{len(candidates)} | "
                f"original={route_target_label(original_route)} | "
                f"original_tier={original_tier} | "
                f"candidate={route_target_label(candidate)} | "
                f"candidate_tier={candidate_tier} | "
                f"priority_reason={priority_reason}"
            )
            observed["same_tier_substitution"] = {
                "status": "succeeded",
                "original_tier": original_tier,
                "unavailable_difficulty": unavailable_difficulty,
                "candidate": route_identity(candidate),
                "candidate_tier": candidate_tier,
                "priority_reason": priority_reason,
                "attempt": attempt_index,
                "unavailable_difficulty_skipped_count": len(unavailable_skips),
            }
            return True

        failed_candidates.append({
            "candidate": route_identity(candidate),
            "candidate_tier": candidate_tier,
            "priority_reason": priority_reason,
            "observed": candidate_observed,
        })
        write_log(
            f"Same-tier substitution failed | "
            f"attempt={attempt_index}/{len(candidates)} | "
            f"candidate={route_target_label(candidate)} | "
            f"candidate_tier={candidate_tier} | "
            f"priority_reason={priority_reason}"
        )

    write_log(
        f"Same-tier substitution exhausted | "
        f"original={route_target_label(original_route)} | "
        f"original_tier={original_tier} | attempts={len(candidates)}"
    )
    observed["same_tier_substitution"] = {
        "status": "exhausted",
        "original_tier": original_tier,
        "unavailable_difficulty": unavailable_difficulty,
        "unavailable_difficulty_skips": unavailable_skips,
        "failed_candidates": failed_candidates,
    }
    return False


def reset_consecutive_navigation_skips(reason):
    global consecutive_navigation_skips

    if consecutive_navigation_skips:
        write_log(
            f"Reset consecutive navigation skips | "
            f"previous={consecutive_navigation_skips} | reason={reason}"
        )

    consecutive_navigation_skips = 0


def observe_route_target_state(hwnd, route):
    observed = {
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

    try:
        park_mouse_before_recognition(
            f"route_target_invariant:{route.get('level')}",
            hwnd,
            enabled=(
                MOUSE_PARKING_BEFORE_CHAPTER_DETECTION
                or MOUSE_PARKING_BEFORE_DIFFICULTY_DETECTION
                or MOUSE_PARKING_BEFORE_LEVEL_DETECTION
            ),
        )
        img = capture_window(hwnd)
    except Exception as e:
        observed["error"] = str(e)
        return observed

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
        LEVEL_STRONG_ACCEPT_THRESHOLD,
        route.get("level_match_threshold", LEVEL_MATCH_THRESHOLD),
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

        green_template = load_template(LEVEL_DOT_GREEN_TEMPLATE)

        if green_template is not None:
            green_found, green_center, green_conf = find_level_dot_left_of_text(
                img,
                match_info,
                green_template,
                LEVEL_DOT_GREEN_MATCH_THRESHOLD,
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
    if not ROUTE_INVARIANT_ALLOW_SELECTED_EVIDENCE:
        return False

    level_confidence = observed.get("level_confidence", 0.0) or 0.0

    if level_confidence < ROUTE_INVARIANT_LEVEL_CONFIDENCE_FLOOR:
        return False

    if ROUTE_INVARIANT_REQUIRE_LEVEL_Y_OK and not observed.get("level_y_ok"):
        return False

    green_text_selected = bool(observed.get("green_text_selected"))
    green_dot_selected = bool(observed.get("green_dot_selected"))
    green_dot_confidence = observed.get("green_dot_confidence", 0.0) or 0.0
    aligned_green_dot_selected = (
        green_dot_selected
        and green_dot_confidence >= ROUTE_INVARIANT_GREEN_DOT_MIN_CONFIDENCE
    )

    return green_text_selected or aligned_green_dot_selected


def route_target_invariant_passes(route, observed):
    return (
        route_target_identity_matches(route, observed)
        and observed.get("level_selected")
    )


def route_target_invariant_confidence_is_strong(observed):
    return (
        observed.get("difficulty_confidence", 0.0) >= DIFFICULTY_MATCH_THRESHOLD
        and observed.get("chapter_confidence", 0.0) >= CHAPTER_MATCH_THRESHOLD
    )


def check_route_target_invariant(hwnd, route, reason):
    observed = observe_route_target_state(hwnd, route)

    write_log(
        f"Route target invariant check | reason={reason} | "
        f"target={route_target_label(route)} | "
        f"observed_difficulty={observed.get('difficulty')}:{observed.get('difficulty_confidence', 0.0):.2f} | "
        f"observed_chapter={observed.get('chapter')}:{observed.get('chapter_confidence', 0.0):.2f} | "
        f"level_match={observed.get('level_match_found')}:{observed.get('level_confidence', 0.0):.2f} | "
        f"level_selected={observed.get('level_selected')} | "
        f"level_strict_selected={observed.get('level_strict_selected')} | "
        f"selected_evidence={observed.get('level_selected_evidence_passed')} | "
        f"level_center={observed.get('level_center')}"
    )

    invariant_passed = route_target_invariant_passes(route, observed)

    if not invariant_passed:
        evidence = last_route_level_selection_evidence

        if isinstance(evidence, dict):
            evidence_route_identity = evidence.get("route_identity")
            target_route_identity = (
                route.get("difficulty"),
                route.get("chapter"),
                route.get("level"),
            )
            evidence_timestamp = evidence.get("timestamp") or 0.0
            evidence_age = time.time() - evidence_timestamp
            evidence_green_confidence = evidence.get("green_confidence", 0.0) or 0.0
            level_confidence = observed.get("level_confidence", 0.0) or 0.0

            recent_evidence_ok = (
                evidence_route_identity == target_route_identity
                and evidence_age <= 10.0
                and evidence_green_confidence >= LEVEL_DOT_GREEN_MATCH_THRESHOLD
            )

            current_identity_ok = (
                route_target_identity_matches(route, observed)
                and route_target_invariant_confidence_is_strong(observed)
            )

            relaxed_level_ok = (
                observed.get("level_y_ok")
                and level_confidence >= 0.75
            )

            if recent_evidence_ok and current_identity_ok and relaxed_level_ok:
                observed["level_selected"] = True
                observed["level_selected_by_recent_click_evidence"] = True
                observed["recent_level_selection_evidence"] = {
                    "source": evidence.get("source"),
                    "age": evidence_age,
                    "green_confidence": evidence_green_confidence,
                    "green_center": evidence.get("green_center"),
                }
                invariant_passed = True
                write_log(
                    f"Route target invariant accepted by recent level-click evidence | "
                    f"reason={reason} | target={route_target_label(route)} | "
                    f"evidence_source={evidence.get('source')} | "
                    f"evidence_age={evidence_age:.2f}s | "
                    f"evidence_green_confidence={evidence_green_confidence:.3f} | "
                    f"level_confidence={level_confidence:.3f} | "
                    f"level_y_ok={observed.get('level_y_ok')}"
                )

    if (
        invariant_passed
        and observed.get("level_selected_evidence_passed")
        and not observed.get("level_strict_selected")
    ):
        write_log(
            "Route target invariant accepted by selected-level evidence | "
            f"reason={reason} | target={route_target_label(route)} | "
            f"level_confidence={observed.get('level_confidence', 0.0):.3f} | "
            f"route_threshold={observed.get('level_route_threshold', 0.0):.3f} | "
            f"invariant_floor={ROUTE_INVARIANT_LEVEL_CONFIDENCE_FLOOR:.3f} | "
            f"green_text_selected={observed.get('green_text_selected')} | "
            f"green_dot_selected={observed.get('green_dot_selected')} | "
            f"green_dot_confidence={observed.get('green_dot_confidence', 0.0):.3f} | "
            f"green_dot_min_confidence={ROUTE_INVARIANT_GREEN_DOT_MIN_CONFIDENCE:.3f} | "
            f"level_y_ok={observed.get('level_y_ok')}"
        )

    if invariant_passed and not route_target_invariant_confidence_is_strong(observed):
        write_log(
            f"Route target invariant confidence warning | reason={reason} | "
            f"target={route_target_label(route)} | "
            f"difficulty={observed.get('difficulty')}:{observed.get('difficulty_confidence', 0.0):.2f} "
            f"threshold={DIFFICULTY_MATCH_THRESHOLD:.2f} | "
            f"chapter={observed.get('chapter')}:{observed.get('chapter_confidence', 0.0):.2f} "
            f"threshold={CHAPTER_MATCH_THRESHOLD:.2f} | "
            f"level_match_found={observed.get('level_match_found')} | "
            f"level_y_ok={observed.get('level_y_ok')} | "
            f"green_text_selected={observed.get('green_text_selected')} | "
            f"green_dot_selected={observed.get('green_dot_selected')}"
        )
        write_log(
            f"Route target invariant accepted by identity + level verification | "
            f"reason={reason} | target={route_target_label(route)}"
        )

    if invariant_passed:
        write_log(
            f"Route target invariant passed | reason={reason} | "
            f"target={route_target_label(route)}"
        )
        return True, observed

    write_log(
        f"Route target invariant failed | reason={reason} | "
        f"target={route_target_label(route)} | observed={observed}"
    )
    return False, observed


def write_navigation_failure_report(route_index, route, observed, failure_reason, action_taken):
    try:
        debug_dir = get_debug_dir()
        debug_dir.mkdir(parents=True, exist_ok=True)
        report_path = debug_dir / "navigation_failures.jsonl"
        payload = {
            "timestamp": now_str(),
            "route_index": route_index + 1,
            "route_count": len(ROUTE),
            "target": {
                "difficulty": route.get("difficulty"),
                "chapter": route.get("chapter"),
                "level": route.get("level"),
                "name": route.get("name"),
            },
            "observed": observed,
            "failure_reason": failure_reason,
            "action_taken": action_taken,
        }

        with report_path.open("a", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
            f.write("\n")

        write_log(f"Navigation failure report written | path={report_path}")
    except Exception as e:
        write_log(f"Navigation failure report write failed | error={e}")


def mark_reward_navigation_interruption(context):
    global reward_navigation_interruption

    reward_navigation_interruption = {
        "context": context,
        "route_key": get_route_navigation_key(),
    }


def consume_reward_navigation_interruption(expected_context):
    global reward_navigation_interruption

    if reward_navigation_interruption is None:
        return False

    write_log(
        f"Reward priority took over; stopping old navigation context | "
        f"context={reward_navigation_interruption.get('context')} | "
        f"expected_context={expected_context}"
    )
    reward_navigation_interruption = None
    return True


def clear_stale_reward_navigation_interruption(context):
    global reward_navigation_interruption

    if reward_navigation_interruption is None:
        return

    write_log(
        f"Reward priority already advanced route; clearing old navigation context before {context} | "
        f"old_context={reward_navigation_interruption.get('context')}"
    )
    reward_navigation_interruption = None


def chapter_number_from_key(chapter):
    try:
        return int(str(chapter).split("_")[1])
    except (IndexError, TypeError, ValueError):
        return None


def route_template_is_loadable(route):
    template_path = route.get("level_template")

    if not template_path:
        return False

    return check_template_loadable(template_path)["status"] == "ok"


def find_anchor_level(difficulty, chapter, exclude_level=None):
    chapter_number = chapter_number_from_key(chapter)

    if chapter_number is None:
        return None

    preferred_levels = [
        f"{chapter_number}-1",
        f"{chapter_number}-2",
    ]

    for preferred_level in preferred_levels:
        if preferred_level == exclude_level:
            continue

        for level in AVAILABLE_LEVELS:
            if (
                level.get("difficulty") == difficulty
                and level.get("chapter") == chapter
                and level.get("level") == preferred_level
                and level.get("enabled", True)
                and route_template_is_loadable(level)
            ):
                return level.copy()

    for level in AVAILABLE_LEVELS:
        if (
            level.get("difficulty") == difficulty
            and level.get("chapter") == chapter
            and level.get("level") != exclude_level
            and level.get("enabled", True)
            and route_template_is_loadable(level)
        ):
            return level.copy()

    return None


def find_alternate_chapter_anchor(route):
    difficulty = route.get("difficulty")
    target_chapter = route.get("chapter")

    for chapter in sorted(CHAPTER_TEMPLATES):
        if chapter == target_chapter:
            continue

        anchor = find_anchor_level(difficulty, chapter)

        if anchor is not None:
            return anchor

    return None


def find_alternate_difficulty(route):
    target_difficulty = route.get("difficulty")

    for difficulty in DIFFICULTY_TEMPLATES:
        if difficulty != target_difficulty:
            return difficulty

    return None


def ordered_recovery_difficulties():
    preferred = ["normal", "nightmare", "hell", "torment"]
    ordered = [item for item in preferred if item in DIFFICULTY_TEMPLATES]

    for difficulty in DIFFICULTY_TEMPLATES:
        if difficulty not in ordered:
            ordered.append(difficulty)

    return ordered


def ordered_recovery_chapters():
    preferred = ["chapter_1", "chapter_2", "chapter_3"]
    ordered = [item for item in preferred if item in CHAPTER_TEMPLATES]

    for chapter in sorted(CHAPTER_TEMPLATES):
        if chapter not in ordered:
            ordered.append(chapter)

    return ordered


def select_recovery_reset_difficulty(hwnd, route, context):
    for difficulty in ordered_recovery_difficulties():
        reward_result = check_reward_priority_during_recovery(
            hwnd,
            f"{context}:reset_difficulty:{difficulty}",
        )
        if reward_result == RECOVERY_REWARD_HANDLED:
            return RECOVERY_REWARD_HANDLED

        ok = select_difficulty(hwnd, difficulty, recovery_fallback=True)

        if ok:
            write_log(
                f"RECOVERY reset difficulty anchor selected | "
                f"context={context} | difficulty={difficulty}"
            )
            return difficulty

        write_log(
            f"RECOVERY root candidate unavailable | "
            f"context={context} | type=difficulty | candidate={difficulty}"
        )

    return None


def select_recovery_reset_chapter(hwnd, route, context):
    difficulty = route.get("difficulty")

    for chapter in ordered_recovery_chapters():
        reward_result = check_reward_priority_during_recovery(
            hwnd,
            f"{context}:reset_chapter:{chapter}",
        )
        if reward_result == RECOVERY_REWARD_HANDLED:
            return RECOVERY_REWARD_HANDLED

        anchor = find_anchor_level(difficulty, chapter)

        if anchor is None:
            write_log(
                f"RECOVERY root candidate unavailable | "
                f"context={context} | type=chapter_level_anchor | "
                f"candidate={chapter} | difficulty={difficulty}"
            )
            continue

        chapter_ok = select_chapter(hwnd, chapter, recovery_fallback=True)

        if not chapter_ok:
            write_log(
                f"RECOVERY root candidate unavailable | "
                f"context={context} | type=chapter | candidate={chapter}"
            )
            continue

        level_ok = find_and_click_level_by_template(hwnd, anchor)

        if not level_ok:
            write_log(
                f"RECOVERY root candidate unavailable | "
                f"context={context} | type=level_anchor | "
                f"candidate={anchor['level']} | chapter={chapter}"
            )
            continue

        write_log(
            f"RECOVERY reset chapter anchor selected | "
            f"context={context} | chapter={chapter} | level={anchor['level']}"
        )
        return anchor

    return None


def recover_root_reset(hwnd, route, context):
    write_log(
        f"RECOVERY root reset start | context={context} | "
        f"target={route['difficulty']} | {route['chapter']} | {route['level']}"
    )

    reward_result = check_reward_priority_during_recovery(hwnd, f"{context}:root_start")
    if reward_result == RECOVERY_REWARD_HANDLED:
        return RECOVERY_REWARD_HANDLED

    reset_anchor = None
    reset_difficulty = None

    for difficulty in ordered_recovery_difficulties():
        reward_result = check_reward_priority_during_recovery(
            hwnd,
            f"{context}:root_difficulty:{difficulty}",
        )
        if reward_result == RECOVERY_REWARD_HANDLED:
            return RECOVERY_REWARD_HANDLED

        difficulty_ok = select_difficulty(
            hwnd,
            difficulty,
            recovery_fallback=True,
        )

        if not difficulty_ok:
            write_log(
                f"RECOVERY root candidate unavailable | "
                f"context={context} | type=difficulty | candidate={difficulty}"
            )
            continue

        write_log(
            f"RECOVERY reset difficulty anchor selected | "
            f"context={context} | difficulty={difficulty}"
        )

        reset_route = dict(route)
        reset_route["difficulty"] = difficulty
        candidate_anchor = select_recovery_reset_chapter(
            hwnd,
            reset_route,
            context,
        )

        if candidate_anchor == RECOVERY_REWARD_HANDLED:
            return RECOVERY_REWARD_HANDLED

        if candidate_anchor is None:
            write_log(
                f"RECOVERY root candidate unavailable | "
                f"context={context} | type=difficulty_chapter_level_root | "
                f"candidate={difficulty}"
            )
            continue

        reset_difficulty = difficulty
        reset_anchor = candidate_anchor
        break

    if reset_anchor is None:
        write_log(
            f"RECOVERY root reset failed: no reset difficulty/chapter/level anchor available | "
            f"context={context}"
        )
        return False

    write_log(
        f"RECOVERY reset level anchor selected | "
        f"context={context} | difficulty={reset_anchor['difficulty']} | "
        f"chapter={reset_anchor['chapter']} | level={reset_anchor['level']}"
    )

    target_difficulty_ok = select_difficulty(
        hwnd,
        route["difficulty"],
        recovery_fallback=True,
    )

    if not target_difficulty_ok:
        write_log(
            f"RECOVERY root reset failed: target difficulty unavailable after reset | "
            f"context={context} | target={route['difficulty']} | "
            f"reset_difficulty={reset_difficulty}"
        )
        return False

    target_chapter_ok = select_chapter(
        hwnd,
        route["chapter"],
        recovery_fallback=True,
    )

    if not target_chapter_ok:
        write_log(
            f"RECOVERY root reset failed: target chapter unavailable after reset | "
            f"context={context} | target={route['chapter']}"
        )
        return False

    target_level_ok = find_and_click_level_by_template(hwnd, route)

    write_log(
        f"RECOVERY root reset complete | context={context} | "
        f"target={route['difficulty']} | {route['chapter']} | {route['level']} | "
        f"success={target_level_ok}"
    )

    return target_level_ok


def check_reward_priority_during_recovery(hwnd, context):
    try:
        img = capture_window(hwnd)
        blue_template = load_template("templates/general/chest_blue.png")
        brown_template = load_template("templates/general/chest_brown.png")
    except Exception as e:
        write_log(f"Recovery reward-priority check skipped | context={context} | reason={e}")
        return False

    detections = detect_all_chests(img, blue_template, brown_template)
    blue_detections = [d for d in detections if d["type"] == "blue"]

    if not blue_detections:
        return False

    blue_log_visible, blue_log_region, blue_log_pixels = detect_blue_log(img)
    best_blue_confidence = max(d["confidence"] for d in blue_detections)

    if not blue_log_visible:
        write_log(
            f"Recovery saw blue chest but reward confirmation is uncertain | "
            f"context={context} | blue_confidence={best_blue_confidence:.2f}"
        )
        return False

    write_log(
        f"Reward priority interrupts navigation recovery | "
        f"context={context} | blue_confidence={best_blue_confidence:.2f} | "
        f"log_region={blue_log_region} | blue_pixels={blue_log_pixels}"
    )
    mark_reward_navigation_interruption(context)
    handle_confirmed_blue_drop(
        detections,
        "reward_priority_during_navigation_recovery",
        f"context={context} | blue_confidence={best_blue_confidence:.2f} | "
        f"log_region={blue_log_region} | blue_pixels={blue_log_pixels}",
        allow_pre_boss=True
    )
    return RECOVERY_REWARD_HANDLED


def reset_route_navigation_retries(reason):
    global route_navigation_retry_count
    global route_navigation_retry_key

    if route_navigation_retry_count != 0:
        write_log(
            f"Reset navigation retry count | "
            f"previous={route_navigation_retry_count} | reason={reason}"
        )

    route_navigation_retry_count = 0
    route_navigation_retry_key = get_route_navigation_key()


def record_route_navigation_failure(reason):
    """
    Count failed full navigation attempts for the current route.
    Returns True when another retry is allowed.
    """
    global route_navigation_retry_count
    global route_navigation_retry_key
    global bot_state

    route = get_current_route()
    route_key = get_route_navigation_key(route)

    if route_navigation_retry_key != route_key:
        route_navigation_retry_count = 0
        route_navigation_retry_key = route_key

    route_navigation_retry_count += 1

    write_log(
        f"Navigation retry count | route={route['name']} | "
        f"{route['difficulty']} | {route['chapter']} | {route['level']} | "
        f"failed_attempts={route_navigation_retry_count} | "
        f"max_retries={MAX_ROUTE_NAVIGATION_RETRIES} | reason={reason}"
    )

    if route_navigation_retry_count <= MAX_ROUTE_NAVIGATION_RETRIES:
        return True

    bot_state = STATE_NAVIGATION_FAILED
    log_navigation_failed_marker(reason)
    write_log(
        f"NAV FAILED final; stopping repeated scroll | "
        f"route={route['name']} | difficulty={route['difficulty']} | "
        f"chapter={route['chapter']} | level={route['level']} | "
        f"failed_attempts={route_navigation_retry_count} | "
        f"max_retries={MAX_ROUTE_NAVIGATION_RETRIES}"
    )
    return False


def get_route_timing():
    """
    Legacy timer helper.
    stay_seconds is no longer required because route switching is event-driven.
    Kept only so old overlay code does not crash.
    """
    route = get_current_route()

    elapsed = time.time() - route_start_time
    total = route.get("stay_seconds", 0)

    if total > 0:
        remaining = max(0, total - elapsed)
    else:
        remaining = 0

    return elapsed, remaining, total

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
        write_log(f"TEMPLATE LOAD FAILED: {template_path}")
        return False, None, 0.0, None

    if region_name not in REGIONS:
        write_log(f"REGION NOT FOUND: {region_name}")
        return False, None, 0.0, None

    region = REGIONS[region_name]
    region_img = crop(img, region)

    if region_img is None:
        write_log(f"REGION CROP FAILED: {region_name}")
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
        write_log(f"REGION CROP FAILED: {label}")
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
        write_log(f"REGION CROP FAILED: {label}")
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

def find_best_difficulty_anchor(img):
    """
    Find the currently visible difficulty dropdown anchor inside map_panel.
    """
    best_name = None
    best_center = None
    best_confidence = 0.0
    best_info = None

    for diff_name, diff_templates in DIFFICULTY_TEMPLATES.items():
        _, center, confidence, match_info = find_template_in_box(
            img,
            diff_templates["anchor"],
            REGIONS["map_panel"],
            DIFFICULTY_MATCH_THRESHOLD,
            label=f"difficulty_anchor_{diff_name}"
        )

        if confidence > best_confidence:
            best_name = diff_name
            best_center = center
            best_confidence = confidence
            best_info = match_info

    return best_name, best_center, best_confidence, best_info


DIFFICULTY_DROPDOWN_ORDER = ("normal", "nightmare", "hell", "torment")


def difficulty_dropdown_geometry_option_center(anchor_center, difficulty):
    if anchor_center is None:
        return None, None

    if difficulty not in DIFFICULTY_DROPDOWN_ORDER:
        return None, None

    if DIFFICULTY_DROPDOWN_ROW_SPACING_PX <= 0:
        return None, None

    row_index = DIFFICULTY_DROPDOWN_ORDER.index(difficulty)
    option_x = int(anchor_center[0] + DIFFICULTY_DROPDOWN_OPTION_X_OFFSET)
    option_y = int(
        anchor_center[1]
        + DIFFICULTY_DROPDOWN_FIRST_ROW_OFFSET_Y
        + row_index * DIFFICULTY_DROPDOWN_ROW_SPACING_PX
    )
    return (option_x, option_y), row_index


def verify_difficulty_anchor_after_geometry_click(hwnd, difficulty, recovery_fallback=False):
    park_mouse_before_recognition(
        f"difficulty_geometry_verify:{difficulty}",
        hwnd,
        enabled=MOUSE_PARKING_BEFORE_DIFFICULTY_DETECTION,
        recovery_fallback=recovery_fallback,
    )
    img_after = capture_window(hwnd)
    verified_name, verified_center, anchor_conf, _ = find_best_difficulty_anchor(img_after)

    if verified_name == difficulty and anchor_conf >= DIFFICULTY_MATCH_THRESHOLD:
        write_log(
            f"Difficulty dropdown geometry verification passed | "
            f"target={difficulty} | verified_anchor={verified_name} | "
            f"confidence={anchor_conf:.2f} | center={verified_center}"
        )
        return True, img_after, verified_name, anchor_conf

    write_log(
        f"Difficulty dropdown geometry verification failed | "
        f"target={difficulty} | verified_anchor={verified_name} | "
        f"confidence={anchor_conf:.2f} | threshold={DIFFICULTY_MATCH_THRESHOLD:.2f} | "
        f"center={verified_center}"
    )
    return False, img_after, verified_name, anchor_conf


def try_difficulty_dropdown_geometry_fallback(
    hwnd,
    difficulty,
    anchor_center,
    tab_confidence,
    recovery_fallback=False,
):
    safe_tab_confidence = float(tab_confidence or 0.0)

    if not DIFFICULTY_DROPDOWN_GEOMETRY_FALLBACK_ENABLED:
        write_log(
            f"Difficulty dropdown geometry fallback skipped | "
            f"target={difficulty} | reason=disabled"
        )
        return False, None, None, safe_tab_confidence

    option_center, row_index = difficulty_dropdown_geometry_option_center(anchor_center, difficulty)

    if option_center is None:
        write_log(
            f"Difficulty dropdown geometry fallback skipped | "
            f"target={difficulty} | reason=untrusted_anchor_or_invalid_config | "
            f"anchor_center={anchor_center} | row_spacing={DIFFICULTY_DROPDOWN_ROW_SPACING_PX}"
        )
        return False, None, None, safe_tab_confidence

    write_log(
        f"Difficulty dropdown geometry fallback start | "
        f"target={difficulty} | anchor_center={anchor_center} | "
        f"row_index={row_index} | option_center={option_center} | "
        f"template_confidence={safe_tab_confidence:.2f} | "
        f"row_spacing={DIFFICULTY_DROPDOWN_ROW_SPACING_PX} | "
        f"first_row_offset_y={DIFFICULTY_DROPDOWN_FIRST_ROW_OFFSET_Y} | "
        f"option_x_offset={DIFFICULTY_DROPDOWN_OPTION_X_OFFSET}"
    )

    write_log(
        f"Difficulty dropdown geometry click attempt | "
        f"target={difficulty} | row_index={row_index} | "
        f"computed_option_center={option_center}"
    )
    click_ok = click_window_point(
        hwnd,
        option_center[0],
        option_center[1],
        label=f"difficulty_dropdown_geometry_{difficulty}",
    )

    if not click_ok:
        write_log(
            f"Difficulty dropdown geometry verification failed | "
            f"target={difficulty} | reason=click_failed_safely | "
            f"computed_option_center={option_center}"
        )
        return False, None, None, safe_tab_confidence

    time.sleep(2.0)

    if not DIFFICULTY_DROPDOWN_GEOMETRY_VERIFY_AFTER_CLICK:
        write_log(
            f"Difficulty dropdown geometry verification failed | "
            f"target={difficulty} | reason=verify_after_click_disabled_for_safety"
        )
        return False, None, None, safe_tab_confidence

    return verify_difficulty_anchor_after_geometry_click(
        hwnd,
        difficulty,
        recovery_fallback=recovery_fallback,
    )


def chapter_order_index(chapter):
    try:
        return CHAPTER_ORDER.index(chapter)
    except ValueError:
        return None


def unique_points_by_x(points, tolerance=CHAPTER_TAB_CLUSTER_X_TOLERANCE):
    unique = []

    for point in sorted(points, key=lambda item: item["center"][0]):
        if any(abs(point["center"][0] - existing["center"][0]) <= tolerance for existing in unique):
            continue

        unique.append(point)

    return unique


def build_chapter_geometry(
    selected_center=None,
    selected_confidence=0.0,
    template_identity=None,
    resolved_candidates=None,
):
    if not CHAPTER_GEOMETRY_FALLBACK_ENABLED:
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
        and item.get("confidence", 0.0) >= CHAPTER_GEOMETRY_MIN_CONFIDENCE
    ]

    selected_point = None

    if selected_center is not None and selected_confidence >= CHAPTER_GEOMETRY_MIN_CONFIDENCE:
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

        if len(row_points) >= len(CHAPTER_ORDER):
            row_points = sorted(row_points, key=lambda item: item["center"][0])[:len(CHAPTER_ORDER)]
            centers = {
                chapter: row_points[index]["center"]
                for index, chapter in enumerate(CHAPTER_ORDER)
            }
            source = "dynamic_tab_row_with_selected_center"

    if not centers and len(candidate_points) >= len(CHAPTER_ORDER):
        row_points = unique_points_by_x(candidate_points)

        if len(row_points) >= len(CHAPTER_ORDER):
            row_points = sorted(row_points, key=lambda item: item["center"][0])[:len(CHAPTER_ORDER)]
            centers = {
                chapter: row_points[index]["center"]
                for index, chapter in enumerate(CHAPTER_ORDER)
            }
            source = "dynamic_tab_row_candidates"

    if not centers and selected_point is not None and template_identity in CHAPTER_ORDER:
        write_log(
            f"Chapter geometry self-anchor skipped | "
            f"template_identity={template_identity} | "
            f"selected_center={selected_center} | "
            f"confidence={selected_confidence:.2f}"
        )

    if not centers:
        if CHAPTER_GEOMETRY_REQUIRE_DYNAMIC_ANCHOR:
            return None

        return None

    map_region = REGIONS["map_panel"]

    for chapter, center in centers.items():
        if not point_inside_region(center, map_region):
            write_log(
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

    write_log(
        f"Chapter geometry calibration | source={source} | "
        f"template_identity={template_identity} | selected_center={selected_center} | "
        f"confidence={selected_confidence:.2f} | centers={centers} | "
        f"candidate_count={len(candidate_points)}"
    )
    return geometry


def point_inside_region(point, region):
    if point is None:
        return False

    x, y = point
    x1, y1, x2, y2 = region
    return x1 <= x <= x2 and y1 <= y <= y2


def classify_chapter_by_geometry(point, confidence, geometry):
    if (
        not CHAPTER_GEOMETRY_FALLBACK_ENABLED
        or geometry is None
        or point is None
        or confidence < CHAPTER_GEOMETRY_MIN_CONFIDENCE
    ):
        return None, None

    best_chapter = None
    best_distance = None

    for chapter, center in geometry["centers"].items():
        distance = abs(point[0] - center[0])

        if best_distance is None or distance < best_distance:
            best_chapter = chapter
            best_distance = distance

    if best_distance is None or best_distance > CHAPTER_GEOMETRY_TOLERANCE_PX:
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
        write_log(
            f"Chapter identity conflict | template_identity={template_identity} | "
            f"geometry_identity={geometry_identity} | selected_center={selected_center} | "
            f"confidence={confidence:.2f} | distance={distance} | "
            f"centers={geometry.get('centers')} | source={geometry.get('source')}"
        )
        return geometry_identity, True, distance

    return template_identity, False, distance


def collect_chapter_tab_candidates(img):
    clusters = []

    for chapter, templates in CHAPTER_TEMPLATES.items():
        candidates = find_template_candidates_in_box(
            img,
            templates["normal"],
            REGIONS["map_panel"],
            CHAPTER_TAB_CANDIDATE_THRESHOLD,
            label=f"{chapter}_normal_candidates",
            max_candidates=6,
        )

        for candidate in candidates:
            cx, cy = candidate["center_full"]
            matched_cluster = None

            for cluster in clusters:
                cluster_x, cluster_y = cluster["center"]

                if (
                    abs(cx - cluster_x) <= CHAPTER_TAB_CLUSTER_X_TOLERANCE
                    and abs(cy - cluster_y) <= CHAPTER_TAB_CLUSTER_Y_TOLERANCE
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

    for chapter, templates in CHAPTER_TEMPLATES.items():
        _, center, confidence, match_info = find_template_in_box(
            img,
            templates["selected"],
            REGIONS["map_panel"],
            CHAPTER_MATCH_THRESHOLD,
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
    write_log(f"Chapter tab candidates | target={target_chapter} | {summary}")

    for item in resolved:
        if item["chapter"] == target_chapter and item["confidence"] >= CHAPTER_AMBIGUOUS_MIN_CONFIDENCE:
            sorted_scores = sorted(
                item["scores"].items(),
                key=lambda score_item: score_item[1],
                reverse=True,
            )

            if len(sorted_scores) >= 2:
                best_chapter, best_score = sorted_scores[0]
                second_chapter, second_score = sorted_scores[1]

                if best_score - second_score <= CHAPTER_CANDIDATE_AMBIGUITY_MARGIN:
                    write_log(
                        f"Chapter candidate ambiguous | "
                        f"target={target_chapter} | best={best_chapter}:{best_score:.2f} | "
                        f"second={second_chapter}:{second_score:.2f} | "
                        f"margin={CHAPTER_CANDIDATE_AMBIGUITY_MARGIN:.2f} | "
                        f"candidate_confidence={item['confidence']:.2f} | "
                        f"ambiguous_min_confidence={CHAPTER_AMBIGUOUS_MIN_CONFIDENCE:.2f}"
                    )
                    save_visual_debug_artifacts(
                        img,
                        reason=f"chapter_candidate_ambiguous:{target_chapter}",
                        roi=REGIONS["map_panel"],
                        target_name=target_chapter,
                        confidence=best_score,
                        threshold=CHAPTER_MATCH_THRESHOLD,
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

            if item["confidence"] >= CHAPTER_MATCH_THRESHOLD:
                return True, item["center"], item["confidence"], item

    best_confidence = max((item["confidence"] for item in resolved), default=0.0)
    save_visual_debug_artifacts(
        img,
        reason=f"chapter_visual_state_ambiguous:{target_chapter}",
        roi=REGIONS["map_panel"],
        target_name=target_chapter,
        confidence=best_confidence,
        threshold=CHAPTER_MATCH_THRESHOLD,
    )
    return False, None, 0.0, {"resolved": resolved}


def reset_chapter_ambiguous_attempt_scope(reason):
    global chapter_ambiguous_click_attempts
    global chapter_ambiguous_attempt_scope_id
    global chapter_geometry_click_attempts

    cleared = len(chapter_ambiguous_click_attempts)
    geometry_cleared = len(chapter_geometry_click_attempts)
    chapter_ambiguous_click_attempts = {}
    chapter_geometry_click_attempts = {}
    chapter_ambiguous_attempt_scope_id += 1
    write_log(
        f"Chapter ambiguous attempt scope reset | "
        f"reason={reason} | scope={chapter_ambiguous_attempt_scope_id} | "
        f"cleared={cleared} | geometry_cleared={geometry_cleared}"
    )


def get_chapter_ambiguous_click_key(chapter, center):
    if center is None:
        return chapter_ambiguous_attempt_scope_id, chapter, None

    return chapter_ambiguous_attempt_scope_id, chapter, int(center[0]), int(center[1])


def get_chapter_ambiguous_click_count(chapter, center):
    return chapter_ambiguous_click_attempts.get(
        get_chapter_ambiguous_click_key(chapter, center),
        0
    )


def record_chapter_ambiguous_click_attempt(chapter, center):
    key = get_chapter_ambiguous_click_key(chapter, center)
    chapter_ambiguous_click_attempts[key] = chapter_ambiguous_click_attempts.get(key, 0) + 1
    write_log(
        f"Chapter ambiguous attempt recorded | "
        f"target={chapter} | center={center} | "
        f"scope={chapter_ambiguous_attempt_scope_id} | "
        f"attempt={chapter_ambiguous_click_attempts[key]}/{CHAPTER_AMBIGUOUS_CLICK_MAX_ATTEMPTS}"
    )
    return chapter_ambiguous_click_attempts[key]


def clear_chapter_ambiguous_attempt(chapter, center, reason):
    key = get_chapter_ambiguous_click_key(chapter, center)

    if key in chapter_ambiguous_click_attempts:
        del chapter_ambiguous_click_attempts[key]
        write_log(
            f"Chapter ambiguous attempt cleared after verification | "
            f"target={chapter} | center={center} | "
            f"scope={chapter_ambiguous_attempt_scope_id} | reason={reason}"
        )


def clear_chapter_ambiguous_attempts_for_chapter(chapter, reason):
    matching_keys = [
        key
        for key in chapter_ambiguous_click_attempts
        if len(key) >= 2 and key[0] == chapter_ambiguous_attempt_scope_id and key[1] == chapter
    ]
    geometry_keys = [
        key
        for key in chapter_geometry_click_attempts
        if len(key) >= 2 and key[0] == chapter_ambiguous_attempt_scope_id and key[1] == chapter
    ]

    for key in matching_keys:
        del chapter_ambiguous_click_attempts[key]

    for key in geometry_keys:
        del chapter_geometry_click_attempts[key]

    if matching_keys or geometry_keys:
        write_log(
            f"Chapter ambiguous attempts cleared after verification | "
            f"target={chapter} | scope={chapter_ambiguous_attempt_scope_id} | "
            f"cleared={len(matching_keys)} | geometry_cleared={len(geometry_keys)} | "
            f"reason={reason}"
        )


def get_chapter_geometry_click_key(chapter, center):
    if center is None:
        return chapter_ambiguous_attempt_scope_id, chapter, None

    return chapter_ambiguous_attempt_scope_id, chapter, int(center[0]), int(center[1])


def try_geometry_chapter_click_and_verify(hwnd, chapter, center, geometry, reason):
    if not CHAPTER_GEOMETRY_FALLBACK_ENABLED:
        return False

    if center is None or geometry is None:
        return False

    if not point_inside_region(center, REGIONS["map_panel"]):
        write_log(
            f"Chapter geometry fallback candidate rejected | "
            f"target={chapter} | center={center} | reason=outside_map_panel | "
            f"source={geometry.get('source')}"
        )
        return False

    key = get_chapter_geometry_click_key(chapter, center)
    previous_attempts = chapter_geometry_click_attempts.get(key, 0)

    if previous_attempts >= 1:
        write_log(
            f"Chapter geometry click attempt blocked within current context | "
            f"target={chapter} | center={center} | scope={chapter_ambiguous_attempt_scope_id} | "
            f"attempts={previous_attempts}/1"
        )
        return False

    chapter_geometry_click_attempts[key] = previous_attempts + 1
    write_log(
        f"Chapter geometry click attempt | target={chapter} | center={center} | "
        f"attempt=1/1 | reason={reason} | source={geometry.get('source')} | "
        f"centers={geometry.get('centers')}"
    )

    click_ok = click_window_point(
        hwnd,
        center[0],
        center[1],
        label=f"chapter_geometry_{chapter}",
    )

    if not click_ok:
        write_log(
            f"Chapter geometry verification failed | "
            f"target={chapter} | reason=click_failed_safely | center={center}"
        )
        return False

    time.sleep(0.8)
    park_mouse_before_recognition(
        f"chapter_geometry_verify:{chapter}",
        hwnd,
        enabled=MOUSE_PARKING_BEFORE_CHAPTER_DETECTION,
        recovery_fallback=True,
    )
    img_after = capture_window(hwnd)
    verified_chapter, selected_center_after, selected_conf_after, _ = find_current_chapter(img_after)

    if verified_chapter == chapter and selected_conf_after >= CHAPTER_GEOMETRY_MIN_CONFIDENCE:
        write_log(
            f"Chapter geometry verification passed | target={chapter} | "
            f"verified={verified_chapter} | confidence={selected_conf_after:.2f} | "
            f"center={selected_center_after}"
        )
        clear_chapter_ambiguous_attempts_for_chapter(
            chapter,
            "chapter_geometry_click_verified",
        )
        return True

    write_log(
        f"Chapter geometry verification failed | target={chapter} | "
        f"verified={verified_chapter} | confidence={selected_conf_after:.2f} | "
        f"center={selected_center_after}"
    )
    return False


def try_ambiguous_chapter_click_and_verify(hwnd, chapter, center, confidence, candidate_info):
    if not CHAPTER_AMBIGUOUS_CLICK_VERIFY_ENABLED:
        write_log(
            f"Chapter candidate ambiguous; bounded click-and-verify disabled | "
            f"target={chapter}"
        )
        return False

    if center is None:
        write_log(
            f"Chapter candidate ambiguous; no target center available for click-and-verify | "
            f"target={chapter}"
        )
        return False

    if confidence < CHAPTER_AMBIGUOUS_MIN_CONFIDENCE:
        write_log(
            f"Chapter candidate ambiguous; confidence below click-and-verify minimum | "
            f"target={chapter} | confidence={confidence:.2f} | "
            f"minimum={CHAPTER_AMBIGUOUS_MIN_CONFIDENCE:.2f}"
        )
        return False

    previous_attempts = get_chapter_ambiguous_click_count(chapter, center)

    if previous_attempts >= CHAPTER_AMBIGUOUS_CLICK_MAX_ATTEMPTS:
        write_log(
            f"Chapter ambiguous attempt blocked within current context | "
            f"target={chapter} | center={center} | "
            f"scope={chapter_ambiguous_attempt_scope_id} | "
            f"attempts={previous_attempts}/{CHAPTER_AMBIGUOUS_CLICK_MAX_ATTEMPTS}"
        )
        return False

    best_chapter = candidate_info.get("best_chapter")
    best_score = candidate_info.get("best_score")
    second_chapter = candidate_info.get("second_chapter")
    second_score = candidate_info.get("second_score")

    write_log(
        f"Chapter candidate ambiguous; attempting bounded click-and-verify | "
        f"target={chapter} | center={center} | confidence={confidence:.2f} | "
        f"best={best_chapter}:{best_score:.2f} | "
        f"second={second_chapter}:{second_score:.2f}"
    )

    attempt = record_chapter_ambiguous_click_attempt(chapter, center)
    write_log(
        f"Chapter ambiguous click attempt | "
        f"target={chapter} | attempt={attempt}/{CHAPTER_AMBIGUOUS_CLICK_MAX_ATTEMPTS} | "
        f"center={center} | confidence={confidence:.2f}"
    )

    click_ok = click_window_point(hwnd, center[0], center[1], label=f"chapter_ambiguous_{chapter}")

    if not click_ok:
        write_log(
            f"Chapter ambiguous click verification failed | "
            f"target={chapter} | reason=click_failed_safely | center={center}"
        )
        return False

    time.sleep(0.8)

    park_mouse_before_recognition(
        f"chapter_ambiguous_verify:{chapter}",
        hwnd,
        enabled=MOUSE_PARKING_BEFORE_CHAPTER_DETECTION,
    )
    img_after = capture_window(hwnd)
    verified_chapter, selected_center_after, selected_conf_after, verify_info = find_current_chapter(img_after)
    verify_geometry_used = bool(verify_info and verify_info.get("geometry_used"))
    verify_threshold = (
        CHAPTER_GEOMETRY_MIN_CONFIDENCE
        if verify_geometry_used
        else CHAPTER_MATCH_THRESHOLD
    )

    if verified_chapter == chapter and selected_conf_after >= verify_threshold:
        write_log(
            f"Chapter ambiguous click verified | "
            f"target={chapter} | verified={verified_chapter} | "
            f"confidence={selected_conf_after:.2f} | center={selected_center_after} | "
            f"threshold={verify_threshold:.2f} | geometry_used={verify_geometry_used}"
        )
        clear_chapter_ambiguous_attempt(
            chapter,
            center,
            "ambiguous_click_verified",
        )
        return True

    write_log(
        f"Chapter ambiguous click verification failed | "
        f"target={chapter} | verified={verified_chapter} | "
        f"confidence={selected_conf_after:.2f} | center={selected_center_after} | "
        f"threshold={verify_threshold:.2f} | geometry_used={verify_geometry_used}"
    )
    return False


def skip_current_route_due_to_navigation_failure(reason, observed=None):
    global current_route_index
    global route_start_time
    global bot_state
    global freeze_start_time
    global current_cycle_number
    global consecutive_navigation_skips

    route_index = current_route_index
    route = get_current_route()
    observed = observed or {}

    if not route.get("_same_tier_substitute"):
        substitute_ok = try_same_tier_substitution_before_skip(
            route,
            reason,
            observed,
        )

        if substitute_ok:
            route_start_time = time.time()
            bot_state = STATE_FREEZE_AFTER_SWITCH
            freeze_start_time = time.time()
            write_log(
                f"Same-tier substitution completed before route skip | "
                f"original_route={route_index + 1}/{len(ROUTE)} | "
                f"active_target={route_target_label(get_current_route())} | "
                "entering freeze window"
            )
            return True
    else:
        write_log(
            f"Same-tier substitution not retried for substitute route | "
            f"target={route_target_label(route)} | reason={reason}"
        )
        observed["same_tier_substitution"] = {"status": "not_retried_for_substitute_route"}

    if NAVIGATION_FAILURE_POLICY == "pause":
        write_log(
            f"Navigation recovery failed for active route | "
            f"policy=pause | route={route_index + 1}/{len(ROUTE)} | "
            f"target={route_target_label(route)} | reason={reason}"
        )
        write_navigation_failure_report(route_index, route, observed, reason, "paused")
        clear_active_same_tier_substitute("navigation_failure_pause")
        bot_state = STATE_NAVIGATION_FAILED
        log_navigation_failed_marker(reason)
        return False

    consecutive_navigation_skips += 1
    skipped_routes_this_session.append({
        "timestamp": now_str(),
        "route_index": route_index + 1,
        "route": route.copy(),
        "reason": reason,
        "observed": observed,
    })

    write_log(
        f"Navigation recovery failed for active route | "
        f"route={route_index + 1}/{len(ROUTE)} | "
        f"target={route_target_label(route)} | reason={reason}"
    )
    write_log(
        f"Route skipped due to navigation failure | "
        f"route={route_index + 1}/{len(ROUTE)} | "
        f"target={route_target_label(route)} | "
        f"consecutive_skips={consecutive_navigation_skips}/{MAX_CONSECUTIVE_NAVIGATION_SKIPS}"
    )

    if SHOW_NAVIGATION_FAILURE_WARNING:
        write_log(
            f"关卡导航失败 {route_index + 1}: "
            f"{route_target_label(route)}. 该关卡被跳过，MAA继续运行。 "
            "请导出log文件以供分析。若不打算分析该问题，请无视本条消息。"
        )

    write_navigation_failure_report(route_index, route, observed, reason, "skipped")

    if consecutive_navigation_skips >= MAX_CONSECUTIVE_NAVIGATION_SKIPS:
        write_log(
            f"Too many consecutive navigation skips; pausing bot | "
            f"consecutive_skips={consecutive_navigation_skips} | "
            f"max={MAX_CONSECUTIVE_NAVIGATION_SKIPS}"
        )
        clear_active_same_tier_substitute("max_consecutive_navigation_skips")
        bot_state = STATE_NAVIGATION_FAILED
        log_navigation_failed_marker("max_consecutive_navigation_skips")
        return False

    previous_index = current_route_index
    previous_route = route
    previous_cycle = current_cycle_number

    current_route_index = (current_route_index + 1) % len(ROUTE)
    clear_active_same_tier_substitute("navigation_failure_skip")

    if current_route_index == 0 and previous_index == len(ROUTE) - 1:
        current_cycle_number += 1

    route_start_time = time.time()
    reset_no_chest_trial_count("route_skipped_navigation_failure")
    reset_route_detection_memory()
    reset_route_navigation_retries("route_skipped_navigation_failure")
    reset_chapter_ambiguous_attempt_scope("route_skipped_navigation_failure")

    next_route = get_current_route()
    log_route_advance_marker(
        previous_index,
        previous_route,
        current_route_index,
        next_route,
        "navigation_failure_skip",
        previous_cycle=previous_cycle,
        next_cycle=current_cycle_number,
    )
    write_log(
        f"Continuing to next route after navigation failure | "
        f"next_route={current_route_index + 1}/{len(ROUTE)} | "
        f"target={route_target_label(next_route)}"
    )

    navigation_ok = navigate_to_current_route_if_enabled()

    if not navigation_ok:
        return False

    bot_state = STATE_FREEZE_AFTER_SWITCH
    freeze_start_time = time.time()
    write_log("Route skip navigation completed. Entering freeze window.")
    return True


def select_difficulty(hwnd, difficulty, recovery_fallback=False):
    """
    Select difficulty using:
    - anchor template: currently selected difficulty button / dropdown opener
    - tab template: option inside opened dropdown
    """
    if difficulty not in DIFFICULTY_TEMPLATES:
        write_log(f"NAV FAILED: unknown difficulty {difficulty}")
        return False

    templates = DIFFICULTY_TEMPLATES[difficulty]

    park_mouse_before_recognition(
        f"difficulty_anchor_detection:{difficulty}",
        hwnd,
        enabled=MOUSE_PARKING_BEFORE_DIFFICULTY_DETECTION,
        recovery_fallback=recovery_fallback,
    )
    img = capture_window(hwnd)
    best_anchor_name, current_anchor_center, best_anchor_conf, _ = find_best_difficulty_anchor(img)

    # 1. If the strongest visible anchor is the target, difficulty is selected.
    if best_anchor_name == difficulty and best_anchor_conf >= DIFFICULTY_MATCH_THRESHOLD:
        write_log(
            f"Difficulty already selected | difficulty={difficulty} | "
            f"anchor_confidence={best_anchor_conf:.2f} | center={current_anchor_center}"
        )
        return True

    # 2. Click the current visible difficulty anchor to open dropdown.
    if current_anchor_center is None or best_anchor_conf < DIFFICULTY_MATCH_THRESHOLD:
        maybe_save_debug_screenshot(
            img,
            folder="debug_screenshots/nav_failures",
            prefix=f"difficulty_anchor_fail_{difficulty}"
        )

        write_log(
            f"NAV FAILED: could not find current difficulty anchor | "
            f"target={difficulty} | best_anchor={best_anchor_name} | "
            f"best_anchor_conf={best_anchor_conf:.2f} | search_region=map_panel"
        )
        return False

    write_log(
        f"Opening difficulty dropdown | "
        f"current_anchor={best_anchor_name} | "
        f"center={current_anchor_center} | confidence={best_anchor_conf:.2f}"
    )

    click_ok = click_window_point(
        hwnd,
        current_anchor_center[0],
        current_anchor_center[1],
        label="difficulty_anchor_open"
    )

    if not click_ok:
        write_log(
            f"NAV FAILED: difficulty anchor click failed safely | "
            f"target={difficulty} | center={current_anchor_center}"
        )
        return False

    time.sleep(0.5)

    # 3. After dropdown opens, find target difficulty tab.
    park_mouse_before_recognition(
        f"difficulty_dropdown_detection:{difficulty}",
        hwnd,
        enabled=MOUSE_PARKING_BEFORE_DIFFICULTY_DETECTION,
        recovery_fallback=recovery_fallback,
    )
    img_dropdown = capture_window(hwnd)

    found_tab, tab_center, tab_conf, _ = find_template_in_box(
        img_dropdown,
        templates["tab"],
        REGIONS["map_panel"],
        DIFFICULTY_MATCH_THRESHOLD,
        label=f"difficulty_dropdown_{difficulty}"
    )

    if not found_tab:
        write_log(
            f"Difficulty tab not found; reopening dropdown once | "
            f"target={difficulty} | first_confidence={tab_conf:.2f}"
        )

        reopen_click_ok = click_window_point(
            hwnd,
            current_anchor_center[0],
            current_anchor_center[1],
            label="difficulty_anchor_reopen"
        )

        if not reopen_click_ok:
            write_log(
                f"NAV FAILED: difficulty anchor reopen click failed safely | "
                f"target={difficulty} | center={current_anchor_center}"
            )
            return False

        time.sleep(0.8)
        park_mouse_before_recognition(
            f"difficulty_dropdown_retry_detection:{difficulty}",
            hwnd,
            enabled=MOUSE_PARKING_BEFORE_DIFFICULTY_DETECTION,
            recovery_fallback=recovery_fallback,
        )
        img_dropdown = capture_window(hwnd)

        found_tab, tab_center, tab_conf, _ = find_template_in_box(
            img_dropdown,
            templates["tab"],
            REGIONS["map_panel"],
            DIFFICULTY_MATCH_THRESHOLD,
            label=f"difficulty_dropdown_retry_{difficulty}"
        )

    if not found_tab:
        geometry_ok, geometry_img, geometry_verified_name, geometry_conf = (
            try_difficulty_dropdown_geometry_fallback(
                hwnd,
                difficulty,
                current_anchor_center,
                tab_conf,
                recovery_fallback=recovery_fallback,
            )
        )

        if geometry_ok:
            return True

        maybe_save_debug_screenshot(
            geometry_img if geometry_img is not None else img_dropdown,
            folder="debug_screenshots/nav_failures",
            prefix=f"difficulty_tab_fail_{difficulty}"
        )

        write_log(
            f"NAV FAILED: target difficulty tab not found after opening dropdown | "
            f"target={difficulty} | tab_confidence={tab_conf:.2f} | "
            f"geometry_verified={geometry_verified_name} | "
            f"geometry_confidence={geometry_conf:.2f} | search_region=map_panel"
        )
        return False

    write_log(
        f"Clicking difficulty tab | difficulty={difficulty} | "
        f"center={tab_center} | confidence={tab_conf:.2f}"
    )

    tab_click_ok = click_window_point(
        hwnd,
        tab_center[0],
        tab_center[1],
        label=f"difficulty_tab_{difficulty}"
    )

    if not tab_click_ok:
        write_log(
            f"NAV FAILED: difficulty tab click failed safely | "
            f"target={difficulty} | center={tab_center}"
        )
        return False

    time.sleep(2.0)

    # 4. Verify target anchor after selecting.
    park_mouse_before_recognition(
        f"difficulty_verify:{difficulty}",
        hwnd,
        enabled=MOUSE_PARKING_BEFORE_DIFFICULTY_DETECTION,
        recovery_fallback=recovery_fallback,
    )
    img_after = capture_window(hwnd)
    verified_name, verified_center, anchor_conf_after, _ = find_best_difficulty_anchor(img_after)

    if verified_name == difficulty and anchor_conf_after >= DIFFICULTY_MATCH_THRESHOLD:
        write_log(
            f"Difficulty verified | difficulty={difficulty} | "
            f"anchor_confidence={anchor_conf_after:.2f} | center={verified_center}"
        )
        return True

    write_log(
        f"Difficulty verification retry | target={difficulty} | "
        f"first_verified={verified_name} | first_confidence={anchor_conf_after:.2f}"
    )

    time.sleep(0.8)
    park_mouse_before_recognition(
        f"difficulty_verify_retry:{difficulty}",
        hwnd,
        enabled=MOUSE_PARKING_BEFORE_DIFFICULTY_DETECTION,
        recovery_fallback=recovery_fallback,
    )
    img_after_retry = capture_window(hwnd)
    verified_name_retry, verified_center_retry, anchor_conf_retry, _ = find_best_difficulty_anchor(img_after_retry)

    if verified_name_retry == difficulty and anchor_conf_retry >= DIFFICULTY_MATCH_THRESHOLD:
        write_log(
            f"Difficulty verified after retry | difficulty={difficulty} | "
            f"anchor_confidence={anchor_conf_retry:.2f} | center={verified_center_retry}"
        )
        return True

    write_log(
        f"NAV WARNING: difficulty tab clicked but anchor verification failed | "
        f"target={difficulty} | verified_anchor={verified_name_retry} | "
        f"anchor_confidence={anchor_conf_retry:.2f}"
    )
    save_visual_debug_artifacts(
        img_after_retry,
        reason=f"difficulty_verification_failed:{difficulty}",
        roi=REGIONS["map_panel"],
        target_name=DIFFICULTY_TEMPLATES[difficulty]["anchor"],
        confidence=anchor_conf_retry,
        threshold=DIFFICULTY_MATCH_THRESHOLD,
    )

    return False

def select_chapter(hwnd, chapter, recovery_fallback=False):
    """
    Click chapter tab and verify selected chapter template.
    """
    if chapter not in CHAPTER_TEMPLATES:
        write_log(f"NAV FAILED: unknown chapter {chapter}")
        return False

    park_mouse_before_recognition(
        f"chapter_visual_state:{chapter}",
        hwnd,
        enabled=MOUSE_PARKING_BEFORE_CHAPTER_DETECTION,
        recovery_fallback=recovery_fallback,
    )
    img = capture_window(hwnd)
    current_chapter, selected_center, selected_conf, current_info = find_current_chapter(img)
    current_geometry = current_info.get("chapter_geometry") if current_info else None
    current_geometry_used = bool(current_info and current_info.get("geometry_used"))

    write_log(
        f"Chapter visual state | target={chapter} | "
        f"current={current_chapter} | selected_center={selected_center} | "
        f"selected_confidence={selected_conf:.2f} | geometry_used={current_geometry_used}"
    )

    # 1. If target chapter is already selected, no click is needed.
    already_selected_threshold = (
        CHAPTER_GEOMETRY_MIN_CONFIDENCE
        if current_geometry_used
        else CHAPTER_MATCH_THRESHOLD
    )
    current_geometry_source = (
        current_geometry.get("source")
        if isinstance(current_geometry, dict)
        else None
    )
    if (
        current_chapter == chapter
        and selected_conf >= already_selected_threshold
        and current_geometry_source == "selected_template_dynamic_anchor"
    ):
        write_log(
            f"Chapter already-selected rejected due to weak self-anchored geometry | "
            f"target={chapter} | current={current_chapter} | "
            f"selected_center={selected_center} | confidence={selected_conf:.2f} | "
            f"geometry_source={current_geometry_source} | "
            f"centers={current_geometry.get('centers') if isinstance(current_geometry, dict) else None}"
        )
        current_chapter = None

    if current_chapter == chapter and selected_conf >= already_selected_threshold:
        write_log(
            f"Chapter already selected | chapter={chapter} | "
            f"confidence={selected_conf:.2f} | center={selected_center} | "
            f"threshold={already_selected_threshold:.2f} | geometry_used={current_geometry_used}"
        )
        clear_chapter_ambiguous_attempts_for_chapter(
            chapter,
            "chapter_already_verified",
        )
        return True

    # 2. Find the target chapter's visible unselected tab inside map_panel.
    found_tab, tab_center, tab_conf, candidate_info = find_chapter_tab_candidate(
        img,
        chapter
    )

    if not found_tab:
        if candidate_info and candidate_info.get("ambiguous"):
            ambiguous_ok = try_ambiguous_chapter_click_and_verify(
                hwnd,
                chapter,
                tab_center,
                tab_conf,
                candidate_info,
            )

            if ambiguous_ok:
                return True

        geometry = current_geometry

        if geometry is None:
            resolved = candidate_info.get("resolved", []) if candidate_info else []
            geometry = build_chapter_geometry(
                selected_center=selected_center,
                selected_confidence=selected_conf,
                template_identity=current_chapter,
                resolved_candidates=resolved,
            )

        geometry_center = (
            geometry.get("centers", {}).get(chapter)
            if geometry is not None
            else None
        )

        if geometry_center is not None:
            write_log(
                f"Chapter geometry fallback candidate | "
                f"target={chapter} | center={geometry_center} | "
                f"current={current_chapter} | selected_center={selected_center} | "
                f"confidence={selected_conf:.2f} | source={geometry.get('source')} | "
                f"centers={geometry.get('centers')}"
            )
            geometry_ok = try_geometry_chapter_click_and_verify(
                hwnd,
                chapter,
                geometry_center,
                geometry,
                "target_tab_template_missing_or_ambiguous",
            )

            if geometry_ok:
                return True

        maybe_save_debug_screenshot(
            img,
            folder="debug_screenshots/nav_failures",
            prefix=f"chapter_tab_fail_{chapter}"
        )

        write_log(
            f"NAV FAILED: chapter tab not found | "
            f"chapter={chapter} | confidence={tab_conf:.2f} | "
            f"current={current_chapter} | selected_confidence={selected_conf:.2f} | "
            f"search_region=map_panel"
        )
        return False

    write_log(
        f"Clicking chapter tab | chapter={chapter} | "
        f"center={tab_center} | confidence={tab_conf:.2f}"
    )

    click_ok = click_window_point(hwnd, tab_center[0], tab_center[1], label=chapter)

    if not click_ok:
        write_log(
            f"NAV FAILED: chapter tab click failed safely | "
            f"chapter={chapter} | center={tab_center}"
        )
        return False

    time.sleep(0.8)

    # 3. Verify selected chapter.
    park_mouse_before_recognition(
        f"chapter_verify:{chapter}",
        hwnd,
        enabled=MOUSE_PARKING_BEFORE_CHAPTER_DETECTION,
        recovery_fallback=recovery_fallback,
    )
    img_after = capture_window(hwnd)
    verified_chapter, selected_center_after, selected_conf_after, verify_info = find_current_chapter(img_after)
    verify_geometry_used = bool(verify_info and verify_info.get("geometry_used"))
    verify_threshold = (
        CHAPTER_GEOMETRY_MIN_CONFIDENCE
        if verify_geometry_used
        else CHAPTER_MATCH_THRESHOLD
    )

    if verified_chapter == chapter and selected_conf_after >= verify_threshold:
        write_log(
            f"Chapter verified | chapter={chapter} | "
            f"confidence={selected_conf_after:.2f} | center={selected_center_after} | "
            f"threshold={verify_threshold:.2f} | geometry_used={verify_geometry_used}"
        )
        clear_chapter_ambiguous_attempts_for_chapter(
            chapter,
            "chapter_click_verified",
        )
        return True

    write_log(
        f"NAV WARNING: chapter click done but verification failed | "
        f"target={chapter} | verified={verified_chapter} | "
        f"center={selected_center_after} | confidence={selected_conf_after:.2f} | "
        f"threshold={verify_threshold:.2f} | geometry_used={verify_geometry_used}"
    )

    maybe_save_debug_screenshot(
        img_after,
        folder="debug_screenshots/nav_failures",
        prefix=f"chapter_verify_fail_{chapter}"
    )

    return False

def select_difficulty_and_chapter(hwnd, route):
    """
    Select/verify target difficulty and chapter before searching for the level.
    """
    difficulty = route["difficulty"]
    chapter = route["chapter"]

    write_log(
        f"Selecting difficulty/chapter | "
        f"difficulty={difficulty} | chapter={chapter}"
    )

    difficulty_ok = select_difficulty(hwnd, difficulty)

    if not difficulty_ok:
        write_log(f"NAV FAILED: difficulty selection failed | difficulty={difficulty}")
        return False

    chapter_ok = select_chapter(hwnd, chapter)

    if not chapter_ok:
        write_log(f"NAV FAILED: chapter selection failed | chapter={chapter}")
        return False

    write_log(
        f"Difficulty/chapter selection completed | "
        f"difficulty={difficulty} | chapter={chapter}"
    )

    return True


def recover_difficulty(hwnd, route):
    target_difficulty = route["difficulty"]

    for attempt in range(1, NAVIGATION_RECOVERY_MAX_ATTEMPTS + 1):
        reward_result = check_reward_priority_during_recovery(hwnd, f"difficulty_attempt_{attempt}")
        if reward_result == RECOVERY_REWARD_HANDLED:
            return RECOVERY_REWARD_HANDLED

        write_log(
            f"RECOVERY difficulty attempt {attempt}/{NAVIGATION_RECOVERY_MAX_ATTEMPTS} | "
            f"target={target_difficulty} | reset_order={ordered_recovery_difficulties()}"
        )

        reset_difficulty = select_recovery_reset_difficulty(
            hwnd,
            route,
            f"difficulty_attempt_{attempt}",
        )

        if reset_difficulty == RECOVERY_REWARD_HANDLED:
            return RECOVERY_REWARD_HANDLED

        if reset_difficulty is None:
            continue

        target_ok = select_difficulty(
            hwnd,
            target_difficulty,
            recovery_fallback=True,
        )

        write_log(
            f"RECOVERY difficulty result | attempt={attempt} | "
            f"target={target_difficulty} | reset_difficulty={reset_difficulty} | "
            f"success={target_ok}"
        )

        if target_ok:
            return True

    return False


def recover_chapter(hwnd, route):
    target_chapter = route["chapter"]
    target_anchor = find_anchor_level(
        route["difficulty"],
        target_chapter,
        exclude_level=route.get("level")
    )

    if target_anchor is None:
        write_log(
            f"RECOVERY chapter failed: no target chapter anchor available | "
            f"target={target_chapter}"
        )
        return False

    for attempt in range(1, NAVIGATION_RECOVERY_MAX_ATTEMPTS + 1):
        reset_chapter_ambiguous_attempt_scope(f"chapter_recovery_attempt_{attempt}")
        reward_result = check_reward_priority_during_recovery(hwnd, f"chapter_attempt_{attempt}")
        if reward_result == RECOVERY_REWARD_HANDLED:
            return RECOVERY_REWARD_HANDLED

        write_log(
            f"RECOVERY chapter attempt {attempt}/{NAVIGATION_RECOVERY_MAX_ATTEMPTS} | "
            f"target={target_chapter} | reset_order={ordered_recovery_chapters()} | "
            f"target_anchor={target_anchor['level']}"
        )

        reset_anchor = select_recovery_reset_chapter(
            hwnd,
            route,
            f"chapter_attempt_{attempt}",
        )

        if reset_anchor == RECOVERY_REWARD_HANDLED:
            return RECOVERY_REWARD_HANDLED

        if reset_anchor is None:
            continue

        write_log(
            f"Recovery alternate anchor selected; returning to target chapter | "
            f"attempt={attempt} | alternate_anchor={reset_anchor['level']} | "
            f"target_chapter={target_chapter} | target_level={route['level']}"
        )
        target_chapter_ok = select_chapter(
            hwnd,
            target_chapter,
            recovery_fallback=True,
        )

        if not target_chapter_ok:
            write_log(
                f"Recovery target chapter verification failed after alternate anchor | "
                f"attempt={attempt} | alternate_anchor={reset_anchor['level']} | "
                f"target_chapter={target_chapter} | target_level={route['level']}"
            )
            continue

        target_anchor_ok = find_and_click_level_by_template(hwnd, target_anchor)

        write_log(
            f"RECOVERY chapter result | attempt={attempt} | "
            f"target={target_chapter} | target_anchor={target_anchor['level']} | "
            f"success={target_anchor_ok}"
        )

        if target_anchor_ok:
            return True

    return False


def recover_level(hwnd, route):
    anchor = find_anchor_level(
        route["difficulty"],
        route["chapter"],
        exclude_level=route.get("level")
    )

    if anchor is None:
        write_log(
            f"RECOVERY level failed: no same-chapter anchor available | "
            f"target={route['level']} | chapter={route['chapter']}"
        )
        return False

    for attempt in range(1, NAVIGATION_RECOVERY_MAX_ATTEMPTS + 1):
        reward_result = check_reward_priority_during_recovery(hwnd, f"level_attempt_{attempt}")
        if reward_result == RECOVERY_REWARD_HANDLED:
            return RECOVERY_REWARD_HANDLED

        write_log(
            f"RECOVERY level attempt {attempt}/{NAVIGATION_RECOVERY_MAX_ATTEMPTS} | "
            f"target={route['level']} | same_chapter_anchor={anchor['level']}"
        )

        anchor_ok = find_and_click_level_by_template(hwnd, anchor)

        if not anchor_ok:
            write_log(
                f"RECOVERY level anchor selection failed | "
                f"attempt={attempt} | anchor={anchor['level']}"
            )
            continue

        target_ok = find_and_click_level_by_template(hwnd, route)

        write_log(
            f"RECOVERY level result | attempt={attempt} | "
            f"target={route['level']} | anchor={anchor['level']} | success={target_ok}"
        )

        if target_ok:
            return True

    return False


def recover_navigation_hierarchy(hwnd, route, reason):
    write_log(
        f"RECOVERY hierarchy start | reason={reason} | "
        f"target={route['difficulty']} | {route['chapter']} | {route['level']} | "
        f"max_attempts={NAVIGATION_RECOVERY_MAX_ATTEMPTS}"
    )

    reward_result = check_reward_priority_during_recovery(hwnd, "hierarchy_start")
    if reward_result == RECOVERY_REWARD_HANDLED:
        return RECOVERY_REWARD_HANDLED

    difficulty_ok = select_difficulty(
        hwnd,
        route["difficulty"],
        recovery_fallback=True,
    )

    if not difficulty_ok:
        write_log("RECOVERY hierarchy escalating to difficulty recovery.")
        difficulty_ok = recover_difficulty(hwnd, route)

    if difficulty_ok == RECOVERY_REWARD_HANDLED:
        return RECOVERY_REWARD_HANDLED

    if not difficulty_ok:
        root_reset_result = recover_root_reset(
            hwnd,
            route,
            "difficulty_recovery_failed",
        )

        if root_reset_result == RECOVERY_REWARD_HANDLED:
            return RECOVERY_REWARD_HANDLED

        if root_reset_result:
            return True

        img = capture_window(hwnd)
        save_visual_debug_artifacts(
            img,
            reason=f"navigation_recovery_failed:difficulty:{route['difficulty']}",
            roi=REGIONS["map_panel"],
            target_name=DIFFICULTY_TEMPLATES[route["difficulty"]]["anchor"],
            threshold=DIFFICULTY_MATCH_THRESHOLD,
        )
        write_log("RECOVERY hierarchy failed at difficulty verification.")
        return False

    chapter_ok = select_chapter(
        hwnd,
        route["chapter"],
        recovery_fallback=True,
    )

    if not chapter_ok:
        write_log("RECOVERY hierarchy escalating to chapter recovery.")
        chapter_ok = recover_chapter(hwnd, route)

    if chapter_ok == RECOVERY_REWARD_HANDLED:
        return RECOVERY_REWARD_HANDLED

    if not chapter_ok:
        root_reset_result = recover_root_reset(
            hwnd,
            route,
            "chapter_recovery_failed",
        )

        if root_reset_result == RECOVERY_REWARD_HANDLED:
            return RECOVERY_REWARD_HANDLED

        if root_reset_result:
            return True

        img = capture_window(hwnd)
        save_visual_debug_artifacts(
            img,
            reason=f"navigation_recovery_failed:chapter:{route['chapter']}",
            roi=REGIONS["map_panel"],
            target_name=route["chapter"],
            threshold=CHAPTER_MATCH_THRESHOLD,
        )
        write_log("RECOVERY hierarchy failed at chapter verification.")
        return False

    level_ok = recover_level(hwnd, route)

    if level_ok == RECOVERY_REWARD_HANDLED:
        return RECOVERY_REWARD_HANDLED

    if not level_ok:
        write_log("RECOVERY hierarchy escalating level failure to chapter recovery.")

        chapter_recovery_result = recover_chapter(hwnd, route)

        if chapter_recovery_result == RECOVERY_REWARD_HANDLED:
            return RECOVERY_REWARD_HANDLED

        if chapter_recovery_result:
            level_ok = find_and_click_level_by_template(hwnd, route)

    if not level_ok:
        root_reset_result = recover_root_reset(
            hwnd,
            route,
            "level_recovery_failed",
        )

        if root_reset_result == RECOVERY_REWARD_HANDLED:
            return RECOVERY_REWARD_HANDLED

        if root_reset_result:
            return True

        img = capture_window(hwnd)
        save_visual_debug_artifacts(
            img,
            reason=f"navigation_recovery_failed:level:{route['level']}",
            roi=REGIONS["map_panel"],
            target_name=route.get("level_template", route.get("level")),
            threshold=route.get("level_match_threshold", LEVEL_MATCH_THRESHOLD),
        )
        write_log("RECOVERY hierarchy failed at level verification.")
        return False

    write_log(
        f"RECOVERY hierarchy succeeded | "
        f"target={route['difficulty']} | {route['chapter']} | {route['level']}"
    )
    return True


def navigate_to_current_route_if_enabled(activate_boss_gate=False):
    global bot_state

    route = get_current_route()
    clear_stale_reward_navigation_interruption("new_route_navigation")
    reset_chapter_ambiguous_attempt_scope("new_route_navigation")

    log_route_start_marker(current_route_index, route)

    if not ENABLE_ROUTE_NAVIGATION:
        write_log(
            f"DRY RUN NAV: route navigation disabled | "
            f"target={route['difficulty']} | {route['chapter']} | {route['level']}"
        )
        return False

    write_log(
        f"Starting route navigation | "
        f"target={route['difficulty']} | {route['chapter']} | {route['level']}"
    )

    selected = select_difficulty_and_chapter(GAME_HWND, route)

    if not selected:
        write_log(f"Route navigation FAILED during difficulty/chapter selection for {route['name']}")
        recovered = recover_navigation_hierarchy(
            GAME_HWND,
            route,
            reason="difficulty_or_chapter_selection_failed"
        )

        if recovered == RECOVERY_REWARD_HANDLED:
            consume_reward_navigation_interruption("difficulty_or_chapter_selection_failed")
            return True

        if not recovered:
            _, observed = check_route_target_invariant(
                GAME_HWND,
                route,
                "recovery_failed_after_difficulty_or_chapter_selection",
            )
            return skip_current_route_due_to_navigation_failure(
                "difficulty_or_chapter_selection_failed_after_recovery",
                observed,
            )

        reset_route_navigation_retries("route_navigation_recovery_success")
        write_log(f"Route navigation recovered for {route['name']} | {route['level']}")

        invariant_ok, observed = check_route_target_invariant(
            GAME_HWND,
            route,
            "after_difficulty_or_chapter_recovery",
        )

        if not invariant_ok:
            return skip_current_route_due_to_navigation_failure(
                "target_invariant_failed_after_difficulty_or_chapter_recovery",
                observed,
            )

        reset_consecutive_navigation_skips("route_navigation_recovery_success")

        if activate_boss_gate:
            reset_route_detection_memory()
            bot_state = STATE_LOOK_FOR_BOSS
            write_log("Manual navigation recovery completed. Now looking for boss warning.")

        return True

    success = find_and_click_level_by_template(GAME_HWND, route)

    if not success:
        write_log(f"Route navigation level selection failed; starting recovery for {route['name']} | {route['level']}")
        success = recover_navigation_hierarchy(
            GAME_HWND,
            route,
            reason="level_selection_failed"
        )

    if success == RECOVERY_REWARD_HANDLED:
        consume_reward_navigation_interruption("level_selection_failed")
        return True

    if success:
        invariant_ok, observed = check_route_target_invariant(
            GAME_HWND,
            route,
            "after_route_navigation",
        )

        if not invariant_ok:
            write_log(
                f"Route navigation reported success but final target invariant failed; "
                f"attempting recovery before skip | target={route_target_label(route)}"
            )
            recovered = recover_navigation_hierarchy(
                GAME_HWND,
                route,
                reason="target_invariant_failed_after_navigation"
            )

            if recovered == RECOVERY_REWARD_HANDLED:
                consume_reward_navigation_interruption("target_invariant_failed_after_navigation")
                return True

            if not recovered:
                return skip_current_route_due_to_navigation_failure(
                    "target_invariant_failed_after_navigation_and_recovery",
                    observed,
                )

            invariant_ok, observed = check_route_target_invariant(
                GAME_HWND,
                route,
                "after_target_invariant_recovery",
            )

            if not invariant_ok:
                return skip_current_route_due_to_navigation_failure(
                    "target_invariant_failed_after_recovery",
                    observed,
                )

        reset_consecutive_navigation_skips("route_navigation_success")
        reset_route_navigation_retries("route_navigation_success")
        write_log(f"Route navigation completed for {route['name']} | {route['level']}")

        if activate_boss_gate:
            reset_route_detection_memory()
            bot_state = STATE_LOOK_FOR_BOSS
            write_log("Manual navigation completed. Now looking for boss warning.")
    else:
        write_log(f"Route navigation FAILED for {route['name']} | {route['level']}")
        _, observed = check_route_target_invariant(
            GAME_HWND,
            route,
            "navigation_failed_after_recovery",
        )
        return skip_current_route_due_to_navigation_failure(
            "level_selection_failed_after_recovery",
            observed,
        )

    return success

def navigate_to_startup_route():
    """
    Enter the first planned route before normal detection is allowed.

    This prevents an old chest from the user's current screen from advancing
    the farm plan before Route 1 has actually been selected.
    """
    global bot_state, freeze_start_time, route_start_time

    route = get_current_route()

    bot_state = STATE_STARTUP_NAVIGATION
    route_start_time = time.time()
    reset_no_chest_trial_count("startup_route_navigation")
    reset_route_detection_memory()

    write_log(
        f"Startup route navigation | "
        f"target={route['difficulty']} | {route['chapter']} | {route['level']}"
    )

    success = navigate_to_current_route_if_enabled()

    if success:
        reset_route_detection_memory()
        bot_state = STATE_FREEZE_AFTER_SWITCH
        freeze_start_time = time.time()
        write_log("Startup navigation completed. Entering freeze window.")
        return True

    if bot_state == STATE_NAVIGATION_FAILED:
        write_log("Startup navigation ended in paused navigation-failed state.")
        return False

    if record_route_navigation_failure("startup_route_navigation_failed"):
        bot_state = STATE_STARTUP_NAVIGATION
        write_log(
            f"Startup navigation failed. Will retry in "
            f"{STARTUP_NAV_RETRY_SECONDS:.0f}s and ignore chest/boss decisions until it succeeds."
        )
    return False

def advance_route(do_navigation=False, reason="unknown"):
    """
    Move to the next route.

    If do_navigation=True, visually navigate to the new route's target level
    before entering freeze.
    """
    global current_route_index, route_start_time
    global bot_state, freeze_start_time
    global current_cycle_number

    previous_index = current_route_index
    previous_route = get_current_route()
    previous_cycle = current_cycle_number

    current_route_index = (current_route_index + 1) % len(ROUTE)
    clear_active_same_tier_substitute("advance_route")

    if current_route_index == 0 and previous_index == len(ROUTE) - 1:
        current_cycle_number += 1

    next_cycle = current_cycle_number
    route_start_time = time.time()

    reset_no_chest_trial_count("advance_route")
    reset_route_detection_memory()

    route = get_current_route()
    reset_route_navigation_retries("advance_route")
    reset_chapter_ambiguous_attempt_scope("advance_route")

    log_route_advance_marker(
        previous_index,
        previous_route,
        current_route_index,
        route,
        reason,
        previous_cycle=previous_cycle,
        next_cycle=next_cycle,
    )

    if next_cycle != previous_cycle:
        log_cycle_wrap_marker(previous_cycle)

    write_log(
        f"Advanced to {route['name']} | "
        f"{route['difficulty']} | {route['chapter']} | {route['level']}"
    )

    navigation_ok = True

    if do_navigation:
        time.sleep(1.0)
        navigation_ok = navigate_to_current_route_if_enabled()

        if not navigation_ok:
            if bot_state == STATE_NAVIGATION_FAILED:
                write_log("Route advance navigation ended in paused navigation-failed state.")
                return False

            if record_route_navigation_failure("route_advance_navigation_failed"):
                bot_state = STATE_STARTUP_NAVIGATION
                write_log(
                    "Route navigation failed after route advance. "
                    "Entering navigation retry state and ignoring detection decisions."
                )
            return False

    bot_state = STATE_FREEZE_AFTER_SWITCH
    freeze_start_time = time.time()
    reset_route_navigation_retries("advance_route_navigation_success")

    write_log("Entering freeze window.")
    return True

def reset_current_route_timer():
    global route_start_time

    route_start_time = time.time()
    route = get_current_route()

    write_log(
        f"Reset timer for {route['name']} | "
        f"{route['difficulty']} | {route['chapter']} | {route['level']}"
    )


def draw_route_overlay(debug_img, chest_state="none"):
    """
    Draw route/state info on the OpenCV preview.
    Route switching is now event-driven, so no stay_seconds timer is needed.
    """
    route = get_current_route()

    action_text = bot_state

    lines = [
        f"Bot state: {bot_state}",
        f"Boss seen this route: {boss_seen_this_route}",
        f"Blue drop handled: {blue_drop_handled_this_route}",
        f"Route: {current_route_index + 1}/{len(ROUTE)} - {route['name']}",
        f"Target: {route['difficulty']} | {route['chapter']} | {route['level']}",
        f"Chest state: {chest_state}",
        f"Next action: {action_text}",
        "Keys: N=next route, R=reset route memory, V=visual nav test, Q=quit",
    ]

    x = 25
    y = 125
    line_gap = 32

    for i, line in enumerate(lines):
        yy = y + i * line_gap

        cv2.putText(
            debug_img,
            line,
            (x, yy),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.75,
            (255, 255, 255),
            3,
            cv2.LINE_AA,
        )

        cv2.putText(
            debug_img,
            line,
            (x, yy),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.75,
            (0, 0, 0),
            1,
            cv2.LINE_AA,
        )

    return debug_img

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
        region_img = crop(img, REGIONS[region_name])

        if region_img is None:
            continue

        red_detected, red_pixels = detect_boss_warning_pixels(
            region_img,
            min_red_pixels=3000
        )

        warning_match = match_template(region_img, boss_warning_template)
        confidence = warning_match["confidence"]
        detected = red_detected and confidence >= BOSS_WARNING_CONFIDENCE_THRESHOLD

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
    global last_clear_debug_log_time

    best_confidence = 0.0
    best_region_name = None
    best_match_info = None

    for region_name in BATTLE_SEARCH_REGION_NAMES:
        region = REGIONS[region_name]
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
                "template_path": CLEAR_TEMPLATE_PATH,
            }

    clear_visible = best_confidence >= CLEAR_MATCH_THRESHOLD

    current_time = time.time()
    if (
        best_confidence >= 0.50
        and current_time - last_clear_debug_log_time >= 1.0
    ):
        last_clear_debug_log_time = current_time
        write_log(
            f"CLEAR match debug | "
            f"best_confidence={best_confidence:.2f} | "
            f"region={best_region_name} | "
            f"passed_threshold={clear_visible} | "
            f"threshold={CLEAR_MATCH_THRESHOLD:.2f}"
        )

    return clear_visible, best_confidence, best_match_info


def fast_boundary_level_search(hwnd, route, level_template, threshold):
    """
    Check map boundaries quickly instead of walking through many scroll chunks.
    """
    write_log(
        f"NAV fast boundary search start | route={route['level']} | "
        f"repeat={FAST_SCROLL_REPEAT} | pause={FAST_SCROLL_PAUSE:.2f}"
    )

    for direction in ("down", "up"):
        write_log(
            f"NAV fast scroll boundary | direction={direction} | "
            f"repeat={FAST_SCROLL_REPEAT}"
        )

        scroll_ok = fast_scroll_map_boundary(
            hwnd,
            direction,
            FAST_SCROLL_REPEAT,
            route=route,
        )

        if not scroll_ok:
            write_log(f"NAV fast boundary search aborted during scroll {direction}.")
            return False

        if FAST_SCROLL_PAUSE > 0:
            time.sleep(FAST_SCROLL_PAUSE)

        current_result = try_current_visible_level(
            hwnd,
            route,
            level_template,
            threshold,
            context=f"fast_boundary_{direction}"
        )

        if current_result is not None:
            return current_result

    write_log(
        f"NAV fast boundary search failed | route={route['level']} | "
        f"repeat={FAST_SCROLL_REPEAT}"
    )
    return None


def slow_chunked_level_search(hwnd, route, level_template, threshold, search_order):
    write_log(
        f"NAV slow chunked search start | route={route['level']} | "
        f"search_order={search_order} | chunks_per_direction={MAP_SCROLL_CHUNKS_PER_DIRECTION}"
    )

    for direction in search_order:
        for chunk_index in range(MAP_SCROLL_CHUNKS_PER_DIRECTION):
            scroll_ok = scroll_map(
                hwnd,
                direction,
                repeat=MAP_SCROLL_CHUNK_REPEAT,
                route=route,
            )

            if not scroll_ok:
                write_log(f"NAV aborted during scroll {direction}.")
                return False

            current_result = try_current_visible_level(
                hwnd,
                route,
                level_template,
                threshold,
                context=f"{direction}_{chunk_index + 1}/{MAP_SCROLL_CHUNKS_PER_DIRECTION}"
            )

            if current_result is None:
                continue

            return current_result

    write_log(
        f"NAV slow chunked search failed | route={route['level']} | "
        f"search_order={search_order} | "
        f"chunks_per_direction={MAP_SCROLL_CHUNKS_PER_DIRECTION}"
    )
    return None


def find_and_click_level_by_template(hwnd, route):
    """
    Search for the target level using route-specific scroll order.

    It scrolls in chunks, detects the level text template, validates position,
    then finds/clicks the white dot to the left of the detected text.
    """
    level_template = load_template(route["level_template"])

    if level_template is None:
        write_log(f"NAV FAILED: could not load level template for {route['level']}")
        return False

    threshold = max(
        LEVEL_STRONG_ACCEPT_THRESHOLD,
        route.get("level_match_threshold", LEVEL_MATCH_THRESHOLD)
    )
    search_order = route.get("search_order", ["up", "down"])

    current_result = try_current_visible_level(
        hwnd,
        route,
        level_template,
        threshold,
        context="before_scroll"
    )

    if current_result is not None:
        return current_result

    if USE_FAST_BOUNDARY_SCROLL:
        search_result = fast_boundary_level_search(
            hwnd,
            route,
            level_template,
            threshold
        )
    else:
        search_result = slow_chunked_level_search(
            hwnd,
            route,
            level_template,
            threshold,
            search_order
        )

    if search_result is not None:
        return search_result

    write_log(
        f"NAV full scroll search failed | route={route['level']} | "
        f"mode={'fast_boundary' if USE_FAST_BOUNDARY_SCROLL else 'slow_chunked'} | "
        f"search_order={search_order}"
    )
    write_log(
        f"NAV FAILED: could not find level {route['level']} | "
        f"search_order={search_order}"
    )

    return False

def load_farm_plan(default_route):
    base_dir = get_base_dir()
    plan_path = get_farm_plan_path()
    config_path = get_config_path()
    runtime_mode = get_runtime_mode()

    write_log(
        "Runtime paths | "
        f"mode={runtime_mode} | "
        f"base_dir={base_dir} | "
        f"config_path={config_path} | "
        f"farm_plan_path={plan_path}"
    )

    if not plan_path.exists():
        write_log(
            f"farm_plan.json not found at resolved path: {plan_path}. "
            "Using default ROUTE fallback."
        )
        return default_route

    try:
        with plan_path.open("r", encoding="utf-8") as f:
            plan = json.load(f)

        if not plan:
            write_log(
                f"farm_plan.json is empty at resolved path: {plan_path}. "
                "Using default ROUTE fallback."
            )
            return default_route

        write_log(f"farm_plan.json loaded successfully from {plan_path}: {len(plan)} routes.")
        return plan

    except Exception as e:
        write_log(f"Failed to load farm_plan.json from {plan_path}: {e}")
        write_log("Using default ROUTE fallback.")
        return default_route

log_app_start_boundary()
log_console_encoding_status()
log_recognition_profile_startup()
ROUTE = load_farm_plan(ROUTE)
log_chest_tier_breakpoint_validation()
log_startup_template_check()

def main():
    global last_boss_log_time
    global last_manual_nav_time
    global bot_state
    global freeze_start_time
    get_config()
    last_boss_log_time = 0
    input_mode = "background PostMessage" if USE_BACKGROUND_INPUT else "foreground mouse"
    log_session_start_marker(input_mode)
    log_cycle_start_marker()
    hwnd, title = find_window_by_title_keyword(WINDOW_KEYWORD)
    global GAME_HWND
    GAME_HWND = hwnd
    if hwnd is None:
        safe_print(f"Could not find a window containing: {WINDOW_KEYWORD}")
        safe_print("Make sure TaskBarHero is open.")
        return

    safe_print(f"Found window: {title}")
    safe_print(f"Input mode: {input_mode}")
    safe_print(f"Preview window: {'on' if SHOW_PREVIEW else 'off'}")
    safe_print(f"Beep: {'on' if ENABLE_BEEP else 'off'}")
    safe_print(f"Navigate on start: {'on' if NAVIGATE_ON_START else 'off'}")
    safe_print(
        "Config-backed thresholds: "
        f"recognition_mode={RECOGNITION_MODE}, "
        f"chest_match={MATCH_THRESHOLD}, "
        f"chapter_tab_candidate={CHAPTER_TAB_CANDIDATE_THRESHOLD}, "
        f"chapter_match={CHAPTER_MATCH_THRESHOLD}, "
        f"difficulty={DIFFICULTY_MATCH_THRESHOLD}, "
        f"level_strong={LEVEL_STRONG_ACCEPT_THRESHOLD}, "
        f"boss_warning={BOSS_WARNING_CONFIDENCE_THRESHOLD}, "
        f"clear_match={CLEAR_MATCH_THRESHOLD}"
    )
    log_ui_coordinate_diagnostics(hwnd, title)

    safe_print("Loading templates...")

    # Your actual template file names:
    blue_template = load_template("templates/general/chest_blue.png")
    brown_template = load_template("templates/general/chest_brown.png")
    boss_warning_template = load_template("templates/general/boss_warning_text.png")
    clear_template = load_template(CLEAR_TEMPLATE_PATH)
    safe_print("Templates loaded.")
    write_log(f"CLEAR template loaded | path={CLEAR_TEMPLATE_PATH}")
    safe_print()
    safe_print("Controls:")
    safe_print("  Move mouse over preview = show coordinate")
    safe_print("  Left click / Right click = print coordinate")
    safe_print("  S = save full screenshot")
    safe_print("  C = save full screenshot + all region crops")
    safe_print("  Q = quit")
    safe_print("  N = next route")
    safe_print("  R = reset route timer")
    safe_print("  V = visual nav test current route")
    safe_print()
    safe_print(f"Template match threshold: {MATCH_THRESHOLD}")
    safe_print()

    if SHOW_PREVIEW:
        cv2.namedWindow("TaskBarHero Capture", cv2.WINDOW_NORMAL)
        cv2.setMouseCallback("TaskBarHero Capture", mouse_callback)

    startup_navigation_done = not NAVIGATE_ON_START
    last_startup_nav_attempt_time = 0

    if NAVIGATE_ON_START:
        write_log(
            "Startup navigation armed. "
            "The bot will enter the first planned route before detection starts."
        )

    while True:
        current_time = time.time()

        if (
            bot_state != STATE_NAVIGATION_FAILED
            and
            not startup_navigation_done
            and current_time - last_startup_nav_attempt_time >= STARTUP_NAV_RETRY_SECONDS
        ):
            last_startup_nav_attempt_time = current_time
            startup_navigation_done = navigate_to_startup_route()
            last_startup_nav_attempt_time = time.time()
            current_time = last_startup_nav_attempt_time

        if (
            startup_navigation_done
            and bot_state == STATE_STARTUP_NAVIGATION
            and current_time - last_startup_nav_attempt_time >= STARTUP_NAV_RETRY_SECONDS
        ):
            last_startup_nav_attempt_time = current_time
            write_log("Retrying pending route navigation. Detection remains paused.")

            if navigate_to_current_route_if_enabled():
                reset_route_detection_memory()
                bot_state = STATE_FREEZE_AFTER_SWITCH
                freeze_start_time = time.time()
                write_log("Pending route navigation completed. Entering freeze window.")
            else:
                if bot_state == STATE_NAVIGATION_FAILED:
                    write_log("Pending route navigation ended in paused navigation-failed state.")
                elif record_route_navigation_failure("pending_route_navigation_failed"):
                    bot_state = STATE_STARTUP_NAVIGATION

            last_startup_nav_attempt_time = time.time()
            current_time = last_startup_nav_attempt_time

        img = capture_window(hwnd)

        detections = detect_all_chests(img, blue_template, brown_template)

        boss_visible, boss_region, boss_pixels, boss_conf = detect_boss_warning(
            img,
            boss_warning_template
        )
        clear_visible, clear_conf, _clear_match_info = detect_clear_screen(img, clear_template)

        if (
            startup_navigation_done
            and bot_state not in {STATE_STARTUP_NAVIGATION, STATE_NAVIGATION_FAILED}
        ):
            chest_state = handle_chest_events(detections)

            bot_info = handle_bot_state(
                img,
                detections,
                boss_visible,
                boss_region,
                boss_pixels,
                boss_conf,
                clear_visible,
                clear_conf
            )
        else:
            chest_state = bot_state
            bot_info = {
                "state": bot_state,
                "boss_visible": False,
                "blue_chest_visible": False,
                "blue_log_visible": False,
                "message": (
                    "Navigation failed; bot paused"
                    if bot_state == STATE_NAVIGATION_FAILED
                    else "Waiting for route navigation"
                )
            }

        maybe_log_heartbeat(current_time, bot_info)
        print_bot_status_on_change(bot_info)
        # print(
        #     f"Bot state: {bot_info['state']} | "
        #     f"Boss: {bot_info['boss_visible']} | "
        #     f"Blue chest: {bot_info['blue_chest_visible']} | "
        #     f"Blue log: {bot_info['blue_log_visible']} | "
        #     f"{bot_info['message']}".ljust(180),
        #     end="\r"
        # )
        # if boss_visible and current_time - last_boss_log_time >= BOSS_LOG_COOLDOWN_SECONDS:
        #     last_boss_log_time = current_time

        #     print(
        #         f"\nBoss warning detected | "
        #         f"region={boss_region} | "
        #         f"red_pixels={boss_pixels} | "
        #         f"confidence={boss_conf:.2f}"
        #     )
        #print_route_status(chest_state)
        #print_detection_summary(detections)

        debug_img = draw_regions(img)
        debug_img = draw_detections(debug_img, detections)
        debug_img = draw_route_overlay(debug_img, chest_state)

        if SHOW_PREVIEW:
            cv2.imshow("TaskBarHero Capture", debug_img)
            key = cv2.waitKey(100) & 0xFF
        else:
            key = 255
            time.sleep(0.1)

        if key == ord("s"):
            maybe_save_debug_screenshot(
                img,
                folder="debug_screenshots/full",
                prefix="full"
            )
    
        elif key == ord("c"):
            save_all_regions(img)

        elif key == ord("q"):
            break
        elif key == ord("n"):
            advance_route(do_navigation=False, reason="manual_next")
            write_log("Manual route advance triggered.")
        elif key == ord("r"):
            reset_no_chest_trial_count("manual_route_reset")
            reset_route_detection_memory()
            write_log("Manual reset route detection memory.")
        elif key == ord("v"):
            if current_time - last_manual_nav_time >= MANUAL_NAV_COOLDOWN_SECONDS:
                last_manual_nav_time = current_time
                route = get_current_route()
                write_log(
                    f"Manual FULL nav test for {route['name']} | "
                    f"{route['difficulty']} | {route['chapter']} | {route['level']}"
                )
                if navigate_to_current_route_if_enabled(activate_boss_gate=True):
                    startup_navigation_done = True

    if SHOW_PREVIEW:
        cv2.destroyAllWindows()


def run_main_with_fatal_logging():
    try:
        main()
    except Exception:
        write_log(
            "FATAL EXCEPTION in bot entry path\n"
            f"{traceback.format_exc()}"
        )
        raise


if __name__ == "__main__":
    run_main_with_fatal_logging()
