# MAA Task Bar Hero
# Concept and direction by Marcus Xu.
# Built with Codex as a coding assistant.
# Shared for learning, experimentation, and automation research.

import time

import pyautogui
import win32api
import win32con
import win32gui


class InputController:
    """
    Mouse, keyboard, and window-input behavior.

    Detection and route decisions stay in runner.py. This class owns the
    low-level coordinate conversion, safe foreground input, background window
    messages, scrolling, and mouse parking mechanics.
    """

    def __init__(
        self,
        *,
        write_log,
        capture_window,
        safe_window_rect,
        safe_client_rect,
        safe_client_origin,
        format_diag_value,
        get_config,
        get_game_hwnd,
        regions,
        use_background_input,
        nav_click_delay_seconds,
        map_scroll_chunk_repeat,
        fast_scroll_use_burst,
        fast_scroll_burst_count,
        coordinate_scaling_enabled,
        coordinate_scaling_auto_detect,
        coordinate_scaling_tolerance,
        pause_on_severe_coordinate_mismatch,
        mouse_fail_safe_margin_px,
        mouse_parking_enabled,
        mouse_parking_x,
        mouse_parking_y,
        mouse_parking_wait_seconds,
        mouse_parking_mode,
        mouse_parking_static_x,
        mouse_parking_static_y,
        mouse_parking_fail_safe_relocate_enabled,
        mouse_parking_fail_safe_min_screen_margin_px,
        mouse_parking_fallback_static_x,
        mouse_parking_fallback_static_y,
    ):
        self.write_log = write_log
        self.capture_window = capture_window
        self.safe_window_rect = safe_window_rect
        self.safe_client_rect = safe_client_rect
        self.safe_client_origin = safe_client_origin
        self.format_diag_value = format_diag_value
        self.get_config = get_config
        self.get_game_hwnd = get_game_hwnd
        self.regions = regions
        self.use_background_input = use_background_input
        self.nav_click_delay_seconds = nav_click_delay_seconds
        self.map_scroll_chunk_repeat = map_scroll_chunk_repeat
        self.fast_scroll_use_burst = fast_scroll_use_burst
        self.fast_scroll_burst_count = fast_scroll_burst_count
        self.coordinate_scaling_enabled = coordinate_scaling_enabled
        self.coordinate_scaling_auto_detect = coordinate_scaling_auto_detect
        self.coordinate_scaling_tolerance = coordinate_scaling_tolerance
        self.pause_on_severe_coordinate_mismatch = pause_on_severe_coordinate_mismatch
        self.mouse_fail_safe_margin_px = mouse_fail_safe_margin_px
        self.mouse_parking_enabled = mouse_parking_enabled
        self.mouse_parking_x = mouse_parking_x
        self.mouse_parking_y = mouse_parking_y
        self.mouse_parking_wait_seconds = mouse_parking_wait_seconds
        self.mouse_parking_mode = mouse_parking_mode
        self.mouse_parking_static_x = mouse_parking_static_x
        self.mouse_parking_static_y = mouse_parking_static_y
        self.mouse_parking_fail_safe_relocate_enabled = mouse_parking_fail_safe_relocate_enabled
        self.mouse_parking_fail_safe_min_screen_margin_px = mouse_parking_fail_safe_min_screen_margin_px
        self.mouse_parking_fallback_static_x = mouse_parking_fallback_static_x
        self.mouse_parking_fallback_static_y = mouse_parking_fallback_static_y
        self.coordinate_scaling_status = None

    def move_to(self, screen_x, screen_y, duration=0.05):
        pyautogui.moveTo(screen_x, screen_y, duration=duration)

    def click(self, screen_x, screen_y):
        pyautogui.click(screen_x, screen_y)

    def scroll(self, amount):
        pyautogui.scroll(amount)

    def press(self, key):
        pyautogui.press(key)

    def hotkey(self, *keys):
        pyautogui.hotkey(*keys)

    def position(self):
        return pyautogui.position()

    def screen_size(self):
        return pyautogui.size()

    def wait(self, seconds):
        time.sleep(seconds)

    def focus_window(self, hwnd, warning_message="Window focus warning", wait_seconds=0.2):
        try:
            win32gui.SetForegroundWindow(hwnd)
            time.sleep(wait_seconds)
            return True
        except Exception as e:
            self.write_log(f"{warning_message}: {e}")
            return False

    def make_lparam(self, x, y):
        """
        Pack x, y into a Win32 LPARAM.
        """
        return (y << 16) | (x & 0xFFFF)

    def local_to_screen(self, hwnd, local_x, local_y):
        """
        Convert captured-window local coordinates to screen coordinates.
        This matches the existing pyautogui click behavior.
        """
        window_left, window_top, _, _ = win32gui.GetWindowRect(hwnd)
        return window_left + local_x, window_top + local_y

    def local_to_client(self, hwnd, local_x, local_y):
        """
        Convert captured-window local coordinates into client coordinates
        for Win32 mouse messages.
        """
        screen_x, screen_y = self.local_to_screen(hwnd, local_x, local_y)
        client_x, client_y = win32gui.ScreenToClient(hwnd, (screen_x, screen_y))
        return client_x, client_y, screen_x, screen_y

    def get_client_screen_point(self, hwnd, client_x, client_y):
        try:
            screen_x, screen_y = win32gui.ClientToScreen(hwnd, (int(client_x), int(client_y)))
            return screen_x, screen_y
        except Exception:
            window_left, window_top, _, _ = win32gui.GetWindowRect(hwnd)
            return window_left + int(client_x), window_top + int(client_y)

    def rect_width_height(self, rect):
        if rect is None:
            return None

        return max(0, rect[2] - rect[0]), max(0, rect[3] - rect[1])

    def build_coordinate_scaling_status(self, hwnd, screenshot_size=None, client_size=None, reason="runtime"):
        if not self.coordinate_scaling_enabled:
            return {
                "enabled": False,
                "active": False,
                "reason": "disabled",
                "hwnd": hwnd,
            }

        if not self.coordinate_scaling_auto_detect:
            return {
                "enabled": True,
                "active": False,
                "reason": "auto_detect_disabled",
                "hwnd": hwnd,
            }

        if client_size is None:
            client_size = self.rect_width_height(self.safe_client_rect(hwnd))

        if screenshot_size is None:
            try:
                img = self.capture_window(hwnd)
                height, width = img.shape[:2]
                screenshot_size = (width, height)
            except Exception as e:
                self.write_log(
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
            abs(scale_x - 1.0) > self.coordinate_scaling_tolerance
            or abs(scale_y - 1.0) > self.coordinate_scaling_tolerance
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
            "tolerance": self.coordinate_scaling_tolerance,
        }

    def update_coordinate_scaling_status(self, hwnd, screenshot_size=None, client_size=None, reason="runtime"):
        self.coordinate_scaling_status = self.build_coordinate_scaling_status(
            hwnd,
            screenshot_size=screenshot_size,
            client_size=client_size,
            reason=reason,
        )
        return self.coordinate_scaling_status

    def get_coordinate_scaling_status(self, hwnd):
        if self.coordinate_scaling_status is None or self.coordinate_scaling_status.get("hwnd") != hwnd:
            self.coordinate_scaling_status = self.build_coordinate_scaling_status(hwnd, reason="click")

        return self.coordinate_scaling_status

    def log_coordinate_scaling_status(self, status):
        status = status or {}
        self.write_log(
            "Coordinate scaling status | "
            f"enabled={status.get('enabled', self.coordinate_scaling_enabled)} | "
            f"auto_detect={self.coordinate_scaling_auto_detect} | "
            f"active={status.get('active')} | "
            f"reason={status.get('reason')} | "
            f"screenshot_size={self.format_diag_value(status.get('screenshot_size'))} | "
            f"client_size={self.format_diag_value(status.get('client_size'))} | "
            f"scale_x={status.get('scale_x')} | "
            f"scale_y={status.get('scale_y')} | "
            f"tolerance={self.coordinate_scaling_tolerance} | "
            f"pause_on_severe_mismatch={self.pause_on_severe_coordinate_mismatch}"
        )

    def screenshot_local_to_click_coordinates(self, hwnd, local_x, local_y, label=""):
        status = self.get_coordinate_scaling_status(hwnd)

        if not status.get("active"):
            client_x, client_y, screen_x, screen_y = self.local_to_client(hwnd, local_x, local_y)
            return client_x, client_y, screen_x, screen_y, status

        scale_x = status.get("scale_x", 1.0)
        scale_y = status.get("scale_y", 1.0)
        client_x = int(round(local_x * scale_x))
        client_y = int(round(local_y * scale_y))
        screen_x, screen_y = self.get_client_screen_point(hwnd, client_x, client_y)

        self.write_log(
            f"Coordinate scaling applied | label={label} | "
            f"screenshot_local=({local_x}, {local_y}) | "
            f"client_local=({client_x}, {client_y}) | "
            f"screen=({screen_x}, {screen_y}) | "
            f"scale_x={scale_x:.4f} | scale_y={scale_y:.4f}"
        )

        return client_x, client_y, screen_x, screen_y, status

    def get_virtual_screen_rect(self):
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
            width, height = self.screen_size()
            return 0, 0, width, height
        except Exception:
            return None

    def get_monitor_rect_for_point(self, screen_x, screen_y):
        try:
            monitor = win32api.MonitorFromPoint(
                (int(screen_x), int(screen_y)),
                win32con.MONITOR_DEFAULTTONEAREST,
            )
            info = win32api.GetMonitorInfo(monitor)
            return info.get("Work") or info.get("Monitor")
        except Exception:
            return self.get_virtual_screen_rect()

    def get_monitor_rect_for_window(self, hwnd):
        try:
            monitor = win32api.MonitorFromWindow(
                hwnd,
                win32con.MONITOR_DEFAULTTONEAREST,
            )
            info = win32api.GetMonitorInfo(monitor)
            return info.get("Work") or info.get("Monitor")
        except Exception:
            rect = self.safe_window_rect(hwnd)

            if rect is None:
                return self.get_virtual_screen_rect()

            left, top, right, bottom = rect
            return self.get_monitor_rect_for_point(
                (left + right) // 2,
                (top + bottom) // 2,
            )

    def is_screen_point_fail_safe_risky(self, screen_x, screen_y, margin=None):
        monitor_rect = self.get_monitor_rect_for_point(screen_x, screen_y)

        if monitor_rect is None:
            return False

        left, top, right, bottom = monitor_rect
        margin = self.mouse_fail_safe_margin_px if margin is None else margin

        if screen_x < left or screen_x >= right or screen_y < top or screen_y >= bottom:
            return True

        return (
            screen_x <= left + margin
            or screen_x >= right - margin
            or screen_y <= top + margin
            or screen_y >= bottom - margin
        )

    def clamp_screen_point_to_safe_monitor_area(self, screen_x, screen_y, hwnd=None):
        monitor_rect = (
            self.get_monitor_rect_for_window(hwnd)
            if hwnd is not None
            else self.get_monitor_rect_for_point(screen_x, screen_y)
        )

        if monitor_rect is None:
            return int(screen_x), int(screen_y), None

        left, top, right, bottom = monitor_rect
        margin = self.mouse_fail_safe_margin_px

        if right - left <= margin * 2:
            safe_x = (left + right) // 2
        else:
            safe_x = max(left + margin, min(int(screen_x), right - margin - 1))

        if bottom - top <= margin * 2:
            safe_y = (top + bottom) // 2
        else:
            safe_y = max(top + margin, min(int(screen_y), bottom - margin - 1))

        return safe_x, safe_y, monitor_rect

    def safe_pyautogui_move_to(self, screen_x, screen_y, label="mouse_move", duration=0.05):
        if self.is_screen_point_fail_safe_risky(screen_x, screen_y):
            self.write_log(
                f"Mouse movement failed safely | label={label} | "
                f"reason=fail_safe_risky_point | screen=({screen_x}, {screen_y}) | "
                f"margin={self.mouse_fail_safe_margin_px}"
            )
            return False

        try:
            pyautogui.moveTo(screen_x, screen_y, duration=duration)
            return True
        except pyautogui.FailSafeException:
            self.write_log(
                f"Mouse movement failed safely | label={label} | "
                "reason=pyautogui_failsafe"
            )
            return False
        except Exception as e:
            self.write_log(
                f"Mouse movement failed safely | label={label} | "
                f"reason={e}"
            )
            return False

    def safe_pyautogui_click(self, screen_x, screen_y, label="mouse_click"):
        if self.is_screen_point_fail_safe_risky(screen_x, screen_y):
            self.write_log(
                f"Mouse click failed safely | label={label} | "
                f"reason=fail_safe_risky_point | screen=({screen_x}, {screen_y}) | "
                f"margin={self.mouse_fail_safe_margin_px}"
            )
            return False

        try:
            pyautogui.click(screen_x, screen_y)
            return True
        except pyautogui.FailSafeException:
            self.write_log(
                f"Mouse movement failed safely | label={label} | "
                "reason=pyautogui_failsafe"
            )
            return False
        except Exception as e:
            self.write_log(
                f"Mouse click failed safely | label={label} | "
                f"reason={e}"
            )
            return False

    def safe_pyautogui_scroll(self, amount, label="mouse_scroll"):
        try:
            pyautogui.scroll(amount)
            return True
        except pyautogui.FailSafeException:
            self.write_log(
                f"Mouse movement failed safely | label={label} | "
                "reason=pyautogui_failsafe"
            )
            return False
        except Exception as e:
            self.write_log(
                f"Mouse scroll failed safely | label={label} | "
                f"reason={e}"
            )
            return False

    def screen_to_local(self, hwnd, screen_x, screen_y):
        window_rect = self.safe_window_rect(hwnd)

        if window_rect is None:
            return int(screen_x), int(screen_y)

        window_left, window_top, _, _ = window_rect
        return int(screen_x - window_left), int(screen_y - window_top)

    def get_client_local_bounds(self, hwnd, window_rect):
        client_rect = self.safe_client_rect(hwnd)
        client_origin = self.safe_client_origin(hwnd)

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

    def build_parking_point_from_local(self, hwnd, local_x, local_y, source, confidence=None, path=None):
        screen_x, screen_y = self.local_to_screen(hwnd, local_x, local_y)

        if self.is_screen_point_fail_safe_risky(
            screen_x,
            screen_y,
            margin=self.mouse_parking_fail_safe_min_screen_margin_px,
        ):
            self.write_log(
                f"Mouse parking candidate unsafe near fail-safe edge | "
                f"source={source} | local=({local_x}, {local_y}) | "
                f"screen=({screen_x}, {screen_y}) | "
                f"margin={self.mouse_parking_fail_safe_min_screen_margin_px}"
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

    def make_clamped_client_point(self, local_x, local_y, client_x1, client_y1, client_x2, client_y2):
        return (
            max(client_x1, min(int(local_x), client_x2)),
            max(client_y1, min(int(local_y), client_y2)),
        )

    def get_client_centerish_parking_candidates(self, client_x1, client_y1, client_x2, client_y2):
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

    def choose_safe_mouse_parking_candidate(self, hwnd, candidates, client_bounds):
        client_x1, client_y1, client_x2, client_y2 = client_bounds

        for local_x, local_y, source in candidates:
            local_x, local_y = self.make_clamped_client_point(
                local_x,
                local_y,
                client_x1,
                client_y1,
                client_x2,
                client_y2,
            )
            parking_point = self.build_parking_point_from_local(
                hwnd,
                local_x,
                local_y,
                source,
            )

            if parking_point is None:
                continue

            if source not in {"manual", "static_client_point"}:
                self.write_log(
                    f"Mouse parking relocated away from fail-safe edge | "
                    f"source={source} | local={parking_point['local']} | "
                    f"screen={parking_point['screen']} | "
                    f"margin={self.mouse_parking_fail_safe_min_screen_margin_px}"
                )

            return parking_point

        self.write_log(
            f"Mouse parking skipped; no safe parking candidate | "
            f"candidate_count={len(candidates)} | "
            f"margin={self.mouse_parking_fail_safe_min_screen_margin_px}"
        )
        return None

    def get_monitor_safe_parking_point(self, hwnd, reason):
        window_rect = self.safe_window_rect(hwnd)

        if window_rect is None:
            return None

        x1, y1, x2, y2 = self.regions["map_panel"]
        local_x = int(x1 + 0.50 * (x2 - x1))
        local_y = int(y1 + 0.50 * (y2 - y1))
        screen_x, screen_y = self.local_to_screen(hwnd, local_x, local_y)

        clamped_x, clamped_y, monitor_rect = self.clamp_screen_point_to_safe_monitor_area(
            screen_x,
            screen_y,
            hwnd=hwnd,
        )
        local_x, local_y = self.screen_to_local(hwnd, clamped_x, clamped_y)

        self.write_log(
            f"Mouse parking using monitor-safe fallback | reason={reason} | "
            f"original_screen=({screen_x}, {screen_y}) | "
            f"clamped_screen=({clamped_x}, {clamped_y}) | "
            f"monitor_rect={self.format_diag_value(monitor_rect)}"
        )

        return {
            "local": (int(local_x), int(local_y)),
            "screen": (int(clamped_x), int(clamped_y)),
            "source": "monitor_safe_point",
            "confidence": None,
        }

    def get_default_mouse_parking_point(self, hwnd):
        window_rect = self.safe_window_rect(hwnd)

        if window_rect is None:
            return None

        window_left, window_top, window_right, window_bottom = window_rect
        width = window_right - window_left
        height = window_bottom - window_top
        client_x1, client_y1, client_x2, client_y2 = self.get_client_local_bounds(
            hwnd,
            window_rect,
        )

        if width <= 1 or height <= 1:
            return None

        client_bounds = (client_x1, client_y1, client_x2, client_y2)
        candidates = []

        if self.mouse_parking_x is not None and self.mouse_parking_y is not None:
            candidates.append((self.mouse_parking_x, self.mouse_parking_y, "manual"))
        else:
            candidates.append((self.mouse_parking_static_x, self.mouse_parking_static_y, "static_client_point"))

        if self.mouse_parking_fail_safe_relocate_enabled:
            candidates.append((
                self.mouse_parking_fallback_static_x,
                self.mouse_parking_fallback_static_y,
                "fallback_static_client_point",
            ))
            candidates.extend(self.get_client_centerish_parking_candidates(*client_bounds))

        return self.choose_safe_mouse_parking_candidate(
            hwnd,
            candidates,
            client_bounds,
        )

    def park_mouse_before_recognition(self, reason, hwnd=None, enabled=True, recovery_fallback=False):
        if not enabled:
            self.write_log(f"Mouse parking skipped | reason={reason} | why=recognition_path_disabled")
            return False

        if not self.mouse_parking_enabled:
            self.write_log(f"Mouse parking skipped | reason={reason} | why=disabled")
            return False

        if self.mouse_parking_mode == "disabled":
            self.write_log(f"Mouse parking skipped | reason={reason} | why=mode_disabled")
            return False

        if self.mouse_parking_mode == "recovery_only" and not recovery_fallback:
            self.write_log(
                f"Mouse parking skipped in normal flow | reason={reason} | "
                "Mouse parking allowed only in recovery fallback"
            )
            return False

        if recovery_fallback:
            self.write_log(f"Mouse parking allowed only in recovery fallback | reason={reason}")

        if hwnd is None:
            hwnd = self.get_game_hwnd()

        if hwnd is None:
            self.write_log(f"Mouse parking skipped | reason={reason} | why=no_window")
            return False

        raw_strategy = str(
            self.get_config().get("mouse_parking_strategy", "static_client_point")
        ).strip().lower()

        if raw_strategy in {"map_anchor", "anchor_map", "visual_anchor", "difficulty_anchor"}:
            self.write_log(
                f"Mouse parking skipped visual-anchor strategy disabled | "
                f"reason={reason} | configured_strategy={raw_strategy} | "
                "using=static_client_point"
            )

        parking_point = self.get_default_mouse_parking_point(hwnd)

        if parking_point is None:
            self.write_log(f"Mouse parking skipped | reason={reason} | why=no_safe_point")
            return False

        local_x, local_y = parking_point["local"]
        screen_x, screen_y = parking_point["screen"]
        source = parking_point["source"]

        if source == "static_client_point":
            self.write_log(
                f"Mouse parking using static client point | reason={reason} | "
                f"local=({local_x}, {local_y}) | screen=({screen_x}, {screen_y}) | "
                f"configured=({self.mouse_parking_static_x}, {self.mouse_parking_static_y})"
            )
        elif source == "fallback_static_client_point":
            self.write_log(
                f"Mouse parking using fallback static client point | reason={reason} | "
                f"local=({local_x}, {local_y}) | screen=({screen_x}, {screen_y}) | "
                f"configured=({self.mouse_parking_fallback_static_x}, {self.mouse_parking_fallback_static_y})"
            )
        elif source.startswith("client_centerish"):
            self.write_log(
                f"Mouse parking using center-ish client point | reason={reason} | "
                f"local=({local_x}, {local_y}) | screen=({screen_x}, {screen_y}) | "
                f"source={source}"
            )
        elif source == "manual":
            self.write_log(
                f"Mouse parking using configured client point | reason={reason} | "
                f"local=({local_x}, {local_y}) | screen=({screen_x}, {screen_y})"
            )

        self.write_log(
            f"Mouse parking before recognition | reason={reason} | "
            f"local=({local_x}, {local_y}) | screen=({screen_x}, {screen_y}) | "
            f"source={source} | wait={self.mouse_parking_wait_seconds:.2f}"
        )

        if not self.safe_pyautogui_move_to(
            screen_x,
            screen_y,
            label=f"mouse_parking:{reason}",
            duration=0.05,
        ):
            self.write_log(f"Mouse parking skipped | reason={reason} | why=move_failed_safe")
            return False

        time.sleep(self.mouse_parking_wait_seconds)
        return True

    def background_click_window_point(self, hwnd, local_x, local_y, label="", coordinate_space="screenshot"):
        """
        Send a background click to the game window without moving the real mouse.
        """
        if coordinate_space == "screenshot":
            client_x, client_y, screen_x, screen_y, scaling_status = self.screenshot_local_to_click_coordinates(
                hwnd,
                local_x,
                local_y,
                label=label,
            )
        else:
            client_x, client_y, screen_x, screen_y = self.local_to_client(hwnd, local_x, local_y)
            scaling_status = {"active": False, "reason": f"{coordinate_space}_coordinate_space"}

        window_rect = self.safe_window_rect(hwnd)
        client_origin = self.safe_client_origin(hwnd)
        lparam = self.make_lparam(client_x, client_y)

        self.write_log(
            f"Background click | label={label} | "
            f"coordinate_space={coordinate_space} | "
            f"local=({local_x}, {local_y}) | "
            f"client=({client_x}, {client_y}) | "
            f"screen=({screen_x}, {screen_y}) | "
            f"scaling_active={scaling_status.get('active')} | "
            f"window_rect={self.format_diag_value(window_rect)} | "
            f"client_origin={self.format_diag_value(client_origin)}"
        )

        win32gui.PostMessage(hwnd, win32con.WM_MOUSEMOVE, 0, lparam)
        time.sleep(0.05)

        win32gui.PostMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lparam)
        time.sleep(0.08)

        win32gui.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, lparam)
        time.sleep(self.nav_click_delay_seconds)

        return True

    def background_scroll_window_point(
        self,
        hwnd,
        local_x,
        local_y,
        direction,
        repeat,
        coordinate_space="legacy_local",
        source="static",
    ):
        """
        Send background mouse wheel messages to the game window.
        Does not move the real mouse.
        """
        if coordinate_space == "screenshot":
            client_x, client_y, screen_x, screen_y, scaling_status = self.screenshot_local_to_click_coordinates(
                hwnd,
                local_x,
                local_y,
                label=f"scroll_map_{direction}",
            )
        else:
            client_x, client_y, screen_x, screen_y = self.local_to_client(hwnd, local_x, local_y)
            scaling_status = {"active": False, "reason": f"{coordinate_space}_coordinate_space"}

        if direction == "up":
            wheel_delta = 120
        else:
            wheel_delta = -120

        # WM_MOUSEWHEEL uses screen coordinates in lParam.
        lparam = self.make_lparam(screen_x, screen_y)

        # High word of wParam is wheel delta.
        wparam = (wheel_delta & 0xFFFF) << 16

        self.write_log(
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

    def click_window_point(self, hwnd, local_x, local_y, label="", coordinate_space="screenshot"):
        """
        Click a point using local captured-window coordinates.
        Uses either real mouse or background window message depending on settings.
        """
        if self.use_background_input:
            return self.background_click_window_point(
                hwnd,
                local_x,
                local_y,
                label=label,
                coordinate_space=coordinate_space,
            )

        window_rect = win32gui.GetWindowRect(hwnd)
        client_origin = self.safe_client_origin(hwnd)

        if coordinate_space == "screenshot":
            client_x, client_y, screen_x, screen_y, scaling_status = self.screenshot_local_to_click_coordinates(
                hwnd,
                local_x,
                local_y,
                label=label,
            )
        else:
            client_x, client_y, screen_x, screen_y = self.local_to_client(hwnd, local_x, local_y)
            scaling_status = {"active": False, "reason": f"{coordinate_space}_coordinate_space"}

        self.write_log(
            f"Click window point | label={label} | "
            f"coordinate_space={coordinate_space} | "
            f"local=({local_x}, {local_y}) | "
            f"client=({client_x}, {client_y}) | "
            f"screen=({screen_x}, {screen_y}) | "
            f"scaling_active={scaling_status.get('active')} | "
            f"window_rect={window_rect} | "
            f"client_origin={self.format_diag_value(client_origin)}"
        )

        try:
            win32gui.SetForegroundWindow(hwnd)
            time.sleep(0.2)
        except Exception as e:
            self.write_log(f"Window focus warning: {e}")

        if not self.safe_pyautogui_move_to(
            screen_x,
            screen_y,
            label=label,
            duration=0.12,
        ):
            return False

        if not self.safe_pyautogui_click(screen_x, screen_y, label=label):
            return False

        time.sleep(self.nav_click_delay_seconds)
        return True

    def scroll_map(self, hwnd, direction, repeat, focus, resolve_legacy_focus):
        local_x = focus["local_x"]
        local_y = focus["local_y"]
        screen_x = focus["screen_x"]
        screen_y = focus["screen_y"]

        if self.use_background_input:
            return self.background_scroll_window_point(
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
            self.write_log(f"Window focus warning before scroll: {e}")

        move_ok = self.safe_pyautogui_move_to(
            screen_x,
            screen_y,
            label=f"scroll_map_{direction}",
            duration=0.15,
        )

        if not move_ok and focus["source"] != "static_map_panel":
            focus = resolve_legacy_focus(
                reason=f"dynamic_move_failed:{focus['source']}",
                label=f"scroll_map_{direction}",
            )
            local_x = focus["local_x"]
            local_y = focus["local_y"]
            screen_x = focus["screen_x"]
            screen_y = focus["screen_y"]
            move_ok = self.safe_pyautogui_move_to(
                screen_x,
                screen_y,
                label=f"scroll_map_{direction}_fallback",
                duration=0.15,
            )

        if not move_ok:
            return False

        time.sleep(0.1)

        # Focus map panel before scrolling.
        click_ok = self.safe_pyautogui_click(
            screen_x,
            screen_y,
            label=f"scroll_map_focus_{direction}",
        )

        if not click_ok and focus["source"] != "static_map_panel":
            focus = resolve_legacy_focus(
                reason=f"dynamic_focus_click_failed:{focus['source']}",
                label=f"scroll_map_{direction}",
            )
            local_x = focus["local_x"]
            local_y = focus["local_y"]
            screen_x = focus["screen_x"]
            screen_y = focus["screen_y"]
            click_ok = self.safe_pyautogui_click(
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
            if not self.safe_pyautogui_scroll(amount, label=f"scroll_map_{direction}"):
                return False

            time.sleep(0.04)

        self.write_log(
            f"Scrolled map {direction} | "
            f"scroll_source={focus['source']} | "
            f"scroll_point_local=({local_x}, {local_y}) | "
            f"scroll_point_screen=({screen_x}, {screen_y}) | "
            f"scaling_active={focus['scaling_active']} | "
            f"repeat={repeat}"
        )

        time.sleep(0.5)
        return True

    def fast_scroll_map_boundary(
        self,
        hwnd,
        direction,
        repeat,
        focus_factory,
        resolve_legacy_focus,
        slow_scroll_fallback,
    ):
        """
        Fast boundary scroll used by level search only.
        Keeps scroll_map unchanged as the reliable slow fallback.
        """
        if not self.fast_scroll_use_burst:
            start_time = time.time()
            ok = slow_scroll_fallback(repeat)
            elapsed = time.time() - start_time
            self.write_log(
                f"NAV fast scroll boundary complete | direction={direction} | "
                f"method=slow_fallback | repeat={repeat} | elapsed={elapsed:.2f}s"
            )
            return ok

        focus = focus_factory()
        local_x = focus["local_x"]
        local_y = focus["local_y"]
        screen_x = focus["screen_x"]
        screen_y = focus["screen_y"]

        start_time = time.time()
        burst_count = max(1, self.fast_scroll_burst_count)
        burst_units = max(1, repeat // burst_count)
        remainder = max(0, repeat - (burst_units * burst_count))

        if direction == "up":
            wheel_unit = 120
            pyautogui_unit = 8
        else:
            wheel_unit = -120
            pyautogui_unit = -8

        try:
            if self.use_background_input:
                lparam = self.make_lparam(screen_x, screen_y)

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
                    self.write_log(f"Window focus warning before fast scroll: {e}")

                move_ok = self.safe_pyautogui_move_to(
                    screen_x,
                    screen_y,
                    label=f"fast_scroll_{direction}",
                    duration=0.02,
                )

                if not move_ok and focus["source"] != "static_map_panel":
                    focus = resolve_legacy_focus(
                        reason=f"dynamic_fast_move_failed:{focus['source']}",
                        label=f"fast_scroll_{direction}",
                    )
                    local_x = focus["local_x"]
                    local_y = focus["local_y"]
                    screen_x = focus["screen_x"]
                    screen_y = focus["screen_y"]
                    move_ok = self.safe_pyautogui_move_to(
                        screen_x,
                        screen_y,
                        label=f"fast_scroll_{direction}_fallback",
                        duration=0.02,
                    )

                if not move_ok:
                    return False

                click_ok = self.safe_pyautogui_click(
                    screen_x,
                    screen_y,
                    label=f"fast_scroll_focus_{direction}",
                )

                if not click_ok and focus["source"] != "static_map_panel":
                    focus = resolve_legacy_focus(
                        reason=f"dynamic_fast_focus_click_failed:{focus['source']}",
                        label=f"fast_scroll_{direction}",
                    )
                    local_x = focus["local_x"]
                    local_y = focus["local_y"]
                    screen_x = focus["screen_x"]
                    screen_y = focus["screen_y"]
                    click_ok = self.safe_pyautogui_click(
                        screen_x,
                        screen_y,
                        label=f"fast_scroll_focus_{direction}_fallback",
                    )

                if not click_ok:
                    return False
                time.sleep(0.03)

                for index in range(burst_count):
                    units = burst_units + (remainder if index == burst_count - 1 else 0)
                    if not self.safe_pyautogui_scroll(
                        pyautogui_unit * units,
                        label=f"fast_scroll_{direction}",
                    ):
                        return False
                    time.sleep(0.01)

                method = "foreground_burst"

        except pyautogui.FailSafeException:
            self.write_log(
                "FAST SCROLL ABORTED: PyAutoGUI fail-safe triggered. "
                "Move mouse away from screen corners."
            )
            return False

        elapsed = time.time() - start_time
        self.write_log(
            f"NAV fast scroll boundary complete | direction={direction} | "
            f"method={method} | repeat={repeat} | bursts={burst_count} | "
            f"scroll_source={focus['source']} | "
            f"scroll_point_local=({local_x}, {local_y}) | "
            f"scroll_point_screen=({screen_x}, {screen_y}) | "
            f"scaling_active={focus['scaling_active']} | elapsed={elapsed:.2f}s"
        )

        return True
