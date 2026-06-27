#!/usr/bin/env python3
"""Reproducible benchmark for terse.

Synthesizes realistic-but-noisy output from common dev tools, runs each through
the matching terse profile, and prints a savings table. No network or external
tools required:  ``python examples/benchmark.py``
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from terse.core import compress  # noqa: E402

ESC = "\x1b"
GREEN = f"{ESC}[32m"
RED = f"{ESC}[31m"
YELLOW = f"{ESC}[33m"
DIM = f"{ESC}[2m"
RST = f"{ESC}[0m"


def npm_log() -> str:
    lines = ["", f"{YELLOW}npm{RST} warn config production Use `--omit=dev` instead."]
    pkgs = [
        "rimraf@2.7.1", "glob@7.2.3", "inflight@1.0.6", "har-validator@5.1.5",
        "uuid@3.4.0", "request@2.88.2", "core-js@2.6.12", "left-pad@1.3.0",
        "fsevents@1.2.13", "chokidar@2.1.8", "querystring@0.2.1", "urix@0.1.0",
    ]
    for p in pkgs * 4:
        lines.append(f"npm warn deprecated {p}: this package is no longer supported.")
    for i in range(30):
        lines.append(f"{DIM}npm{RST} http fetch GET 200 https://registry.npmjs.org/pkg{i} 412ms (cache miss)")
    lines.append("\r[          ] / reify:core-js: timing reifyNode:node_modules/x")
    lines.append("\r[######    ] \\ reify:lodash: timing reifyNode:node_modules/y")
    lines.append("\r[##########] - reify:react: timing reifyNode:node_modules/z")
    lines += [
        "",
        f"{GREEN}added 1043 packages{RST}, and audited 1044 packages in 24s",
        "",
        "118 packages are looking for funding",
        "  run `npm fund` for details",
        "",
        f"{RED}3 moderate severity vulnerabilities{RST}",
        "To address all issues, run: npm audit fix",
    ]
    return "\n".join(lines) + "\n"


def pip_log() -> str:
    lines = []
    deps = ["urllib3", "certifi", "idna", "charset-normalizer", "requests",
            "numpy", "pandas", "pytz", "six", "python-dateutil", "scipy",
            "click", "jinja2", "markupsafe", "werkzeug", "flask"]
    for d in deps:
        lines.append(f"Collecting {d}")
        lines.append(f"  Downloading {d}-1.2.3-py3-none-any.whl (1.4 MB)")
        lines.append(f"     |████████████████████████████████| 1.4 MB 12.3 MB/s eta 0:00:00")
        lines.append(f"  Using cached {d}-1.2.3-py3-none-any.whl")
    for d in deps:
        lines.append(f"Requirement already satisfied: {d} in ./venv/lib/python3.11/site-packages")
    lines.append("Building wheels for collected packages: numpy, scipy")
    lines.append("  Building wheel for numpy (setup.py): started")
    lines.append("  Building wheel for numpy (setup.py): finished with status 'done'")
    lines.append("Successfully installed " + " ".join(f"{d}-1.2.3" for d in deps))
    return "\n".join(lines) + "\n"


def pytest_log() -> str:
    lines = ["============================= test session starts =============================",
             "platform linux -- Python 3.11.0, pytest-8.0.0, pluggy-1.4.0",
             "collected 214 items", ""]
    for mod in ("core", "api", "utils", "models", "views"):
        for i in range(40):
            lines.append(f"tests/test_{mod}.py::test_case_{i:02d} {GREEN}PASSED{RST}    [ {i}%]")
    lines += [
        f"tests/test_api.py::test_timeout {RED}FAILED{RST}                            [ 98%]",
        "",
        "=================================== FAILURES ===================================",
        "________________________________ test_timeout _________________________________",
        "    def test_timeout():",
        ">       assert client.get('/slow').status_code == 200",
        "E       assert 504 == 200",
        "tests/test_api.py:88: AssertionError",
        "",
        f"{RED}=========================== short test summary info ============================{RST}",
        "FAILED tests/test_api.py::test_timeout - assert 504 == 200",
        "=================== 1 failed, 213 passed in 12.40s ====================",
    ]
    return "\n".join(lines) + "\n"


def webpack_log() -> str:
    lines = ["asset bundle.js 2.4 MiB [emitted] [big] (name: main)",
             "asset vendor.js 1.1 MiB [emitted] (name: vendors)"]
    for i in range(60):
        lines.append(f"asset chunk.{i:03d}.js {12 + i} KiB [emitted] (id hint: {i})")
    lines.append("runtime modules 3.2 KiB 12 modules")
    for i in range(120):
        lines.append(f"  [{i}] ./src/components/Comp{i}.jsx 1.2 KiB {{179}} [built] [code generated]")
    lines += ["", "webpack 5.90.0 compiled successfully in 8423 ms"]
    return "\n".join(lines) + "\n"


CASES = [
    ("npm install", "npm", npm_log()),
    ("pip install -r requirements.txt", "pip", pip_log()),
    ("pytest -v", "pytest", pytest_log()),
    ("webpack --mode production", "build", webpack_log()),
]


def main() -> None:
    rows = []
    tot_o = tot_c = 0
    for cmd, profile, raw in CASES:
        r = compress(raw, profile=profile)
        rows.append((cmd, profile, r.original_tokens, r.compressed_tokens, r.token_savings_pct))
        tot_o += r.original_tokens
        tot_c += r.compressed_tokens

    w = max(len(c) for c, *_ in rows)
    print(f"{'command'.ljust(w)}  profile  {'tokens in':>9}  {'tokens out':>10}  saved")
    print("-" * (w + 42))
    for cmd, profile, o, c, pct in rows:
        print(f"{cmd.ljust(w)}  {profile:<7}  {o:>9,}  {c:>10,}  {pct:>5.0f}%")
    overall = 100.0 * (tot_o - tot_c) / tot_o
    print("-" * (w + 42))
    print(f"{'TOTAL'.ljust(w)}  {'':<7}  {tot_o:>9,}  {tot_c:>10,}  {overall:>5.0f}%")
    print("\nMarkdown:")
    print("| command | profile | tokens in | tokens out | saved |")
    print("|---|---|--:|--:|--:|")
    for cmd, profile, o, c, pct in rows:
        print(f"| `{cmd}` | {profile} | {o:,} | {c:,} | **{pct:.0f}%** |")
    print(f"| **total** | | **{tot_o:,}** | **{tot_c:,}** | **{overall:.0f}%** |")


if __name__ == "__main__":
    main()
