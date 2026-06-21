import copy
import json
import sys
from pathlib import Path


APP_VERSION = "2.0.0"
_CONFIG_LOAD_MESSAGES = []
_CONFIG_LOAD_MESSAGES_EMITTED = False

INVISIBLE_UNICODE_TRANSLATION = {
    ord("\u200b"): None,
    ord("\u200c"): None,
    ord("\u200d"): None,
    ord("\ufeff"): None,
}


def configure_console_encoding():
    for stream in (getattr(sys, "stdout", None), getattr(sys, "stderr", None)):
        if stream is None or not hasattr(stream, "reconfigure"):
            continue

        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def sanitize_text_for_output(value):
    return str(value).translate(INVISIBLE_UNICODE_TRANSLATION)


def safe_print(*args, **kwargs):
    sanitized_args = [sanitize_text_for_output(arg) for arg in args]

    try:
        print(*sanitized_args, **kwargs)
    except UnicodeEncodeError:
        encoding = getattr(getattr(sys, "stdout", None), "encoding", None) or "utf-8"
        fallback_args = [
            str(arg).encode(encoding, errors="replace").decode(encoding, errors="replace")
            for arg in sanitized_args
        ]
        print(*fallback_args, **kwargs)


configure_console_encoding()


def _record_config_load_message(message):
    _CONFIG_LOAD_MESSAGES.append(message)


def emit_config_load_messages():
    global _CONFIG_LOAD_MESSAGES_EMITTED

    if _CONFIG_LOAD_MESSAGES_EMITTED:
        return

    for message in _CONFIG_LOAD_MESSAGES:
        safe_print(message)

    _CONFIG_LOAD_MESSAGES_EMITTED = True


