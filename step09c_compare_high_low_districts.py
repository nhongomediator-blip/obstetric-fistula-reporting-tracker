"""
================================================================================
STEP 9C: HIGH-GAP VERSUS LOW-GAP DISTRICTS
================================================================================

Compares districts with high and low reporting gaps in two ways:

  1. Mann-Whitney U test: districts are split into a high-gap group and
     a low-gap group and the test asks whether the groups' gap values
     differ by more than chance. A split of seven districts into three
     and four gives a smallest possible p-value of 0.057, so this test
     is secondary and descriptive.

  2. Local Moran's I (LISA): classifies each district by its relation
     to its neighbours as High-High, Low-Low, High-Low, Low-High or not
     significant. Neighbours are defined by Queen contiguity. The local
     statistic is I = z x (average z of the neighbours), where z is the
     district's standardised gap. Significance is assessed with an EXACT
     conditional permutation test: with seven districts, a district with
     k neighbours has only C(6, k) possible arrangements of neighbour
     values (15 or 20), so every arrangement is listed and no random
     numbers or seed are needed (see exact_permutation.py). The p-value
     is one-sided, in the direction of the district's own I.
     Because the observed arrangement is itself one of the possible
     arrangements, the smallest p-value attainable is 1/15 = 0.067 for
     districts with 2 or 4 neighbours and 1/20 = 0.050 for districts with
     3 neighbours. A district is classified as significant only if p is
     BELOW 0.05, so on this map of seven districts no district can be
     classified as significant. The quadrant (High-High, Low-Low and so
     on) is still reported as the direction of the pattern.

Explanatory variables (poverty, literacy, distance) are not tested here.
They are examined in Step 11.

Input:  manicaland_study_area.geojson (Step 1)
        reporting_gap_results.csv (Step 8)
Output: high_low_comparison_results.csv (Mann-Whitney U result)
        lisa_results.csv (LISA classification for each district; same
        columns as before)

Usage:
    python step09c_compare_high_low_districts.py
================================================================================
"""

from environment_setup import fix_proj_database
fix_proj_database()

import geopandas as gpd
import pandas as pd
import numpy as np
from scipy import stats
from libpysal.weights import Queen

from exact_permutation import conditional_arrangements, exact_tail_p_values


# ------------------------------------------------------------------------------
# SETTINGS
# ------------------------------------------------------------------------------

BASE = r"C:\Users\nhong\OneDrive\Desktop\DISSERTATION FOR SUBMISSION FINALEST\CHAPTER 3 METHODOLOGY"
STUDY_AREA_FILE = BASE + r"\manicaland_study_area.geojson"
REPORTING_GAP_FILE = BASE + r"\reporting_gap_results.csv"

MANN_WHITNEY_OUTPUT_FILE = BASE + r"\high_low_comparison_results.csv"
LISA_OUTPUT_FILE = BASE + r"\lisa_results.csv"

ALPHA = 0.05  # a district is significant only if its exact p-value is BELOW this


def split_high_low_groups(reporting_gap):
    """
    Splits districts into High Gap and Low Gap groups using a median
    split on reporting_gap_pct (Step 8's real whole-period result).

    Args:
        reporting_gap (pandas.DataFrame): Step 8's output.

    Returns:
        pandas.DataFrame: The input with a new "gap_group" column
            ("High Gap" or "Low Gap").
    """
    median_gap = reporting_gap["reporting_gap_pct"].median()
    reporting_gap = reporting_gap.copy()
    reporting_gap["gap_group"] = np.where(
        reporting_gap["reporting_gap_pct"] > median_gap, "High Gap", "Low Gap"
    )
    return reporting_gap


def run_mann_whitney_test(reporting_gap_grouped):
    """
    Runs a Mann-Whitney U test comparing the High Gap and Low Gap
    groups' own reporting gap values -- a formal test of whether the
    apparent split is a statistically real difference, not just an
    artefact of the median split.

    Args:
        reporting_gap_grouped (pandas.DataFrame): Output of
            split_high_low_groups().

    Returns:
        pandas.DataFrame: A single-row summary of the test result.
    """
    high_group = reporting_gap_grouped[reporting_gap_grouped["gap_group"] == "High Gap"]
    low_group = reporting_gap_grouped[reporting_gap_grouped["gap_group"] == "Low Gap"]

    u_stat, p_value = stats.mannwhitneyu(
        high_group["reporting_gap_pct"], low_group["reporting_gap_pct"], alternative="two-sided"
    )

    return pd.DataFrame([{
        "high_gap_median_pct": round(high_group["reporting_gap_pct"].median(), 2),
        "low_gap_median_pct": round(low_group["reporting_gap_pct"].median(), 2),
        "high_gap_n": len(high_group),
        "low_gap_n": len(low_group),
        "U_statistic": round(u_stat, 2),
        "p_value": round(p_value, 4),
        "significant": p_value < 0.05,
    }])


