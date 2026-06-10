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
from detector import load_template, detect_chests_in_region, detect_boss_warning_pixels, match_template, detect_blue_text_pixels
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
)
import pyautogui
import win32gui
import json
import os
import win32con
import win32api

def env_flag(name, default=False):
    value = os.environ.get(name)

    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "on"}


##Parameters For Test Purpose##
WINDOW_KEYWORD = "TaskBarHero"
USE_BACKGROUND_INPUT = os.environ.get("MAATBH_INPUT_MODE", "foreground").lower() == "background"
ENABLE_CLICKING = False
AUTO_OPEN_CONFIRMED_BLUE_CHEST = env_flag("MAATBH_AUTO_OPEN_BLUE", True)
SHOW_PREVIEW = env_flag("MAATBH_SHOW_PREVIEW", False)
NAVIGATE_ON_START = env_flag("MAATBH_NAVIGATE_ON_START", True)
STARTUP_NAV_RETRY_SECONDS = 5.0
MANUAL_NAV_COOLDOWN_SECONDS = 2.0
CHAPTER_TAB_CANDIDATE_THRESHOLD = 0.80
CHAPTER_TAB_CLUSTER_X_TOLERANCE = 32
CHAPTER_TAB_CLUSTER_Y_TOLERANCE = 22


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
STATE_LOOK_FOR_BOSS = "look_for_boss"
STATE_LOOK_FOR_BLUE_DROP = "look_for_blue_drop"

bot_state = STATE_LOOK_FOR_BOSS
freeze_start_time = time.time()
FREEZE_SECONDS_AFTER_SWITCH = 5
POST_BOSS_DROP_WINDOW_SECONDS = 45
ORPHAN_BLUE_RECOVERY_SECONDS = 8

boss_seen_this_route = False
blue_drop_handled_this_route = False

MATCH_THRESHOLD = 0.80
BLUE_ALERT_COOLDOWN_SECONDS = 10
BROWN_LOG_COOLDOWN_SECONDS = 10
NO_CHEST_RESET_SECONDS = 2
last_boss_log_time = 0
BOSS_LOG_COOLDOWN_SECONDS = 5
last_manual_nav_time = 0

last_blue_log_seen_after_boss = 0
last_blue_chest_seen_after_boss = 0
orphan_blue_chest_first_seen = 0
ENABLE_BEEP = env_flag("MAATBH_ENABLE_BEEP", False)
LOG_FILE = "detection_log.txt"

mouse_x = 0
mouse_y = 0
last_blue_alert_time = 0
last_brown_log_time = 0
last_seen_chest_time = 0
last_state = "none"
current_route_index = 0
route_start_time = time.time()

last_route_status_print_time = 0
ROUTE_STATUS_PRINT_INTERVAL = 1.0
GAME_HWND = None
last_bot_status_signature = None


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
    line = f"[{now_str()}] {message}"
    print("\n" + line)

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


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
        print(f"\nLeft click at: x={x}, y={y}")

    elif event == cv2.EVENT_RBUTTONDOWN:
        print(f"\nRight click at: x={x}, y={y}")


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
    save_debug_screenshot(img, folder="debug_screenshots/full", prefix="full")

    for name, region in REGIONS.items():
        cropped = crop(img, region)

        if cropped is not None:
            save_debug_screenshot(
                cropped,
                folder=f"debug_screenshots/{name}",
                prefix=name
            )


def print_detection_summary(detections):
    if not detections:
        print("No chest detected.".ljust(160), end="\r")
        return

    parts = []

    for det in detections:
        parts.append(
            f"{det['type']} {det['confidence']:.2f} "
            f"at {det['center_full']} in {det['region_name']}"
        )

    msg = " | ".join(parts)
    print(msg[:160].ljust(160), end="\r")

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

    boss_seen_this_route = False
    blue_drop_handled_this_route = False

    last_blue_log_seen_after_boss = 0
    last_blue_chest_seen_after_boss = 0
    orphan_blue_chest_first_seen = 0

