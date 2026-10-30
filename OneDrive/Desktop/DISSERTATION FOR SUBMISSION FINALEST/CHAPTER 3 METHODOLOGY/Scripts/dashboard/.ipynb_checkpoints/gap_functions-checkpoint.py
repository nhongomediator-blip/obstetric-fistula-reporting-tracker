"""
gap_functions.py

The calculations from dash01 and dash02, packaged as functions that the
dashboard calls. The formulas are the same as in Step 8 of the analysis.

    expected_cases(district, year)        adult women x 0.001
    poisson_interval(k)                   believable range for a count
    gap_table(entries, year, ref_year)    the full table the dashboard shows
"""

import pandas as pd
from scipy.stats import chi2

ADULT_FEMALE_POP_2022 = {
    "Buhera": 72063, "Chimanimani": 41821, "Chipinge": 108538, "Makoni": 90288,
    "Mutare": 149509, "Mutasa": 56047, "Nyanga": 40515,
}
DISTRICTS = list(ADULT_FEMALE_POP_2022)
ANNUAL_GROWTH = 1.015      # population grows 1.5% a year after the 2022 census
PREVALENCE = 0.001         # 1 woman in every 1,000 (Maheu-Giroux et al., 2015)


def expected_cases(district, year):
    """Adult women in that year x 0.001."""
    return ADULT_FEMALE_POP_2022[district] * ANNUAL_GROWTH ** (year - 2022) * PREVALENCE


def poisson_interval(k, confidence=0.95):
    """Lowest and highest believable counts, given that k cases were seen."""
    tail = (1 - confidence) / 2
    lowest = 0.0 if k == 0 else chi2.ppf(tail, 2 * k) / 2
    highest = chi2.ppf(1 - tail, 2 * k + 2) / 2
    return lowest, highest


def verdict(reported, expected):
    """Gap %, its 95% range and the verdict, for one row of the table."""
    low, high = poisson_interval(reported)
    gap = (1 - reported / expected) * 100
    gap_low = (1 - high / expected) * 100      # ends swap: high ratio = low gap
    gap_high = (1 - low / expected) * 100
    if high / expected < 1:
        label = "Significant gap"
    elif low / expected > 1:
        label = "Above expected"
    else:
        label = "Not distinguishable"
    return gap, gap_low, gap_high, label


def gap_table(entries, year="All", reference_year=2024):
    """
    The district table.

    entries         the case records (district, year, first_time, count, ...)
    year            "All" for the whole period, or one year such as 2023
    reference_year  for the whole period, expected cases use this year's population

    Districts with NO records for the chosen period are left out. They are
    missing, never counted as zero.
    """
    records = entries
    if year != "All":
        records = records[records["year"] == int(year)]

    rows = []
    for district in DISTRICTS:
        theirs = records[records["district"] == district]
        if theirs.empty:
            continue                                   # no report = left out
        reported = int(theirs.loc[theirs["first_time"] == "Yes", "count"].sum())
        expected = expected_cases(district, reference_year if year == "All" else int(year))
        rows.append({"District": district, "Reported": reported, "Expected": expected})

    table = pd.DataFrame(rows)
    if table.empty:
        return table

    # Province row: add up first, then work out the gap (never average the %).
    province = {"District": "Province", "Reported": table["Reported"].sum(),
                "Expected": table["Expected"].sum()}
    table = pd.concat([table.sort_values("Reported", ascending=False), pd.DataFrame([province])],
                      ignore_index=True)

    results = [verdict(o, e) for o, e in zip(table["Reported"], table["Expected"])]
    table["Gap %"] = [r[0] for r in results]
    table["Gap low"] = [r[1] for r in results]
    table["Gap high"] = [r[2] for r in results]
    table["Result"] = [r[3] for r in results]

    # Largest gap first, province row always last.
    body = table[table["District"] != "Province"].sort_values("Gap %", ascending=False)
    return pd.concat([body, table[table["District"] == "Province"]], ignore_index=True)
