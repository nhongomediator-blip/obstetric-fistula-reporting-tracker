"""
================================================================================
STEP 5: FACILITY ACCESS MEASURES
================================================================================

Calculates two access measures for each district:

    Facility density = (number of facilities / district area) x 100
                       (facilities per 100 sq km; also per 10,000 people)

    Population-weighted mean distance to the nearest facility (km)

Distance is calculated on WorldPop gridded population. For each 1 km
grid square, the distance to the nearest facility is found and weighted
by the number of people living in the square before averaging, so that
the result describes the typical resident and not the district centre.

Boundaries and facilities are reprojected from latitude/longitude
(EPSG:4326) to UTM Zone 36S (EPSG:32736) before any area or distance
calculation, so that results are in metres and kilometres.

Input:  manicaland_study_area.geojson (Step 1)
        manicaland_health_facilities.csv (Step 4)
        WorldPop gridded population (.tif)
        panel_with_population_births.csv (Step 3)
Output: facility_access_metrics.csv

Usage:
    python step05_calculate_facility_access.py
================================================================================
"""

from environment_setup import fix_proj_database
fix_proj_database()

import geopandas as gpd
import pandas as pd
import numpy as np
import rasterio
from shapely.geometry import Point
from scipy.spatial import cKDTree


# ------------------------------------------------------------------------------
# SETTINGS
# ------------------------------------------------------------------------------

BASE = r"C:\Users\nhong\OneDrive\Desktop\DISSERTATION FOR SUBMISSION FINALEST\CHAPTER 3 METHODOLOGY"
STUDY_AREA_FILE = BASE + r"\manicaland_study_area.geojson"
FACILITIES_FILE = BASE + r"\manicaland_health_facilities.csv"
POPULATION_RASTER = BASE + r"\RAW DATA\zwe_pop_2020_CN_1km_R2025A_UA_v1.tif"
PANEL_FILE = BASE + r"\panel_with_population_births.csv"
OUTPUT_FILE = BASE + r"\facility_access_metrics.csv"

# UTM Zone 36S -- the standard metric coordinate system for this part of
# Zimbabwe, used so that distances and areas come out in  kilometres.
METRIC_CRS = "EPSG:32736"


def calculate_facility_density(study_area, facilities):
    """
    Calculates facility density per district: number of facilities per
    100 km2 of district area, and per 10,000 population.

    Args:
        study_area (geopandas.GeoDataFrame): District boundaries, with a
            "district" column (Step 1's output).
        facilities (pandas.DataFrame): Facility locations, with a
            "district" column (Step 4's output).

    Returns:
        pandas.DataFrame: One row per district, with columns "district",
            "area_km2", and "facility_count".
    """
    # Reproject to a metric CRS so area comes out in real square kilometres,
    # not degrees.
    study_area_metric = study_area.to_crs(METRIC_CRS)
    study_area_metric["area_km2"] = study_area_metric.geometry.area / 1_000_000  # m^2 -> km^2

    facility_counts = facilities.groupby("district").size().reset_index(name="facility_count")

    result = study_area_metric[["district", "area_km2"]].merge(facility_counts, on="district", how="left")
    result["facility_count"] = result["facility_count"].fillna(0).astype(int)
    return result


