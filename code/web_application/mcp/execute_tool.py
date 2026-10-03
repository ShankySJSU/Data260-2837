import json
import sys
from pathlib import Path
from typing import Any


# ============================================================
# IMPORT APPLICATION MODELS
# ============================================================

WEB_APP_DIR = Path(__file__).resolve().parents[1]

if str(WEB_APP_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_APP_DIR))


from database import db_session_basede26
from domain.models import Restaurant, RestaurantInspection


# ============================================================
# COMMON RESPONSE ENVELOPE
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


def json_result(payload: dict[str, Any]) -> str:
    return json.dumps(
        payload,
        sort_keys=True,
    )


# ============================================================
# DATABASE REPOSITORY
# ============================================================

class SqlAlchemyDomainRepository:
    """
    Production repository used by execute_tool.

    Each method opens and closes its own database session.
    """

    def _serialize(
        self,
        inspection: RestaurantInspection,
    ) -> dict[str, Any]:
        restaurant = inspection.restaurant

        return {
            "id": inspection.id,
            "name": inspection.name,
            "inspection_code": (
                inspection.inspection_code
            ),
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

    def search(
        self,
        query: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        db = db_session_basede26()

        try:
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

            return [
                self._serialize(record)
                for record in records
            ]

        finally:
            db.close()

    def detail_lookup(
        self,
        inspection_id: int,
    ) -> dict[str, Any] | None:
        db = db_session_basede26()

        try:
            record = (
                db.query(RestaurantInspection)
                .filter(
                    RestaurantInspection.id
                    == inspection_id
                )
                .first()
            )

            if record is None:
                return None

            return self._serialize(record)

        finally:
            db.close()

    def aggregate(
        self,
        status: str | None,
    ) -> dict[str, Any]:
        db = db_session_basede26()

        try:
            query = db.query(RestaurantInspection)

            if status:
                query = query.filter(
                    RestaurantInspection.status
                    == status
                )

            records = query.all()

            scores = [
                record.score
                for record in records
                if record.score is not None
            ]

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

            return {
                "status_filter": status,
                "total_restaurants": (
                    db.query(Restaurant).count()
                ),
                "total_inspections": len(records),
                "average_score": (
                    round(
                        sum(scores) / len(scores),
                        2,
                    )
                    if scores
                    else 0
                ),
                "counts_by_status": counts,
            }

        finally:
            db.close()


# ============================================================
# INPUT VALIDATION
# ============================================================

VALID_STATUSES = {
    "PASS",
    "FAIL",
    "WARNING",
}


def validate_search_inputs(
    inputs: dict[str, Any],
) -> tuple[str, int]:
    query = inputs.get("query")
    limit = inputs.get("limit", 10)

    if not isinstance(query, str):
        raise ValueError(
            "query must be a string"
        )

    query = query.strip()

    if not query:
        raise ValueError(
            "query cannot be empty"
        )

    if (
        isinstance(limit, bool)
        or not isinstance(limit, int)
    ):
        raise ValueError(
            "limit must be an integer"
        )

    if not 1 <= limit <= 25:
        raise ValueError(
            "limit must be between 1 and 25"
        )

    return query, limit


def validate_detail_inputs(
    inputs: dict[str, Any],
) -> int:
    inspection_id = inputs.get(
        "inspection_id"
    )

    if (
        isinstance(inspection_id, bool)
        or not isinstance(inspection_id, int)
    ):
        raise ValueError(
            "inspection_id must be an integer"
        )

    if inspection_id <= 0:
        raise ValueError(
            "inspection_id must be greater than zero"
        )

    return inspection_id


def validate_aggregate_inputs(
    inputs: dict[str, Any],
) -> str | None:
    status = inputs.get("status")

    if status is None or status == "":
        return None

    if not isinstance(status, str):
        raise ValueError(
            "status must be a string"
        )

    status = status.strip().upper()

    if status not in VALID_STATUSES:
        raise ValueError(
            "status must be PASS, FAIL, or WARNING"
        )

    return status

#================
# Enfornce saftety rules for tool execution.
#  Only approved tools can be executed, and inputs are validated to prevent injection attacks or other unsafe operations.
#=========================================

def enforce_safety_rules(
    tool_name: str,
    data,
) -> str | None:
    """
    Return an error message when a domain safety
    rule is violated.
    """

    if tool_name == "detail_lookup":
        if isinstance(data, dict):
            score = data.get("score")

            if (
                not isinstance(score, int)
                or score < 0
                or score > 100
            ):
                return (
                    "Safety rule blocked the response: "
                    "inspection score must be between "
                    "0 and 100"
                )

    return None

# ============================================================
# SINGLE SAFE TOOL ENTRY POINT
# ============================================================

def execute_tool(
    name: str,
    inputs: dict[str, Any],
    repository=None,
) -> str:
    """
    Execute one approved domain tool.

    Returns a JSON string and never exposes an
    unhandled exception to the caller.
    """
    try:
        if not isinstance(name, str):
            return json_result(
                failure(
                    "tool name must be a string"
                )
            )

        if not isinstance(inputs, dict):
            return json_result(
                failure(
                    "inputs must be a JSON object"
                )
            )

        approved_tools = {
            "search",
            "detail_lookup",
            "aggregate",
        }

        if name not in approved_tools:
            return json_result(
                failure(
                    f"unknown tool: {name}"
                )
            )

        if repository is None:
            repository = (
                SqlAlchemyDomainRepository()
            )

        if name == "search":
            query, limit = validate_search_inputs(
                inputs
            )

            data = repository.search(
                query,
                limit,
            )

            return json_result(
                success(data)
            )

        if name == "detail_lookup":
            inspection_id = (
                validate_detail_inputs(inputs)
            )

            data = repository.detail_lookup(
                inspection_id
            )

            if data is None:
                return json_result(
                    failure(
                        f"inspection "
                        f"{inspection_id} "
                        f"was not found"
                    )
                )

            safety_error = enforce_safety_rules(
                "detail_lookup",
                data,
            )

            if safety_error:
                return json_result(
                    failure(safety_error)
                )

            return json_result(
                success(data)
            )

        if name == "aggregate":
            status = (
                validate_aggregate_inputs(
                    inputs
                )
            )

            data = repository.aggregate(
                status
            )

            return json_result(
                success(data)
            )

        return json_result(
            failure(
                f"unsupported tool: {name}"
            )
        )

    except ValueError as exc:
        return json_result(
            failure(str(exc))
        )

    except Exception as exc:
        return json_result(
            failure(
                f"tool execution failed: {exc}"
            )
        )