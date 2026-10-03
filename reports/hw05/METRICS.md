# DATA260 HW5 Metrics

## Configuration

| Value | Result |
|---|---|
| SID4 | 2837 |
| PORT_BASE | 8137 |
| PREFIX | s2837 |
| SEED | 2837 |
| VERIFY_SEED | 262837 |
| DOMAIN_ID | 5 |
| Assigned domain | Local restaurant inspections |
| Local model | qwen2.5:1.5b |
| Repository | https://github.com/ShankySJSU/Data260-2837 |
| Final commit hash | To be added after the final HW5 commit |

---

## Part 1 - Backend and Redux Client

The HW5 backend extends the HW4 restaurant-inspection application with a
meaningful Restaurant-to-RestaurantInspection relationship.

Implemented backend features:

- Restaurant CRUD endpoints
- Restaurant inspection CRUD endpoints
- Restaurant-to-inspection relationship endpoint
- Pagination
- Unique permit-code validation
- Unique inspection-code validation
- Status validation
- Score validation from 0 through 100
- HTTP 404 responses for missing resources
- HTTP 409 responses for constraint violations
- Protection against deleting a restaurant with inspections

Implemented Redux Toolkit features:

- Redux store
- Inspection slice
- Fetch inspection thunk
- Create inspection thunk
- Update inspection thunk
- Delete inspection thunk
- Loading state
- Error state
- Success state
- Redux-based Home screen
- Redux-based Create screen
- Redux-based Update screen
- Redux-based Delete screen

Successful API verification included:

```text
POST /login                         200 OK
GET  /me                            200 OK
POST /restaurants/                  201 Created
GET  /restaurants/                  200 OK
POST /inspection/                  201 Created
GET  /inspection/                  200 OK
GET  /inspection/{id}              200 OK
PUT  /inspection/{id}              200 OK
DELETE /inspection/{id}            200 OK
GET  /restaurants/{id}/inspections 200 OK
```

---

## Part 2 - MCP Tool Servers

### TheMealDB MCP Server

The TheMealDB MCP server provides four tools:

```text
search_meals_by_name
meals_by_ingredient
random_meal
meal_details
```

The server uses STDIO transport. All application logs are sent to STDERR
so that STDOUT remains available for MCP JSON-RPC communication.

Inspector validation was completed for all four tools.

### Domain MCP Server

The domain MCP server provides exactly three tools:

```text
search
detail_lookup
aggregate
```

All three tools use the common response envelope:

```json
{
  "ok": true,
  "data": {},
  "error": null
}
```

Rejected calls use:

```json
{
  "ok": false,
  "data": null,
  "error": "description of the error"
}
```

Successful and intentionally invalid calls were tested in MCP Inspector.

---

## Part 3 - Retry and Fault-Injection Metrics

The retry experiment used:

```text
VERIFY_SEED = 262837
Calls per failure rate = 50
Total calls = 150
Maximum attempts = 3
Timeout per attempt = 1 second
Base backoff delay = 0.005 seconds
Maximum backoff delay = 0.02 seconds
```

### Retry demonstrations

| Scenario | Result | Attempts |
|---|---|---:|
| Success on first attempt | Success | 1 |
| Failure followed by retry success | Success | 2 |
| Failure after all allowed retries | Clean failure | 3 |

Console output:

```text
success_on_first_attempt: success=True, attempts=1, error=None
failure_then_success_after_retry: success=True, attempts=2, error=None
failure_after_all_allowed_retries: success=False, attempts=3, error=injected transient failure
```

### Fault-injection results

| Injected failure rate | Success rate | Mean latency (ms) | p99 latency (ms) |
|---:|---:|---:|---:|
| 0% | 100.00% | 1.743 | 2.242 |
| 20% | 98.00% | 3.897 | 17.706 |
| 50% | 92.00% | 5.819 | 18.786 |

At a 0% failure rate, all calls succeeded on their first attempt and latency
was lowest.

