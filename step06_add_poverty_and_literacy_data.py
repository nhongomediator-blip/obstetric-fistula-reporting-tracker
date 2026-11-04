"""
================================================================================
STEP 6: POVERTY AND LITERACY
================================================================================

Adds each district's poverty rate and literacy rate to the panel. One
value per district is used for every year, because district-level
figures are not published annually.

Poverty rate (% of households below the Total Consumption Poverty
Line), Zimbabwe Poverty Atlas 2021:

    Mutare 41.1 | Chimanimani 50.5 | Makoni 51.6 | Mutasa 54.0 |
    Nyanga 55.4 | Chipinge 63.4 | Buhera 69.5

Literacy rate (population aged 15 and over), 2022 Population and
Housing Census, Manicaland Province report:

    Mutasa 94.0 | Makoni 93.4 | Buhera 92.9 | Chimanimani 92.7 |
    Nyanga 92.1 | Chipinge 85.5 | Mutare 95.6

The literacy figure is the all-adult rate, used as a proxy for female
youth literacy, for which district-level figures are not available.

Input:  facility_access_metrics.csv (Step 5)
Output: panel_with_poverty_literacy.csv

Usage:
    python step06_add_poverty_and_literacy_data.py
================================================================================
"""

from environment_setup import fix_proj_database
fix_proj_database()

import pandas as pd


# ------------------------------------------------------------------------------
# SETTINGS
# ------------------------------------------------------------------------------

BASE = r"C:\Users\nhong\OneDrive\Desktop\DISSERTATION FOR SUBMISSION FINALEST\CHAPTER 3 METHODOLOGY"
INPUT_FILE = BASE + r"\facility_access_metrics.csv"
OUTPUT_FILE = BASE + r"\panel_with_poverty_literacy.csv"

# Poverty rate (% below Total Consumption Poverty Line), by district.
# Source: Zimbabwe Poverty Atlas 2021 (PICES 2017).
POVERTY_RATE = {
    "Mutare": 41.1,
    "Chimanimani": 50.5,
    "Makoni": 51.6,
    "Mutasa": 54.0,
    "Nyanga": 55.4,
    "Chipinge": 63.4,
    "Buhera": 69.5,
}

# Literacy rate (% of population aged 15+ who are literate), by district.
# Source: 2022 Population and Housing Census (Manicaland.pdf), used as a
# documented proxy for youth-specific literacy -- see module docstring.
LITERACY_RATE = {
    "Mutasa": 94.0,
    "Makoni": 93.4,
    "Buhera": 92.9,
    "Chimanimani": 92.7,
    "Nyanga": 92.1,
    "Chipinge": 85.5,
    "Mutare": 95.6,
}


def add_poverty_and_literacy(panel, poverty_rates, literacy_rates):
    """
    Adds "poverty_rate" and "literacy_rate" columns to the panel, mapping
    each district-year row to its district's real, sourced value.

    Args:
        panel (pandas.DataFrame): The district-year panel, with a
            "district" column.
        poverty_rates (dict[str, float]): District name -> poverty rate (%).
        literacy_rates (dict[str, float]): District name -> literacy rate (%).

    Returns:
        pandas.DataFrame: The input panel with two new columns added.
    """
    panel = panel.copy()
    panel["poverty_rate"] = panel["district"].map(poverty_rates)
    panel["literacy_rate"] = panel["district"].map(literacy_rates)
    return panel


def main():
    """
    Runs the full Step 6 pipeline: load the panel, join real poverty and
    literacy rates by district, and save the result.
    """
    print("Loading panel from Step 5's output...")
    panel = pd.read_csv(INPUT_FILE)
    print(f"Loaded {len(panel)} rows.")

    panel = add_poverty_and_literacy(panel, POVERTY_RATE, LITERACY_RATE)

    # Sanity check: confirm every district got a value (no missing/mismatched names)
    missing_poverty = panel[panel["poverty_rate"].isna()]["district"].unique()
    missing_literacy = panel[panel["literacy_rate"].isna()]["district"].unique()
    if len(missing_poverty) > 0:
        print(f"\nWARNING: no poverty rate found for: {list(missing_poverty)}")
    if len(missing_literacy) > 0:
        print(f"\nWARNING: no literacy rate found for: {list(missing_literacy)}")
    if len(missing_poverty) == 0 and len(missing_literacy) == 0:
        print("\nAll districts matched successfully -- no missing values.")

    panel.to_csv(OUTPUT_FILE, index=False)
    print(f"\nSaved to: {OUTPUT_FILE}")

    print("\nOne row per district (poverty rate, literacy rate):")
    summary = panel.drop_duplicates("district")[["district", "poverty_rate", "literacy_rate"]].sort_values("district")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
