The details are in the "word/PDF" document. Here is the text version of the same document.


Execution flow
All commands were run from the code folder, in this order. The dashboard (Part 1) is shown first in this report because the assignment lists it first, but it was run last: it only displays the evidence produced by Parts 2, 3 and 4.
Step	Command	What it produced	Report section
1	docker compose up -d kafka redis  (MySQL and Ollama already running)	Kafka and Redis containers	Setup
2	python planner.py / python writer.py / python reviewer.py  (in web_application/kafka_pipeline, one terminal each)	The three HW8 agents listening; they now also write spans	Part 4.1
3	python -m web_application.hw10.smoke_test	Offline logic check only (fakes, temporary folder); not used as evidence	-
4	python -m web_application.hw10.run_part2 --pipeline kafka	raw/eval_results.json: scores for 3 end-to-end questions	Part 2
5	python -m web_application.hw10.run_part4 traces --pipeline kafka	raw/part4_traces.json: cache-miss, cache-hit and failed trace	Part 4.2
6	python -m web_application.hw10.run_part4 latency --pipeline kafka --n 50 --restart --flush-cache	Latency run started; I stopped it after 8 requests to do Part 3	Part 4.3
7	python -m web_application.hw10.build_eval_cases --pipeline kafka	eval_cases.json (20 Writer drafts), human_labels.csv with empty labels	Part 3.1
8	python -m web_application.hw10.label_cases	My 20 hand-assigned labels (no model involved)	Part 3.1
9	git add reports/hw10/eval_cases.json reports/hw10/human_labels.csv ; git commit	Freeze commit 84a305061e, before any judge score	Part 3.1
10	python -m web_application.hw10.run_part3	judge_scores.csv, raw/part3_validation.json (3 judge runs on the 20 drafts)	Part 3.2, 3.3
11	python -m web_application.hw10.run_part4 latency --pipeline kafka --n 50	Latency run resumed from request 9 and completed 50 confirmed misses; raw/part4_latency.json	Part 4.3
12	python -m web_application.hw10.verify_hw10	verification.json, 34 of 34 checks passed	Verification
13	python -m streamlit run web_application/hw10/dashboard.py --server.port 8139	Operations dashboard reading the files above	Part 1
14	python -m web_application.hw10.make_hw10_report	This report (METRICS.md and the Word file)	-

Part 1 - Streamlit operations dashboard
The dashboard (code/web_application/hw10/dashboard.py, port 8139) is a read-only operations and evidence view of the existing system. It reads the span file written by the request path and the agents, the evaluation and validation result files, and the HW9 Redis counters.

1.1 Summary page
Shows the request count, the semantic-cache hit rate with cache hits and cache misses as separate numbers, the error rate, and end-to-end latency (cache-miss and cache-hit p50/p95 kept apart). Under every metric the page states the time window (selectable: 15 minutes to all time, with the UTC bounds) and the data source.
Metric	Data source	Time window
Recent requests	spans.jsonl, root span (stage = request)	selected window
Cache hit rate, hits, misses	spans.jsonl, cache_lookup spans (attrs.cache_hit)	selected window
Error rate	spans.jsonl, spans with status = error	selected window
End-to-end latency	spans.jsonl, duration of the root request span	selected window
Lifetime hits / misses	Redis hash s2837:semcache:stats	since last cache flush
Stage latency table	raw/part4_latency.json (computed from spans)	the 50-request experiment

Caching: @st.cache_resource holds the one reusable Redis connection; @st.cache_data caches the parsed span file and result files, keyed on file modification time and size so they are re-read only when they change.
 
Screenshot - Part 1 Dashboard: Streamlit dashboard started on port 8139
 
Screenshot - Part 1.1 Summary page: request count, cache hit rate with hits and misses, error rate and end-to-end latency, each with its time window and data source
 
Screenshot - Part 1.1 Summary page (continued): stage latency over the 50 confirmed cache misses, with cache-hit latency reported separately
1.2 Evaluation page
Shows the scores by pipeline stage (Planner, Writer, Reviewer) and by case (trace_id), the case detail with reasons, the Part 3 judge validation (Spearman, mean absolute difference, repeatability, raw per-case table) and the interpretation.
 
Screenshot - Part 1.2 Evaluation page: Part 2 scores by pipeline stage and case, with the coordination interpretation
 
