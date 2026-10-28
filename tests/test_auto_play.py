import threading
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from ournotes_auto import commands
from ournotes_auto.agent.params import ParamError, worker_args
from ournotes_auto.cli import build_parser
from ournotes_auto.config import Config, SyncParams
from ournotes_auto.player import session


@pytest.mark.parametrize("seconds", [0, -1, float("nan"), float("inf")])
def test_wait_rejects_invalid_time(seconds):
    with pytest.raises(ValueError):
        session.PlaySession.play_when_started(None, None, threading.Event(), seconds)


def test_session_waits_for_notes_without_monitoring():
    calls = []
    tracker = SimpleNamespace(p=SyncParams(), max_start_delay_s=25)
    plan = object()
    fake = SimpleNamespace(
        prepare=lambda chart: (plan, tracker),
        _play=lambda *args, **kwargs: calls.append(kwargs) or "outcome",
    )
    assert session.PlaySession.play_when_started(fake, SimpleNamespace(key="test"), threading.Event(), 900) == "outcome"
    assert calls == [{"prepared": (plan, tracker), "monitor": False}]
    assert tracker.p.timeout_s == 900 and tracker.max_start_delay_s == 0


def test_agent_manual_task_and_validation():
    attach = {"manual_song": "春日影", "manual_difficulty": "hard", "manual_wait_seconds": 900, "touch": "minitouch",
              "human_great": 0, "human_timing": 0, "human_position": False, "watch_combo": True}
    args = worker_args("auto_play", attach, {})
    assert args[-6:] == ["auto-play", "春日影", "--difficulty", "hard", "--timeout", "900"]
    parsed = build_parser().parse_args(args)
    assert "--watch-combo" not in args
    assert parsed.func is commands.cmd_auto_play
    assert parsed.timeout == 900 and parsed.difficulty == "hard"
    for changes in ({"manual_song": " "}, {"manual_difficulty": "high_first"}, {"manual_wait_seconds": 0}):
        with pytest.raises(ParamError):
            worker_args("auto_play", {**attach, **changes}, {})


@pytest.mark.parametrize("failure, code", [(None, 0), (InterruptedError(), 130), (TimeoutError(), 1)])
def test_command_only_waits_and_plays(monkeypatch, tmp_path, failure, code):
    monkeypatch.chdir(tmp_path)
    calls = []
    chart = SimpleNamespace(music_id=100008, difficulty="expert", key="100008_expert")
    monkeypatch.setattr(commands, "_chart", lambda *args: calls.append("chart") or chart)

    @contextmanager
    def device(cfg):
        calls.append("device")
        yield "source", "touch"

    class Session:
        def __init__(self, *args, **kwargs):
            assert args[0].play.guard_lost_s == 0
            assert args[0].play.guard_life_zero_s == 0
            assert kwargs.get("combo_reader") is None
            calls.append("session")

        def play_when_started(self, actual_chart, stop, seconds):
            assert actual_chart is chart and seconds == 600
            calls.append("wait-play")
            if failure is not None:
                raise failure
            return SimpleNamespace(stats=SimpleNamespace(aborted=False, sent=42))

    monkeypatch.setattr(commands, "_device", device)
    monkeypatch.setattr(session, "PlaySession", Session)
    args = build_parser().parse_args(["auto-play", "100008"])
    args.stop = threading.Event()
    assert args.func(Config(), args) == code
    assert calls == ["chart", "device", "session", "wait-play"]
