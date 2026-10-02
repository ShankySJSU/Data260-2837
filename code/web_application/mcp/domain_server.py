import logging
import sys
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP


# ============================================================
# IMPORT THE EXISTING APPLICATION
# ============================================================

# Add code/web_application to Python's import path.
WEB_APP_DIR = Path(__file__).resolve().parents[1]

if str(WEB_APP_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_APP_DIR))


from database import db_session_basede26
from domain.models import Restaurant, RestaurantInspection


# ============================================================
# LOGGING
# ============================================================

# STDOUT is reserved for MCP JSON-RPC communication.
# All logs go to STDERR.
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

logger = logging.getLogger("domain-server")


# ============================================================
# MCP SERVER
# ============================================================

mcp = FastMCP(
    name="domain",
)


# ============================================================
# RESPONSE ENVELOPE
# ============================================================

def success(data: Any) -> dict[str, Any]:
    return {
        "ok": True,
        "data": data,
        "error": None,
    }


def failure(message: str) -> dict[str, Any]:
    return {
        "ok": False,
        "data": None,
        "error": message,
    }


# ============================================================
# HELPERS
# ============================================================

VALID_STATUSES = {
    "PASS",
    "FAIL",
    "WARNING",
}


def serialize_inspection(
    inspection: RestaurantInspection,
) -> dict[str, Any]:
    restaurant = inspection.restaurant

    return {
        "id": inspection.id,
        "name": inspection.name,
        "inspection_code": inspection.inspection_code,
        "inspection_date": (
            inspection.inspection_date.isoformat()
            if inspection.inspection_date
            else None
        ),
        "status": (
            inspection.status.upper()
            if inspection.status
            else None
        ),
        "score": inspection.score,
        "restaurant_id": inspection.restaurant_id,
        "restaurant_name": (
            restaurant.name
            if restaurant
            else None
        ),
        "restaurant_permit_code": (
            restaurant.permit_code
            if restaurant
            else None
        ),
    }


def validate_limit(limit: int):
    if limit < 1 or limit > 25:
        raise ValueError(
            "limit must be between 1 and 25"
        )


def validate_status(
    status: str | None,
) -> str | None:
    if status is None:
        return None

    normalized = status.strip().upper()

    if normalized not in VALID_STATUSES:
        raise ValueError(
            "status must be PASS, FAIL, or WARNING"
        )

    return normalized


# ============================================================
# TOOL 1: SEARCH
# ============================================================

@mcp.tool()
def search(
    query: str,
    limit: int = 10,
) -> dict[str, Any]:
    """
    Search restaurant inspections by restaurant name,
    inspection name, inspection code, or status.
    """
    db = db_session_basede26()

    try:
        query = query.strip()

        if not query:
            return failure(
                "query cannot be empty"
            )

        validate_limit(limit)

        search_text = f"%{query}%"

        records = (
            db.query(RestaurantInspection)
            .join(
                Restaurant,
                Restaurant.id
                == RestaurantInspection.restaurant_id,
            )
            .filter(
                (
                    RestaurantInspection.name.ilike(
                        search_text
                    )
                    | Restaurant.name.ilike(
                        search_text
                    )
                    | RestaurantInspection.inspection_code.ilike(
                        search_text
                    )
                    | RestaurantInspection.status.ilike(
                        search_text
                    )
                )
            )
            .order_by(RestaurantInspection.id)
            .limit(limit)
            .all()
        )

        return success(
            [
                serialize_inspection(record)
                for record in records
            ]
        )

    except ValueError as exc:
        return failure(str(exc))

    except Exception as exc:
        logger.exception("Search tool failed")
        return failure(
            f"search failed: {exc}"
        )

    finally:
        db.close()


# ============================================================
# TOOL 2: DETAIL LOOKUP
# ============================================================

@mcp.tool()
def detail_lookup(
    inspection_id: int,
) -> dict[str, Any]:
    """
    Retrieve one inspection and its related restaurant.
    """
    db = db_session_basede26()

    try:
        if inspection_id <= 0:
            return failure(
                "inspection_id must be greater than zero"
            )

        record = (
            db.query(RestaurantInspection)
            .join(
                Restaurant,
                Restaurant.id
                == RestaurantInspection.restaurant_id,
            )
            .filter(
                RestaurantInspection.id
                == inspection_id
            )
            .first()
        )

        if record is None:
            return failure(
                f"inspection {inspection_id} was not found"
            )

        return success(
            serialize_inspection(record)
        )

    except Exception as exc:
        logger.exception("Detail lookup failed")
        return failure(
            f"detail lookup failed: {exc}"
        )

    finally:
        db.close()


# ============================================================
# TOOL 3: AGGREGATE
# ============================================================

@mcp.tool()
def aggregate(
    status: str | None = None,
) -> dict[str, Any]:
    """
    Return inspection counts and average score.

    Optional status filter:
    PASS, FAIL, or WARNING.
    """
    db = db_session_basede26()

    try:
        normalized_status = validate_status(status)

        query = db.query(RestaurantInspection)

        if normalized_status:
            query = query.filter(
                RestaurantInspection.status
                == normalized_status
            )

        records = query.all()

        total_inspections = len(records)

        scores = [
            record.score
            for record in records
            if record.score is not None
        ]

        average_score = (
            round(sum(scores) / len(scores), 2)
            if scores
            else 0
        )

        counts = {
            "PASS": 0,
            "FAIL": 0,
            "WARNING": 0,
        }

        for record in records:
            record_status = (
                record.status.upper()
                if record.status
                else "UNKNOWN"
            )

            if record_status in counts:
                counts[record_status] += 1

        return success(
            {
                "status_filter": normalized_status,
                "total_restaurants": (
                    db.query(Restaurant).count()
                ),
                "total_inspections": total_inspections,
                "average_score": average_score,
                "counts_by_status": counts,
            }
        )

    except ValueError as exc:
        return failure(str(exc))

    except Exception as exc:
        logger.exception("Aggregate tool failed")
        return failure(
            f"aggregate failed: {exc}"
        )

    finally:
        db.close()


# ============================================================
# STDIO ENTRY POINT
# ============================================================

if __name__ == "__main__":
    logger.info(
        "Starting domain MCP server over STDIO"
    )

    mcp.run(
        transport="stdio"
    )