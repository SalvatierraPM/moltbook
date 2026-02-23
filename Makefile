.PHONY: setup test ui-check verify

PYTHON ?= python3
VENV ?= .venv
PYTHON_BIN ?= $(PYTHON)

setup:
	$(PYTHON) -m venv $(VENV)
	. $(VENV)/bin/activate && python -m pip install --upgrade pip && python -m pip install -r requirements.lock && python -m pip install -e .

test:
	$(PYTHON_BIN) -m unittest discover -s tests -p 'test_*.py'

ui-check:
	node scripts/check_ui_coherence.js

verify:
	PYTHON_BIN=$(PYTHON_BIN) scripts/repro_check.sh
