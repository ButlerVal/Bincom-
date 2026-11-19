"""
Bincom ICT - Preliminary Online Interview Test
Beginner Python solution (basic Python + Flask, no Django)

Stack chosen (STEP 0): Python - Beginner level - basic PYTHON
  Flask is used only as a tiny web framework for routing/pages.
  All database work is plain SQL with parameterized queries.

Questions answered:
  Q1 (/q1) - Display the result for any individual polling unit.
             Uses a chained combo box: LGA -> Ward -> Polling Unit.
  Q2 (/q2) - Display the summed total of all polling units under a
             Local Government (selected with a select box).
             The sum is calculated from announced_pu_results ONLY.
             announced_lga_results is NOT used here (per instructions).
  Q3 (/q3) - Store results for ALL parties for a new polling unit
             (inserts one row per party into announced_pu_results).

Database:
  Original dump is MySQL (bincom_test.sql, database `bincomphptest`).
  The app can also run in SQLite demo mode (bincom_demo.db) so it can
  be hosted anywhere without MySQL. See config.py and README.md.

Run:
  pip install -r requirements.txt
  python3 build_demo_db.py     # only needed for SQLite demo mode
  python3 app.py               # then open http://127.0.0.1:5000
"""

import os
from datetime import datetime

from flask import Flask, jsonify, request

import config

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Database helpers (basic Python - one small helper for each job)
# ---------------------------------------------------------------------------
# The app supports two databases with the same tables/columns:
#   * MySQL  via pymysql  (original test database)
#   * SQLite via sqlite3  (demo database built from the same dump)
# Queries below use "?" placeholders. For MySQL they are converted to
# "%s" automatically, so the same query text works for both.

_db_mode = None  # "mysql" or "sqlite", decided once at startup


def decide_db_mode():
    """Pick mysql or sqlite. 'auto' tries MySQL, falls back to SQLite."""
    global _db_mode
    if _db_mode is not None:
        return _db_mode
    wanted = config.DB_MODE.lower()
    if wanted == "sqlite":
        _db_mode = "sqlite"
    elif wanted == "mysql":
        _db_mode = "mysql"
    else:  # auto
        try:
            import pymysql
            conn = pymysql.connect(connect_timeout=2, **config.MYSQL_CONFIG)
            conn.close()
            _db_mode = "mysql"
        except Exception:
            _db_mode = "sqlite"
    print(f"[DB] Using {_db_mode} database")
    return _db_mode


def get_connection():
    """Open a new database connection (caller must close it)."""
    mode = decide_db_mode()
    if mode == "mysql":
        import pymysql
        import pymysql.cursors
        return pymysql.connect(
            cursorclass=pymysql.cursors.DictCursor, **config.MYSQL_CONFIG)
    else:
        import sqlite3
        conn = sqlite3.connect(config.SQLITE_PATH)
        conn.row_factory = sqlite3.Row
        return conn


def convert_placeholders(query):
    """Convert ? placeholders to %s for MySQL; leave as-is for SQLite."""
    if decide_db_mode() == "mysql":
        return query.replace("?", "%s")
    return query


def fetch_all(query, params=()):
    """Run a SELECT and return all rows as a list of dicts."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(convert_placeholders(query), params)
        rows = cur.fetchall()
        # sqlite3.Row -> dict; pymysql already returns dicts.
        return [dict(r) for r in rows]
    finally:
        conn.close()


def fetch_one(query, params=()):
    """Run a SELECT and return the first row as a dict, or None."""
    rows = fetch_all(query, params)
    return rows[0] if rows else None


def execute(query, params=()):
    """Run an INSERT/UPDATE, commit, and return the new row id."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(convert_placeholders(query), params)
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Small helpers shared by the pages
# ---------------------------------------------------------------------------

# The party table stores 'LABOUR' but the results tables use the
# 4-character abbreviation 'LABO' (party_abbreviation is char(4)).
# Map it when inserting so new rows match the existing data.
PARTY_ABBREV_MAP = {"LABOUR": "LABO"}


def get_lgas():
    """All LGAs in Delta State (state_id = 25), alphabetical."""
    return fetch_all(
        "SELECT lga_id, lga_name FROM lga WHERE state_id = 25 "
        "ORDER BY lga_name")


