#!/usr/bin/env python3
"""Verify generated art commits against pixels.json and the Phase-1 snapshot."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ART_RE = re.compile(r"^art: (\d{4}) pixel (\d{4}-\d{2}-\d{2})$")


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True)


def main() -> None:
    pixels = json.loads((ROOT / "pixels.json").read_text())
    snapshot = json.loads((ROOT / "phase1-snapshot.json").read_text())
    expected = {
        value
        for year, design in pixels["years"].items()
        for value in design["dates"]
    }
    occupied = {
        cell["date"]
        for year in snapshot["years"].values()
        for cell in year["occupiedCells"]
    }

    actual: list[str] = []
    malformed: list[str] = []
    date_mismatches: list[str] = []
    raw = git("log", "--format=%aI%x00%cI%x00%s", "HEAD")
    for line in raw.splitlines():
        author_date, committer_date, subject = line.split("\0", 2)
        if not subject.startswith("art: "):
            continue
        match = ART_RE.fullmatch(subject)
        if not match:
            malformed.append(subject)
            continue
        year, value = match.groups()
        actual.append(value)
        if not value.startswith(f"{year}-") or author_date[:10] != value or committer_date[:10] != value:
            date_mismatches.append(subject)

    counts = Counter(actual)
    duplicates = sorted(value for value, count in counts.items() if count != 1)
    actual_set = set(actual)
    missing = sorted(expected - actual_set)
    unexpected = sorted(actual_set - expected)
    collisions = sorted(expected & occupied)

    failures = {
        "missing": missing,
        "unexpected": unexpected,
        "duplicates": duplicates,
        "malformed": malformed,
        "dateMismatches": date_mismatches,
        "originallyOccupied": collisions,
    }
    failed = any(failures.values())

    per_year: dict[str, int] = defaultdict(int)
    for value in actual:
        per_year[value[:4]] += 1
    print(json.dumps({
        "ok": not failed,
        "expectedPixels": len(expected),
        "verifiedArtCommits": len(actual),
        "perYear": dict(sorted(per_year.items())),
        "failures": failures,
    }, indent=2))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

