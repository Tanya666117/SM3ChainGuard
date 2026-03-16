"""Time related utilities for timestamp matching."""

from __future__ import annotations

from bisect import bisect_left
from typing import Sequence


def nearest_index(sorted_values: Sequence[float], target: float) -> int:
    """Return nearest index in sorted numeric sequence."""
    if not sorted_values:
        raise ValueError("sorted_values must not be empty.")

    pos = bisect_left(sorted_values, target)
    if pos == 0:
        return 0
    if pos == len(sorted_values):
        return len(sorted_values) - 1

    before = sorted_values[pos - 1]
    after = sorted_values[pos]
    return pos if abs(after - target) < abs(target - before) else (pos - 1)
