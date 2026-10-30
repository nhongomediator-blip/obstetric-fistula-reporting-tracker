"""
dash05_entering_cases.py

DASHBOARD 05: entering cases and saving them live. It adds two things to dash04.
  1. TABS      the page is now split into tabs: "Overview" (everything from
               dash04) and "Add a record" (new).
  2. THE FORM  a record is typed into a form, checked, saved to
               data/entries.csv with the date of entry, and shows up on the
               Overview tab within about a second. The program is not restarted.

THE CHECKS 
Before anything is saved, the record must pass every rule in dashboard_data.py:
  - the district is one of the seven study districts
  - the year is a whole number from 2015 to 2024
  - the count is a whole number of zero or more
  - first-time status is Yes or No
A record that breaks a rule is NOT saved, and the message says which rule. Only
first-time patients count as reported cases, so a "No" record is stored but does
not change the gap.

THE NEW IDEAS IN THIS STEP
  @reactive.event   "do this only when the Save button is pressed"
  @reactive.poll    "look at the file every second; if it changed, read it again".
                    This is what makes the dashboard LIVE. Everything that uses
                    records() (cards, bars, table) is redrawn when the file changes.

YEAR LIST
The Year drop-down now stops at 2024 (the end of the study window). In dash03 and
dash04 it went up to 2030.

HOW TO TEST THIS STAGE
  1. Open "Add a record", choose Mutare, 2024, count 5, first-time Yes, Save.
     The Overview should show 5 more reported cases for Mutare within a second.
  2. Try year 2030, then count 2.5, then count -1. Each should be rejected.
  3. Testing adds rows to data/entries.csv. When finished, delete the rows whose
     id starts with d (dash08 adds a Remove button for this).

FILES NEEDED IN THE SAME FOLDER
    gap_functions.py          the calculations (dash01 and dash02, packaged)
    dashboard_data.py         reads, checks and saves the records
    data/entries.csv          the records

HOW TO RUN
    pip install -r requirements.txt
    shiny run --launch-browser dash05_entering_cases.py
Your browser opens at http://127.0.0.1:8000. Press Ctrl+C in the terminal to stop.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import Patch
from shiny import App, reactive, render, ui

from gap_functions import DISTRICTS, gap_table
from dashboard_data import (
    FIRST_TIME_CHOICES, TEMPLATE_TEXT, YEAR_MAX, YEAR_MIN,
    add_record, deletable_ids, delete_record, import_records, load_entries,
)

APP_DIR = Path(__file__).parent
DATA_FILE = APP_DIR / "data" / "entries.csv"
BOUNDARY_FILE = APP_DIR / "data" / "manicaland_study_area.geojson"   # Step 1 output
DISTRICT_FIELD = "district"                                          # name column in that file

# The drop-down choices: the whole period, then each year of the study window.
YEAR_CHOICES = ["All"] + [str(y) for y in range(YEAR_MAX, YEAR_MIN - 1, -1)]

# Colour AND pattern for each status, so the screen and a black-and-white
# printout both tell the statuses apart.
COLOURS = {"Significant gap": "#c0392b", "Not distinguishable": "#e0a800", "Above expected": "#2e7d32"}
PALE = {"Significant gap": "#f8d7da", "Not distinguishable": "#fff3cd", "Above expected": "#d4edda"}
HATCH = {"Significant gap": "///", "Not distinguishable": "..", "Above expected": ""}
SMALL_COUNT_NOTE = (
    "Districts with few records have wide intervals, so they are flagged less often. "
    "A district that is not flagged is not proof that its reporting is good."
)


def card(title, value, note="", colour="#34495e"):
    """One summary box: small title, big number, small note, coloured left edge."""
    return ui.div(
        ui.div(title, style="font-size:0.85rem;color:#555;"),
        ui.div(value, style=f"font-size:1.8rem;font-weight:700;color:{colour};"),
        ui.div(note, style="font-size:0.8rem;color:#777;"),
        style=(f"flex:1;min-width:180px;border:1px solid #ddd;border-left:6px solid {colour};"
               "border-radius:6px;padding:10px 14px;background:#fff;"),
    )


def message_box(kind, text):
    """A coloured message (kind: success, danger, warning, info)."""
    return ui.div(text, class_=f"alert alert-{kind}", style="margin-top:10px;")


def file_stamp():
    """Changes whenever entries.csv is saved; the live check watches this."""
    return DATA_FILE.stat().st_mtime if DATA_FILE.exists() else 0


# ----------------------------------------------------------------------------
# PART 1: WHAT THE PAGE LOOKS LIKE
# ----------------------------------------------------------------------------
app_ui = ui.page_fluid(
    ui.h2("Obstetric Fistula Reporting Tracker - Manicaland"),
    ui.p("Reporting gap = the share of expected cases that never reach the records."),
    ui.input_select("year", "Year", YEAR_CHOICES, selected="All"),
    ui.navset_tab(
        ui.nav_panel(
            "Overview",
            ui.output_ui("summary_cards"),
            ui.h4("Gap by district"),
            ui.output_plot("gap_bars", height="380px"),
            ui.h4("Reporting gap table"),
            ui.output_data_frame("district_table"),
            ui.p("Districts with no records for the chosen period are left out. They are missing, "
                 "never counted as zero.", style="color:#777;font-size:0.85rem;margin-top:8px;"),
        ),
        ui.nav_panel(
            "Add a record",
            ui.layout_columns(
                ui.card(
                    ui.card_header("Add one record"),
                    ui.input_select("entry_district", "District", DISTRICTS),
                    ui.input_numeric("entry_year", "Year", YEAR_MAX, min=YEAR_MIN, max=YEAR_MAX, step=1),
                    ui.input_text("entry_facility", "Facility or repair camp (optional)"),
                    ui.input_text("entry_source", "Source", value="Repair camp"),
                    ui.input_radio_buttons("entry_first_time", "First-time patients?",
                                           FIRST_TIME_CHOICES, selected="Yes", inline=True),
                    ui.input_numeric("entry_count", "Number of patients", 1, min=0, step=1),
                    ui.input_action_button("entry_save", "Save record", class_="btn-primary"),
                    ui.output_ui("entry_message"),
                ),
                ui.card(
                    ui.card_header("How records are used"),
                    ui.p("Only first-time patients count as reported cases, so a record marked "
                         "'No' is stored but does not change the gap."),
                    ui.p(f"The year must be between {YEAR_MIN} and {YEAR_MAX}, and the count must be a "
                         "whole number of zero or more. Anything else is rejected with a reason."),
                    ui.p("Enter counts only. Do not type patient names or other personal details "
                         "in any box."),
                    ui.p("A saved record appears in the tables and charts within about a second. "
                         "The program does not need to be restarted."),
                ),
                col_widths=[6, 6],
            ),
        ),
    ),
    ui.p("Only aggregate counts are stored; no names or personal identifiers.",
         style="color:#777;font-size:0.8rem;margin-top:12px;"),
    title="Fistula Reporting Tracker",
)


# ----------------------------------------------------------------------------
# PART 2: WHAT THE PAGE DOES
# ----------------------------------------------------------------------------
def server(input, output, session):

    # THE LIVE CHECK: Shiny looks at entries.csv every second. When the file
    # has changed, records() is read again and everything that uses it
    # (cards, bars, table, map) is recalculated automatically.
    @reactive.poll(file_stamp, 1)
    def records():
        return load_entries(DATA_FILE)

    # The one shared calculation: the same gap_table() used by the analysis.
    @reactive.calc
    def current():
        return gap_table(records(), year=input.year())

    # ---- the five summary cards ------------------------------------------
    @render.ui
    def summary_cards():
        t = current()
        if t.empty:
            return ui.p("No records for this period yet.")
        province = t[t["District"] == "Province"].iloc[0]
        districts = t[t["District"] != "Province"]
        top = districts.iloc[0]                      # gap_table sorts largest gap first
        cards = [
            card("Province reported", f"{int(province['Reported'])}", "first-time cases in the records"),
            card("Province expected", f"{province['Expected']:.1f}", "adult women x 0.001"),
            card("Province gap", f"{province['Gap %']:.1f}%",
                 f"95% range {province['Gap low']:.1f} to {province['Gap high']:.1f}: {province['Result']}",
                 COLOURS[province["Result"]]),
            card("Largest district gap", top["District"],
                 f"{top['Gap %']:.1f}% ({top['Result']})", COLOURS[top["Result"]]),
            card("Districts with records", f"{len(districts)} of {len(DISTRICTS)}",
                 "others left out, not counted as zero"),
        ]
        return ui.div(*cards, style="display:flex;gap:12px;flex-wrap:wrap;margin:12px 0;")


    # ---- the gap bars ------------------------------------------------------
    @render.plot
    def gap_bars():
        t = current()
        districts = t[t["District"] != "Province"] if not t.empty else t
        fig, ax = plt.subplots(figsize=(8, 4.5))
        if districts.empty:
            ax.text(0.5, 0.5, "No records for this period yet", ha="center")
            ax.axis("off")
            return fig
        d = districts.iloc[::-1]                     # reverse so the largest gap is on top
        for _, r in d.iterrows():
            ax.barh(r["District"], r["Gap %"], color=COLOURS[r["Result"]], hatch=HATCH[r["Result"]],
                    edgecolor="black")
            ax.errorbar(r["Gap %"], r["District"],
                        xerr=[[r["Gap %"] - r["Gap low"]], [r["Gap high"] - r["Gap %"]]],
                        fmt="none", ecolor="#333", capsize=4)
        ax.axvline(0, color="black", linewidth=1)    # 0% gap = reporting matches expected
        ax.set_xlim(min(-10, d["Gap low"].min() - 5), 105)
        ax.set_xlabel("Reporting gap, % of expected cases missing (whiskers = 95% range)")
        keys = [Patch(facecolor=COLOURS[s], hatch=HATCH[s], edgecolor="black") for s in COLOURS]
        ax.legend(keys, COLOURS.keys(), loc="upper center", bbox_to_anchor=(0.5, -0.18),
                  ncol=3, frameon=False)
        fig.tight_layout()
        return fig

    # ---- the coloured table ------------------------------------------------
    @render.data_frame
    def district_table():
        t = current()
        if t.empty:
            return pd.DataFrame({"Message": ["No records for this period yet."]})
        shown = pd.DataFrame({
            "District": t["District"],
            "Reported": t["Reported"],
            "Expected": t["Expected"].round(1),
            "Gap %": t["Gap %"].round(1),
            "95% range": t["Gap low"].round(1).astype(str) + " to " + t["Gap high"].round(1).astype(str),
            "Result": t["Result"],
        })
        styles = [{"rows": [i], "style": {"background-color": PALE[r]}}
                  for i, r in enumerate(t["Result"])]
        styles.append({"rows": [len(t) - 1], "style": {"font-weight": "bold"}})   # province row
        return render.DataGrid(shown, width="100%", styles=styles)

    # ---- the entry form ------------------------------------------------------
    entry_feedback = reactive.value(None)

    @reactive.effect
    @reactive.event(input.entry_save)
    def _save_entry():
        try:
            new_id = add_record(DATA_FILE, {
                "district": input.entry_district(),
                "year": input.entry_year(),
                "facility": input.entry_facility(),
                "source": input.entry_source(),
                "first_time": input.entry_first_time(),
                "count": input.entry_count(),
            })
        except ValueError as error:                  # a rule was broken: nothing is saved
            entry_feedback.set(("danger", f"Not saved. {error}"))
        except OSError as error:
            entry_feedback.set(("danger", f"Not saved. {error}"))
        else:
            entry_feedback.set(("success", f"Saved as {new_id}. The tables and charts update within a second."))

    @render.ui
    def entry_message():
        feedback = entry_feedback()
        return message_box(*feedback) if feedback else None




app = App(app_ui, server)
