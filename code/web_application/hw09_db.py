"""Access to the s2837_rel relational database (MySQL, same tables as HW4-HW7).

Tables used: restaurant, restaurant_inspection (primary entity), inspection_related.
HW9 adds one column, restaurant_inspection.view_count (Part 1), and seeds ten named
restaurants with inspection codes S2837-H9-0001..0010 (taken from reference_data.json) so
the cache questions and the Part 4 reference dataset describe the same records.
"""

import json
import sqlite3
from datetime import datetime

from . import config as cfg
from .util import log

HW9_CODE_PREFIX = "S2837-H9-"


class Db:
    def __init__(self):
        if cfg.SQLITE_PATH:  # offline smoke test only
            self.dialect = "sqlite"
            self.conn = sqlite3.connect(cfg.SQLITE_PATH)
        else:
            import pymysql
            self.dialect = "mysql"
            self.conn = pymysql.connect(host=cfg.DB_HOST, port=cfg.DB_PORT, user=cfg.DB_USER,
                                        password=cfg.DB_PASSWORD, database=cfg.DB_NAME,
                                        autocommit=False, charset="utf8mb4")

    # ---- low level -------------------------------------------------------------
    def _sql(self, sql):
        return sql.replace("%s", "?") if self.dialect == "sqlite" else sql

    def execute(self, sql, params=(), commit=True):
        cur = self.conn.cursor()
        cur.execute(self._sql(sql), params)
        if commit:
            self.conn.commit()
        return cur

    def query(self, sql, params=()):
        cur = self.conn.cursor()
        cur.execute(self._sql(sql), params)
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    def columns(self, table):
        cur = self.conn.cursor()
        cur.execute(f"SELECT * FROM {table} LIMIT 0")
        return [c[0] for c in cur.description]

    def close(self):
        self.conn.close()

    # ---- schema ----------------------------------------------------------------
    def ensure_schema(self):
        """Create the HW5 tables if they are missing and add view_count (idempotent)."""
        auto = "INTEGER PRIMARY KEY AUTOINCREMENT" if self.dialect == "sqlite" \
            else "INT PRIMARY KEY AUTO_INCREMENT"
        self.execute(f"""CREATE TABLE IF NOT EXISTS restaurant (
            id {auto}, name VARCHAR(255) NOT NULL, address VARCHAR(500) NOT NULL,
            permit_code VARCHAR(50) NOT NULL UNIQUE, created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL)""")
        self.execute(f"""CREATE TABLE IF NOT EXISTS restaurant_inspection (
            id {auto}, name VARCHAR(255) NOT NULL, inspection_code VARCHAR(50) NOT NULL UNIQUE,
            inspection_date DATETIME NOT NULL, status VARCHAR(50) NOT NULL,
            score INT NOT NULL DEFAULT 0, restaurant_id INT NOT NULL,
            created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL)""")
        self.execute(f"""CREATE TABLE IF NOT EXISTS inspection_related (
            id {auto}, inspection_id INT NOT NULL, details VARCHAR(255))""")
        if "view_count" not in self.columns("restaurant_inspection"):
            self.execute("ALTER TABLE restaurant_inspection "
                         "ADD COLUMN view_count INT NOT NULL DEFAULT 0")
            log("DB", "added column restaurant_inspection.view_count")

    def seed_hw9_records(self, reset=False):
        """Insert (or with reset=True restore) the ten HW9 records from reference_data.json."""
        ref = json.loads(cfg.REFERENCE_FILE.read_text(encoding="utf-8"))
        now = datetime.now().replace(microsecond=0)
        for rec in ref["restaurants"]:
            row = self.query("SELECT id FROM restaurant WHERE permit_code=%s", (rec["permit_code"],))
            if row:
                rid = row[0]["id"]
            else:
                rid = self.execute("INSERT INTO restaurant (name,address,permit_code,created_at,"
                                   "updated_at) VALUES (%s,%s,%s,%s,%s)",
                                   (rec["restaurant"], rec["address"], rec["permit_code"], now,
                                    now)).lastrowid
            insp_date = datetime.fromisoformat(rec["inspection_date"] + "T10:00:00")
            name = f"{rec['restaurant']} - routine inspection"
            row = self.query("SELECT id FROM restaurant_inspection WHERE inspection_code=%s",
                             (rec["inspection_code"],))
            if row:
                iid = row[0]["id"]
                if reset:
                    self.execute("UPDATE restaurant_inspection SET status=%s, score=%s, "
                                 "inspection_date=%s, updated_at=%s WHERE id=%s",
                                 (rec["status"], rec["score"], insp_date, now, iid))
            else:
                iid = self.execute("INSERT INTO restaurant_inspection (name,inspection_code,"
                                   "inspection_date,status,score,restaurant_id,created_at,"
                                   "updated_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                                   (name, rec["inspection_code"], insp_date, rec["status"],
                                    rec["score"], rid, now, now)).lastrowid
            have = self.query("SELECT COUNT(*) AS n FROM inspection_related WHERE inspection_id=%s",
                              (iid,))[0]["n"]
            if have == 0 or reset:
                self.execute("DELETE FROM inspection_related WHERE inspection_id=%s", (iid,))
                for v in rec["violations"]:
                    self.execute("INSERT INTO inspection_related (inspection_id, details) "
                                 "VALUES (%s,%s)", (iid, v["text"][:255]))

    # ---- entity access -----------------------------------------------------------
    def hw9_records(self):
        rows = self.query(
            "SELECT i.id, i.inspection_code, i.inspection_date, i.status, i.score, i.view_count, "
            "r.name AS restaurant FROM restaurant_inspection i JOIN restaurant r "
            "ON r.id = i.restaurant_id WHERE i.inspection_code LIKE %s ORDER BY i.inspection_code",
            (HW9_CODE_PREFIX + "%",))
        for row in rows:
            row["violations"] = [r["details"] for r in self.query(
                "SELECT details FROM inspection_related WHERE inspection_id=%s ORDER BY id",
                (row["id"],))]
            row["inspection_date"] = str(row["inspection_date"])[:10]
        return rows

    def inspection_by_code(self, code):
        rows = self.query("SELECT id, inspection_code, status, score, view_count "
                          "FROM restaurant_inspection WHERE inspection_code=%s", (code,))
        return rows[0] if rows else None

    def get_view_count(self, inspection_id):
        rows = self.query("SELECT view_count FROM restaurant_inspection WHERE id=%s",
                          (inspection_id,))
        return rows[0]["view_count"] if rows else None

    def set_view_count(self, inspection_id, count):
        self.execute("UPDATE restaurant_inspection SET view_count=%s WHERE id=%s",
                     (count, inspection_id))

    def update_inspection(self, code, status, score, redis_client=None):
        """The only write path for HW9 records: updates s2837_rel and bumps the data-version
        marker s2837:dv:inspection:<code> in Redis so cached answers can detect staleness."""
        self.execute("UPDATE restaurant_inspection SET status=%s, score=%s, updated_at=%s "
                     "WHERE inspection_code=%s",
                     (status, score, datetime.now().replace(microsecond=0), code))
        version = None
        if redis_client is not None:
            version = int(redis_client.incr(cfg.DATA_VERSION_KEY.format(code=code)))
        return version
