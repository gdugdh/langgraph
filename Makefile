PYTHON := $(shell if [ -x .venv/bin/python ]; then echo .venv/bin/python; elif [ -x ../.venv/bin/python ]; then echo ../.venv/bin/python; elif [ -x ../../.venv/bin/python ]; then echo ../../.venv/bin/python; else echo python; fi)
PIP := $(PYTHON) -m pip

.PHONY: install run test benchmark

install:
	$(PIP) install -r requirements.txt

run:
	$(PYTHON) support_bot.py

test:
	$(PYTHON) -m unittest discover -s tests -v

benchmark:
	$(PYTHON) tests/run_duplicate_similarity_benchmark.py
