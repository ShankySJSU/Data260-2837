# METRICS.md – Homework 3
SID4: 2837  
Student: Shashank Ranjan  

# HW4 N+1 Query Metrics

## Summary Table

| Page Size | Version | SQL stmts/req | p50 (ms) | p95 (ms) | p99 (ms) |
|----------|---------|---------------|----------|----------|----------|
| 10       | naive   | <fill>        | <fill>   | <fill>   | <fill>   |
| 10       | fixed   | <fill>        | <fill>   | <fill>   | <fill>   |
| 50       | naive   | <fill>        | <fill>   | <fill>   | <fill>   |
| 50       | fixed   | <fill>        | <fill>   | <fill>   | <fill>   |
| 200      | naive   | <fill>        | <fill>   | <fill>   | <fill>   |
| 200      | fixed   | <fill>        | <fill>   | <fill>   | <fill>   |

## Notes

- Naive version triggers N+1 queries (1 query per record).
- Fixed version uses joinedload which collapses N queries into 1.
- As page size grows, naive version gets exponentially slower.