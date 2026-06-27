# Contributing

Thanks for considering a contribution! `terse` is small and dependency-free, and
the goal is to keep it that way.

## Development setup

```bash
git clone https://github.com/386522758/terse && cd terse
pip install -e ".[dev]"

pytest -q                  # run the test suite
ruff check .               # lint
python examples/benchmark.py
```

## Adding a profile

A profile is one function that takes a list of lines and returns a smaller list
plus a list of human-readable notes:

1. Write `profile_<tool>(lines)` in
   [`src/terse/compressors.py`](src/terse/compressors.py), reusing
   `collapse_matching` / `collapse_runs` for the heavy lifting.
2. Register it in the `PROFILES` dict and teach `detect_profile` which commands
   should trigger it.
3. Add a synthetic case to
   [`examples/benchmark.py`](examples/benchmark.py) and a test in
   [`tests/test_compressors.py`](tests/test_compressors.py).

## Ground rules

- **No runtime dependencies.** Standard library only.
- **Never drop signal.** Rules may fold repetitive noise, but must keep errors,
  failures, and final summaries intact. When in doubt, keep the line.
- **Never make output larger.** Guard every collapse behind a threshold so the
  summary marker always pays for itself.
- **Keep it green.** `pytest -q` and `ruff check .` should both pass before you
  open a pull request.
