# terse

**Compress noisy command output before it reaches your AI coding agent — 60-95% fewer tokens, zero dependencies.**

[![CI](https://github.com/386522758/terse/actions/workflows/ci.yml/badge.svg)](https://github.com/386522758/terse/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)

When an AI coding agent (Claude Code, Codex, Cursor, Gemini CLI, …) runs `npm install`,
`pip install`, a test suite, or a build, it pipes the **entire** wall of output back into
the model's context. Most of that is noise — deprecation warnings, download bars, 200
identical "PASSED" lines, ANSI color codes — and you pay for every token of it, on every
tool call.

`terse` wraps the command and hands the agent a compact version that keeps the signal
(errors, failures, summaries) and folds away the noise.

```console
$ terse pytest -v
============================= test session starts =============================
platform linux -- Python 3.11.0, pytest-8.0.0, pluggy-1.4.0
collected 214 items

[terse] collapsed 200 passing-test line(s)
tests/test_api.py::test_timeout FAILED                            [ 98%]

=================================== FAILURES ===================================
________________________________ test_timeout _________________________________
    def test_timeout():
>       assert client.get('/slow').status_code == 200
E       assert 504 == 200
tests/test_api.py:88: AssertionError
=================== 1 failed, 213 passed in 12.40s ====================

[terse] pytest · 5,578→423 tokens (-92%) · ANSI stripped; collapsed 200 passing-test lines
```

The failure, the traceback, and the summary survive untouched. The 200 passing lines
become one. That's **92% fewer tokens** for the model to read.

## Why this matters

Token cost and latency scale with everything the agent reads, and noisy build/test output
is some of the least information-dense text it ever sees. Trimming it:

- **cuts cost** — you stop paying for 200 copies of "PASSED",
- **speeds up the loop** — less to send, less to process,
- **sharpens attention** — the model isn't hunting for one `FAILED` in a haystack of green.

## Benchmark

Reproducible numbers from [`examples/benchmark.py`](examples/benchmark.py) (run it yourself —
no network or external tools needed). Tokens are measured with the built-in estimator.

| command | profile | tokens in | tokens out | saved |
|---|---|--:|--:|--:|
| `npm install` | npm | 2,477 | 114 | **95%** |
| `pip install -r requirements.txt` | pip | 2,329 | 191 | **92%** |
| `pytest -v` | pytest | 5,578 | 423 | **92%** |
| `webpack --mode production` | build | 5,293 | 119 | **98%** |
| **total** | | **15,677** | **847** | **95%** |

```console
$ python examples/benchmark.py
```

## Install

Pure standard library — nothing to pull in.

```bash
pip install terse-cli          # from PyPI (package name: terse-cli, command: terse)
# or, straight from source:
git clone https://github.com/386522758/terse && cd terse && pip install -e .
# or just drop src/terse on your PATH — there are no dependencies.
```

Requires Python 3.8+.

## Usage

Put `terse` in front of any command:

```bash
terse npm install
terse pip install -r requirements.txt
terse pytest -q
```

…or pipe something into it:

```bash
cat build.log | terse --profile build
docker build . 2>&1 | terse
```

`terse` runs the command, prints the compressed output to **stdout**, prints a one-line
savings summary to **stderr**, and **exits with the wrapped command's exit code** — so it's
safe to drop into scripts and CI.

If the command has its own flags, separate them with `--`:

```bash
terse -- git --no-pager diff
```

### Options

| flag | effect |
|---|---|
| `--profile NAME` | force a profile instead of auto-detecting (`generic`, `npm`, `pip`, `pytest`, `git`, `build`) |
| `--max-repeat N` | keep at most N identical consecutive lines before collapsing (default 1) |
| `--keep-ansi` | don't strip ANSI color / control codes |
| `--stats` / `--no-stats` | force the savings line on/off (default: on when stderr is a terminal) |
| `--json-stats` | emit savings as JSON to stderr (handy for tooling) |
| `--version` | print version |

## Profiles

The profile is auto-detected from the command and decides which tool-specific noise to fold.
Every profile also gets the universal rules (ANSI stripping, carriage-return collapse,
progress-bar removal, duplicate-line folding).

| profile | triggers on | folds away |
|---|---|---|
| `npm` | `npm` / `pnpm` / `yarn` / `bun` | deprecation warnings, `npm http/sill/verb` logs, resolver progress |
| `pip` | `pip` / `pip3` | `Collecting` / `Downloading` / `Using cached`, already-satisfied requirements, wheel builds |
| `pytest` | `pytest` / `jest` / `vitest` / `mocha` | passing & skipped tests (**failures always kept**) |
| `git` | `git status` / `git diff` / `git log` | long runs of file entries and unchanged diff context |
| `build` | `webpack` / `vite` / `tsc` / `next` / … | asset-size tables and module listings |
| `generic` | everything else | universal rules only |

## Use it with an AI agent

Point your agent at `terse` instead of the raw command. For example, in a Claude Code / Codex
project, add a note to your instructions file:

> When running installs, tests, or builds, prefix the command with `terse ` to keep output compact.

Or alias the common offenders so it happens transparently:

```bash
alias npm='terse npm'
alias pytest='terse pytest'
```

## How it works

`terse` is a small pipeline of conservative, order-independent rules:

1. **Strip ANSI** escape sequences (colors, cursor moves, hyperlinks).
2. **Resolve carriage returns** — a progress widget repaints one line many times; keep only
   the final frame.
3. **Drop progress bars** and download-speed readouts.
4. **Collapse consecutive duplicate lines** into one + a `(×N)` marker.
5. **Apply the profile** — fold the tool-specific noise.
6. **Squash blank-line runs.**

It never drops lines that look like errors, failures, or final summaries — only repetitive
noise the model doesn't need.

### The one guarantee

**`terse` never makes output larger.** On already-compact input the markers can cost more
than they save, so if the result would be bigger than the original, `terse` hands back the
original untouched. Worst case it does nothing; it never works against you.

## Limitations (honest list)

- **Output is buffered, not streamed.** `terse` runs the command to completion, then prints.
  You won't see live progress — which is usually the point for an agent, but not what you want
  for a long interactive build.
- **The token count is an estimate.** It's a dependency-free approximation (~10-15% of
  `tiktoken` on typical logs), used to compare before/after — not an exact billing figure.
- **Profiles are heuristic.** They target the common, high-volume noise of each tool. Unusual
  formats fall back to the universal rules, which are still useful but less aggressive.

## Develop

```bash
pip install -e ".[dev]"
pytest -q                  # run the test suite
python examples/benchmark.py
```

Contributions welcome — new profiles are easy to add: write one function that takes a list of
lines and returns a smaller list, register it in `PROFILES`, and add a case to the benchmark.

## License

[MIT](LICENSE) © 2026 zibaoyang
