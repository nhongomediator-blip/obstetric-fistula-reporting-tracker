"""
dash_tests.py

THE AUTOMATIC TESTS FOR THE DASHBOARD (Section 3.3.7 of Chapter 3)

HOW TO RUN (in the same folder as gap_functions.py and dashboard_data.py)
    python dash_tests.py
Each check prints PASS or FAIL. The program ends with a count, and stops with an error
if any check failed. The tests work on a TEMPORARY COPY of data/entries.csv, so they
never add, change or remove a record in your real data.

WHAT IS TESTED
  1. ACCURACY      the dashboard's whole-period table is compared with the Step 8
                   results (reported, expected, gap, 95% interval) for every district,
                   the province row is checked, and rows of the yearly table are
                   compared with Step 8b. A difference above rounding is a FAIL.
  2. ALERT LOGIC   records with known counts give a "Significant gap", an
                   "Above expected" and a "Not distinguishable" result, and a
                   district with no records is left out and not shown as zero.
  3. RULES         the entry rules reject a wrong district, year, count or status.
  4. SAVING        a saved record appears in the table and a removed record
                   disappears; study records cannot be removed.
  5. IMPORT        valid rows are saved, bad rows are rejected with a reason, and
                   importing the same file twice adds nothing.

Step 8 and Step 8b results are read from your CHAPTER 3 METHODOLOGY folder when the
files are there; otherwise the values printed by those steps (stored below) are used.
The browser checks (tabs, year filter, map, entry form) are done by hand using the
"HOW TO TEST" lists at the top of dash05 to dash08.
"""

import shutil
import sys
import tempfile
from pathlib import Path

import pandas as pd

from gap_functions import gap_table
from dashboard_data import (add_record, delete_record, import_records, load_entries, validate_record)

HERE = Path(__file__).parent
ENTRIES = HERE / "data" / "entries.csv"
BASE = Path(r"C:\Users\nhong\OneDrive\Desktop\DISSERTATION FOR SUBMISSION FINALEST\CHAPTER 3 METHODOLOGY")
STEP8_FILE = BASE / "reporting_gap_results.csv"
STEP8B_FILE = BASE / "yearly_reporting_gap_results.csv"

# Step 8 as printed: district: (reported, expected, gap %, ratio, ratio lower, ratio upper)
STEP8 = {
    "Makoni": (14, 93.0, 84.9, 0.151, 0.082, 0.253),
    "Mutasa": (9, 57.7, 84.4, 0.156, 0.071, 0.296),
    "Nyanga": (13, 41.7, 68.9, 0.311, 0.166, 0.533),
    "Mutare": (60, 154.0, 61.0, 0.390, 0.297, 0.501),
    "Buhera": (36, 74.2, 51.5, 0.485, 0.340, 0.671),
    "Chimanimani": (26, 43.1, 39.7, 0.603, 0.394, 0.884),
    "Chipinge": (72, 111.8, 35.6, 0.644, 0.504, 0.811),
}
# Step 8b as printed: (district, year): (expected, reported, ratio, lower, upper)
STEP8B = {
    ("Buhera", 2018): (67.9, 8, 0.118, 0.051, 0.232),
    ("Chipinge", 2018): (102.3, 39, 0.381, 0.271, 0.521),
    ("Makoni", 2018): (85.1, 1, 0.012, 0.000, 0.065),
    ("Mutare", 2019): (143.0, 23, 0.161, 0.102, 0.241),
    ("Mutare", 2020): (145.1, 1, 0.007, 0.000, 0.038),
    ("Nyanga", 2022): (40.5, 3, 0.074, 0.015, 0.216),
    ("Chimanimani", 2022): (41.8, 14, 0.335, 0.183, 0.562),
}

results = []


def check(name, condition, detail=""):
    results.append(bool(condition))
    print(("PASS  " if condition else "FAIL  ") + name + (f"   [{detail}]" if detail and not condition else ""))


def ratio_interval(row):
    """Converts a dashboard row back to ratio, lower and upper ratio (the Step 8 form)."""
    return (row["Reported"] / row["Expected"], 1 - row["Gap high"] / 100, 1 - row["Gap low"] / 100)


def row_of(table, district):
    return table[table["District"] == district].iloc[0]


