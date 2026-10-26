import pandas as pd

from web_application.react_mrkl.tools_csv_sql import (
    load_uploaded_csv,
    csv_sql,
)

from web_application.react_mrkl.tools_pricing import (
    policy_retriever,
)

from web_application.react_mrkl.tools_calculator import (
    calculator,
)


# -----------------------------------------------------
# TEST 1: CSV SQL TOOL
# -----------------------------------------------------

def test_csv_sql_basic():
    print("\n=== TEST: csv_sql basic SELECT ===")

    # Create a tiny mock dataframe to simulate uploaded CSV
    df = pd.DataFrame({
        "trip_id": [1, 2, 3],
        "duration": [10, 20, 30],
        "user_type": ["member", "casual", "member"],
    })

    load_uploaded_csv(df)

    result = csv_sql("SELECT trip_id, duration FROM trips WHERE duration > 10")

    print("Result:", result)
    assert result["success"] is True
    assert result["data"]["row_count"] == 2
    assert result["data"]["rows"][0]["duration"] == 20


def test_csv_sql_reject_non_select():
    print("\n=== TEST: csv_sql rejects non‑SELECT ===")

    result = csv_sql("DELETE FROM trips")

    print("Result:", result)
    assert result["success"] is False
    assert "Only read‑only SELECT" in result["error"]


# -----------------------------------------------------
# TEST 2: POLICY RETRIEVER TOOL
# -----------------------------------------------------

def test_policy_retriever():
    print("\n=== TEST: policy_retriever ===")

    # Fake URL with known HTML for testing (HTTP example)
    # In real HW7 you use actual pricing page URLs during screenshot evidence.
    test_html = """
        <html><body>
            Monthly Membership: $25 per month.
            Single Trip: $3.99 per ride.
        </body></html>
    """

    # Use requests-mock if available, or monkeypatch the requests.get inside policy_retriever.
    # For this course, we simulate directly:
    import requests
    from unittest.mock import MagicMock

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = test_html
    requests.get = MagicMock(return_value=mock_resp)

    result = policy_retriever("http://fake-url", "Membership")

    print("Result:", result)
    assert result["success"] is True
    assert len(result["data"]["passages"]) >= 1


# -----------------------------------------------------
# TEST 3: CALCULATOR TOOL
# -----------------------------------------------------

def test_calculator_basic():
    print("\n=== TEST: calculator basic arithmetic ===")

    result = calculator("10 + 20 * 2")

    print("Result:", result)
    assert result["success"] is True
    assert result["data"]["value"] == 50


def test_calculator_invalid():
    print("\n=== TEST: calculator invalid expression ===")

    result = calculator("import os")

    print("Result:", result)
    assert result["success"] is False
    assert "error" in result


'''
#How to Run Tests
#python -m web_application.react_mrkl.test_mrkl_tools
'''