def get_wards(lga_id):
    """Wards in one LGA. Returns uniqueid, ward_id and ward_name."""
    return fetch_all(
        "SELECT uniqueid, ward_id, ward_name FROM ward "
        "WHERE lga_id = ? ORDER BY ward_name", (lga_id,))


def get_polling_units(lga_id, ward_uniqueid=None):
    """
    Polling units in one LGA, optionally narrowed to one ward.

    The dummy data links polling units to wards in two ways
    (ward_id and uniquewardid) and neither is fully consistent,
    so we match EITHER column. If a ward has no matching polling
    units, we fall back to all polling units in the LGA and the
    page shows a note. This keeps the chained combo usable.
    """
    if ward_uniqueid:
        ward = fetch_one(
            "SELECT ward_id FROM ward WHERE uniqueid = ?",
            (ward_uniqueid,))
        if ward:
            rows = fetch_all(
                "SELECT uniqueid, polling_unit_number, polling_unit_name "
                "FROM polling_unit WHERE lga_id = ? "
                "AND (ward_id = ? OR uniquewardid = ?) "
                "ORDER BY polling_unit_name",
                (lga_id, ward["ward_id"], ward_uniqueid))
            if rows:
                return rows, False  # (rows, used_fallback)
    rows = fetch_all(
        "SELECT uniqueid, polling_unit_number, polling_unit_name "
        "FROM polling_unit WHERE lga_id = ? ORDER BY polling_unit_name",
        (lga_id,))
    return rows, bool(ward_uniqueid)  # fallback used if ward was chosen


def get_parties():
    """All parties from the party table, in table order."""
    return fetch_all(
        "SELECT id, partyid, partyname FROM party ORDER BY id")


def esc(text):
    """Escape HTML special characters (basic protection for output)."""
    if text is None:
        return ""
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


# ---------------------------------------------------------------------------
# Page layout (inline HTML/CSS - no template files needed)
# ---------------------------------------------------------------------------

CSS = """
body { font-family: Arial, Helvetica, sans-serif; margin: 0; background: #f4f6f8; color: #222; }
header { background: #0a7a3d; color: white; padding: 16px 20px; }
header h1 { margin: 0 0 4px 0; font-size: 22px; }
header p { margin: 0; font-size: 14px; opacity: 0.9; }
nav { background: #065c2e; padding: 8px 20px; }
nav a { color: white; text-decoration: none; margin-right: 18px; font-weight: bold; }
nav a:hover { text-decoration: underline; }
main { max-width: 900px; margin: 20px auto; background: white; padding: 24px; border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.15); }
h2 { color: #0a7a3d; margin-top: 0; }
table { border-collapse: collapse; width: 100%; margin: 12px 0; }
th, td { border: 1px solid #ccc; padding: 8px; text-align: left; }
th { background: #e8f5ec; }
tr:nth-child(even) { background: #f9f9f9; }
label { display: block; margin: 12px 0 4px 0; font-weight: bold; }
select, input[type=text], input[type=number] { width: 100%; max-width: 480px; padding: 8px; border: 1px solid #999; border-radius: 4px; box-sizing: border-box; }
button { background: #0a7a3d; color: white; border: none; padding: 10px 22px; border-radius: 4px; cursor: pointer; font-size: 15px; margin-top: 14px; }
button:hover { background: #065c2e; }
.message { padding: 12px; border-radius: 4px; margin: 12px 0; }
.success { background: #e6f4ea; border: 1px solid #0a7a3d; }
.error { background: #fce8e6; border: 1px solid #c5221f; }
.note { background: #fef7e0; border: 1px solid #e37400; padding: 10px; border-radius: 4px; margin: 12px 0; }
.total { font-weight: bold; font-size: 17px; }
.small { font-size: 13px; color: #555; }
footer { text-align: center; color: #666; font-size: 13px; margin: 20px; }
"""