def test_accuracy(entries):
    print("\n1. ACCURACY against Step 8 (whole period)")
    step8 = STEP8
    if STEP8_FILE.exists():
        file = pd.read_csv(STEP8_FILE)
        step8 = {r["district"]: (r["reported_cases"], r["expected_cases"], r["reporting_gap_pct"],
                                 r["reported_to_expected_ratio"], r["ratio_95CI_lower"], r["ratio_95CI_upper"])
                 for _, r in file.iterrows()}
        print("   (comparing with reporting_gap_results.csv)")
    table = gap_table(entries, "All")
    for district, (reported, expected, gap, ratio, low, high) in step8.items():
        r = row_of(table, district)
        got_ratio, got_low, got_high = ratio_interval(r)
        check(f"{district}: reported {int(reported)}", int(r["Reported"]) == int(reported), r["Reported"])
        check(f"{district}: expected {expected:.1f}", abs(round(r["Expected"], 1) - round(expected, 1)) < 0.051, r["Expected"])
        check(f"{district}: gap {gap:.1f}%", abs(round(r["Gap %"], 1) - round(gap, 1)) < 0.051, r["Gap %"])
        check(f"{district}: ratio and interval",
              all(abs(round(a, 3) - round(b, 3)) < 0.0015 for a, b in
                  [(got_ratio, ratio), (got_low, low), (got_high, high)]),
              (round(got_ratio, 3), round(got_low, 3), round(got_high, 3)))
    province = row_of(table, "Province")
    body = table[table["District"] != "Province"]
    check("Province: reported is the sum of the districts", int(province["Reported"]) == int(body["Reported"].sum()))
    check("Province: expected is the sum of the districts", abs(province["Expected"] - body["Expected"].sum()) < 1e-9)
    check("Province: gap is worked out after adding (never averaged)",
          abs(province["Gap %"] - (1 - province["Reported"] / province["Expected"]) * 100) < 1e-9)
    check("Province row is last", table.iloc[-1]["District"] == "Province")

    print("\n   ACCURACY against Step 8b (single years)")
    step8b = STEP8B
    if STEP8B_FILE.exists():
        file = pd.read_csv(STEP8B_FILE)
        step8b = {(r["district"], int(r["year"])): (r["expected_cases"], r["reported_cases"],
                                                    r["reported_to_expected_ratio"], r["ratio_95CI_lower"],
                                                    r["ratio_95CI_upper"]) for _, r in file.iterrows()}
        print("   (comparing all rows of yearly_reporting_gap_results.csv)")
    for (district, year), (expected, reported, ratio, low, high) in step8b.items():
        r = row_of(gap_table(entries, year), district)
        got_ratio, got_low, got_high = ratio_interval(r)
        ok = (int(r["Reported"]) == int(reported)
              and abs(round(r["Expected"], 1) - round(expected, 1)) < 0.051
              and all(abs(round(a, 3) - round(b, 3)) < 0.0015 for a, b in
                      [(got_ratio, ratio), (got_low, low), (got_high, high)]))
        check(f"{district} {year}", ok, (int(r["Reported"]), round(r["Expected"], 1), round(got_ratio, 3)))


def test_alert_logic(entries):
    print("\n2. ALERT LOGIC (Mutare 2022: expected 149.5 cases)")

    def status(count, first_time="Yes"):
        records = pd.DataFrame([{"district": "Mutare", "year": 2022, "first_time": first_time, "count": count}])
        return gap_table(records, 2022)

    check("20 reported gives Significant gap", row_of(status(20), "Mutare")["Result"] == "Significant gap")
    check("149 reported gives Not distinguishable", row_of(status(149), "Mutare")["Result"] == "Not distinguishable")
    check("200 reported gives Above expected", row_of(status(200), "Mutare")["Result"] == "Above expected")
    check("a district with no records is left out, not shown as zero",
          list(status(20)["District"]) == ["Mutare", "Province"])
    check("a 'No' (not first-time) record does not count as reported",
          int(row_of(status(100, "No"), "Mutare")["Reported"]) == 0)
    check("no records at all gives an empty table", gap_table(entries, 2024).empty)
    t2020 = gap_table(entries, 2020)
    check("2020 has only Mutare (the other six are missing, not zero)",
          list(t2020["District"]) == ["Mutare", "Province"])
    ranked = gap_table(entries, "All")
    body = ranked[ranked["District"] != "Province"]
    check("districts are ranked by size of gap, largest first",
          list(body["Gap %"]) == sorted(body["Gap %"], reverse=True))


def test_rules():
    print("\n3. ENTRY RULES")
    cases = [
        ("valid record", ("Mutare", 2024, 5, "Yes"), True),
        ("zero count", ("Mutare", 2024, 0, "Yes"), True),
        ("first year of the window (2015)", ("Buhera", 2015, 1, "No"), True),
        ("district not in the study", ("Harare", 2024, 5, "Yes"), False),
        ("year after the window (2025)", ("Mutare", 2025, 5, "Yes"), False),
        ("year before the window (2014)", ("Mutare", 2014, 5, "Yes"), False),
        ("year that is not a whole number", ("Mutare", 2020.5, 5, "Yes"), False),
        ("negative count", ("Mutare", 2024, -1, "Yes"), False),
        ("fractional count", ("Mutare", 2024, 2.5, "Yes"), False),
        ("count missing", ("Mutare", 2024, None, "Yes"), False),
        ("count is text", ("Mutare", 2024, "five", "Yes"), False),
        ("first-time status missing", ("Mutare", 2024, 5, ""), False),
        ("first-time status not Yes/No", ("Mutare", 2024, 5, "Maybe"), False),
    ]
    for name, args, should_pass in cases:
        check(name + (" is accepted" if should_pass else " is rejected"),
              (validate_record(*args) == []) == should_pass)


