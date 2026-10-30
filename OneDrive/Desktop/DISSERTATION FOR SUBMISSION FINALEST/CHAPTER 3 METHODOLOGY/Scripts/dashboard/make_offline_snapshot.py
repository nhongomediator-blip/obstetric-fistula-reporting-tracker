"""
make_offline_snapshot.py

THE OFFLINE COPY OF THE DASHBOARD (Section 3.3.8 of Chapter 3)

WHAT IT MAKES
One file, dashboard_offline.html, that opens by double-clicking it in any web browser. It needs no
Python, no installation and no internet connection, so examiners can use it straight from the CD.
It holds a snapshot of the dashboard taken at the moment this script is run:
  - the Year drop-down (whole period, or any single year from 2015 to 2024)
  - the alert banner and ranked list, the five summary cards, the gap bars and the coloured table
  - the district map (colour and pattern, with each district's name and gap percentage)
  - a list of all the records behind the figures, with a filter box
The page can be printed; the tabs are laid out one after another on paper.

WHAT IT CANNOT DO
It is read-only. New records cannot be added to it, because a web page on a disc has nowhere to save
them. To add records, use the full dashboard (dash08_import_and_records.py), then run this script
again to make a fresh snapshot.

NOTHING IS CALCULATED IN THE BROWSER
Every number is worked out here by gap_table() in gap_functions.py, the same function that the
dashboard and the tests use, and is written into the page. The page only chooses which period to
show. So the offline copy cannot disagree with the dashboard or with Step 8.

HOW TO RUN (in the dashboard folder, next to gap_functions.py and the data folder)
    python make_offline_snapshot.py
Then open dashboard_offline.html. Needs data/entries.csv and data/manicaland_study_area.geojson.
"""

import json
import math
from datetime import date
from pathlib import Path

from shapely.geometry import shape

from gap_functions import DISTRICTS, gap_table
from dashboard_data import YEAR_MAX, YEAR_MIN, load_entries

HERE = Path(__file__).parent
ENTRIES_FILE = HERE / "data" / "entries.csv"
BOUNDARY_FILE = HERE / "data" / "manicaland_study_area.geojson"
DISTRICT_FIELD = "district"                        # name column in the boundary file
OUTPUT_FILE = HERE / "dashboard_offline.html"

MAP_WIDTH = 600        # width of the map drawing, in screen units
MAP_MARGIN = 12


# ---------------------------------------------------------------- the numbers
def period_rows(entries, key):
    """The dashboard table for one period, as plain lists the page can use."""
    table = gap_table(entries, year=key)
    if table.empty:
        return []
    return [
        {
            "district": row["District"],
            "reported": int(row["Reported"]),
            "expected": round(float(row["Expected"]), 4),
            "gap": round(float(row["Gap %"]), 4),
            "low": round(float(row["Gap low"]), 4),
            "high": round(float(row["Gap high"]), 4),
            "result": row["Result"],
        }
        for _, row in table.iterrows()
    ]


