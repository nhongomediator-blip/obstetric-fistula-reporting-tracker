"""
================================================================================
STEP 10: COVID-19 PERIOD COMPARISON (DISTRICT LEVEL)
================================================================================

Compares, for each district, the reported-to-expected ratio across three
periods: Pre-COVID (2015-2019), COVID (2020-2022) and Post-COVID
(2023-2024). Three pairwise period rate ratios, each with a 95%
confidence interval, are calculated: COVID vs Pre-COVID, Post-COVID vs
Pre-COVID and Post-COVID vs COVID.

    Period rate ratio = (reported / expected, period 2)
                        / (reported / expected, period 1)

A ratio below 1.0 means reporting relative to expectation fell between
the two periods; above 1.0 means it rose. The interval uses the
log-transformation (delta method) for comparing two independent Poisson
rates (Rothman, Greenland & Lash, 2008; Li, Tang & Wong, 2014).

For each district and period, reported and expected cases are summed
over the years that have records in that period. Expected cases for
each year use that year's projected adult female population x 0.001.
Missing years are left out and never counted as zero. A comparison
cannot be calculated if either period has zero reported cases for the
district (the log ratio is undefined); this is stated in the output.

Input:  panel_with_population_births.csv (Step 3)
        manicaland_case_data.xlsx, sheet "Yearly Counts" (Step 7)
Output: period_comparison_results.csv (one row per district: period
        totals and the three pairwise comparisons)

Usage:
    python step10_compare_covid_periods.py
================================================================================
"""

from environment_setup import fix_proj_database
fix_proj_database()

import pandas as pd
import numpy as np
from scipy import stats


# ------------------------------------------------------------------------------
# SETTINGS
# ------------------------------------------------------------------------------

BASE = r"C:\Users\nhong\OneDrive\Desktop\DISSERTATION FOR SUBMISSION FINALEST\CHAPTER 3 METHODOLOGY"
POPULATION_BIRTHS_FILE = BASE + r"\panel_with_population_births.csv"
CASE_DATA_FILE = BASE + r"\manicaland_case_data.xlsx"
OUTPUT_FILE = BASE + r"\period_comparison_results.csv"

POINT_PREVALENCE = 1.0 / 1000  # per Maheu-Giroux et al. (2015), matching Step 8
CONFIDENCE_LEVEL = 0.95

# Study periods: before, during and after the COVID-19 pandemic.
PERIODS = {
    "pre_covid": range(2015, 2020),   # 2015-2019
    "covid": range(2020, 2023),        # 2020-2022
    "post_covid": range(2023, 2025),   # 2023-2024
}

# Pairwise comparisons: entering COVID, after COVID, and COVID to after.
COMPARISON_PAIRS = [
    ("pre_covid", "covid", "covid_vs_pre"),
    ("pre_covid", "post_covid", "post_vs_pre"),
    ("covid", "post_covid", "post_vs_covid"),
]


def calculate_period_totals(district, years, yearly_reported, population_births, prevalence):
    """
    Sums reported and expected cases for one district across one period,
    using only years with real reported data.

    Args:
        district (str): District name.
        years (range): The years belonging to this period.
        yearly_reported (pandas.DataFrame): Step 7's real yearly counts.
        population_births (pandas.DataFrame): Step 3's output.
        prevalence (float): Point prevalence rate.

    Returns:
        tuple[float, float, int]: (total reported, total expected,
            number of real years contributing).
    """
    district_years = yearly_reported[
        (yearly_reported["district"] == district) & (yearly_reported["year"].isin(years))
    ]
    if len(district_years) == 0:
        return 0, 0, 0

    total_reported = district_years["reported_cases"].sum()

    total_expected = 0
    for _, row in district_years.iterrows():
        pop_row = population_births[
            (population_births["district"] == district) & (population_births["year"] == row["year"])
        ]
        if len(pop_row) > 0:
            total_expected += pop_row["adult_female_population_18plus"].values[0] * prevalence

    return total_reported, total_expected, len(district_years)


