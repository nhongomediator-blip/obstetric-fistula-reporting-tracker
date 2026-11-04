"""
================================================================================
STEP 4: HEALTH FACILITY LOCATIONS
================================================================================

Filters the national health facility list to the facilities in the
seven study districts and corrects data-quality problems.

Corrections:
  - 35 records are tagged Province = "Manicaland" but have a district of
    "Bulawayo" (33 records) or "Bulilima" (2 records). Neither is a
    Manicaland district, so these records are excluded.
  - "Chimanimani Urban" is merged into "Chimanimani", so that each
    district is a single unit, as in the boundary file.

Input:  zimbabwe_facilities_master.csv (national facility list)
Output: manicaland_health_facilities.csv

Usage:
    python step04_prepare_health_facility_list.py
================================================================================
"""

from environment_setup import fix_proj_database
fix_proj_database()

import pandas as pd


# ------------------------------------------------------------------------------
# SETTINGS
# ------------------------------------------------------------------------------

INPUT_FILE = r"C:\Users\nhong\OneDrive\Desktop\DISSERTATION FOR SUBMISSION FINALEST\CHAPTER 3 METHODOLOGY\RAW DATA\zimbabwe_facilities_master-1782225366.csv"
OUTPUT_FILE = r"C:\Users\nhong\OneDrive\Desktop\DISSERTATION FOR SUBMISSION FINALEST\CHAPTER 3 METHODOLOGY\manicaland_health_facilities.csv"

# The source file uses two different spellings for the Manicaland province field
PROVINCE_VALUES = ["Manicaland", "Manicaland Province"]

# 7 real study districts, plus the Rural/Urban-style split names that
# should be merged into them
VALID_DISTRICTS = ["Mutasa", "Chipinge", "Makoni", "Mutare", "Buhera", "Nyanga", "Chimanimani"]
MERGE_INTO = {
    "Chimanimani Urban": "Chimanimani",
}


def load_and_filter_facilities(input_file, province_values, valid_districts, merge_map):
    """
    Loads the national facility list and filters it down to genuine
    Manicaland facilities, excluding any mistagged records and merging
    Rural/Urban district name splits.

    Args:
        input_file (str): Path to the national facility CSV file.
        province_values (list[str]): Accepted spellings of "Manicaland" in
            the Province column.
        valid_districts (list[str]): The 7 real study district names to
            keep, after merging.
        merge_map (dict[str, str]): Maps a split district name to the
            combined district name it belongs to.

    Returns:
        pandas.DataFrame: Cleaned facility records for the 7 study
            districts only, with a "district" column holding the merged
            name.
    """
    print("Reading national facility master list...")
    facilities = pd.read_csv(input_file)
    print(f"Loaded {len(facilities)} total facilities (nationwide).")

    in_province = facilities[facilities["Province"].isin(province_values)].copy()
    print(f"\n{len(in_province)} facilities tagged as Manicaland province.")

    in_province["district"] = in_province["DISTRICT"].replace(merge_map)

    # Identify and report mistagged records before dropping them, so the
    # exclusion is visible and traceable, not silent.
    mistagged = in_province[~in_province["district"].isin(valid_districts)]
    if len(mistagged) > 0:
        print(f"\nFound {len(mistagged)} mistagged records (district value is not "
              f"an actual Manicaland district) -- excluding these:")
        print(mistagged["district"].value_counts())

    cleaned = in_province[in_province["district"].isin(valid_districts)].copy()
    print(f"\nKept {len(cleaned)} genuine Manicaland facilities across {cleaned['district'].nunique()} districts:")
    print(cleaned["district"].value_counts())

    return cleaned


def main():
    """
    Runs the full Step 4 pipeline: load the national facility list, filter
    and clean it down to Manicaland's 7 study districts, and save the
    result.
    """
    cleaned = load_and_filter_facilities(INPUT_FILE, PROVINCE_VALUES, VALID_DISTRICTS, MERGE_INTO)

    output_columns = ["district", "NAMEOFFACI", "TYPEOFFACI", "LATITUDE", "LONGITUDE", "OWNERSHIP"]
    result = cleaned[output_columns].rename(columns={
        "NAMEOFFACI": "facility_name",
        "TYPEOFFACI": "facility_type",
        "LATITUDE": "latitude",
        "LONGITUDE": "longitude",
        "OWNERSHIP": "ownership",
    })
    result = result.sort_values(["district", "facility_name"]).reset_index(drop=True)

    result.to_csv(OUTPUT_FILE, index=False)
    print(f"\nSaved {len(result)} facilities to: {OUTPUT_FILE}")
    print("\nFirst few rows:")
    print(result.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
