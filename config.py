"""
Database settings for the Bincom election test app.

Choose ONE mode:

1. MySQL (original test database)
   - Import bincom_test.sql into MySQL, e.g.:
       mysql -u root -p < bincom_test.sql
     (the dump creates database `bincomphptest`; you may rename it)
   - Set the values below (or use environment variables).
   - Set DB_MODE = "mysql"

2. SQLite demo (no MySQL needed - good for quick hosting / trying out)
   - Build the demo database once:
       python3 build_demo_db.py
   - Set DB_MODE = "sqlite"

DB_MODE = "auto" tries MySQL first and falls back to SQLite if MySQL
is not reachable. This is handy for temporary hosting.
"""

import os

DB_MODE = os.environ.get("DB_MODE", "auto")  # "mysql", "sqlite" or "auto"

# --- MySQL settings (used when DB_MODE is "mysql" or "auto") ---
MYSQL_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": int(os.environ.get("DB_PORT", "3306")),
    "user": os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", ""),
    # Database name inside bincom_test.sql is `bincomphptest`.
    # If you imported it under a different name, change this.
    "database": os.environ.get("DB_NAME", "bincomphptest"),
}

# --- SQLite demo settings ---
SQLITE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "bincom_demo.db")