def handle_confirmed_blue_drop(detections, reason, details):
    """
    Shared action once a blue drop is confirmed by normal or recovery logic.
    """
    global blue_drop_handled_this_route

    blue_drop_handled_this_route = True

    write_log(f"CONFIRMED BLUE DROP | reason={reason} | {details}")

    if ENABLE_BEEP:
        winsound.Beep(1600, 250)
        winsound.Beep(1900, 250)
        winsound.Beep(2200, 250)

    if ENABLE_CLICKING or AUTO_OPEN_CONFIRMED_BLUE_CHEST:
        write_log("Blue drop confirmed. Opening blue chest before route advance.")
        time.sleep(1.0)

        click_success = click_blue_chest_once(GAME_HWND, detections)

        if click_success:
            write_log("Blue chest click completed.")
            time.sleep(0.8)
        else:
            write_log("Blue chest click failed. Route will still advance in dry logic.")
    else:
        write_log("DRY RUN: would click blue chest once.")

    advance_route(do_navigation=True)

    return {
        "state": bot_state,
        "boss_visible": False,
        "blue_chest_visible": False,
        "blue_log_visible": False,
        "message": "Advanced route; freeze started"
    }

def handle_bot_state(img, detections, boss_visible, boss_region, boss_pixels, boss_conf):
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

    current_time = time.time()

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
        blue_chest_visible = any(d["type"] == "blue" for d in detections)
        blue_log_visible, blue_log_region, blue_log_pixels = detect_blue_log(img)

        if blue_chest_visible:
            if orphan_blue_chest_first_seen == 0:
                orphan_blue_chest_first_seen = current_time
                write_log(
                    "Blue chest visible while waiting for boss. "
                    "Treating as possible orphan drop."
                )

            orphan_elapsed = current_time - orphan_blue_chest_first_seen

            if blue_log_visible or orphan_elapsed >= ORPHAN_BLUE_RECOVERY_SECONDS:
                reason = "orphan_blue_with_log" if blue_log_visible else "orphan_blue_stable"
                details = (
                    f"blue_log_visible={blue_log_visible} | "
                    f"log_region={blue_log_region} | "
                    f"blue_pixels={blue_log_pixels} | "
                    f"visible_seconds={orphan_elapsed:.1f}"
                )
                return handle_confirmed_blue_drop(detections, reason, details)
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
                else "Possible orphan blue chest; waiting for blue log or stable recovery"
            )
        }

    # State 3: Look for blue drop only
    if bot_state == STATE_LOOK_FOR_BLUE_DROP:
        blue_chest_visible = any(d["type"] == "blue" for d in detections)
        blue_log_visible, blue_log_region, blue_log_pixels = detect_blue_log(img)

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

        return {
            "state": bot_state,
            "boss_visible": False,
            "blue_chest_visible": blue_chest_visible,
            "blue_log_visible": blue_log_visible,
            "message": (
                f"Looking for blue drop | "
                f"chest_recent={blue_chest_recent} | "
                f"log_recent={blue_log_recent}"
            )
        }

    return {
        "state": bot_state,
        "boss_visible": False,
        "blue_chest_visible": False,
        "blue_log_visible": False,
        "message": "Unknown state"
    }

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

    window_left, window_top, _, _ = win32gui.GetWindowRect(hwnd)

    screen_x = window_left + local_x
    screen_y = window_top + local_y

    write_log(
        f"Clicking blue chest | "
        f"mouse_before=({mouse_before_x}, {mouse_before_y}) | "
        f"local=({local_x}, {local_y}) | "
        f"screen=({screen_x}, {screen_y}) | "
        f"blue_box=({blue_left},{blue_top})-({blue_right},{blue_bottom}) | "
        f"confidence={best_blue['confidence']:.2f}"
    )

    try:
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.2)
    except Exception as e:
        write_log(f"Window focus warning: {e}")

    pyautogui.moveTo(screen_x, screen_y, duration=0.15)

    pyautogui.click(screen_x, screen_y)
    time.sleep(0.35)

    pyautogui.click(screen_x, screen_y)
    time.sleep(0.2)

    pyautogui.click(screen_x, screen_y)

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

    print(
        "\n"
        f"Bot state: {bot_info['state']} | "
        f"Boss: {bot_info['boss_visible']} | "
        f"Blue chest: {bot_info['blue_chest_visible']} | "
        f"Blue log: {bot_info['blue_log_visible']} | "
        f"{bot_info['message']}"
    )

def detect_level_in_map(img, level_template, threshold=LEVEL_MATCH_THRESHOLD):
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
    map_img = crop(img, REGIONS["map_panel"])

    if map_img is None:
        return False, None, 0.0

    match = match_template(map_img, level_template)
    confidence = match["confidence"]

    map_x1, map_y1, _, _ = REGIONS["map_panel"]

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


