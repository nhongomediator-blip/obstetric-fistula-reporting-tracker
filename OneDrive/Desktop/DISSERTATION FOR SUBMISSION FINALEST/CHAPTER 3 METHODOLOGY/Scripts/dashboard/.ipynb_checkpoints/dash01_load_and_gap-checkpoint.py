"""
dash01_load_and_gap.py

DASHBOARD 01: load the case data and work out the reporting gap
for each district, using plain Python. No dashboard yet. This is the calculation
engine that the dashboard runs.

WHY START HERE
A dashboard is a window onto numbers. If the numbers are wrong the dashboard
is wrong, so the calculation is built first and checked against the Objective 1
results and the interface is added afterwards.

WHAT THIS SCRIPT DOES
  1. Reads the first-time repair cases from data/entries.csv
  2. Works out EXPECTED cases for each district
  3. Compares REPORTED with EXPECTED to get the reporting gap
  4. Checks the answer against the Objective 1 results in the dissertation

THE THREE IDEAS 
  Reported cases  = first-time repair patients who appear in the repair camp records
  Expected cases  = how many women would be expected to be living with fistula,
                    if the rate were 1 in every 1,000 adult women
                    (Maheu-Giroux et al., 2015)
  Reporting gap   = the share of expected cases that never appear in the
                    records.  Gap % = (1 - Reported / Expected) x 100

HOW TO RUN
    pip install pandas
    python dash01_load_and_gap.py
"""

from pathlib import Path
import pandas as pd

# ----------------------------------------------------------------------------
# SETTINGS  (the only numbers the calculation depends on)
# ----------------------------------------------------------------------------
HERE = Path(__file__).parent
DATA_FILE = HERE / "data" / "entries.csv"

# Adult female population (aged 18 and over) in each district, 2022 census.
ADULT_FEMALE_POP_2022 = {
    "Buhera": 72063,
    "Chimanimani": 41821,
    "Chipinge": 108538,
    "Makoni": 90288,
    "Mutare": 149509,
    "Mutasa": 56047,
    "Nyanga": 40515,
}

ANNUAL_GROWTH = 1.015      # population grows 1.5% a year after the census
PREVALENCE = 0.001         # 1 woman in every 1,000
REFERENCE_YEAR = 2024      # whole-period expected cases use this year's population

# The Objective 1 results from Chapter 4, used only to CHECK our answer.
THESIS_GAP = {
    "Makoni": 84.9, "Mutasa": 84.4, "Nyanga": 68.9, "Mutare": 61.0,
    "Buhera": 51.5, "Chimanimani": 39.7, "Chipinge": 35.6,
}


# ----------------------------------------------------------------------------
# STEP 1: LOAD THE DATA
# ----------------------------------------------------------------------------
print("STEP 1: loading the data")
entries = pd.read_csv(DATA_FILE)

# Each row is "this many cases, for this district, in this year".
# first_time says whether those patients were having their FIRST repair.
print(entries.head())
print(f"\n  Rows in the file : {len(entries)}")

# Only count first-time patients. A woman who comes back for a second
# repair is already known to the system, so she is not a "new" case.
first_time_only = entries[entries["first_time"] == "Yes"]
print(f"  First-time cases : {first_time_only['count'].sum()}")


# ----------------------------------------------------------------------------
# STEP 2: EXPECTED CASES FOR ONE DISTRICT (worked example first)
# ----------------------------------------------------------------------------
print("\nSTEP 2: worked example for Makoni")


def expected_cases(district, year):
    """Expected cases = adult women in that year x 0.001."""
    pop_2022 = ADULT_FEMALE_POP_2022[district]
    years_since_census = year - 2022
    pop_in_year = pop_2022 * ANNUAL_GROWTH ** years_since_census
    return pop_in_year * PREVALENCE


makoni_expected = expected_cases("Makoni", REFERENCE_YEAR)
print(f"  Adult women in Makoni, 2022 : {ADULT_FEMALE_POP_2022['Makoni']:,}")
print(f"  Grown to {REFERENCE_YEAR} (x 1.015 twice)  : "
      f"{ADULT_FEMALE_POP_2022['Makoni'] * ANNUAL_GROWTH ** 2:,.0f}")
print(f"  Expected cases (x 0.001)     : {makoni_expected:.1f}")

makoni_reported = first_time_only.loc[first_time_only["district"] == "Makoni", "count"].sum()
makoni_gap = (1 - makoni_reported / makoni_expected) * 100
print(f"  Reported first-time cases    : {makoni_reported}")
print(f"  Reporting gap                : (1 - {makoni_reported}/{makoni_expected:.1f}) x 100 = {makoni_gap:.1f}%")


# ----------------------------------------------------------------------------
# STEP 3: THE SAME CALCULATION FOR EVERY DISTRICT
# ----------------------------------------------------------------------------
print("\nSTEP 3: reporting gap for all districts (whole period)")

rows = []
for district in ADULT_FEMALE_POP_2022:
    reported = first_time_only.loc[first_time_only["district"] == district, "count"].sum()
    expected = expected_cases(district, REFERENCE_YEAR)
    rows.append({
        "District": district,
        "Reported": int(reported),
        "Expected": expected,                       # keep full precision here
        "Gap %": (1 - reported / expected) * 100,   # round only when we print
    })

gap = pd.DataFrame(rows).sort_values("Gap %", ascending=False)

# Province row: add up reported and expected first, THEN work out the gap.
# (Never average the district percentages; big districts must count for more.)
total_reported = gap["Reported"].sum()
total_exp = gap["Expected"].sum()
province = {"District": "Province", "Reported": total_reported, "Expected": total_exp,
            "Gap %": (1 - total_reported / total_exp) * 100}
gap = pd.concat([gap, pd.DataFrame([province])], ignore_index=True)
print(gap.round(1).to_string(index=False))   # rounding is only for display


# ----------------------------------------------------------------------------
# STEP 4: CHECK AGAINST THE OBJECTIVES OF THE STUDY
# ----------------------------------------------------------------------------
print("\nSTEP 4: check against Objective 1 results")
all_match = True
for district, thesis_value in THESIS_GAP.items():
    ours = round(gap.loc[gap["District"] == district, "Gap %"].iloc[0], 1)
    ok = abs(ours - thesis_value) < 0.05
    all_match &= ok
    print(f"  {district:<12} ours {ours:5.1f}   thesis {thesis_value:5.1f}   {'OK' if ok else 'MISMATCH'}")

print("\nAll districts match the study." if all_match else "\nSomething does not match - check the settings.")
