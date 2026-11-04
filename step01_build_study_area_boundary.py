"""
================================================================================
STEP 1: STUDY AREA BOUNDARY
================================================================================

Extracts the seven Manicaland study districts (Mutare, Makoni, Buhera,
Chipinge, Chimanimani, Nyanga and Mutasa) from the national district
boundary file and merges Rural/Urban splits into one shape per district.
Every later step uses the boundaries produced here.

Input:  admin_level2_districts.geojson (national boundary file)
Output: manicaland_study_area.geojson (seven districts, one polygon each)

Usage:
    python step01_build_study_area_boundary.py

Requires: geopandas
================================================================================
"""

from environment_setup import fix_proj_database
fix_proj_database()  # fixes a known Windows/Anaconda pyproj issue -- see environment_setup.py

import geopandas as gpd


# ------------------------------------------------------------------------------
# SETTINGS -- edit these two paths if your files are saved somewhere different
# ------------------------------------------------------------------------------

INPUT_FILE = r"C:\Users\nhong\OneDrive\Desktop\DISSERTATION FOR SUBMISSION FINALEST\CHAPTER 3 METHODOLOGY\RAW DATA\admin_level2_districts.geojson"
OUTPUT_FILE = r"C:\Users\nhong\OneDrive\Desktop\DISSERTATION FOR SUBMISSION FINALEST\CHAPTER 3 METHODOLOGY\manicaland_study_area.geojson"

STUDY_DISTRICTS = ["Mutare", "Makoni", "Buhera", "Chipinge", "Chimanimani", "Nyanga", "Mutasa"]

# Some districts appear as separate Rural/Urban entries in the raw file.
# This maps each split name to the single combined district it belongs to.
MERGE_INTO = {
    "Mutare Urban": "Mutare",
    "Rusape": "Makoni",           # Rusape Town Council sits within Makoni district
    "Chipinge Urban": "Chipinge",
}

# Column names this function will try, in order, to find the district name field.
NAME_COLUMN_CANDIDATES = ["district", "District", "ADM2_EN", "NAME_2", "admin2Name"]


def find_name_column(gdf, candidates):
    """
    Finds which column in a GeoDataFrame holds district names, by checking
    a list of common candidate names and returning the first one present.

    Different data sources label this column differently (e.g. "district"
    vs "ADM2_EN"), so rather than assuming one fixed name, this function
    checks each candidate against the actual file.

    Args:
        gdf (geopandas.GeoDataFrame): The loaded boundary data to search.
        candidates (list[str]): Column names to try, in priority order.

    Returns:
        str or None: The first matching column name found, or None if
            none of the candidates exist in this file.
    """
    for candidate in candidates:
        if candidate in gdf.columns:
            return candidate
    return None


def load_and_filter_districts(input_file, name_column_candidates, study_districts, merge_map):
    """
    Loads the national boundary file and filters it down to just the rows
    belonging to the study area, relabelling Rural/Urban splits so they
    merge into a single district name.

    Args:
        input_file (str): Path to the raw, national GeoJSON boundary file.
        name_column_candidates (list[str]): Possible column names for the
            district name field (see find_name_column).
        study_districts (list[str]): The district names to keep.
        merge_map (dict[str, str]): Maps a split Rural/Urban name to the
            combined district name it should be treated as.

    Returns:
        geopandas.GeoDataFrame: Rows belonging to the study area only, with
            a new "study_district" column holding each row's merged name.
    """
    print("Reading national boundary file...")
    all_districts = gpd.read_file(input_file)
    print(f"Loaded {len(all_districts)} total features.")
    print("Columns found:", list(all_districts.columns))
    print("Coordinate system detected:", all_districts.crs)

    name_column = find_name_column(all_districts, name_column_candidates)
    if name_column is None:
        raise ValueError(
            "Could not find a district name column. "
            f"Columns available were: {list(all_districts.columns)}"
        )
    print(f"\nUsing '{name_column}' as the district name column.")

    all_districts["study_district"] = all_districts[name_column].replace(merge_map)
    filtered = all_districts[all_districts["study_district"].isin(study_districts)].copy()

    print(f"\nFiltered down to {len(filtered)} rows matching our study districts:")
    print(filtered["study_district"].value_counts())

    return filtered


def dissolve_to_one_polygon_per_district(filtered_gdf):
    """
    Merges (dissolves) all shapes sharing the same study district name into
    a single polygon per district -- so, for example, Mutare Rural and
    Mutare Urban become one combined "Mutare" shape.

    Args:
        filtered_gdf (geopandas.GeoDataFrame): Output of
            load_and_filter_districts, containing a "study_district" column.

    Returns:
        geopandas.GeoDataFrame: One row per district, sorted alphabetically,
            with exactly two columns: "district" and "geometry".
    """
    dissolved = filtered_gdf.dissolve(by="study_district").reset_index()

    # Select ONLY these two columns before renaming. The source file already
    # has its own column literally called "district", so renaming without
    # first dropping it would create two same-named columns and raise an error.
    dissolved = dissolved[["study_district", "geometry"]].rename(
        columns={"study_district": "district"}
    )
    return dissolved.sort_values("district").reset_index(drop=True)


def main():
    """
    Runs the full Step 1 pipeline: load the raw national boundary file,
    filter and merge it down to the 7 Manicaland study districts, and save
    the result as this project's standard study area file.
    """
    filtered = load_and_filter_districts(
        INPUT_FILE, NAME_COLUMN_CANDIDATES, STUDY_DISTRICTS, MERGE_INTO
    )
    dissolved = dissolve_to_one_polygon_per_district(filtered)

    dissolved.to_file(OUTPUT_FILE, driver="GeoJSON")
    print(f"\nSaved {len(dissolved)} district polygons to: {OUTPUT_FILE}")
    print("Districts included:", dissolved["district"].tolist())
    print("Output coordinate system:", dissolved.crs)


if __name__ == "__main__":
    # This guard means: only run main() when this file is executed directly
    # (e.g. "python step01_build_study_area_boundary.py"), not when another script imports
    # functions from this file. This is standard Python practice and lets
    # later steps reuse these functions without re-running this whole script.
    main()