def calculate_period_rate_ratio(obs1, exp1, obs2, exp2, confidence_level):
    """
    Calculates the Period Rate Ratio (period 2 vs. period 1) and its 95%
    confidence interval, using the log-transformation (delta method)
    approach for comparing two independent Poisson rates.

    Args:
        obs1, exp1 (float): Reported and expected cases in the baseline period.
        obs2, exp2 (float): Reported and expected cases in the comparison period.
        confidence_level (float): e.g. 0.95.

    Returns:
        tuple[float, float, float, bool] or None: (rate ratio, lower CI,
            upper CI, significant), or None if either period has zero
            reported cases (undefined on the log scale).
    """
    if obs1 == 0 or obs2 == 0:
        return None

    ratio1 = obs1 / exp1
    ratio2 = obs2 / exp2
    rate_ratio = ratio2 / ratio1

    se_log_rr = np.sqrt(1 / obs1 + 1 / obs2)
    z = stats.norm.ppf(1 - (1 - confidence_level) / 2)

    log_rr = np.log(rate_ratio)
    lower = np.exp(log_rr - z * se_log_rr)
    upper = np.exp(log_rr + z * se_log_rr)
    significant = not (lower <= 1.0 <= upper)

    return rate_ratio, lower, upper, significant


def main():
    """
    Runs the full Step 10 pipeline: for each district, calculates the
    reported-to-expected ratio in all three periods, and all three
    pairwise Period Rate Ratios between them, with 95% confidence
    intervals.
    """
    print("Loading data...")
    population_births = pd.read_csv(POPULATION_BIRTHS_FILE)
    yearly_reported = pd.read_excel(CASE_DATA_FILE, sheet_name="Yearly Counts")

    districts = sorted(yearly_reported["district"].unique())
    rows = []

    for district in districts:
        period_totals = {}
        for period_name, years in PERIODS.items():
            obs, exp, n_years = calculate_period_totals(
                district, years, yearly_reported, population_births, POINT_PREVALENCE
            )
            period_totals[period_name] = {"reported": obs, "expected": exp, "years_with_data": n_years}

        row = {"district": district}
        for period_name in PERIODS:
            row[f"{period_name}_years_with_data"] = period_totals[period_name]["years_with_data"]
            row[f"{period_name}_reported"] = period_totals[period_name]["reported"]
            row[f"{period_name}_expected"] = round(period_totals[period_name]["expected"], 1)

        for period1, period2, label in COMPARISON_PAIRS:
            obs1, exp1 = period_totals[period1]["reported"], period_totals[period1]["expected"]
            obs2, exp2 = period_totals[period2]["reported"], period_totals[period2]["expected"]
            result = calculate_period_rate_ratio(obs1, exp1, obs2, exp2, CONFIDENCE_LEVEL)

            if result is None:
                row[f"{label}_rate_ratio"] = None
                row[f"{label}_95CI_lower"] = None
                row[f"{label}_95CI_upper"] = None
                row[f"{label}_significant"] = None
            else:
                rate_ratio, lower, upper, significant = result
                row[f"{label}_rate_ratio"] = round(rate_ratio, 3)
                row[f"{label}_95CI_lower"] = round(lower, 3)
                row[f"{label}_95CI_upper"] = round(upper, 3)
                row[f"{label}_significant"] = significant

        rows.append(row)

    result_df = pd.DataFrame(rows)
    print("\nThree-period totals per district:")
    summary_cols = ["district"] + [f"{p}_reported" for p in PERIODS] + [f"{p}_expected" for p in PERIODS]
    print(result_df[summary_cols].to_string(index=False))

    print("\nPairwise comparisons:")
    for period1, period2, label in COMPARISON_PAIRS:
        cols = ["district", f"{label}_rate_ratio", f"{label}_95CI_lower", f"{label}_95CI_upper", f"{label}_significant"]
        print(f"\n--- {period2} vs {period1} ---")
        print(result_df[cols].to_string(index=False))

    for period1, period2, label in COMPARISON_PAIRS:
        n_sig = result_df[f"{label}_significant"].sum()
        n_calc = result_df[f"{label}_significant"].notna().sum()
        print(f"\n{n_sig} of {n_calc} districts show a statistically significant "
              f"change from {period1} to {period2}.")

    result_df.to_csv(OUTPUT_FILE, index=False)
    print(f"\nSaved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
