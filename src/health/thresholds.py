"""Piecewise-linear interpolation and step-band helpers for the scoring engine."""
from __future__ import annotations


def interpolate_score(value, table):
    if value is None or value != value:
        return 0.0
    t = sorted(table, key=lambda p: p[0])
    if value <= t[0][0]:
        return t[0][1]
    if value >= t[-1][0]:
        return t[-1][1]
    for (x0, y0), (x1, y1) in zip(t, t[1:]):
        if x0 <= value <= x1:
            return y0 if x1 == x0 else y0 + (value - x0) / (x1 - x0) * (y1 - y0)
    return t[-1][1]


def band_score(value, table):
    """table = [(min_value_inclusive, score)]; returns score of the highest band reached."""
    if value is None or value != value:
        return 0.0
    for min_v, score in sorted(table, key=lambda p: -p[0]):
        if value >= min_v:
            return score
    return 0.0
