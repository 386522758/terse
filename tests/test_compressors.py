from terse import compressors as C


def test_strip_ansi_removes_colors():
    colored = "\x1b[31mERROR\x1b[0m something \x1b[1;32mok\x1b[0m"
    assert C.strip_ansi(colored) == "ERROR something ok"


def test_strip_ansi_removes_osc_hyperlink():
    linked = "see \x1b]8;;https://example.com\x07link\x1b]8;;\x07 here"
    assert "example.com" not in C.strip_ansi(linked)


def test_resolve_carriage_returns_keeps_last_frame():
    text = "Downloading 10%\rDownloading 50%\rDownloading 100%"
    assert C.resolve_carriage_returns(text) == "Downloading 100%"


def test_drop_progress_lines():
    lines = [
        "Building...",
        "[####          ] 30%",
        "real output line",
        "12.4 MiB/s",
        "████████░░░░ downloading",
    ]
    out, removed = C.drop_progress_lines(lines)
    assert removed == 3
    assert "real output line" in out
    assert "Building..." in out


def test_collapse_consecutive_dupes():
    lines = ["same"] * 5 + ["unique"]
    out, removed = C.collapse_consecutive_dupes(lines, max_repeat=1)
    assert removed == 4
    assert out[0] == "same"
    assert "×5" in out[1]
    assert out[-1] == "unique"


def test_collapse_consecutive_dupes_ignores_blanks():
    lines = ["", "", ""]
    out, removed = C.collapse_consecutive_dupes(lines)
    assert removed == 0


def test_collapse_blank_lines():
    lines = ["a", "", "", "", "b"]
    out = C.collapse_blank_lines(lines, keep=1)
    assert out == ["a", "", "b"]


def test_collapse_matching_threshold_noop():
    lines = ["Collecting a", "real"]
    out, count = C.collapse_matching(lines, r"^Collecting ", "download", threshold=3)
    assert count == 0
    assert out == lines


def test_collapse_matching_summarizes():
    lines = [f"Collecting pkg{i}" for i in range(10)] + ["Successfully installed"]
    out, count = C.collapse_matching(lines, r"^Collecting ", "download")
    assert count == 10
    assert any("collapsed 10 download" in line for line in out)
    assert "Successfully installed" in out


def test_collapse_runs_preserves_position():
    lines = ["header"] + ["\tfile" for _ in range(10)] + ["footer"]
    out, removed = C.collapse_runs(lines, r"^\t", "file entry", threshold=6, keep_head=3)
    assert removed == 7
    assert out[0] == "header"
    assert out[-1] == "footer"
    assert any("more file entry" in line for line in out)


def test_profile_pytest_keeps_failures():
    lines = [
        "tests/test_a.py::test_one PASSED",
        "tests/test_a.py::test_two PASSED",
        "tests/test_a.py::test_three PASSED",
        "tests/test_b.py::test_four FAILED",
        "tests/test_b.py::test_five PASSED",
    ]
    out, notes = C.profile_pytest(lines)
    joined = "\n".join(out)
    assert "FAILED" in joined
    assert "PASSED" not in joined or joined.count("PASSED") < 4
    assert notes


def test_detect_profile():
    assert C.detect_profile("npm install") == "npm"
    assert C.detect_profile("pnpm i") == "npm"
    assert C.detect_profile("pip install requests") == "pip"
    assert C.detect_profile("pytest -q") == "pytest"
    assert C.detect_profile("git status") == "git"
    assert C.detect_profile("git commit -m x") == "generic"
    assert C.detect_profile("vite build") == "build"
    assert C.detect_profile("echo hi") == "generic"
    assert C.detect_profile("") == "generic"
    assert C.detect_profile("/usr/local/bin/npm ci") == "npm"