def page(title, body):
    """Wrap *body* in a full HTML page."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} - Bincom Election Test</title>
<style>{CSS}</style></head>
<body>
<header><h1>Bincom ICT - 2011 Election Results (Delta State)</h1>
<p>Preliminary Online Interview Test - Beginner Python Solution</p></header>
<nav><a href="/">Home</a><a href="/q1">Q1: Polling Unit Result</a>
<a href="/q2">Q2: LGA Summed Result</a><a href="/q3">Q3: Enter New Result</a></nav>
<main>{body}</main>
<footer>Basic Python + Flask &middot; MySQL/SQLite &middot; Dummy 2011 election data</footer>
</body></html>"""


# JavaScript for the chained combo boxes (LGA -> Ward -> Polling Unit).
# It fetches options from /api/... so the page updates without reloading.
# If JavaScript is off, the forms still work by submitting and reloading.
CHAIN_JS = """
<script>
async function loadWards() {
  var lga = document.getElementById('lga_id').value;
  var wardSel = document.getElementById('ward_id');
  var puSel = document.getElementById('pu_id');
  wardSel.innerHTML = '<option value="">-- Select Ward --</option>';
  if (puSel) puSel.innerHTML = '<option value="">-- Select Polling Unit --</option>';
  if (!lga) return;
  var r = await fetch('/api/wards?lga_id=' + lga);
  var wards = await r.json();
  wards.forEach(function(w) {
    var o = document.createElement('option');
    o.value = w.uniqueid; o.textContent = w.ward_name;
    wardSel.appendChild(o);
  });
}
async function loadPUs() {
  var lga = document.getElementById('lga_id').value;
  var ward = document.getElementById('ward_id').value;
  var puSel = document.getElementById('pu_id');
  if (!puSel) return;
  puSel.innerHTML = '<option value="">-- Select Polling Unit --</option>';
  if (!lga) return;
  var url = '/api/polling_units?lga_id=' + lga;
  if (ward) url += '&ward_id=' + ward;
  var r = await fetch(url);
  var pus = await r.json();
  pus.forEach(function(p) {
    var o = document.createElement('option');
    o.value = p.uniqueid;
    o.textContent = (p.polling_unit_number || '') + ' - ' + (p.polling_unit_name || '');
    puSel.appendChild(o);
  });
}
</script>
"""


def chained_selects_html(lgas, wards, pus, sel_lga, sel_ward, sel_pu):
    """HTML for the LGA -> Ward -> Polling Unit chained combo boxes."""
    lga_opts = "".join(
        f'<option value="{l["lga_id"]}"'
        f'{" selected" if str(l["lga_id"]) == str(sel_lga) else ""}>'
        f'{esc(l["lga_name"])}</option>' for l in lgas)
    ward_opts = "".join(
        f'<option value="{w["uniqueid"]}"'
        f'{" selected" if str(w["uniqueid"]) == str(sel_ward) else ""}>'
        f'{esc(w["ward_name"])}</option>' for w in (wards or []))
    pu_opts = "".join(
        f'<option value="{p["uniqueid"]}"'
        f'{" selected" if str(p["uniqueid"]) == str(sel_pu) else ""}>'
        f'{esc(p["polling_unit_number"])} - {esc(p["polling_unit_name"])}</option>'
        for p in (pus or []))
    return f"""
    <label for="lga_id">1. Select Local Government (LGA):</label>
    <select name="lga_id" id="lga_id" onchange="loadWards(); loadPUs();">
      <option value="">-- Select LGA --</option>{lga_opts}</select>

    <label for="ward_id">2. Select Ward:</label>
    <select name="ward_id" id="ward_id" onchange="loadPUs();">
      <option value="">-- Select Ward --</option>{ward_opts}</select>

    <label for="pu_id">3. Select Polling Unit:</label>
    <select name="pu_id" id="pu_id">
      <option value="">-- Select Polling Unit --</option>{pu_opts}</select>
    <button type="submit">Show Result</button>
    """


# ---------------------------------------------------------------------------
# Home page
# ---------------------------------------------------------------------------

