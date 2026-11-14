# HW10 run guide - Shashank Ranjan (PREFIX s2837)

All commands run from `code/`. trace_id = HW8 correlation_id everywhere.

## 0. One-time setup
```
pip install -r web_application/hw10/requirements_hw10.txt
ollama pull qwen3:4b            # local judge (HW10_JUDGE_MODEL changes it)
python -m web_application.hw10.smoke_test     # offline logic check, writes to a temp folder
```

## 1. Start the system (same as HW8/HW9)
```
docker compose up -d kafka redis        # + MySQL s2837_rel, + Ollama
python web_application/kafka_pipeline/create_topics.py
python web_application/kafka_pipeline/planner.py      # terminal 1
python web_application/kafka_pipeline/writer.py       # terminal 2
python web_application/kafka_pipeline/reviewer.py     # terminal 3
```
Restart the three agents after pulling this code: agent_base.py now writes the spans.

## 2. Run order
| Step | Command | Output |
|---|---|---|
| Part 2 | `python -m web_application.hw10.run_part2` | raw/eval_results.json |
| Part 3.1 | `python -m web_application.hw10.build_eval_cases` | eval_cases.json, human_labels.csv (empty labels) |
| Part 3.1 | `python -m web_application.hw10.label_cases` | I type a 1-5 label for each draft |
| Part 3.1 | `git add reports/hw10/eval_cases.json reports/hw10/human_labels.csv` then `git commit` | frozen BEFORE any judge score |
| Part 3.2/3.3 | `python -m web_application.hw10.run_part3` | judge_scores.csv, raw/part3_validation.json |
| Part 4.2 | `python -m web_application.hw10.run_part4 traces` | raw/part4_traces.json (hit, miss, failed) |
| Part 4.3 | `python -m web_application.hw10.run_part4 latency` | raw/part4_latency.json (50 misses, resumable) |
| Check | `python -m web_application.hw10.verify_hw10` | verification.json |
| Part 1 | `python -m streamlit run web_application/hw10/dashboard.py --server.port 8139` | dashboard |
| Report | `python -m web_application.hw10.make_hw10_report` | METRICS.md, Ranjan_HW10_For_PDF.docx |

Evaluate any earlier request again: `python -m web_application.hw10.evaluator --trace-id <id>`.

## Notes
- Human labels are mine. No script writes a label; label_cases.py refuses to run once judge
  scores exist; run_part3.py refuses to run until both files are committed.
- The 4.3 run takes long on CPU (50 pipeline runs + 4 judge calls each). It can be stopped
  and restarted; finished requests are kept. `--flush-cache` empties the semantic cache if
  too many candidates are served from it.
- `--pipeline direct` and `HW10_JUDGE=mock` exist only for debugging; verify_hw10.py fails
  results produced with them.
