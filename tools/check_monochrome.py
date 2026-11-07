#!/usr/bin/env python3
"""Fail if a chromatic colour has crept back into the stylesheets.

The interface is deliberately monochrome: every state is carried by ink --
fill, weight and shape -- rather than by hue. That is easy to state and easy
to erode, because the quickest way to make something stand out is to reach
for red, and because a single `.dark .badge-red` with two classes in it can
quietly outrank a later rule. Both happened while this was being built.

So the rule is checked rather than remembered. Any colour literal whose RGB
channels differ by more than TOLERANCE is reported, with its file and line.

Greys are allowed. So are the mapping selectors, which name Tailwind's
colour classes in order to neutralise them -- `.badge-red { background:
var(--rn-text) }` is the fix, not the problem, so only literal colour VALUES
are inspected, never selectors.

Usage: python3 tools/check_monochrome.py [paths...]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

TOLERANCE = 12  # max spread between R, G and B before it counts as a hue

HEX = re.compile(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})\b")
RGB = re.compile(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)")
# Alpha low enough that no hue is perceptible.
RGBA_ALPHA = re.compile(r"rgba\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*,\s*([\d.]+)\s*\)")

DEFAULT_PATHS = ["frontend/styles"]


def channels(hex_or_rgb: str) -> tuple[int, int, int] | None:
    m = HEX.fullmatch(hex_or_rgb)
    if m:
        h = m.group(1)
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return None


def scan(path: Path) -> list[tuple[int, str, str]]:
    findings: list[tuple[int, str, str]] = []
    for lineno, line in enumerate(path.read_text().splitlines(), start=1):
        code = line.split("/*")[0]
        if not code.strip():
            continue

        for match in HEX.finditer(code):
            rgb = channels(match.group(0))
            if rgb and max(rgb) - min(rgb) > TOLERANCE:
                findings.append((lineno, match.group(0), line.strip()[:84]))

        for match in RGB.finditer(code):
            r, g, b = (int(match.group(i)) for i in (1, 2, 3))
            if max(r, g, b) - min(r, g, b) <= TOLERANCE:
                continue
            alpha = RGBA_ALPHA.search(code[match.start():])
            # A strong hue at 4% opacity is invisible; below that it is noise.
            if alpha and float(alpha.group(1)) < 0.05:
                continue
            findings.append((lineno, match.group(0) + ")", line.strip()[:84]))
    return findings


def main(argv: list[str]) -> int:
    roots = [Path(p) for p in (argv or DEFAULT_PATHS)]
    files = sorted(
        f for root in roots
        for f in ([root] if root.is_file() else root.rglob("*.css"))
    )
    if not files:
        print("no stylesheets found")
        return 1

    total = 0
    for path in files:
        findings = scan(path)
        if findings:
            print(f"\n{path}")
            for lineno, value, context in findings:
                print(f"  {lineno:>4}: {value:<26} {context}")
            total += len(findings)

    print()
    if total:
        print(f"FAIL: {total} chromatic colour value(s) in {len(files)} stylesheet(s).")
        print("The interface is monochrome; express the state with ink, not hue.")
        return 1
    print(f"PASS: {len(files)} stylesheet(s), no chromatic colour values.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