@app.route("/")
def home():
    body = """
    <h2>Welcome</h2>
    <p>This app answers the three questions in the Bincom
    <em>Basic Programming Test</em> using the dummy 2011 election
    database (<code>bincom_test.sql</code>). Only Delta State
    (state_id = 25) is in the database.</p>
    <ul>
      <li><a href="/q1"><strong>Question 1</strong></a> - Display the
      result for any individual polling unit (chained combo box:
      LGA &rarr; Ward &rarr; Polling Unit).</li>
      <li><a href="/q2"><strong>Question 2</strong></a> - Display the
      summed total of all polling units under a Local Government
      (LGA chosen with a select box). The total is summed from
      <code>announced_pu_results</code> only.</li>
      <li><a href="/q3"><strong>Question 3</strong></a> - Store results
      for <strong>all parties</strong> for a new polling unit.</li>
    </ul>
    <p class="small">Tables used: <code>lga</code>, <code>ward</code>,
    <code>polling_unit</code>, <code>party</code>,
    <code>announced_pu_results</code>. Key link:
    <code>polling_unit.uniqueid = announced_pu_results.polling_unit_uniqueid</code>.</p>
    """
    return page("Home", body)


# ---------------------------------------------------------------------------
# Q1 - Result for one polling unit
# ---------------------------------------------------------------------------

@app.route("/q1")
def q1():
    lgas = get_lgas()
    sel_lga = request.args.get("lga_id", "")
    sel_ward = request.args.get("ward_id", "")
    sel_pu = request.args.get("pu_id", "")

    wards, pus, fallback_note = [], [], ""
    if sel_lga:
        wards = get_wards(sel_lga)
        pus, used_fallback = get_polling_units(sel_lga, sel_ward or None)
        if used_fallback:
            fallback_note = ('<div class="note">No polling units matched '
                             'this ward in the dummy data, so all polling '
                             'units in this LGA are shown.</div>')

    result_html = ""
    if sel_pu:
        # Polling unit details (join to LGA for the LGA name).
        pu = fetch_one(
            "SELECT p.uniqueid, p.polling_unit_number, p.polling_unit_name, "
            "p.ward_id, p.lga_id, l.lga_name FROM polling_unit p "
            "LEFT JOIN lga l ON p.lga_id = l.lga_id WHERE p.uniqueid = ?",
            (sel_pu,))
        # Party scores for this polling unit (one row per party).
        rows = fetch_all(
            "SELECT party_abbreviation, party_score, entered_by_user, "
            "date_entered FROM announced_pu_results "
            "WHERE polling_unit_uniqueid = ? ORDER BY party_abbreviation",
            (str(sel_pu),))

        if pu:
            result_html += f"""
            <h3>Polling Unit: {esc(pu["polling_unit_name"])}
            ({esc(pu["polling_unit_number"])})</h3>
            <p>LGA: {esc(pu["lga_name"])} &middot; Ward ID: {esc(pu["ward_id"])}
            &middot; Polling Unit Unique ID: {esc(pu["uniqueid"])}</p>"""
        if rows:
            total = sum(r["party_score"] for r in rows)
            trs = "".join(
                f"<tr><td>{esc(r['party_abbreviation'])}</td>"
                f"<td>{r['party_score']:,}</td>"
                f"<td>{esc(r['entered_by_user'])}</td>"
                f"<td>{esc(r['date_entered'])}</td></tr>" for r in rows)
            result_html += f"""
            <table><tr><th>Party</th><th>Score</th>
            <th>Entered By</th><th>Date Entered</th></tr>{trs}</table>
            <p class="total">Total votes: {total:,}</p>"""
        else:
            result_html += ('<div class="note">No results have been entered '
                            'for this polling unit yet. '
                            '<a href="/q3">Enter results for this polling '
                            'unit</a>.</div>')

    body = f"""
    <h2>Question 1 - Result for an Individual Polling Unit</h2>
    <p>Choose an LGA, then a Ward, then a Polling Unit. The result
    for that polling unit will be displayed below.</p>
    <form method="get" action="/q1">
    {chained_selects_html(lgas, wards, pus, sel_lga, sel_ward, sel_pu)}
    </form>
    {fallback_note}
    {result_html}
    {CHAIN_JS}
    """
    return page("Q1 Polling Unit Result", body)


# ---------------------------------------------------------------------------
# Q2 - Summed total for all polling units in an LGA
# ---------------------------------------------------------------------------