def lisa_quadrant(z_value, neighbour_average):
    """
    Names the LISA quadrant from the signs of the district's own
    standardised gap and the average of its neighbours'.

    Args:
        z_value (float): The district's standardised gap.
        neighbour_average (float): Average standardised gap of its neighbours.

    Returns:
        str: "High-High", "Low-Low", "High-Low" or "Low-High".
    """
    own = "High" if z_value > 0 else "Low"
    around = "High" if neighbour_average > 0 else "Low"
    return f"{own}-{around}"


def run_lisa(study_area, reporting_gap):
    """
    Runs Local Moran's I (LISA) on the reporting gap with exact
    conditional permutation p-values, classifying each district as
    High-High, Low-Low, High-Low, Low-High, or Not significant.

    For district i, with row-standardised weights:
        I_i = z_i x (average z of its neighbours)
    where z is the gap standardised by the mean and sample standard
    deviation of all seven districts (the same scaling esda used, so the
    I values match the earlier output). The p-value is the share of all possible
    arrangements of neighbour values (ties included) that give a value
    of I at least as extreme as the observed one, in the direction of
    the observed I.

    Args:
        study_area (geopandas.GeoDataFrame): Step 1's district boundaries.
        reporting_gap (pandas.DataFrame): Step 8's output, same district
            order as study_area.

    Returns:
        pandas.DataFrame: One row per district, with LISA classification.
    """
    weights = Queen.from_dataframe(study_area, use_index=False)
    neighbours = [list(weights.neighbors[i]) for i in range(len(study_area))]

    values = reporting_gap["reporting_gap_pct"].values.astype(float)
    z = (values - values.mean()) / values.std(ddof=1)  # sample standard deviation, as in the earlier esda output

    rows = []
    for i, district in enumerate(study_area["district"]):
        k = len(neighbours[i])
        neighbour_average = z[neighbours[i]].mean()
        local_i = z[i] * neighbour_average

        # every possible arrangement of neighbour values (conditional on z_i)
        simulated_i = z[i] * conditional_arrangements(z, i, k) / k
        p_high, p_low = exact_tail_p_values(local_i, simulated_i)
        p_value = p_high if local_i > 0 else p_low

        significant = round(p_value, 6) < ALPHA
        rows.append({
            "district": district,
            "reporting_gap_pct": values[i],
            "lisa_I": round(local_i, 3),
            "p_value": round(p_value, 4),
            "classification": lisa_quadrant(z[i], neighbour_average) if significant else "Not significant",
            "_direction": lisa_quadrant(z[i], neighbour_average),
            "_smallest_possible_p": round(1 / len(simulated_i), 4),
        })
    return pd.DataFrame(rows)


def main():
    """
    Runs the full Step 9C pipeline: loads district boundaries and
    whole-period reporting gaps, runs a Mann-Whitney U test comparing
    the High Gap and Low Gap district groups, and runs LISA to
    spatially classify each district's relationship to its neighbours.
    """
    print("Loading data...")
    study_area = gpd.read_file(STUDY_AREA_FILE).sort_values("district").reset_index(drop=True)
    reporting_gap = pd.read_csv(REPORTING_GAP_FILE).sort_values("district").reset_index(drop=True)

    if list(study_area["district"]) != list(reporting_gap["district"]):
        raise ValueError("District order mismatch between study area and reporting gap data.")

    print("\n--- Mann-Whitney U Test: High Gap vs. Low Gap districts ---")
    reporting_gap_grouped = split_high_low_groups(reporting_gap)
    print("\nGroup assignment:")
    print(reporting_gap_grouped[["district", "reporting_gap_pct", "gap_group"]].to_string(index=False))

    mw_result = run_mann_whitney_test(reporting_gap_grouped)
    print("\nMann-Whitney U test result:")
    print(mw_result.to_string(index=False))
    print("\nNote: with only 7 districts split into two small groups, this test has")
    print("very limited statistical power -- see module docstring.")

    mw_result.to_csv(MANN_WHITNEY_OUTPUT_FILE, index=False)
    print(f"\nSaved Mann-Whitney result to: {MANN_WHITNEY_OUTPUT_FILE}")

    print("\n\n--- Local Moran's I (LISA), exact conditional permutation ---")
    lisa_results = run_lisa(study_area, reporting_gap)
    saved_columns = ["district", "reporting_gap_pct", "lisa_I", "p_value", "classification"]
    print("\nLISA classification results:")
    print(lisa_results[saved_columns].to_string(index=False))

    print("\nDirection of each district's pattern, and the smallest p-value its number of")
    print("neighbours allows (a district cannot be significant unless p is below 0.05):")
    print(lisa_results[["district", "_direction", "p_value", "_smallest_possible_p"]]
          .rename(columns={"_direction": "direction", "_smallest_possible_p": "smallest_possible_p"})
          .to_string(index=False))

    n_significant = (lisa_results["classification"] != "Not significant").sum()
    print(f"\n{n_significant} of {len(lisa_results)} districts show a statistically "
          f"significant spatial relationship with their neighbours.")

    lisa_results[saved_columns].to_csv(LISA_OUTPUT_FILE, index=False)
    print(f"\nSaved LISA results to: {LISA_OUTPUT_FILE}")


if __name__ == "__main__":
    main()
