import sys

import pytest

from terse.cli import main


class FakeStdin:
    def __init__(self, data, tty=False):
        self._data = data
        self._tty = tty

    def read(self):
        return self._data

    def isatty(self):
        return self._tty


def test_stdin_mode_compresses(monkeypatch, capsys):
    noisy = ("INFO  fetching metadata for dependency tree\n" * 30)
    monkeypatch.setattr(sys, "stdin", FakeStdin(noisy))
    rc = main(["--no-stats", "--profile", "generic"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "×30" in out
    assert len(out) < len(noisy)


def test_stdin_tty_with_no_command_errors(monkeypatch):
    monkeypatch.setattr(sys, "stdin", FakeStdin("", tty=True))
    with pytest.raises(SystemExit):
        main(["--no-stats"])


def test_command_mode_runs_and_propagates_exit_code(capsys):
    code = "import sys; [print('noise') for _ in range(20)]; sys.exit(7)"
    rc = main(["--no-stats", sys.executable, "-c", code])
    out = capsys.readouterr().out
    assert rc == 7
    assert "noise" in out
    assert "×20" in out  # 20 identical lines collapsed


def test_command_not_found_returns_127(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--no-stats", "definitely-not-a-real-binary-xyz"])
    assert exc.value.code == 127


def test_json_stats(monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", FakeStdin("a\na\na\n"))
    rc = main(["--json-stats", "--profile", "generic"])
    err = capsys.readouterr().err
    assert rc == 0
    assert '"profile"' in err
    assert '"token_savings_pct"' in err


def test_double_dash_separates_command(capsys):
    code = "print('hello')"
    rc = main(["--no-stats", "--", sys.executable, "-c", code])
    out = capsys.readouterr().out
    assert rc == 0
    assert "hello" in out