DEFAULT_CONFIG = {
    "ui_scale": 1.0,
    "recognition_mode": "balanced",
    "default_no_chest_retries": 4,
    "default_max_trials_if_no_chest": 5,
    "post_clear_reward_wait_seconds": 3.0,
    "save_debug_screenshots": False,
    "max_route_navigation_retries": 2,
    "use_fast_boundary_scroll": True,
    "fast_scroll_repeat": 80,
    "fast_scroll_use_burst": True,
    "fast_scroll_burst_count": 4,
    "fast_scroll_pause": 0.25,
    "use_expanded_roi_retry": True,
    "expanded_roi_margin_px": 48,
    "expanded_roi_scale_factor": 1.15,
    "expanded_roi_only_on_ui_warning": True,
    "level_y_position_tolerance_px": 5,
    "chapter_ambiguous_click_verify_enabled": True,
    "chapter_ambiguous_click_max_attempts": 1,
    "chapter_ambiguous_min_confidence": None,
    "chapter_geometry_fallback_enabled": True,
    "chapter_tab_spacing_px": 64,
    "chapter_geometry_tolerance_px": 18,
    "chapter_geometry_min_confidence": 0.78,
    "chapter_geometry_require_dynamic_anchor": True,
    "mouse_parking_enabled": True,
    "mouse_parking_x": None,
    "mouse_parking_y": None,
    "mouse_parking_wait_seconds": 0.15,
    "mouse_parking_before_chapter_detection": True,
    "mouse_parking_before_difficulty_detection": True,
    "mouse_parking_before_level_detection": False,
    "mouse_parking_mode": "recovery_only",
    "mouse_parking_strategy": "static_client_point",
    "mouse_parking_static_x": 320,
    "mouse_parking_static_y": 120,
    "mouse_parking_fail_safe_relocate_enabled": True,
    "mouse_parking_fail_safe_min_screen_margin_px": 60,
    "mouse_parking_fallback_static_x": 320,
    "mouse_parking_fallback_static_y": 220,
    "mouse_parking_fallback_strategy": "monitor_safe_point",
    "mouse_fail_safe_margin_px": 40,
    "mouse_movement_fail_safe_policy": "return_failure",
    "coordinate_scaling_enabled": True,
    "coordinate_scaling_auto_detect": True,
    "coordinate_scaling_tolerance": 0.05,
    "pause_on_severe_coordinate_mismatch": False,
    "difficulty_dropdown_geometry_fallback_enabled": True,
    "difficulty_dropdown_row_spacing_px": 43,
    "difficulty_dropdown_first_row_offset_y": 42,
    "difficulty_dropdown_option_x_offset": 0,
    "difficulty_dropdown_geometry_verify_after_click": True,
    "same_tier_substitution_enabled": True,
    "same_tier_substitution_max_candidates": 3,
    "same_tier_substitution_prefer_farm_plan_routes": True,
    "same_tier_substitution_allow_cross_difficulty": True,
    "dynamic_scroll_focus_enabled": True,
    "dynamic_scroll_focus_min_anchor_confidence": 0.78,
    "dynamic_scroll_focus_y": 520,
    "dynamic_scroll_focus_edge_margin_px": 40,
    "navigation_failure_policy": "skip_route",
    "max_consecutive_navigation_skips": 3,
    "show_navigation_failure_warning": True,
    "emergency_hotkey_enabled": True,
    "emergency_hotkey_modifiers": "ctrl+shift",
    "emergency_hotkey_key": "F12",
    "route_invariant_allow_selected_evidence": True,
    "route_invariant_level_confidence_floor": 0.88,
    "route_invariant_green_dot_min_confidence": 0.75,
    "route_invariant_require_level_y_ok": True,
    "level_near_match_margin": 0.10,
    "selected_level_green_pixel_min": 20,
    "selected_level_green_ratio_min": 0.03,
    "selected_level_green_hsv_lower": [35, 40, 40],
    "selected_level_green_hsv_upper": [95, 255, 255],
    "stop_if_blue_chest_found": True,
    "open_all_boxes_on_same_level": True,
    "non_blue_box_click_cooldown_seconds": 1.0,
    "recover_orphan_blue_chest_before_boss": True,
    "orphan_blue_chest_confirm_cycles": 2,
    "orphan_blue_chest_near_threshold_margin": 0.03,
    "repeat_same_level_after_blue_chest": False,
    "assume_mailbox_after_max_trials": True,
    "skip_level_if_already_selected": True,
    "move_backpack_to_storage_after_blue_chest": False,
    "move_backpack_to_storage_after_non_blue_box": True,
    "post_blue_chest_storage_wait_seconds": 0.8,
    "backpack_to_storage_match_threshold": 0.80,
    "post_storage_click_wait_seconds": 0.8,
    "auto_switch_stash_when_full": True,
    "max_stash_pages_to_scan": 4,
    "stash_tab_match_threshold": 0.80,
    "storage_anchor_match_threshold": 0.80,
    "stash_last_slot_blank_threshold": 0.85,
    "stash_last_slot_uncertain_margin": 0.05,
    "stash_switch_wait_seconds": 0.6,
    "storage_anchor_template": "templates/general/anchor_storage.png",
    "stash_sort_template": "templates/general/stash_sort.png",
    "sort_stash_before_full_check": True,
    "post_stash_sort_wait_seconds": 0.4,
    "stash_blank_template": "templates/general/blank.png",
    "stash_tab_templates": {
        "stash_1": "templates/general/stash_1.png",
        "stash_2": "templates/general/stash_2.png",
        "stash_3": "templates/general/stash_3.png",
        "stash_4": "templates/general/stash_4.png",
    },
    "storage_stash_search_region": "hero_panel",
    "stash_last_slot_anchor_offset_x": -9,
    "stash_last_slot_anchor_offset_y": -55,
    "stash_last_slot_width": 38,
    "stash_last_slot_height": 38,
    "storage_grid_anchor_offset_x": -249,
    "storage_grid_anchor_offset_y": -295,
    "storage_grid_slot_width": 38,
    "storage_grid_slot_height": 38,
    "storage_grid_slot_gap_x": 2,
    "storage_grid_slot_gap_y": 2,
    "storage_grid_rows": 7,
    "storage_grid_cols": 7,
    "always_save_storage_diagnostics_on_failure": True,
    "input_control_mode": "normal",
    "force_game_window_before_action": False,
    "max_input_retries": 3,
    "thresholds": {
        "chest_match": None,
        "chapter_tab_candidate": None,
        "chapter_match": None,
        "difficulty": None,
        "level_dot_white": None,
        "level_dot_green": None,
        "boss_warning": None,
        "clear_match": None,
        "current_level_detection": None,
    },
}

