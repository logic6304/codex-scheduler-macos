# Codex 定时唤醒（macOS）

这是一个给普通用户使用的 macOS 小工具：选择一个时间，Mac 会在后台打开 Codex 新聊天，填入一条短消息并提交。默认消息是 `hello`。

## 下载

打开 [GitHub Releases](https://github.com/logic6304/codex-scheduler-macos/releases)，下载最新的 `Codex-Scheduler-macOS-*.zip`，解压整个文件夹。

不要只把 `Codex Scheduler.app` 单独拖走。这个版本的 App 外壳需要和同一文件夹里的 Python 脚本一起使用。

电脑需要安装 Python 3。没有安装时，可以从 [python.org](https://www.python.org/downloads/macos/) 安装 macOS 版 Python。

## 第一次使用

1. 双击文件夹里的 **Codex Scheduler.app**。
2. 如果 macOS 阻止打开，右键 App，选择“打开”，再确认一次。
3. 在“时间”中输入目标时间，例如 `07:00`。
4. “日期”留空表示每天运行；填写 `2026-11-01` 表示只运行一次。
5. “发送内容”保持 `hello`，或改成你需要的短文本。
6. “创建方式”保持为 `deeplink`，选择工作区是可选的。
7. 点击 **保存设置并启用**。
8. 界面下方必须看到“后台任务：已加载”，并显示下一次运行时间，才表示设置成功。

只填写时间不会自动保存，也不会安装后台任务。

如果你在当天 07:00 之后才点击启用，下一次运行会是第二天 07:00；想立即验证请使用“立即发送”。

第一次建议先点击 **预览脚本**。它只显示将要执行的内容，不会打开 Codex，也不会发送消息。确认设置后，可以点击 **立即发送** 做一次真实测试；按钮会先询问确认。

## macOS 权限

首次执行时，macOS 可能会提示权限：

- 在“系统设置 → 隐私与安全性 → 辅助功能”中允许你启动程序的终端或 Python 控制 ChatGPT/Codex；
- 如果出现自动化提示，允许它控制“系统事件”和 ChatGPT/Codex。

OpenAI 的官方说明也要求 macOS 桌面自动化使用辅助功能权限。[查看官方说明](https://developers.openai.com/training/walkthroughs/using-your-computer-and-browser#use-computer-browser-or-chrome)

程序默认使用 Codex 官方 `codex://new?prompt=...` 深链接创建新本地聊天，再提交预填文本。[查看官方命令文档](https://learn.chatgpt.com/docs/app/commands#deep-links)

## 7:00 没有运行时怎么检查

在工具文件夹中打开终端，运行：

```bash
python3 codex_scheduler.py status
```

正常情况应看到：

```text
配置文件：已创建
LaunchAgent 文件：已创建
后台任务：已加载
下一次运行：...
```

如果显示“未创建”或“未加载”，重新打开 GUI，确认时间后点击 **保存设置并启用**。如果仍然失败，把 GUI 下方的输出和下面的日志内容一起保留：

```bash
tail -100 "$HOME/Library/Logs/codex-scheduler.log"
launchctl print "gui/$(id -u)/com.codex-scheduler.daily"
```

Mac 需要处于已登录的桌面会话。睡眠、关机、注销期间不会在屏幕上执行；唤醒后 macOS 可能会延迟执行。Codex 需要保持登录状态。

## 停用

打开 GUI 点击 **停用定时任务**，或者在终端运行：

```bash
python3 codex_scheduler.py uninstall
```

## 重要限制

- 这是个人桌面自动化，不是 Codex 官方调度 API。
- 应用更新、权限、登录状态或深链接行为变化都可能影响执行。
- 日志中的“prompt submitted”只表示本机自动化没有报错，不保证服务端已经接受消息，也不保证一定触发或改变五小时限额。
- 请按自己的账户条款使用，不要高频循环发送。
