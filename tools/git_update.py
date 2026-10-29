"""原生 Git 更新页后端：fetch + rebase，验证本地文件后部署，输出提交记录。"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

URL = "https://github.com/ZHENG-maki/OurNotes-Auto.git"
PREFIXES = ("agent/", "ournotes_auto/", "tasks/", "locales/", "docs/", "resource/")
TOP = {"interface.json", "LICENSE", "TERMS_OF_SERVICE.md", "THIRD_PARTY_NOTICES.md", "config.example.yaml", "tools/git_update.py"}


class UpdateError(RuntimeError):
    pass


def git(repo: Path, *args: str) -> str:
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_EDITOR": "true", "PYTHONUTF8": "1"}
    p = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env, timeout=120,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if p.returncode:
        raise UpdateError((p.stderr or p.stdout).strip())
    return p.stdout.strip()


def sync(repo: Path) -> None:
    if git(repo, "branch", "--show-current") != "main":
        raise UpdateError("本地分支不是 main，请先整理分支；本次不修改代码")
    for state in ("rebase-merge", "rebase-apply", "MERGE_HEAD"):
        p = Path(git(repo, "rev-parse", "--git-path", state))
        if (p if p.is_absolute() else repo / p).exists():
            raise UpdateError("本地已有未结束的合并或 rebase，请先处理")
    if git(repo, "status", "--porcelain"):
        raise UpdateError("本地有未提交修改，请先提交；已保留所有文件，本次不更新")
    print("正在检查 origin/main…", flush=True)
    git(repo, "fetch", "origin", "main")
    print("正在 rebase 到 origin/main…", flush=True)
    try:
        git(repo, "rebase", "origin/main")
    except UpdateError as error:
        try:
            git(repo, "rebase", "--abort")
        except UpdateError as abort_error:
            raise UpdateError(f"rebase 失败且无法撤销，请手动处理：{abort_error}") from error
        raise UpdateError(f"rebase 冲突，已撤销并保留原本地提交：{error}") from error


def commits(repo: Path) -> list[list[str]]:
    lines = git(repo, "log", "-40", "--date=iso-strict", "--format=%h%x09%ad%x09%an%x09%s")
    return [line.split("\t", 3) for line in lines.splitlines()]


def safe(root: Path, rel: str) -> Path:
    path = root / rel
    if not path.resolve().is_relative_to(root.resolve()):
        raise UpdateError(f"路径越界：{rel}")
    return path


def payload(repo: Path) -> dict[str, bytes]:
    result = {}
    for rel in git(repo, "-c", "core.quotepath=false", "ls-files").splitlines():
        if rel in TOP or rel.startswith(PREFIXES) or (rel.startswith("README") and rel.endswith(".md")):
            source = safe(repo, rel)
            if source.is_file():
                result[rel] = source.read_bytes()
    if "interface.json" not in result:
        raise UpdateError("源码缺少 interface.json")
    interface = json.loads(result["interface.json"])
    interface["agent"]["child_exec"] = "./python/python.exe"
    interface["agent"]["child_args"] = ["./agent/main.py"]
    result["interface.json"] = (json.dumps(interface, ensure_ascii=False, indent=4) + "\n").encode("utf-8")
    return result


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def deploy(repo: Path, root: Path) -> int:
    desired = payload(repo)
    state = root / "cache/git-update/installed.json"
    old = json.loads(state.read_text(encoding="utf-8")) if state.exists() else {}
    changes = []
    for rel in sorted(set(old) | set(desired)):
        path = safe(root, rel)
        current = path.read_bytes() if path.exists() else None
        new = desired.get(rel)
        if current == new:
            continue
        if current is not None and old.get(rel) != sha(current):
            raise UpdateError(f"安装文件有本地修改，保留并停止更新：{rel}")
        changes.append((rel, current, new))
    backup = root / "backup" / ("git-update-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
    if changes:
        backup.mkdir(parents=True)
    applied = []
    try:
        for rel, current, new in changes:
            path = safe(root, rel)
            if current is not None:
                dest = safe(backup, rel)
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(current)
            applied.append((path, current))
            if new is None:
                path.unlink(missing_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                temp = path.with_name(path.name + ".git-update-tmp")
                temp.write_bytes(new)
                os.replace(temp, path)
        python = root / "python/python.exe"
        if changes and python.exists():
            check = subprocess.run([str(python), "-X", "utf8", "-c",
                "import ournotes_auto.cli, ournotes_auto.commands, ournotes_auto.runner"],
                cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if check.returncode:
                raise UpdateError("更新后导入检查失败，恢复原文件：" + check.stderr[-1500:])
        state.parent.mkdir(parents=True, exist_ok=True)
        temp = state.with_suffix(".tmp")
        temp.write_text(json.dumps({rel: sha(data) for rel, data in desired.items()}, indent=2), encoding="utf-8")
        os.replace(temp, state)
    except Exception:
        for path, current in reversed(applied):
            if current is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(current)
        raise
    print(f"安装完成：更新 {len(changes)} 个文件" if changes else "已是最新版本", flush=True)
    return len(changes)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--check-only", action="store_true", help="仅同步 Git；下次启动再部署")
    args = parser.parse_args()
    root = args.root.resolve()
    config = json.loads((root / "git-update.json").read_text(encoding="utf-8"))
    repo = Path(config["repository"])
    sys.path.insert(0, str(root))
    from ournotes_auto.release import FileLock, APPLY_LOCK, BUSY_DIR, is_locked
    lock = FileLock(root / APPLY_LOCK)
    try:
        if not lock.acquire():
            raise UpdateError("另一个更新正在进行")
        if any(is_locked(path) for path in (root / BUSY_DIR).glob("*.lock")):
            raise UpdateError("演奏任务正在运行，请结束任务后再更新")
        sync(repo)
        if args.check_only:
            print("STATUS\t源码已同步 · main · " + git(repo, "rev-parse", "--short", "HEAD")
                  + " · 重新打开程序后应用更新", flush=True)
            return 0
        deploy(repo, root)
        print("STATUS\t更新成功 · main · " + git(repo, "rev-parse", "--short", "HEAD"), flush=True)
        return 0
    except Exception as error:
        print("STATUS\t更新未完成：" + str(error).replace("\n", " "), flush=True)
        return 1
    finally:
        lock.release()
        try:
            for row in commits(repo):
                print("COMMIT\t" + "\t".join(row), flush=True)
        except Exception:
            pass


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
