#!/usr/bin/env python3
"""Schedule a small prompt in the macOS ChatGPT/Codex desktop app.

The scheduler itself is silent: launchd starts this file in the user's GUI
session at the configured time. Codex's official deep link creates the chat;
the final submit action uses macOS Accessibility automation (System Events).
"""

from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import json
import logging
import os
import re
import plistlib
import subprocess
import sys
import tempfile
import textwrap
import urllib.parse
from pathlib import Path
from typing import Any


LABEL = "com.codex-scheduler.daily"
APP_SUPPORT = Path.home() / "Library" / "Application Support" / "codex-scheduler"
CONFIG_PATH = APP_SUPPORT / "config.json"
LOG_PATH = Path.home() / "Library" / "Logs" / "codex-scheduler.log"
PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
LOCK_PATH = APP_SUPPORT / "run.lock"

DEFAULT_CONFIG: dict[str, Any] = {
    "time": "09:00",
    "date": None,
    "app": "auto",
    "prompt": "hello",
    "method": "deeplink",
    "workspace_path": None,
    "new_chat_shortcut": "cmd+option+n",
    "open_delay_seconds": 3.0,
    "new_chat_delay_seconds": 1.2,
}


def setup_logging() -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.FileHandler(LOG_PATH, encoding="utf-8")],
    )


def parse_time(value: str) -> tuple[int, int]:
    if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value):
        raise argparse.ArgumentTypeError("时间必须是 HH:MM，例如 08:30")
    try:
        parsed = dt.datetime.strptime(value, "%H:%M")
    except ValueError as exc:
        raise argparse.ArgumentTypeError("时间必须是 HH:MM，例如 08:30") from exc
    return parsed.hour, parsed.minute


def parse_date(value: str) -> tuple[int, int, int]:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise argparse.ArgumentTypeError("日期必须是 YYYY-MM-DD，例如 2026-12-01")
    try:
        parsed = dt.datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise argparse.ArgumentTypeError("日期必须是 YYYY-MM-DD，例如 2026-12-01") from exc
    return parsed.year, parsed.month, parsed.day


def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    if not path.exists():
        return dict(DEFAULT_CONFIG)
    with path.open(encoding="utf-8") as handle:
        loaded = json.load(handle)
    if not isinstance(loaded, dict):
        raise ValueError(f"配置文件必须是 JSON 对象: {path}")
    config = dict(DEFAULT_CONFIG)
    config.update(loaded)
    validate_config(config)
    return config