Screenshot - Part 1.2 Evaluation page: Part 3 judge validation, human label vs the three judge runs per draft
1.3 Trace lookup page
A trace_id input shows the request journey in stage order with start time, end time, duration, status and error for each stage. A cache hit shows a green CACHE HIT banner and only the cache_lookup stage; a cache miss shows the CACHE MISS banner and the full Kafka path; a failure shows the failing stage and its error.
Part 2 - Automated evaluation of the Kafka pipeline
2.1 Evaluation inputs and linkage
After a test question has gone through the pipeline, the evaluator reads s2837_tasks (plan), s2837_drafts (draft) and s2837_final (final answer) with a group-less Kafka consumer and joins the three messages on correlation_id. The original message values are stored with topic, partition, offset and timestamp in raw/eval_results.json, together with the judge settings, so an evaluation can be reproduced.
Bounds: the Kafka read stops at the end offsets captured at start or after 30 s; messages that are not JSON objects are counted and skipped; a missing or malformed plan/draft/final gives that criterion the status missing_input instead of blocking. Each Ollama call has a 180 s HTTP timeout, each GEval measurement a 240 s wall-clock limit, and after 3 consecutive failures the judge is marked unavailable and the remaining judgments are skipped.
found, stats = self.source.fetch([trace_id], start_offsets=start_offsets)  # bounded
messages = found.get(trace_id, {})          # {"plan":..., "draft":..., "final":...}
record["inputs"] = messages                 # original messages + topic/partition/offset
plan   = judge("plan_quality", plan_text(data["steps"]))
writer = judge("writer_helpfulness", data["draft"])
final  = judge("final_helpfulness", data["final"])
draft_same_metric = judge("final_helpfulness", data["draft"])   # baseline for improvement

2.2 Evaluation criteria and results
Scale for every criterion and for the human labels: 1 very poor, 2 poor, 3 acceptable, 4 good, 5 excellent. GEval scores 0-10 internally; the rubric defines five bands (0-2, 3-4, 5-6, 7-8, 9-10) that map to 1-5. For Final-vs-Draft Improvement the draft and the final answer are both scored with the same Final Answer Helpfulness metric so the two scores are comparable.
Case (trace_id)	Question	Plan Quality	Writer Helpfulness	Final Answer Helpfulness	Draft (final metric)	Final - draft
9c9ce44c-63fc-4f2e-a6ab-20403b3901bf	Taj Grill received a WARNING. What exactly must the owner fix, and by what date is the re-...	3	5	5	5	0
34903040-dc68-45f9-99c3-521482a694ef	What violations were found at Golden Dragon Bistro, and what does its FAIL status mean for...	3	5	5	5	0
312c88ab-ca80-4d99-8851-ddfc337fd704	Did Cafe Milano pass its latest inspection, and does it need a re-inspection?	3	5	5	5	0

Detail for trace_id 9c9ce44c-63fc-4f2e-a6ab-20403b3901bf:
Criterion	Saved fields
Plan Quality	score 3; reason: The plan steps are specific to the question (Taj Grill, score, re-inspection date) but step 2 is vague about 'determine the score' without referencing the county policy. The steps are logically ordered but lack specificity on how to calculate the re-inspection...
Writer Helpfulness	score 5; trace_id 9c9ce44c-63fc-4f2e-a6ab-20403b3901bf
Final Answer Helpfulness	score 5; final answer: Taj Grill received a WARNING due to violations of Cold-holding unit above 41°F and Prepared food missing date labels. The inspection was conducted on October 20, 2026, with a score of 78. According to the County policy, a score of 70-84 requires a re-inspectio...
Final-vs-Draft Improvement	draft 5, final 5, difference 0. The final answer is byte-identical to the Writer draft: the HW8 Reviewer is a rule-based gate (length, on-domain, no error text) that approves or rejects a draft but never rewrites it, so it cannot improve the text. Both texts received the same score, so there is no improvement.

What the scores indicate about coordination
Across 3 evaluated request(s) the mean scores on the 1-5 scale are: Plan Quality 3.0, Writer Helpfulness 5.0, Final Answer Helpfulness 5.0.
Planner -> Writer: the drafts score clearly higher than the plans. This suggests the Writer answers mostly from the facts in the question and gets little from the plan, so the Planner adds limited value in this hand-off.
Writer -> Reviewer: in 3 of 3 request(s) the final answer is identical to the draft. Final-minus-draft difference: 0 higher, 0 lower, 3 unchanged (mean 0.0).
The final answer did NOT improve on the draft. This is expected from the design: my HW8 Reviewer is a rule-based gate (length, on-domain, no error text) that approves or rejects but never edits, so the Reviewer cannot raise quality - it can only block a bad draft. Any non-zero difference between identical texts is judge noise.
Reviewer decisions in this set: 3 approved, 0 rejected.
The same evaluator also scored the Part 4 requests; over all 54 evaluated requests the means are Plan Quality 2.89, Writer Helpfulness 4.11, Final Answer Helpfulness 4.35, final minus draft 0.02.
 
