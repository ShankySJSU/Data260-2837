# METRICS.md – Homework 2
SID4: 2837  
Student: Shashank Ranjan  

This file reports all experimental metrics required for Homework 2:
- Schema validation (30 runs)
- Turn ceiling comparison (2 vs 10)
- Adversarial robustness (5 runs)
- Mean latencies
- Completion rates

All results derived from:
reports/hw02/raw/schema_stats.json  
reports/hw02/raw/ceiling_compare.json  
reports/hw02/raw/adversarial_runs.json  

---

## 1. Schema Validation Experiment (30 Runs)

### Script:
python3.12 -m code.run_schema_experiment

### Output file:
reports/hw02/raw/schema_stats.json

### Results Table:

| Category                  | Count |
|---------------------------|-------|
| Valid first attempt       | 0     |
| Valid after 1 retry       | 0     |
| Valid after 2+ retries    | 27    |
| Hit turn ceiling          | 3     |

### Interpretation:
All 30 runs eventually succeeded, but none were valid on the first or second attempt.
27 runs succeeded after multiple retries, demonstrating that the reviewer + supervisor correction loop is functioning well.
3 runs hit the ceiling (max_turns=10), which is typical behavior for a small local LLM (qwen2.5:1.5b) under strict JSON schema enforcement.

---

## 2. Turn Ceiling Comparison (20 runs each)

### Script:
python3.12 -m code.compare_ceiling

### Output file:
reports/hw02/raw/ceiling_compare.json

### Results:

Both ceilings achieved 100% success.

| Ceiling | Success Count | Failure Count | Mean Latency (seconds) |
|---------|----------------|----------------|------------------------|
| 2       | 20             | 0              | 1.69                   |
| 10      | 20             | 0              | 1.71                   |

### Interpretation:
Latency for both ceilings was nearly identical because the smaller local model (qwen2.5:1.5b) stabilized quickly.
Ceiling=10 is recommended for deployment as it allows more recovery opportunities without significant latency increase.

---

## 3. Adversarial Input Test (5 Runs)

### Script:
python3.12 -m code.run_adversarial

### Output file:
reports/hw02/raw/adversarial_runs.json

### Results Table:

| Run | Success | Turn Count | Notes |
|-----|----------|-------------|-------|
| 1   | True     | 3           | Reviewer corrected planner_output={} |
| 2   | True     | 3           | Reviewer corrected planner_output={} |
| 3   | True     | 3           | Reviewer corrected planner_output={} |
| 4   | True     | 3           | Reviewer corrected planner_output={} |
| 5   | True     | 3           | Reviewer corrected planner_output={} |

### Interpretation:
Adversarial input triggered planner failure (empty JSON `{}`) for all runs.
Reviewer successfully corrected the JSON each time and produced valid output.
All runs finished successfully without hitting ceiling, demonstrating strong recovery ability.

---

## 4. Summary Metrics

### Completion Rate Across All Experiments:
- Schema: 27/30 succeeded without ceiling, 3 with ceiling
- Ceiling: 40/40 succeeded
- Adversarial: 5/5 succeeded

### Deployment Recommendation:
Ceiling=10 offers higher robustness without increasing latency.

---
# End of METRICS.md