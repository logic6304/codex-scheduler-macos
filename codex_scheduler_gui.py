#!/usr/bin/env python3
"""Tk-based macOS GUI for Codex Scheduler.

The GUI delegates scheduling and automation to the tested CLI module so both
entry points use the same config format and launchd behavior.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

import codex_scheduler as scheduler


ROOT = Path(__file__).resolve().parent
CLI = ROOT / "codex_scheduler.py"


class SchedulerGUI(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Codex 定时唤醒")
        self.geometry("720x680")
        self.minsize(640, 600)
        self.configure(bg="#f4f6fb")

        config = scheduler.load_config()
        self.time_var = tk.StringVar(value=str(config.get("time", "09:00")))
        self.date_var = tk.StringVar(value=str(config.get("date") or ""))
        self.prompt_var = tk.StringVar(value=str(config.get("prompt", "hello")))
        self.app_var = tk.StringVar(value=str(config.get("app", "auto")))
        self.method_var = tk.StringVar(value=str(config.get("method", "deeplink")))
        self.workspace_var = tk.StringVar(value=str(config.get("workspace_path") or ""))
        self.shortcut_var = tk.StringVar(value=str(config.get("new_chat_shortcut", "cmd+option+n")))
        self.status_var = tk.StringVar(value="正在读取状态…")
        self.busy = False

        self._build_style()
        self._build_ui()
        self.refresh_status()

    def _build_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("aqua")
        except tk.TclError:
            pass
        style.configure("App.TFrame", background="#f4f6fb")
        style.configure("Card.TLabelframe", background="#ffffff", padding=14)
        style.configure("Card.TLabelframe.Label", background="#ffffff", foreground="#26324a", font=("SF Pro Display", 12, "bold"))
        style.configure("Title.TLabel", background="#f4f6fb", foreground="#15203b", font=("SF Pro Display", 24, "bold"))
        style.configure("Subtitle.TLabel", background="#f4f6fb", foreground="#5e6b85", font=("SF Pro Text", 11))
        style.configure("Status.TLabel", background="#e8efff", foreground="#244b9b", padding=(10, 8))
        style.configure("Primary.TButton", padding=(14, 8))
        style.configure("Danger.TButton", foreground="#9c2f3e", padding=(14, 8))

    def _build_ui(self) -> None:
        outer = ttk.Frame(self, style="App.TFrame", padding=(28, 24, 28, 20))
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(3, weight=1)
        outer.rowconfigure(4, weight=1)

        ttk.Label(outer, text="Codex 定时唤醒", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            outer,
            text="设置一次，macOS 会在后台按时打开 Codex 新聊天并发送短消息。",
            style="Subtitle.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(4, 16))
        ttk.Label(outer, textvariable=self.status_var, style="Status.TLabel").grid(row=2, column=0, sticky="ew", pady=(0, 14))

        card = ttk.LabelFrame(outer, text="定时任务", style="Card.TLabelframe")
        card.grid(row=3, column=0, sticky="nsew")
        card.columnconfigure(1, weight=1)

        self._field(card, 0, "时间", self.time_var, "HH:MM，例如 08:30")
        self._field(card, 1, "日期", self.date_var, "留空表示每天运行")
        self._field(card, 2, "发送内容", self.prompt_var, "建议使用短的 ASCII 文本，例如 hello")

        ttk.Label(card, text="应用", anchor="e").grid(row=3, column=0, sticky="e", padx=(0, 12), pady=8)
        app_box = ttk.Combobox(card, textvariable=self.app_var, values=("auto", "ChatGPT", "Codex"), state="normal")
        app_box.grid(row=3, column=1, sticky="ew", pady=8)
        ttk.Label(card, text="auto 会优先查找 Codex.app，否则使用 ChatGPT.app", foreground="#6a7488").grid(row=3, column=2, sticky="w", padx=(12, 0))

        ttk.Label(card, text="创建方式", anchor="e").grid(row=4, column=0, sticky="e", padx=(0, 12), pady=8)
        method_box = ttk.Combobox(card, textvariable=self.method_var, values=("deeplink", "keyboard"), state="readonly")
        method_box.grid(row=4, column=1, sticky="ew", pady=8)
        ttk.Label(card, text="推荐 deeplink；旧版本可尝试 keyboard", foreground="#6a7488").grid(row=4, column=2, sticky="w", padx=(12, 0))

        ttk.Label(card, text="工作区", anchor="e").grid(row=5, column=0, sticky="e", padx=(0, 12), pady=8)
        ttk.Entry(card, textvariable=self.workspace_var).grid(row=5, column=1, sticky="ew", pady=8)
        ttk.Button(card, text="选择…", command=self.choose_workspace).grid(row=5, column=2, sticky="w", padx=(12, 0))

        ttk.Label(card, text="备用快捷键", anchor="e").grid(row=6, column=0, sticky="e", padx=(0, 12), pady=8)
        ttk.Entry(card, textvariable=self.shortcut_var).grid(row=6, column=1, sticky="ew", pady=8)
        ttk.Label(card, text="仅 keyboard 模式使用", foreground="#6a7488").grid(row=6, column=2, sticky="w", padx=(12, 0))

        action_bar = ttk.Frame(card)
        action_bar.grid(row=7, column=0, columnspan=3, sticky="ew", pady=(18, 0))
        action_bar.columnconfigure(0, weight=1)
        ttk.Button(action_bar, text="保存设置并启用", style="Primary.TButton", command=self.install).grid(row=0, column=0, sticky="w")
        ttk.Button(action_bar, text="立即发送", command=self.run_now).grid(row=0, column=1, padx=(8, 0))
        ttk.Button(action_bar, text="预览脚本", command=self.preview).grid(row=0, column=2, padx=(8, 0))
        ttk.Button(action_bar, text="停用定时任务", style="Danger.TButton", command=self.uninstall).grid(row=0, column=3, padx=(8, 0))

        ttk.Label(
            card,
            text="注意：只填写时间不会生效，必须点击“保存设置并启用”。保存成功后可在下方看到后台任务状态。",
            foreground="#9a5b18",
            wraplength=620,
        ).grid(row=8, column=0, columnspan=3, sticky="w", pady=(12, 0))

        log_card = ttk.LabelFrame(outer, text="最近输出", style="Card.TLabelframe")
        log_card.grid(row=4, column=0, sticky="nsew", pady=(14, 0))
        log_card.columnconfigure(0, weight=1)
        log_card.rowconfigure(0, weight=1)
        self.output = ScrolledText(log_card, height=7, wrap="word", font=("SF Mono", 10), relief="flat", background="#fbfcff")
        self.output.grid(row=0, column=0, sticky="nsew")
        ttk.Button(log_card, text="打开日志文件", command=self.open_log).grid(row=1, column=0, sticky="w", pady=(10, 0))

    @staticmethod
    def _field(parent: ttk.Widget, row: int, label: str, variable: tk.StringVar, hint: str) -> None:
        ttk.Label(parent, text=label, anchor="e").grid(row=row, column=0, sticky="e", padx=(0, 12), pady=8)
        ttk.Entry(parent, textvariable=variable).grid(row=row, column=1, sticky="ew", pady=8)
        ttk.Label(parent, text=hint, foreground="#6a7488").grid(row=row, column=2, sticky="w", padx=(12, 0))

    def choose_workspace(self) -> None:
        selected = filedialog.askdirectory(title="选择 Codex 工作区")
        if selected:
            self.workspace_var.set(selected)

    def _config_from_ui(self) -> dict[str, object]:
        time_text = self.time_var.get().strip()
        scheduler.parse_time(time_text)
        date_text = self.date_var.get().strip()
        if date_text:
            scheduler.parse_date(date_text)
        prompt = self.prompt_var.get()
        if not prompt.strip():
            raise ValueError("发送内容不能为空")
        config = dict(scheduler.DEFAULT_CONFIG)
        config.update(
            {
                "time": time_text,
                "date": date_text or None,
                "app": self.app_var.get().strip() or "auto",
                "prompt": prompt,
                "method": self.method_var.get(),
                "workspace_path": self.workspace_var.get().strip() or None,
                "new_chat_shortcut": self.shortcut_var.get().strip() or "cmd+option+n",
            }
        )
        scheduler.validate_config(config)
        return config

    def _install_args(self) -> list[str]:
        config = self._config_from_ui()
        date_text = str(config["date"] or "")
        args = [sys.executable, str(CLI), "install", "--time", str(config["time"])]
        if date_text:
            args.extend(["--date", date_text])
        args.extend(["--app", str(config["app"]), "--prompt", str(config["prompt"])])
        args.extend(["--method", str(config["method"]), "--shortcut", str(config["new_chat_shortcut"])])
        workspace = str(config["workspace_path"] or "")
        if workspace:
            args.extend(["--workspace", workspace])
        return args

    def _run_async(self, args: list[str], done_message: str) -> None:
        if self.busy:
            return
        self.busy = True
        self.status_var.set("正在执行…")
        self._append("$ " + " ".join(args[2:]) + "\n")

        def worker() -> None:
            try:
                result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, check=False)
                output = (result.stdout + result.stderr).strip() or "（无输出）"
                self.after(0, lambda: self._finish(result.returncode, output, done_message))
            except OSError as exc:
                self.after(0, lambda: self._finish(1, str(exc), "执行失败"))

        threading.Thread(target=worker, daemon=True).start()

    def _finish(self, code: int, output: str, message: str) -> None:
        self.busy = False
        self._append(output + "\n")
        if code == 0:
            self.status_var.set(message)
        else:
            self.status_var.set("执行失败，请查看输出")
            messagebox.showerror("Codex Scheduler", output)

    def _append(self, text: str) -> None:
        self.output.insert("end", text)
        self.output.see("end")

    def install(self) -> None:
        try:
            args = self._install_args()
        except (ValueError, TypeError, OSError) as exc:
            messagebox.showerror("设置无效", str(exc))
            return
        self._run_async(args, "已保存并启用定时任务")

    def run_now(self) -> None:
        if not messagebox.askyesno("确认发送", "现在打开 Codex 并发送这条消息吗？"):
            return
        try:
            config = self._config_from_ui()
            scheduler.save_config(config)
        except (ValueError, TypeError, OSError) as exc:
            messagebox.showerror("设置无效", str(exc))
            return
        self._run_async([sys.executable, str(CLI), "run"], "已请求发送消息")

    def preview(self) -> None:
        try:
            config = self._config_from_ui()
            scheduler.save_config(config)
        except (ValueError, TypeError, OSError) as exc:
            messagebox.showerror("设置无效", str(exc))
            return
        self._run_async([sys.executable, str(CLI), "run", "--dry-run"], "预览完成")

    def uninstall(self) -> None:
        if not messagebox.askyesno("确认停用", "停用后台定时任务吗？"):
            return
        self._run_async([sys.executable, str(CLI), "uninstall"], "已停用定时任务")

    def refresh_status(self) -> None:
        self._run_async([sys.executable, str(CLI), "status"], "状态已刷新")

    def open_log(self) -> None:
        if not scheduler.LOG_PATH.exists():
            messagebox.showinfo("日志", "还没有日志文件。")
            return
        subprocess.run(["open", "-a", "TextEdit", str(scheduler.LOG_PATH)], check=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Codex Scheduler GUI")
    parser.add_argument("--self-test", action="store_true", help="只验证模块可导入，不打开窗口")
    args = parser.parse_args(argv)
    if args.self_test:
        print("Codex Scheduler GUI import OK")
        return 0
    app = SchedulerGUI()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