def save_config(config: dict[str, Any], path: Path = CONFIG_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as tmp:
        json.dump(config, tmp, ensure_ascii=False, indent=2)
        tmp.write("\n")
        temporary = Path(tmp.name)
    temporary.replace(path)


def resolve_app(app: str) -> str:
    """Return the app name accepted by `open -a`.

    `auto` prefers a separately installed Codex app and falls back to the
    ChatGPT desktop app, which currently contains the Codex workspace.
    """
    if app != "auto":
        return app
    for candidate in ("Codex", "ChatGPT"):
        if Path(f"/Applications/{candidate}.app").exists() or Path.home().joinpath("Applications", f"{candidate}.app").exists():
            return candidate
    return "ChatGPT"


def shortcut_modifiers(shortcut: str) -> list[str]:
    parts = [part.strip().lower() for part in shortcut.split("+") if part.strip()]
    if not parts:
        raise ValueError("new_chat_shortcut 不能为空")
    key = parts[-1]
    modifiers = []
    for part in parts[:-1]:
        if part in {"cmd", "command", "⌘"}:
            modifiers.append("command down")
        elif part in {"option", "alt", "⌥"}:
            modifiers.append("option down")
        elif part in {"control", "ctrl", "⌃"}:
            modifiers.append("control down")
        elif part in {"shift", "⇧"}:
            modifiers.append("shift down")
        else:
            raise ValueError(f"不支持的快捷键修饰键: {part}")
    if not key or len(key) != 1:
        raise ValueError("快捷键最后一段必须是单个字符，例如 cmd+option+n")
    return [key, *modifiers]


def validate_config(config: dict[str, Any]) -> None:
    parse_time(str(config["time"]))
    if config.get("date"):
        parse_date(str(config["date"]))
    if config.get("method") not in {"deeplink", "keyboard"}:
        raise ValueError("method 必须是 deeplink 或 keyboard")
    shortcut_modifiers(str(config["new_chat_shortcut"]))
    for key in ("open_delay_seconds", "new_chat_delay_seconds"):
        if float(config[key]) < 0:
            raise ValueError(f"{key} 不能为负数")


def codex_deep_link(config: dict[str, Any]) -> str:
    query = {"prompt": str(config["prompt"])}
    if config.get("workspace_path"):
        query["path"] = str(Path(str(config["workspace_path"])).expanduser())
    encoded = urllib.parse.urlencode(query, quote_via=urllib.parse.quote)
    return f"codex://new?{encoded}"


def apple_script(config: dict[str, Any]) -> str:
    app = resolve_app(str(config["app"]))
    key, *modifiers = shortcut_modifiers(str(config["new_chat_shortcut"]))
    keypress = f'keystroke "{key}"'
    if modifiers:
        keypress += f" using {{{', '.join(modifiers)}}}"

    # Values are passed as AppleScript arguments, so prompt text cannot alter
    # the script itself or break its quoting.
    return textwrap.dedent(
        f"""
        on run argv
            set appName to item 1 of argv
            set promptText to item 2 of argv
            tell application appName to activate
            delay {float(config['open_delay_seconds']):.3f}
            tell application "System Events"
                tell process appName
                    {keypress}
                    delay {float(config['new_chat_delay_seconds']):.3f}
                    keystroke promptText
                    key code 36
                end tell
            end tell
        end run
        """
    ).strip() + "\n"


def submit_prefilled_script(config: dict[str, Any]) -> str:
    app = resolve_app(str(config["app"]))
    return textwrap.dedent(
        f"""
        on run argv
            set appName to item 1 of argv
            tell application appName to activate
            delay {float(config['open_delay_seconds']):.3f}
            tell application "System Events"
                tell process appName
                    key code 36
                end tell
            end tell
        end run
        """
    ).strip() + "\n"


def launch_agent(config: dict[str, Any], python_path: str = sys.executable) -> dict[str, Any]:
    hour, minute = parse_time(str(config["time"]))
    calendar: dict[str, int] = {"Hour": hour, "Minute": minute}
    if config.get("date"):
        year, month, day = parse_date(str(config["date"]))
        calendar.update({"Year": year, "Month": month, "Day": day})
    return {
        "Label": LABEL,
        "ProgramArguments": [python_path, str(Path(__file__).resolve()), "run"],
        "StartCalendarInterval": calendar,
        "RunAtLoad": False,
        "ProcessType": "Background",
        "LowPriorityIO": True,
        "StandardOutPath": str(LOG_PATH),
        "StandardErrorPath": str(LOG_PATH),
        "EnvironmentVariables": {"PYTHONUNBUFFERED": "1"},
    }


def install(config: dict[str, Any]) -> None:
    validate_config(config)
    APP_SUPPORT.mkdir(parents=True, exist_ok=True)
    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    save_config(config)
    with PLIST_PATH.open("wb") as handle:
        plistlib.dump(launch_agent(config), handle, sort_keys=False)

    # Unload an older copy if present, then load the new schedule. A missing
    # job is expected on first install, so the first command is best-effort.
    domain = f"gui/{os.getuid()}"
    subprocess.run(["launchctl", "bootout", domain, str(PLIST_PATH)], check=False, capture_output=True)
    try:
        subprocess.run(["launchctl", "bootstrap", domain, str(PLIST_PATH)], check=True, capture_output=True, text=True)
        subprocess.run(["launchctl", "print", f"{domain}/{LABEL}"], check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "未知错误").strip()
        logging.error("launchd install failed: %s", detail)
        raise RuntimeError(
            "无法启用 macOS 后台任务。请确认当前用户已登录桌面，并允许终端/Python 的自动化权限。\n"
            f"launchctl: {detail}"
        ) from exc
    logging.info("installed %s at %s", LABEL, config["time"])
    print(f"已安装：{PLIST_PATH}")
    print(f"日志：{LOG_PATH}")


def uninstall() -> None:
    subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}", str(PLIST_PATH)], check=False)
    if PLIST_PATH.exists():
        PLIST_PATH.unlink()
    print("已卸载定时任务。配置文件仍保留在：", CONFIG_PATH)


def run_once(config: dict[str, Any], dry_run: bool = False) -> int:
    app = resolve_app(str(config["app"]))
    method = str(config.get("method", "deeplink"))
    script = submit_prefilled_script(config) if method == "deeplink" else apple_script(config)
    if dry_run:
        print(f"app={app}")
        print(f"method={method}")
        print(f"prompt={config['prompt']}")
        if method == "deeplink":
            print(f"url={codex_deep_link(config)}")
        print(script)
        return 0

    APP_SUPPORT.mkdir(parents=True, exist_ok=True)
    with LOCK_PATH.open("w") as lock_handle:
        try:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            logging.info("another run is already active; exiting")
            return 0

        logging.info("opening %s and submitting prompt", app)
        try:
            if method == "deeplink":
                subprocess.run(["open", "-g", codex_deep_link(config)], check=True, capture_output=True, text=True)
            else:
                subprocess.run(["open", "-a", app], check=True, capture_output=True, text=True)
            result = subprocess.run(
                ["osascript", "-", app] if method == "deeplink" else ["osascript", "-", app, str(config["prompt"])],
                input=script,
                text=True,
                capture_output=True,
                check=False,
            )
        except OSError:
            logging.exception("failed to start macOS automation")
            return 1
        if result.returncode:
            logging.error("osascript failed (%s): %s", result.returncode, result.stderr.strip())
            return result.returncode
        logging.info("prompt submitted")
        return 0


