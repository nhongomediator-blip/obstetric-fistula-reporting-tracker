"""
dashboard_data.py

THE DATA LAYER OF THE DASHBOARD
Everything that reads, checks, saves, imports or removes case records lives
here, separate from the screen (the dash scripts) and from the calculations
(gap_functions.py). Keeping the three apart means a rule such as "the year
must be between 2015 and 2024" is written once and applies to the entry
form and to file import alike.

THE RULES 
Each record is checked before it is saved:
  - district  must be one of the seven study districts
  - year      must be a whole number inside the study window (2015 to 2024)
  - count     must be a whole number of zero or more
  - first_time must be "Yes" or "No" (only "Yes" counts as a reported case)
Records are saved with the date of entry. Only aggregate counts are stored:
no names or other personal identifiers.

RECORD NUMBERS
  s000 to s030   the 31 study records (repair camp logs); these cannot be removed
  d001, d002 ... records added through the entry form
  i001, i002 ... records added by importing a file
Only d and i records can be removed, so a mistaken entry can be corrected
without ever altering the study data.

SAVING IS SAFE
A record is first written to a temporary file, which then replaces
entries.csv in one step. The dashboard checks entries.csv every second, so
it can never read a half-written file.
"""

import os
from datetime import date
from pathlib import Path

import pandas as pd

from gap_functions import DISTRICTS

YEAR_MIN = 2015
YEAR_MAX = 2024
FIRST_TIME_CHOICES = ["Yes", "No"]
COLUMNS = ["id", "district", "year", "facility", "source", "first_time", "count", "added"]
PROTECTED_PREFIX = "s"          # study records: s000 to s030
MAX_TEXT_LENGTH = 100

TEMPLATE_TEXT = (
    "district,year,facility,source,first_time,count\n"
    "Mutare,2024,Example repair camp,Repair camp,Yes,5\n"
    "Makoni,2024,Example repair camp,Repair camp,Yes,2\n"
)


# ------------------------------------------------------------------ reading
def load_entries(path):
    """Reads the records table. A missing file gives an empty table."""
    path = Path(path)
    if not path.exists():
        return pd.DataFrame(columns=COLUMNS)
    data = pd.read_csv(path, dtype=str, keep_default_na=False)
    for column in COLUMNS:
        if column not in data.columns:
            data[column] = ""
    data["year"] = pd.to_numeric(data["year"], errors="coerce").fillna(0).astype(int)
    data["count"] = pd.to_numeric(data["count"], errors="coerce").fillna(0).astype(int)
    return data[COLUMNS]


def save_entries(data, path):
    """Writes the table safely: temporary file first, then replace."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    data[COLUMNS].to_csv(temporary, index=False)
    try:
        os.replace(temporary, path)
    except PermissionError as error:
        temporary.unlink(missing_ok=True)
        raise OSError(
            f"{path.name} is open in another program (for example Excel). "
            "Close it and try again."
        ) from error


# --------------------------------------------------------------- validating
def whole_number(value):
    """Returns value as an int if it is a whole number, otherwise None."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(str(value).strip())
    except ValueError:
        return None
    if number != number or not number.is_integer():      # NaN or a fraction
        return None
    return int(number)


def canonical_district(name):
    """Matches a district name ignoring case and spaces; None if not a study district."""
    wanted = str(name).strip().lower()
    for district in DISTRICTS:
        if district.lower() == wanted:
            return district
    return None


def canonical_first_time(value):
    """Accepts yes/no in any capitalisation; None for anything else."""
    wanted = str(value).strip().lower()
    return {"yes": "Yes", "no": "No"}.get(wanted)


def validate_record(district, year, count, first_time):
    """
    Checks one record against the rules above.

    Returns:
        list of str: the problems found (an empty list means the record is valid).
    """
    problems = []
    if district not in DISTRICTS:
        problems.append(f"District must be one of the seven study districts (got '{district}').")
    year_number = whole_number(year)
    if year_number is None:
        problems.append("Year must be a whole number.")
    elif not YEAR_MIN <= year_number <= YEAR_MAX:
        problems.append(f"Year must be between {YEAR_MIN} and {YEAR_MAX} (got {year_number}).")
    count_number = whole_number(count)
    if count_number is None:
        problems.append("Count must be a whole number.")
    elif count_number < 0:
        problems.append("Count must be zero or more.")
    if first_time not in FIRST_TIME_CHOICES:
        problems.append("First-time status must be Yes or No.")
    return problems


