# MAA Task Bar Hero
# Concept and direction by Marcus Xu.
# Built with Codex as a coding assistant.
# Shared for learning, experimentation, and automation research.

import json
import os
import ctypes
from ctypes import wintypes
from pathlib import Path
import re
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog
from tkinter import scrolledtext
from tkinter import messagebox
from tkinter import ttk

from config import CONFIG_FILE_NAME, get_base_dir, get_config, get_recognition_mode
from debug_files import (
    clear_generated_debug_files,
    export_debug_zip,
    get_export_default_path,
    has_significant_error,
    refresh_stale_debug_zip_selection,
)
from route_config import AVAILABLE_LEVELS


BASE_DIR = get_base_dir()
OUTPUT_FILE = BASE_DIR / "farm_plan.json"
MAIN_FILE = BASE_DIR / "main.py"
BOT_CONSOLE_LOG = BASE_DIR / "bot_console.log"
APP_VERSION = "v1.2, 2026-06-12"

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


configure_console_encoding()

RECOMMENDED_GUIDE_LEVELS = [
    "80级 | 折磨 | 1-3",
    "65级 | 地狱 | 2-5",
    "50级 | 噩梦 | 3-5",
    "40级 | 噩梦 | 1-9",
    "30级 | 普通 | 3-8",
    "20级 | 普通 | 2-8",
    "15级 | 普通 | 2-3",
    "10级 | 普通 | 1-8",
    "5级 | 普通 | 1-4",
    "普通 | 1-1",
]

RECOMMENDED_GUIDE_ROUTES = [
    ("torment", "chapter_1", "1-3"),
    ("hell", "chapter_2", "2-5"),
    ("nightmare", "chapter_3", "3-5"),
    ("nightmare", "chapter_1", "1-9"),
    ("normal", "chapter_3", "3-8"),
    ("normal", "chapter_2", "2-8"),
    ("normal", "chapter_2", "2-3"),
    ("normal", "chapter_1", "1-8"),
    ("normal", "chapter_1", "1-4"),
    ("normal", "chapter_1", "1-1"),
]

DIFFICULTY_OPTIONS = [
    ("normal", "普通"),
    ("nightmare", "噩梦"),
    ("hell", "地狱"),
    ("torment", "折磨"),
]

RECOGNITION_MODE_OPTIONS = [
    ("safe", "安全(仅推荐1K使用)"),
    ("balanced", "平衡(推荐大多数用户使用)"),
    ("aggressive", "兼容/激进(推荐高分无法兼容使用)"),
]

# GUI display labels are localized; config/internal values remain English.
DIFFICULTY_LABELS = {
    key: label for key, label in DIFFICULTY_OPTIONS
}
DIFFICULTY_KEYS_BY_LABEL = {
    label: key for key, label in DIFFICULTY_OPTIONS
}

RECOGNITION_MODE_LABELS = {
    key: label for key, label in RECOGNITION_MODE_OPTIONS
}

WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
EMERGENCY_HOTKEY_ID = 0x4DAA
MODIFIER_FLAGS = {
    "alt": 0x0001,
    "ctrl": 0x0002,
    "control": 0x0002,
    "shift": 0x0004,
    "win": 0x0008,
}
FUNCTION_KEY_VK = {
    f"F{index}": 0x70 + index - 1
    for index in range(1, 25)
}

try:
    USER32 = ctypes.WinDLL("user32", use_last_error=True) if os.name == "nt" else None
    KERNEL32 = ctypes.WinDLL("kernel32", use_last_error=True) if os.name == "nt" else None
except Exception:
    USER32 = None
    KERNEL32 = None


class POINT(ctypes.Structure):
    _fields_ = [
        ("x", wintypes.LONG),
        ("y", wintypes.LONG),
    ]


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", POINT),
    ]


if USER32 is not None:
    USER32.RegisterHotKey.argtypes = [
        wintypes.HWND,
        ctypes.c_int,
        wintypes.UINT,
        wintypes.UINT,
    ]
    USER32.RegisterHotKey.restype = wintypes.BOOL
    USER32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
    USER32.UnregisterHotKey.restype = wintypes.BOOL
    USER32.GetMessageW.argtypes = [
        ctypes.POINTER(MSG),
        wintypes.HWND,
        wintypes.UINT,
        wintypes.UINT,
    ]
    USER32.GetMessageW.restype = ctypes.c_int
    USER32.PostThreadMessageW.argtypes = [
        wintypes.DWORD,
        wintypes.UINT,
        wintypes.WPARAM,
        wintypes.LPARAM,
    ]
    USER32.PostThreadMessageW.restype = wintypes.BOOL

if KERNEL32 is not None:
    # GetCurrentThreadId is exported by kernel32.dll, not user32.dll.
    KERNEL32.GetCurrentThreadId.argtypes = []
    KERNEL32.GetCurrentThreadId.restype = wintypes.DWORD


def config_bool_value(name, default):
    value = get_config().get(name, default)

    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}

    return bool(value)


def parse_emergency_hotkey_config():
    modifiers_text = str(
        get_config().get("emergency_hotkey_modifiers", "ctrl+shift")
    ).strip()
    key_text = str(get_config().get("emergency_hotkey_key", "F12")).strip().upper()

    modifiers = 0
    display_parts = []

    for part in re.split(r"[+\s]+", modifiers_text.lower()):
        if not part:
            continue

        flag = MODIFIER_FLAGS.get(part)

        if flag is None:
            continue

        modifiers |= flag
        display_parts.append("Ctrl" if part in {"ctrl", "control"} else part.title())

    if key_text in FUNCTION_KEY_VK:
        vk = FUNCTION_KEY_VK[key_text]
    elif len(key_text) == 1 and key_text.isalnum():
        vk = ord(key_text)
    else:
        vk = None

    display = " + ".join(display_parts + ([key_text] if key_text else []))
    return modifiers, vk, display or "Ctrl + Shift + F12"