def background_click_window_point(hwnd, local_x, local_y, label=""):
    """
    Send a background click to the game window without moving the real mouse.
    """
    client_x, client_y, screen_x, screen_y = local_to_client(hwnd, local_x, local_y)
    lparam = make_lparam(client_x, client_y)

    write_log(
        f"Background click | label={label} | "
        f"local=({local_x}, {local_y}) | "
        f"client=({client_x}, {client_y}) | "
        f"screen=({screen_x}, {screen_y})"
    )

    win32gui.PostMessage(hwnd, win32con.WM_MOUSEMOVE, 0, lparam)
    time.sleep(0.05)

    win32gui.PostMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lparam)
    time.sleep(0.08)

    win32gui.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, lparam)
    time.sleep(NAV_CLICK_DELAY_SECONDS)

    return True


def background_scroll_window_point(hwnd, local_x, local_y, direction, repeat):
    """
    Send background mouse wheel messages to the game window.
    Does not move the real mouse.
    """
    client_x, client_y, screen_x, screen_y = local_to_client(hwnd, local_x, local_y)

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
        f"local=({local_x}, {local_y}) | "
        f"client=({client_x}, {client_y}) | "
        f"screen=({screen_x}, {screen_y}) | repeat={repeat}"
    )

    for _ in range(repeat):
        win32gui.PostMessage(hwnd, win32con.WM_MOUSEWHEEL, wparam, lparam)
        time.sleep(0.04)

    time.sleep(0.5)
    return True

def click_window_point(hwnd, local_x, local_y, label=""):
    """
    Click a point using local captured-window coordinates.
    Uses either real mouse or background window message depending on settings.
    """
    if USE_BACKGROUND_INPUT:
        return background_click_window_point(hwnd, local_x, local_y, label=label)

    window_left, window_top, _, _ = win32gui.GetWindowRect(hwnd)

    screen_x = window_left + local_x
    screen_y = window_top + local_y

    write_log(
        f"Click window point | label={label} | "
        f"local=({local_x}, {local_y}) | screen=({screen_x}, {screen_y})"
    )

    try:
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.2)
    except Exception as e:
        write_log(f"Window focus warning: {e}")

    pyautogui.moveTo(screen_x, screen_y, duration=0.12)
    pyautogui.click(screen_x, screen_y)

    time.sleep(NAV_CLICK_DELAY_SECONDS)
    return True
    
def scroll_map(hwnd, direction, repeat=None):
    """
    Scroll inside the map panel from a dynamic safe point.

    direction: 'up' or 'down'
    repeat: number of wheel scroll pulses
    """
    if repeat is None:
        repeat = MAP_SCROLL_CHUNK_REPEAT

    x1, y1, x2, y2 = REGIONS["map_panel"]

    map_w = x2 - x1
    map_h = y2 - y1

    # Dynamic safe point inside map panel.
    # Slightly right of center, away from map edge.
    local_x = int(x1 + 0.65 * map_w)
    local_y = int(y1 + 0.50 * map_h)
    if USE_BACKGROUND_INPUT:
        return background_scroll_window_point(
            hwnd,
            local_x,
            local_y,
            direction=direction,
            repeat=repeat
        )
    window_left, window_top, _, _ = win32gui.GetWindowRect(hwnd)

    screen_x = window_left + local_x
    screen_y = window_top + local_y

    try:
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.2)
    except Exception as e:
        write_log(f"Window focus warning before scroll: {e}")

    pyautogui.moveTo(screen_x, screen_y, duration=0.15)
    time.sleep(0.1)

    # Focus map panel before scrolling.
    pyautogui.click(screen_x, screen_y)
    time.sleep(0.15)

    if direction == "up":
        amount = 8
    else:
        amount = -8

    for _ in range(repeat):
        try:
            pyautogui.scroll(amount)
        except pyautogui.FailSafeException:
            write_log(
                "SCROLL ABORTED: PyAutoGUI fail-safe triggered. "
                "Move mouse away from screen corners."
            )
            return False

        time.sleep(0.04)

    write_log(
        f"Scrolled map {direction} | "
        f"scroll_point_local=({local_x}, {local_y}) | "
        f"scroll_point_screen=({screen_x}, {screen_y}) | "
        f"repeat={repeat}"
    )

    time.sleep(0.5)
    return True

