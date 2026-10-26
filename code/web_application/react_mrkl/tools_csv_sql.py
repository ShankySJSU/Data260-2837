import duckdb
import pandas as pd
from datetime import datetime

# Global placeholder loaded by your UI endpoint
UPLOADED_DF = None

def load_uploaded_csv(df: pd.DataFrame):
    """
    The UI uses this to populate the global dataframe.
    """
    global UPLOADED_DF
    UPLOADED_DF = df


def _timestamp():
    return datetime.utcnow().isoformat()


def csv_sql(sql: str):
    """
    Execute read-only SQL SELECT queries against the uploaded CSV.

    HW7 Requirements:
    - MUST enforce SELECT only (no INSERT, UPDATE, DELETE)
    - Return common tool schema
    """
    if UPLOADED_DF is None:
        return {
            "success": False,
            "error": "CSV not uploaded",
            "source": "csv_sql",
            "ts": _timestamp()
        }

    # SECURITY: enforce SELECT-only queries
    sql_upper = sql.strip().upper()
    if not sql_upper.startswith("SELECT"):
        return {
            "success": False,
            "error": "Only read‑only SELECT queries are allowed.",
            "source": "csv_sql",
            "ts": _timestamp()
        }

    try:
        # Register the dataframe as a DuckDB table
        con = duckdb.connect()
        con.register("trips", UPLOADED_DF)

        result_df = con.execute(sql).df()
        rows = result_df.to_dict("records")

        return {
            "success": True,
            "data": {
                "rows": rows,
                "row_count": len(rows),
                "source": "uploaded.csv"
            },
            "error": None,
            "source": "csv_sql",
            "ts": _timestamp()
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"SQL execution failed: {str(e)}",
            "source": "csv_sql",
            "ts": _timestamp()
        }