# ------------------------------------------------------------------- adding
def next_id(data, prefix):
    """The next free record number for a prefix, for example d001 then d002."""
    numbers = [
        int(identifier[len(prefix):])
        for identifier in data["id"]
        if identifier.startswith(prefix) and identifier[len(prefix):].isdigit()
    ]
    return f"{prefix}{(max(numbers) + 1 if numbers else 1):03d}"


def _clean_text(value, default=""):
    text = str(value).strip() if value is not None else ""
    return text[:MAX_TEXT_LENGTH] if text else default


def add_record(path, record):
    """
    Validates and saves one record from the entry form.

    Args:
        path: the records file.
        record (dict): district, year, count, first_time, and optionally
            facility and source.

    Returns:
        str: the new record number.

    Raises:
        ValueError: if the record breaks a rule (the message lists every problem).
        OSError: if the file cannot be written.
    """
    problems = validate_record(
        record.get("district"), record.get("year"), record.get("count"), record.get("first_time")
    )
    if problems:
        raise ValueError(" ".join(problems))
    data = load_entries(path)
    new_id = next_id(data, "d")
    row = {
        "id": new_id,
        "district": record["district"],
        "year": whole_number(record["year"]),
        "facility": _clean_text(record.get("facility")),
        "source": _clean_text(record.get("source"), "Dashboard entry"),
        "first_time": record["first_time"],
        "count": whole_number(record["count"]),
        "added": date.today().isoformat(),
    }
    save_entries(pd.concat([data, pd.DataFrame([row])], ignore_index=True), path)
    return new_id


# ---------------------------------------------------------------- importing
def import_records(path, uploaded):
    """
    Validates every row of an uploaded table and saves the valid ones.

    Required columns: district, year, first_time, count. Optional: facility,
    source. Rows that break a rule are rejected and listed with the reason.
    Rows that repeat a record already stored (or repeat an earlier row in the
    same file) are skipped as duplicates, so importing the same file twice
    cannot double the counts.

    Returns:
        dict with "saved" (int), "duplicates" (int) and "rejected"
        (DataFrame of file row numbers and reasons).

    Raises:
        ValueError: if a required column is missing.
    """
    uploaded = uploaded.copy()
    uploaded.columns = [str(c).strip().lower() for c in uploaded.columns]
    missing = [c for c in ["district", "year", "first_time", "count"] if c not in uploaded.columns]
    if missing:
        raise ValueError("The file is missing required column(s): " + ", ".join(missing) + ".")
    for optional in ["facility", "source"]:
        if optional not in uploaded.columns:
            uploaded[optional] = ""

    data = load_entries(path)
    seen = set(
        zip(data["district"], data["year"], data["facility"], data["source"],
            data["first_time"], data["count"])
    )
    accepted, rejected, duplicates = [], [], 0
    for position, row in uploaded.iterrows():
        file_row = position + 2                      # row 1 of the file is the header
        district = canonical_district(row["district"])
        first_time = canonical_first_time(row["first_time"])
        problems = validate_record(district, row["year"], row["count"], first_time)
        if problems:
            rejected.append({"file row": file_row, "reason": " ".join(problems)})
            continue
        record = {
            "district": district,
            "year": whole_number(row["year"]),
            "facility": _clean_text(row["facility"]),
            "source": _clean_text(row["source"], "Import"),
            "first_time": first_time,
            "count": whole_number(row["count"]),
        }
        key = (record["district"], record["year"], record["facility"], record["source"],
               record["first_time"], record["count"])
        if key in seen:
            duplicates += 1
            continue
        seen.add(key)
        accepted.append(record)

    if accepted:
        today = date.today().isoformat()
        new_rows = []
        for record in accepted:
            identifier = next_id(pd.concat([data, pd.DataFrame(new_rows, columns=COLUMNS)]), "i")
            new_rows.append({"id": identifier, **record, "added": today})
        save_entries(pd.concat([data, pd.DataFrame(new_rows)], ignore_index=True), path)
    return {
        "saved": len(accepted),
        "duplicates": duplicates,
        "rejected": pd.DataFrame(rejected, columns=["file row", "reason"]),
    }


# ----------------------------------------------------------------- removing
def deletable_ids(data):
    """Records that may be removed: everything except the study records."""
    return [i for i in data["id"] if not i.startswith(PROTECTED_PREFIX)]


def delete_record(path, record_id):
    """
    Removes one record added through the dashboard.

    Raises:
        ValueError: if the record is a study record or does not exist.
    """
    data = load_entries(path)
    if record_id.startswith(PROTECTED_PREFIX):
        raise ValueError(f"{record_id} is a study record and cannot be removed.")
    if record_id not in set(data["id"]):
        raise ValueError(f"Record {record_id} was not found.")
    save_entries(data[data["id"] != record_id], path)