KEY_INFO_LINES = [
    "使用前请确保以下事项已准备就绪：",
    "",
    "1.解压文件夹内的所有内容都在固定位置，不要移动或删除任何文件，且路径不支持中文字符",
    "2.地图已经被打开，并且可以看到关卡列表，若开启放入仓库 则需要打开仓库界面",
    "3.箱子掉落UI没有被透明化，UI大小为1x，日志处于固定窗口状态（设置内调整）",
    "4.推荐配置为1080p，缩放比100%，以获得最佳效果，目前已做到兼容2K,3K,4K，但不保证所有设备都能完美适配",
    "5.MAA切换关卡时会出现抢鼠标的情况，请不要操作鼠标，等待MAA完成关卡切换。若看到鼠标抽风，请不要慌张，MAA正在自动修正中，等待10-20秒通常可以恢复正常",
    "6.如果需要紧急停止，使用热键Ctrl + Shift + F12，该热键在任何时候都可以安全停止MAA",
]

class RoutePlannerApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"MAA Task Bar Hero - {APP_VERSION}")
        self.root.geometry("1180x840")
        self.root.minsize(1040, 760)

        self.selected_routes = []
        self.available_level_items = []
        self.bot_process = None
        self.bot_log_handle = None
        self.log_read_position = 0
        self.is_closing = False
        self.hotkey_registered = False
        self.hotkey_polling = False
        self.hotkey_thread = None
        self.hotkey_thread_id = None
        self.hotkey_thread_started = threading.Event()
        self.emergency_stop_pending = False
        self.emergency_hotkey_enabled = config_bool_value("emergency_hotkey_enabled", True)
        self.emergency_hotkey_modifiers, self.emergency_hotkey_vk, self.emergency_hotkey_display = (
            parse_emergency_hotkey_config()
        )
        self.last_navigation_failure_warning = ""
        self.notified_warning_keys = set()
        self.status_var = tk.StringVar(value="就绪：选择路线后可以保存并启动MAA。")
        self.background_input_var = tk.BooleanVar(value=False)
        self.move_to_storage_var = tk.BooleanVar(
            value=bool(get_config().get("move_backpack_to_storage_after_blue_chest", False))
        )
        self.move_to_storage_after_non_blue_var = tk.BooleanVar(
            value=config_bool_value("move_backpack_to_storage_after_non_blue_box", True)
        )
        self.repeat_same_level_var = tk.BooleanVar(
            value=config_bool_value("repeat_same_level_after_blue_chest", False)
        )
        self.same_tier_substitution_var = tk.BooleanVar(
            value=config_bool_value("same_tier_substitution_enabled", True)
        )
        self.no_chest_retries_var = tk.StringVar(value=str(self.get_default_no_chest_retries()))
        self.difficulty_var = tk.StringVar(value="normal")
        self.difficulty_display_var = tk.StringVar(value=DIFFICULTY_LABELS.get("normal", "普通"))
        self.recognition_mode_var = tk.StringVar(
            value=RECOGNITION_MODE_LABELS.get(get_recognition_mode(), "平衡")
        )

        style = ttk.Style()
        style.configure("TLabel", font=("Segoe UI", 10))
        style.configure("TButton", font=("Segoe UI", 10))
        style.configure("TLabelframe.Label", font=("Segoe UI", 11, "bold"))

        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=0)
        root.rowconfigure(1, weight=3)
        root.rowconfigure(2, weight=0)
        root.rowconfigure(3, weight=2)

        # Top: usage info on the left, recommendation guide on the right.
        top_frame = tk.Frame(root)
        top_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 6))
        top_frame.columnconfigure(0, weight=1)
        top_frame.columnconfigure(1, weight=1)

        key_info_frame = tk.LabelFrame(top_frame, text="使用前说明")
        key_info_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        key_info_frame.columnconfigure(0, weight=1)

        key_info_text = "\n".join(KEY_INFO_LINES)
        tk.Label(
            key_info_frame,
            text=key_info_text,
            anchor="nw",
            justify="left",
            wraplength=520,
            fg="#333333",
        ).grid(row=0, column=0, sticky="nsew", padx=8, pady=6)

        guide_frame = tk.LabelFrame(top_frame, text="推荐刷图参考")
        guide_frame.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        guide_frame.columnconfigure(0, weight=1)

        guide_text = "\n".join(RECOMMENDED_GUIDE_LEVELS)
        tk.Label(
            guide_frame,
            text=guide_text,
            anchor="w",
            justify="left",
            wraplength=440,
            fg="#333333",
        ).grid(row=0, column=0, sticky="ew", padx=8, pady=6)

        guide_button_frame = tk.Frame(guide_frame)
        guide_button_frame.grid(row=0, column=1, sticky="e", padx=8, pady=6)

        tk.Button(
            guide_button_frame,
            text="使用推荐路线",
            width=16,
            command=self.load_recommended_plan,
        ).grid(row=0, column=0, pady=(0, 4))

        tk.Button(
            guide_button_frame,
            text="一键保存并启动",
            width=16,
            command=self.start_recommended_plan,
        ).grid(row=1, column=0)

        # Middle: route planner.
        planner_frame = tk.LabelFrame(root, text="路线选择")
        planner_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=4)
        planner_frame.columnconfigure(0, weight=1)
        planner_frame.columnconfigure(2, weight=1)
        planner_frame.rowconfigure(2, weight=1)

        # Left: difficulty dropdown + filtered levels.
        filter_frame = tk.Frame(planner_frame)
        filter_frame.grid(row=0, column=0, columnspan=3, sticky="ew", padx=8, pady=(8, 4))
        filter_frame.columnconfigure(1, weight=1)

        tk.Label(filter_frame, text="选择难度：").grid(row=0, column=0, sticky="w")

        difficulty_menu = tk.OptionMenu(
            filter_frame,
            self.difficulty_display_var,
            *[label for _key, label in DIFFICULTY_OPTIONS],
            command=self.on_difficulty_changed,
        )
        difficulty_menu.grid(row=0, column=1, sticky="w", padx=(8, 0))

        tk.Label(planner_frame, text="可用关卡").grid(
            row=1, column=0, sticky="n", padx=(0, 10), pady=(0, 0)
        )

        self.available_listbox = tk.Listbox(planner_frame, width=52, height=16, exportselection=False)
        self.available_listbox.grid(row=2, column=0, sticky="nsew", padx=(8, 10), pady=(24, 8))

        # Middle buttons.
        button_frame = tk.Frame(planner_frame)
        button_frame.grid(row=2, column=1, sticky="n", padx=8, pady=(24, 8))

        tk.Button(button_frame, text="添加 →", width=14, command=self.add_selected).grid(row=0, column=0, pady=4)
        tk.Button(button_frame, text="← 移除", width=14, command=self.remove_selected).grid(row=1, column=0, pady=4)
        tk.Button(button_frame, text="上移", width=14, command=self.move_up).grid(row=2, column=0, pady=4)
        tk.Button(button_frame, text="下移", width=14, command=self.move_down).grid(row=3, column=0, pady=4)
        tk.Button(button_frame, text="清空路线", width=14, command=self.clear_plan).grid(row=4, column=0, pady=4)
        tk.Button(button_frame, text="读取路线", width=14, command=self.load_existing_plan).grid(row=5, column=0, pady=4)

        # Right: selected plan.
        tk.Label(planner_frame, text="当前刷图循环").grid(
            row=1, column=2, sticky="n", padx=(10, 0), pady=(0, 0)
        )

        self.plan_listbox = tk.Listbox(planner_frame, width=52, height=16, exportselection=False)
        self.plan_listbox.grid(row=2, column=2, sticky="nsew", padx=(10, 8), pady=(24, 8))

        # Help text.
        help_text = (
            "使用说明：左侧先选择难度，再选择关卡并添加到右侧循环列表。\n"
            "右侧列表会自动循环执行，无需重复添加。重复次数会保存到每条路线。\n"
            "更多功能开发中，欢迎加入Q群851450292反馈 BUG 与开发建议。\n"
            "有问题请私信 B站UP主：没变成彩天鹅的笔小鸭~"
        )

        tk.Label(planner_frame, text=help_text, justify="left", anchor="w").grid(
            row=3, column=0, columnspan=3, sticky="ew", padx=8, pady=(0, 8)
        )

        # Controls.
        control_frame = tk.LabelFrame(root, text="MAA 控制")
        control_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 8))
        control_frame.columnconfigure(4, weight=1)

        tk.Button(
            control_frame,
            text="保存并启动 MAA",
            width=18,
            command=self.start_bot,
        ).grid(row=0, column=0, padx=(10, 8), pady=(10, 4))

        tk.Button(
            control_frame,
            text="停止 MAA",
            width=14,
            command=self.stop_bot,
        ).grid(row=0, column=1, padx=(0, 12), pady=(10, 4))

        tk.Button(
            control_frame,
            text="导出报错log压缩包",
            width=18,
            command=self.export_debug_zip,
        ).grid(row=2, column=0, columnspan=2, sticky="w", padx=(10, 8), pady=(0, 8))

        tk.Label(
            control_frame,
            text="识别模式：",
            anchor="w",
        ).grid(row=2, column=2, sticky="w", padx=(0, 4), pady=(0, 8))

        recognition_menu = tk.OptionMenu(
            control_frame,
            self.recognition_mode_var,
            *[label for _key, label in RECOGNITION_MODE_OPTIONS],
            command=self.on_recognition_mode_changed,
        )
        recognition_menu.grid(row=2, column=3, sticky="w", pady=(0, 8))

        tk.Label(
            control_frame,
            text="若箱子刷关后未掉落，重复关卡次数:",
            anchor="w",
        ).grid(row=0, column=2, sticky="w", padx=(0, 4), pady=(10, 4))

        tk.Checkbutton(
            control_frame,
            text="自动转移背包物品到仓库",
            variable=self.move_to_storage_var,
        ).grid(row=1, column=2, columnspan=3, sticky="w", padx=(0, 10), pady=(4, 10))

        tk.Checkbutton(
            control_frame,
            text="蓝箱掉落后重复同一关卡",
            variable=self.repeat_same_level_var,
        ).grid(row=1, column=4, sticky="w", padx=(14, 10), pady=(4, 10))

        tk.Checkbutton(
            control_frame,
            text="路线失败时尝试同等级箱子替代关卡",
            variable=self.same_tier_substitution_var,
        ).grid(row=2, column=4, sticky="w", padx=(14, 10), pady=(0, 8))

        tk.Checkbutton(
            control_frame,
            text="棕/其他箱后转移背包到仓库",
            variable=self.move_to_storage_after_non_blue_var,
        ).grid(row=3, column=2, columnspan=2, sticky="w", padx=(0, 10), pady=(0, 8))

        tk.Entry(
            control_frame,
            textvariable=self.no_chest_retries_var,
            width=6,
        ).grid(row=0, column=3, sticky="w", pady=(10, 4))

        tk.Label(
            control_frame,
            textvariable=self.status_var,
            anchor="w",
        ).grid(row=0, column=4, sticky="ew", padx=(14, 10), pady=(10, 4))

        tk.Checkbutton(
            control_frame,
            text="后台输入模式（仅供开发者调试开发）",
            variable=self.background_input_var,
        ).grid(row=1, column=0, columnspan=2, sticky="w", padx=(10, 8), pady=(4, 10))

        tk.Label(
            control_frame,
            text=f"Concept & Direction: Marcus Xu · Build {APP_VERSION}",
            anchor="e",
            fg="#666666",
        ).grid(row=4, column=2, columnspan=3, sticky="e", padx=(8, 10), pady=(0, 8))

        tk.Label(
            control_frame,
            text=f"紧急停止热键：{self.emergency_hotkey_display}",
            anchor="w",
            fg="#444444",
        ).grid(row=3, column=0, columnspan=2, sticky="w", padx=(10, 8), pady=(0, 8))

        # Log panel.
        log_frame = tk.LabelFrame(root, text="MAA 日志")
        log_frame.grid(row=3, column=0, sticky="nsew", padx=10, pady=(0, 10))
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)

        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            height=9,
            state="disabled",
            wrap="word",
        )
        self.log_text.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)

        self.populate_available_levels()
        self.load_existing_plan(silent=True)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.register_emergency_hotkey()
        self.root.after(1000, self.refresh_bot_status)

    def register_emergency_hotkey(self):
        if not self.emergency_hotkey_enabled:
            self.append_log_text("\n[GUI] Emergency stop hotkey disabled by config.\n")
            return

        if USER32 is None:
            self.append_log_text(
                "\n[GUI] Emergency stop hotkey unavailable: Windows user32 API not available.\n"
            )
            return

        if not self.emergency_hotkey_modifiers or self.emergency_hotkey_vk is None:
            self.append_log_text(
                "\n[GUI] Emergency stop hotkey registration failed: invalid hotkey config.\n"
            )
            return

        if self.hotkey_thread is not None and self.hotkey_thread.is_alive():
            self.append_log_text(
                "\n[GUI] Emergency hotkey registration skipped; thread already running.\n"
            )
            return

        self.hotkey_polling = True
        self.hotkey_thread_started.clear()
        self.hotkey_thread = threading.Thread(
            target=self.emergency_hotkey_message_loop,
            name="MAA-TBH-emergency-hotkey",
            daemon=True,
        )
        self.hotkey_thread.start()

    def unregister_emergency_hotkey(self):
        self.hotkey_polling = False

        if USER32 is None:
            return

        thread_id = self.hotkey_thread_id

        if thread_id:
            ok = USER32.PostThreadMessageW(thread_id, WM_QUIT, 0, 0)

            if not ok:
                error_code = ctypes.get_last_error()
                self.append_log_text(
                    "\n[GUI] Emergency hotkey WM_QUIT post failed | "
                    f"thread_id={thread_id} | error_code={error_code}\n"
                )

        if self.hotkey_thread is not None and self.hotkey_thread.is_alive():
            self.hotkey_thread.join(timeout=0.5)

            if self.hotkey_thread.is_alive():
                self.append_log_text(
                    "\n[GUI] Emergency hotkey thread did not exit before GUI close timeout.\n"
                )

    def notify_from_hotkey_thread(self, callback, *args):
        if self.is_closing:
            return

        try:
            self.root.after(0, callback, *args)
        except Exception:
            pass

    def notify_hotkey_log(self, text):
        self.notify_from_hotkey_thread(self.append_log_text, text)

    def notify_hotkey_status(self, text):
        self.notify_from_hotkey_thread(self.status_var.set, text)

    def emergency_hotkey_message_loop(self):
        thread_id = KERNEL32.GetCurrentThreadId()
        self.hotkey_thread_id = thread_id
        self.hotkey_thread_started.set()

        ok = USER32.RegisterHotKey(
            None,
            EMERGENCY_HOTKEY_ID,
            self.emergency_hotkey_modifiers,
            self.emergency_hotkey_vk,
        )

        if not ok:
            error_code = ctypes.get_last_error()
            self.hotkey_registered = False
            self.hotkey_polling = False
            self.hotkey_thread_id = None
            self.notify_hotkey_log(
                "\n[GUI] Emergency hotkey registration failed | "
                f"hotkey={self.emergency_hotkey_display} | "
                f"thread_id={thread_id} | hotkey_id={EMERGENCY_HOTKEY_ID} | "
                f"error_code={error_code}\n"
            )
            self.notify_hotkey_status(
                f"紧急停止热键注册失败，GUI 可继续使用：{self.emergency_hotkey_display}"
            )
            return

        self.hotkey_registered = True
        self.notify_hotkey_log(
            "\n[GUI] Emergency hotkey registered | "
            f"hotkey={self.emergency_hotkey_display} | "
            f"modifiers={self.emergency_hotkey_modifiers} | "
            f"vk={self.emergency_hotkey_vk} | "
            f"thread_id={thread_id} | hotkey_id={EMERGENCY_HOTKEY_ID}\n"
        )

        msg = MSG()

        try:
            while True:
                result = USER32.GetMessageW(ctypes.byref(msg), None, 0, 0)

                if result == 0:
                    break

                if result == -1:
                    error_code = ctypes.get_last_error()
                    self.notify_hotkey_log(
                        "\n[GUI] Emergency hotkey message loop error | "
                        f"thread_id={thread_id} | error_code={error_code}\n"
                    )
                    break

                if msg.message == WM_HOTKEY and msg.wParam == EMERGENCY_HOTKEY_ID:
                    self.notify_hotkey_log(
                        "\n[GUI] Emergency hotkey WM_HOTKEY received | "
                        f"thread_id={thread_id} | hotkey_id={EMERGENCY_HOTKEY_ID}\n"
                    )
                    self.notify_from_hotkey_thread(self.handle_emergency_hotkey)
        finally:
            if self.hotkey_registered:
                USER32.UnregisterHotKey(None, EMERGENCY_HOTKEY_ID)
                self.hotkey_registered = False

            if self.hotkey_polling and not self.is_closing:
                self.notify_hotkey_log(
                    "\n[GUI] Emergency hotkey thread exited unexpectedly.\n"
                )

            self.hotkey_thread_id = None
            self.notify_hotkey_log(
                "\n[GUI] Emergency hotkey message loop exited.\n"
            )

    def handle_emergency_hotkey(self):
        self.append_log_text("\n[GUI] EMERGENCY STOP triggered by global hotkey\n")

        if self.bot_log_handle is not None:
            try:
                self.write_bot_console_log("EMERGENCY STOP triggered by global hotkey\n")
                self.bot_log_handle.flush()
            except Exception:
                pass

        self.emergency_stop_bot_process()

    def emergency_stop_bot_process(self):
        if self.emergency_stop_pending:
            return

        if self.bot_process is None or self.bot_process.poll() is not None:
            self.status_var.set("紧急停止热键已触发：MAA 当前没有运行。")
            self.append_log_text("[GUI] Emergency stop hotkey pressed; no bot process was running.\n")

            if self.bot_process is not None:
                self.bot_process = None
                self.close_bot_log_handle()

            return

        self.emergency_stop_pending = True
        self.status_var.set("紧急停止热键已触发：正在停止 MAA...")

        try:
            self.bot_process.terminate()
        except Exception as e:
            self.append_log_text(f"[GUI] Emergency terminate failed: {e}\n")

        self.root.after(750, self.finish_emergency_stop_bot_process)

    def finish_emergency_stop_bot_process(self):
        process = self.bot_process

        if process is None:
            self.emergency_stop_pending = False
            self.close_bot_log_handle()
            return

        try:
            if process.poll() is None:
                self.append_log_text("[GUI] Emergency stop escalating to process kill.\n")

                if os.name == "nt":
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                        timeout=2,
                    )
                else:
                    process.kill()

            try:
                process.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                pass
        except Exception as e:
            self.append_log_text(f"[GUI] Emergency kill/check failed: {e}\n")
        finally:
            self.bot_process = None
            self.emergency_stop_pending = False
            self.close_bot_log_handle()
            self.cleanup_after_clean_stop(process_exit_code=None, closing=False)
            self.status_var.set("紧急停止已执行：MAA 已停止。")

    def find_available_level(self, difficulty, chapter, level_name):
        for level in AVAILABLE_LEVELS:
            if (
                level.get("difficulty") == difficulty
                and level.get("chapter") == chapter
                and level.get("level") == level_name
            ):
                return level

        return None

    def build_recommended_plan(self):
        plan = []
        missing = []

        for difficulty, chapter, level_name in RECOMMENDED_GUIDE_ROUTES:
            level = self.find_available_level(difficulty, chapter, level_name)

            if level is None or not level.get("enabled", True):
                missing.append(f"{difficulty} {level_name}")
                continue

            plan.append(level.copy())

        return plan, missing

    def load_recommended_plan(self, show_message=True):
        plan, missing = self.build_recommended_plan()

        if not plan:
            messagebox.showwarning("推荐路线不可用", "没有找到可用的推荐路线。")
            return False

        self.selected_routes = plan
        self.refresh_plan_listbox()
        self.status_var.set(f"已加载推荐路线：{len(plan)} 条。")

        if show_message:
            if missing:
                messagebox.showwarning(
                    "推荐路线部分缺失",
                    "已加载可用推荐路线。以下目标不可用：\n" + "\n".join(missing),
                )
            else:
                messagebox.showinfo("推荐路线已加载", f"已加载 {len(plan)} 条推荐路线。")

        return True

    def start_recommended_plan(self):
        if not self.load_recommended_plan(show_message=False):
            return

        self.start_bot()

    def get_default_no_chest_retries(self):
        config = get_config()

        if "default_no_chest_retries" in config:
            value = config.get("default_no_chest_retries")
        else:
            value = int(config.get("default_max_trials_if_no_chest", 1)) - 1

        try:
            value = int(value)
        except (TypeError, ValueError):
            return 0

        return max(0, value)

    def get_no_chest_retries_from_input(self):
        raw_value = self.no_chest_retries_var.get().strip()

        try:
            retries = int(raw_value)
        except ValueError:
            messagebox.showwarning(
                "重复次数无效",
                "重复关卡次数必须是大于等于 0 的整数。"
            )
            return None

        if retries < 0:
            messagebox.showwarning(
                "重复次数无效",
                "重复关卡次数必须是大于等于 0 的整数。"
            )
            return None

        return retries

    def get_selected_recognition_mode(self):
        selected_label = self.recognition_mode_var.get()

        for key, label in RECOGNITION_MODE_OPTIONS:
            if selected_label == label or selected_label == key:
                return key

        return "balanced"

    def on_recognition_mode_changed(self, _value=None):
        if self.get_selected_recognition_mode() != "aggressive":
            return

        messagebox.showwarning(
            "激进识别模式",
            "激进识别模式可能改善缩放显示器或弱模板的匹配效果，"
            "但也会增加选错章节或关卡的风险。建议仅用于平衡无法使用时；"
            "如果行为异常，请导出报错log压缩包。"
        )

    def save_recognition_mode_config(self):
        config_path = BASE_DIR / CONFIG_FILE_NAME
        selected_mode = self.get_selected_recognition_mode()

        try:
            if config_path.exists():
                with config_path.open("r", encoding="utf-8") as f:
                    config = json.load(f)
            else:
                config = get_config().copy()
        except (OSError, json.JSONDecodeError):
            config = get_config().copy()

        if not isinstance(config, dict):
            config = get_config().copy()

        config["recognition_mode"] = selected_mode
        config["same_tier_substitution_enabled"] = bool(self.same_tier_substitution_var.get())
        config["repeat_same_level_after_blue_chest"] = bool(self.repeat_same_level_var.get())
        config["move_backpack_to_storage_after_non_blue_box"] = bool(
            self.move_to_storage_after_non_blue_var.get()
        )

        with config_path.open("w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
            f.write("\n")

        return selected_mode

    def format_difficulty_cn(self, difficulty):
        mapping = {
            "normal": "普通",
            "nightmare": "噩梦",
            "hell": "地狱",
            "torment": "折磨",
        }
        return mapping.get(difficulty, difficulty)

    def format_chapter_cn(self, chapter):
        mapping = {
            "chapter_1": "第1章",
            "chapter_2": "第2章",
            "chapter_3": "第3章",
        }
        return mapping.get(chapter, chapter)

    def format_level_label(self, level):
        # if route_config.py already has display_name use it directly for simplicity and to allow custom labels, otherwise build a default one.
        if "display_name" in level:
            return level["display_name"]

        difficulty = self.format_difficulty_cn(level["difficulty"])
        chapter = self.format_chapter_cn(level["chapter"])
        stage = level["level"]

        return f"{difficulty} | {chapter} | {stage}"

    def on_difficulty_changed(self, display_label):
        self.difficulty_var.set(DIFFICULTY_KEYS_BY_LABEL.get(display_label, display_label))
        self.populate_available_levels()

    def populate_available_levels(self):
        self.available_listbox.delete(0, tk.END)
        self.available_level_items = []

        selected_difficulty = self.difficulty_var.get()

        for level in AVAILABLE_LEVELS:
            if level.get("difficulty") != selected_difficulty:
                continue

            self.available_level_items.append(level)
            label = self.format_level_label(level)

            if not level.get("enabled", True):
                note = level.get("note", "")
                label = f"[未开放] {label}"

                if note:
                    label += f" - {note}"

            self.available_listbox.insert(tk.END, label)

    def refresh_plan_listbox(self):
        self.plan_listbox.delete(0, tk.END)

        for i, level in enumerate(self.selected_routes, start=1):
            label = self.format_level_label(level)
            self.plan_listbox.insert(tk.END, f"{i}. {label}")

    def add_selected(self):
        selection = self.available_listbox.curselection()

        if not selection:
            return

        index = selection[0]
        level = self.available_level_items[index]

        if not level.get("enabled", True):
            messagebox.showwarning(
                "关卡暂不可用",
                f"{self.format_level_label(level)} 暂时不可添加。\n\n"
                f"{level.get('note', '')}"
            )
            return

        self.selected_routes.append(level.copy())
        self.refresh_plan_listbox()

    def remove_selected(self):
        selection = self.plan_listbox.curselection()

        if not selection:
            return

        index = selection[0]
        self.selected_routes.pop(index)
        self.refresh_plan_listbox()

    def move_up(self):
        selection = self.plan_listbox.curselection()

        if not selection:
            return

        index = selection[0]

        if index == 0:
            return

        self.selected_routes[index - 1], self.selected_routes[index] = (
            self.selected_routes[index],
            self.selected_routes[index - 1],
        )

        self.refresh_plan_listbox()
        self.plan_listbox.selection_set(index - 1)

    def move_down(self):
        selection = self.plan_listbox.curselection()

        if not selection:
            return

        index = selection[0]

        if index >= len(self.selected_routes) - 1:
            return

        self.selected_routes[index + 1], self.selected_routes[index] = (
            self.selected_routes[index],
            self.selected_routes[index + 1],
        )

        self.refresh_plan_listbox()
        self.plan_listbox.selection_set(index + 1)

    def clear_plan(self):
        self.selected_routes = []
        self.refresh_plan_listbox()

    def save_plan(self, show_message=True):
        if not self.selected_routes:
            messagebox.showwarning(
                "没有选择路线",
                "请至少添加一个刷图目标到右侧路线列表。"
            )
            return False

        no_chest_retries = self.get_no_chest_retries_from_input()

        if no_chest_retries is None:
            return False

        try:
            selected_mode = self.save_recognition_mode_config()
        except OSError as e:
            messagebox.showerror("配置保存失败", f"无法保存 recognition_mode 到 config.json：\n\n{e}")
            return False

        plan = []

        for i, level in enumerate(self.selected_routes, start=1):
            route = level.copy()
            route["name"] = f"Route {i}"
            route["no_chest_retries"] = no_chest_retries
            route.pop("max_trials_if_no_chest", None)
            plan.append(route)

        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(plan, f, indent=4, ensure_ascii=False)

        self.status_var.set(f"已保存 {len(plan)} 条路线到 {OUTPUT_FILE.name}。")

        if show_message:
            messagebox.showinfo(
                "保存成功",
                f"刷图路线已保存到 {OUTPUT_FILE.name}\n"
                f"识别模式：{RECOGNITION_MODE_LABELS.get(selected_mode, selected_mode)}"
            )

        return True

    def start_bot(self):
        if self.bot_process is not None and self.bot_process.poll() is None:
            messagebox.showinfo("MAA 已在运行", "别急，MAA 已经在跑了。")
            return

        if not self.save_plan(show_message=False):
            return

        frozen_app = getattr(sys, "frozen", False)

        if not frozen_app and not MAIN_FILE.exists():
            messagebox.showerror("启动失败", f"找不到 {MAIN_FILE}")
            return

        try:
            self.close_bot_log_handle()
            self.clear_log_text()
            self.log_read_position = 0
            self.bot_log_handle = open(BOT_CONSOLE_LOG, "w", encoding="utf-8", buffering=1)
            self.log_read_position = 0
            self.write_bot_console_log(
                f"=== Bot process started | timestamp={self.current_timestamp()} ===\n"
            )

            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            env = os.environ.copy()
            input_mode = "background" if self.background_input_var.get() else "foreground"
            env["MAATBH_INPUT_MODE"] = input_mode
            env["MAATBH_SHOW_PREVIEW"] = "0"
            env["MAATBH_ENABLE_BEEP"] = "0"
            env["MAATBH_AUTO_OPEN_BLUE"] = "1"
            env["MAATBH_NAVIGATE_ON_START"] = "1"
            env["MAATBH_MOVE_TO_STORAGE"] = "1" if self.move_to_storage_var.get() else "0"
            env["MAATBH_MOVE_TO_STORAGE_AFTER_NON_BLUE_BOX"] = (
                "1" if self.move_to_storage_after_non_blue_var.get() else "0"
            )
            env["MAATBH_REPEAT_SAME_LEVEL_AFTER_BLUE_CHEST"] = (
                "1" if self.repeat_same_level_var.get() else "0"
            )
            env["PYTHONUNBUFFERED"] = "1"
            env["PYTHONIOENCODING"] = "utf-8"
            self.write_bot_console_log(f"=== Input mode: {input_mode} ===\n")
            self.write_bot_console_log(
                f"=== Recognition mode: {self.get_selected_recognition_mode()} ===\n"
            )
            self.write_bot_console_log(
                f"=== Move backpack to storage: {'on' if self.move_to_storage_var.get() else 'off'} ===\n"
            )
            self.write_bot_console_log(
                "=== Move backpack to storage after non-blue box: "
                f"{'on' if self.move_to_storage_after_non_blue_var.get() else 'off'} ===\n"
            )
            self.write_bot_console_log(
                f"=== Repeat same level after blue chest: {'on' if self.repeat_same_level_var.get() else 'off'} ===\n"
            )
            bot_command = (
                [sys.executable, "--bot"]
                if frozen_app
                else [sys.executable, "-u", str(MAIN_FILE)]
            )

            self.bot_process = subprocess.Popen(
                bot_command,
                cwd=str(BASE_DIR),
                stdin=subprocess.PIPE,
                stdout=self.bot_log_handle,
                stderr=subprocess.STDOUT,
                creationflags=creationflags,
                env=env,
            )
            if self.bot_process.stdin is not None:
                self.bot_process.stdin.close()
            if input_mode == "background":
                self.status_var.set("MAA 已启动：后台输入实验模式。若游戏无响应，请关闭该选项。")
            else:
                self.status_var.set("MAA 已启动：前台鼠标模式。")
        except Exception as e:
            self.close_bot_log_handle()
            self.bot_process = None
            messagebox.showerror("启动失败", f"无法启动 main.py：\n\n{e}")

    def stop_bot(self):
        if not self.stop_bot_process():
            self.status_var.set("MAA 当前没有运行。")

    def export_debug_zip(self):
        self.prepare_debug_export_logs()

        default_path = get_export_default_path(BASE_DIR)
        zip_path = filedialog.asksaveasfilename(
            title="导出报错log压缩包",
            initialdir=str(default_path.parent),
            initialfile=default_path.name,
            defaultextension=".zip",
            filetypes=[("ZIP 压缩包", "*.zip"), ("所有文件", "*.*")],
        )

        if not zip_path:
            self.status_var.set("已取消导出报错log压缩包；日志已保留。")
            return

        zip_path = refresh_stale_debug_zip_selection(zip_path, default_path)

        self.prepare_debug_export_logs()

        try:
            result = export_debug_zip(
                BASE_DIR,
                zip_path,
                gui_console_text=self.get_gui_console_text(),
            )
        except Exception as e:
            messagebox.showerror("导出报错log压缩包失败", f"无法导出报错log压缩包：\n\n{e}")
            self.status_var.set("导出报错log压缩包失败；日志已保留。")
            return

        cleanup_allowed = (
            result.get("has_runtime_evidence")
            and not result.get("is_stale_export")
        )

        if cleanup_allowed:
            cleanup = self.clear_generated_debug_files_after_safe_event("debug_zip_exported")
            cleanup_message = f"已清理生成的调试文件：{len(cleanup['removed'])}"
        else:
            cleanup = {"removed": [], "failed": []}
            cleanup_message = "生成的调试文件未清理。"

        message = (
            f"调试压缩包已导出：\n{Path(result['zip_path']).name}\n\n"
            f"ZIP 路径：{result['zip_path']}\n"
            f"已包含文件：{len(result['included'])}\n"
            f"缺失的可选文件：{len(result['missing'])}\n"
            f"包含运行证据：{result.get('has_runtime_evidence')}\n"
            f"检测到警告：{result.get('has_warnings')}\n"
            f"{cleanup_message}"
        )

        if cleanup["failed"]:
            message += f"\n清理跳过或失败的文件数：{len(cleanup['failed'])}"

        if not result.get("has_runtime_evidence"):
            message += (
                "\n\n调试压缩包没有包含运行证据，可能是旧导出，"
                "或从错误文件夹导出。"
            )
            messagebox.showwarning("导出调试压缩包", message)
            self.status_var.set("调试压缩包已导出，但没有运行证据；日志已保留。")
        elif result.get("is_stale_export"):
            message += (
                "\n\n调试压缩包导出时发现旧证据或缺失证据警告。"
                "生成的调试文件未清理。"
            )
            messagebox.showwarning("导出调试压缩包", message)
            self.status_var.set("调试压缩包已导出，但有警告；日志已保留。")
        elif result.get("has_warnings"):
            message += "\n\n调试压缩包已导出，但有警告。请查看 debug_manifest.txt。"
            messagebox.showwarning("导出调试压缩包", message)
            self.status_var.set(f"调试压缩包已导出，但有警告：{Path(result['zip_path']).name}")
        else:
            messagebox.showinfo("导出调试压缩包", message)
            self.status_var.set(f"调试压缩包已导出：{Path(result['zip_path']).name}")

    def prepare_debug_export_logs(self):
        if self.bot_log_handle is not None:
            try:
                self.bot_log_handle.flush()
            except Exception:
                pass

        try:
            self.refresh_process_log()
        except Exception:
            pass

    def current_timestamp(self):
        from datetime import datetime

        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def write_bot_console_log(self, text):
        if self.bot_log_handle is None:
            return

        try:
            self.bot_log_handle.write(sanitize_text_for_output(text))
        except UnicodeEncodeError:
            fallback = sanitize_text_for_output(text).encode(
                "utf-8",
                errors="replace",
            ).decode("utf-8", errors="replace")
            self.bot_log_handle.write(fallback)

    def clear_generated_debug_files_after_safe_event(self, reason):
        cleanup = clear_generated_debug_files(BASE_DIR)

        if cleanup["failed"]:
            self.append_log_text(
                "\n[GUI] 调试文件清理时有跳过或失败项，触发事件："
                f"{reason}:\n"
                + "\n".join(f"- {path}: {error}" for path, error in cleanup["failed"])
                + "\n"
            )

        return cleanup

    def cleanup_after_clean_stop(self, process_exit_code=None, closing=False):
        if has_significant_error(BASE_DIR, process_exit_code=process_exit_code):
            if not closing:
                self.status_var.set("MAA 已停止；检测到错误，调试文件已保留。")
            return

        cleanup = self.clear_generated_debug_files_after_safe_event("clean_bot_stop")

        if not closing:
            self.status_var.set(f"MAA 已正常停止；已清理 {len(cleanup['removed'])} 个生成的调试文件。")

    def stop_bot_process(self, closing=False):
        if self.bot_process is None:
            return False

        process = self.bot_process

        existing_code = process.poll()

        if existing_code is not None:
            self.bot_process = None
            self.close_bot_log_handle()
            self.cleanup_after_clean_stop(process_exit_code=existing_code, closing=closing)
            return False

        stop_failed = False

        try:
            if self.bot_log_handle is not None:
                self.write_bot_console_log("=== GUI requested bot shutdown ===\n")
                self.bot_log_handle.flush()

            process.terminate()

            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                if os.name == "nt":
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    )
                else:
                    process.kill()

                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3)

            if not closing:
                self.status_var.set("MAA 已停止。")
        except Exception as e:
            stop_failed = True
            if not closing:
                messagebox.showerror("停止 MAA 失败", f"无法停止 MAA：\n\n{e}")
        finally:
            self.bot_process = None
            self.close_bot_log_handle()

            if not stop_failed:
                self.cleanup_after_clean_stop(process_exit_code=None, closing=closing)

        return True

    def refresh_bot_status(self):
        if self.is_closing:
            return

        self.refresh_process_log()

        if self.bot_process is not None:
            code = self.bot_process.poll()

            if code is not None:
                self.status_var.set(f"MAA 已结束，退出码：{code}")
                self.bot_process = None
                self.close_bot_log_handle()
                self.cleanup_after_clean_stop(process_exit_code=code)

        if not self.is_closing:
            self.root.after(1000, self.refresh_bot_status)

    def close_bot_log_handle(self):
        if self.bot_log_handle is not None:
            try:
                self.bot_log_handle.close()
            except Exception:
                pass

            self.bot_log_handle = None

    def clear_log_text(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state="disabled")

    def append_log_text(self, text):
        if not text:
            return

        text = sanitize_text_for_output(text).replace("\x00", "")

        if not text:
            return

        self.log_text.configure(state="normal")
        self.log_text.insert(tk.END, text)
        self.log_text.see(tk.END)
        self.log_text.configure(state="disabled")

    def get_gui_console_text(self):
        try:
            return self.log_text.get("1.0", tk.END).strip()
        except Exception:
            return ""

    def refresh_process_log(self):
        if not BOT_CONSOLE_LOG.exists():
            return

        try:
            file_size = BOT_CONSOLE_LOG.stat().st_size

            if self.log_read_position > file_size:
                self.log_read_position = 0

            with open(BOT_CONSOLE_LOG, "r", encoding="utf-8", errors="replace") as f:
                f.seek(self.log_read_position)
                text = f.read()
                self.log_read_position = f.tell()

            self.append_log_text(text)
            self.handle_navigation_failure_warning(text)
        except Exception as e:
            self.append_log_text(f"\n[GUI] 无法读取 MAA 日志：{e}\n")

    def handle_navigation_failure_warning(self, text):
        if "USER WARNING: Navigation failed" not in text:
            return

        warning_lines = [
            line.strip()
            for line in text.splitlines()
            if "USER WARNING: Navigation failed" in line
        ]

        if not warning_lines:
            return

        for warning in warning_lines:
            key = self.make_navigation_failure_warning_key(warning)

            if key in self.notified_warning_keys:
                self.append_log_text(
                    f"\n[GUI] GUI warning suppressed after first notification | key={key}\n"
                )
                continue

            self.notified_warning_keys.add(key)
            self.last_navigation_failure_warning = warning
            self.status_var.set("某条路线导航失败，已跳过并继续。建议导出调试压缩包。")
            messagebox.showwarning(
                "路线已跳过",
                warning.replace("USER WARNING: ", "")
            )

    def make_navigation_failure_warning_key(self, warning):
        route_match = re.search(r"Route\s+(\d+)", warning)
        route = route_match.group(1) if route_match else "unknown_route"

        target = "unknown_target"
        target_match = re.search(
            r"Route\s+\d+:\s*(.*?)\.\s*The route was skipped",
            warning,
        )

        if target_match:
            target = target_match.group(1).strip()

        reason = "navigation_failed"
        reason_match = re.search(r"reason=([^|\]]+)", warning)

        if reason_match:
            reason = reason_match.group(1).strip()

        return f"navigation_failure|route={route}|target={target}|reason={reason}"

    def on_close(self):
        self.is_closing = True
        self.unregister_emergency_hotkey()
        self.stop_bot_process(closing=True)
        self.close_bot_log_handle()
        self.root.destroy()

    def load_existing_plan(self, silent=False):
        if not os.path.exists(OUTPUT_FILE):
            if not silent:
                messagebox.showinfo("没有找到路线文件", f"{OUTPUT_FILE.name} 不存在。")
            return

        try:
            with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                plan = json.load(f)

            if not isinstance(plan, list):
                raise ValueError("farm_plan.json 必须是一个列表。")

            self.selected_routes = plan
            if plan:
                first_route = plan[0]

                if "no_chest_retries" in first_route:
                    retries = first_route.get("no_chest_retries")
                elif "max_trials_if_no_chest" in first_route:
                    retries = first_route.get("max_trials_if_no_chest", 1)
                else:
                    retries = self.get_default_no_chest_retries()

                try:
                    if "no_chest_retries" not in first_route and "max_trials_if_no_chest" in first_route:
                        retries = int(retries) - 1

                    retries = max(0, int(retries))
                    self.no_chest_retries_var.set(str(retries))
                except (TypeError, ValueError):
                    self.no_chest_retries_var.set(str(self.get_default_no_chest_retries()))

            self.refresh_plan_listbox()

            if not silent:
                messagebox.showinfo("读取成功", f"已从 {OUTPUT_FILE.name} 读取 {len(plan)} 条路线。")

            self.status_var.set(f"已读取 {len(plan)} 条路线。")

        except Exception as e:
            messagebox.showerror("读取失败", f"无法读取 {OUTPUT_FILE.name}：\n\n{e}")


if __name__ == "__main__":
    if "--bot" in sys.argv:
        import main

        main.run_main_with_fatal_logging()
    else:
        root = tk.Tk()
        app = RoutePlannerApp(root)
        root.mainloop()