def test_saving(work_file):
    print("\n4. SAVING AND REMOVING RECORDS (on a temporary copy)")
    before = gap_table(load_entries(work_file), "All")
    new_id = add_record(work_file, {"district": "Mutare", "year": 2024, "count": 5, "first_time": "Yes",
                                    "facility": "Test camp", "source": "Repair camp"})
    after = load_entries(work_file)
    check("a saved record gets the next d number", new_id == "d001")
    check("the record is in the file with today's date",
          new_id in set(after["id"]) and after.loc[after["id"] == new_id, "added"].iloc[0] != "")
    check("the table changes: Mutare reported rises by 5",
          int(row_of(gap_table(after, "All"), "Mutare")["Reported"]) ==
          int(row_of(before, "Mutare")["Reported"]) + 5)
    check("a second record gets d002", add_record(work_file, {"district": "Makoni", "year": 2024, "count": 1,
                                                              "first_time": "Yes"}) == "d002")
    size = len(load_entries(work_file))
    try:
        add_record(work_file, {"district": "Mutare", "year": 2030, "count": 5, "first_time": "Yes"})
        rejected = False
    except ValueError:
        rejected = True
    check("an invalid record raises an error and nothing is saved", rejected and len(load_entries(work_file)) == size)
    delete_record(work_file, "d001")
    check("a removed record disappears", "d001" not in set(load_entries(work_file)["id"]))
    for protected in ["s000", "s030"]:
        try:
            delete_record(work_file, protected)
            refused = False
        except ValueError:
            refused = True
        check(f"study record {protected} cannot be removed", refused)
    try:
        delete_record(work_file, "d999")
        refused = False
    except ValueError:
        refused = True
    check("removing a record that does not exist is refused", refused)


def test_import(work_file):
    print("\n5. IMPORTING A FILE (on a temporary copy)")
    start = len(load_entries(work_file))
    upload = pd.DataFrame({
        "district": ["Nyanga", "mutare", "Harare", "Buhera", "Nyanga"],
        "year": ["2024", "2024", "2024", "2030", "2024"],
        "facility": ["Camp A", "Camp A", "Camp A", "Camp A", "Camp A"],
        "source": ["Repair camp"] * 5,
        "first_time": ["Yes", "yes", "Yes", "Yes", "Yes"],
        "count": ["4", "3", "2", "1", "4"],
    })
    result = import_records(work_file, upload)
    check("2 valid rows are saved (lower-case district accepted)", result["saved"] == 2, result["saved"])
    check("the repeated row is skipped as a duplicate", result["duplicates"] == 1, result["duplicates"])
    check("2 bad rows are rejected (wrong district, year 2030)", len(result["rejected"]) == 2)
    check("rejected rows give the file row number", list(result["rejected"]["file row"]) == [4, 5])
    check("the file now has 2 more records", len(load_entries(work_file)) == start + 2)
    again = import_records(work_file, upload)
    check("importing the same file again saves nothing", again["saved"] == 0 and again["duplicates"] == 3,
          (again["saved"], again["duplicates"]))
    ids = list(load_entries(work_file)["id"])
    check("imported records are numbered i001, i002", "i001" in ids and "i002" in ids)
    try:
        import_records(work_file, pd.DataFrame({"district": ["Mutare"], "year": [2024]}))
        refused = False
    except ValueError:
        refused = True
    check("a file with a missing column is refused", refused)


def main():
    if not ENTRIES.exists():
        sys.exit(f"Cannot find {ENTRIES}. Run this file from the dashboard folder.")
    with tempfile.TemporaryDirectory() as folder:
        work_file = Path(folder) / "entries.csv"
        shutil.copy(ENTRIES, work_file)
        entries = load_entries(ENTRIES)
        print(f"Testing with {len(entries)} records from {ENTRIES}")
        test_accuracy(entries)
        test_alert_logic(entries)
        test_rules()
        test_saving(work_file)
        test_import(work_file)
    passed = sum(results)
    print(f"\n{passed} of {len(results)} checks passed.")
    if passed != len(results):
        sys.exit("Some checks FAILED. Read the FAIL lines above.")


if __name__ == "__main__":
    main()
