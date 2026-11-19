# Bincom ICT — Preliminary Online Interview Test (Beginner Python Solution)

**Stack chosen (STEP 0): Python — Beginner level — basic PYTHON**
(Flask is used only as a tiny web framework for routing/pages. No Django.
All database work is plain SQL with parameterized queries.)

## What this app does

| Page | Question | What it does |
|---|---|---|
| `/` | — | Home page with links and explanation |
| `/q1` | **Q1** | Display the result for **any individual polling unit**. Chained combo box: **LGA → Ward → Polling Unit**, then a table of party scores + total. |
| `/q2` | **Q2** | Display the **summed total** of all polling units under a Local Government (chosen with a **select box**). The sum is calculated from `announced_pu_results` **only** — `announced_lga_results` is **not** used. |
| `/q3` | **Q3** | **Store results for ALL parties** for a new polling unit (one row per party in `announced_pu_results`). |

## Files

| File | Purpose |
|---|---|
| `app.py` | **Main program** — all 3 pages + chained-combo APIs |
| `config.py` | Database settings (MySQL / SQLite demo) |
| `build_demo_db.py` | Converts `bincom_test.sql` (MySQL) → `bincom_demo.db` (SQLite) for demo mode |
| `bincom_test.sql` | Original test database dump (MySQL, database `bincomphptest`) |
| `bincom_demo.db` | SQLite demo database (same tables/data, built by `build_demo_db.py`) |
| `requirements.txt` | `flask`, `pymysql` |
| `.env.example` | Settings template |

## How to run

### Option A — SQLite demo mode (no MySQL needed, recommended for quick hosting)

```bash
pip install -r requirements.txt
python build_demo_db.py   # creates bincom_demo.db (once)
python app.py
# Open http://127.0.0.1:5000
```

### Option B — MySQL mode (original test database)

1. Import the dump:
   ```bash
   mysql -u root -p < bincom_test.sql
   ```
   The dump creates database `bincomphptest`.
2. Set your MySQL details in `config.py` (or as environment variables —
   see `.env.example`), and set `DB_MODE=mysql` (or leave `auto`).
3. Run:
   ```bash
   pip install -r requirements.txt
   python3 app.py
   ```

`DB_MODE=auto` (default) tries MySQL first and falls back to SQLite if
MySQL is not reachable, so the app still runs on temporary hosting
without a MySQL server.

## Database notes (important for the assessor)

- Only **Delta State (state_id = 25)** is in the database (25 LGAs).
- Key link (as stated in the test):
  `polling_unit.uniqueid = announced_pu_results.polling_unit_uniqueid`
  (note: `polling_unit_id` is a different column and is **not** used).
- `polling_unit.lga_id` and `ward.lga_id` refer to `lga.lga_id`
  (not `lga.uniqueid`). The LGA dropdown therefore uses `lga_id` as the
  value and `lga_name` as the label.
- `announced_lga_results.lga_name` actually stores the `lga_id` as text.
- The `party` table lists 9 parties (`PDP, DPP, ACN, PPA, CDC, JP, ANPP,
  LABOUR, CPP`), but the results tables use the 4-character abbreviation
  `LABO` for LABOUR (`party_abbreviation` is `char(4)`). Q3 maps
  `LABOUR → LABO` when inserting so new rows match existing data.
- The dummy data is intentionally messy: only 18 of 272 polling units
  have results, one polling unit (uniqueid 10) has duplicate party rows,
  and ward links (`ward_id` / `uniquewardid`) are inconsistent. The
  chained combo handles this by matching **either** ward column and
  falling back to all polling units in the LGA (with a note on the page).

## SQL used (summary)

**Q1 — one polling unit:**
```sql
SELECT party_abbreviation, party_score, entered_by_user, date_entered
FROM announced_pu_results
WHERE polling_unit_uniqueid = ? ORDER BY party_abbreviation;
```

**Q2 — summed LGA total (from polling unit results ONLY):**
```sql
SELECT r.party_abbreviation, SUM(r.party_score) AS total_score
FROM polling_unit p
JOIN announced_pu_results r ON p.uniqueid = r.polling_unit_uniqueid
WHERE p.lga_id = ?
GROUP BY r.party_abbreviation ORDER BY total_score DESC;
```

**Q3 — insert all parties (one row per party):**
```sql
INSERT INTO announced_pu_results
  (polling_unit_uniqueid, party_abbreviation, party_score,
   entered_by_user, date_entered, user_ip_address)
VALUES (?, ?, ?, ?, ?, ?);
```
Q3 first checks that no results exist yet for the chosen polling unit
and validates that every party score is a whole number ≥ 0.

## User-friendliness (Hints)

- **Chained combo boxes** (LGA → Ward → Polling Unit) on Q1 and Q3,
  powered by small `/api/wards` and `/api/polling_units` endpoints.
  The forms also work without JavaScript (they submit and reload).
- Clear labels, required-field validation with friendly error messages,
  totals shown on Q1/Q2, and graceful "No results found" messages for
  LGAs/polling units without dummy data.
- All queries are **parameterized** (no string formatting of user input).

## Hosting (STEP 2 — temporary hosting for assessment)

The app binds to `0.0.0.0:$PORT` (default 5000), so it runs on most
free hosts (Render, Railway, Fly.io, PythonAnywhere, etc.):

```bash
pip install -r requirements.txt
python3 build_demo_db.py   # if using SQLite demo mode
gunicorn app:app           # or: python3 app.py
```

Then submit the hosted URL in the STEP 3 online form.

## Sample checks

- Q1: LGA **Sapele** (lga_id 17) → Polling Unit **DT1708006**
  (uniqueid 8) shows PDP 802, DPP 719, ACN 416, PPA 939, CDC 394, JP 99.
- Q2: LGA **Uvwie** (lga_id 22) sums 5 polling units; ANPP total 3,126
  is the highest.
- Q3: Pick any polling unit without results (254 of 272), enter 9
  scores, and the rows appear in Q1.
