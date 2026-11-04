"""
================================================================================
STEP 2: DISTRICT-YEAR PANEL
================================================================================

Creates the table on which the study is built: one row for every
combination of district and year. Seven districts over ten years
(2015-2024) give 70 rows. Later steps add columns to this table,
always matched on district and year, so a district-year with missing
data stays visible instead of dropping out.

Each year is labelled once with its COVID-19 period: Pre-COVID
(2015-2019), COVID (2020-2022) or Post-COVID (2023-2024).

Input:  manicaland_study_area.geojson (Step 1)
Output: panel_skeleton.csv (70 rows: district, year, covid_period)

Usage:
    python step02_build_district_year_table.py
================================================================================
"""

from environment_setup import fix_proj_database
fix_proj_database()

import geopandas as gpd
import pandas as pd


# ------------------------------------------------------------------------------
# SETTINGS
# ------------------------------------------------------------------------------

STUDY_AREA_FILE = r"C:\Users\nhong\OneDrive\Desktop\DISSERTATION FOR SUBMISSION FINALEST\CHAPTER 3 METHODOLOGY\manicaland_study_area.geojson"
OUTPUT_FILE = r"C:\Users\nhong\OneDrive\Desktop\DISSERTATION FOR SUBMISSION FINALEST\CHAPTER 3 METHODOLOGY\panel_skeleton.csv"

START_YEAR = 2015
END_YEAR = 2024


def get_covid_period(year):
    """
    Labels a single year with its COVID-19 study period.

    Args:
        year (int): The calendar year to classify.

    Returns:
        str: One of "Pre-COVID" (2015-2019), "COVID" (2020-2022), or
            "Post-COVID" (2023-2024).
    """
    if year <= 2019:
        return "Pre-COVID"
    elif year <= 2022:
        return "COVID"
    else:
        return "Post-COVID"


def load_district_list(study_area_file):
    """
    Reads the list of study districts from Step 1's output file.

    Args:
        study_area_file (str): Path to manicaland_study_area.geojson.

    Returns:
        list[str]: The 7 district names, alphabetically sorted.
    """
    print("Loading study area districts from Step 1's output...")
    study_area = gpd.read_file(study_area_file)
    districts = sorted(study_area["district"].tolist())
    print(f"Found {len(districts)} districts: {districts}")
    return districts


def build_panel_skeleton(districts, start_year, end_year):
    """
    Builds one row for every combination of district and year, each
    labelled with its COVID-19 period.

    Args:
        districts (list[str]): District names to include.
        start_year (int): First year of the study period (inclusive).
        end_year (int): Last year of the study period (inclusive).

    Returns:
        pandas.DataFrame: Columns "district", "year", "covid_period",
            with one row per district-year combination.
    """
    rows = []
    for district in districts:
        for year in range(start_year, end_year + 1):
            rows.append({
                "district": district,
                "year": year,
                "covid_period": get_covid_period(year),
            })
    return pd.DataFrame(rows)


def main():
    """
    Runs the full Step 2 pipeline: load the district list from Step 1,
    build the district-year panel skeleton, and save it.
    """
    districts = load_district_list(STUDY_AREA_FILE)
    panel = build_panel_skeleton(districts, START_YEAR, END_YEAR)

    expected_rows = len(districts) * (END_YEAR - START_YEAR + 1)
    print(f"\nBuilt {len(panel)} rows (expected {expected_rows}: "
          f"{len(districts)} districts x {END_YEAR - START_YEAR + 1} years).")
    print("\nRows per COVID period:")
    print(panel["covid_period"].value_counts())

    panel.to_csv(OUTPUT_FILE, index=False)
    print(f"\nSaved panel skeleton to: {OUTPUT_FILE}")
    print("\nFirst few rows:")
    print(panel.head(12).to_string(index=False))


if __name__ == "__main__":
    main()
