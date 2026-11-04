"""
================================================================================
STEP 10B: COVID-19 PERIODS (PROVINCE-WIDE CHI-SQUARE TEST)
================================================================================

Tests whether the province-wide proportion of expected cases that was
reported differs across the Pre-COVID, COVID and Post-COVID periods,
using a chi-square test of homogeneity of proportions.

Reported and expected cases are pooled over all districts within each
period, over the same district-years that have records. This gives a
3 x 2 table:

                Reported        Not reported
    Pre-COVID      ...              ...
    COVID          ...              ...
    Post-COVID     ...              ...

"Reported" is the total reported cases and "Not reported" is expected
cases minus reported cases. The test asks whether the proportion
reported is the same in all three periods.

Because expected cases here are the sum of annual expected cases for the
district-years that have records, the percentages differ from the
whole-period gaps of Step 8, which use the 2024 reference-year
population.

Input:  panel_with_population_births.csv (Step 3)
        manicaland_case_data.xlsx, sheet "Yearly Counts" (Step 7)
Output: chi_square_proportions_result.csv

Usage:
    python step10b_chi_square_proportions.py
================================================================================
"""

from environment_setup import fix_proj_database
fix_proj_database()

import pandas as pd
from scipy.stats import chi2_contingency


# ------------------------------------------------------------------------------
# SETTINGS
# ------------------------------------------------------------------------------

BASE = r"C:\Users\nhong\OneDrive\Desktop\DISSERTATION FOR SUBMISSION FINALEST\CHAPTER 3 METHODOLOGY"
POPULATION_BIRTHS_FILE = BASE + r"\panel_with_population_births.csv"
CASE_DATA_FILE = BASE + r"\manicaland_case_data.xlsx"
OUTPUT_FILE = BASE + r"\chi_square_proportions_result.csv"

POINT_PREVALENCE = 1.0 / 1000  # per Maheu-Giroux et al. (2015), matching Step 8

# Same period definitions as Step 10.
PERIODS = {
    "Pre-COVID": range(2015, 2020),
    "COVID": range(2020, 2023),
    "Post-COVID": range(2023, 2025),
}


def calculate_province_wide_period_totals(period_years, yearly_reported, population_births, prevalence):
    """
    Sums reported and expected cases across ALL districts, for one
    period, using only real reported district-years.

    Args:
        period_years (range): The years belonging to this period.
        yearly_reported (pandas.DataFrame): Step 7's real yearly counts.
        population_births (pandas.DataFrame): Step 3's output.
        prevalence (float): Point prevalence rate.

    Returns:
        tuple[float, float]: (total reported, total expected), pooled
            across every district.
    """
    period_data = yearly_reported[yearly_reported["year"].isin(period_years)]
    total_reported = period_data["reported_cases"].sum()

    total_expected = 0
    for _, row in period_data.iterrows():
        pop_row = population_births[
            (population_births["district"] == row["district"]) & (population_births["year"] == row["year"])
        ]
        if len(pop_row) > 0:
            total_expected += pop_row["adult_female_population_18plus"].values[0] * prevalence

    return total_reported, total_expected


def run_chi_square_test(period_totals):
    """
    Builds the 2x3 contingency table and runs the Chi-square test of
    homogeneity of proportions across the three periods.

    Args:
        period_totals (dict): {period_name: {"reported": x, "expected": y}}

    Returns:
        tuple[pandas.DataFrame, float, float, int]: (contingency table,
            chi-square statistic, p-value, degrees of freedom).
    """
    rows = []
    for period, vals in period_totals.items():
        reported = vals["reported"]
        not_reported = vals["expected"] - vals["reported"]
        rows.append([reported, not_reported])

    table = pd.DataFrame(rows, index=period_totals.keys(), columns=["Reported", "Not_Reported"])
    chi2, p_value, dof, _ = chi2_contingency(table.values)
    return table, chi2, p_value, dof


def main():
    """
    Runs the full Step 10B pipeline: pools real reported and expected
    cases across all districts within each of the three periods, then
    runs a Chi-square test of homogeneity of proportions.
    """
    print("Loading data...")
    population_births = pd.read_csv(POPULATION_BIRTHS_FILE)
    yearly_reported = pd.read_excel(CASE_DATA_FILE, sheet_name="Yearly Counts")

    period_totals = {}
    for period_name, years in PERIODS.items():
        reported, expected = calculate_province_wide_period_totals(
            years, yearly_reported, population_births, POINT_PREVALENCE
        )
        proportion = reported / expected if expected > 0 else float("nan")
        period_totals[period_name] = {"reported": reported, "expected": expected}
        print(f"{period_name}: Reported={reported}, Expected={expected:.1f}, "
              f"Proportion reported={proportion:.3f}")

    print("\nRunning Chi-square test of homogeneity of proportions...")
    table, chi2, p_value, dof = run_chi_square_test(period_totals)
    print("\n2x3 Contingency table:")
    print(table.to_string())

    print(f"\nChi-square statistic = {chi2:.3f}")
    print(f"Degrees of freedom = {dof}")
    print(f"p-value = {p_value:.6f}")
    print(f"\nConclusion: {'STATISTICALLY SIGNIFICANT' if p_value < 0.05 else 'NOT statistically significant'} "
          f"difference in reporting proportions across the Pre-COVID, COVID, and Post-COVID periods.")

    result = pd.DataFrame([{
        "chi_square_statistic": round(chi2, 3),
        "degrees_of_freedom": dof,
        "p_value": p_value,
        "statistically_significant": p_value < 0.05,
    }])
    result.to_csv(OUTPUT_FILE, index=False)
    print(f"\nSaved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
