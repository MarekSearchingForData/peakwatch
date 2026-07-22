"""Unit tests for the peak-probability model's probability math."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from peakwatch.peakmodel import exceed_prob


QP = np.array([20000, 21000, 21800, 22400, 23500])  # p05..p95 predicted maxes


def test_threshold_below_all_quantiles_is_near_certain():
    assert exceed_prob(QP, 18000) == 0.99


def test_threshold_above_all_quantiles_is_near_zero():
    assert exceed_prob(QP, 25000) == 0.01


def test_threshold_at_median_gives_half():
    assert abs(exceed_prob(QP, 21800) - 0.5) < 1e-9


def test_monotone_decreasing_in_threshold():
    ps = [exceed_prob(QP, t) for t in (20500, 21500, 22000, 23000)]
    assert all(a >= b for a, b in zip(ps, ps[1:]))


def test_handles_unsorted_quantiles():
    shuffled = np.array([21800, 20000, 23500, 21000, 22400])
    assert abs(exceed_prob(shuffled, 21800) - 0.5) < 1e-9
