"""
================================================================================
STEP 7: CASE DATA EXTRACTION
================================================================================

Reads the repair camp patient log files and extracts the home district
and procedure year of each first-time patient, together with the
duration of delay. Output is the number of reported cases for every
district-year.

Only first-time patients are counted. A woman returning for repeat or
revision surgery is already known to the system, so counting every row
would count the same woman more than once. A patient is first-time when
the number of previous repairs is zero or the "New Patient" flag is
Yes, whichever the file provides.

The log files come from different hospitals and formats. The script
handles three differences automatically:
  1. Title rows above the column headers (several header rows are tried).
  2. Workbooks with reference lists on the first sheet and patient data
     on another sheet (every sheet is checked).
  3. Files that store the province in "Patient Home District" and the
     district in a separate location column (the layout is detected).

No individual-level information is retained. Only counts and average
delay per district-year are saved.

Input:  folder of repair camp log files (.xlsx and .xls)
Output: manicaland_case_data.xlsx
        sheet "Yearly Counts" (district-year counts)
        sheet "Whole-Period Totals" (district totals)

Usage:
    python step07_case_data_extraction.py
================================================================================
"""

from environment_setup import fix_proj_database
fix_proj_database()

import pandas as pd
import glob
import os


# ------------------------------------------------------------------------------
# SETTINGS
# ------------------------------------------------------------------------------

INPUT_FOLDER = r"C:\Users\nhong\OneDrive\Desktop\DISSERTATION FOR SUBMISSION FINALEST\CHAPTER 3 METHODOLOGY\RAW DATA\Fistula logs"
OUTPUT_FILE = r"C:\Users\nhong\OneDrive\Desktop\DISSERTATION FOR SUBMISSION FINALEST\CHAPTER 3 METHODOLOGY\manicaland_case_data.xlsx"

STUDY_START_YEAR = 2015
STUDY_END_YEAR = 2024
MAX_HEADER_ROWS_TO_TRY = 8
PREFERRED_SHEET_NAMES = ["patient log", "surgery log", "fistula surgery log", "data"]

MANICALAND_DISTRICTS = {
    "MUTARE": "Mutare", "MAKONI": "Makoni", "BUHERA": "Buhera",
    "CHIPINGE": "Chipinge", "CHIMANIMANI": "Chimanimani",
    "NYANGA": "Nyanga", "INYANGA": "Nyanga", "MUTASA": "Mutasa",
    # Some files record a well-known sub-area/town name instead of the
    # formal district name. These are added here so such patients are
    # still correctly counted under their real district, rather than
    # silently excluded for not matching a formal district name exactly.
    # "Honde Valley" was found in real data (CPH Oct2018 Fistula Log.xlsx)
    # recorded as a district value, and is a well-known area within
    # Mutasa District.
    "HONDE VALLEY": "Mutasa",
    "RUSAPE": "Makoni",  # Rusape Town Council sits within Makoni District
}

# Two different column layouts appear across files -- see module docstring.
DIRECT_DISTRICT_CANDIDATES = ["Home District/County", "Home District"]
PROVINCE_CANDIDATES = ["Patient Home District"]
LOCATION_VILLAGE_CANDIDATES = ["Patient Home Location/Village", "Home Location/Village"]

DATE_COLUMN_CANDIDATES = ["Date of Procedure", "Date of Admission (MM/DD/YYYY)",
                           "Date of Surgery (MM/DD/YYYY)", "Date of Surgery (dd/mm/yyyy)", "Date of Surgery"]
DURATION_COLUMN_CANDIDATES = ["Years living with Fistula", "yrs with Fistula (in years)"]
PREV_SURGERY_COUNT_CANDIDATES = ["Number of previous fistula repair surgeries TOTAL"]
NEW_PATIENT_FLAG_CANDIDATES = ["New Patient (Yes/No)"]


def find_column(columns, candidates):
    """
    Finds which column in a list matches one of several possible names,
    ignoring case and leading/trailing whitespace differences.

    Args:
        columns (Iterable[str]): Column names actually present in a file.
        candidates (list[str]): Acceptable names to look for, in order.

    Returns:
        str or None: The matching column name as it actually appears in
            the file, or None if no candidate matched.
    """
    cleaned = {str(c).strip().lower(): c for c in columns}
    for candidate in candidates:
        key = candidate.strip().lower()
        if key in cleaned:
            return cleaned[key]
    return None


