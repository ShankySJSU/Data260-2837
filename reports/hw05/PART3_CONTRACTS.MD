# DATA260 HW5 Part 3 - Domain Tool Contracts

## Overview

Part 3 documents the input contracts and rejected-call behavior for the
same three domain MCP tools tested in Part 2B:

- `search`
- `detail_lookup`
- `aggregate`

Each tool uses the following response envelope:

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

---

## 1. search

### Purpose

Search restaurant inspection records by restaurant name, inspection name,
inspection code, or inspection status.

### Expected input schema

```json
{
  "query": "string, required, non-empty",
  "limit": "integer, optional, must be between 1 and 25"
}
```

### Valid input example

```json
{
  "query": "Rangoli",
  "limit": 5
}
```

### Rejected input

```json
{
  "query": "",
  "limit": 5
}
```

### Returned error output

```json
{
  "ok": false,
  "data": null,
  "error": "query cannot be empty"
}
```

### Explanation

The request is rejected because the `query` field is required and cannot
be empty. The tool returns a structured error instead of raising an
unhandled exception.

The `limit` value must also be between 1 and 25.

---

## 2. detail_lookup

### Purpose

Retrieve one inspection record together with its related restaurant
information.

### Expected input schema

```json
{
  "inspection_id": "positive integer, required"
}
```

### Valid input example

```json
{
  "inspection_id": 1
}
```

### Rejected input

```json
{
  "inspection_id": -1
}
```

### Returned error output

```json
{
  "ok": false,
  "data": null,
  "error": "inspection_id must be greater than zero"
}
```

### Explanation

The request is rejected because an inspection ID must be a positive
integer. Zero and negative values are invalid identifiers.

If a positive ID does not exist, the tool returns a structured not-found
error:

```json
{
  "ok": false,
  "data": null,
  "error": "inspection 999999 was not found"
}
```

---

## 3. aggregate

### Purpose

Return inspection totals, average score, restaurant count, and counts
grouped by inspection status.

### Expected input schema

```json
{
  "status": "optional string; allowed values are PASS, FAIL, or WARNING"
}
```

The status comparison is case-insensitive. These values are equivalent:

```text
PASS
Pass
pass
```

### Valid input example

```json
{
  "status": "PASS"
}
```

### Rejected input

```json
{
  "status": "UNKNOWN"
}
```

### Returned error output

```json
{
  "ok": false,
  "data": null,
  "error": "status must be PASS, FAIL, or WARNING"
}
```

### Explanation

The request is rejected because `UNKNOWN` is not a supported inspection
status.

The allowed statuses are:

- `PASS`
- `FAIL`
- `WARNING`

The aggregate tool can also be called without a filter:

```json
{}
```

This returns aggregate results for all inspection records.

---

## Common Error-Handling Contract

All three domain tools follow the same behavior:

1. Validate the input.
2. Return `ok: false` when validation fails.
3. Set `data` to `null` for rejected calls.
4. Return a short human-readable error.
5. Avoid exposing Python tracebacks to the MCP client.
6. Return `ok: true` with data when the request succeeds.

### Successful response structure

```json
{
  "ok": true,
  "data": {},
  "error": null
}
```

### Rejected response structure

```json
{
  "ok": false,
  "data": null,
  "error": "clear explanation of the problem"
}
```

This same response envelope will be reused by the `execute_tool` function
in Part 4.