def find_level_dot_left_of_text(img, match_info, dot_template, threshold, dot_name="dot"):
    """
    Search for a dot state, white or green, immediately to the left of detected level text.
    """
    text_left, text_top = match_info["top_left_full"]
    text_right, text_bottom = match_info["bottom_right_full"]
    text_w, text_h = match_info["size"]

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

    match = match_template(search_img, dot_template)
    confidence = match["confidence"]

    dot_center_x, dot_center_y = match["center"]

    dot_center_full = (
        search_x1 + dot_center_x,
        search_y1 + dot_center_y
    )

    write_log(
        f"DOT SEARCH DEBUG | type={dot_name} | "
        f"text_box=({text_left},{text_top})-({text_right},{text_bottom}) | "
        f"search_box=({search_x1},{search_y1})-({search_x2},{search_y2}) | "
        f"best_dot=({dot_center_full[0]}, {dot_center_full[1]}) | "
        f"confidence={confidence:.2f} | threshold={threshold:.2f}"
    )

    if confidence < threshold:
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
        click_window_point(hwnd, white_center[0], white_center[1], label=f"level_dot_{route['level']}")
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
            return True

        write_log(
            f"NAV WARNING: clicked white dot but green verification failed | "
            f"route={route['level']} | green_conf_after={green_conf_after:.2f}"
        )
        return False

    else:
        write_log(
            f"DRY RUN NAV: would click white dot for level {route['level']} "
            f"at local={white_center}"
        )
        return True

def level_match_passes_expected_y(route, match_info, context):
    center_x, center_y = match_info["center_full"]
    expected_y_min = route.get("expected_y_min", None)
    expected_y_max = route.get("expected_y_max", None)

    if expected_y_min is not None and center_y < expected_y_min:
        write_log(
            f"NAV rejected level {route['level']} by Y position | "
            f"context={context} | "
            f"center_y={center_y} < expected_y_min={expected_y_min} | "
            f"confidence={match_info['confidence']:.2f}"
        )
        return False

    if expected_y_max is not None and center_y > expected_y_max:
        write_log(
            f"NAV rejected level {route['level']} by Y position | "
            f"context={context} | "
            f"center_y={center_y} > expected_y_max={expected_y_max} | "
            f"confidence={match_info['confidence']:.2f}"
        )
        return False

    return True