def pick_sheet_order(sheet_names):
    """
    Orders a workbook's sheets so that likely-data sheets (matching
    PREFERRED_SHEET_NAMES) are tried first, with every other sheet tried
    afterward as a fallback.

    Args:
        sheet_names (list[str]): All sheet names in a workbook.

    Returns:
        list[str]: The same sheet names, reordered by likely relevance.
    """
    lower_map = {s.lower(): s for s in sheet_names}
    ordered = [lower_map[pref] for pref in PREFERRED_SHEET_NAMES if pref in lower_map]
    ordered += [s for s in sheet_names if s not in ordered]
    return ordered


def try_read_file(filepath):
    """
    Attempts to find the real patient data within one log file, trying
    each sheet and each candidate header row until the required columns
    are found.

    Args:
        filepath (str): Path to one .xlsx or .xls log file.

    Returns:
        dict or None: Details of the successful read (dataframe, sheet
            name, header row, which column layout was used, and which
            columns were found), or None if no valid combination worked.
    """
    try:
        xl = pd.ExcelFile(filepath)
    except Exception:
        return None

    for sheet in pick_sheet_order(xl.sheet_names):
        for header_row in range(MAX_HEADER_ROWS_TO_TRY):
            try:
                df = pd.read_excel(filepath, sheet_name=sheet, header=header_row)
            except Exception:
                continue

            date_col = find_column(df.columns, DATE_COLUMN_CANDIDATES)
            if not date_col:
                continue

            direct_district_col = find_column(df.columns, DIRECT_DISTRICT_CANDIDATES)
            province_col = find_column(df.columns, PROVINCE_CANDIDATES)
            village_col = find_column(df.columns, LOCATION_VILLAGE_CANDIDATES)
            prev_col = find_column(df.columns, PREV_SURGERY_COUNT_CANDIDATES)
            newpatient_col = find_column(df.columns, NEW_PATIENT_FLAG_CANDIDATES)
            duration_col = find_column(df.columns, DURATION_COLUMN_CANDIDATES)

            if direct_district_col:
                return {"df": df, "sheet": sheet, "header_row": header_row, "mode": "direct",
                        "district_col": direct_district_col, "date_col": date_col,
                        "prev_col": prev_col, "newpatient_col": newpatient_col, "duration_col": duration_col}

            if province_col and village_col:
                return {"df": df, "sheet": sheet, "header_row": header_row, "mode": "province_village",
                        "province_col": province_col, "village_col": village_col, "date_col": date_col,
                        "prev_col": prev_col, "newpatient_col": newpatient_col, "duration_col": duration_col}

    return None


def process_one_file(filepath):
    """
    Reads, filters, and cleans one log file down to first-time
    Manicaland-resident patients within the study period, keeping only
    district, year, and duration of delay.

    Args:
        filepath (str): Path to one .xlsx or .xls log file.

    Returns:
        tuple[pandas.DataFrame or None, str]: The qualifying rows (or
            None if there were zero), and a status string explaining
            what happened: "ok", "unreadable" (columns could not be
            found at all), or "zero_qualifying" (read successfully, but
            no rows matched Manicaland/first-time/study-year criteria).
    """
    result = try_read_file(filepath)
    if result is None:
        return None, "unreadable"

    df = result["df"]
    total_rows_before_filtering = len(df)

    if result["mode"] == "direct":
        df["district_clean"] = df[result["district_col"]].astype(str).str.strip().str.upper()
    else:
        df["province_clean"] = df[result["province_col"]].astype(str).str.strip().str.upper()
        df = df[df["province_clean"] == "MANICALAND"].copy()
        df["district_clean"] = df[result["village_col"]].astype(str).str.strip().str.upper()

    df = df[df["district_clean"].isin(MANICALAND_DISTRICTS.keys())].copy()
    rows_after_district_filter = len(df)

    if result["prev_col"]:
        df = df[pd.to_numeric(df[result["prev_col"]], errors="coerce").fillna(0) == 0].copy()
    elif result["newpatient_col"]:
        df = df[df[result["newpatient_col"]].astype(str).str.strip().str.lower() == "yes"].copy()
    rows_after_firsttime_filter = len(df)

    if len(df) == 0:
        print(f"    (read OK: {total_rows_before_filtering} total rows -> "
              f"{rows_after_district_filter} in Manicaland -> "
              f"{rows_after_firsttime_filter} first-time patients)")
        return None, "zero_qualifying"

    df["district"] = df["district_clean"].map(MANICALAND_DISTRICTS)
    df["year"] = pd.to_datetime(df[result["date_col"]], errors="coerce").dt.year
    df = df[(df["year"] >= STUDY_START_YEAR) & (df["year"] <= STUDY_END_YEAR)]

    if len(df) == 0:
        print(f"    (read OK: {rows_after_firsttime_filter} first-time Manicaland patients, "
              f"but none fell within {STUDY_START_YEAR}-{STUDY_END_YEAR})")
        return None, "zero_qualifying"

    if result["duration_col"]:
        df["duration_years"] = pd.to_numeric(df[result["duration_col"]], errors="coerce")
    else:
        df["duration_years"] = pd.NA

    return df[["district", "year", "duration_years"]], "ok"


