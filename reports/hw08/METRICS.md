# HW8 METRICS - Shashank Ranjan (SID4 2837, PREFIX s2837)

Generated 2026-11-02T08:22:08.022+00:00 by run_hw08_failures.py from raw/part3_results.json.
Kafka bootstrap: localhost:9092; s2837_tasks partitions = 2; MAX_RETRIES = 3; VERIFY_SEED = 262837.

## Part 1 - request/response over Kafka

| Operation | correlation_id | success | result | preserved |
|---|---|---|---|---|
| CREATE_INSPECTION | 81382958-c78b-454f-af44-b8ea73093926 | True | inspection_id=5c72cee2-0d9a-4186-adaa-8705114cde4b | True |
| GET_INSPECTION | 6e6c3788-feca-49bc-8d7d-57abf1f3c027 | True | entity returned | True |

## Part 2 - three-agent pipeline

- correlation_id `c88dcfc7-8966-41c3-8ba1-afb40890e891` status **approved**, stages: planner -> writer -> reviewer, writer model: ollama:qwen2.5:1.5b (temperature 0, seed 2837)

## Part 3 - failure table

| Failure scenario | Before fix | After fix |
|---|---|---|
| Duplicate delivery | same correlation_id delivered twice -> 2 drafts, 2 finals (extra side effect) | idempotency store -> 1 draft, 1 final, 1 DUPLICATE skips |
| Consumer killed mid-work | commit-before-processing: offset already {1: 4, 0: 3} at kill -> after restart message_lost=True | commit-after-success: committed {1: 5, 0: 3} at kill -> redelivered, REDELIVERY detected=True, draft completed=True, committed now {1: 6, 0: 3} |
| Poison message | unbounded retry: 18 attempts in 15s, good messages processed 0/3 (partition blocked) | 3 attempts (limit 3) -> 1 record in s2837_dead_letter, good messages processed 3/3 |
| Two partitions/two consumers | no key: 4/4 entities split across partitions, 2/4 processed out of order (2 inversions) | key=entity_id: 0/4 split, 0/4 out of order (0 inversions) |

### Ordering run - unkeyed

| entity | processed seq order | partitions | writers | in order |
|---|---|---|---|---|
| INSP-2837-A | [2, 1, 3] | [0, 1] | writer-order-1-unkeyed, writer-order-2-unkeyed | False |
| INSP-2837-B | [1, 3, 2, 4, 5, 6, 7, 8] | [0, 1] | writer-order-1-unkeyed, writer-order-2-unkeyed | False |
| INSP-2837-C | [1, 2, 3, 4, 5] | [0, 1] | writer-order-1-unkeyed, writer-order-2-unkeyed | True |
| INSP-2837-D | [1, 2, 3, 4] | [0, 1] | writer-order-1-unkeyed, writer-order-2-unkeyed | True |

### Ordering run - keyed

| entity | processed seq order | partitions | writers | in order |
|---|---|---|---|---|
| INSP-2837-A | [1, 2, 3] | [1] | writer-order-2-keyed | True |
| INSP-2837-B | [1, 2, 3, 4, 5, 6, 7, 8] | [0] | writer-order-1-keyed | True |
| INSP-2837-C | [1, 2, 3, 4, 5] | [0] | writer-order-1-keyed | True |
| INSP-2837-D | [1, 2, 3, 4] | [1] | writer-order-2-keyed | True |
