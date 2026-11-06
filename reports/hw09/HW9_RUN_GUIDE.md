# HW9 run guide – Shashank Ranjan (SID4 2837, PREFIX s2837)

All commands from `C:\SJSURepo\Data260\Data260-2837\code` unless noted. Every log line prints
`Shashank Ranjan | s2837`, so terminal screenshots show your name. Start each screenshot with
`echo "Shashank Ranjan - HW9 - Part N"`.

## 0. One-time setup
```
pip install -r requirements_hw9.txt
cd ..  &&  docker compose up -d redis kafka  &&  cd code      (s2837-redis = Redis Stack with vector search)
docker exec s2837-redis redis-cli MODULE LIST                   (should list "search")
ollama list                                                      (qwen2.5:1.5b present; Ollama running)
```
MySQL `s2837_rel` must be running (same as HW4-HW7, root/sjsu2026). The first HW9 run adds
`restaurant_inspection.view_count` and seeds ten records `S2837-H9-0001..0010` (restaurants
from `hw9/agents/data/reference_data.json`). Override credentials with HW9_DB_USER /
HW9_DB_PASSWORD if yours differ.

## Part 1 – view counter
```
python -m web_application.hw9.view_counter
```
Screenshot also: `SELECT inspection_code, view_count FROM restaurant_inspection WHERE inspection_code='S2837-H9-0001';`
and `docker exec s2837-redis redis-cli GET s2837:views:inspection:<id>`.

## Part 2 – semantic cache in front of the HW8 agents
Start the HW8 agents (3 terminals, from `code\web_application\kafka_pipeline`):
`python planner.py`, `python writer.py`, `python reviewer.py`. Then:
```
python -m web_application.hw9.run_part2
```
If Kafka gives trouble: `python -m web_application.hw9.run_part2 --agent direct` (same HW8
plan/write/review functions in-process) – say which one you used in the report.
Optional API: `python -m uvicorn web_application.hw9_main:app --port 8138` then POST /qa.

## Part 3 – sweep, false hit, cost, stale answers
```
python -m web_application.hw9.run_part3 sweep      (~70 agent calls the first time; answers memoised in raw/part3_agent_memo.json)
python -m web_application.hw9.run_part3 stale
```
Commit `hw9/cache_cases.yaml` BEFORE running the sweep, and do not edit it afterwards
(use `hw9/cache_cases_errata.md` for any labeling mistake).
If no false hit appears at 0.85, add `--false-hit-threshold 0.80` (or 0.75).

## Part 4 – Answering + Evaluator agents
```
python -m web_application.hw9.agents.run_part4 all      (train -> validate -> test -> demo)
```
Writes `hw9/agents/data/lessons.json` (commit it) and raw/part4_*.json.

## Verify and build the report
```
python -m web_application.hw9.verify_hw09
python -m web_application.hw9.make_hw09_report
```
Open `reports/hw09/Ranjan_HW9_For_PDF.docx`, paste screenshots at the yellow markers, write the
AI Use section in your own words, add the hw9 commit hash (`git rev-parse HEAD`), export to PDF.

## Tag
```
git add -A && git commit -m "HW9" && git tag hw9 && git push && git push origin hw9
```
