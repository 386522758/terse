"""The compression pipeline: glue the rules and profiles together."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from . import compressors as C
from .tokens import estimate_tokens, human_bytes


@dataclass
class Result:
    """Outcome of a compression run, with before/after measurements."""

    text: str
    profile: str
    original_chars: int
    compressed_chars: int
    original_tokens: int
    compressed_tokens: int
    notes: List[str] = field(default_factory=list)

    @property
    def token_savings(self) -> int:
        return self.original_tokens - self.compressed_tokens

    @property
    def token_savings_pct(self) -> float:
        if self.original_tokens == 0:
            return 0.0
        return 100.0 * self.token_savings / self.original_tokens

    @property
    def char_savings_pct(self) -> float:
        if self.original_chars == 0:
            return 0.0
        return 100.0 * (self.original_chars - self.compressed_chars) / self.original_chars

    def summary_line(self) -> str:
        """One-line, human-readable stats string for stderr."""
        detail = "; ".join(self.notes) if self.notes else "no noise found"
        return (
            f"{C.MARKER} {self.profile} · "
            f"{self.original_tokens:,}→{self.compressed_tokens:,} tokens "
            f"(-{self.token_savings_pct:.0f}%) · "
            f"{human_bytes(self.original_chars)}→{human_bytes(self.compressed_chars)} · "
            f"{detail}"
        )


def compress(
    text: str,
    profile: str = "generic",
    max_repeat: int = 1,
    keep_ansi: bool = False,
) -> Result:
    """Compress captured command output.

    Parameters
    ----------
    text:
        Raw captured stdout/stderr.
    profile:
        One of :data:`terse.compressors.PROFILES`. ``"generic"`` applies only
        the universal rules.
    max_repeat:
        Keep at most this many identical consecutive lines before collapsing.
    keep_ansi:
        If ``True``, do not strip ANSI escape sequences.
    """
    original_text = text
    original_chars = len(text)
    original_tokens = estimate_tokens(text)
    notes: List[str] = []

    if not keep_ansi:
        stripped = C.strip_ansi(text)
        if stripped != text:
            notes.append("stripped ANSI escape codes")
        text = stripped

    text = C.resolve_carriage_returns(text)
    lines = text.split("\n")

    lines, removed = C.drop_progress_lines(lines)
    if removed:
        notes.append(f"dropped {removed} progress line(s)")

    lines, removed = C.collapse_consecutive_dupes(lines, max_repeat=max_repeat)
    if removed:
        notes.append(f"collapsed {removed} repeated line(s)")

    profile_fn = C.PROFILES.get(profile, C.profile_generic)
    lines, profile_notes = profile_fn(lines)
    notes.extend(profile_notes)

    lines = C.collapse_blank_lines(lines, keep=1)

    out = "\n".join(lines)
    compressed_tokens = estimate_tokens(out)

    # Hard guarantee: terse never makes output bigger. On already-compact input
    # the markers can cost more than they save, so hand back the original.
    if compressed_tokens > original_tokens:
        return Result(
            text=original_text,
            profile=profile,
            original_chars=original_chars,
            compressed_chars=original_chars,
            original_tokens=original_tokens,
            compressed_tokens=original_tokens,
            notes=["input already compact — left unchanged"],
        )

    return Result(
        text=out,
        profile=profile,
        original_chars=original_chars,
        compressed_chars=len(out),
        original_tokens=original_tokens,
        compressed_tokens=compressed_tokens,
        notes=notes,
    )
