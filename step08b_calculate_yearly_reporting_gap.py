"""
================================================================================
STEP 8B: REPORTING GAP BY YEAR
================================================================================

Calculates the reported-to-expected ratio and its 95% confidence
interval for every district-year that has records, to show how each
district's gap changed from year to year.

Single years often contain very few cases and so have wide intervals.
The whole-period results of Step 8 are the primary comparison; these
yearly results are descriptive.

Expected cases for each district-year use that year's projected adult
female population x 0.001. A district-year with no records is missing,
not zero, so the ratio is calculated only for district-years that have
records.

Input:  panel_with_population_births.csv (Step 3)
        manicaland_case_data.xlsx, sheet "Yearly Counts" (Step 7)
Output: yearly_reporting_gap_results.csv (one row per district-year
        with records)

Usage:
    python step08b_calculate_yearly_reporting_gap.py
================================================================================
"""

from environment_setup import fix_proj_database
fix_proj_database()

import pandas as pd
from scipy import stats


# ------------------------------------------------------------------------------
# SETTINGS
# ------------------------------------------------------------------------------

BASE = r"C:\Users\nhong\OneDrive\Desktop\DISSERTATION FOR SUBMISSION FINALEST\CHAPTER 3 METHODOLOGY"
POPULATION_BIRTHS_FILE = BASE + r"\panel_with_population_births.csv"
CASE_DATA_FILE = BASE + r"\manicaland_case_data.xlsx"
OUTPUT_FILE = BASE + r"\yearly_reporting_gap_results.csv"

POINT_PREVALENCE = 1.0 / 1000  # per Maheu-Giroux et al. (2015)
CONFIDENCE_LEVEL = 0.95


def calculate_ratio_with_confidence_interval(reported, expected, confidence_level):
    """
    Calculates the reported-to-expected ratio and its exact Poisson confidence interval for one
    district-year. Identical method to Step 8, applied here at yearly
    granularity instead of whole-period totals.

    Args:
        reported (float): Reported case count for this
            district-year.
        expected (float): Expected case count for this district-year.
        confidence_level (float): e.g. 0.95 for a 95% confidence interval.

    Returns:
        tuple[float, float, float, bool]: (ratio, lower CI bound, upper CI
            bound, statistically significant).
    """
    alpha = 1 - confidence_level
    ratio = reported / expected

    if reported == 0:
        lower_count = 0
        upper_count = stats.chi2.ppf(1 - alpha / 2, 2 * (reported + 1)) / 2
    else:
        lower_count = stats.chi2.ppf(alpha / 2, 2 * reported) / 2
        upper_count = stats.chi2.ppf(1 - alpha / 2, 2 * (reported + 1)) / 2

    lower_ratio = lower_count / expected
    upper_ratio = upper_count / expected
    significant = not (lower_ratio <= 1.0 <= upper_ratio)

    return ratio, lower_ratio, upper_ratio, significant


def main():
    """
    Runs the full Step 8B pipeline: loads real yearly reported cases
    (Step 7) and calculates the matching expected cases for that exact
    year (Step 3), then computes the reported-to-expected ratio with a 95% confidence interval for
    every district-year with real data.
    """
    print("Loading population/births data from Step 3's output...")
    population_births = pd.read_csv(POPULATION_BIRTHS_FILE)

    print("Loading real yearly reported cases from Step 7's output...")
    yearly_reported = pd.read_excel(CASE_DATA_FILE, sheet_name="Yearly Counts")

    # Match each real reported district-year to its exact expected cases
    # for that SAME year (not a whole-period total).
    merged = yearly_reported.merge(
        population_births[["district", "year", "adult_female_population_18plus"]],
        on=["district", "year"],
        how="left"
    )
    merged["expected_cases"] = merged["adult_female_population_18plus"] * POINT_PREVALENCE

    print(f"\nCalculating reported-to-expected ratio for {len(merged)} real district-year observations...")
    rows = []
    for _, row in merged.iterrows():
        ratio, lower, upper, significant = calculate_ratio_with_confidence_interval(
            row["reported_cases"], row["expected_cases"], CONFIDENCE_LEVEL
        )
        rows.append({
            "district": row["district"],
            "year": int(row["year"]),
            "expected_cases": round(row["expected_cases"], 1),
            "reported_cases": int(row["reported_cases"]),
            "reported_to_expected_ratio": round(ratio, 3),
            "ratio_95CI_lower": round(lower, 3),
            "ratio_95CI_upper": round(upper, 3),
            "statistically_significant": significant,
        })

    result = pd.DataFrame(rows).sort_values(["district", "year"])

    print("\nYearly reported-to-expected ratio results:")
    print(result.to_string(index=False))

    n_significant = result["statistically_significant"].sum()
    print(f"\n{n_significant} of {len(result)} district-years show a statistically "
          f"significant reporting gap (95% CI excludes 1.0).")
    print("\nNote: individual-year results are more statistically volatile than the")
    print("whole-period totals in Step 8, due to smaller case counts per year --")
    print("interpret a single non-significant year with caution, not as proof of 'no gap'.")

    result.to_csv(OUTPUT_FILE, index=False)
    print(f"\nSaved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
