"""
================================================================================
STEP 13: PREPARE MAPPING DATA FOR QGIS
================================================================================

Merges the district boundaries (Step 1) with the results of the other
steps into a single GeoJSON file that opens directly in QGIS, so that
no separate joins are needed inside QGIS.

Maps supported by this file:
  Map 0: Study area boundary
  Map 1: Reported cases (Step 7)
  Map 2: Getis-Ord Gi* hotspot classification (Step 9)
  Map 2B: LISA cluster classification (Step 9C)
  Map 3: Poverty rate (Step 6)
  Map 4: Literacy rate (Step 6)
  Map 5: Distance to nearest facility (Step 5)
  Map 6: Facility density (Step 5)
  Map 7: Reporting gap (Step 8)

The COVID-19 comparison (Step 10B) gives one province-wide result and is
not mapped.

Input:  manicaland_study_area.geojson (Step 1)
        facility_access_metrics.csv (Step 5)
        panel_with_poverty_literacy.csv (Step 6)
        manicaland_case_data.xlsx, sheet "Whole-Period Totals" (Step 7)
        reporting_gap_results.csv (Step 8)
        hotspot_results.csv (Step 9)
        lisa_results.csv (Step 9C)
Output: manicaland_mapping_data.geojson

Usage:
    python step13_prepare_mapping_data.py
================================================================================
"""

from environment_setup import fix_proj_database
fix_proj_database()

import geopandas as gpd
import pandas as pd


# ------------------------------------------------------------------------------
# SETTINGS
# ------------------------------------------------------------------------------

BASE = r"C:\Users\nhong\OneDrive\Desktop\DISSERTATION FOR SUBMISSION FINALEST\CHAPTER 3 METHODOLOGY"
STUDY_AREA_FILE = BASE + r"\manicaland_study_area.geojson"
FACILITY_ACCESS_FILE = BASE + r"\facility_access_metrics.csv"
POVERTY_LITERACY_FILE = BASE + r"\panel_with_poverty_literacy.csv"
CASE_DATA_FILE = BASE + r"\manicaland_case_data.xlsx"
REPORTING_GAP_FILE = BASE + r"\reporting_gap_results.csv"
HOTSPOT_FILE = BASE + r"\hotspot_results.csv"
LISA_FILE = BASE + r"\lisa_results.csv"

OUTPUT_FILE = BASE + r"\manicaland_mapping_data.geojson"


def load_and_merge_all_sources():
    """
    Loads every data source needed for the maps and merges them
    onto the district boundaries by district name.

    Returns:
        geopandas.GeoDataFrame: One row per district, with geometry and
            every mapped variable attached as columns.
    """
    study_area = gpd.read_file(STUDY_AREA_FILE)

    # Map 5 & 6: facility distance and density (one row per district,
    # so duplicates are dropped after taking the first/only value)
    facility_access = pd.read_csv(FACILITY_ACCESS_FILE)
    facility_lookup = facility_access[
        ["district", "distance_to_facility_km", "facility_density_per_100km2"]
    ].drop_duplicates("district")

    # Map 3 & 4: poverty and literacy (also one row per district)
    poverty_literacy = pd.read_csv(POVERTY_LITERACY_FILE)
    poverty_literacy_lookup = poverty_literacy[
        ["district", "poverty_rate", "literacy_rate"]
    ].drop_duplicates("district")

    # Map 1: real reported cases, whole-period total
    case_totals = pd.read_excel(CASE_DATA_FILE, sheet_name="Whole-Period Totals")
    case_totals = case_totals.rename(columns={"total_reported_cases": "reported_cases_total"})

    # Map 7: reporting gap
    reporting_gap = pd.read_csv(REPORTING_GAP_FILE)

    # Map 2: hotspot classification
    hotspot = pd.read_csv(HOTSPOT_FILE)

    # Map 2B: LISA classification
    lisa = pd.read_csv(LISA_FILE)

    # Merge everything onto the boundaries, one join at a time
    merged = study_area.merge(facility_lookup, on="district", how="left")
    merged = merged.merge(poverty_literacy_lookup, on="district", how="left")
    merged = merged.merge(
        case_totals[["district", "reported_cases_total"]], on="district", how="left"
    )
    merged = merged.merge(
        reporting_gap[["district", "expected_cases", "reported_cases",
                        "reporting_gap_pct", "reported_to_expected_ratio",
                        "statistically_significant"]].rename(
            columns={"statistically_significant": "gap_significant"}
        ),
        on="district", how="left"
    )
    merged = merged.merge(
        hotspot[["district", "gi_star_z_score", "gi_star_p_value", "classification"]].rename(
            columns={"classification": "hotspot_classification"}
        ),
        on="district", how="left"
    )
    merged = merged.merge(
        lisa[["district", "lisa_I", "p_value", "classification"]].rename(
            columns={"lisa_I": "lisa_local_I", "p_value": "lisa_p_value", "classification": "lisa_classification"}
        ),
        on="district", how="left"
    )

    return merged


def main():
    """
    Runs the full Step 13 data-preparation pipeline: loads and merges
    every data source needed for the maps and saves the result ready for QGIS.
    """
    print("Loading and merging all real data sources (Steps 1, 5, 6, 7, 8, 9, 9C)...")
    merged = load_and_merge_all_sources()

    print("\nChecking for any unmatched districts across all joins:")
    check_columns = [
        "reported_cases_total", "reporting_gap_pct", "hotspot_classification",
        "lisa_classification", "poverty_rate", "literacy_rate",
        "distance_to_facility_km", "facility_density_per_100km2",
    ]
    for col in check_columns:
        missing = merged[merged[col].isna()]["district"].tolist()
        if missing:
            print(f"  WARNING: {col} is missing for: {missing}")
        else:
            print(f"  {col}: all 7 districts matched successfully.")

    merged.to_file(OUTPUT_FILE, driver="GeoJSON")
    print(f"\nSaved merged mapping data to: {OUTPUT_FILE}")
    print("\nColumns available for mapping in QGIS:")
    for col in merged.columns:
        if col != "geometry":
            print(f"  - {col}")


if __name__ == "__main__":
    main()
