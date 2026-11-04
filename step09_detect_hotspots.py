"""
================================================================================
STEP 9: HOTSPOT DETECTION (LOCAL GETIS-ORD Gi*)
================================================================================

Tests whether districts with large reporting gaps are concentrated in
particular parts of the province. The local Getis-Ord Gi* statistic is
calculated for each district, using the district together with its
neighbours, and compared with the provincial mean. Districts with a
significantly high local value are hotspots (large gaps) and those with
a significantly low value are cold spots (small gaps).

Settings:
  - Neighbours: Queen contiguity (districts sharing any part of a
    border).
  - Gi* includes each district in its own neighbourhood (the district
    plus its neighbours). The z-score is the standard Getis-Ord Gi*
    z-score (Ord & Getis, 1995), calculated directly in this script.
  - Significance: an EXACT conditional permutation test. With seven
    districts, a district with k neighbours has only C(6, k) possible
    arrangements of neighbour values (15 or 20), so every arrangement is
    listed and no random numbers or seed are needed (see
    exact_permutation.py). The p-value is one-sided, in the direction of
    the district's own z-score.
  - Because the observed arrangement is itself one of the possible
    arrangements, the smallest p-value attainable is 1/15 = 0.067 for
    districts with 2 or 4 neighbours and 1/20 = 0.050 for districts with
    3 neighbours. A district is classified as significant only if p is
    BELOW 0.05, and on this map of seven districts no district can reach
    that, because even the most extreme arrangement gives p = 0.050 or
    more. The results therefore show direction (which districts lean
    high or low) but cannot show statistical significance.

Input:  manicaland_study_area.geojson (Step 1)
        reporting_gap_results.csv (Step 8)
Output: hotspot_results.csv (Gi* z-score, p-value and classification
        for each district; same columns as before)

Usage:
    python step09_detect_hotspots.py
================================================================================
"""

from environment_setup import fix_proj_database
fix_proj_database()

import geopandas as gpd
import pandas as pd
import numpy as np
from libpysal.weights import Queen

from exact_permutation import conditional_arrangements, exact_tail_p_values


# ------------------------------------------------------------------------------
# SETTINGS
# ------------------------------------------------------------------------------

BASE = r"C:\Users\nhong\OneDrive\Desktop\DISSERTATION FOR SUBMISSION FINALEST\CHAPTER 3 METHODOLOGY"
STUDY_AREA_FILE = BASE + r"\manicaland_study_area.geojson"
REPORTING_GAP_FILE = BASE + r"\reporting_gap_results.csv"
OUTPUT_FILE = BASE + r"\hotspot_results.csv"

# Value tested for spatial clustering: the reporting gap percentage
# (higher = more severe under-reporting), so hotspots = clusters of
# severe under-reporting.
VALUE_COLUMN = "reporting_gap_pct"

ALPHA = 0.05  # a district is significant only if its exact p-value is BELOW this


def build_neighbour_lists(study_area):
    """
    Finds each district's neighbours using Queen contiguity: two districts
    are neighbours if they share any part of a border.

    Args:
        study_area (geopandas.GeoDataFrame): District boundaries, sorted
            to match the order of the reporting gap data.

    Returns:
        list of list of int: for each district (by row position), the row
        positions of its neighbours.
    """
    weights = Queen.from_dataframe(study_area, use_index=False)
    return [list(weights.neighbors[i]) for i in range(len(study_area))]


def getis_ord_star_z(values, neighbours, i):
    """
    Standard Getis-Ord Gi* z-score for district i (Ord & Getis, 1995).

    The neighbourhood is district i plus its neighbours (binary weights;
    the z-score is the same whether or not the weights are row-
    standardised). The local sum of values is compared with what would be
    expected if the neighbourhood were any group of the same size drawn
    from all seven districts.

    Args:
        values (numpy.ndarray): The variable being tested (reporting gap).
        neighbours (list of list of int): Neighbours of every district.
        i (int): Position of the district being tested.

    Returns:
        float: The Gi* z-score. Positive = high values cluster here
        (hotspot direction); negative = low values cluster here.
    """
    n = len(values)
    neighbourhood = [i] + list(neighbours[i])
    size = len(neighbourhood)                      # sum of weights (each weight = 1)
    mean = values.mean()
    sd = np.sqrt((values ** 2).mean() - mean ** 2)
    local_sum = values[neighbourhood].sum()
    spread = sd * np.sqrt((n * size - size ** 2) / (n - 1))
    return (local_sum - size * mean) / spread


