# AI Use - HW8 (Shashank Ranjan, SID4 2837)

1. What I used an AI assistant for and what I did myself: I used Claude to draft the Kafka code for this homework (worker, request client, FastAPI wrapper, Planner/Writer/Reviewer agents, the failure-test runner, docker-compose, the smoke test and the report builder) on top of my existing HW1-HW7 repository. I did myself: computing my configuration (SID4 2837, PREFIX s2837, PORT_BASE 8137, VERIFY_SEED 262837), choosing Inspection as the primary entity and reusing my InspectionCreate schema, running Docker/Kafka and every experiment on my machine, taking the screenshots, checking each log and table against the raw files, and the final review of the report.

2. One AI-produced output that was wrong: the first version of the duplicate-delivery experiment reported 3 drafts for one replayed correlation_id instead of 2, which would have overstated the duplicate problem in the failure table.

3. How I detected it: I read every record on s2837_drafts with its writer instance and test tag. The extra draft came from my normal Part 2 writer (group s2837_writers), which was still running and also consumed the test message, because each consumer group receives every message on the topic.

4. What I changed and why it works now: every Part 3 test message now carries a test_run tag. Agents only handle messages whose tag matches their --test-run value and log IGNORED for everything else, and the runner counts only tagged outputs. Each experiment also uses its own consumer group. A rerun gave exactly 2 drafts before the fix and 1 after it. The same check (replayed_task_produces_no_second_draft) is part of verify_hw08.py.
