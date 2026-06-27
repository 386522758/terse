from terse.core import compress


def test_compress_reduces_tokens_on_noisy_input():
    raw = "\n".join(["the same warning line"] * 200 + ["final summary: ok"])
    result = compress(raw, profile="generic")
    assert result.compressed_tokens < result.original_tokens
    assert result.token_savings_pct > 50
    assert "final summary: ok" in result.text


def test_compress_is_safe_on_clean_input():
    raw = "line one\nline two\nline three\n"
    result = compress(raw, profile="generic")
    # Nothing to compress: content is preserved.
    for line in ("line one", "line two", "line three"):
        assert line in result.text


def test_compress_strips_ansi_by_default():
    raw = "\x1b[31mred\x1b[0m\n"
    result = compress(raw)
    assert "\x1b" not in result.text
    assert "red" in result.text


def test_compress_keep_ansi():
    raw = "\x1b[31mred\x1b[0m\n"
    result = compress(raw, keep_ansi=True)
    assert "\x1b" in result.text


def test_result_percentages_bounded():
    raw = "x\n" * 100
    result = compress(raw)
    assert 0 <= result.token_savings_pct <= 100
    assert 0 <= result.char_savings_pct <= 100


def test_summary_line_mentions_profile():
    result = compress("a\na\na\n", profile="npm")
    assert "npm" in result.summary_line()
    assert "tokens" in result.summary_line()


def test_empty_input():
    result = compress("")
    assert result.original_tokens == 0
    assert result.token_savings_pct == 0.0


def test_never_expands_tiny_input():
    # Three short identical lines: collapsing would cost more than it saves,
    # so terse must hand back something no larger than the input.
    raw = "a\na\na\n"
    result = compress(raw)
    assert result.compressed_tokens <= result.original_tokens
    assert result.token_savings_pct >= 0