@app.route("/q2")
def q2():
    lgas = get_lgas()
    sel_lga = request.args.get("lga_id", "")

    lga_opts = "".join(
        f'<option value="{l["lga_id"]}"'
        f'{" selected" if str(l["lga_id"]) == str(sel_lga) else ""}>'
        f'{esc(l["lga_name"])}</option>' for l in lgas)

    result_html = ""
    if sel_lga:
        lga = fetch_one("SELECT lga_name FROM lga WHERE lga_id = ?",
                        (sel_lga,)) or {"lga_name": "Unknown LGA"}
        # IMPORTANT: the summed total is calculated from the polling
        # unit results ONLY (announced_pu_results joined through
        # polling_unit). announced_lga_results is NOT used here.
        rows = fetch_all(
            "SELECT r.party_abbreviation, SUM(r.party_score) AS total_score "
            "FROM polling_unit p "
            "JOIN announced_pu_results r "
            "ON p.uniqueid = r.polling_unit_uniqueid "
            "WHERE p.lga_id = ? "
            "GROUP BY r.party_abbreviation ORDER BY total_score DESC",
            (sel_lga,))
        pu_count = fetch_one(
            "SELECT COUNT(DISTINCT p.uniqueid) AS n FROM polling_unit p "
            "JOIN announced_pu_results r "
            "ON p.uniqueid = r.polling_unit_uniqueid WHERE p.lga_id = ?",
            (sel_lga,))
        pu_list = fetch_all(
            "SELECT DISTINCT p.uniqueid, p.polling_unit_number, "
            "p.polling_unit_name FROM polling_unit p "
            "JOIN announced_pu_results r "
            "ON p.uniqueid = r.polling_unit_uniqueid "
            "WHERE p.lga_id = ? ORDER BY p.polling_unit_name", (sel_lga,))

        if rows:
            grand = sum(r["total_score"] for r in rows)
            trs = "".join(
                f"<tr><td>{esc(r['party_abbreviation'])}</td>"
                f"<td>{r['total_score']:,}</td></tr>" for r in rows)
            pu_items = "".join(
                f"<li>{esc(p['polling_unit_number'])} - "
                f"{esc(p['polling_unit_name'])}</li>" for p in pu_list)
            result_html = f"""
            <h3>Summed Result for {esc(lga["lga_name"])} LGA</h3>
            <p>Summed from {pu_count["n"] if pu_count else 0} polling unit(s) with results
            in this LGA (from <code>announced_pu_results</code>).</p>
            <table><tr><th>Party</th><th>Total Score</th></tr>{trs}</table>
            <p class="total">Grand Total: {grand:,}</p>
            <p><strong>Polling units included:</strong></p><ul>{pu_items}</ul>
            """
        else:
            result_html = ('<div class="note">No polling unit results found '
                           'for this LGA in the dummy data.</div>')

    body = f"""
    <h2>Question 2 - Summed Total Result for an LGA</h2>
    <p>Select a Local Government to see the summed total of all its
    polling units. The total is calculated from the individual
    polling unit results.</p>
    <form method="get" action="/q2">
      <label for="lga_id">Select Local Government:</label>
      <select name="lga_id" id="lga_id">
        <option value="">-- Select LGA --</option>{lga_opts}</select>
      <button type="submit">Show Summed Result</button>
    </form>
    {result_html}
    """
    return page("Q2 LGA Summed Result", body)


# ---------------------------------------------------------------------------
# Q3 - Store results for ALL parties for a new polling unit
# ---------------------------------------------------------------------------

