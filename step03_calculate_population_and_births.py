"""
================================================================================
STEP 3: POPULATION
================================================================================

Adds each district-year's projected total population and adult female
population (aged 18 and over) to the panel. Annual births are also
estimated as demographic background; they are not used in the
calculation of expected cases or in the regression.

Population projection:
    Population(t) = Population(2022) x (1 + 0.015) ^ (year - 2022)

The 2022 census gives one figure per district, so it is projected
forward and backward at the national inter-censal growth rate of 1.5%
per year (ZIMSTAT).

Baseline data (2022 Population and Housing Census, Manicaland Province
report; Rural/Urban and Rusape splits merged into the seven districts):

    Total population: Buhera 271,920 | Chimanimani 153,619 |
    Chipinge 410,218 | Makoni 326,347 | Mutare 531,564 |
    Mutasa 197,808 | Nyanga 146,227   (sum 2,037,703)

    Adult female population (18+): Buhera 72,063 | Chimanimani 41,821 |
    Chipinge 108,538 | Makoni 90,288 | Mutare 149,509 |
    Mutasa 56,047 | Nyanga 40,515

Birth rate: Manicaland's yearly births (60,429) divided by its adult
female population (558,781) gives 0.1081 births per adult woman per
year. District rates are not published, so this rate is applied to each
district's own adult female population.

Input:  panel_skeleton.csv (Step 2)
Output: panel_with_population_births.csv

Usage:
    python step03_calculate_population_and_births.py
================================================================================
"""

from environment_setup import fix_proj_database
fix_proj_database()

import pandas as pd


# ------------------------------------------------------------------------------
# SETTINGS
# ------------------------------------------------------------------------------

INPUT_FILE = r"C:\Users\nhong\OneDrive\Desktop\DISSERTATION FOR SUBMISSION FINALEST\CHAPTER 3 METHODOLOGY\panel_skeleton.csv"
OUTPUT_FILE = r"C:\Users\nhong\OneDrive\Desktop\DISSERTATION FOR SUBMISSION FINALEST\CHAPTER 3 METHODOLOGY\panel_with_population_births.csv"

CENSUS_YEAR = 2022
ANNUAL_GROWTH_RATE = 0.015  # Zimbabwe's official inter-censal growth rate

# 2022 total population, by district (2022 census, Manicaland Province report;
# Rural/Urban and Rusape splits merged into the 7 study districts)
POPULATION_2022 = {
    "Buhera": 271920,
    "Chimanimani": 153619,
    "Chipinge": 375259 + 34959,       # Rural + Urban
    "Makoni": 288441 + 37906,          # Makoni + Rusape
    "Mutare": 306760 + 224804,         # Rural + Urban
    "Mutasa": 197808,
    "Nyanga": 146227,
}

# 2022 adult (18+) female population, by district (2022 census, Manicaland Province report;
# same merging applied)
ADULT_FEMALE_POPULATION_2022 = {
    "Buhera": 72063,
    "Chimanimani": 41821,
    "Chipinge": 98086 + 10452,
    "Makoni": 78373 + 11915,
    "Mutare": 79265 + 70244,
    "Mutasa": 56047,
    "Nyanga": 40515,
}

# Derived birth rate: Manicaland's total yearly births (60,429) divided by
# its total adult female population (558,781).
BIRTH_RATE_PER_ADULT_WOMAN = 60429 / 558781


def project_population(population_2022, year, growth_rate):
    """
    Projects a district's population for a given year, forward or backward
    from the 2022 Census baseline, using a constant annual growth rate.

    Args:
        population_2022 (float): The district's population in the 2022
            Census (the baseline year).
        year (int): The year to project population for.
        growth_rate (float): Annual growth rate (e.g. 0.015 for 1.5%).

    Returns:
        float: The projected population for the given year.
    """
    years_from_baseline = year - CENSUS_YEAR
    return population_2022 * (1 + growth_rate) ** years_from_baseline


def add_population_and_births(panel, population_2022, adult_female_2022, birth_rate):
    """
    Adds "total_population" and "annual_births" columns to the panel, calculated
    by projecting the 2022 baseline at the annual growth rate.

    Args:
        panel (pandas.DataFrame): The district-year panel (from Step 2),
            with "district" and "year" columns.
        population_2022 (dict[str, float]): 2022 baseline population, by
            district.
        adult_female_2022 (dict[str, float]): 2022 adult female population,
            by district.
        birth_rate (float): Births per adult woman per year.

    Returns:
        pandas.DataFrame: The input panel with two new columns added:
            "total_population" and "annual_births".
    """
    panel = panel.copy()

    panel["total_population"] = panel.apply(
        lambda row: project_population(population_2022[row["district"]], row["year"], ANNUAL_GROWTH_RATE),
        axis=1,
    )

    # Adult female population is projected the same way as total population,
    # using the same growth rate, then multiplied by the birth rate.
    panel["adult_female_population_18plus"] = panel.apply(
        lambda row: project_population(adult_female_2022[row["district"]], row["year"], ANNUAL_GROWTH_RATE),
        axis=1,
    )
    panel["annual_births"] = panel["adult_female_population_18plus"] * birth_rate

    return panel


def main():
    """
    Runs the full Step 3 pipeline: load the panel skeleton, add projected
    population and births for every district-year, and save the result.
    """
    print("Loading panel skeleton from Step 2's output...")
    panel = pd.read_csv(INPUT_FILE)
    print(f"Loaded {len(panel)} rows.")

    print(f"\nUsing derived birth rate: {BIRTH_RATE_PER_ADULT_WOMAN:.4f} "
          f"births per adult woman per year "
          f"(~{BIRTH_RATE_PER_ADULT_WOMAN * 1000:.1f} per 1,000 adult women).")

    panel = add_population_and_births(
        panel, POPULATION_2022, ADULT_FEMALE_POPULATION_2022, BIRTH_RATE_PER_ADULT_WOMAN
    )

    panel["total_population"] = panel["total_population"].round().astype(int)
    panel["adult_female_population_18plus"] = panel["adult_female_population_18plus"].round().astype(int)
    panel["annual_births"] = panel["annual_births"].round().astype(int)

    panel.to_csv(OUTPUT_FILE, index=False)
    print(f"\nSaved to: {OUTPUT_FILE}")

    print("\nSample rows (2015, 2022, 2024) per district:")
    sample = panel[panel["year"].isin([2015, 2022, 2024])].sort_values(["district", "year"])
    print(sample.to_string(index=False))


if __name__ == "__main__":
    main()
