# MAA Task Bar Hero
# Concept and direction by Marcus Xu.
# Built with Codex as a coding assistant.
# Shared for learning, experimentation, and automation research.

import time
import winsound
import cv2
from vision import (
    find_window_by_title_keyword,
    capture_window,
    save_debug_screenshot,
    configure_visual_detection,
    configure_navigation_visual_observation,
    get_last_window_lookup_error,
    check_template_loadable,
    load_template,
    match_template,
    save_visual_debug_artifacts,
    clamp_region,
    crop,
    regions_equal,
    expand_region_for_retry,
    get_expanded_roi_retry_reason,
    expanded_roi_retry_enabled,
    log_expanded_roi_retry_start,
    log_expanded_roi_retry_result,
    detect_all_chests,
    draw_regions,
    draw_detections,
    save_all_regions,
    print_detection_summary,
    detect_blue_log,
    find_template_in_region,
    find_template_in_box,
    find_template_candidates_in_box,
    detect_current_stash_page,
    check_stash_grid_space,
    check_stash_last_slot_blank,
    detect_boss_warning,
    detect_clear_screen,
    collect_detection_snapshot,
    detect_level_in_map,
    find_level_dot_left_of_text,
    check_selected_level_green_text,
    verify_current_level_selected_by_green_text,
    level_match_passes_expected_y,
    find_best_difficulty_anchor,
    chapter_order_index,
    unique_points_by_x,
    build_chapter_geometry,
    point_inside_region,
    classify_chapter_by_geometry,
    apply_chapter_geometry_identity,
    collect_chapter_tab_candidates,
    summarize_chapter_candidates,
    find_current_chapter,
    find_chapter_tab_candidate,
    empty_route_target_observation,
    observe_route_target_state_from_image,
    route_target_identity_matches,
    route_invariant_selected_evidence_passes,
    route_target_invariant_passes,
    route_target_invariant_confidence_is_strong,
)
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
import win32gui
import json
import os
import sys
import traceback
import ctypes
import win32con
import win32api
from actions import InputController
from logger import safe_print, sanitize_text_for_output, timestamp
from state import (
    BotRuntimeState,
    FREEZE_SECONDS_AFTER_SWITCH,
    ORPHAN_BLUE_RECOVERY_SECONDS,
    POST_BOSS_DROP_WINDOW_SECONDS,
    RECOVERY_REWARD_HANDLED,
    STATE_FREEZE_AFTER_SWITCH,
    STATE_LOOK_FOR_BLUE_DROP,
    STATE_LOOK_FOR_BOSS,
    STATE_NAVIGATION_FAILED,
    STATE_STARTUP_NAVIGATION,
    blue_signal_recent,
    chapter_number_from_key,
    get_no_chest_policy,
    route_identity,
    route_target_label,
    same_tier_priority_sort_key,
    same_tier_route_copy,
)
from config import (
    APP_VERSION,
    CONFIG_FILE_NAME,
    emit_config_load_messages,
    get_base_dir,
    get_config,
    get_effective_thresholds,
    get_recognition_mode,
    get_threshold,
)


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


def maybe_save_debug_screenshot(img, folder, prefix):
    if not SAVE_DEBUG_SCREENSHOTS:
        return None

    return save_debug_screenshot(img, folder=folder, prefix=prefix)


def get_debug_dir():
    return get_base_dir() / "debug"


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
bot_state = STATE_LOOK_FOR_BOSS
freeze_start_time = time.time()
state_memory = BotRuntimeState()

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
REPEAT_SAME_LEVEL_AFTER_BLUE_CHEST = env_flag(
    "MAATBH_REPEAT_SAME_LEVEL_AFTER_BLUE_CHEST",
    config_bool("repeat_same_level_after_blue_chest", False),
)
OPEN_ALL_BOXES_ON_SAME_LEVEL = config_bool("open_all_boxes_on_same_level", True)
NON_BLUE_BOX_CLICK_COOLDOWN_SECONDS = config_non_negative_float(
    "non_blue_box_click_cooldown_seconds",
    1.0,
)
RECOVER_ORPHAN_BLUE_CHEST_BEFORE_BOSS = config_bool(
    "recover_orphan_blue_chest_before_boss",
    True,
)
ORPHAN_BLUE_CHEST_CONFIRM_CYCLES = config_positive_int(
    "orphan_blue_chest_confirm_cycles",
    2,
)
ORPHAN_BLUE_CHEST_NEAR_THRESHOLD_MARGIN = config_non_negative_float(
    "orphan_blue_chest_near_threshold_margin",
    0.03,
)
MOVE_BACKPACK_TO_STORAGE_AFTER_NON_BLUE_BOX = env_flag(
    "MAATBH_MOVE_TO_STORAGE_AFTER_NON_BLUE_BOX",
    config_bool("move_backpack_to_storage_after_non_blue_box", True),
)
AUTO_SWITCH_STASH_WHEN_FULL = config_bool("auto_switch_stash_when_full", True)
MAX_STASH_PAGES_TO_SCAN = config_positive_int("max_stash_pages_to_scan", 4)
STASH_TAB_MATCH_THRESHOLD = config_non_negative_float("stash_tab_match_threshold", 0.80)
STORAGE_ANCHOR_MATCH_THRESHOLD = config_non_negative_float("storage_anchor_match_threshold", 0.80)
STASH_LAST_SLOT_BLANK_THRESHOLD = config_non_negative_float("stash_last_slot_blank_threshold", 0.85)
STASH_LAST_SLOT_UNCERTAIN_MARGIN = config_non_negative_float("stash_last_slot_uncertain_margin", 0.05)
STASH_SWITCH_WAIT_SECONDS = config_non_negative_float("stash_switch_wait_seconds", 0.6)
STORAGE_ANCHOR_TEMPLATE = get_config().get("storage_anchor_template", "templates/general/anchor_storage.png")
STASH_SORT_TEMPLATE = get_config().get("stash_sort_template", "templates/general/stash_sort.png")
SORT_STASH_BEFORE_FULL_CHECK = config_bool("sort_stash_before_full_check", True)
POST_STASH_SORT_WAIT_SECONDS = config_non_negative_float("post_stash_sort_wait_seconds", 0.4)
STASH_BLANK_TEMPLATE = get_config().get("stash_blank_template", "templates/general/blank.png")
STASH_TAB_TEMPLATES = get_config().get("stash_tab_templates", {
    "stash_1": "templates/general/stash_1.png",
    "stash_2": "templates/general/stash_2.png",
    "stash_3": "templates/general/stash_3.png",
    "stash_4": "templates/general/stash_4.png",
})
STORAGE_STASH_SEARCH_REGION = get_config().get("storage_stash_search_region", "hero_panel")
STASH_LAST_SLOT_ANCHOR_OFFSET_X = config_int("stash_last_slot_anchor_offset_x", -9)
STASH_LAST_SLOT_ANCHOR_OFFSET_Y = config_int("stash_last_slot_anchor_offset_y", -55)
STASH_LAST_SLOT_WIDTH = config_positive_int("stash_last_slot_width", 38)
STASH_LAST_SLOT_HEIGHT = config_positive_int("stash_last_slot_height", 38)
STORAGE_GRID_ANCHOR_OFFSET_X = config_int("storage_grid_anchor_offset_x", -249)
STORAGE_GRID_ANCHOR_OFFSET_Y = config_int("storage_grid_anchor_offset_y", -295)
STORAGE_GRID_SLOT_WIDTH = config_positive_int("storage_grid_slot_width", 38)
STORAGE_GRID_SLOT_HEIGHT = config_positive_int("storage_grid_slot_height", 38)
STORAGE_GRID_SLOT_GAP_X = config_non_negative_int("storage_grid_slot_gap_x", 2)
STORAGE_GRID_SLOT_GAP_Y = config_non_negative_int("storage_grid_slot_gap_y", 2)
STORAGE_GRID_ROWS = config_positive_int("storage_grid_rows", 7)
STORAGE_GRID_COLS = config_positive_int("storage_grid_cols", 7)
ALWAYS_SAVE_STORAGE_DIAGNOSTICS_ON_FAILURE = config_bool(
    "always_save_storage_diagnostics_on_failure",
    True,
)
STASH_PAGE_ORDER = ("stash_1", "stash_2", "stash_3", "stash_4")
BLUE_ALERT_COOLDOWN_SECONDS = 10
BROWN_LOG_COOLDOWN_SECONDS = 10
NO_CHEST_RESET_SECONDS = 2
last_boss_log_time = 0
BOSS_LOG_COOLDOWN_SECONDS = 5
last_manual_nav_time = 0