At 20% and 50% failure rates, retry attempts increased both mean latency and
p99 latency. The retry policy recovered many transient failures, which is why
the final success rates remained 98% and 92%.

The retry policy is suitable for an interactive assistant because it uses a
bounded number of attempts and short backoff delays. For batch processing,
the system could use more retries, longer timeouts, and larger backoff delays
because batch jobs can tolerate longer processing times.

Raw records are stored in:

```text
reports/hw05/raw/fault_injection_calls.csv
```

The CSV contains:

```text
151 rows = 1 header row + 150 call records
```

Additional raw files:

```text
reports/hw05/raw/fault_injection_summary.json
reports/hw05/raw/retry_demonstration.json
```

---

## Part 4 - execute_tool and Offline Tests

The `execute_tool(name, inputs)` function is the single entry point used by
the agent to access the three domain tools.

It provides:

- Tool-name validation
- Input validation
- Safe dispatching
- JSON-string responses
- Structured success responses
- Structured error responses
- Exception handling without crashing

The offline tests use an in-memory fake repository and do not require:

```text
MySQL
Ollama
MCP Inspector
TheMealDB
Internet access
```

Tests completed:

```text
PASS search_valid
PASS search_invalid
PASS detail_valid
PASS detail_invalid
PASS aggregate_valid
PASS aggregate_invalid
PASS unknown_tool
PASS safety_rule_allows_valid_score
PASS safety_rule_blocks_invalid_score
PASS agent_stops_at_max_steps
```

Final test result:

```text
10/10 tests passed
```

---

## Part 5 - Safety Rule and Agent Loop

### Safety rule

The domain safety rule requires every inspection score to be between 0 and
100.

Valid score example:

```json
{
  "score": 92
}
```

Blocked score example:

```json
{
  "score": 150
}
```

Blocked response:

```json
{
  "ok": false,
  "data": null,
  "error": "Safety rule blocked the response: inspection score must be between 0 and 100"
}
```

### Agent loop

The agent:

- Uses the local Ollama model
- Calls only `execute_tool`
- Tracks the current step
- Enforces a maximum step count
- Records each model action
- Records each tool call
- Records each tool result
- Records the final stop reason
- Writes JSONL logs

The agent log is stored in:

```text
reports/hw05/raw/agent_runs.jsonl
```

The four-scenario summary is stored in:

```text
reports/hw05/raw/agent_scenarios.json
```

The scenario log is stored in:

```text
reports/hw05/raw/agent_scenarios.jsonl
```

### Agent scenario metrics

| Scenario | Steps | Stop reason | Tool calls |
|---|---:|---|---:|
| search_rangoli | 4 | model_error | 3 |
| inspection_detail | 4 | normal_completion | 3 |
| pass_aggregate | 4 | normal_completion | 3 |
| fail_search | 6 | normal_completion | 5 |

### Scenario observations

The `inspection_detail` scenario completed successfully and returned the
correct status and score for inspection 5006.

The `pass_aggregate` scenario completed successfully and returned the number
of PASS inspections and the average score.

The `search_rangoli` scenario experienced a model error after several
successful tool calls. The harness stopped safely and logged the error.

The `fail_search` scenario reached normal completion, although the model
made an invalid tool request during the process. The tool layer rejected the
invalid input without crashing.

These results demonstrate that the agent harness can safely handle:

- Successful tool calls
- Repeated tool calls
- Invalid tool inputs
- Model errors
- Bounded execution
- Clean stop reasons

---

## Raw Evidence Files

The following machine-readable files were generated:

```text
reports/hw05/raw/fault_injection_calls.csv
reports/hw05/raw/fault_injection_summary.json
reports/hw05/raw/retry_demonstration.json
reports/hw05/raw/agent_runs.jsonl
reports/hw05/raw/agent_scenarios.jsonl
reports/hw05/raw/agent_scenarios.json
```

The final commit hash will be added after the HW5 verification script runs
successfully and the repository is tagged with:

```text
hw5
```