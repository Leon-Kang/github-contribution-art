#!/usr/bin/env python3
"""Generate deliberately backdated empty commits from pixels.json."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load_dates() -> list[tuple[str, str]]:
    payload = json.loads((ROOT / "pixels.json").read_text())
    pixels: list[tuple[str, str]] = []
    for year, design in payload["years"].items():
        for value in design["dates"]:
            if not value.startswith(f"{year}-"):
                raise SystemExit(f"Date {value} is outside declared year {year}")
            date.fromisoformat(value)
            pixels.append((year, value))
    if len({value for _, value in pixels}) != len(pixels):
        raise SystemExit("pixels.json contains duplicate dates")
    return sorted(pixels, key=lambda item: item[1])


def run_git(*args: str, env: dict[str, str] | None = None) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=ROOT, env=env, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if completed.returncode:
        sys.stderr.write(completed.stderr)
        raise SystemExit(completed.returncode)
    return completed.stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    pixels = load_dates()

    if args.dry_run:
        for year, value in pixels:
            print(f'{value}  git commit --allow-empty -m "art: {year} pixel {value}"')
        print(f"Dry run: {len(pixels)} empty commits; Git history unchanged.")
        return

    if run_git("rev-parse", "--is-inside-work-tree") != "true":
        raise SystemExit("Run this only inside the dedicated Git repository")

    existing = run_git("log", "--format=%s", "--all")
    if any(line.startswith("art: ") for line in existing.splitlines()):
        raise SystemExit("Art commits already exist; refusing to generate duplicates")

    for index, (year, value) in enumerate(pixels, start=1):
        stamp = f"{value}T12:00:00+09:00"
        env = os.environ.copy()
        env["GIT_AUTHOR_DATE"] = stamp
        env["GIT_COMMITTER_DATE"] = stamp
        run_git("commit", "--allow-empty", "-m", f"art: {year} pixel {value}", env=env)
        if index % 100 == 0 or index == len(pixels):
            print(f"Generated {index}/{len(pixels)}")


if __name__ == "__main__":
    main()

