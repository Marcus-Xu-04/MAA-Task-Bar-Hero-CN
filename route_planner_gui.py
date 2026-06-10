# MAA Task Bar Hero
# Concept and direction by Marcus Xu.
# Built with Codex as a coding assistant.
# Shared for learning, experimentation, and automation research.

import json
import os
from pathlib import Path
import subprocess
import sys
import tkinter as tk
from tkinter import scrolledtext
from tkinter import messagebox

from route_config import AVAILABLE_LEVELS


BASE_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
OUTPUT_FILE = BASE_DIR / "farm_plan.json"
MAIN_FILE = BASE_DIR / "main.py"
BOT_CONSOLE_LOG = BASE_DIR / "bot_console.log"
APP_VERSION = "2026.06.09"


class RoutePlannerApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"MAA Task Bar Hero Planner - {APP_VERSION}")
        self.root.geometry("980x760")

        self.selected_routes = []
        self.bot_process = None
        self.bot_log_handle = None
        self.log_read_position = 0
        self.is_closing = False
        self.status_var = tk.StringVar(value="就绪：选择路线后可以保存并启动 Bot。")
        self.background_input_var = tk.BooleanVar(value=False)

        root.columnconfigure(0, weight=1)
        root.columnconfigure(2, weight=1)
        root.rowconfigure(1, weight=1)
        root.rowconfigure(11, weight=1)

        # Left side: available levels
        tk.Label(root, text="可用刷图目标").grid(row=0, column=0, padx=10, pady=(10, 0))

        self.available_listbox = tk.Listbox(root, width=52, height=22)
        self.available_listbox.grid(row=1, column=0, padx=10, pady=10, rowspan=8)

        # Middle buttons
        tk.Button(root, text="添加 →", width=14, command=self.add_selected).grid(row=1, column=1, pady=5)
        tk.Button(root, text="← 移除", width=14, command=self.remove_selected).grid(row=2, column=1, pady=5)
        tk.Button(root, text="上移", width=14, command=self.move_up).grid(row=3, column=1, pady=5)
        tk.Button(root, text="下移", width=14, command=self.move_down).grid(row=4, column=1, pady=5)
        tk.Button(root, text="清空路线", width=14, command=self.clear_plan).grid(row=5, column=1, pady=5)
        tk.Button(root, text="保存路线", width=14, command=self.save_plan).grid(row=6, column=1, pady=5)
        tk.Button(root, text="读取路线", width=14, command=self.load_existing_plan).grid(row=7, column=1, pady=5)

        # Right side: selected route cycle
        tk.Label(root, text="当前刷图循环顺序").grid(row=0, column=2, padx=10, pady=(10, 0))

        self.plan_listbox = tk.Listbox(root, width=52, height=22)
        self.plan_listbox.grid(row=1, column=2, padx=10, pady=10, rowspan=8)

        help_text = (
            "使用说明：\n\n"
            "挂机时，请确保英雄页面与地图保持打开状态，且日志窗口已启动并固定\n"
            "左侧：目前已建立可执行的刷图目标\n"
            "右侧：main.py 实际会循环执行的刷图顺序。\n"
            "带有【未开放】的关卡会显示出来 主播暂时还没通关到后面 会慢慢更新的！\n"
            "更多功能开发中！欢迎提供关卡截图素材和建议！也欢迎反馈BUG与优化路径！\n"
            "有问题请私信B站UP主 没变成彩天鹅的笔小鸭 ~\n"
        )

        tk.Label(root, text=help_text, justify="left").grid(
            row=9, column=0, columnspan=3, padx=10, pady=10
        )

        control_frame = tk.Frame(root)
        control_frame.grid(row=10, column=0, columnspan=3, sticky="ew", padx=10, pady=(0, 10))
        control_frame.columnconfigure(2, weight=1)

        tk.Button(
            control_frame,
            text="保存并启动 Bot",
            width=18,
            command=self.start_bot,
        ).grid(row=0, column=0, padx=(0, 8), pady=4)

        tk.Button(
            control_frame,
            text="停止 Bot",
            width=14,
            command=self.stop_bot,
        ).grid(row=0, column=1, padx=(0, 8), pady=4)

        tk.Label(
            control_frame,
            textvariable=self.status_var,
            anchor="w",
        ).grid(row=0, column=2, sticky="ew", pady=4)

        tk.Checkbutton(
            control_frame,
            text="全自动后台挂机（实验版）",
            variable=self.background_input_var,
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(2, 0))

        tk.Label(
            control_frame,
            text=f"Concept & direction by Marcus Xu · Build {APP_VERSION}",
            anchor="e",
            fg="#666666",
        ).grid(row=1, column=2, sticky="e", pady=(2, 0))

        log_frame = tk.LabelFrame(root, text="Bot 运行日志")
        log_frame.grid(row=11, column=0, columnspan=3, sticky="nsew", padx=10, pady=(0, 10))
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
        self.root.after(1000, self.refresh_bot_status)

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
        # 如果 route_config.py 里已经写了 display_name，就优先用它
        if "display_name" in level:
            return level["display_name"]

        difficulty = self.format_difficulty_cn(level["difficulty"])
        chapter = self.format_chapter_cn(level["chapter"])
        stage = level["level"]

        return f"{difficulty} | {chapter} | {stage}"

    def populate_available_levels(self):
        self.available_listbox.delete(0, tk.END)

        for level in AVAILABLE_LEVELS:
            label = self.format_level_label(level)

            if not level.get("enabled", True):
                note = level.get("note", "")
                label = f"【未开放】{label}"

                if note:
                    label += f" — {note}"

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
        level = AVAILABLE_LEVELS[index]

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

        plan = []

        for i, level in enumerate(self.selected_routes, start=1):
            route = level.copy()
            route["name"] = f"Route {i}"
            plan.append(route)

        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(plan, f, indent=4, ensure_ascii=False)

        self.status_var.set(f"已保存 {len(plan)} 条路线到 {OUTPUT_FILE.name}。")

        if show_message:
            messagebox.showinfo("保存成功", f"刷图路线已保存到 {OUTPUT_FILE.name}")

        return True

    def start_bot(self):
        if self.bot_process is not None and self.bot_process.poll() is None:
            messagebox.showinfo("Bot 已在运行", "别急！")
            return

        if not self.save_plan(show_message=False):
            return

        frozen_app = getattr(sys, "frozen", False)

        if not frozen_app and not MAIN_FILE.exists():
            messagebox.showerror("寄！启动失败", f"找不到 {MAIN_FILE}")
            return

        try:
            self.close_bot_log_handle()
            self.clear_log_text()
            self.log_read_position = 0
            self.bot_log_handle = open(BOT_CONSOLE_LOG, "w", encoding="utf-8", buffering=1)
            self.bot_log_handle.write("=== Bot process started ===\n")

            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            env = os.environ.copy()
            input_mode = "background" if self.background_input_var.get() else "foreground"
            env["MAATBH_INPUT_MODE"] = input_mode
            env["MAATBH_SHOW_PREVIEW"] = "0"
            env["MAATBH_ENABLE_BEEP"] = "0"
            env["MAATBH_AUTO_OPEN_BLUE"] = "1"
            env["MAATBH_NAVIGATE_ON_START"] = "1"
            env["PYTHONUNBUFFERED"] = "1"
            self.bot_log_handle.write(f"=== Input mode: {input_mode} ===\n")

            bot_command = (
                [sys.executable, "--bot"]
                if frozen_app
                else [sys.executable, "-u", str(MAIN_FILE)]
            )

            self.bot_process = subprocess.Popen(
                bot_command,
                cwd=str(BASE_DIR),
                stdin=subprocess.DEVNULL,
                stdout=self.bot_log_handle,
                stderr=subprocess.STDOUT,
                creationflags=creationflags,
                env=env,
            )
            if input_mode == "background":
                self.status_var.set("Bot 已启动：后台输入实验模式。若游戏无反应，请关闭该选项。")
            else:
                self.status_var.set("Bot 已启动：前台鼠标模式。")
        except Exception as e:
            self.close_bot_log_handle()
            self.bot_process = None
            messagebox.showerror("寄！启动失败", f"无法启动 main.py：\n\n{e}")

    def stop_bot(self):
        if not self.stop_bot_process():
            self.status_var.set("Bot 当前没有运行。")

    def stop_bot_process(self, closing=False):
        if self.bot_process is None:
            return False

        process = self.bot_process

        if process.poll() is not None:
            self.bot_process = None
            self.close_bot_log_handle()
            return False

        try:
            if self.bot_log_handle is not None:
                self.bot_log_handle.write("=== GUI requested bot shutdown ===\n")
                self.bot_log_handle.flush()

            process.terminate()

            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)

            if not closing:
                self.status_var.set("Bot 已停止。")
        except Exception as e:
            if not closing:
                messagebox.showerror("停止 Bot 失败", f"无法停止 Bot：\n\n{e}")
        finally:
            self.bot_process = None
            self.close_bot_log_handle()

        return True

    def refresh_bot_status(self):
        if self.is_closing:
            return

        self.refresh_process_log()

        if self.bot_process is not None:
            code = self.bot_process.poll()

            if code is not None:
                self.status_var.set(f"Bot 已结束，退出码：{code}")
                self.bot_process = None
                self.close_bot_log_handle()

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

        self.log_text.configure(state="normal")
        self.log_text.insert(tk.END, text)
        self.log_text.see(tk.END)
        self.log_text.configure(state="disabled")

    def refresh_process_log(self):
        if not BOT_CONSOLE_LOG.exists():
            return

        try:
            with open(BOT_CONSOLE_LOG, "r", encoding="utf-8", errors="replace") as f:
                f.seek(self.log_read_position)
                text = f.read()
                self.log_read_position = f.tell()

            self.append_log_text(text)
        except Exception as e:
            self.append_log_text(f"\n[GUI] 无法读取 Bot 日志：{e}\n")

    def on_close(self):
        self.is_closing = True
        self.stop_bot_process(closing=True)
        self.close_bot_log_handle()
        self.root.destroy()

    def load_existing_plan(self, silent=False):
        if not os.path.exists(OUTPUT_FILE):
            if not silent:
                messagebox.showinfo("没有找到路线文件", f"{OUTPUT_FILE.name} 不存在捏。")
            return

        try:
            with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                plan = json.load(f)

            if not isinstance(plan, list):
                raise ValueError("farm_plan.json 必须是一个列表。")

            self.selected_routes = plan
            self.refresh_plan_listbox()

            if not silent:
                messagebox.showinfo("读取成功", f"已从 {OUTPUT_FILE.name} 读取 {len(plan)} 条路线。")

            self.status_var.set(f"已读取 {len(plan)} 条路线。")

        except Exception as e:
            messagebox.showerror("读取失败", f"无法读取 {OUTPUT_FILE.name}：\n\n{e}")


if __name__ == "__main__":
    if "--bot" in sys.argv:
        import main

        main.main()
    else:
        root = tk.Tk()
        app = RoutePlannerApp(root)
        root.mainloop()
