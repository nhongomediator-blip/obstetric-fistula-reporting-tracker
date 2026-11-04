"""
================================================================================
EXACT CONDITIONAL PERMUTATION HELPER (used by Step 9 and Step 9c)
================================================================================

WHY THIS FILE EXISTS
With only seven districts, a random permutation test is not needed and
gives misleading p-values. For a district with k neighbours, the null
hypothesis ("the neighbours' values are just any k of the other six
districts' values") has only C(6, k) possible arrangements: 15 for
k = 2 or 4, and 20 for k = 3. This file lists ALL of them, so the p-value
is exact, needs no random seed, and can be checked by hand.

Two rules make the p-value honest:
  1. The observed arrangement is one of the possible arrangements, so the
     smallest p-value that can ever be obtained is 1 / C(6, k)
     (0.067 for 15 arrangements, 0.050 for 20).
  2. Ties count. An arrangement that gives exactly the observed value is
     "as extreme as" the observed value, in both tails.

This file uses only the standard library and numpy, so it cannot be
affected by libpysal / esda version problems.
================================================================================
"""

from itertools import combinations

import numpy as np


def conditional_arrangements(values, i, k):
    """
    Lists the sum of the neighbour values for EVERY possible arrangement.

    District i keeps its own value. Its k neighbours are chosen in every
    possible way from the other n - 1 districts.

    Args:
        values: all n district values.
        i: index of the district being tested.
        k: number of neighbours that district has.

    Returns:
        numpy.ndarray: one neighbour-sum per arrangement
        (length = C(n - 1, k)).
    """
    others = np.delete(np.asarray(values, dtype=float), i)
    return np.array([others[list(c)].sum() for c in combinations(range(len(others)), k)])


def exact_tail_p_values(observed, simulated, tol=1e-9):
    """
    Exact one-sided p-values for an observed statistic.

    Args:
        observed: the observed value of the statistic.
        simulated: the statistic for every possible arrangement.
        tol: tolerance so that equal values are treated as ties.

    Returns:
        (p_high, p_low): the share of arrangements at least as high as,
        and at least as low as, the observed value. Ties are included in
        both, so neither can be smaller than 1 / number of arrangements.
    """
    simulated = np.asarray(simulated, dtype=float)
    p_high = float(np.mean(simulated >= observed - tol))
    p_low = float(np.mean(simulated <= observed + tol))
    return p_high, p_low
