# Git 更新（ZHENG-maki 修改版，免费开源）

默认仓库：`ZHENG-maki/OurNotes-Auto`，默认分支：`main`。

双击原安装目录里的 `MFAAvalonia.exe`，启动时先检查并应用 Git 更新，再加载界面和任务配置。
「Git更新」直接集成在原 MFAAvalonia 的侧栏里，与首页、监控、截图并列；使用原生 SukiUI 控件，跟随原来的明暗主题。
页面显示最新 40 条本地提交（提交号、时间、作者和说明）、最近检查时间，以及可展开的更新详情。
不再使用 WinForms 外壳、嵌入窗口或额外的「打开演出／关闭演出窗口」按钮。

每次启动执行 `git fetch origin main` 和 `git rebase origin/main`。本地独有的已提交修改会重放在远端提交之后，不自动推送。
本地存在未提交修改、未结束的合并/rebase 或安装文件被另行修改时停止更新，保留文件并显示原因。
本次 rebase 发生冲突时自动 abort 回到更新前的本地提交；不会擅自处理原本就存在的冲突。
网络失败时仍可使用已安装版本，失败原因显示在 Git 更新页。

手动检查：结束当前任务后，在侧栏「Git更新」点击「检查更新」。此时只 fetch / rebase 同步源码，重新关闭并打开程序后再应用文件。
这样不会在原界面仍持有旧任务配置时替换资源。普通启动会自动同步并应用，无需手动检查。
运行中的任务持有锁时不部署文件，也不强制终止游戏或任务。

部署前核对已安装文件的哈希，旧文件放在 `backup/git-update-时间/`。
部署失败或 Python 模块导入检查失败时恢复已替换的文件。`config/`、`data/`、`cache/` 和本机配置不会从仓库覆盖。
为了保留 fork 的修改，检测到 `git-update.json` 时停用原上游 Release 更新器。

本机 `git-update.json` 的 `repository` 指向开发用 Git 工作区；该文件只保留在本机，不提交 Git。
更新器不执行 upstream 合并，也不自动更新 .NET、Python 依赖或 MFAA 二进制；涉及运行环境或 C# 页面变更需要重新编译安装。
Git 修改版会停用 MFAA 自带的上游界面／资源更新，避免覆盖原生 Git 页。

## 重新构建原生界面

需要 Git 和 .NET 10 SDK。运行 `python tools/build_native_ui.py`，脚本会取 MFAAvalonia v2.16.2 的固定源码提交 `1080d3e1500f3439ac896ab2eca9aeb8e885f1f4`，应用 `tools/native-ui/integration.patch` 和新增的 C#／AXAML 页面，再编译到 `cache/native-ui/publish`。
可用 `--source <源码路径> --out <输出路径>` 指定构建目录。重复执行会识别已经应用的补丁，不重复打补丁。

源码来自 [MFAAvalonia](https://github.com/SweetSmellFox/MFAAvalonia/tree/v2.16.2)，按 GPL-3.0 提供；修改源码与构建脚本随本仓库提供。安装时保留 `LICENSE-MFAA`，替换原生 EXE、入口 DLL 与 `libs/MFAAvalonia.Core.dll`，先备份旧文件。
旧 WinForms 启动器与改名前的 Core EXE 在本次安装的备份目录保留，不再作为启动入口。