def status() -> None:
    print(f"配置文件：{'已创建' if CONFIG_PATH.exists() else '未创建'}")
    print(f"LaunchAgent 文件：{'已创建' if PLIST_PATH.exists() else '未创建'}")
    domain = f"gui/{os.getuid()}"
    loaded = subprocess.run(["launchctl", "print", f"{domain}/{LABEL}"], capture_output=True, text=True, check=False).returncode == 0
    print(f"后台任务：{'已加载' if loaded else '未加载'}")
    if not CONFIG_PATH.exists():
        print("下一步：在 GUI 点击“保存设置并启用”。")
        return
    config = load_config()
    next_run = next_run_text(config)
    print(f"计划：{config['date'] + ' ' if config.get('date') else '每天 '}{config['time']}")
    print(f"下一次运行：{next_run}")
    print(f"应用：{resolve_app(str(config['app']))}")
    print(f"文本：{config['prompt']}")


def next_run_text(config: dict[str, Any]) -> str:
    now = dt.datetime.now().astimezone()
    hour, minute = parse_time(str(config["time"]))
    if config.get("date"):
        year, month, day = parse_date(str(config["date"]))
        scheduled = now.replace(year=year, month=month, day=day, hour=hour, minute=minute, second=0, microsecond=0)
        return scheduled.strftime("%Y-%m-%d %H:%M %Z") if scheduled >= now else "已过期（请重新设置日期）"
    scheduled = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if scheduled <= now:
        scheduled += dt.timedelta(days=1)
    return scheduled.strftime("%Y-%m-%d %H:%M %Z")


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="按时间在 macOS ChatGPT/Codex 中发送一个短消息")
    sub = parser.add_subparsers(dest="command", required=True)

    install_parser = sub.add_parser("install", help="写入配置并安装 launchd 后台任务")
    install_parser.add_argument("--time", required=True, type=parse_time, metavar="HH:MM")
    install_parser.add_argument("--date", type=parse_date, metavar="YYYY-MM-DD", help="只运行一次；不填则每天运行")
    install_parser.add_argument("--app", default="auto", help="应用名，默认 auto（Codex 或 ChatGPT）")
    install_parser.add_argument("--prompt", default="hello", help="发送的文本，默认 hello")
    install_parser.add_argument("--method", choices=("deeplink", "keyboard"), default="deeplink", help="默认使用 Codex 深链接；旧版本可用 keyboard")
    install_parser.add_argument("--workspace", help="可选的 Codex 本地工作区绝对路径")
    install_parser.add_argument("--shortcut", default="cmd+option+n", help="新聊天快捷键，默认 cmd+option+n")
    install_parser.add_argument("--open-delay", type=float, default=3.0)
    install_parser.add_argument("--new-chat-delay", type=float, default=1.2)

    sub.add_parser("uninstall", help="卸载 launchd 后台任务")
    sub.add_parser("status", help="查看配置和任务状态")
    run_parser = sub.add_parser("run", help="执行一次自动化（供 launchd 使用）")
    run_parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = make_parser().parse_args(argv)
    if args.command == "install":
        config = dict(DEFAULT_CONFIG)
        config.update(
            {
                "time": f"{args.time[0]:02d}:{args.time[1]:02d}",
                "date": f"{args.date[0]:04d}-{args.date[1]:02d}-{args.date[2]:02d}" if args.date else None,
                "app": args.app,
                "prompt": args.prompt,
                "method": args.method,
                "workspace_path": args.workspace,
                "new_chat_shortcut": args.shortcut,
                "open_delay_seconds": args.open_delay,
                "new_chat_delay_seconds": args.new_chat_delay,
            }
        )
        setup_logging()
        try:
            install(config)
        except (RuntimeError, OSError, ValueError) as exc:
            print(f"安装失败：{exc}", file=sys.stderr)
            return 1
        return 0
    if args.command == "uninstall":
        uninstall()
        return 0
    if args.command == "status":
        status()
        return 0
    config = load_config()
    if not args.dry_run:
        setup_logging()
    return run_once(config, dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
