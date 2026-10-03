# DATA260 HW5 Part 3 Metrics

- VERIFY_SEED: `262837`
- Calls per failure rate: `50`
- Total calls: `150`
- Maximum attempts: `3`
- Timeout per attempt: `1.0` seconds
- Base backoff delay: `0.005` seconds
- Maximum backoff delay: `0.02` seconds

| Injected failure rate | Success rate | Mean latency (ms) | p99 latency (ms) |
|---:|---:|---:|---:|
| 0% | 100.00% | 1.743 | 2.242 |
| 20% | 98.00% | 3.897 | 17.706 |
| 50% | 92.00% | 5.819 | 18.786 |

## Retry demonstration

The retry policy demonstrates three cases:

1. Success on the first attempt.
2. Failure on the first attempt followed by success after retry.
3. Failure after all allowed retry attempts.

Raw call records are stored in:

`reports/hw05/raw/fault_injection_calls.csv`

Summary results are stored in:

`reports/hw05/raw/fault_injection_summary.json`
## Part 3 - Retry and Fault-Injection Metrics

The retry experiment used `VERIFY_SEED = 262837` and ran 50 calls at
each injected failure rate. There were 150 total calls.

The retry policy used a maximum of three attempts, a one-second timeout
per attempt, and bounded exponential backoff delays.

| Injected failure rate | Success rate | Mean latency (ms) | p99 latency (ms) |
|---:|---:|---:|---:|
| 0% | 100.00% | 1.743 | 2.242 |
| 20% | 98.00% | 3.897 | 17.706 |
| 50% | 92.00% | 5.819 | 18.786 |

At a 0% injected failure rate, all calls succeeded on the first attempt,
so latency was lowest. At 20% and 50% failure rates, retry attempts
increased the mean and p99 latency. The retry policy recovered many
transient failures, which is why the final success rates remained 98% and
92%.

The policy is suitable for an interactive assistant because it uses a
small bounded number of retries and short backoff delays. For batch
processing, the system could use a larger maximum attempt count, longer
timeouts, and larger backoff limits because batch jobs can tolerate longer
processing times.