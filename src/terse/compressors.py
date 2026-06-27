"""Compression rules and per-tool profiles.

A *rule* is a small, pure function that takes the captured output (either as a
whole string or as a list of lines) and returns a smaller version plus a count
of what it removed. A *profile* is an ordered bundle of rules tuned for one
family of tools (npm, pip, pytest, ...).

Everything here is intentionally conservative: rules never drop lines that look
like errors, failures, or final summaries — only the repetitive noise that an
AI agent does not need in order to understand what happened.
"""

from __future__ import annotations

import os
import re
from typing import Callable, List, Tuple

LineRule = Callable[[List[str]], Tuple[List[str], int]]

MARKER = "[terse]"

# --------------------------------------------------------------------------- #
# Whole-string rules (run before splitting into lines)
# --------------------------------------------------------------------------- #

# CSI sequences (colors, cursor moves) and OSC sequences (window titles, links).
_ANSI_RE = re.compile(
    r"\x1b\[[0-9;?]*[ -/]*[@-~]"          # CSI ... command
    r"|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)"  # OSC ... BEL / ST
    r"|\x1b[@-Z\\-_]"                       # lone two-char escapes
)


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences (colors, cursor control, hyperlinks)."""
    return _ANSI_RE.sub("", text)


def resolve_carriage_returns(text: str) -> str:
    """Collapse terminal redraws.

    A progress widget repaints a line by writing ``\\r`` and overwriting it.
    The captured buffer keeps every frame; only the text after the final
    ``\\r`` is what the user ultimately saw, so we keep just that.

    CRLF line endings are normalized first; otherwise the trailing ``\\r`` of
    every line would be mistaken for a redraw and wipe the line's content.
    """
    text = text.replace("\r\n", "\n")
    out = []
    for line in text.split("\n"):
        if "\r" in line:
            line = line.split("\r")[-1]
        out.append(line)
    return "\n".join(out)


# --------------------------------------------------------------------------- #
# Universal line rules
# --------------------------------------------------------------------------- #

_BAR_RES = [
    re.compile(r"[█▉▊▋▌▍▎▏░▒▓]{3,}"),
    re.compile(r"\[[#=\-.\s]{6,}\]"),               # [#####     ]
    re.compile(r"\d+/\d+\s*\[[#=<>:.\s\-]*\]"),      # tqdm: 45/100 [###    ]
    re.compile(r"\d+(?:\.\d+)?\s?[KMG]i?B/s"),        # download speed
]


def drop_progress_lines(lines: List[str]) -> Tuple[List[str], int]:
    """Drop animated progress bars and download-speed readouts."""
    out, removed = [], 0
    for line in lines:
        if any(rx.search(line) for rx in _BAR_RES):
            removed += 1
            continue
        out.append(line)
    return out, removed


def collapse_consecutive_dupes(lines: List[str], max_repeat: int = 1) -> Tuple[List[str], int]:
    """Collapse runs of identical, non-blank lines into one + a ``(xN)`` note.

    Keeps up to ``max_repeat`` copies of each line. Only fires when it removes
    at least two lines — otherwise the summary marker would not pay for itself.
    """
    keep = max(1, max_repeat)
    out, removed = [], 0
    i, n = 0, len(lines)
    while i < n:
        j = i
        while j < n and lines[j] == lines[i]:
            j += 1
        run = j - i
        if run - keep >= 2 and lines[i].strip():
            out.extend([lines[i]] * keep)
            out.append(f"{MARKER} … (×{run} identical lines)")
            removed += run - keep
        else:
            out.extend(lines[i:j])
        i = j
    return out, removed


def collapse_blank_lines(lines: List[str], keep: int = 1) -> List[str]:
    """Squash runs of blank lines down to ``keep`` of them."""
    out, blanks = [], 0
    for line in lines:
        if line.strip() == "":
            blanks += 1
            if blanks <= keep:
                out.append(line)
        else:
            blanks = 0
            out.append(line)
    return out


# --------------------------------------------------------------------------- #
# Reusable helpers for profiles
# --------------------------------------------------------------------------- #

def collapse_matching(
    lines: List[str], pattern: str, label: str, threshold: int = 3
) -> Tuple[List[str], int]:
    """Globally collapse every line matching ``pattern`` into one summary.

    The summary is inserted at the position of the first match; the rest are
    removed. No-op unless at least ``threshold`` lines match (so we never make
    short output longer).
    """
    rx = re.compile(pattern)
    matched = [i for i, line in enumerate(lines) if rx.search(line)]
    if len(matched) < threshold:
        return lines, 0
    first, matched_set = matched[0], set(matched)
    out = []
    for i, line in enumerate(lines):
        if i == first:
            out.append(f"{MARKER} collapsed {len(matched)} {label} line(s)")
        elif i in matched_set:
            continue
        else:
            out.append(line)
    return out, len(matched)


def collapse_runs(
    lines: List[str], pattern: str, label: str, threshold: int = 6, keep_head: int = 3
) -> Tuple[List[str], int]:
    """Collapse *consecutive* runs of matching lines, preserving position.

    Keeps the first ``keep_head`` lines of each long run and replaces the tail
    with a single note. Unlike :func:`collapse_matching` this keeps unrelated
    blocks where they were, which matters for things like ``git status``.
    """
    rx = re.compile(pattern)
    out, removed = [], 0
    i, n = 0, len(lines)
    while i < n:
        if rx.search(lines[i]):
            j = i
            while j < n and rx.search(lines[j]):
                j += 1
            run = j - i
            if run >= threshold:
                out.extend(lines[i : i + keep_head])
                out.append(f"{MARKER} … {run - keep_head} more {label} line(s) hidden")
                removed += run - keep_head
            else:
                out.extend(lines[i:j])
            i = j
        else:
            out.append(lines[i])
            i += 1
    return out, removed


def _note(notes: List[str], count: int, text: str) -> None:
    if count:
        notes.append(text)


# --------------------------------------------------------------------------- #
# Profiles
# --------------------------------------------------------------------------- #

def profile_generic(lines: List[str]) -> Tuple[List[str], List[str]]:
    return lines, []


def profile_npm(lines: List[str]) -> Tuple[List[str], List[str]]:
    notes: List[str] = []
    lines, c = collapse_matching(lines, r"(?i)\bdeprecated\b", "deprecation warning")
    _note(notes, c, f"collapsed {c} deprecation warnings")
    lines, c = collapse_matching(lines, r"^npm (?:warn|WARN) ", "npm warning")
    _note(notes, c, f"collapsed {c} npm warnings")
    lines, c = collapse_matching(
        lines, r"^\s*npm (?:http|sill|silly|verb|info|timing|notice) ", "npm log"
    )
    _note(notes, c, f"collapsed {c} verbose npm log lines")
    lines, c = collapse_matching(lines, r"^\s*Progress: resolved ", "pnpm/yarn progress")
    _note(notes, c, f"collapsed {c} resolver-progress lines")
    lines, c = collapse_matching(lines, r"^\s*(?:added|reused|downloaded) \S", "package fetch")
    _note(notes, c, f"collapsed {c} package-fetch lines")
    return lines, notes


def profile_pip(lines: List[str]) -> Tuple[List[str], List[str]]:
    notes: List[str] = []
    lines, c = collapse_matching(
        lines, r"^\s*(?:Collecting|Downloading|Using cached|Obtaining) ", "download"
    )
    _note(notes, c, f"collapsed {c} download lines")
    lines, c = collapse_matching(lines, r"^\s*Requirement already satisfied", "already-satisfied")
    _note(notes, c, f"collapsed {c} already-satisfied requirements")
    lines, c = collapse_matching(
        lines,
        r"^\s*(?:Building wheel|Created wheel|Stored in directory|Preparing metadata|Getting requirements)",
        "build-step",
    )
    _note(notes, c, f"collapsed {c} wheel/metadata build steps")
    return lines, notes


def profile_pytest(lines: List[str]) -> Tuple[List[str], List[str]]:
    notes: List[str] = []
    # Keep FAILED / ERROR lines; collapse the passing & skipped chatter.
    lines, c = collapse_matching(lines, r"\bPASSED\b", "passing-test")
    _note(notes, c, f"collapsed {c} passing-test lines")
    lines, c = collapse_matching(lines, r"\b(?:SKIPPED|XFAIL|XPASS)\b", "skipped-test")
    _note(notes, c, f"collapsed {c} skipped-test lines")
    lines, c = collapse_matching(lines, r"^\s*✓ ", "passing-spec")  # jest/vitest check marks
    _note(notes, c, f"collapsed {c} passing-spec lines")
    return lines, notes


def profile_git(lines: List[str]) -> Tuple[List[str], List[str]]:
    notes: List[str] = []
    # Long runs of tab-indented file entries under status sections.
    lines, c = collapse_runs(lines, r"^\t", "file entry", threshold=6, keep_head=3)
    _note(notes, c, f"hid {c} file-status lines")
    # diff: collapse long unchanged context runs (lines starting with a space).
    lines, c = collapse_runs(lines, r"^ [^+\-]", "unchanged context", threshold=8, keep_head=2)
    _note(notes, c, f"hid {c} unchanged diff-context lines")
    return lines, notes


def profile_build(lines: List[str]) -> Tuple[List[str], List[str]]:
    notes: List[str] = []
    # Webpack/Vite asset and module listings.
    lines, c = collapse_runs(
        lines, r"(?:KiB|MiB|bytes)\b", "asset", threshold=6, keep_head=4
    )
    _note(notes, c, f"hid {c} asset-size lines")
    lines, c = collapse_runs(lines, r"^\s*\[\d+\]", "module", threshold=8, keep_head=3)
    _note(notes, c, f"hid {c} module lines")
    return lines, notes


PROFILES = {
    "generic": profile_generic,
    "npm": profile_npm,
    "pip": profile_pip,
    "pytest": profile_pytest,
    "git": profile_git,
    "build": profile_build,
}


def detect_profile(command: str) -> str:
    """Guess the best profile from a command string."""
    if not command or not command.strip():
        return "generic"
    parts = command.split()
    exe = os.path.basename(parts[0]).lower()
    if exe.endswith(".exe"):
        exe = exe[:-4]

    # `python -m pytest ...` / `python -m pip ...`: treat the module as the tool.
    if exe in {"python", "python3", "py"} and "-m" in parts:
        idx = parts.index("-m") + 1
        if idx < len(parts):
            exe = parts[idx].split(".")[0].lower()

    sub = parts[1].lower() if len(parts) > 1 else ""

    if exe in {"npm", "pnpm", "yarn", "bun"}:
        return "npm"
    if exe in {"pip", "pip3"} or (exe in {"python", "python3"} and "pip" in parts):
        return "pip"
    if exe in {"pytest", "py.test"}:
        return "pytest"
    if exe in {"jest", "vitest", "mocha", "ava"}:
        return "pytest"
    if exe == "git" and sub in {"status", "diff", "log", "show"}:
        return "git"
    if exe in {"webpack", "vite", "rollup", "esbuild", "tsc", "next", "ng", "turbo"}:
        return "build"
    return "generic"
