LIVE DASHBOARD (STEP 12)
========================
The dashboard tracks reported against expected obstetric fistula cases for each district
of Manicaland and shows the reporting gap with a 95% interval. It uses the same
expected-case formula and confidence interval as Step 8 of the analysis pipeline. This
folder is separate from the pipeline (step01 to step13); do not add these scripts to the
pipeline runner.

FILES
  gap_functions.py                  the calculations (dash01 and dash02, packaged)
  dashboard_data.py                 reads, checks, saves, imports and removes records
  data/entries.csv                  the records (the 31 study records are s000 to s030)
  data/manicaland_study_area.geojson  the district boundaries (copy of the Step 1 output; the map
                                    reads it with shapely, so no geopandas or PROJ is needed)
  dash_tests.py                     the automatic tests 
  make_offline_snapshot.py          builds dashboard_offline.html, the read-only copy for examiners
  requirements.txt                  the software the dashboard needs
  start_dashboard.bat               double-click start-up for Windows

BUILD ORDER (each script adds one capability to the one before)
  dash01_load_and_gap.py            load the data and calculate the gap (plain Python)
  dash02_confidence_intervals.py    test whether each gap is real or chance (exact Poisson)
  dash03_first_dashboard.py         first dashboard: table with a year filter (Shiny)
  dash04_colours_cards_bars.py      colours, summary cards and gap bars
  dash05_entering_cases.py          tabs, the entry form, rules, saving, live update
  dash06_alerts.py                  alert banner, ranked list, small-count note
  dash07_district_map.py            district map (colour and pattern)
  Obstetric_Fistula_Reporting_Tracker_final_dashboard.py      import a CSV file, list all records, remove a mistake

HOW TO RUN
  pip install -r requirements.txt
  python dash_tests.py                                   (all checks should pass)
  shiny run --launch-browser dash08_import_and_records.py   (stop with Ctrl+C)
Or double-click start_dashboard.bat.

Run dash04 to the final dashboard one at a time to test each stage. The top of each script says what
it adds and how to test it. dash_tests.py works on a temporary copy of the records, so it
never changes data/entries.csv. Testing in the browser does add rows to data/entries.csv;
remove them afterwards on the "All records" tab (final dashboard).

OFFLINE COPY FOR EXAMINERS (no installation needed)
  python make_offline_snapshot.py
makes dashboard_offline.html in this folder. It opens by double-clicking in any web browser, works
without internet, and shows the year filter, alerts, cards, bars, table, map and the list of records.
It is a read-only snapshot taken when the script is run, so run the script again after adding records.


A CD is read-only, so copy this folder to the computer's hard drive before adding records.