RECOGNITION_MODES = ("safe", "balanced", "aggressive")

LEGACY_DEFAULT_THRESHOLDS = {
    "chest_match": 0.80,
    "chapter_tab_candidate": 0.80,
    "clear_match": 0.85,
    "current_level_detection": 0.85,
}

RECOGNITION_THRESHOLD_PROFILES = {
    "safe": {
        "difficulty_anchor_accept": 0.85,
        "difficulty_tab_accept": 0.88,
        "torment_tab_candidate": 0.70,
        "chapter_selected_accept": 0.83,
        "chapter_candidate_click": 0.83,
        "chapter_verify_accept": 0.83,
        "level_strong_accept": 0.88,
        "level_cautious_accept": 0.86,
        "white_dot_accept": 0.85,
        "green_dot_after_click_accept": 0.80,
        "clear_accept": 0.85,
        "boss_warning_accept": 0.90,
        "blue_chest_accept": 0.88,
        "blue_chest_with_log_accept": 0.85,
        "brown_chest_accept": 0.85,
        "chest_match": 0.80,
        "late_blue_wait_seconds": 3.0,
    },
    "balanced": {
        "difficulty_anchor_accept": 0.80,
        "difficulty_tab_accept": 0.85,
        "torment_tab_candidate": 0.65,
        "chapter_selected_accept": 0.80,
        "chapter_candidate_click": 0.80,
        "chapter_verify_accept": 0.80,
        "level_strong_accept": 0.88,
        "level_cautious_accept": 0.84,
        "white_dot_accept": 0.82,
        "green_dot_after_click_accept": 0.78,
        "clear_accept": 0.85,
        "boss_warning_accept": 0.90,
        "blue_chest_accept": 0.88,
        "blue_chest_with_log_accept": 0.82,
        "brown_chest_accept": 0.85,
        "chest_match": 0.80,
        "late_blue_wait_seconds": 3.0,
    },
    "aggressive": {
        "difficulty_anchor_accept": 0.78,
        "difficulty_tab_accept": 0.82,
        "torment_tab_candidate": 0.62,
        "chapter_selected_accept": 0.78,
        "chapter_candidate_click": 0.78,
        "chapter_verify_accept": 0.78,
        "level_strong_accept": 0.88,
        "level_cautious_accept": 0.82,
        "level_ignore_below": 0.80,
        "white_dot_accept": 0.80,
        "green_dot_after_click_accept": 0.75,
        "clear_accept": 0.85,
        "boss_warning_accept": 0.88,
        "blue_chest_accept": 0.88,
        "blue_chest_with_log_accept": 0.80,
        "brown_chest_accept": 0.85,
        "chest_match": 0.80,
        "late_blue_wait_seconds": 5.0,
    },
}

THRESHOLD_PROFILE_ALIASES = {
    "chest_match": "chest_match",
    "chapter_tab_candidate": "chapter_candidate_click",
    "chapter_match": "chapter_verify_accept",
    "difficulty": "difficulty_anchor_accept",
    "level_dot_white": "white_dot_accept",
    "level_dot_green": "green_dot_after_click_accept",
    "boss_warning": "boss_warning_accept",
    "clear_match": "clear_accept",
    "current_level_detection": "level_strong_accept",
}

CONFIG_FILE_NAME = "config.json"
_CONFIG_CACHE = None


