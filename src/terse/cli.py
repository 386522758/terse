"""Command-line interface for ``terse``.

Two ways to use it:

    terse <command ...>     run a command, print a compressed version of its output
    <command> | terse       compress whatever is piped in

The wrapped command's exit code is propagated, so ``terse`` is safe to drop in
front of anything in a script or an agent tool call.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from typing import List, Optional

from . import __version__
from .compressors import PROFILES, detect_profile
from .core import compress

_EPILOG = """\
examples:
  terse npm install              # auto-detects the npm profile
  terse pytest -q                # keep failures, fold away the passing noise
  terse -- git --no-pager diff   # use -- when the command has its own flags
  cat build.log | terse --profile build
"""


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="terse",
        description="Compress noisy command output before it reaches an LLM agent.",
        epilog=_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--profile",
        choices=sorted(PROFILES),
        help="force a profile instead of auto-detecting from the command",
    )
    parser.add_argument(
        "--max-repeat",
        type=int,
        default=1,
        metavar="N",
        help="keep at most N identical consecutive lines (default: 1)",
    )
    parser.add_argument(
        "--keep-ansi",
        action="store_true",
        help="do not strip ANSI color / control codes",
    )
    stats = parser.add_mutually_exclusive_group()
    stats.add_argument(
        "--stats",
        dest="stats",
        action="store_true",
        default=None,
        help="always print the savings line to stderr",
    )
    stats.add_argument(
        "--no-stats",
        dest="stats",
        action="store_false",
        help="never print the savings line",
    )
    parser.add_argument(
        "--json-stats",
        action="store_true",
        help="print savings as a JSON object to stderr",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"terse {__version__}",
    )
    parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="command to run; omit to read from stdin",
    )
    return parser


def _capture(cmd: List[str]) -> "tuple[str, int]":
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError:
        sys.stderr.write(f"terse: command not found: {cmd[0]}\n")
        raise SystemExit(127)
    raw = proc.stdout
    if proc.stderr:
        raw = f"{raw}\n{proc.stderr}" if raw else proc.stderr
    return raw, proc.returncode


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    cmd = list(args.command)
    if cmd and cmd[0] == "--":
        cmd = cmd[1:]

    if cmd:
        profile = args.profile or detect_profile(" ".join(cmd))
        raw, exit_code = _capture(cmd)
    else:
        if sys.stdin.isatty():
            parser.error("no command given and nothing piped to stdin")
        raw = sys.stdin.read()
        profile = args.profile or "generic"
        exit_code = 0

    result = compress(
        raw,
        profile=profile,
        max_repeat=args.max_repeat,
        keep_ansi=args.keep_ansi,
    )

    sys.stdout.write(result.text)
    if result.text and not result.text.endswith("\n"):
        sys.stdout.write("\n")

    if args.json_stats:
        json.dump(
            {
                "profile": result.profile,
                "original_tokens": result.original_tokens,
                "compressed_tokens": result.compressed_tokens,
                "token_savings_pct": round(result.token_savings_pct, 1),
                "original_chars": result.original_chars,
                "compressed_chars": result.compressed_chars,
                "notes": result.notes,
            },
            sys.stderr,
        )
        sys.stderr.write("\n")
    else:
        show = args.stats if args.stats is not None else sys.stderr.isatty()
        if show:
            sys.stderr.write(result.summary_line() + "\n")

    return exit_code


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