Screenshot - Part 2.2: run_part2 console output, evaluator scores for the end-to-end test questions (saved to eval_results.json)
Part 3 - Validate the judge
3.1 Frozen evaluation cases
reports/hw10/eval_cases.json holds 20 Writer drafts produced by my pipeline for 20 restaurant-inspection questions (look-ups, date arithmetic, policy boundaries, comparisons, advice, and questions the database cannot answer). reports/hw10/human_labels.csv holds my hand-assigned 1-5 helpfulness label for each draft. I labeled them myself with label_cases.py, which shows only the question, the facts and the draft and never calls a model. Both files were committed before any judge score existed; run_part3.py refuses to start otherwise and records the commit and SHA-256 of both files, and verify_hw10.py checks they are unchanged.
File	Commit	Committed at	SHA-256 (first 16)
eval_cases.json	84a305061e5a	2026-11-14T23:24:38-08:00	99e764ef4cfe6e25
human_labels.csv	84a305061e5a	2026-11-14T23:24:38-08:00	7e25cd40329ecb5d
case_id,human_label,note
C01,5,Perfect match
C02,1,wrong answer about the re-inspection date. has to be within 30 days
C03,5,clearly mentioned about the violations
C04,5,very accurate
C05,5,excellent analysis
C06,5,correct calculation of re-inspection date
C07,4,did not mentioned cross contamination
C08,1,"factual wrong. 83 is less than 85, hene it is NOT a pass"
C09,5,correct calculation
C10,3,it is a pass but also mentioned there is warning whihc is not right
C11,1,wrong analysis. 97 is higher than 94 for Cafe Milano
C12,3,ok but missed the violations details
C13,5,all correct
C14,5,
C15,5,
C16,5,
C17,4,
C18,4,
C19,1,did not answer the main question
C20,5,

 
Screenshot - Part 3.1: hand-labeling a draft with label_cases.py (question, facts and draft are shown; I type the 1-5 label and a note)
 
Screenshot - Part 3.1: Git activity for reports/hw10/eval_cases.json (VS Code Git output) before the judge run
3.2 Judge scores vs human labels
Statistic	Value
Drafts	20
Spearman rank correlation (human vs judge run 1)	0.4063
Mean absolute difference (human vs judge run 1)	0.9
Human label distribution (1..5)	{'1': 4, '2': 0, '3': 2, '4': 3, '5': 11}
Judge score distribution run 1 (1..5)	{'1': 3, '2': 1, '3': 0, '4': 4, '5': 12}
Failed judge calls (of 60)	0

Raw per-case data (also in reports/hw10/judge_scores.csv), from which the statistics can be recomputed:
Case	Human	Judge run 1	Judge run 2	Judge run 3	|human - run 1|	Range across runs
C01	5	5	5	5	0	0
C02	1	5	5	5	4	0
C03	5	5	5	5	0	0
C04	5	4	4	4	1	0
C05	5	5	5	5	0	0
C06	5	5	5	5	0	0
C07	4	5	5	5	1	0
C08	1	1	1	1	0	0
C09	5	5	5	5	0	0
C10	3	2	2	2	1	0
C11	1	1	1	1	0	0
C12	3	4	4	4	1	0
C13	5	4	5	5	1	1
C14	5	5	5	5	0	0
C15	5	5	5	5	0	0
C16	5	4	4	4	1	0
C17	4	1	1	1	3	0
C18	4	5	5	5	1	0
C19	1	5	5	5	4	0
C20	5	5	5	5	0	0

 
Screenshot - Part 3.2 / 3.3: run_part3 console output, my label and the three judge runs for the 20 drafts
3.3 Repeatability
The judge ran three times on the same 20 drafts with identical inputs and settings (ollama:qwen3:4b (local), temperature 0, seed 2837).
Measure	Value
Drafts whose score changed in at least one run	1 of 20 (5.0%)
Pairwise comparisons that differ	2 of 60
Mean absolute change (all pairwise comparisons)	0.0333
Mean absolute change when a score changed	1.0
Maximum absolute change	1

Runs	Changed	Mean abs change	Max abs change
1 vs 2	1 of 20	0.05	1
1 vs 3	1 of 20	0.05	1
2 vs 3	0 of 20	0.0	0