def exact_p_value(values, neighbours, i, z_score):
    """
    Exact one-sided conditional permutation p-value for district i, in the
    direction of its z-score.

    Every possible way of choosing the district's neighbours from the
    other six districts is listed. The p-value is the share of those
    arrangements that give a local sum at least as extreme as the
    observed one (ties included).

    Args:
        values (numpy.ndarray): The variable being tested.
        neighbours (list of list of int): Neighbours of every district.
        i (int): Position of the district being tested.
        z_score (float): The district's Gi* z-score (sets the direction).

    Returns:
        tuple: (p_value, number_of_arrangements)
    """
    k = len(neighbours[i])
    observed = values[i] + values[neighbours[i]].sum()
    simulated = values[i] + conditional_arrangements(values, i, k)
    p_high, p_low = exact_tail_p_values(observed, simulated)
    p_value = p_high if z_score > 0 else p_low
    return p_value, len(simulated)


def classify_hotspot(z_score, p_value, alpha=ALPHA):
    """
    Classifies a district as a hotspot, cold spot, or not significant,
    based on its Gi* z-score and exact p-value.

    Args:
        z_score (float): The district's Gi* z-score.
        p_value (float): The district's exact one-sided p-value.
        alpha (float): Significance threshold (default 0.05).

    Returns:
        str: "Hotspot", "Cold spot", or "Not significant".
    """
    if round(p_value, 6) >= alpha:
        return "Not significant"
    return "Hotspot" if z_score > 0 else "Cold spot"


def main():
    """
    Runs the full Step 9 pipeline: loads district boundaries and
    whole-period reporting gaps, finds Queen contiguity neighbours,
    calculates the Gi* z-score and exact conditional permutation p-value
    for each district, and saves the per-district classification.
    """
    print("Loading study area boundaries from Step 1...")
    study_area = gpd.read_file(STUDY_AREA_FILE).sort_values("district").reset_index(drop=True)

    print("Loading whole-period reporting gap results from Step 8...")
    reporting_gap = pd.read_csv(REPORTING_GAP_FILE).sort_values("district").reset_index(drop=True)

    # Confirm both datasets have exactly the same districts, in the same order,
    # before doing any spatial analysis -- a mismatch here would silently
    # misalign values with the wrong district's geometry.
    if list(study_area["district"]) != list(reporting_gap["district"]):
        raise ValueError(
            "District order mismatch between study area and reporting gap data. "
            f"Study area: {list(study_area['district'])}. "
            f"Reporting gap: {list(reporting_gap['district'])}."
        )

    values = reporting_gap[VALUE_COLUMN].values.astype(float)
    districts = list(study_area["district"])

    print("\nFinding neighbours with Queen contiguity (which districts share a border)...")
    neighbours = build_neighbour_lists(study_area)
    print("Neighbours found for each district:")
    for i, district in enumerate(districts):
        print(f"  {district}: {[districts[j] for j in neighbours[i]]}")

    print("\nCalculating Gi* z-scores and exact conditional permutation p-values...")
    rows = []
    detail = []
    for i, district in enumerate(districts):
        z_score = getis_ord_star_z(values, neighbours, i)
        p_value, n_arrangements = exact_p_value(values, neighbours, i, z_score)
        rows.append({
            "district": district,
            "reporting_gap_pct": values[i],
            "gi_star_z_score": round(z_score, 3),
            "gi_star_p_value": round(p_value, 4),
            "classification": classify_hotspot(z_score, p_value),
        })
        detail.append({
            "district": district,
            "neighbours": len(neighbours[i]),
            "possible_arrangements": n_arrangements,
            "smallest_possible_p": round(1 / n_arrangements, 4),
        })

    result = pd.DataFrame(rows).sort_values("gi_star_z_score", ascending=False)
    print("\nLocal Getis-Ord Gi* results (highest z-score first):")
    print(result.to_string(index=False))

    print("\nWhy no p-value can be very small (exact test with 7 districts):")
    print(pd.DataFrame(detail).to_string(index=False))

    result.to_csv(OUTPUT_FILE, index=False)
    print(f"\nSaved to: {OUTPUT_FILE}")

    print("\nNote: with only 7 spatial units, this analysis has very limited statistical")
    print("power. A p-value equal to 'smallest_possible_p' means the district's")
    print("neighbourhood is the most extreme arrangement there could be. Results")
    print("should be interpreted as suggestive, not definitive.")


if __name__ == "__main__":
    main()
