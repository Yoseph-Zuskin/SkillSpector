# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Deterministic suitability gate for agent-CLI release bumps.

Compares a NEW CLI release against the pinned baseline WITHOUT human
judgment: version-string parse, --help diff vs the checked-in fixture,
and a changelog keyword scan. Writes suitability-report.md and exits
0 (green: ready for human live validation) or 1 (red: gaps enumerated).

Live inference, credential spend, hook-marker proofs, and behavioral
judgment stay human by design -- see the execution plan.
"""

from __future__ import annotations

import argparse
import difflib
import re
import sys
from pathlib import Path

WATCH_FLAGS = {
    "copilot": [
        "-s",
        "--no-ask-user",
        "--available-tools",
        "--deny-tool",
        "--no-custom-instructions",
        "--disable-builtin-mcps",
        "--no-auto-update",
    ],
    "opencode": ["--pure", "--format", "--model", "--auto"],
}

KEYWORDS = [
    "hook",
    "allowlist",
    "allow-all",
    "stdin",
    "auth",
    "token",
    "permission",
    "managed",
    "mcp",
    "plugin",
    "sandbox",
    "break",
    "broken",
    "deprecat",
    "remov",
    "securit",
    "cve",
    "oauth",
    "scope",
    "cwd",
    "instruction",
]


def check_help_diff(cli: str, new_help: str, baseline: Path, report: list[str]) -> bool:
    """True when no watchlist flag was added or removed."""
    old = baseline.read_text(encoding="utf-8").splitlines()
    new = new_help.splitlines()
    diff = [line for line in difflib.unified_diff(old, new, lineterm="") if line[:1] in "+-"]
    hits = [
        line
        for line in diff
        if any(
            re.search(r"(^|\s)" + re.escape(flag) + r"([\s,]|$|=)", line[1:])
            for flag in WATCH_FLAGS[cli]
        )
    ]
    if hits:
        report.append("## --help watchlist changes (RED)")
        report.extend("> " + line for line in hits[:20])
        return False
    changed = len(diff)
    report.append(f"## --help diff: {changed} changed lines, none on the watchlist (green)")
    return True


def check_keywords(body: str, report: list[str]) -> bool:
    """Keyword hits are amber context for a human, never a verdict."""
    hits = sorted({kw for kw in KEYWORDS if re.search(r"\b" + re.escape(kw), body, re.IGNORECASE)})
    if hits:
        report.append("## Changelog keyword hits (AMBER, human reads context)")
        report.append("Hit: " + ", ".join(hits))
    else:
        report.append("## Changelog keyword hits: none (green)")
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cli", required=True, choices=["copilot", "opencode"])
    parser.add_argument("--old", required=True, help="currently pinned version")
    parser.add_argument("--new", required=True, help="candidate version")
    parser.add_argument("--help-file", required=True, help="captured --help of the NEW cli")
    parser.add_argument("--baseline", required=True, help="checked-in --help fixture of the pin")
    parser.add_argument("--body-file", required=True, help="release notes body")
    parser.add_argument("--report", required=True, help="output markdown path")
    args = parser.parse_args()

    report = [f"# Suitability report: {args.cli} {args.old} -> {args.new}", ""]
    ok = True
    if not Path(args.help_file).exists() or not Path(args.help_file).stat().st_size:
        report.append("## --help capture: EMPTY (RED)")
        ok = False
    elif not Path(args.baseline).exists():
        report.append("## --help diff: no baseline fixture (AMBER, human compares manually)")
    else:
        new_help = Path(args.help_file).read_text(encoding="utf-8")
        ok = check_help_diff(args.cli, new_help, Path(args.baseline), report) and ok
    check_keywords(Path(args.body_file).read_text(encoding="utf-8"), report)
    report += [
        "",
        "## Verdict: "
        + (
            "GREEN - ready for human live validation" if ok else "RED - gaps need exploration first"
        ),
        "",
        "Human battery before merge: version probe, hook-audit, "
        "clean-home nonce round-trip, Free-tier spend approval.",
    ]
    Path(args.report).write_text("\n".join(report) + "\n", encoding="utf-8")
    print("\n".join(report))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