@app.route("/q3", methods=["GET", "POST"])
def q3():
    lgas = get_lgas()
    parties = get_parties()
    message_html = ""

    # --- POST: save the form ---
    if request.method == "POST":
        pu_id = request.form.get("pu_id", "").strip()
        entered_by = request.form.get("entered_by_user", "").strip()

        # Read the score for every party from the form.
        scores = {}
        for party in parties:
            key = f"score_{party['partyid']}"
            scores[party["partyid"]] = request.form.get(key, "").strip()

        # Basic validation (beginner-friendly error messages).
        error = ""
        if not pu_id:
            error = "Please select a polling unit."
        elif not entered_by:
            error = "Please enter your name (entered by user)."
        else:
            for party in parties:
                value = scores[party["partyid"]]
                if value == "":
                    error = f"Please enter a score for {party['partyid']}."
                    break
                try:
                    number = int(value)
                except ValueError:
                    error = f"Score for {party['partyid']} must be a whole number."
                    break
                if number < 0:
                    error = f"Score for {party['partyid']} cannot be negative."
                    break

        # Do not enter results twice for the same polling unit.
        if not error:
            existing = fetch_one(
                "SELECT COUNT(*) AS n FROM announced_pu_results "
                "WHERE polling_unit_uniqueid = ?", (str(pu_id),))
            if existing and existing["n"] > 0:
                error = ("Results have already been entered for this "
                         "polling unit. Please choose a different polling "
                         "unit, or view the existing result in Question 1.")

        if error:
            message_html = f'<div class="error">{esc(error)}</div>'
        else:
            # Insert one row per party (ALL parties).
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ip = request.headers.get("X-Forwarded-For",
                                     request.remote_addr or "127.0.0.1")
            for party in parties:
                abbrev = PARTY_ABBREV_MAP.get(party["partyid"],
                                              party["partyid"])
                execute(
                    "INSERT INTO announced_pu_results "
                    "(polling_unit_uniqueid, party_abbreviation, "
                    "party_score, entered_by_user, date_entered, "
                    "user_ip_address) VALUES (?, ?, ?, ?, ?, ?)",
                    (str(pu_id), abbrev, int(scores[party["partyid"]]),
                     entered_by, now, ip))
            message_html = (
                '<div class="success">Results saved successfully for all '
                f'{len(parties)} parties. '
                f'<a href="/q1?pu_id={esc(pu_id)}">View the saved result '
                'in Question 1</a>.</div>')

    # --- GET (and re-display after POST): chained selects + form ---
    sel_lga = request.args.get("lga_id", "") or request.form.get("lga_id", "")
    sel_ward = request.args.get("ward_id", "") or request.form.get("ward_id", "")
    sel_pu = request.args.get("pu_id", "") or request.form.get("pu_id", "")

    wards, pus = [], []
    if sel_lga:
        wards = get_wards(sel_lga)
        pus, _ = get_polling_units(sel_lga, sel_ward or None)

    # One score input per party.
    score_inputs = "".join(
        f'<label for="score_{esc(p["partyid"])}">'
        f'{esc(p["partyid"])} score:</label>'
        f'<input type="number" min="0" required '
        f'name="score_{esc(p["partyid"])}" '
        f'id="score_{esc(p["partyid"])}" placeholder="0">'
        for p in parties)

    body = f"""
    <h2>Question 3 - Store Results for a New Polling Unit</h2>
    <p>Select the polling unit, enter the score for <strong>every
    party</strong>, and submit. One row per party will be saved to
    <code>announced_pu_results</code>.</p>
    {message_html}
    <form method="post" action="/q3">
    {chained_selects_html(lgas, wards, pus, sel_lga, sel_ward, sel_pu)}
    <label for="entered_by_user">Your name (entered by user):</label>
    <input type="text" name="entered_by_user" id="entered_by_user"
           required placeholder="e.g. Jane Doe">
    {score_inputs}
    <button type="submit">Save Results</button>
    </form>
    {CHAIN_JS}
    """
    return page("Q3 Enter New Result", body)


# ---------------------------------------------------------------------------
# API endpoints for the chained combo boxes (used by the JavaScript)
# ---------------------------------------------------------------------------

@app.route("/api/wards")
def api_wards():
    lga_id = request.args.get("lga_id", "")
    if not lga_id:
        return jsonify([])
    return jsonify(get_wards(lga_id))


@app.route("/api/polling_units")
def api_polling_units():
    lga_id = request.args.get("lga_id", "")
    ward_id = request.args.get("ward_id", "") or None
    if not lga_id:
        return jsonify([])
    pus, _ = get_polling_units(lga_id, ward_id)
    return jsonify(pus)


# ---------------------------------------------------------------------------
# Start the server
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    decide_db_mode()
    # host 0.0.0.0 so it works on temporary hosting / in containers.
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")),
            debug=True)