def calculate_population_weighted_distance(study_area, facilities, population_raster_path):
    """
    Calculates, for each district, the population-weighted average
    distance to the nearest health facility.

    For every populated raster cell within a district, this finds the
    straight-line distance to the nearest facility, then computes a
    weighted average of these distances using each cell's population as
    the weight.

    Args:
        study_area (geopandas.GeoDataFrame): District boundaries (Step 1).
        facilities (pandas.DataFrame): Facility locations, with
            "latitude" and "longitude" columns (Step 4).
        population_raster_path (str): Path to the WorldPop .tif file.

    Returns:
        dict[str, float]: District name -> population-weighted average
            distance to nearest facility, in kilometres.
    """
    study_area_metric = study_area.to_crs(METRIC_CRS)

    # Build a fast nearest-neighbour lookup structure (a KD-Tree) from all
    # facility locations, reprojected to the same metric coordinate system.
    facility_points = gpd.GeoDataFrame(
        facilities,
        geometry=[Point(xy) for xy in zip(facilities["longitude"], facilities["latitude"])],
        crs="EPSG:4326",
    ).to_crs(METRIC_CRS)
    facility_coords = np.column_stack([facility_points.geometry.x, facility_points.geometry.y])
    facility_tree = cKDTree(facility_coords)

    print("Reading population raster...")
    with rasterio.open(population_raster_path) as src:
        population_data = src.read(1)
        raster_transform = src.transform
        raster_crs = src.crs

        # Get the row/column indices of every raster cell so we can convert
        # them to real-world coordinates.
        rows, cols = np.where(population_data > 0)  # only cells with people in them
        print(f"Found {len(rows)} populated grid cells nationwide.")

        # Convert each populated cell's row/column position to a real-world
        # x, y coordinate (the centre of that cell), applying the affine
        # transform formula directly. This is done manually, rather than
        # via rasterio.transform.xy(), to avoid a version-compatibility
        # issue between some rasterio/numpy combinations where that
        # function fails with "Could not convert object to sequence".
        # The +0.5 offsets target the CENTRE of each cell, not its corner.
        a, b, c, d, e, f = raster_transform.a, raster_transform.b, raster_transform.c, \
                            raster_transform.d, raster_transform.e, raster_transform.f
        xs = a * (cols + 0.5) + b * (rows + 0.5) + c
        ys = d * (cols + 0.5) + e * (rows + 0.5) + f
        populations = population_data[rows, cols]

    # Build a GeoDataFrame of populated cells and reproject to our metric CRS.
    cells = gpd.GeoDataFrame(
        {"total_population": populations},
        geometry=[Point(x, y) for x, y in zip(xs, ys)],
        crs=raster_crs,
    ).to_crs(METRIC_CRS)

    # Keep only cells that actually fall within Manicaland and tag each
    # with which district it belongs to.
    cells_in_study_area = gpd.sjoin(cells, study_area_metric[["district", "geometry"]], how="inner", predicate="within")
    print(f"{len(cells_in_study_area)} populated cells fall within Manicaland's 7 districts.")

    if len(cells_in_study_area) == 0:
        raise ValueError(
            "No populated raster cells were found inside the study area boundaries. "
            "This usually means the raster file does not actually cover Manicaland, "
            "or there is a coordinate system mismatch. Check that POPULATION_RASTER "
            "points to the correct file and genuinely covers Zimbabwe."
        )

    # For every cell, find the distance (in metres) to its nearest facility.
    cell_coords = np.column_stack([cells_in_study_area.geometry.x, cells_in_study_area.geometry.y])
    distances_m, _ = facility_tree.query(cell_coords)
    cells_in_study_area = cells_in_study_area.copy()
    cells_in_study_area["distance_km"] = distances_m / 1000

    # Population-weighted average: sum(population x distance) / sum(population), per district.
    weighted = cells_in_study_area.groupby("district").apply(
        lambda g: np.average(g["distance_km"], weights=g["total_population"])
    )
    return weighted.to_dict()


def main():
    """
    Runs the full Step 5 pipeline: calculates facility density and
    population-weighted distance per district, joins both onto the
    district-year panel, and saves the result.
    """
    print("Loading study area, facilities, and panel...")
    study_area = gpd.read_file(STUDY_AREA_FILE)
    facilities = pd.read_csv(FACILITIES_FILE)
    panel = pd.read_csv(PANEL_FILE)

    density = calculate_facility_density(study_area, facilities)
    density["facility_density_per_100km2"] = (density["facility_count"] / density["area_km2"]) * 100

    print("\nFacility density by district:")
    print(density.to_string(index=False))

    print("\nCalculating population-weighted distance (this may take a minute)...")
    distances = calculate_population_weighted_distance(study_area, facilities, POPULATION_RASTER)
    print("\nPopulation-weighted average distance to nearest facility, by district (km):")
    for d, dist in sorted(distances.items()):
        print(f"  {d}: {dist:.2f} km")

    # Merge both metrics onto the panel, plus recalculate density per 10,000
    # population using each district-year's actual (projected) population.
    result = panel.merge(density[["district", "area_km2", "facility_count", "facility_density_per_100km2"]], on="district", how="left")
    result["distance_to_facility_km"] = result["district"].map(distances)
    result["facility_density_per_10k_pop"] = (result["facility_count"] / result["total_population"]) * 10000

    result.to_csv(OUTPUT_FILE, index=False)
    print(f"\nSaved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
