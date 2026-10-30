"""
dash08_import_and_records.py

DASHBOARD 08: importing camp CSV files and the records list. This is the finished
dashboard. It adds two tabs to dash07: "Import records" and "All records".

IMPORTING A FILE
A CSV file with the columns district, year, first_time and count (facility and source
are optional) can be imported. A blank template can be downloaded from the tab. Every
row goes through the same rules as the entry form:
  - rows that break a rule are rejected, and the result lists the file row number and
    the reason, so the file can be fixed and imported again
  - rows already stored (or repeated inside the file) are skipped as duplicates, so
    importing the same file twice cannot double the counts
  - the valid rows are saved with the date of entry and the record numbers i001, i002 ...

ALL RECORDS AND CORRECTIONS
The "All records" tab lists every record with a filter box on each column. A mistaken
entry can be removed there. Study records (s000 to s030) are protected and cannot be
removed; only records added through the form (d) or by import (i) can.

HOW TO TEST THIS STAGE
  1. Download the template, change the counts, save it and import it. The Overview
     should change within a second.
  2. Import the same file again: all rows should be skipped as duplicates.
  3. Put a year of 2030 in one row: that row should be rejected with its row number.
  4. On "All records", remove one of your test records and check the Overview.
  5. Run dash_tests.py for the full set of checks in Section 3.3.7.

FILES NEEDED IN THE SAME FOLDER
    gap_functions.py          the calculations (dash01 and dash02, packaged)
    dashboard_data.py         reads, checks and saves the records
    data/entries.csv          the records
    data/manicaland_study_area.geojson   the district boundaries (Step 1 output)

HOW TO RUN
    pip install -r requirements.txt
    shiny run --launch-browser dash08_import_and_records.py
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
            ui.output_ui("alerts"),
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
        ui.nav_panel(
            "Map",
            ui.output_plot("map_plot", height="620px"),
            ui.p("Colour and pattern show the status of each district; the percentage is its reporting "
                 "gap. Districts with no records in the chosen period are grey and are not shown as zero.",
                 style="color:#777;font-size:0.85rem;"),
        ),
        ui.nav_panel(
            "Import records",
            ui.layout_columns(
                ui.card(
                    ui.card_header("Import a CSV file"),
                    ui.p("The file needs the columns district, year, first_time and count. "
                         "The columns facility and source are optional."),
                    ui.input_file("import_file", "Choose a CSV file", accept=[".csv"], multiple=False),
                    ui.input_action_button("import_go", "Import", class_="btn-primary"),
                    ui.download_button("template", "Download a blank template"),
                ),
                ui.card(ui.card_header("Import result"), ui.output_ui("import_result")),
                col_widths=[5, 7],
            ),
        ),
        ui.nav_panel(
            "All records",
            ui.card(ui.card_header("All records"), ui.output_data_frame("records_table")),
            ui.card(
                ui.card_header("Correct a mistaken entry"),
                ui.p("Study records (s000 to s030) are fixed. Records added through the form (d) or "
                     "by import (i) can be removed here."),
                ui.input_select("delete_id", "Record to remove", choices=[]),
                ui.input_action_button("delete_go", "Remove record", class_="btn-outline-danger"),
                ui.output_ui("delete_message"),
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

    # ---- the alert banner and ranked list ---------------------------------
    @render.ui
    def alerts():
        t = current()
        if t.empty:
            return message_box("secondary", "No records for this period yet, so no alerts can be raised.")
        districts = t[t["District"] != "Province"]
        flagged = districts[districts["Result"] == "Significant gap"]    # largest gap first
        above = districts[districts["Result"] == "Above expected"]
        absent = [d for d in DISTRICTS if d not in set(districts["District"])]

        parts = []
        if flagged.empty:
            parts.append(ui.tags.strong("No district shows a significant reporting gap in this period."))
        else:
            parts.append(ui.tags.strong(
                f"ALERT: {len(flagged)} district(s) with significantly low reporting "
                "(ranked by size of gap)"))
            parts.append(ui.tags.ol(*[
                ui.tags.li(
                    f"{r['District']}: gap {r['Gap %']:.1f}% (95% range {r['Gap low']:.1f}% to "
                    f"{r['Gap high']:.1f}%); {int(r['Reported'])} reported of {r['Expected']:.1f} expected")
                for _, r in flagged.iterrows()
            ]))
        if not above.empty:
            parts.append(ui.p("Above expected: " + ", ".join(above["District"]) + ".", style="margin:4px 0;"))
        if absent:
            parts.append(ui.p("No records in this period (not shown as zero): " + ", ".join(absent) + ".",
                              style="margin:4px 0;"))
        parts.append(ui.p(SMALL_COUNT_NOTE, style="margin:4px 0;font-size:0.85rem;"))
        return ui.div(*parts, class_="alert alert-danger" if not flagged.empty else "alert alert-info")

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

    # ---- the district map ----------------------------------------------------
    @render.plot
    def map_plot():
        fig, ax = plt.subplots(figsize=(7, 7))
        ax.set_axis_off()
        try:
            import geopandas as gpd
            boundaries = gpd.read_file(BOUNDARY_FILE)
        except Exception as error:                   # no geopandas, or the boundary file is missing
            ax.text(0.5, 0.5, f"The map could not be drawn.\n{error}", ha="center", va="center",
                    wrap=True, transform=ax.transAxes)
            return fig

        t = current()
        status, gap = {}, {}
        if not t.empty:
            for _, r in t[t["District"] != "Province"].iterrows():
                status[r["District"]] = r["Result"]
                gap[r["District"]] = r["Gap %"]
        boundaries["status"] = boundaries[DISTRICT_FIELD].map(status).fillna("No records")

        for name, colour in {**COLOURS, "No records": "#d9d9d9"}.items():
            part = boundaries[boundaries["status"] == name]
            if not part.empty:
                part.plot(ax=ax, facecolor=colour, edgecolor="black", linewidth=1,
                          hatch=HATCH.get(name, "xx"))
        for _, row in boundaries.iterrows():
            point = row.geometry.representative_point()
            name = row[DISTRICT_FIELD]
            label = f"{name}\n{gap[name]:.0f}%" if name in gap else f"{name}\nno records"
            ax.annotate(label, (point.x, point.y), ha="center", va="center", fontsize=9,
                        bbox=dict(boxstyle="round,pad=0.2", facecolor="white", alpha=0.8, edgecolor="none"))
        keys = [Patch(facecolor=COLOURS[s], hatch=HATCH[s], edgecolor="black") for s in COLOURS]
        keys.append(Patch(facecolor="#d9d9d9", hatch="xx", edgecolor="black"))
        ax.legend(keys, list(COLOURS) + ["No records"], loc="lower center",
                  bbox_to_anchor=(0.5, -0.08), ncol=4, frameon=False, fontsize=8)
        ax.set_title("Reporting gap by district, " +
                     ("whole period" if input.year() == "All" else input.year()))
        fig.tight_layout()
        return fig

    # ---- importing a file ------------------------------------------------------
    import_feedback = reactive.value(None)

    @reactive.effect
    @reactive.event(input.import_go)
    def _import_file():
        files = input.import_file()
        if not files:
            import_feedback.set(("warning", "Choose a CSV file first.", None))
            return
        try:
            uploaded = pd.read_csv(files[0]["datapath"], dtype=str, keep_default_na=False)
            result = import_records(DATA_FILE, uploaded)
        except (ValueError, OSError, pd.errors.ParserError) as error:
            import_feedback.set(("danger", f"Nothing was imported. {error}", None))
            return
        kind = "success" if result["saved"] and result["rejected"].empty else "warning"
        text = (f"{result['saved']} record(s) saved, {result['duplicates']} duplicate(s) skipped, "
                f"{len(result['rejected'])} row(s) rejected.")
        import_feedback.set((kind, text, result["rejected"]))

    @render.ui
    def import_result():
        feedback = import_feedback()
        if not feedback:
            return ui.p("No file imported yet.", style="color:#777;")
        kind, text, rejected = feedback
        parts = [message_box(kind, text)]
        if rejected is not None and not rejected.empty:
            parts.append(ui.p("Rejected rows (fix these in the file and import again):"))
            parts.append(ui.HTML(rejected.to_html(index=False, classes="table table-sm", border=0)))
        return ui.div(*parts)

    @render.download(filename="import_template.csv")
    def template():
        yield TEMPLATE_TEXT

    # ---- the list of all records and corrections ---------------------------------
    @render.data_frame
    def records_table():
        return render.DataGrid(records(), filters=True, width="100%")

    @reactive.effect
    def _refresh_delete_choices():
        data = records()
        choices = {
            row["id"]: f"{row['id']}: {row['district']} {row['year']}, {row['count']} ({row['first_time']})"
            for _, row in data.iterrows() if row["id"] in set(deletable_ids(data))
        }
        ui.update_select("delete_id", choices=choices)

    delete_feedback = reactive.value(None)

    @reactive.effect
    @reactive.event(input.delete_go)
    def _delete_entry():
        chosen = input.delete_id()
        if not chosen:
            delete_feedback.set(("warning", "There is no record to remove."))
            return
        try:
            delete_record(DATA_FILE, chosen)
        except (ValueError, OSError) as error:
            delete_feedback.set(("danger", f"Not removed. {error}"))
        else:
            delete_feedback.set(("success", f"Removed {chosen}."))

    @render.ui
    def delete_message():
        feedback = delete_feedback()
        return message_box(*feedback) if feedback else None


app = App(app_ui, server)
