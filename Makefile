# DATA-260 HW8 helpers (Windows without make: run the python commands directly from code/)
PY ?= python

up:
	docker compose up -d --build

topics:
	cd code && $(PY) web_application/kafka_pipeline/create_topics.py

demo:
	cd code && $(PY) web_application/kafka_pipeline/homework_demo.py

failures:
	cd code && $(PY) web_application/kafka_pipeline/run_hw08_failures.py all

verify-hw08:
	cd code && $(PY) -m web_application.verify_hw08

report-hw08:
	cd code && $(PY) -m web_application.make_hw08_report

# ---------------- DATA-260 HW9 ----------------
redis:
	docker compose up -d redis

hw9-part1:
	cd code && $(PY) -m web_application.hw9.view_counter

hw9-part2:
	cd code && $(PY) -m web_application.hw9.run_part2

hw9-part3:
	cd code && $(PY) -m web_application.hw9.run_part3 all

hw9-part4:
	cd code && $(PY) -m web_application.hw9.agents.run_part4 all

verify-hw09:
	cd code && $(PY) -m web_application.hw9.verify_hw09

report-hw09:
	cd code && $(PY) -m web_application.hw9.make_hw09_report
