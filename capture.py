# MAA Task Bar Hero
# Concept and direction by Marcus Xu.
# Built with Codex as a coding assistant.
# Shared for learning, experimentation, and automation research.

import time
import os
import ctypes
import win32gui
import win32ui
import numpy as np
import cv2


def find_window_by_title_keyword(keyword: str):
    """
    Find a visible window whose title contains the keyword.
    Example keyword: "TaskBarHero"
    """
    matched_windows = []

    def enum_handler(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if keyword.lower() in title.lower():
                matched_windows.append((hwnd, title))

    win32gui.EnumWindows(enum_handler, None)

    if not matched_windows:
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
