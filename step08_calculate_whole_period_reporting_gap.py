"""
================================================================================
STEP 8: REPORTING GAP (WHOLE PERIOD)
================================================================================

Calculates the reporting gap for each district: the shortfall of
reported cases against expected cases, with a 95% confidence interval.

    Expected cases   = adult female population (18+) x 0.001
    Reporting gap %  = (1 - reported / expected) x 100
    Ratio            = reported / expected

The prevalence of 1.0 case per 1,000 women is from Maheu-Giroux et al.
(2015), a meta-analysis of national household surveys in 19
sub-Saharan African countries. A prevalence benchmark is used because
repair camp records contain women who developed fistula years earlier,
so they represent an accumulated caseload and not only new cases.

For the whole period, expected cases use each district's adult female
population in the reference year (the latest year in the panel, 2024).
Reported cases are the district's total over all years with records.

The confidence interval is the exact Poisson interval for the count of
reported cases, in chi-square form, divided by expected cases. A gap is
significant when the interval for the ratio excludes 1.0.

Input:  panel_with_population_births.csv (Step 3)
        manicaland_case_data.xlsx, sheet "Whole-Period Totals" (Step 7)
Output: reporting_gap_results.csv (one row per district: reported,
        expected, ratio, 95% interval, gap %, significance)

Usage:
    python step08_calculate_whole_period_reporting_gap.py
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
OUTPUT_FILE = BASE + r"\reporting_gap_results.csv"

# Point prevalence of vaginal fistula symptoms, per Maheu-Giroux et al.
# (2015): 1.0 per 1,000 women of reproductive age (95% CrI 0.3-2.4).
POINT_PREVALENCE = 1.0 / 1000

CONFIDENCE_LEVEL = 0.95


def calculate_expected_cases(population_births_file, prevalence):
    """
    Calculates each district's expected case count, using the most
    recent available adult female population and the point prevalence
    rate (prevalence-based, per the module docstring above).

    Args:
        population_births_file (str): Path to Step 3's output.
        prevalence (float): Point prevalence rate (cases per woman).

    Returns:
        pandas.DataFrame: Columns "district" and "expected_cases".
    """
    panel = pd.read_csv(population_births_file)
    # Use the most recent year's adult female population per district as
    # the representative population figure for the whole-period comparison.
    latest = panel.sort_values("year").groupby("district").tail(1)
    latest = latest[["district", "adult_female_population_18plus"]].copy()
    latest["expected_cases"] = latest["adult_female_population_18plus"] * prevalence
    return latest[["district", "expected_cases"]]


def load_reported_cases(case_data_file):
    """
    Loads each district's whole-period reported case total
    from Step 7's output.

    Args:
        case_data_file (str): Path to Step 7's output Excel file.

    Returns:
        pandas.DataFrame: Columns "district" and "reported_cases".
    """
    totals = pd.read_excel(case_data_file, sheet_name="Whole-Period Totals")
    totals = totals.rename(columns={"total_reported_cases": "reported_cases"})
    return totals[["district", "reported_cases"]]


def calculate_ratio_with_confidence_interval(reported, expected, confidence_level):
    """
    Calculates the reported-to-expected ratio and its exact Poisson
    confidence interval for one district.

    Args:
        reported (float): Reported case count.
        expected (float): Expected case count.
        confidence_level (float): e.g. 0.95 for a 95% confidence interval.

    Returns:
        tuple[float, float, float, bool]: (ratio, lower CI bound, upper
            CI bound, statistically significant -- i.e. CI excludes 1.0).
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
    Runs the full Step 8 pipeline: calculates prevalence-based expected
    cases per district (from Step 3), loads reported cases per district
    (from Step 7), calculates the reported-to-expected ratio with a 95%
    confidence interval for each district, and saves the result.
    """
    print("Calculating prevalence-based expected cases from Step 3's output...")
    expected = calculate_expected_cases(POPULATION_BIRTHS_FILE, POINT_PREVALENCE)

    print("Loading reported cases from Step 7's output...")
    reported = load_reported_cases(CASE_DATA_FILE)

    result = expected.merge(reported, on="district", how="left")
    missing = result[result["reported_cases"].isna()]["district"].tolist()
    if missing:
        # A district with no records is missing, never zero cases.
        raise ValueError(f"No case records found for: {missing}")

    print("\nCalculating reported-to-expected ratio with 95% confidence intervals...")
    rows = []
    for _, row in result.iterrows():
        ratio, lower, upper, significant = calculate_ratio_with_confidence_interval(
            row["reported_cases"], row["expected_cases"], CONFIDENCE_LEVEL
        )
        reporting_gap_pct = (1 - row["reported_cases"] / row["expected_cases"]) * 100
        rows.append({
            "district": row["district"],
            "expected_cases": round(row["expected_cases"], 1),
            "reported_cases": int(row["reported_cases"]),
            "reporting_gap_pct": round(reporting_gap_pct, 1),
            "reported_to_expected_ratio": round(ratio, 3),
            "ratio_95CI_lower": round(lower, 3),
            "ratio_95CI_upper": round(upper, 3),
            "statistically_significant": significant,
        })

    final = pd.DataFrame(rows).sort_values("reported_to_expected_ratio")

    print("\nResults (sorted by ratio, lowest/most under-reported first):")
    print(final.to_string(index=False))

    n_significant = final["statistically_significant"].sum()
    print(f"\n{n_significant} of {len(final)} districts show a STATISTICALLY SIGNIFICANT "
          f"reporting gap (95% CI excludes 1.0).")

    final.to_csv(OUTPUT_FILE, index=False)
    print(f"\nSaved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