def build_summary_tables(all_patient_rows):
    """
    Aggregates individual patient rows into two safe, summary-only
    tables: yearly counts, and whole-period totals, each with average
    duration of delay.

    Args:
        all_patient_rows (pandas.DataFrame): Combined rows from every
            file, columns "district", "year", "duration_years".

    Returns:
        tuple[pandas.DataFrame, pandas.DataFrame]: (yearly summary,
            whole-period summary).
    """
    yearly = all_patient_rows.groupby(["district", "year"]).agg(
        reported_cases=("duration_years", "size"),
        avg_duration_years=("duration_years", "mean"),
    ).reset_index()
    yearly["avg_duration_years"] = yearly["avg_duration_years"].round(2)
    yearly = yearly.sort_values(["district", "year"])

    totals = all_patient_rows.groupby("district").agg(
        total_reported_cases=("duration_years", "size"),
        avg_duration_years=("duration_years", "mean"),
    ).reset_index()
    totals["avg_duration_years"] = totals["avg_duration_years"].round(2)
    totals = totals.sort_values("district")

    return yearly, totals


def main():
    """
    Runs the full Step 7 pipeline: reads every log file in the input
    folder, extracts and cleans qualifying patient rows, builds the
    yearly and whole-period summary tables, and saves both to a single,
    clearly organised Excel file.
    """
    all_files = glob.glob(os.path.join(INPUT_FOLDER, "*.xlsx")) + glob.glob(os.path.join(INPUT_FOLDER, "*.xls"))
    print(f"Found {len(all_files)} files to process.\n")

    all_rows = []
    unreadable = []
    zero_qualifying = []

    for filepath in all_files:
        fname = os.path.basename(filepath)
        rows, status = process_one_file(filepath)
        if status == "unreadable":
            unreadable.append(fname)
            print(f"UNREADABLE (no matching columns found): {fname}")
        elif status == "zero_qualifying":
            zero_qualifying.append(fname)
            print(f"READ OK, but 0 qualifying rows: {fname}")
        else:
            all_rows.append(rows)
            print(f"OK: {fname} -> {len(rows)} qualifying rows")

    print(f"\n--- Summary ---")
    print(f"{len(all_files)} files found.")
    print(f"{len(all_files) - len(unreadable) - len(zero_qualifying)} files contributed real data.")
    print(f"{len(zero_qualifying)} files were read successfully but had zero qualifying rows "
          f"(check the reasons printed above -- e.g. no Manicaland patients, all repeat patients, "
          f"or outside 2015-2024).")
    print(f"{len(unreadable)} files could not be read at all (genuinely different format, "
          f"or missing a district column entirely).")
    if unreadable:
        print("\nTruly unreadable files:", unreadable)
    if zero_qualifying:
        print("\nRead OK but zero qualifying rows:", zero_qualifying)

    if not all_rows:
        print("\nNo qualifying rows found across any file. Nothing to save.")
        return

    combined = pd.concat(all_rows, ignore_index=True)
    yearly, totals = build_summary_tables(combined)

    print("\nYearly counts:")
    print(yearly.to_string(index=False))
    print("\nWhole-period totals:")
    print(totals.to_string(index=False))

    # Save both tables as separate, clearly labelled sheets in one Excel file.
    with pd.ExcelWriter(OUTPUT_FILE, engine="openpyxl") as writer:
        yearly.to_excel(writer, sheet_name="Yearly Counts", index=False)
        totals.to_excel(writer, sheet_name="Whole-Period Totals", index=False)

    print(f"\nSaved to: {OUTPUT_FILE}")
    print("(Sheets: 'Yearly Counts' and 'Whole-Period Totals')")


if __name__ == "__main__":
    main()
