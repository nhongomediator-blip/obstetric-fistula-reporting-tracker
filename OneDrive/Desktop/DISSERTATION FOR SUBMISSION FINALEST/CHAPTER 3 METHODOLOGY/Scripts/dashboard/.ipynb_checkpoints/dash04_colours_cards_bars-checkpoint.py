"""
dash04_colours_cards_bars.py

DASHBOARD 04: adds three things to the dash03 dashboard.
  1. COLOURS      each row of the table is coloured by its verdict
  2. CARDS        five summary boxes for the province at the top of the page
  3. GAP BARS     one bar per district showing the gap, with its 95% range

NOTHING NEW IS CALCULATED HERE
Every number still comes from gap_table() in gap_functions.py (the same
Step 8 formula and exact Poisson interval). This step only changes how the
results LOOK, so the dashboard and the analysis can never disagree.

THE NEW IDEA IN THIS STEP: @reactive.calc
In dash03 the table function read the records and ran gap_table() itself.
Now the table, the cards and the bars all need the same result. A
@reactive.calc runs the calculation ONCE per year choice and shares it, so
the three outputs always show the same numbers and the work is not repeated.

COLOUR KEY (the verdict from gap_functions.verdict)
  red     Significant gap       the whole 95% range is below expected
  amber   Not distinguishable   the range includes expected, so chance cannot be ruled out
  green   Above expected        the whole 95% range is above expected
Colour is for reading the table quickly. Alerts come later (dash06).

HOW TO RUN (file sits in the same folder as gap_functions.py and data/)
    pip install shiny pandas scipy matplotlib
    shiny run --launch-browser dash04_colours_cards_bars.py
"""

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from shiny import App, reactive, render, ui

from gap_functions import DISTRICTS, gap_table

DATA_FILE = Path(__file__).parent / "data" / "entries.csv"
YEAR_CHOICES = ["All"] + [str(y) for y in range(2024, 2014, -1)]

# Strong colours for cards and bars, pale versions for table rows.
COLOURS = {"Significant gap": "#c0392b", "Not distinguishable": "#e0a800", "Above expected": "#2e7d32"}
PALE = {"Significant gap": "#f8d7da", "Not distinguishable": "#fff3cd", "Above expected": "#d4edda"}


def card(title, value, note="", colour="#34495e"):
    """One summary box: small title, big number, small note, coloured left edge."""
    return ui.div(
        ui.div(title, style="font-size:0.85rem;color:#555;"),
        ui.div(value, style=f"font-size:1.8rem;font-weight:700;color:{colour};"),
        ui.div(note, style="font-size:0.8rem;color:#777;"),
        style=(f"flex:1;min-width:180px;border:1px solid #ddd;border-left:6px solid {colour};"
               "border-radius:6px;padding:10px 14px;background:#fff;"),
    )


# ----------------------------------------------------------------------------
# PART 1: WHAT THE PAGE LOOKS LIKE
# ----------------------------------------------------------------------------
app_ui = ui.page_fluid(
    ui.h2("Obstetric Fistula Reporting Tracker - Manicaland"),
    ui.p("Reporting gap = the share of expected cases that never reach the records."),
    ui.input_select("year", "Year", YEAR_CHOICES, selected="All"),
    ui.output_ui("summary_cards"),
    ui.h4("Gap by district"),
    ui.output_plot("gap_bars", height="380px"),
    ui.h4("Reporting gap table"),
    ui.output_data_frame("district_table"),
    ui.p("Districts with no records for the chosen period are left out. They are missing, "
         "never counted as zero.", style="color:#777;font-size:0.85rem;margin-top:8px;"),
)


# ----------------------------------------------------------------------------
# PART 2: WHAT THE PAGE DOES
# ----------------------------------------------------------------------------
def server(input, output, session):

    @reactive.calc
    def current():
        """The one shared calculation: read the records, run gap_table()."""
        entries = pd.read_csv(DATA_FILE)
        return gap_table(entries, year=input.year())

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
        left = (d["Gap %"] - d["Gap low"]).values    # how far the whisker reaches left
        right = (d["Gap high"] - d["Gap %"]).values  # ...and right
        ax.barh(d["District"], d["Gap %"], color=[COLOURS[r] for r in d["Result"]],
                xerr=[left, right], capsize=4, ecolor="#333")
        ax.axvline(0, color="black", linewidth=1)    # 0% gap = reporting matches expected
        ax.set_xlim(min(-10, d["Gap low"].min() - 5), 105)
        ax.set_xlabel("Reporting gap, % of expected cases missing (whiskers = 95% range)")
        keys = [plt.Rectangle((0, 0), 1, 1, color=c) for c in COLOURS.values()]
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


app = App(app_ui, server)