chapter_ambiguous_click_attempts = {}
chapter_ambiguous_attempt_scope_id = 0
chapter_geometry_click_attempts = {}
CHAPTER_ORDER = ["chapter_1", "chapter_2", "chapter_3"]
skipped_routes_this_session = []
coordinate_scaling_status = None
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
last_non_blue_box_click_time = 0
last_seen_chest_time = 0
last_state = "none"
current_route_index = 0
route_start_time = time.time()
current_cycle_number = 1

last_route_status_print_time = 0
ROUTE_STATUS_PRINT_INTERVAL = 1.0
GAME_HWND = None
last_frame_signature = None
last_frame_change_time = time.time()
last_frame_stale_warning_time = 0

last_blue_reward_signature = None
last_blue_reward_handled_time = 0
startup_runtime_initialized = False
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
    return timestamp()


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


configure_visual_detection(
    regions=REGIONS,
    battle_search_region_names=BATTLE_SEARCH_REGION_NAMES,
    preview_region_names=PREVIEW_REGION_NAMES,
    region_colors=REGION_COLORS,
    detection_colors=DETECTION_COLORS,
    match_threshold=MATCH_THRESHOLD,
    boss_warning_confidence_threshold=BOSS_WARNING_CONFIDENCE_THRESHOLD,
    clear_match_threshold=CLEAR_MATCH_THRESHOLD,
    clear_template_path=CLEAR_TEMPLATE_PATH,
    use_expanded_roi_retry=USE_EXPANDED_ROI_RETRY,
    expanded_roi_margin_px=EXPANDED_ROI_MARGIN_PX,
    expanded_roi_scale_factor=EXPANDED_ROI_SCALE_FACTOR,
    expanded_roi_only_on_ui_warning=EXPANDED_ROI_ONLY_ON_UI_WARNING,
    recognition_mode=RECOGNITION_MODE,
    get_ui_retry_state=lambda: (
        ui_diagnostics_suggests_roi_retry,
        ui_diagnostics_health_status,
    ),
    get_mouse_position=lambda: (mouse_x, mouse_y),
    write_log=write_log,
    safe_print=safe_print,
    save_debug_screenshot_callback=maybe_save_debug_screenshot,
    get_debug_dir=get_debug_dir,
)

configure_navigation_visual_observation(
    difficulty_templates=DIFFICULTY_TEMPLATES,
    chapter_templates=CHAPTER_TEMPLATES,
    chapter_order=CHAPTER_ORDER,
    level_match_threshold=LEVEL_MATCH_THRESHOLD,
    level_strong_accept_threshold=LEVEL_STRONG_ACCEPT_THRESHOLD,
    level_dot_green_template=LEVEL_DOT_GREEN_TEMPLATE,
    level_dot_green_match_threshold=LEVEL_DOT_GREEN_MATCH_THRESHOLD,
    level_dot_max_vertical_distance=LEVEL_DOT_MAX_VERTICAL_DISTANCE,
    difficulty_match_threshold=DIFFICULTY_MATCH_THRESHOLD,
    chapter_match_threshold=CHAPTER_MATCH_THRESHOLD,
    chapter_tab_candidate_threshold=CHAPTER_TAB_CANDIDATE_THRESHOLD,
    chapter_tab_cluster_x_tolerance=CHAPTER_TAB_CLUSTER_X_TOLERANCE,
    chapter_tab_cluster_y_tolerance=CHAPTER_TAB_CLUSTER_Y_TOLERANCE,
    chapter_candidate_ambiguity_margin=CHAPTER_CANDIDATE_AMBIGUITY_MARGIN,
    chapter_ambiguous_min_confidence=CHAPTER_AMBIGUOUS_MIN_CONFIDENCE,
    chapter_geometry_fallback_enabled=CHAPTER_GEOMETRY_FALLBACK_ENABLED,
    chapter_geometry_min_confidence=CHAPTER_GEOMETRY_MIN_CONFIDENCE,
    chapter_geometry_require_dynamic_anchor=CHAPTER_GEOMETRY_REQUIRE_DYNAMIC_ANCHOR,
    chapter_geometry_tolerance_px=CHAPTER_GEOMETRY_TOLERANCE_PX,
    selected_level_green_pixel_min=SELECTED_LEVEL_GREEN_PIXEL_MIN,
    selected_level_green_ratio_min=SELECTED_LEVEL_GREEN_RATIO_MIN,
    selected_level_green_hsv_lower=SELECTED_LEVEL_GREEN_HSV_LOWER,
    selected_level_green_hsv_upper=SELECTED_LEVEL_GREEN_HSV_UPPER,
    level_y_position_tolerance_px=LEVEL_Y_POSITION_TOLERANCE_PX,
    route_invariant_allow_selected_evidence=ROUTE_INVARIANT_ALLOW_SELECTED_EVIDENCE,
    route_invariant_level_confidence_floor=ROUTE_INVARIANT_LEVEL_CONFIDENCE_FLOOR,
    route_invariant_green_dot_min_confidence=ROUTE_INVARIANT_GREEN_DOT_MIN_CONFIDENCE,
    route_invariant_require_level_y_ok=ROUTE_INVARIANT_REQUIRE_LEVEL_Y_OK,
)


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
        screen_size = get_screen_size()
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
        f"version={APP_VERSION}\n"
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
        f"repeat_same_level_after_blue_chest={REPEAT_SAME_LEVEL_AFTER_BLUE_CHEST} | "
        f"open_all_boxes_on_same_level={OPEN_ALL_BOXES_ON_SAME_LEVEL} | "
        f"non_blue_box_click_cooldown={NON_BLUE_BOX_CLICK_COOLDOWN_SECONDS:.2f}s | "
        f"recover_orphan_blue_chest_before_boss={RECOVER_ORPHAN_BLUE_CHEST_BEFORE_BOSS} | "
        f"orphan_blue_chest_confirm_cycles={ORPHAN_BLUE_CHEST_CONFIRM_CYCLES} | "
        f"orphan_blue_chest_near_threshold_margin={ORPHAN_BLUE_CHEST_NEAR_THRESHOLD_MARGIN:.2f} | "
        f"move_backpack_to_storage_after_non_blue_box={MOVE_BACKPACK_TO_STORAGE_AFTER_NON_BLUE_BOX} | "
        f"auto_switch_stash_when_full={AUTO_SWITCH_STASH_WHEN_FULL} | "
        f"max_stash_pages_to_scan={MAX_STASH_PAGES_TO_SCAN} | "
        f"stash_last_slot_blank_threshold={STASH_LAST_SLOT_BLANK_THRESHOLD:.2f} | "
        f"sort_stash_before_full_check={SORT_STASH_BEFORE_FULL_CHECK} | "
        f"post_stash_sort_wait={POST_STASH_SORT_WAIT_SECONDS:.2f}s | "
        f"storage_grid=offset({STORAGE_GRID_ANCHOR_OFFSET_X},{STORAGE_GRID_ANCHOR_OFFSET_Y}) "
        f"slot({STORAGE_GRID_SLOT_WIDTH}x{STORAGE_GRID_SLOT_HEIGHT}) "
        f"gap({STORAGE_GRID_SLOT_GAP_X},{STORAGE_GRID_SLOT_GAP_Y}) "
        f"rows={STORAGE_GRID_ROWS} cols={STORAGE_GRID_COLS} | "
        f"always_save_storage_diagnostics_on_failure={ALWAYS_SAVE_STORAGE_DIAGNOSTICS_ON_FAILURE} | "
        "post-click level verification remains enabled | "
        "blue reward route-advance logic unchanged"
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
    add_template_spec(specs, seen_paths, "general:storage_anchor", STORAGE_ANCHOR_TEMPLATE)
    add_template_spec(specs, seen_paths, "general:stash_sort", STASH_SORT_TEMPLATE)
    add_template_spec(specs, seen_paths, "general:stash_blank_slot", STASH_BLANK_TEMPLATE)

    if isinstance(STASH_TAB_TEMPLATES, dict):
        for stash_name, path in STASH_TAB_TEMPLATES.items():
            add_template_spec(specs, seen_paths, f"general:{stash_name}", path)

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
        f"reason={reason} | count={state_memory.no_chest_trial_count}/{total_clears}\n"
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
        f"Brown chest detected | "
        f"confidence={detection['confidence']:.2f} | "
        f"location={detection['center_full']} | "
        f"region={detection['region_name']}"
    )

    write_log(msg)


