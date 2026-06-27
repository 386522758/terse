from terse.tokens import estimate_tokens, human_bytes


def test_empty_is_zero():
    assert estimate_tokens("") == 0


def test_monotonic_with_length():
    short = estimate_tokens("hello world")
    long = estimate_tokens("hello world " * 50)
    assert long > short


def test_newlines_counted():
    assert estimate_tokens("a\nb\nc") > estimate_tokens("a b c")


def test_long_identifier_splits():
    # A 20-char identifier should be more than one token.
    assert estimate_tokens("a" * 20) >= 5


def test_human_bytes():
    assert human_bytes(512) == "512B"
    assert human_bytes(2048) == "2.0KB"
    assert human_bytes(5 * 1024 * 1024) == "5.0MB"
