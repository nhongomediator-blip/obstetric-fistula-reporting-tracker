"""
dash03_first_dashboard.py

DASHBOARD 03: the first dashboard. It shows the reporting-gap table with a
year filter.

HOW A SHINY APP IS BUILT
A Shiny app has exactly two parts:

    app_ui   = WHAT THE PAGE LOOKS LIKE  (titles, drop-downs, empty slots)
    server() = WHAT THE PAGE DOES        (fills the slots with results)

They are connected by names:
    input.year()        the value the person picked in the "year" drop-down
    output.district_table  the slot called "district_table" that we fill with a table

The important idea is REACTIVITY. Inside server() the calculation is written once.
Shiny remembers that it uses input.year(), so whenever a person changes the
year, Shiny re-runs the calculation and redraws the table.

WHAT THIS STEP SHOWS
  - app_ui with a title, one drop-down and one table slot
  - server() that calls gap_table() from gap_functions.py

HOW TO RUN
    pip install shiny pandas scipy
    shiny run --launch-browser dash03_first_dashboard.py
Your browser opens at http://127.0.0.1:8000. Press Ctrl+C in the terminal to stop.
"""

from pathlib import Path

import pandas as pd
from shiny import App, render, ui

from gap_functions import gap_table

DATA_FILE = Path(__file__).parent / "data" / "entries.csv"

# The drop-down choices: the whole period, then each year from 2030 back to 2015.
YEAR_CHOICES = ["All"] + [str(y) for y in range(2030, 2014, -1)]


# ----------------------------------------------------------------------------
# PART 1: WHAT THE PAGE LOOKS LIKE
# ----------------------------------------------------------------------------
app_ui = ui.page_fluid(
    ui.h2("Obstetric Fistula Reporting Tracker - Manicaland"),
    ui.p("Reporting gap = the share of expected cases that never reach the records."),

    # A drop-down. Its first argument, "year", is the NAME the server will use:
    # input.year() gives whatever the person has selected.
    ui.input_select("year", "Year", YEAR_CHOICES, selected="All"),

    # An empty slot named "district_table". The server fills it.
    ui.output_data_frame("district_table"),
)


# ----------------------------------------------------------------------------
# PART 2: WHAT THE PAGE DOES
# ----------------------------------------------------------------------------
def server(input, output, session):

    # @render.data_frame says: "whatever this function returns goes into the
    # slot with the same name (district_table)". Because the function reads
    # input.year(), Shiny re-runs it every time the year changes.
    @render.data_frame
    def district_table():
        entries = pd.read_csv(DATA_FILE)             # read the latest records
        table = gap_table_for(entries, input.year())
        return render.DataGrid(table, width="100%")


def gap_table_for(entries, year):
    """Ask gap_functions for the table, then tidy it for showing on screen."""
    table = gap_table(entries, year=year)            # the dash01 + dash02 calculation
    if table.empty:
        return pd.DataFrame({"Message": ["No records for this period yet."]})
    # Round only for display, and give the columns friendly names.
    return pd.DataFrame({
        "District": table["District"],
        "Reported": table["Reported"],
        "Expected": table["Expected"].round(1),
        "Gap %": table["Gap %"].round(1),
        "95% range": table["Gap low"].round(1).astype(str) + " to " + table["Gap high"].round(1).astype(str),
        "Result": table["Result"],
    })


app = App(app_ui, server)
