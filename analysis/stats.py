"""Paired task-level statistics; all bootstrap draws resample tasks."""
from __future__ import annotations

import math
import random


def paired_bootstrap(values: list[float], resamples: int = 10000,
                     seed: int = 2026092801) -> tuple[float, float, float]:
    if not values:
        raise ValueError("at least one paired task is required")
    if resamples < 1:
        raise ValueError("resamples must be positive")
    rng = random.Random(seed)
    n = len(values)
    draws = sorted(sum(values[rng.randrange(n)] for _ in range(n)) / n
                   for _ in range(resamples))
    return sum(values) / n, draws[int(0.025 * (resamples - 1))], draws[int(0.975 * (resamples - 1))]


def mcnemar_exact(left: list[int], right: list[int]) -> tuple[int, int, float]:
    if len(left) != len(right) or not left:
        raise ValueError("paired arrays must have equal nonzero length")
    b = sum(a == 1 and c == 0 for a, c in zip(left, right, strict=True))
    c = sum(a == 0 and d == 1 for a, d in zip(left, right, strict=True))
    discordant = b + c
    if discordant == 0:
        return b, c, 1.0
    tail = sum(math.comb(discordant, k) for k in range(min(b, c) + 1)) / (2 ** discordant)
    return b, c, min(1.0, 2 * tail)


def holm(p_values: list[float]) -> list[float]:
    indexed = sorted(enumerate(p_values), key=lambda pair: pair[1])
    result = [0.0] * len(p_values)
    previous = 0.0
    for rank, (index, value) in enumerate(indexed):
        previous = max(previous, min(1.0, (len(p_values) - rank) * value))
        result[index] = previous
    return result