# ------------------------------------------------------------------- the map
def build_map(path, field):
    """Turns the boundary file into drawing paths. Only the standard library and shapely are used."""
    with open(path, encoding="utf-8") as file:
        features = json.load(file)["features"]
    shapes = [(str(f["properties"][field]), shape(f["geometry"])) for f in features]
    if not shapes:
        raise ValueError("The boundary file contains no districts.")

    west = min(g.bounds[0] for _, g in shapes)
    south = min(g.bounds[1] for _, g in shapes)
    east = max(g.bounds[2] for _, g in shapes)
    north = max(g.bounds[3] for _, g in shapes)
    in_degrees = max(abs(west), abs(east), abs(south), abs(north)) <= 360
    squeeze = math.cos(math.radians((south + north) / 2)) if in_degrees else 1.0   # keeps shapes true
    scale = (MAP_WIDTH - 2 * MAP_MARGIN) / ((east - west) * squeeze)
    height = (north - south) * scale + 2 * MAP_MARGIN

    def project(x, y):
        return ((x - west) * squeeze * scale + MAP_MARGIN, (north - y) * scale + MAP_MARGIN)

    districts = []
    for name, geometry in shapes:
        polygons = list(geometry.geoms) if hasattr(geometry, "geoms") else [geometry]
        parts = []
        for polygon in polygons:
            for ring in [polygon.exterior, *polygon.interiors]:
                points = [project(x, y) for x, y in ring.coords]
                parts.append("M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in points) + "Z")
        label = geometry.representative_point()
        lx, ly = project(label.x, label.y)
        districts.append({"name": name, "path": "".join(parts), "lx": round(lx, 1), "ly": round(ly, 1)})
    return {"viewBox": f"0 0 {MAP_WIDTH} {height:.0f}", "districts": districts}


# ------------------------------------------------------------------ the page
PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Obstetric fistula reporting tracker: Manicaland (offline copy)</title>
<style>
  :root {
    --ink: #1c2530; --muted: #5d6875; --line: #d5dae0; --paper: #ffffff; --wash: #f3f5f7;
    --brand: #23415a;
    --red: #c0392b; --red-pale: #f8d7da; --amber: #e0a800; --amber-pale: #fff3cd;
    --green: #2e7d32; --green-pale: #d4edda; --grey-pale: #e4e6e9;
  }
  * { box-sizing: border-box; }
  body { margin: 0; color: var(--ink); background: var(--paper); line-height: 1.5;
         font-family: "Segoe UI", system-ui, -apple-system, "Helvetica Neue", Arial, sans-serif; }
  header { padding: 22px 24px 14px; border-bottom: 3px solid var(--brand); }
  h1 { margin: 0 0 4px; font: 600 1.7rem/1.2 Georgia, "Times New Roman", serif; color: var(--brand); }
  header p { margin: 0; color: var(--muted); }
  main { max-width: 1040px; margin: 0 auto; padding: 18px 24px 40px; }
  .copy-note { background: var(--wash); border-left: 5px solid var(--brand); padding: 10px 14px;
               font-size: 0.9rem; margin-bottom: 16px; }
  .controls { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 12px; }
  label { font-weight: 600; }
  select, input[type=search] { font: inherit; padding: 6px 10px; border: 1px solid #9aa4af; border-radius: 4px;
                                background: #fff; color: var(--ink); }
  .tabs { display: flex; gap: 2px; border-bottom: 1px solid var(--line); margin: 6px 0 18px; }
  .tabs button { font: inherit; padding: 9px 16px; border: 1px solid transparent; border-bottom: none;
                 background: none; color: #1565a8; cursor: pointer; border-radius: 4px 4px 0 0; }
  .tabs button[aria-selected=true] { color: var(--ink); border-color: var(--line); background: var(--paper);
                                      margin-bottom: -1px; font-weight: 600; }
  :focus-visible { outline: 3px solid #1565a8; outline-offset: 2px; }
  h2 { font: 600 1.15rem/1.3 Georgia, "Times New Roman", serif; margin: 26px 0 8px; color: var(--brand); }
  .alert { padding: 12px 16px; border-radius: 5px; margin: 0 0 14px; border: 1px solid; }
  .alert.danger { background: var(--red-pale); border-color: #e6a5ab; }
  .alert.info { background: #e3f1f8; border-color: #a9d3e6; }
  .alert.secondary { background: var(--wash); border-color: var(--line); }
  .alert ol { margin: 8px 0 8px 20px; padding: 0; }
  .alert p { margin: 4px 0; }
  .small { font-size: 0.85rem; }
  .muted { color: var(--muted); }
  .cards { display: flex; flex-wrap: wrap; gap: 12px; margin: 14px 0; }
  .card { flex: 1 1 170px; border: 1px solid var(--line); border-left: 6px solid #34495e; border-radius: 6px;
          padding: 10px 14px; background: #fff; }
  .card .t { font-size: 0.85rem; color: var(--muted); }
  .card .v { font-size: 1.7rem; font-weight: 700; line-height: 1.25; }
  .card .n { font-size: 0.8rem; color: #6b7480; }
  .scroll { overflow-x: auto; }
  table { border-collapse: collapse; width: 100%; font-size: 0.95rem; }
  th, td { padding: 7px 10px; text-align: left; border-bottom: 1px solid var(--line); }
  th { background: var(--wash); font-weight: 600; white-space: nowrap; }
  td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
  tr.province td { font-weight: 700; }
  svg { max-width: 100%; height: auto; }
  .legend { display: flex; flex-wrap: wrap; gap: 8px 18px; margin: 8px 0 0; font-size: 0.85rem; }
  .legend span { display: inline-flex; align-items: center; gap: 6px; }
  .map-wrap { max-width: 560px; margin: 0 auto; }
  .map-label, .map-halo { font: 600 12px "Segoe UI", system-ui, Arial, sans-serif; text-anchor: middle; }
  .map-label { fill: #111; }
  .map-halo { fill: none; stroke: #fff; stroke-width: 4px; stroke-linejoin: round; }
  .foot { margin-top: 30px; font-size: 0.82rem; color: var(--muted); border-top: 1px solid var(--line); padding-top: 12px; }
  .print { font: inherit; padding: 6px 12px; border: 1px solid #9aa4af; background: #fff; border-radius: 4px; cursor: pointer; }
  @media print {
    .tabs, .controls, .print { display: none; }
    [role=tabpanel][hidden] { display: block; }
    [role=tabpanel] { break-inside: avoid-page; }
    header { border-bottom-color: #000; }
  }
</style>
</head>
<body>
<svg width="0" height="0" style="position:absolute" aria-hidden="true" focusable="false">
  <defs>
    <pattern id="p-sig" width="8" height="8" patternUnits="userSpaceOnUse">
      <rect width="8" height="8" fill="#c0392b"/><path d="M-1,1 l2,-2 M0,8 l8,-8 M7,9 l2,-2" stroke="#3b0f0a" stroke-width="1.4"/>
    </pattern>
    <pattern id="p-nd" width="7" height="7" patternUnits="userSpaceOnUse">
      <rect width="7" height="7" fill="#e0a800"/><circle cx="3.5" cy="3.5" r="1.1" fill="#4a3800"/>
    </pattern>
    <pattern id="p-above" width="8" height="8" patternUnits="userSpaceOnUse">
      <rect width="8" height="8" fill="#2e7d32"/>
    </pattern>
    <pattern id="p-none" width="8" height="8" patternUnits="userSpaceOnUse">
      <rect width="8" height="8" fill="#d9d9d9"/><path d="M0,0 L8,8 M8,0 L0,8" stroke="#8a8a8a" stroke-width="0.9"/>
    </pattern>
  </defs>
</svg>

<header>
  <h1>Obstetric fistula reporting tracker: Manicaland Province</h1>
  <p>Reporting gap = the share of expected cases that never reach the records.</p>
</header>

<main>
  <div class="copy-note" id="copy-note"></div>

  <div class="controls">
    <label for="year">Year</label>
    <select id="year"></select>
    <button class="print" type="button" onclick="window.print()">Print this page</button>
  </div>

  <div class="tabs" role="tablist" aria-label="Sections">
    <button type="button" role="tab" id="tab-overview" aria-controls="panel-overview" aria-selected="true">Overview</button>
    <button type="button" role="tab" id="tab-map" aria-controls="panel-map" aria-selected="false">Map</button>
    <button type="button" role="tab" id="tab-records" aria-controls="panel-records" aria-selected="false">All records</button>
  </div>

  <section role="tabpanel" id="panel-overview" aria-labelledby="tab-overview">
    <div id="alerts"></div>
    <div id="cards" class="cards"></div>
    <h2>Gap by district</h2>
    <div id="bars"></div>
    <div class="legend" id="legend-bars"></div>
    <h2>Reporting gap table</h2>
    <div class="scroll" id="table"></div>
    <p class="small muted">Districts with no records for the chosen period are left out. They are missing, never counted as zero.</p>
  </section>

  <section role="tabpanel" id="panel-map" aria-labelledby="tab-map" hidden>
    <h2 id="map-title">Reporting gap by district</h2>
    <div class="map-wrap" id="map"></div>
    <div class="legend" id="legend-map"></div>
    <p class="small muted">Colour and pattern show the status of each district; the percentage is its reporting gap. Districts with no records in the chosen period are grey with crosses and are not shown as zero.</p>
  </section>

  <section role="tabpanel" id="panel-records" aria-labelledby="tab-records" hidden>
    <h2>All records</h2>
    <p class="small muted">The records behind every figure. Only first-time patients count as reported cases. Only aggregate counts are stored, with no names or personal identifiers.</p>
    <p><label for="filter">Filter </label><input type="search" id="filter" placeholder="Type a district, year or source"></p>
    <p class="small" id="records-count"></p>
    <div class="scroll" id="records"></div>
  </section>

  <div class="foot" id="foot"></div>
</main>

<script id="data" type="application/json">__DATA__</script>
<script>
(function () {
  "use strict";
  var DATA = JSON.parse(document.getElementById("data").textContent);
  var STATUS = {
    "Significant gap":     { colour: "#c0392b", pale: "#f8d7da", pattern: "p-sig" },
    "Not distinguishable": { colour: "#e0a800", pale: "#fff3cd", pattern: "p-nd" },
    "Above expected":      { colour: "#2e7d32", pale: "#d4edda", pattern: "p-above" }
  };
  var STATUS_NAMES = ["Significant gap", "Not distinguishable", "Above expected"];
  var SMALL_COUNT_NOTE = "Districts with few records have wide intervals, so they are flagged less often. " +
                         "A district that is not flagged is not proof that its reporting is good.";

  function $(id) { return document.getElementById(id); }
  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; });
  }
  function f1(x) { return Number(x).toFixed(1); }
  function split(rows) {
    return { districts: rows.filter(function (r) { return r.district !== "Province"; }),
             province: rows.filter(function (r) { return r.district === "Province"; })[0] };
  }
  function current() {
    var key = $("year").value;
    return { key: key, rows: DATA.periods[key] || [] };
  }
  function colour(result) { return STATUS[result].colour; }

  /* ---- header, note, footer ------------------------------------------------ */
  $("copy-note").innerHTML =
    "<strong>Offline copy.</strong> This is a read-only snapshot made on " + esc(DATA.generated) + " from " +
    DATA.records.length + " records. It cannot take new records; the full dashboard can. " +
    "Every figure was calculated by the same code as the analysis (Step 8), and the page only chooses which period to show.";
  $("foot").innerHTML =
    "<p><strong>How the figures are worked out.</strong> Expected cases = adult women projected to the year x 0.001; " +
    "for the whole period the " + DATA.reference_year + " population is used. Reported cases are first-time patients only. " +
    "The gap is 1 minus reported divided by expected, with an exact Poisson 95% interval. A district is flagged " +
    "&ldquo;Significant gap&rdquo; when the whole interval for its reported cases lies below expected, " +
    "&ldquo;Above expected&rdquo; when it lies above, and &ldquo;Not distinguishable&rdquo; otherwise. " +
    "The province row adds reported and expected cases first and then works out the gap.</p>";

  /* ---- year list --------------------------------------------------------------- */
  var select = $("year");
  DATA.keys.forEach(function (k) {
    var o = document.createElement("option");
    o.value = k; o.textContent = k === "All" ? "All years (whole period)" : k;
    select.appendChild(o);
  });

  /* ---- legend swatches -------------------------------------------------------- */
  function legendHtml(includeNone) {
    var items = STATUS_NAMES.map(function (n) {
      return '<span><svg width="26" height="14" aria-hidden="true"><rect width="26" height="14" fill="url(#' +
             STATUS[n].pattern + ')" stroke="#222"/></svg>' + n + "</span>";
    });
    if (includeNone) {
      items.push('<span><svg width="26" height="14" aria-hidden="true"><rect width="26" height="14" fill="url(#p-none)" stroke="#222"/></svg>No records</span>');
    }
    return items.join("");
  }
  $("legend-bars").innerHTML = legendHtml(false);
  $("legend-map").innerHTML = legendHtml(true);

  /* ---- alert banner ------------------------------------------------------------ */
  function renderAlerts(c) {
    var box = $("alerts");
    if (!c.rows.length) {
      box.innerHTML = '<div class="alert secondary">No records for this period yet, so no alerts can be raised.</div>';
      return;
    }
    var d = split(c.rows).districts;
    var flagged = d.filter(function (r) { return r.result === "Significant gap"; });
    var above = d.filter(function (r) { return r.result === "Above expected"; });
    var present = d.map(function (r) { return r.district; });
    var absent = DATA.districts.filter(function (n) { return present.indexOf(n) < 0; });
    var html = "";
    if (!flagged.length) {
      html += "<strong>No district shows a significant reporting gap in this period.</strong>";
    } else {
      html += "<strong>ALERT: " + flagged.length + " district(s) with significantly low reporting (ranked by size of gap)</strong><ol>";
      flagged.forEach(function (r) {
        html += "<li>" + esc(r.district) + ": gap " + f1(r.gap) + "% (95% range " + f1(r.low) + "% to " + f1(r.high) +
                "%); " + r.reported + " reported of " + f1(r.expected) + " expected</li>";
      });
      html += "</ol>";
    }
    if (above.length) html += "<p>Above expected: " + above.map(function (r) { return esc(r.district); }).join(", ") + ".</p>";
    if (absent.length) html += "<p>No records in this period (not shown as zero): " + absent.map(esc).join(", ") + ".</p>";
    html += '<p class="small">' + SMALL_COUNT_NOTE + "</p>";
    box.innerHTML = '<div class="alert ' + (flagged.length ? "danger" : "info") + '">' + html + "</div>";
  }

  /* ---- summary cards ------------------------------------------------------------ */
  function card(title, value, note, colourCode) {
    return '<div class="card" style="border-left-color:' + (colourCode || "#34495e") + '"><div class="t">' + esc(title) +
           '</div><div class="v" style="color:' + (colourCode || "inherit") + '">' + esc(value) +
           '</div><div class="n">' + esc(note) + "</div></div>";
  }
  function renderCards(c) {
    if (!c.rows.length) { $("cards").innerHTML = "<p>No records for this period yet.</p>"; return; }
    var s = split(c.rows), p = s.province, top = s.districts[0];
    $("cards").innerHTML =
      card("Province reported", String(p.reported), "first-time cases in the records") +
      card("Province expected", f1(p.expected), "adult women x 0.001") +
      card("Province gap", f1(p.gap) + "%", "95% range " + f1(p.low) + " to " + f1(p.high) + ": " + p.result, colour(p.result)) +
      card("Largest district gap", top.district, f1(top.gap) + "% (" + top.result + ")", colour(top.result)) +
      card("Districts with records", s.districts.length + " of " + DATA.districts.length, "others left out, not counted as zero");
  }

  /* ---- gap bars ------------------------------------------------------------------ */
  function renderBars(c) {
    var box = $("bars");
    var d = c.rows.length ? split(c.rows).districts : [];
    if (!d.length) { box.innerHTML = '<p class="muted">No records for this period yet.</p>'; return; }
    var W = 760, left = 120, right = 60, rowH = 38, top = 14, bottom = 52;
    var H = top + rowH * d.length + bottom;
    var lo = Math.min(-10, Math.min.apply(null, d.map(function (r) { return r.low; })) - 5), hi = 105;
    function x(v) { return left + (v - lo) / (hi - lo) * (W - left - right); }
    var s = '<svg viewBox="0 0 ' + W + " " + H + '" role="img" aria-label="Reporting gap by district with 95% ranges">';
    for (var t = Math.ceil(lo / 20) * 20; t <= 100; t += 20) {
      s += '<line x1="' + x(t) + '" y1="' + top + '" x2="' + x(t) + '" y2="' + (H - bottom) + '" stroke="#e1e5ea"/>' +
           '<text x="' + x(t) + '" y="' + (H - bottom + 16) + '" font-size="11" text-anchor="middle" fill="#5d6875">' + t + "%</text>";
    }
    d.forEach(function (r, i) {
      var y = top + i * rowH, mid = y + rowH / 2, x0 = x(0), x1 = x(r.gap);
      s += '<text x="' + (left - 10) + '" y="' + (mid + 4) + '" font-size="13" text-anchor="end" fill="#1c2530">' + esc(r.district) + "</text>";
      s += '<rect x="' + Math.min(x0, x1) + '" y="' + (y + 6) + '" width="' + Math.abs(x1 - x0) + '" height="' + (rowH - 12) +
           '" fill="url(#' + STATUS[r.result].pattern + ')" stroke="#222"/>';
      s += '<line x1="' + x(r.low) + '" y1="' + mid + '" x2="' + x(r.high) + '" y2="' + mid + '" stroke="#fff" stroke-width="5"/>' +
           '<line x1="' + x(r.low) + '" y1="' + (mid - 7) + '" x2="' + x(r.low) + '" y2="' + (mid + 7) + '" stroke="#fff" stroke-width="5"/>' +
           '<line x1="' + x(r.high) + '" y1="' + (mid - 7) + '" x2="' + x(r.high) + '" y2="' + (mid + 7) + '" stroke="#fff" stroke-width="5"/>' +
           '<line x1="' + x(r.low) + '" y1="' + mid + '" x2="' + x(r.high) + '" y2="' + mid + '" stroke="#111" stroke-width="1.6"/>' +
           '<line x1="' + x(r.low) + '" y1="' + (mid - 6) + '" x2="' + x(r.low) + '" y2="' + (mid + 6) + '" stroke="#111" stroke-width="1.6"/>' +
           '<line x1="' + x(r.high) + '" y1="' + (mid - 6) + '" x2="' + x(r.high) + '" y2="' + (mid + 6) + '" stroke="#111" stroke-width="1.6"/>';
      s += '<text x="' + (x(r.high) + 8) + '" y="' + (mid + 4) + '" font-size="12" fill="#1c2530">' + f1(r.gap) + "%</text>";
    });
    s += '<line x1="' + x(0) + '" y1="' + top + '" x2="' + x(0) + '" y2="' + (H - bottom) + '" stroke="#111" stroke-width="1.4"/>';
    s += '<text x="' + ((left + W - right) / 2) + '" y="' + (H - 12) + '" font-size="12" text-anchor="middle" fill="#5d6875">' +
         "Reporting gap, % of expected cases missing (whiskers = 95% range)</text></svg>";
    box.innerHTML = s;
  }

  /* ---- table ------------------------------------------------------------------------- */
  function renderTable(c) {
    var box = $("table");
    if (!c.rows.length) { box.innerHTML = '<p class="muted">No records for this period yet.</p>'; return; }
    var html = '<table><thead><tr><th>District</th><th class="num">Reported</th><th class="num">Expected</th>' +
               '<th class="num">Gap %</th><th>95% range</th><th>Result</th></tr></thead><tbody>';
    c.rows.forEach(function (r) {
      html += '<tr class="' + (r.district === "Province" ? "province" : "") + '" style="background:' + STATUS[r.result].pale + '">' +
              "<td>" + esc(r.district) + '</td><td class="num">' + r.reported + '</td><td class="num">' + f1(r.expected) +
              '</td><td class="num">' + f1(r.gap) + "</td><td>" + f1(r.low) + " to " + f1(r.high) + "</td><td>" + esc(r.result) + "</td></tr>";
    });
    box.innerHTML = html + "</tbody></table>";
  }

  /* ---- map ----------------------------------------------------------------------------- */
  function renderMap(c) {
    var byName = {};
    c.rows.forEach(function (r) { if (r.district !== "Province") byName[r.district] = r; });
    var s = '<svg viewBox="' + DATA.map.viewBox + '" role="img" aria-label="Map of reporting gap by district">';
    DATA.map.districts.forEach(function (m) {
      var r = byName[m.name];
      s += '<path d="' + m.path + '" fill="url(#' + (r ? STATUS[r.result].pattern : "p-none") +
           ')" fill-rule="evenodd" stroke="#111" stroke-width="1.2" stroke-linejoin="round"/>';
    });
    DATA.map.districts.forEach(function (m) {
      var r = byName[m.name];
      var second = r ? Math.round(r.gap) + "%" : "no records";
      ["map-halo", "map-label"].forEach(function (cls) {
        s += '<text class="' + cls + '" x="' + m.lx + '" y="' + (m.ly - 2) + '">' + esc(m.name) + "</text>" +
             '<text class="' + cls + '" x="' + m.lx + '" y="' + (m.ly + 13) + '">' + second + "</text>";
      });
    });
    $("map").innerHTML = s + "</svg>";
    $("map-title").textContent = "Reporting gap by district, " + (c.key === "All" ? "whole period" : c.key);
  }

  /* ---- records ---------------------------------------------------------------------------- */
  function renderRecords() {
    var q = $("filter").value.trim().toLowerCase();
    var rows = DATA.records.filter(function (r) {
      return !q || [r.id, r.district, r.year, r.facility, r.source, r.first_time, r.count, r.added].join(" ").toLowerCase().indexOf(q) >= 0;
    });
    var html = '<table><thead><tr><th>ID</th><th>District</th><th class="num">Year</th><th>Facility</th><th>Source</th>' +
               '<th>First-time</th><th class="num">Count</th><th>Added</th></tr></thead><tbody>';
    rows.forEach(function (r) {
      html += "<tr><td>" + esc(r.id) + "</td><td>" + esc(r.district) + '</td><td class="num">' + r.year + "</td><td>" + esc(r.facility) +
              "</td><td>" + esc(r.source) + "</td><td>" + esc(r.first_time) + '</td><td class="num">' + r.count + "</td><td>" + esc(r.added) + "</td></tr>";
    });
    $("records").innerHTML = html + "</tbody></table>";
    $("records-count").textContent = "Showing " + rows.length + " of " + DATA.records.length + " records.";
  }

  /* ---- tabs and events ---------------------------------------------------------------------- */
  var TABS = ["overview", "map", "records"];
  function showTab(name) {
    TABS.forEach(function (t) {
      var on = t === name;
      $("tab-" + t).setAttribute("aria-selected", on ? "true" : "false");
      $("panel-" + t).hidden = !on;
    });
  }
  TABS.forEach(function (t) { $("tab-" + t).addEventListener("click", function () { showTab(t); }); });

  function renderAll() {
    var c = current();
    renderAlerts(c); renderCards(c); renderBars(c); renderTable(c); renderMap(c);
  }
  select.addEventListener("change", renderAll);
  $("filter").addEventListener("input", renderRecords);
  renderAll();
  renderRecords();
})();
</script>
</body>
</html>
"""


def main():
    for needed in (ENTRIES_FILE, BOUNDARY_FILE):
        if not needed.exists():
            raise SystemExit(f"Cannot find {needed}. Run this file from the dashboard folder.")

    entries = load_entries(ENTRIES_FILE)
    keys = ["All"] + [str(year) for year in range(YEAR_MAX, YEAR_MIN - 1, -1)]
    data = {
        "generated": date.today().isoformat(),
        "reference_year": 2024,
        "keys": keys,
        "districts": list(DISTRICTS),
        "periods": {key: period_rows(entries, key) for key in keys},
        "map": build_map(BOUNDARY_FILE, DISTRICT_FIELD),
        "records": [
            {"id": r["id"], "district": r["district"], "year": int(r["year"]), "facility": r["facility"],
             "source": r["source"], "first_time": r["first_time"], "count": int(r["count"]), "added": r["added"]}
            for _, r in entries.sort_values("id").iterrows()
        ],
    }
    payload = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    OUTPUT_FILE.write_text(PAGE.replace("__DATA__", payload), encoding="utf-8")
    print(f"Saved {OUTPUT_FILE.name} ({OUTPUT_FILE.stat().st_size / 1024:.0f} KB) from {len(entries)} records.")
    print("Open it by double-clicking. It works offline and cannot take new records.")


if __name__ == "__main__":
    main()
