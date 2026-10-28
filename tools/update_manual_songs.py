"""从已有公开曲目缓存生成「自动演出」歌曲下拉列表，不复制运行记录。

用法：python tools/update_manual_songs.py --cache-dir cache/charts
新增歌曲后刷新曲目缓存，再运行本脚本并重开界面。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANGUAGES = {"zh_cn": 3, "zh_tw": 2, "en_us": 1, "ja_jp": 0, "ko_kr": 4}


def update(cache_dir: Path) -> int:
    charts = json.loads((cache_dir / "charts.json").read_text(encoding="utf-8"))["charts"]
    intl_path = cache_dir / "intl_songs.json"
    intl = json.loads(intl_path.read_text(encoding="utf-8")) if intl_path.exists() else {}
    songs = {}
    for chart in charts:
        if chart["difficulty"] in ("easy", "normal", "hard", "expert"):
            songs.setdefault(int(chart["musicId"]), chart)
    if not songs:
        raise ValueError("曲目缓存为空，不修改下拉列表")
    cases = [{"name": "unselected", "label": "$opt.ManualSong.choose", "pipeline_override": {
        "OurNotesParam": {"attach": {"manual_song": ""}}}}]
    for mid in sorted(songs):
        cases.append({"name": f"music_{mid}", "label": f"$song.manual.{mid}", "pipeline_override": {
            "OurNotesParam": {"attach": {"manual_song": str(mid)}}}})
    option = {"type": "select", "label": "$opt.ManualSong", "cases": cases, "default_case": "unselected"}
    path = ROOT / "tasks/play.json"
    text = path.read_text(encoding="utf-8")
    start = text.index('        "ManualSong": {', text.index('    "option":'))
    end = text.index('        "ManualDifficulty": {', start)
    lines = json.dumps(option, ensure_ascii=False, indent=4).splitlines()
    block = '        "ManualSong": ' + lines[0] + '\n' + '\n'.join('        ' + line for line in lines[1:]) + ',\n'
    path.write_text(text[:start] + block + text[end:], encoding="utf-8", newline="\n")
    prompts = {"zh_cn": "请选择歌曲", "zh_tw": "請選擇歌曲", "en_us": "Select a song", "ja_jp": "楽曲を選択", "ko_kr": "곡을 선택하세요"}
    for language, index in LANGUAGES.items():
        path = ROOT / "locales" / f"{language}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data = {k: v for k, v in data.items() if not k.startswith("song.manual.") and k not in ("opt.ManualSong.song", "opt.ManualSong.msg")}
        data["opt.ManualSong.choose"] = prompts[language]
        for mid in sorted(songs):
            titles = intl.get(str(mid), {}).get("musicTitle", [])
            title = titles[index] if len(titles) > index and titles[index] else songs[mid]["title"]
            data[f"song.manual.{mid}"] = f"{title}  [{mid}]"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=4) + "\n", encoding="utf-8", newline="\n")
    return len(songs)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, default=ROOT / "cache/charts")
    print(f"Generated {update(parser.parse_args().cache_dir)} song choices")
