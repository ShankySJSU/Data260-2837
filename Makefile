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
