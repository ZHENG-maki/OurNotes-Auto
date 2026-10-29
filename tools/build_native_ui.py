"""Build the original MFAAvalonia UI with OurNotes' native Git update page.

Requires Git, .NET 10 SDK and NuGet access. Third-party sources stay in cache;
the exact source revision, patch and additional source files are reproducible.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import subprocess

REVISION = "1080d3e1500f3439ac896ab2eca9aeb8e885f1f4"  # MFAAvalonia v2.16.2, GPL-3.0
REPOSITORY = "https://github.com/SweetSmellFox/MFAAvalonia.git"
BASE = Path(__file__).resolve().parent


def run(*args: str, cwd: Path) -> None:
    subprocess.run(args, cwd=cwd, check=True)


def prepare(source: Path) -> None:
    if not (source / ".git").exists():
        source.parent.mkdir(parents=True, exist_ok=True)
        run("git", "clone", "--depth", "1", "--branch", "v2.16.2", REPOSITORY, str(source), cwd=source.parent)
    actual = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip()
    if actual != REVISION:
        raise RuntimeError(f"Wrong MFAAvalonia revision: {actual}; expected {REVISION}")
    patch = str(BASE / "native-ui" / "integration.patch")
    already_applied = subprocess.run(["git", "apply", "--reverse", "--check", patch], cwd=source,
                                     capture_output=True).returncode == 0
    if not already_applied:
        run("git", "apply", "--check", patch, cwd=source)
        run("git", "apply", patch, cwd=source)
    for name, destination in {
        "GitUpdateService.cs": "MFAAvalonia/Helper/GitUpdateService.cs",
        "GitUpdateView.axaml": "MFAAvalonia/Views/Pages/GitUpdateView.axaml",
        "GitUpdateView.axaml.cs": "MFAAvalonia/Views/Pages/GitUpdateView.axaml.cs",
    }.items():
        shutil.copy2(BASE / "native-ui" / name, source / destination)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=BASE.parent / "cache/native-ui/source")
    parser.add_argument("--out", type=Path, default=BASE.parent / "cache/native-ui/publish")
    args = parser.parse_args()
    source, out = args.source.resolve(), args.out.resolve()
    prepare(source)
    run("dotnet", "publish", "MFAAvalonia.Desktop/MFAAvalonia.Desktop.csproj", "-c", "Release",
        "-r", "win-x64", "--self-contained", "false", "-o", str(out), "-p:NuGetAudit=false", cwd=source)
    shutil.copy2(source / "LICENSE", out / "LICENSE-MFAA")
    print(f"Native UI built: {out}")


if __name__ == "__main__":
    main()