def get_non_blue_box_open_guard_reason(clear_visible=False):
    if not OPEN_ALL_BOXES_ON_SAME_LEVEL:
        return "disabled_by_config"

    if GAME_HWND is None:
        return "game_window_unavailable"

    if bot_state not in {STATE_LOOK_FOR_BOSS, STATE_LOOK_FOR_BLUE_DROP}:
        return f"state_not_same_level_observation:{bot_state}"

    if clear_visible:
        return "clear_screen_visible"

    if state_memory.blue_drop_handled_this_route:
        return "blue_drop_already_handled"

    if state_memory.post_clear_wait_started_at > 0:
        return "post_clear_reward_wait_active"

    if state_memory.reward_navigation_interruption is not None:
        return "reward_navigation_interruption_active"

    return None


def click_non_blue_box_once(hwnd, detections):
    non_blue_detections = [d for d in detections if d.get("type") != "blue"]

    if not non_blue_detections:
        write_log("NON-BLUE BOX CLICK SKIPPED: no non-blue box detection available.")
        return False

    best_box = max(non_blue_detections, key=lambda d: d["confidence"])
    box_type = best_box.get("type", "non_blue")
    center_x, center_y = best_box["center_full"]
    box_w, box_h = best_box["size"]
    box_left = center_x - box_w // 2
    box_right = center_x + box_w // 2
    box_top = center_y - box_h // 2
    box_bottom = center_y + box_h // 2
    local_x = int(center_x)
    local_y = int(center_y)

    write_log(
        f"Opening same-level non-blue box | "
        f"type={box_type} | confidence={best_box['confidence']:.2f} | "
        f"center=({local_x}, {local_y}) | "
        f"box=({box_left},{box_top})-({box_right},{box_bottom}) | "
        f"region={best_box.get('region_name')}"
    )

    click_ok = click_window_point(
        hwnd,
        local_x,
        local_y,
        label=f"same_level_{box_type}_box",
    )

    if not click_ok:
        write_log(
            f"NON-BLUE BOX CLICK FAILED safely | "
            f"type={box_type} | center=({local_x}, {local_y})"
        )
        return False

    time.sleep(0.25)
    write_log(
        f"Same-level non-blue box click completed; staying on current route | "
        f"type={box_type} | center=({local_x}, {local_y})"
    )
    return True


def maybe_open_non_blue_boxes_same_level(detections, clear_visible=False):
    global last_non_blue_box_click_time

    if not detections:
        return False

    blue_candidate = classify_best_blue_chest_candidate(detections)

    if blue_candidate["visible"] and blue_candidate["blocks_non_blue"]:
        reason = (
            "accepted_blue_chest_priority"
            if blue_candidate["status"] == "accepted"
            else "recoverable_orphan_blue_chest_priority"
        )
        write_log(
            f"Same-level non-blue box open skipped | reason={reason} | "
            f"blue_status={blue_candidate['status']} | "
            f"blue_confidence={blue_candidate['confidence']:.2f} | "
            f"accept_threshold={blue_candidate['accept_threshold']:.2f} | "
            f"near_threshold={blue_candidate['near_threshold']:.2f} | "
            f"orphan_recovery_tracking={blue_candidate['orphan_recovery_tracking']}"
        )
        return False

    if blue_candidate["visible"]:
        write_log(
            f"Same-level non-blue box allowed despite weak blue candidate | "
            f"blue_status={blue_candidate['status']} | "
            f"blue_confidence={blue_candidate['confidence']:.2f} | "
            f"accept_threshold={blue_candidate['accept_threshold']:.2f} | "
            f"near_threshold={blue_candidate['near_threshold']:.2f}"
        )

    non_blue_detections = [d for d in detections if d.get("type") != "blue"]

    if not non_blue_detections:
        return False

    guard_reason = get_non_blue_box_open_guard_reason(clear_visible=clear_visible)

    if guard_reason is not None:
        write_log(
            f"Same-level non-blue box open skipped | "
            f"reason={guard_reason} | detections={len(non_blue_detections)}"
        )
        return False

    current_time = time.time()
    elapsed = current_time - last_non_blue_box_click_time

    if elapsed < NON_BLUE_BOX_CLICK_COOLDOWN_SECONDS:
        return False

    click_success = click_non_blue_box_once(GAME_HWND, non_blue_detections)
    last_non_blue_box_click_time = current_time

    if click_success:
        write_log(
            "Non-blue box opened during same-level flow; evaluating storage transfer policy."
        )
        try_move_backpack_to_storage_after_non_blue_box()
        write_log("Returning to same-level observation after non-blue box handling.")

    return click_success


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


def get_no_chest_policy_for_current_route():
    route = get_current_route()
    return get_no_chest_policy(
        route,
        DEFAULT_NO_CHEST_RETRIES,
        DEFAULT_MAX_TRIALS_IF_NO_CHEST,
    )


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
    state_memory.reset_no_chest_trial_count(reason, write_log=write_log)


def reset_route_detection_memory():
    state_memory.reset_route_detection_memory()


def get_blue_chest_accept_threshold():
    return EFFECTIVE_RECOGNITION_THRESHOLDS.get(
        "blue_chest_accept",
        MATCH_THRESHOLD,
    ) or MATCH_THRESHOLD


def classify_blue_chest_candidate(confidence):
    accept_threshold = get_blue_chest_accept_threshold()
    near_threshold = max(
        0.0,
        accept_threshold - ORPHAN_BLUE_CHEST_NEAR_THRESHOLD_MARGIN,
    )

    if confidence >= accept_threshold:
        status = "accepted"
    elif confidence >= near_threshold:
        status = "near_threshold"
    else:
        status = "weak"

    return {
        "status": status,
        "confidence": confidence,
        "accept_threshold": accept_threshold,
        "near_threshold": near_threshold,
        "margin": ORPHAN_BLUE_CHEST_NEAR_THRESHOLD_MARGIN,
    }


def orphan_blue_recovery_can_track():
    return (
        RECOVER_ORPHAN_BLUE_CHEST_BEFORE_BOSS
        and bot_state == STATE_LOOK_FOR_BOSS
        and not state_memory.blue_drop_handled_this_route
        and state_memory.post_clear_wait_started_at == 0
        and state_memory.reward_navigation_interruption is None
    )


def classify_best_blue_chest_candidate(detections):
    blue_confidence = max(
        (d.get("confidence", 0.0) for d in detections if d.get("type") == "blue"),
        default=0.0,
    )
    classification = classify_blue_chest_candidate(blue_confidence)
    classification["visible"] = blue_confidence > 0.0
    classification["orphan_recovery_tracking"] = (
        classification["status"] == "near_threshold"
        and orphan_blue_recovery_can_track()
    )
    classification["blocks_non_blue"] = (
        classification["status"] == "accepted"
        or classification["orphan_recovery_tracking"]
    )
    return classification


def handle_confirmed_blue_drop(detections, reason, details, allow_pre_boss=False):
    """
    Shared action once a blue drop is confirmed by normal or recovery logic.
    """
    global bot_state

    if not state_memory.boss_seen_this_route and not allow_pre_boss:
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

    if not state_memory.boss_seen_this_route and allow_pre_boss:
        write_log(
            "Boss warning not detected, but confirmed blue reward appeared; "
            f"treating as missed boss-warning reward | "
            f"reason={reason} | {details}"
        )
        write_log("Confirmed orphan reward; opening before route advance.")
    elif state_memory.boss_seen_this_route:
        write_log(
            f"Confirmed post-boss blue reward; opening before route advance | "
            f"reason={reason} | {details}"
        )

    if state_memory.post_clear_wait_started_at > 0:
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

        state_memory.blue_drop_handled_this_route = True
        write_log("Blue chest click completed.")
        try_move_backpack_to_storage_after_blue_chest()
    else:
        state_memory.blue_drop_handled_this_route = True
        write_log("DRY RUN: would click blue chest once.")

    if STOP_IF_BLUE_CHEST_FOUND:
        reset_no_chest_trial_count("confirmed_blue_drop")

    if REPEAT_SAME_LEVEL_AFTER_BLUE_CHEST:
        write_log(
            "Blue chest completed and repeat_same_level_after_blue_chest is enabled. "
            "Route advancement skipped; same route/level will be repeated."
        )
        repeat_current_route_after_blue_chest()
        return {
            "state": bot_state,
            "boss_visible": False,
            "blue_chest_visible": False,
            "blue_log_visible": False,
            "message": "Repeated same route after blue chest"
        }

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
        f"no_chest_clears={state_memory.no_chest_trial_count}/{get_max_trials_for_current_route()}"
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
        f"{route['level']} | no_chest_clears={state_memory.no_chest_trial_count}/{get_max_trials_for_current_route()}"
    )
    write_log("No route navigation will be performed for this retry.")
    write_log("Detector cycle reset. Entering freeze window before looking for boss warning.")


