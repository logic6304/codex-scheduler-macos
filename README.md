# Codex Scheduler for macOS

一个带 macOS GUI 的 Codex 后台定时器。它在指定时间由 `launchd` 启动，通过 Codex 官方桌面深链接打开新本地聊天，预填并发送一条很短的文本（默认 `hello`）。适合做个人自动化实验；它不使用 API key，也不读取或保存登录凭据。

仓库同时提供 `Codex Scheduler.app` 图形界面、`open_gui.command` 启动脚本和原来的 Python CLI。GUI 可以设置时间、日期、文本、工作区、创建方式，并执行启用、预览、立即发送和停用。

## 工作方式

1. `install` 将配置写入 `~/Library/Application Support/codex-scheduler/config.json`。
2. 它生成一个用户级 LaunchAgent：`~/Library/LaunchAgents/com.codex-scheduler.daily.plist`。
3. 到时间后，任务在当前用户的 GUI 会话中运行 `open -g codex://new?...`，再用一次 `osascript` 回车提交已预填的文本。

Codex 官方文档提供了 `codex://new?prompt=...` 深链接，但它只负责打开新聊天并预填 composer，不会自动发送；脚本因此只把回车交给当前 Codex 窗口。应用可能会短暂出现在前台，任务进程本身不会打开终端窗口。

## 安装

需要 macOS、Python 3.9+，并先在 ChatGPT/Codex 中完成登录。项目目录中运行：

最方便的方式是双击项目里的 `Codex Scheduler.app`。如果 Finder 没有直接打开权限，可以双击 `open_gui.command`，或者在终端运行：

```bash
python3 codex_scheduler_gui.py
```

GUI 的“保存并启用”按钮会写入 LaunchAgent；“立即发送”会先保存当前设置，再请求一次真实发送。首次使用建议先点“预览脚本”。

```bash
python3 codex_scheduler.py install --time 08:30
```

常用选项：

```bash
# 每天 23:10 发送自定义文本
python3 codex_scheduler.py install --time 23:10 --prompt hello

# 指定 ChatGPT.app；如果你的应用名是 Codex，可改成 --app Codex
python3 codex_scheduler.py install --time 08:30 --app ChatGPT

# 只在某个日期运行一次
python3 codex_scheduler.py install --time 08:30 --date 2026-12-01

# 如果希望新聊天附着到指定本地工作区
python3 codex_scheduler.py install --time 08:30 --workspace "$HOME/Documents/demo"
```

首次运行时，在“系统设置 → 隐私与安全性 → 辅助功能”中允许你实际运行该命令的终端或 Python 宿主控制 ChatGPT/Codex。若 macOS 还提示自动化权限，请允许该终端控制“系统事件”和目标应用。OpenAI 的官方说明也指出，macOS 桌面自动化需要辅助功能权限。[OpenAI 官方说明](https://developers.openai.com/training/walkthroughs/using-your-computer-and-browser#use-computer-browser-or-chrome)

默认使用 Codex 深链接，不需要猜测新聊天快捷键。官方文档列出了 `codex://new?prompt=...` 和 `codex://threads/new`；同时明确 `Cmd+Option+N` 是 ChatGPT Quick chat，不是 Codex standalone chat。[桌面命令文档](https://learn.chatgpt.com/docs/app/commands#deep-links)

如果你的旧版本没有深链接，可切换到键盘备用方案。默认备用快捷键是 `cmd+option+n`；为提高键盘模拟兼容性，发送内容建议使用短的 ASCII 文本，例如 `hello`：

```bash
python3 codex_scheduler.py install --time 08:30 --method keyboard --shortcut cmd+n
```

## 验证和管理

先只查看将要执行的 AppleScript，不会打开应用或消耗消息：

```bash
python3 codex_scheduler.py run --dry-run
```

安装后查看状态和日志：

```bash
python3 codex_scheduler.py status
tail -f "$HOME/Library/Logs/codex-scheduler.log"
```

卸载定时任务：

```bash
python3 codex_scheduler.py uninstall
```

## 限制

- 这是个人桌面自动化，不是 Codex 官方 API 或官方调度接口。应用更新、区域版本、登录状态和快捷键改变都可能影响结果。
- macOS 睡眠、注销或没有 GUI 会话时，执行时间可能延迟；LaunchAgent 会在用户登录后重新加载。
- “发送成功”只表示 `osascript` 没有报告错误，不代表服务端已经接受消息或一定改变了账户限额。请按自己的账户条款和平台规则使用，不要高频循环发送。
- 任何需要真实 UI 行为的改动，都应先用 `run --dry-run`，再在一个不会影响工作的时间手动执行一次。

## 发布到 GitHub

建议先在本地验证，再初始化仓库：

```bash
python3 -m unittest discover -s tests -v
git init
git add README.md codex_scheduler.py tests .gitignore LICENSE
git commit -m "Add macOS Codex scheduler"
```

MIT License，见 [LICENSE](LICENSE)。
