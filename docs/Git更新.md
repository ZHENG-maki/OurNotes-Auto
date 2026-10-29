# Git 更新（ZHENG-maki 修改版，免费开源）

默认仓库：`ZHENG-maki/OurNotes-Auto`，默认分支：`main`。

双击原安装目录里的 `MFAAvalonia.exe`，启动界面先检查 Git 更新，再打开原演出程序。
「演出」页保留 MFAA 界面；「Git更新」页显示最新 40 条本地提交（提交号、时间、作者和说明），以及本次检查结果。

每次启动执行 `git fetch origin main` 和 `git rebase origin/main`。本地独有的已提交修改会重放在远端提交之后，不自动推送。
本地存在未提交修改、未结束的合并/rebase 或安装文件被另行修改时停止更新，保留文件并显示原因。
本次 rebase 发生冲突时自动 abort 回到更新前的本地提交；不会擅自处理原本就存在的冲突。
网络失败时仍可使用已安装版本，失败原因显示在 Git 更新页。

手动更新前，先在演出页点击「关闭演出窗口」，再在 Git 更新页点「检查并 rebase 更新」，完成后点「打开演出」。
运行中的任务持有锁时不部署文件，也不强制终止游戏或任务。

部署前核对已安装文件的哈希，旧文件放在 `backup/git-update-时间/`。
部署失败或 Python 模块导入检查失败时恢复已替换的文件。`config/`、`data/`、`cache/` 和本机配置不会从仓库覆盖。
为了保留 fork 的修改，检测到 `git-update.json` 时停用原上游 Release 更新器。

本机 `git-update.json` 的 `repository` 指向开发用 Git 工作区；该文件只保留在本机，不提交 Git。
启动器不执行 upstream 合并，也不自动更新 .NET、Python 依赖或第三方 MFAA 二进制；涉及这些运行环境变更需要重新打包安装。
启动界面 C# 源码在 `tools/GitLauncher.cs`，可用 Windows 自带的 .NET Framework C# 编译器构建；修改该源码后需重新编译启动器。

原第三方程序保留为 `MFAAvalonia.Core.exe`；原来的可执行文件另有备份。需要绕过启动器时可直接运行 Core 程序。
