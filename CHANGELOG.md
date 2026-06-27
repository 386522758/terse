# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- `resolve_carriage_returns` no longer wipes CRLF (`\r\n`) input. Line endings
  are normalized before carriage-return redraw frames are resolved, so the
  public `compress()` API is safe on Windows-style text.

### Added
- `--timeout SECS` kills a wrapped command that hangs and exits with code 124.
- Profile auto-detection for `python -m pytest` and `python -m pip`.

### Changed
- A wrapped command's stderr is now interleaved with stdout in the order it was
  written, instead of being appended after all of stdout.
- Subprocess output is decoded as UTF-8 with `errors="replace"`, so non-UTF-8
  byte sequences no longer crash terse on locales whose default codec isn't UTF-8.

## [0.1.0] - 2026-06-27

### Added
- Initial release: a buffered command-output compressor with `generic`, `npm`,
  `pip`, `pytest`, `git`, and `build` profiles.
- Universal rules: ANSI stripping, carriage-return resolution, progress-bar
  removal, consecutive-duplicate folding, blank-line squashing.
- Dependency-free token estimator and a reproducible benchmark
  (`examples/benchmark.py`).
- "Never expand" guarantee: terse returns the original output untouched if
  compression would make it larger.
