import json
import tempfile
from execute_tool import execute_tool
from pathlib import Path
from agent import MockModel, run_agent


class FakeRepository:
    """
    In-memory repository.

    The tests do not use MySQL, MCP Inspector,
    TheMealDB, or Ollama.
    """

    def __init__(self):
        self.records = [
            {
                "id": 1,
                "name": "Rangoli Sweets and Snacks",
                "inspection_code": "INSP-00000001",
                "inspection_date": "2026-10-02T12:00:00",
                "status": "PASS",
                "score": 92,
                "restaurant_id": 1,
                "restaurant_name": (
                    "Legacy HW4 Restaurants"
                ),
                "restaurant_permit_code": (
                    "LEGACY-2837"
                ),
            },
            {
                "id": 2,
                "name": "Moonlight Garden Restaurant",
                "inspection_code": "INSP-00000002",
                "inspection_date": "2026-10-02T12:00:00",
                "status": "FAIL",
                "score": 45,
                "restaurant_id": 1,
                "restaurant_name": (
                    "Legacy HW4 Restaurants"
                ),
                "restaurant_permit_code": (
                    "LEGACY-2837"
                ),
            },
        ]

    def search(
        self,
        query: str,
        limit: int,
    ):
        query = query.lower()

        matches = [
            record
            for record in self.records
            if (
                query in record["name"].lower()
                or query
                in record["inspection_code"].lower()
                or query
                in record["status"].lower()
            )
        ]

        return matches[:limit]

    def detail_lookup(
        self,
        inspection_id: int,
    ):
        for record in self.records:
            if record["id"] == inspection_id:
                return record

        return None

    def aggregate(
        self,
        status: str | None,
    ):
        records = self.records

        if status:
            records = [
                record
                for record in records
                if record["status"] == status
            ]

        counts = {
            "PASS": 0,
            "FAIL": 0,
            "WARNING": 0,
        }

        for record in records:
            counts[record["status"]] += 1

        scores = [
            record["score"]
            for record in records
        ]

        return {
            "status_filter": status,
            "total_restaurants": 1,
            "total_inspections": len(records),
            "average_score": (
                sum(scores) / len(scores)
                if scores
                else 0
            ),
            "counts_by_status": counts,
        }

class UnsafeFakeRepository(FakeRepository):
    def detail_lookup(
        self,
        inspection_id: int,
    ):
        if inspection_id == 99:
            unsafe_record = dict(
                self.records[0]
            )

            unsafe_record["id"] = 99
            unsafe_record["score"] = 150

            return unsafe_record

        return super().detail_lookup(
            inspection_id
        )

def parse_result(
    result: str,
):
    return json.loads(result)


def run_test(
    name: str,
    test_function,
):
    try:
        test_function()
        print(f"PASS {name}")
        return True

    except AssertionError as exc:
        print(f"FAIL {name}: {exc}")
        return False

    except Exception as exc:
        print(f"FAIL {name}: {exc}")
        return False


def test_search_valid():
    result = parse_result(
        execute_tool(
            "search",
            {
                "query": "Rangoli",
                "limit": 5,
            },
            repository=FakeRepository(),
        )
    )

    assert result["ok"] is True
    assert result["error"] is None
    assert len(result["data"]) == 1
    assert result["data"][0]["id"] == 1


def test_search_invalid():
    result = parse_result(
        execute_tool(
            "search",
            {
                "query": "",
                "limit": 5,
            },
            repository=FakeRepository(),
        )
    )

    assert result["ok"] is False
    assert result["data"] is None
    assert result["error"] == (
        "query cannot be empty"
    )


def test_detail_valid():
    result = parse_result(
        execute_tool(
            "detail_lookup",
            {
                "inspection_id": 1,
            },
            repository=FakeRepository(),
        )
    )

    assert result["ok"] is True
    assert result["data"]["id"] == 1
    assert result["data"]["status"] == "PASS"


