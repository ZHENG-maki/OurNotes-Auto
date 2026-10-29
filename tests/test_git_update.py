import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("git_update", Path(__file__).parents[1] / "tools/git_update.py")
update = importlib.util.module_from_spec(spec)
spec.loader.exec_module(update)


def command(repo, *args):
    return update.git(repo, *args)


def commit(repo, text):
    command(repo, "add", ".")
    command(repo, "commit", "-m", text)


@pytest.fixture
def repos(tmp_path):
    remote, source, local = [tmp_path / p for p in ("remote", "source", "local")]
    command(tmp_path, "init", "--bare", str(remote))
    command(tmp_path, "clone", str(remote), str(source))
    command(source, "switch", "-c", "main")
    for repo in [source]:
        command(repo, "config", "user.name", "Test")
        command(repo, "config", "user.email", "test@example.com")
    (source / "one.txt").write_text("initial")
    commit(source, "initial")
    command(source, "push", "-u", "origin", "main")
    command(tmp_path, "clone", "-b", "main", str(remote), str(local))
    command(local, "config", "user.name", "Test")
    command(local, "config", "user.email", "test@example.com")
    return source, local


def test_rebase_preserves_local_commit(repos):
    source, local = repos
    (local / "local.txt").write_text("local")
    commit(local, "local commit")
    (source / "remote.txt").write_text("remote")
    commit(source, "remote commit")
    command(source, "push")
    update.sync(local)
    assert (local / "local.txt").read_text() == "local"
    assert (local / "remote.txt").read_text() == "remote"
    assert command(local, "rev-list", "--count", "origin/main..HEAD") == "1"


def test_dirty_files_untouched(repos):
    _, local = repos
    (local / "one.txt").write_text("dirty")
    with pytest.raises(update.UpdateError, match="未提交"):
        update.sync(local)
    assert (local / "one.txt").read_text() == "dirty"


def test_conflict_aborts_to_original_head(repos):
    source, local = repos
    (local / "one.txt").write_text("local")
    commit(local, "local")
    before = command(local, "rev-parse", "HEAD")
    (source / "one.txt").write_text("remote")
    commit(source, "remote")
    command(source, "push")
    with pytest.raises(update.UpdateError, match="已撤销"):
        update.sync(local)
    assert command(local, "rev-parse", "HEAD") == before
    assert (local / "one.txt").read_text() == "local"
    assert not command(local, "status", "--porcelain")


def test_deploy_blocks_runtime_edits_and_preserves_data(tmp_path, monkeypatch):
    root = tmp_path
    (root / "data").mkdir()
    (root / "data/user.txt").write_text("private")
    monkeypatch.setattr(update, "payload", lambda repo: {"ournotes_auto/a.py": b"old"})
    assert update.deploy(root, root) == 1
    assert update.deploy(root, root) == 0
    (root / "ournotes_auto/a.py").write_bytes(b"user edit")
    monkeypatch.setattr(update, "payload", lambda repo: {"ournotes_auto/a.py": b"new"})
    with pytest.raises(update.UpdateError, match="本地修改"):
        update.deploy(root, root)
    assert (root / "ournotes_auto/a.py").read_bytes() == b"user edit"
    assert (root / "data/user.txt").read_text() == "private"


def test_deploy_rollback(tmp_path, monkeypatch):
    monkeypatch.setattr(update, "payload", lambda repo: {"a": b"old", "b": b"old"})
    update.deploy(tmp_path, tmp_path)
    monkeypatch.setattr(update, "payload", lambda repo: {"a": b"new", "b": b"new"})
    replace = update.os.replace
    def fail(src, dest):
        if Path(dest).name == "b":
            raise OSError("simulated write failure")
        return replace(src, dest)
    monkeypatch.setattr(update.os, "replace", fail)
    with pytest.raises(OSError):
        update.deploy(tmp_path, tmp_path)
    assert (tmp_path / "a").read_bytes() == b"old"
    assert (tmp_path / "b").read_bytes() == b"old"


def test_manual_check_rebases_without_replacing_running_files(repos, tmp_path, monkeypatch, capsys):
    source, local = repos
    (source / "remote.txt").write_text("new remote commit")
    commit(source, "new commit")
    command(source, "push")
    root = tmp_path / "installed"
    root.mkdir()
    (root / "git-update.json").write_text(json.dumps({"repository": str(local)}))
    (root / "interface.json").write_bytes(b"currently loaded interface")
    monkeypatch.setattr(update.sys, "argv", ["git_update.py", "--root", str(root), "--check-only"])
    monkeypatch.setattr(update, "deploy", lambda *_: pytest.fail("manual check must not deploy"))
    assert update.main() == 0
    assert (local / "remote.txt").read_text() == "new remote commit"
    assert (root / "interface.json").read_bytes() == b"currently loaded interface"
    assert not (root / "cache/git-update/installed.json").exists()
    output = capsys.readouterr().out
    assert "重新打开程序后应用更新" in output
    assert "COMMIT\t" in output