Run	Spearman vs human	Mean abs difference vs human
1	0.4063	0.9
2	0.4687	0.85
3	0.4687	0.85

 
Screenshot - Part 3.3: run_part3 console, the frozen-file commit 84a305061e and the judge calls of the repeated runs on the same 20 drafts
Would I trust this judge to gate a deployment?
No - I would not let this judge gate a deployment yet. It misses 2 of my 5 criteria (Spearman vs human >= 0.7; Mean absolute difference <= 0.75).
My criterion	Measured	Met
Spearman vs human >= 0.7	0.4063	no
Mean absolute difference <= 0.75	0.9	no
Drafts whose score changed across 3 runs <= 10.0%	5.0	yes
Largest score change <= 1	1	yes
No failed judge calls	0	yes

Additional evidence I would require first:
•	A larger labeled set (100+ drafts) with enough 1-2 and 4-5 labels to test both ends of the scale.
•	A second human labeler and the human-human agreement, to know the ceiling the judge can reach.
•	Agreement on the gate decision itself (e.g. score >= 4 passes): false-pass and false-block rates, not only rank correlation.
•	Repeatability across days, after an Ollama/model update, and with a second judge model.
•	A check that the judge catches factual errors against s2837_rel (wrong score, status or date), since those are the costly mistakes in this domain.
Part 4 - Distributed tracing and latency analysis
4.1 Trace propagation
The trace_id is created once at the Q&A ingress (traced_qa.py) and sent to Kafka as the HW8 correlation_id, so there is one identifier and nothing to join: the cache lookup, every message on inbox, tasks, drafts and final, the dead-letter record and the evaluator all carry the same value. Each stage appends one JSON line to reports/hw10/raw/spans.jsonl. The Kafka agents write their spans in the shared loop (agent_base.py): a queue-wait span from the producer timestamp of the input record to the moment the agent received it, and a stage span from receipt until the output was acknowledged; a dead-lettered message gives a stage span with status error.
Stage	What the span measures
cache_lookup	embedding + Redis KNN + data-version check; attrs.cache_hit true / false separates the hit and miss paths
inbox / tasks / drafts / final	queue wait on that topic (produced -> consumed)
planner / writer / reviewer	agent work (received -> output acknowledged)
cache_store	writing the new answer to the semantic cache
evaluation	the GEval judge calls for the trace
request	root span: what the caller waited for

{
 "trace_id": "fd8c5f21-1153-4425-bf0b-6d4b924a219e",
 "stage": "writer",
 "start_time": "2026-11-15T05:29:29.955+00:00",
 "end_time": "2026-11-15T05:29:52.913+00:00",
 "duration_ms": 22958.0,
 "status": "ok",
 "error": null,
 "attrs": {
  "attempts": 1,
  "output_topics": [
   "s2837_drafts"
  ],
  "agent": "writer-1",
  "topic": "s2837_tasks",
  "partition": 0,
  "offset": 35
 }
}

•	python planner.py
 
Screenshot - Part 4.1: Planner console, the same correlation_id (= trace_id) read from s2837_inbox and sent to s2837_tasks
•	python writer.py
 
Screenshot - Part 4.1: Writer console, the same correlation_id read from s2837_tasks and sent to s2837_drafts
•	python reviewer.py
 
Screenshot - Part 4.1: Reviewer console, the same correlation_id read from s2837_drafts and sent to s2837_final
4.2 Trace examples
Example	trace_id	Path	Status	Stages recorded
Cache hit	0de4dddd-4404-4fc2-8ac2-a7594aac86ab	hit	ok	cache_lookup
Cache miss (completed agent path)	071fa4ea-43b8-49be-a94b-6bf7d584c982	miss	ok	cache_lookup -> inbox -> planner -> tasks -> writer -> drafts -> reviewer -> final -> cache_store -> evaluation
Failed	f8e1bfbc-c522-4e2c-b0b3-394273c7f3dc	miss	error	cache_lookup -> inbox -> planner -> tasks -> writer

