"""terse — compress noisy command output before it reaches an LLM agent."""

__version__ = "0.1.0"

from .core import Result, compress

__all__ = ["compress", "Result", "__version__"]
