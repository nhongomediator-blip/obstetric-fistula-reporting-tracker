"""
dash02_confidence_intervals.py

DASHBOARD 02: decide whether a gap is REAL or could be chance.

WHY WE NEED THIS
A district can show a gap of 80% just because only a handful of cases were
counted. With such small numbers, luck matters. So next to every gap put a
95% interval (a range of believable values) and a verdict: is the gap
"significant" (clearly real) or "not distinguishable" from the expected level?

THE METHOD (same as Objective 1 in the study)
  Cases are counts of rare events, so use the exact Poisson interval.
  1. Take the reported count k and find the lowest and highest numbers of
     cases that would be believable (the 95% interval for k).
  2. Divide both by the expected cases. This gives a ratio: reported/expected.
  3. RULE:  if the whole interval sits BELOW 1.0, reported is clearly lower
            than expected  -> "Significant gap"
            if the whole interval sits ABOVE 1.0 -> "Above expected"
            if the interval includes 1.0          -> "Not distinguishable"

  (A ratio of 1.0 means "exactly as many cases as expected".)

HOW TO RUN
    pip install pandas scipy
    python dash02_confidence_intervals.py
"""

from pathlib import Path
import pandas as pd
from scipy.stats import chi2

HERE = Path(__file__).parent
DATA_FILE = HERE / "data" / "entries.csv"

ADULT_FEMALE_POP_2022 = {
    "Buhera": 72063, "Chimanimani": 41821, "Chipinge": 108538, "Makoni": 90288,
    "Mutare": 149509, "Mutasa": 56047, "Nyanga": 40515,
}
ANNUAL_GROWTH, PREVALENCE, REFERENCE_YEAR = 1.015, 0.001, 2024

# Objective 1 intervals (reported / expected), used only to check the answer.
THESIS_RATIO_CI = {
    "Makoni": (0.082, 0.253), "Mutasa": (0.071, 0.296), "Nyanga": (0.166, 0.533),
    "Mutare": (0.297, 0.501), "Buhera": (0.340, 0.671),
    "Chimanimani": (0.394, 0.884), "Chipinge": (0.504, 0.811),
}


def expected_cases(district, year):
    """Adult women in that year x 0.001 (see dash01)."""
    return ADULT_FEMALE_POP_2022[district] * ANNUAL_GROWTH ** (year - 2022) * PREVALENCE


# ----------------------------------------------------------------------------
# STEP 1: THE EXACT POISSON INTERVAL
# ----------------------------------------------------------------------------
def poisson_interval(k, confidence=0.95):
    """
    Lowest and highest believable counts, given that we saw k cases.

    The formula uses the chi-square distribution. This is the standard exact
    method; it works even when k is 0 or very small, where simple
    "plus or minus" formulas fail.
    """
    tail = (1 - confidence) / 2                      # 0.025 at each end
    lowest = 0.0 if k == 0 else chi2.ppf(tail, 2 * k) / 2
    highest = chi2.ppf(1 - tail, 2 * k + 2) / 2
    return lowest, highest


print("STEP 1: the interval for one district (Makoni, 14 cases)")
low, high = poisson_interval(14)
print(f"  We counted 14 cases. Believable range: {low:.2f} to {high:.2f}")

expected = expected_cases("Makoni", REFERENCE_YEAR)
print(f"  Expected cases: {expected:.1f}")
print(f"  Ratio (reported / expected): 14 / {expected:.1f} = {14 / expected:.3f}")
print(f"  Ratio interval: {low:.2f}/{expected:.1f} to {high:.2f}/{expected:.1f} = "
      f"{low / expected:.3f} to {high / expected:.3f}")
print("  The whole interval is below 1.0, so Makoni's gap is significant.")


# ----------------------------------------------------------------------------
# STEP 2: TURN THE INTERVAL INTO A GAP RANGE AND A VERDICT
# ----------------------------------------------------------------------------
def gap_with_verdict(reported, expected):
    """Gap %, its 95% range, and the significant / not significant verdict."""
    low, high = poisson_interval(reported)
    ratio_low, ratio_high = low / expected, high / expected

    # Gap = 1 - ratio, so a HIGH ratio gives a LOW gap: the ends swap places.
    gap = (1 - reported / expected) * 100
    gap_low = (1 - ratio_high) * 100
    gap_high = (1 - ratio_low) * 100

    if ratio_high < 1:
        verdict = "Significant gap"
    elif ratio_low > 1:
        verdict = "Above expected"
    else:
        verdict = "Not distinguishable"
    return gap, gap_low, gap_high, ratio_low, ratio_high, verdict


# ----------------------------------------------------------------------------
# STEP 3: THE FULL TABLE
# ----------------------------------------------------------------------------
print("\nSTEP 3: gap, range and verdict for every district")
entries = pd.read_csv(DATA_FILE)
first_time_only = entries[entries["first_time"] == "Yes"]

rows = []
for district in ADULT_FEMALE_POP_2022:
    reported = int(first_time_only.loc[first_time_only["district"] == district, "count"].sum())
    expected = expected_cases(district, REFERENCE_YEAR)
    gap, g_lo, g_hi, r_lo, r_hi, verdict = gap_with_verdict(reported, expected)
    rows.append({"District": district, "Reported": reported, "Expected": round(expected, 1),
                 "Gap %": round(gap, 1), "Gap range": f"{g_lo:.1f} to {g_hi:.1f}",
                 "Verdict": verdict, "_ratio_low": r_lo, "_ratio_high": r_hi})

table = pd.DataFrame(rows).sort_values("Gap %", ascending=False)
print(table.drop(columns=["_ratio_low", "_ratio_high"]).to_string(index=False))


# ----------------------------------------------------------------------------
# STEP 4: CHECK AGAINST THE STUDY
# ----------------------------------------------------------------------------
print("\nSTEP 4: check the ratio intervals against Chapter 4")
all_match = True
for _, r in table.iterrows():
    t_lo, t_hi = THESIS_RATIO_CI[r["District"]]
    ok = abs(r["_ratio_low"] - t_lo) < 0.0015 and abs(r["_ratio_high"] - t_hi) < 0.0015
    all_match &= ok
    print(f"  {r['District']:<12} ours {r['_ratio_low']:.3f} to {r['_ratio_high']:.3f}   "
          f"thesis {t_lo:.3f} to {t_hi:.3f}   {'OK' if ok else 'MISMATCH'}")

print("\nAll intervals match the study." if all_match else "\nSomething does not match.")