Failed trace: the failing stage is writer and the error is "RuntimeError: injected failure in writer stage (HW10 failed-trace demo) (dead-lettered after 3 attempts)". The failure was triggered on purpose with a fault flag on the request (inject_failure = writer); the agent retried, dead-lettered the message to s2837_dead_letter and the client reported the failing stage.
Cache-miss trace 071fa4ea-43b8-49be-a94b-6bf7d584c982:
Stage	Start time	End time	Duration (ms)	Status	Error
cache_lookup	2026-11-15T05:49:59.158+00:00	2026-11-15T05:49:59.173+00:00	15.0	ok	
inbox	2026-11-15T05:49:59.194+00:00	2026-11-15T05:49:59.201+00:00	7.6	ok	
planner	2026-11-15T05:49:59.201+00:00	2026-11-15T05:50:17.100+00:00	17898.9	ok	
tasks	2026-11-15T05:50:17.085+00:00	2026-11-15T05:50:17.101+00:00	16.8	ok	
writer	2026-11-15T05:50:17.101+00:00	2026-11-15T05:50:31.257+00:00	14156.1	ok	
drafts	2026-11-15T05:50:31.242+00:00	2026-11-15T05:50:31.252+00:00	10.4	ok	
reviewer	2026-11-15T05:50:31.252+00:00	2026-11-15T05:50:31.284+00:00	32.1	ok	
final	2026-11-15T05:50:31.270+00:00	2026-11-15T05:50:31.280+00:00	10.9	ok	
cache_store	2026-11-15T05:50:31.282+00:00	2026-11-15T05:50:31.457+00:00	174.2	ok	
evaluation	2026-11-15T05:50:31.464+00:00	2026-11-15T05:53:01.483+00:00	150019.8	ok	

Cache-hit trace 0de4dddd-4404-4fc2-8ac2-a7594aac86ab:
Stage	Start time	End time	Duration (ms)	Status	Error
cache_lookup	2026-11-15T05:53:01.493+00:00	2026-11-15T05:53:01.519+00:00	25.9	ok	

Failed trace f8e1bfbc-c522-4e2c-b0b3-394273c7f3dc:
Stage	Start time	End time	Duration (ms)	Status	Error
cache_lookup	2026-11-15T05:53:01.523+00:00	2026-11-15T05:53:01.547+00:00	23.2	ok	
inbox	2026-11-15T05:53:01.561+00:00	2026-11-15T05:53:01.567+00:00	6.1	ok	
planner	2026-11-15T05:53:01.567+00:00	2026-11-15T05:53:10.451+00:00	8884.5	ok	
tasks	2026-11-15T05:53:10.431+00:00	2026-11-15T05:53:10.449+00:00	18.2	ok	
writer	2026-11-15T05:53:10.449+00:00	2026-11-15T05:53:12.005+00:00	1556.7	error	RuntimeError: injected failure in writer stage (HW10 failed-trace demo)

 
Screenshot - Part 4.2: run_part4 traces console output with the cache-miss, cache-hit and failed trace IDs
4.3 Stage-latency experiment
50 requests, each a confirmed cache miss: every request did the real semantic-cache lookup and returned is_cached = False (highest nearest-neighbour similarity 0.0, threshold 0.85). Experiment answers were not stored in the cache, so no request could be served by an earlier one; 0 candidate(s) were excluded (cache hit or failure) and replaced. End-to-end is measured from the start of the cache lookup to the end of the evaluation; the share column is the sum of the stage over all requests divided by the sum of end-to-end.
Stage	p50 (ms)	p95 (ms)	% of cache-miss end-to-end
Cache lookup	38.4	56.7	0.03
Planner	9096.6	13663.4	6.64
Writer	16031.1	24296.0	11.15
Reviewer	20.4	31.3	0.02
Queue wait (total)	30.3	52.0	0.03
Evaluation	117578.2	149696.7	82.15
Other (cache store, client overhead)	0.0	4.8	0.0
End-to-end (cache lookup -> evaluation end)	141323.0	178709.3	100.0
User-facing request (cache lookup -> answer)	25361.3	35212.4	16.62

Cache-hit latency (separate metric, not part of the table): p50 28.2 ms, p95 28.2 ms over 1 cache-hit request(s).
Over 50 confirmed cache misses the dominant contributor is Evaluation with 82.15% of the cache-miss end-to-end latency (p50 117578.2 ms, p95 149696.7 ms).
Optimize the evaluation first: it is off the user's critical path, so run it asynchronously (or sample requests), use one judge call that returns all criteria, skip the draft re-judgment when the final text is identical, or use a smaller judge model.
Cache hits are reported separately: p50 28.2 ms, p95 28.2 ms over 1 hit request(s).
 
Screenshot - Part 4.3: run_part4 latency console output, stage latency table over the 50 confirmed cache misses
Verification
 
Screenshot - Verification: verify_hw10 output, 34 of 34 checks passed

AI Use
1. What I used an AI assistant for and what I did myself: 
I used Claude to get the understanding of this assignment at high level and design the flow. This helped me to understand the architecture of this assignment.
2. One AI-produced output that was wrong: 
The judge design and ranking of the question was totally wrong. The question was “when will be the next inspection after the warning for a given date “ and the answer provided was provided for that day itself and NOT after 10 dyas.
3. How I detected it: 
I looked at the response and found out that it was NOT right based on the inspection policy.