def try_current_visible_level(hwnd, route, level_template, threshold, context):
    """
    Check the current map view before scrolling.
    Returns True/False when the target is visible, None when not visible.
    """
    img = capture_window(hwnd)

    found, match_info, confidence = detect_level_in_map(
        img,
        level_template,
        threshold=threshold
    )

    if not found:
        write_log(
            f"NAV current view: level not visible | "
            f"route={route['level']} | context={context} | "
            f"best_confidence={confidence:.2f} | threshold={threshold:.2f}"
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
    return ROUTE[current_route_index]


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

    return confidence >= threshold, match_info["center_full"], confidence, match_info

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

    return best_chapter, best_center, best_confidence, best_info

def find_chapter_tab_candidate(img, target_chapter):
    """
    Resolve chapter tabs by clustering all normal-tab template candidates.
    The chosen target must be the strongest chapter identity in its cluster.
    """
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

    summary = " | ".join(
        f"{item['chapter']}@{item['center']}:{item['confidence']:.2f}"
        for item in resolved
    )
    write_log(f"Chapter tab candidates | target={target_chapter} | {summary}")

    for item in resolved:
        if item["chapter"] == target_chapter and item["confidence"] >= CHAPTER_MATCH_THRESHOLD:
            return True, item["center"], item["confidence"], item

    return False, None, 0.0, {"resolved": resolved}

def select_difficulty(hwnd, difficulty):
    """
    Select difficulty using:
    - anchor template: currently selected difficulty button / dropdown opener
    - tab template: option inside opened dropdown
    """
    if difficulty not in DIFFICULTY_TEMPLATES:
        write_log(f"NAV FAILED: unknown difficulty {difficulty}")
        return False

    templates = DIFFICULTY_TEMPLATES[difficulty]

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
        save_debug_screenshot(
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

    click_window_point(
        hwnd,
        current_anchor_center[0],
        current_anchor_center[1],
        label="difficulty_anchor_open"
    )

    time.sleep(0.5)

    # 3. After dropdown opens, find target difficulty tab.
    img_dropdown = capture_window(hwnd)

    found_tab, tab_center, tab_conf, _ = find_template_in_box(
        img_dropdown,
        templates["tab"],
        REGIONS["map_panel"],
        DIFFICULTY_MATCH_THRESHOLD,
        label=f"difficulty_dropdown_{difficulty}"
    )

    if not found_tab:
        save_debug_screenshot(
            img_dropdown,
            folder="debug_screenshots/nav_failures",
            prefix=f"difficulty_tab_fail_{difficulty}"
        )

        write_log(
            f"NAV FAILED: target difficulty tab not found after opening dropdown | "
            f"target={difficulty} | tab_confidence={tab_conf:.2f} | "
            f"search_region=map_panel"
        )
        return False

    write_log(
        f"Clicking difficulty tab | difficulty={difficulty} | "
        f"center={tab_center} | confidence={tab_conf:.2f}"
    )

    click_window_point(
        hwnd,
        tab_center[0],
        tab_center[1],
        label=f"difficulty_tab_{difficulty}"
    )

    time.sleep(0.8)

    # 4. Verify target anchor after selecting.
    img_after = capture_window(hwnd)
    verified_name, verified_center, anchor_conf_after, _ = find_best_difficulty_anchor(img_after)

    if verified_name == difficulty and anchor_conf_after >= DIFFICULTY_MATCH_THRESHOLD:
        write_log(
            f"Difficulty verified | difficulty={difficulty} | "
            f"anchor_confidence={anchor_conf_after:.2f} | center={verified_center}"
        )
        return True

    write_log(
        f"NAV WARNING: difficulty tab clicked but anchor verification failed | "
        f"target={difficulty} | verified_anchor={verified_name} | "
        f"anchor_confidence={anchor_conf_after:.2f}"
    )

    return False

def select_chapter(hwnd, chapter):
    """
    Click chapter tab and verify selected chapter template.
    """
    if chapter not in CHAPTER_TEMPLATES:
        write_log(f"NAV FAILED: unknown chapter {chapter}")
        return False

    img = capture_window(hwnd)
    current_chapter, selected_center, selected_conf, _ = find_current_chapter(img)

    write_log(
        f"Chapter visual state | target={chapter} | "
        f"current={current_chapter} | selected_center={selected_center} | "
        f"selected_confidence={selected_conf:.2f}"
    )

    # 1. If target chapter is already selected, no click is needed.
    if current_chapter == chapter and selected_conf >= CHAPTER_MATCH_THRESHOLD:
        write_log(
            f"Chapter already selected | chapter={chapter} | "
            f"confidence={selected_conf:.2f} | center={selected_center}"
        )
        return True

    # 2. Find the target chapter's visible unselected tab inside map_panel.
    found_tab, tab_center, tab_conf, _ = find_chapter_tab_candidate(
        img,
        chapter
    )

    if not found_tab:
        save_debug_screenshot(
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

    click_window_point(hwnd, tab_center[0], tab_center[1], label=chapter)
    time.sleep(0.8)

    # 3. Verify selected chapter.
    img_after = capture_window(hwnd)
    verified_chapter, selected_center_after, selected_conf_after, _ = find_current_chapter(img_after)

    if verified_chapter == chapter and selected_conf_after >= CHAPTER_MATCH_THRESHOLD:
        write_log(
            f"Chapter verified | chapter={chapter} | "
            f"confidence={selected_conf_after:.2f} | center={selected_center_after}"
        )
        return True

    write_log(
        f"NAV WARNING: chapter click done but verification failed | "
        f"target={chapter} | verified={verified_chapter} | "
        f"center={selected_center_after} | confidence={selected_conf_after:.2f}"
    )

    save_debug_screenshot(
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

def navigate_to_current_route_if_enabled(activate_boss_gate=False):
    global bot_state

    route = get_current_route()

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
        return False

    success = find_and_click_level_by_template(GAME_HWND, route)

    if success:
        write_log(f"Route navigation completed for {route['name']} | {route['level']}")

        if activate_boss_gate:
            reset_route_detection_memory()
            bot_state = STATE_LOOK_FOR_BOSS
            write_log("Manual navigation completed. Now looking for boss warning.")
    else:
        write_log(f"Route navigation FAILED for {route['name']} | {route['level']}")

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

    bot_state = STATE_STARTUP_NAVIGATION
    write_log(
        f"Startup navigation failed. Will retry in "
        f"{STARTUP_NAV_RETRY_SECONDS:.0f}s and ignore chest/boss decisions until it succeeds."
    )
    return False

def advance_route(do_navigation=False):
    """
    Move to the next route.

    If do_navigation=True, visually navigate to the new route's target level
    before entering freeze.
    """
    global current_route_index, route_start_time
    global bot_state, freeze_start_time

    current_route_index = (current_route_index + 1) % len(ROUTE)
    route_start_time = time.time()

    reset_route_detection_memory()

    route = get_current_route()

    write_log(
        f"Advanced to {route['name']} | "
        f"{route['difficulty']} | {route['chapter']} | {route['level']}"
    )

    if do_navigation:
        time.sleep(1.0)
        navigate_to_current_route_if_enabled()

    bot_state = STATE_FREEZE_AFTER_SWITCH
    freeze_start_time = time.time()

    write_log("Entering freeze window.")

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
        BOSS_WARNING_CONFIDENCE_THRESHOLD = 0.85
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

    threshold = route.get("level_match_threshold", LEVEL_MATCH_THRESHOLD)
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

    for direction in search_order:
        for chunk_index in range(MAP_SCROLL_CHUNKS_PER_DIRECTION):
            scroll_ok = scroll_map(
                hwnd,
                direction,
                repeat=MAP_SCROLL_CHUNK_REPEAT
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
        f"NAV FAILED: could not find level {route['level']} | "
        f"search_order={search_order}"
    )

    return False

def load_farm_plan(default_route):
    plan_path = "farm_plan.json"

    if not os.path.exists(plan_path):
        print("farm_plan.json not found. Using default ROUTE.")
        return default_route

    try:
        with open(plan_path, "r", encoding="utf-8") as f:
            plan = json.load(f)

        if not plan:
            print("farm_plan.json is empty. Using default ROUTE.")
            return default_route

        print(f"Loaded farm plan from {plan_path}: {len(plan)} routes.")
        return plan

    except Exception as e:
        print(f"Failed to load farm_plan.json: {e}")
        print("Using default ROUTE.")
        return default_route
ROUTE = load_farm_plan(ROUTE)

def main():
    global last_boss_log_time
    global last_manual_nav_time
    last_boss_log_time = 0
    hwnd, title = find_window_by_title_keyword(WINDOW_KEYWORD)
    global GAME_HWND
    GAME_HWND = hwnd
    if hwnd is None:
        print(f"Could not find a window containing: {WINDOW_KEYWORD}")
        print("Make sure TaskBarHero is open.")
        return

    print(f"Found window: {title}")
    print(f"Input mode: {'background PostMessage' if USE_BACKGROUND_INPUT else 'foreground mouse'}")
    print(f"Preview window: {'on' if SHOW_PREVIEW else 'off'}")
    print(f"Beep: {'on' if ENABLE_BEEP else 'off'}")
    print(f"Navigate on start: {'on' if NAVIGATE_ON_START else 'off'}")

    print("Loading templates...")

    # Your actual template file names:
    blue_template = load_template("templates/general/chest_blue.png")
    brown_template = load_template("templates/general/chest_brown.png")
    boss_warning_template = load_template("templates/general/boss_warning_text.png")
    print("Templates loaded.")
    print()
    print("Controls:")
    print("  Move mouse over preview = show coordinate")
    print("  Left click / Right click = print coordinate")
    print("  S = save full screenshot")
    print("  C = save full screenshot + all region crops")
    print("  Q = quit")
    print("  N = next route")
    print("  R = reset route timer")
    print("  V = visual nav test current route")
    print()
    print(f"Template match threshold: {MATCH_THRESHOLD}")
    print()

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
            not startup_navigation_done
            and current_time - last_startup_nav_attempt_time >= STARTUP_NAV_RETRY_SECONDS
        ):
            last_startup_nav_attempt_time = current_time
            startup_navigation_done = navigate_to_startup_route()
            last_startup_nav_attempt_time = time.time()
            current_time = last_startup_nav_attempt_time

        img = capture_window(hwnd)

        detections = detect_all_chests(img, blue_template, brown_template)

        boss_visible, boss_region, boss_pixels, boss_conf = detect_boss_warning(
            img,
            boss_warning_template
        )

        if startup_navigation_done:
            chest_state = handle_chest_events(detections)

            bot_info = handle_bot_state(
                img,
                detections,
                boss_visible,
                boss_region,
                boss_pixels,
                boss_conf
            )
        else:
            chest_state = "startup_navigation"
            bot_info = {
                "state": bot_state,
                "boss_visible": False,
                "blue_chest_visible": False,
                "blue_log_visible": False,
                "message": "Waiting for startup route navigation"
            }

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
            save_debug_screenshot(
                img,
                folder="debug_screenshots/full",
                prefix="full"
            )
    
        elif key == ord("c"):
            save_all_regions(img)

        elif key == ord("q"):
            break
        elif key == ord("n"):
            advance_route(do_navigation=False)
            write_log("Manual route advance triggered.")
        elif key == ord("r"):
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

if __name__ == "__main__":
    main()