def handle_clear_no_chest_trial(clear_conf):
    """
    Handle CLEAR as a fallback signal that the level ended without blue chest.
    """

    if state_memory.clear_handled_this_trial:
        return {
            "state": bot_state,
            "boss_visible": False,
            "blue_chest_visible": False,
            "blue_log_visible": False,
            "message": "CLEAR already handled for this trial"
        }

    state_memory.clear_handled_this_trial = True
    state_memory.no_chest_trial_count += 1

    no_chest_retries, max_trials, policy_source = get_no_chest_policy_for_current_route()
    route = get_current_route()

    write_log(
        f"CLEAR detected | confidence={clear_conf:.2f} | "
        f"route={route['name']} | no blue drop confirmed"
    )
    write_log(
        f"No-chest trial counted | "
        f"count={state_memory.no_chest_trial_count}/{max_trials} | "
        f"no_chest_retries={no_chest_retries} | "
        f"total_allowed_no_chest_clears={max_trials} | "
        f"source={policy_source} | route={route['level']}"
    )

    if state_memory.no_chest_trial_count < max_trials:
        write_log(
            f"No-chest trial below limit. Retrying detector cycle on same selected level | "
            f"count={state_memory.no_chest_trial_count}/{max_trials} | "
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
        f"count={state_memory.no_chest_trial_count}/{max_trials} | "
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
        and not state_memory.blue_drop_handled_this_route
        and bot_state != STATE_FREEZE_AFTER_SWITCH
    ):
        if state_memory.post_clear_wait_started_at > 0:
            priority_reason = "late_blue_reward_after_clear"
        elif not state_memory.boss_seen_this_route:
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
            blue_candidate = classify_blue_chest_candidate(best_blue_confidence)
            recoverable_blue = blue_candidate["status"] in {"accepted", "near_threshold"}

            if state_memory.orphan_blue_chest_first_seen == 0:
                state_memory.orphan_blue_chest_first_seen = current_time
                write_log(
                    f"Orphan blue chest detected before boss confirmation | "
                    f"blue_status={blue_candidate['status']} | "
                    f"blue_confidence={best_blue_confidence:.2f} | "
                    f"accept_threshold={blue_candidate['accept_threshold']:.2f} | "
                    f"near_threshold={blue_candidate['near_threshold']:.2f} | "
                    f"required_cycles={ORPHAN_BLUE_CHEST_CONFIRM_CYCLES}"
                )

            if recoverable_blue:
                state_memory.orphan_blue_chest_confirm_count += 1
            else:
                if state_memory.orphan_blue_chest_confirm_count > 0:
                    write_log(
                        f"Orphan blue recovery counter reset by weak blue candidate | "
                        f"previous_cycles={state_memory.orphan_blue_chest_confirm_count} | "
                        f"blue_confidence={best_blue_confidence:.2f} | "
                        f"near_threshold={blue_candidate['near_threshold']:.2f}"
                    )
                state_memory.orphan_blue_chest_confirm_count = 0

            orphan_blue_elapsed = current_time - state_memory.orphan_blue_chest_first_seen
            orphan_blue_ready = (
                orphan_blue_recovery_can_track()
                and recoverable_blue
                and state_memory.orphan_blue_chest_confirm_count >= ORPHAN_BLUE_CHEST_CONFIRM_CYCLES
            )

            if orphan_blue_ready:
                recovery_kind = (
                    "accepted"
                    if blue_candidate["status"] == "accepted"
                    else "near_threshold"
                )
                write_log(
                    f"Orphan blue recovery confirmed | kind={recovery_kind} | "
                    f"cycles={state_memory.orphan_blue_chest_confirm_count}/"
                    f"{ORPHAN_BLUE_CHEST_CONFIRM_CYCLES} | "
                    f"visible_seconds={orphan_blue_elapsed:.2f} | "
                    f"blue_confidence={best_blue_confidence:.2f} | "
                    f"accept_threshold={blue_candidate['accept_threshold']:.2f} | "
                    f"near_threshold={blue_candidate['near_threshold']:.2f}"
                )
                write_log(
                    "Clicking orphan blue chest and continuing normal blue "
                    "reward/storage/repeat/advance flow."
                )

                return handle_confirmed_blue_drop(
                    detections,
                    f"orphan_blue_chest_{recovery_kind}_stable_before_boss",
                    f"cycles={state_memory.orphan_blue_chest_confirm_count}/"
                    f"{ORPHAN_BLUE_CHEST_CONFIRM_CYCLES} | "
                    f"visible_seconds={orphan_blue_elapsed:.2f} | "
                    f"blue_confidence={best_blue_confidence:.2f} | "
                    f"accept_threshold={blue_candidate['accept_threshold']:.2f} | "
                    f"near_threshold={blue_candidate['near_threshold']:.2f}",
                    allow_pre_boss=True,
                )

            if not RECOVER_ORPHAN_BLUE_CHEST_BEFORE_BOSS:
                write_log(
                    f"Orphan blue recovery disabled; waiting for boss/log confirmation | "
                    f"blue_confidence={best_blue_confidence:.2f}"
                )
            elif not recoverable_blue:
                write_log(
                    f"Orphan blue recovery ignoring weak candidate | "
                    f"blue_status={blue_candidate['status']} | "
                    f"blue_confidence={best_blue_confidence:.2f} | "
                    f"accept_threshold={blue_candidate['accept_threshold']:.2f} | "
                    f"near_threshold={blue_candidate['near_threshold']:.2f}"
                )
            elif state_memory.orphan_blue_chest_confirm_count < ORPHAN_BLUE_CHEST_CONFIRM_CYCLES:
                write_log(
                    f"Orphan blue recovery waiting for stability | "
                    f"blue_status={blue_candidate['status']} | "
                    f"cycles={state_memory.orphan_blue_chest_confirm_count}/"
                    f"{ORPHAN_BLUE_CHEST_CONFIRM_CYCLES} | "
                    f"blue_confidence={best_blue_confidence:.2f} | "
                    f"accept_threshold={blue_candidate['accept_threshold']:.2f} | "
                    f"near_threshold={blue_candidate['near_threshold']:.2f}"
                )
        else:
            if state_memory.orphan_blue_chest_confirm_count > 0:
                write_log(
                    f"Orphan blue chest no longer visible; recovery counter reset | "
                    f"previous_cycles={state_memory.orphan_blue_chest_confirm_count}"
                )

            state_memory.orphan_blue_chest_first_seen = 0
            state_memory.orphan_blue_chest_confirm_count = 0

        if boss_visible:
            state_memory.boss_seen_this_route = True
            bot_state = STATE_LOOK_FOR_BLUE_DROP
            state_memory.orphan_blue_chest_first_seen = 0
            state_memory.orphan_blue_chest_confirm_count = 0

            # Clear blue memory when boss is first confirmed.
            state_memory.last_blue_log_seen_after_boss = 0
            state_memory.last_blue_chest_seen_after_boss = 0

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
            state_memory.last_blue_chest_seen_after_boss = current_time

        if blue_log_visible:
            state_memory.last_blue_log_seen_after_boss = current_time

        blue_chest_recent = blue_signal_recent(
            state_memory.last_blue_chest_seen_after_boss,
            current_time,
            POST_BOSS_DROP_WINDOW_SECONDS,
        )

        blue_log_recent = blue_signal_recent(
            state_memory.last_blue_log_seen_after_boss,
            current_time,
            POST_BOSS_DROP_WINDOW_SECONDS,
        )

        if (
            state_memory.boss_seen_this_route
            and blue_chest_recent
            and blue_log_recent
            and not state_memory.blue_drop_handled_this_route
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
            state_memory.last_clear_seen_time = current_time
            state_memory.post_clear_best_conf = max(state_memory.post_clear_best_conf, clear_conf)

            if state_memory.blue_drop_handled_this_route:
                if not state_memory.clear_handled_this_trial:
                    state_memory.clear_handled_this_trial = True
                    write_log(
                        f"CLEAR ignored because blue drop was already handled | "
                        f"confidence={clear_conf:.2f}"
                    )
            else:
                if state_memory.post_clear_wait_started_at == 0:
                    state_memory.post_clear_wait_started_at = current_time
                    state_memory.post_clear_best_conf = clear_conf
                    write_log(
                        f"CLEAR detected; waiting for late blue reward | "
                        f"confidence={clear_conf:.2f} | "
                        f"wait_seconds={POST_CLEAR_REWARD_WAIT_SECONDS:.1f}"
                    )

        if state_memory.post_clear_wait_started_at > 0 and not state_memory.blue_drop_handled_this_route:
            post_clear_elapsed = current_time - state_memory.post_clear_wait_started_at

            if post_clear_elapsed >= POST_CLEAR_REWARD_WAIT_SECONDS:
                return handle_clear_no_chest_trial(state_memory.post_clear_best_conf)

        return {
            "state": bot_state,
            "boss_visible": False,
            "blue_chest_visible": blue_chest_visible,
            "blue_log_visible": blue_log_visible,
            "message": (
                f"Looking for blue drop | "
                f"chest_recent={blue_chest_recent} | "
                f"log_recent={blue_log_recent} | "
                f"post_clear_wait={state_memory.post_clear_wait_started_at > 0}"
            )
        }

    return {
        "state": bot_state,
        "boss_visible": False,
        "blue_chest_visible": False,
        "blue_log_visible": False,
        "message": "Unknown state"
    }


def get_stash_tab_templates():
    if not isinstance(STASH_TAB_TEMPLATES, dict):
        return {}

    return {
        stash_name: path
        for stash_name, path in STASH_TAB_TEMPLATES.items()
        if stash_name in STASH_PAGE_ORDER and path
    }


def get_storage_stash_search_region():
    return REGIONS.get(STORAGE_STASH_SEARCH_REGION, REGIONS.get("hero_panel", (0, 220, 640, 680)))


def next_stash_page_name(current_stash):
    if current_stash not in STASH_PAGE_ORDER:
        return None

    index = STASH_PAGE_ORDER.index(current_stash)
    return STASH_PAGE_ORDER[(index + 1) % len(STASH_PAGE_ORDER)]


def detect_storage_stash_page(screenshot):
    templates = get_stash_tab_templates()

    if not templates:
        return {
            "detected": False,
            "stash": None,
            "confidence": 0.0,
            "reason": "stash_tab_templates_missing_or_invalid",
        }

    return detect_current_stash_page(
        screenshot,
        templates,
        get_storage_stash_search_region(),
        STASH_TAB_MATCH_THRESHOLD,
    )


def check_current_stash_last_slot(screenshot):
    return check_stash_last_slot_blank(
        screenshot,
        STASH_BLANK_TEMPLATE,
        STASH_SORT_TEMPLATE,
        get_storage_stash_search_region(),
        STORAGE_ANCHOR_MATCH_THRESHOLD,
        STASH_LAST_SLOT_BLANK_THRESHOLD,
        STASH_LAST_SLOT_UNCERTAIN_MARGIN,
        STASH_LAST_SLOT_ANCHOR_OFFSET_X,
        STASH_LAST_SLOT_ANCHOR_OFFSET_Y,
        STASH_LAST_SLOT_WIDTH,
        STASH_LAST_SLOT_HEIGHT,
        save_debug=SAVE_DEBUG_SCREENSHOTS,
        anchor_label="stash_sort",
    )


def check_current_stash_grid_space(screenshot):
    return check_stash_grid_space(
        screenshot,
        STASH_BLANK_TEMPLATE,
        STASH_SORT_TEMPLATE,
        get_storage_stash_search_region(),
        STORAGE_ANCHOR_MATCH_THRESHOLD,
        STASH_LAST_SLOT_BLANK_THRESHOLD,
        STASH_LAST_SLOT_UNCERTAIN_MARGIN,
        STORAGE_GRID_ANCHOR_OFFSET_X,
        STORAGE_GRID_ANCHOR_OFFSET_Y,
        STORAGE_GRID_SLOT_WIDTH,
        STORAGE_GRID_SLOT_HEIGHT,
        STORAGE_GRID_SLOT_GAP_X,
        STORAGE_GRID_SLOT_GAP_Y,
        STORAGE_GRID_ROWS,
        STORAGE_GRID_COLS,
        save_debug=SAVE_DEBUG_SCREENSHOTS,
        force_debug_on_failure=ALWAYS_SAVE_STORAGE_DIAGNOSTICS_ON_FAILURE,
    )


def find_stash_sort_button(screenshot):
    try:
        found, center, confidence, match_info = find_template_in_box(
            screenshot,
            STASH_SORT_TEMPLATE,
            get_storage_stash_search_region(),
            STORAGE_ANCHOR_MATCH_THRESHOLD,
            label="stash_sort",
        )
    except Exception as e:
        write_log(
            f"Stash sort button detection failed | "
            f"template={STASH_SORT_TEMPLATE} | error={e}"
        )
        return {
            "found": False,
            "center": None,
            "confidence": 0.0,
            "match_info": None,
            "error": str(e),
        }

    return {
        "found": found,
        "center": center,
        "confidence": confidence,
        "match_info": match_info,
        "error": None,
    }


def sort_current_stash_before_full_check(hwnd, screenshot, stash_label, attempt, max_pages):
    if not SORT_STASH_BEFORE_FULL_CHECK:
        write_log(
            f"Stash sort skipped before full check: disabled by config | "
            f"stash={stash_label} | attempt={attempt}/{max_pages}"
        )
        return screenshot

    sort_button = find_stash_sort_button(screenshot)
    write_log(
        f"Stash sort button search | stash={stash_label} | attempt={attempt}/{max_pages} | "
        f"found={sort_button.get('found')} | "
        f"confidence={sort_button.get('confidence', 0.0):.2f} | "
        f"threshold={STORAGE_ANCHOR_MATCH_THRESHOLD:.2f} | "
        f"center={sort_button.get('center')}"
    )

    if not sort_button.get("found") or sort_button.get("center") is None:
        write_log(
            f"Storage transfer aborted safely: stash sort button not found | "
            f"stash={stash_label} | attempt={attempt}/{max_pages} | "
            f"confidence={sort_button.get('confidence', 0.0):.2f}"
        )
        return None

    center_x, center_y = sort_button["center"]
    click_ok = click_window_point(
        hwnd,
        center_x,
        center_y,
        label="stash_sort",
    )

    if not click_ok:
        write_log(
            f"Storage transfer aborted safely: stash sort click failed | "
            f"stash={stash_label} | center={sort_button.get('center')}"
        )
        return None

    write_log(
        f"Stash sort click sent before full check | "
        f"stash={stash_label} | center={sort_button.get('center')} | "
        f"wait={POST_STASH_SORT_WAIT_SECONDS:.2f}s"
    )
    time.sleep(POST_STASH_SORT_WAIT_SECONDS)

    try:
        return capture_window(hwnd)
    except Exception as e:
        write_log(
            f"Storage transfer aborted safely: screenshot after stash sort failed | "
            f"stash={stash_label} | error={e}"
        )
        return None


def click_stash_page_tab(hwnd, screenshot, stash_name):
    templates = get_stash_tab_templates()
    template_path = templates.get(stash_name)

    if not template_path:
        write_log(f"Stash switch failed: template missing from config | stash={stash_name}")
        return False

    try:
        found, center, confidence, _match_info = find_template_in_box(
            screenshot,
            template_path,
            get_storage_stash_search_region(),
            STASH_TAB_MATCH_THRESHOLD,
            label=f"select_{stash_name}",
        )
    except Exception as e:
        write_log(
            f"Stash switch failed: target tab detection error | "
            f"target={stash_name} | path={template_path} | error={e}"
        )
        return False

    write_log(
        f"Stash tab search | target={stash_name} | "
        f"confidence={confidence:.2f} | threshold={STASH_TAB_MATCH_THRESHOLD:.2f} | "
        f"center={center}"
    )

    if not found or center is None:
        write_log(
            f"Stash switch failed: target tab not found | "
            f"target={stash_name} | confidence={confidence:.2f}"
        )
        return False

    click_ok = click_window_point(
        hwnd,
        center[0],
        center[1],
        label=f"stash_tab_{stash_name}",
    )

    if not click_ok:
        write_log(
            f"Stash switch failed safely during click | "
            f"target={stash_name} | center={center}"
        )
        return False

    write_log(f"Stash switch click sent | target={stash_name} | center={center}")
    return True


def ensure_storage_stash_has_space(hwnd, screenshot):
    if not AUTO_SWITCH_STASH_WHEN_FULL:
        write_log("Auto stash switch disabled; continuing storage transfer without stash scan.")
        return screenshot

    max_pages = max(1, min(MAX_STASH_PAGES_TO_SCAN, len(STASH_PAGE_ORDER)))
    current_screenshot = screenshot
    checked_pages = []
    expected_current_page = None

    for attempt in range(1, max_pages + 1):
        try:
            stash_page = detect_storage_stash_page(current_screenshot)
            visual_stash_name = stash_page.get("stash")
            visual_detected = stash_page.get("detected")
            stash_name = (
                expected_current_page
                if expected_current_page in STASH_PAGE_ORDER
                else visual_stash_name
            )
            stash_label = stash_name or "unknown"

            if expected_current_page is not None and visual_stash_name != expected_current_page:
                write_log(
                    f"Stash page visual/expected mismatch before sort | "
                    f"attempt={attempt}/{max_pages} | visual={visual_stash_name} | "
                    f"visual_detected={visual_detected} | expected={expected_current_page} | "
                    f"using={stash_label}"
                )

            current_screenshot = sort_current_stash_before_full_check(
                hwnd,
                current_screenshot,
                stash_label,
                attempt,
                max_pages,
            )

            if current_screenshot is None:
                return None

            stash_page = detect_storage_stash_page(current_screenshot)
            visual_stash_name = stash_page.get("stash")
            visual_detected = stash_page.get("detected")
            stash_name = (
                expected_current_page
                if expected_current_page in STASH_PAGE_ORDER
                else visual_stash_name
            )
            stash_label = stash_name or "unknown"

            if expected_current_page is not None and visual_stash_name != expected_current_page:
                write_log(
                    f"Stash page visual/expected mismatch after sort | "
                    f"attempt={attempt}/{max_pages} | visual={visual_stash_name} | "
                    f"visual_detected={visual_detected} | expected={expected_current_page} | "
                    f"using={stash_label}"
                )

            grid_space = check_current_stash_grid_space(current_screenshot)
        except Exception as e:
            write_log(
                f"Storage transfer aborted safely: stash visual check failed | "
                f"attempt={attempt}/{max_pages} | error={e}"
            )
            return None

        if stash_label in checked_pages:
            write_log(
                f"Storage scan revisiting stash label | stash={stash_label} | "
                f"attempt={attempt}/{max_pages} | checked={checked_pages} | "
                f"expected_current_page={expected_current_page}"
            )

        checked_pages.append(stash_label)

        anchor = grid_space.get("anchor", {})
        write_log(
            f"Stash grid space check | attempt={attempt}/{max_pages} | "
            f"stash={stash_label} | visual_stash={visual_stash_name} | "
            f"expected_stash={expected_current_page} | "
            f"stash_confidence={stash_page.get('confidence', 0.0):.2f} | "
            f"anchor_found={anchor.get('found')} | anchor_confidence={anchor.get('confidence', 0.0):.2f} | "
            f"anchor_label={anchor.get('label')} | "
            f"grid_first_slot_center={grid_space.get('grid_first_slot_center')} | "
            f"blank_count={grid_space.get('blank_count')} | "
            f"occupied_count={grid_space.get('occupied_count')} | "
            f"uncertain_count={grid_space.get('uncertain_count')} | "
            f"best_blank_confidence={grid_space.get('best_blank_confidence', 0.0):.2f} | "
            f"blank_threshold={STASH_LAST_SLOT_BLANK_THRESHOLD:.2f} | "
            f"status={grid_space.get('status')} | reason={grid_space.get('reason')} | "
            f"debug_grid_annotated={grid_space.get('debug_grid_annotated_path')}"
        )

        if grid_space.get("status") == "available":
            write_log(
                f"Stash page has available grid slot; continuing storage transfer | "
                f"stash={stash_label} | checked={checked_pages} | "
                f"blank_count={grid_space.get('blank_count')} | "
                f"best_blank_confidence={grid_space.get('best_blank_confidence', 0.0):.2f}"
            )
            return current_screenshot

        if grid_space.get("status") == "uncertain":
            write_log(
                f"Storage transfer aborted safely: stash grid space state uncertain | "
                f"stash={stash_label} | checked={checked_pages} | "
                f"reason={grid_space.get('reason')} | "
                f"blank_count={grid_space.get('blank_count')} | "
                f"occupied_count={grid_space.get('occupied_count')} | "
                f"uncertain_count={grid_space.get('uncertain_count')} | "
                f"debug_grid_annotated={grid_space.get('debug_grid_annotated_path')}"
            )
            return None

        if not stash_page.get("detected") or stash_name not in STASH_PAGE_ORDER:
            write_log(
                f"Storage transfer aborted safely: current stash page unknown while grid appears full | "
                f"stash_confidence={stash_page.get('confidence', 0.0):.2f} | "
                f"checked={checked_pages}"
            )
            return None

        if attempt >= max_pages:
            break

        next_stash = next_stash_page_name(stash_name)

        if next_stash is None:
            write_log(
                f"Storage transfer aborted safely: could not determine next stash page | "
                f"current={stash_name} | checked={checked_pages}"
            )
            return None

        write_log(
            f"Current stash grid appears full; switching stash page | "
            f"current={stash_name} | next={next_stash} | attempt={attempt}/{max_pages}"
        )

        if not click_stash_page_tab(hwnd, current_screenshot, next_stash):
            write_log(
                f"Storage transfer aborted safely: stash switch failed | "
                f"current={stash_name} | next={next_stash} | checked={checked_pages}"
            )
            return None

        expected_current_page = next_stash
        write_log(
            f"Stash switch target recorded | target={next_stash} | "
            f"checked={checked_pages}"
        )
        time.sleep(STASH_SWITCH_WAIT_SECONDS)

        try:
            current_screenshot = capture_window(hwnd)
        except Exception as e:
            write_log(
                f"Storage transfer aborted safely: screenshot after stash switch failed | "
                f"next={next_stash} | error={e}"
            )
            return None

    write_log(
        f"Storage transfer aborted safely: all checked stash pages appear full | "
        f"checked={checked_pages} | max_pages={max_pages}"
    )
    return None


def run_backpack_to_storage_transfer(context="blue_chest"):
    wait_seconds = config_non_negative_float("post_blue_chest_storage_wait_seconds", 0.8)
    threshold = config_non_negative_float("backpack_to_storage_match_threshold", 0.80)
    post_click_wait = config_non_negative_float("post_storage_click_wait_seconds", 0.8)

    write_log(f"Starting backpack-to-storage transfer | context={context}")
    time.sleep(wait_seconds)

    template_path = "templates/general/backpack_to_storage_button.png"

    try:
        template = load_template(template_path)
    except FileNotFoundError as e:
        write_log(
            f"Storage transfer skipped: template missing | context={context} | "
            f"path={template_path} | error={e}"
        )
        return False

    if template is None:
        write_log(
            f"Storage transfer skipped: template failed to load | "
            f"context={context} | path={template_path}"
        )
        return False

    screenshot = capture_window(GAME_HWND)

    if screenshot is None:
        write_log(f"Storage transfer skipped: screenshot failed | context={context}")
        return False

    screenshot = ensure_storage_stash_has_space(GAME_HWND, screenshot)

    if screenshot is None:
        write_log(
            f"Storage transfer skipped: no available stash page confirmed | context={context}"
        )
        return False

    # The storage/backpack button appears in the hero panel, not battle_bottom.
    x1, y1, x2, y2 = REGIONS.get("hero_panel", (0, 220, 640, 680))
    region_img = crop(screenshot, (x1, y1, x2, y2))

    if region_img is None:
        write_log(f"Storage transfer skipped: hero_panel crop failed | context={context}")
        return False

    match = match_template(region_img, template)
    confidence = match["confidence"]

    write_log(
        f"Storage button search | region=hero_panel | "
        f"confidence={confidence:.2f} | threshold={threshold:.2f} | context={context}"
    )

    if confidence < threshold:
        write_log(
            f"Storage button not found; skipping | "
            f"region=hero_panel | confidence={confidence:.2f} | "
            f"threshold={threshold:.2f} | context={context}"
        )
        return False

    center_x, center_y = match["center"]
    local_x = x1 + center_x
    local_y = y1 + center_y

    write_log(
        f"Storage button found | region=hero_panel | "
        f"confidence={confidence:.2f} | center=({local_x}, {local_y}) | context={context}"
    )

    click_window_point(GAME_HWND, local_x, local_y, label="backpack_to_storage")
    time.sleep(post_click_wait)

    write_log(f"Backpack-to-storage click completed | context={context}")
    return True


def try_move_backpack_to_storage_after_blue_chest():
    move_to_storage_enabled = env_flag(
        "MAATBH_MOVE_TO_STORAGE",
        config_bool("move_backpack_to_storage_after_blue_chest", False)
    )

    if not move_to_storage_enabled:
        write_log("Storage transfer disabled by GUI/config; skipping.")
        return False

    return run_backpack_to_storage_transfer(context="blue_chest")


def try_move_backpack_to_storage_after_non_blue_box():
    if not MOVE_BACKPACK_TO_STORAGE_AFTER_NON_BLUE_BOX:
        write_log("Storage transfer after non-blue box disabled by GUI/config; skipping.")
        return False

    if GAME_HWND is None:
        write_log("Storage transfer after non-blue box skipped: game window unavailable.")
        return False

    if bot_state not in {STATE_LOOK_FOR_BOSS, STATE_LOOK_FOR_BLUE_DROP}:
        write_log(
            f"Storage transfer after non-blue box skipped: "
            f"state_not_same_level_observation:{bot_state}"
        )
        return False

    if state_memory.blue_drop_handled_this_route:
        write_log(
            "Storage transfer after non-blue box skipped: blue drop already handled this route."
        )
        return False

    if state_memory.post_clear_wait_started_at > 0:
        write_log(
            "Storage transfer after non-blue box skipped: post-clear reward wait is active."
        )
        return False

    if state_memory.reward_navigation_interruption is not None:
        write_log(
            "Storage transfer after non-blue box skipped: reward navigation interruption is active."
        )
        return False

    write_log("Starting storage transfer after non-blue box.")
    transfer_ok = run_backpack_to_storage_transfer(context="non_blue_box")

    if transfer_ok:
        write_log("Storage transfer completed after non-blue box.")
    else:
        write_log("Storage transfer skipped/failed after non-blue box.")

    return transfer_ok


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

    mouse_before_x, mouse_before_y = get_mouse_position()

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

    focus_window(hwnd, warning_message="Window focus warning", wait_seconds=0.2)

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
    if not state_memory.should_print_bot_status(bot_info):
        return

    safe_print(
        "\n"
        f"Bot state: {bot_info['state']} | "
        f"Boss: {bot_info['boss_visible']} | "
        f"Blue chest: {bot_info['blue_chest_visible']} | "
        f"Blue log: {bot_info['blue_log_visible']} | "
        f"{bot_info['message']}"
    )


def maybe_log_heartbeat(current_time, bot_info):
    if not state_memory.heartbeat_due(current_time, HEARTBEAT_LOG_INTERVAL_SECONDS):
        return

    route = get_current_route()
    _, max_trials, _ = get_no_chest_policy_for_current_route()

    write_log(
        "HEARTBEAT | "
        f"state={bot_info['state']} | "
        f"route={current_route_index + 1}/{len(ROUTE)} | "
        f"target={route['difficulty']} | {route['chapter']} | {route['level']} | "
        f"no_chest_count={state_memory.no_chest_trial_count}/{max_trials}"
    )


input_controller = InputController(
    write_log=write_log,
    capture_window=capture_window,
    safe_window_rect=safe_window_rect,
    safe_client_rect=safe_client_rect,
    safe_client_origin=safe_client_origin,
    format_diag_value=format_diag_value,
    get_config=get_config,
    get_game_hwnd=lambda: GAME_HWND,
    regions=REGIONS,
    use_background_input=USE_BACKGROUND_INPUT,
    nav_click_delay_seconds=NAV_CLICK_DELAY_SECONDS,
    map_scroll_chunk_repeat=MAP_SCROLL_CHUNK_REPEAT,
    fast_scroll_use_burst=FAST_SCROLL_USE_BURST,
    fast_scroll_burst_count=FAST_SCROLL_BURST_COUNT,
    coordinate_scaling_enabled=COORDINATE_SCALING_ENABLED,
    coordinate_scaling_auto_detect=COORDINATE_SCALING_AUTO_DETECT,
    coordinate_scaling_tolerance=COORDINATE_SCALING_TOLERANCE,
    pause_on_severe_coordinate_mismatch=PAUSE_ON_SEVERE_COORDINATE_MISMATCH,
    mouse_fail_safe_margin_px=MOUSE_FAIL_SAFE_MARGIN_PX,
    mouse_parking_enabled=MOUSE_PARKING_ENABLED,
    mouse_parking_x=MOUSE_PARKING_X,
    mouse_parking_y=MOUSE_PARKING_Y,
    mouse_parking_wait_seconds=MOUSE_PARKING_WAIT_SECONDS,
    mouse_parking_mode=MOUSE_PARKING_MODE,
    mouse_parking_static_x=MOUSE_PARKING_STATIC_X,
    mouse_parking_static_y=MOUSE_PARKING_STATIC_Y,
    mouse_parking_fail_safe_relocate_enabled=MOUSE_PARKING_FAIL_SAFE_RELOCATE_ENABLED,
    mouse_parking_fail_safe_min_screen_margin_px=MOUSE_PARKING_FAIL_SAFE_MIN_SCREEN_MARGIN_PX,
    mouse_parking_fallback_static_x=MOUSE_PARKING_FALLBACK_STATIC_X,
    mouse_parking_fallback_static_y=MOUSE_PARKING_FALLBACK_STATIC_Y,
)

# Preserve the old helper names in runner while the implementations live in actions.py.
make_lparam = input_controller.make_lparam
local_to_screen = input_controller.local_to_screen
local_to_client = input_controller.local_to_client
get_client_screen_point = input_controller.get_client_screen_point
rect_width_height = input_controller.rect_width_height
build_coordinate_scaling_status = input_controller.build_coordinate_scaling_status
update_coordinate_scaling_status = input_controller.update_coordinate_scaling_status
get_coordinate_scaling_status = input_controller.get_coordinate_scaling_status
log_coordinate_scaling_status = input_controller.log_coordinate_scaling_status
screenshot_local_to_click_coordinates = input_controller.screenshot_local_to_click_coordinates
get_virtual_screen_rect = input_controller.get_virtual_screen_rect
get_monitor_rect_for_point = input_controller.get_monitor_rect_for_point
get_monitor_rect_for_window = input_controller.get_monitor_rect_for_window
is_screen_point_fail_safe_risky = input_controller.is_screen_point_fail_safe_risky
clamp_screen_point_to_safe_monitor_area = input_controller.clamp_screen_point_to_safe_monitor_area
safe_pyautogui_move_to = input_controller.safe_pyautogui_move_to
safe_pyautogui_click = input_controller.safe_pyautogui_click
safe_pyautogui_scroll = input_controller.safe_pyautogui_scroll
screen_to_local = input_controller.screen_to_local
get_client_local_bounds = input_controller.get_client_local_bounds
build_parking_point_from_local = input_controller.build_parking_point_from_local
make_clamped_client_point = input_controller.make_clamped_client_point
get_client_centerish_parking_candidates = input_controller.get_client_centerish_parking_candidates
choose_safe_mouse_parking_candidate = input_controller.choose_safe_mouse_parking_candidate
get_monitor_safe_parking_point = input_controller.get_monitor_safe_parking_point
get_default_mouse_parking_point = input_controller.get_default_mouse_parking_point
park_mouse_before_recognition = input_controller.park_mouse_before_recognition
background_click_window_point = input_controller.background_click_window_point
background_scroll_window_point = input_controller.background_scroll_window_point
focus_window = input_controller.focus_window
get_mouse_position = input_controller.position
get_screen_size = input_controller.screen_size

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
    return input_controller.click_window_point(
        hwnd,
        local_x,
        local_y,
        label=label,
        coordinate_space=coordinate_space,
    )
    
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
    return input_controller.scroll_map(
        hwnd,
        direction,
        repeat,
        focus,
        resolve_legacy_focus=lambda reason, label: resolve_legacy_map_scroll_focus(
            hwnd,
            reason=reason,
            label=label,
        ),
    )


def fast_scroll_map_boundary(hwnd, direction, repeat, route=None):
    return input_controller.fast_scroll_map_boundary(
        hwnd,
        direction,
        repeat,
        focus_factory=lambda: resolve_map_scroll_focus(
            hwnd,
            route=route,
            label=f"fast_scroll_{direction}",
        ),
        resolve_legacy_focus=lambda reason, label: resolve_legacy_map_scroll_focus(
            hwnd,
            reason=reason,
            label=label,
        ),
        slow_scroll_fallback=lambda fallback_repeat: scroll_map(
            hwnd,
            direction,
            repeat=fallback_repeat,
        ),
    )


def click_or_verify_level_dot(hwnd, match_info, route):
    """
    Verify target level selection using green dot.
    If not already selected, find white dot, click it, then verify green dot.
    """
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
        state_memory.mark_level_selection_evidence(
            route,
            "green_dot_already_selected",
            green_center,
            green_conf,
        )
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
            state_memory.mark_level_selection_evidence(
                route,
                "green_dot_after_click",
                green_center_after,
                green_conf_after,
            )
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
    return state_memory.get_current_route(ROUTE, current_route_index)


def clear_active_same_tier_substitute(reason):
    state_memory.clear_active_same_tier_substitute(reason, write_log=write_log)


def set_active_same_tier_substitute(route, original_route, reason):
    state_memory.set_active_same_tier_substitute(
        route,
        original_route,
        reason,
        write_log=write_log,
    )


def get_route_navigation_key(route=None):
    if route is None:
        route = get_current_route()

    return state_memory.get_route_navigation_key(current_route_index, route)


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
    state_memory.reset_consecutive_navigation_skips(reason, write_log=write_log)


def observe_route_target_state(hwnd, route):
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
        observed = empty_route_target_observation()
        observed["error"] = str(e)
        return observed

    return observe_route_target_state_from_image(img, route)


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
        evidence = state_memory.last_route_level_selection_evidence

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
    state_memory.mark_reward_navigation_interruption(
        context,
        get_route_navigation_key(),
    )


def consume_reward_navigation_interruption(expected_context):
    return state_memory.consume_reward_navigation_interruption(
        expected_context,
        write_log=write_log,
    )


def clear_stale_reward_navigation_interruption(context):
    state_memory.clear_stale_reward_navigation_interruption(
        context,
        write_log=write_log,
    )


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
    state_memory.reset_route_navigation_retries(
        reason,
        get_route_navigation_key(),
        write_log=write_log,
    )


def record_route_navigation_failure(reason):
    """
    Count failed full navigation attempts for the current route.
    Returns True when another retry is allowed.
    """
    global bot_state

    route = get_current_route()
    route_key = get_route_navigation_key(route)
    retry_allowed = state_memory.record_route_navigation_failure(
        route,
        route_key,
        MAX_ROUTE_NAVIGATION_RETRIES,
        reason,
        write_log=write_log,
    )

    if retry_allowed:
        return True

    bot_state = STATE_NAVIGATION_FAILED
    log_navigation_failed_marker(reason)
    write_log(
        f"NAV FAILED final; stopping repeated scroll | "
        f"route={route['name']} | difficulty={route['difficulty']} | "
        f"chapter={route['chapter']} | level={route['level']} | "
        f"failed_attempts={state_memory.route_navigation_retry_count} | "
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

    state_memory.consecutive_navigation_skips += 1
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
        f"consecutive_skips={state_memory.consecutive_navigation_skips}/{MAX_CONSECUTIVE_NAVIGATION_SKIPS}"
    )

    if SHOW_NAVIGATION_FAILURE_WARNING:
        write_log(
            f"关卡导航失败 {route_index + 1}: "
            f"{route_target_label(route)}. 该关卡被跳过，MAA继续运行。 "
            "请导出log文件以供分析。若不打算分析该问题，请无视本条消息。"
        )

    write_navigation_failure_report(route_index, route, observed, reason, "skipped")

    if state_memory.consecutive_navigation_skips >= MAX_CONSECUTIVE_NAVIGATION_SKIPS:
        write_log(
            f"Too many consecutive navigation skips; pausing bot | "
            f"consecutive_skips={state_memory.consecutive_navigation_skips} | "
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


def repeat_current_route_after_blue_chest():
    """
    Repeat the current route after successful blue reward handling without
    advancing the route index.
    """
    global route_start_time
    global bot_state
    global freeze_start_time

    route = get_current_route()
    route_start_time = time.time()

    write_log(
        f"Repeating same route after blue chest | "
        f"route_index={current_route_index + 1}/{len(ROUTE)} | "
        f"target={route['difficulty']} | {route['chapter']} | {route['level']}"
    )

    clear_active_same_tier_substitute("repeat_same_level_after_blue_chest")
    reset_no_chest_trial_count("repeat_same_level_after_blue_chest")
    reset_route_detection_memory()
    reset_route_navigation_retries("repeat_same_level_after_blue_chest")
    reset_chapter_ambiguous_attempt_scope("repeat_same_level_after_blue_chest")

    navigation_ok = True
    time.sleep(1.0)
    navigation_ok = navigate_to_current_route_if_enabled()

    if not navigation_ok:
        if bot_state == STATE_NAVIGATION_FAILED:
            write_log("Same-level repeat navigation ended in paused navigation-failed state.")
            return False

        if record_route_navigation_failure("repeat_same_level_after_blue_chest_navigation_failed"):
            bot_state = STATE_STARTUP_NAVIGATION
            write_log(
                f"Same-level repeat navigation failed. Will retry in "
                f"{STARTUP_NAV_RETRY_SECONDS:.0f}s and ignore chest/boss decisions until it succeeds."
            )
            return False

    reset_route_detection_memory()
    bot_state = STATE_FREEZE_AFTER_SWITCH
    freeze_start_time = time.time()
    write_log(
        f"Same-level repeat armed; route index unchanged | "
        f"route_index={current_route_index + 1}/{len(ROUTE)} | "
        f"target={route['difficulty']} | {route['chapter']} | {route['level']} | "
        "entering freeze window"
    )
    return True


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
        f"Boss seen this route: {state_memory.boss_seen_this_route}",
        f"Blue drop handled: {state_memory.blue_drop_handled_this_route}",
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

def initialize_startup_runtime():
    global ROUTE
    global startup_runtime_initialized

    if startup_runtime_initialized:
        return

    emit_config_load_messages()
    log_app_start_boundary()
    log_console_encoding_status()
    log_recognition_profile_startup()
    ROUTE = load_farm_plan(ROUTE)
    log_chest_tier_breakpoint_validation()
    log_startup_template_check()
    startup_runtime_initialized = True


def main():
    global last_boss_log_time
    global last_manual_nav_time
    global bot_state
    global freeze_start_time
    initialize_startup_runtime()
    get_config()
    last_boss_log_time = 0
    input_mode = "background PostMessage" if USE_BACKGROUND_INPUT else "foreground mouse"
    log_session_start_marker(input_mode)
    log_cycle_start_marker()
    hwnd, title = find_window_by_title_keyword(WINDOW_KEYWORD)
    global GAME_HWND
    GAME_HWND = hwnd
    if hwnd is None:
        lookup_error = get_last_window_lookup_error()

        if lookup_error:
            write_log(f"Window lookup failed | keyword={WINDOW_KEYWORD} | {lookup_error}")
            safe_print(f"Window enumeration failed while looking for: {WINDOW_KEYWORD}")
            safe_print(lookup_error)
        else:
            write_log(f"Game window not found | keyword={WINDOW_KEYWORD}")
            safe_print(f"Could not find a window containing: {WINDOW_KEYWORD}")

        safe_print("Make sure TaskBarHero is open and visible, then start the bot again.")
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

        visual_snapshot = collect_detection_snapshot(
            img,
            blue_template,
            brown_template,
            boss_warning_template,
            clear_template,
        )
        detections = visual_snapshot.detections
        boss_visible = visual_snapshot.boss_visible
        boss_region = visual_snapshot.boss_region
        boss_pixels = visual_snapshot.boss_pixels
        boss_conf = visual_snapshot.boss_confidence
        clear_visible = visual_snapshot.clear_visible
        clear_conf = visual_snapshot.clear_confidence

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
            maybe_open_non_blue_boxes_same_level(
                detections,
                clear_visible=clear_visible,
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