def get_base_dir():
    """
    Return the directory where user-editable files should live.

    In source runs this is the project/script directory. In PyInstaller builds
    this is the executable directory, so config.json stays beside the .exe.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent

    return Path(__file__).resolve().parent


def _merge_dicts(defaults, overrides):
    merged = copy.deepcopy(defaults)

    for key, value in overrides.items():
        if (
            isinstance(value, dict)
            and isinstance(merged.get(key), dict)
        ):
            merged[key] = _merge_dicts(merged[key], value)
        else:
            merged[key] = value

    return merged


def _write_default_config(config_path):
    with config_path.open("w", encoding="utf-8") as f:
        json.dump(DEFAULT_CONFIG, f, indent=4)
        f.write("\n")


def load_config():
    """
    Load config.json, creating it from defaults when missing.

    Invalid JSON is reported clearly and defaults are returned so optional
    configuration problems do not stop the bot from starting.
    """
    config_path = get_base_dir() / CONFIG_FILE_NAME
    _record_config_load_message(f"Config path: {config_path}")

    if not config_path.exists():
        _write_default_config(config_path)
        _record_config_load_message("Default config.json created.")
        return copy.deepcopy(DEFAULT_CONFIG)

    try:
        with config_path.open("r", encoding="utf-8") as f:
            user_config = json.load(f)
    except json.JSONDecodeError as e:
        _record_config_load_message(
            "Invalid config.json detected: "
            f"{e.msg} at line {e.lineno}, column {e.colno}. "
            "Using built-in defaults for this run."
        )
        return copy.deepcopy(DEFAULT_CONFIG)
    except OSError as e:
        _record_config_load_message(f"Could not read config.json: {e}. Using built-in defaults for this run.")
        return copy.deepcopy(DEFAULT_CONFIG)

    if not isinstance(user_config, dict):
        _record_config_load_message("Invalid config.json detected: root value must be an object. Using built-in defaults for this run.")
        return copy.deepcopy(DEFAULT_CONFIG)

    merged = _merge_dicts(DEFAULT_CONFIG, user_config)

    if (
        "default_no_chest_retries" not in user_config
        and "default_max_trials_if_no_chest" in user_config
    ):
        try:
            old_total_clears = int(user_config["default_max_trials_if_no_chest"])
            merged["default_no_chest_retries"] = max(0, old_total_clears - 1)
        except (TypeError, ValueError):
            pass

    _record_config_load_message("config.json loaded successfully.")
    return merged


def get_config():
    global _CONFIG_CACHE

    if _CONFIG_CACHE is None:
        _CONFIG_CACHE = load_config()

    return _CONFIG_CACHE


def get_recognition_mode():
    mode = str(get_config().get("recognition_mode", "balanced")).strip().lower()

    if mode in {"compatibility", "aggressive_compatibility", "aggressive / compatibility"}:
        return "aggressive"

    if mode not in RECOGNITION_MODES:
        return "balanced"

    return mode


def get_profile_threshold(name, default=None):
    mode = get_recognition_mode()
    profile = RECOGNITION_THRESHOLD_PROFILES.get(mode, RECOGNITION_THRESHOLD_PROFILES["balanced"])
    profile_key = THRESHOLD_PROFILE_ALIASES.get(name, name)
    return profile.get(profile_key, default)


def get_effective_thresholds():
    mode = get_recognition_mode()
    profile = RECOGNITION_THRESHOLD_PROFILES.get(mode, RECOGNITION_THRESHOLD_PROFILES["balanced"])
    effective = dict(profile)

    for alias_name, profile_key in THRESHOLD_PROFILE_ALIASES.items():
        effective[alias_name] = profile.get(profile_key)

    thresholds = get_config().get("thresholds", {})

    if isinstance(thresholds, dict):
        for name, value in thresholds.items():
            if value is None:
                continue

            legacy_default = LEGACY_DEFAULT_THRESHOLDS.get(name)

            if legacy_default is not None and value == legacy_default:
                continue

            effective[name] = value

    return effective


def get_threshold(name, default=None):
    thresholds = get_config().get("thresholds", {})

    if not isinstance(thresholds, dict):
        thresholds = {}

    value = thresholds.get(name, default)

    if value is None:
        return get_profile_threshold(name, default)

    legacy_default = LEGACY_DEFAULT_THRESHOLDS.get(name)

    if legacy_default is not None and value == legacy_default:
        return get_profile_threshold(name, default)

    return value
