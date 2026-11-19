"""
Build a SQLite demo database from the MySQL dump (bincom_test.sql).

Why this file exists
--------------------
The original test database is MySQL (phpMyAdmin dump). For quick hosting
and for trying the app without setting up MySQL, app.py can run in
"demo mode" against a SQLite file with the same tables and data.

This script converts the MySQL dump to SQLite:
  python3 build_demo_db.py
  -> creates bincom_demo.db next to this file

It is NOT needed if you use MySQL (see README.md). It only parses the
CREATE TABLE / INSERT statements; it does not change any data.
"""

import os
import re
import sqlite3

HERE = os.path.dirname(os.path.abspath(__file__))
SQL_PATH = os.path.join(HERE, "bincom_test.sql")
DB_PATH = os.path.join(HERE, "bincom_demo.db")


def split_outside_quotes(text, sep=","):
    """Split *text* on *sep* characters that are outside single quotes."""
    parts = []
    current = []
    in_quote = False
    for ch in text:
        if ch == "'":
            in_quote = not in_quote
            current.append(ch)
        elif ch == sep and not in_quote:
            parts.append("".join(current))
            current = []
        else:
            current.append(ch)
    parts.append("".join(current))
    return parts


def extract_tuples(values_text):
    """Extract each (...) tuple from a MySQL VALUES list, respecting quotes."""
    tuples = []
    depth = 0
    in_quote = False
    start = None
    for i, ch in enumerate(values_text):
        if ch == "'":
            in_quote = not in_quote
        elif not in_quote:
            if ch == "(":
                if depth == 0:
                    start = i
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0 and start is not None:
                    tuples.append(values_text[start + 1:i])
                    start = None
    return tuples


def parse_value(token):
    """Convert one MySQL value token to a Python value."""
    token = token.strip()
    if token.upper() == "NULL":
        return None
    if len(token) >= 2 and token.startswith("'") and token.endswith("'"):
        return token[1:-1]
    # Try int, then float, else keep as text.
    try:
        return int(token)
    except ValueError:
        pass
    try:
        return float(token)
    except ValueError:
        return token


def parse_create_table(sql, table):
    """Return (columns, sqlite_types) for *table* from its CREATE TABLE."""
    pattern = rf"CREATE TABLE.*?`{table}`\s*\((.*?)\)\s*ENGINE"
    m = re.search(pattern, sql, re.S | re.I)
    if not m:
        raise ValueError(f"CREATE TABLE for {table} not found")
    body = m.group(1)
    columns = []
    types = []
    for line in body.splitlines():
        line = line.strip().rstrip(",")
        cm = re.match(r"`([^`]+)`\s+(\w+)", line)
        if cm:
            col, mysql_type = cm.group(1), cm.group(2).lower()
            columns.append(col)
            types.append("INTEGER" if mysql_type in ("int", "bigint", "smallint", "tinyint") else "TEXT")
    return columns, types


def main():
    with open(SQL_PATH, "r", encoding="utf-8") as fh:
        sql = fh.read()

    tables = ["lga", "ward", "polling_unit", "party",
              "announced_pu_results", "announced_lga_results",
              "states", "agentname"]

    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    for table in tables:
        columns, types = parse_create_table(sql, table)
        cols_sql = ", ".join(f'"{c}" {t}' for c, t in zip(columns, types))
        cur.execute(f'CREATE TABLE "{table}" ({cols_sql})')
        print(f"Created {table}: {columns}")

        m = re.search(rf"INSERT INTO `{table}`.*?VALUES\s*(.*?);", sql, re.S)
        if not m:
            print(f"  (no data for {table})")
            continue
        tuples = extract_tuples(m.group(1))
        placeholders = ", ".join("?" for _ in columns)
        col_list = ", ".join(f'"{c}"' for c in columns)
        rows = []
        for tup in tuples:
            tokens = split_outside_quotes(tup)
            if len(tokens) != len(columns):
                print(f"  WARNING: row has {len(tokens)} values, "
                      f"expected {len(columns)}: {tup[:120]}")
                continue
            rows.append(tuple(parse_value(t) for t in tokens))
        cur.executemany(
            f'INSERT INTO "{table}" ({col_list}) VALUES ({placeholders})', rows)
        print(f"  Inserted {len(rows)} rows")

    conn.commit()
    conn.close()
    print(f"\nDone. SQLite demo database written to {DB_PATH}")


if __name__ == "__main__":
    main()