def test_detail_invalid():
    result = parse_result(
        execute_tool(
            "detail_lookup",
            {
                "inspection_id": -1,
            },
            repository=FakeRepository(),
        )
    )

    assert result["ok"] is False
    assert result["data"] is None
    assert result["error"] == (
        "inspection_id must be greater than zero"
    )


def test_aggregate_valid():
    result = parse_result(
        execute_tool(
            "aggregate",
            {
                "status": "pass",
            },
            repository=FakeRepository(),
        )
    )

    assert result["ok"] is True
    assert result["data"]["total_inspections"] == 1
    assert result["data"]["counts_by_status"]["PASS"] == 1


def test_aggregate_invalid():
    result = parse_result(
        execute_tool(
            "aggregate",
            {
                "status": "UNKNOWN",
            },
            repository=FakeRepository(),
        )
    )

    assert result["ok"] is False
    assert result["data"] is None
    assert result["error"] == (
        "status must be PASS, FAIL, or WARNING"
    )


def test_unknown_tool():
    result = parse_result(
        execute_tool(
            "not_a_real_tool",
            {},
            repository=FakeRepository(),
        )
    )

    assert result["ok"] is False
    assert result["data"] is None
    assert result["error"] == (
        "unknown tool: not_a_real_tool"
    )

#add two more tests for the safetly rules for valid and invalid scores
def test_safety_rule_allows_valid_score():
    result = parse_result(
        execute_tool(
            "detail_lookup",
            {
                "inspection_id": 1,
            },
            repository=FakeRepository(),
        )
    )

    assert result["ok"] is True
    assert result["data"]["score"] == 92


def test_safety_rule_blocks_invalid_score():
    result = parse_result(
        execute_tool(
            "detail_lookup",
            {
                "inspection_id": 99,
            },
            repository=UnsafeFakeRepository(),
        )
    )

    assert result["ok"] is False
    assert result["data"] is None
    assert result["error"] == (
        "Safety rule blocked the response: "
        "inspection score must be between "
        "0 and 100"
    )

def test_agent_stops_at_max_steps():
    def fake_executor(
        tool_name,
        inputs,
    ):
        return json.dumps(
            {
                "ok": True,
                "data": [],
                "error": None,
            }
        )

    repeated_tool_actions = [
        {
            "action": "tool",
            "tool_name": "search",
            "inputs": {
                "query": "Rangoli",
                "limit": 5,
            },
        },
        {
            "action": "tool",
            "tool_name": "search",
            "inputs": {
                "query": "Rangoli",
                "limit": 5,
            },
        },
    ]

    model = MockModel(
        repeated_tool_actions
    )

    with tempfile.TemporaryDirectory() as folder:
        log_path = (
            Path(folder)
            / "agent_runs.jsonl"
        )

        result = run_agent(
            user_input="Find Rangoli inspections.",
            model=model,
            max_steps=2,
            tool_executor=fake_executor,
            log_path=log_path,
        )

        assert result["stop_reason"] == (
            "max_steps"
        )

        assert result["steps"] == 2
        assert result["tool_calls"] == 2
        assert log_path.exists()

if __name__ == "__main__":
    tests = [
        (
            "search_valid",
            test_search_valid,
        ),
        (
            "search_invalid",
            test_search_invalid,
        ),
        (
            "detail_valid",
            test_detail_valid,
        ),
        (
            "detail_invalid",
            test_detail_invalid,
        ),
        (
            "aggregate_valid",
            test_aggregate_valid,
        ),
        (
            "aggregate_invalid",
            test_aggregate_invalid,
        ),
        (
            "unknown_tool",
            test_unknown_tool,
        ),

        (
            "safety_rule_allows_valid_score",
            test_safety_rule_allows_valid_score,
        ),
        (
            "safety_rule_blocks_invalid_score",
            test_safety_rule_blocks_invalid_score,
        ),
        (
            "agent_stops_at_max_steps",
            test_agent_stops_at_max_steps,
        ),
    ]

    passed = 0

    for name, function in tests:
        if run_test(name, function):
            passed += 1

    print()
    print(
        f"{passed}/{len(tests)} tests passed"
    )

    if passed != len(tests):
        raise SystemExit(1)