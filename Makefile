.PHONY: install install-dev lint lint-fix typecheck test coverage ci clean docs docs-serve

PYTHON ?= python

install:
	$(PYTHON) -m pip install -e .

install-dev:
	$(PYTHON) -m pip install -e ".[dev,runtime]"
	$(PYTHON) -m pip install pre-commit mkdocs-material pymdown-extensions
	pre-commit install

lint:
	ruff check swarm/ tests/

lint-fix:
	ruff check --fix swarm/ tests/

typecheck:
	mypy swarm/

test:
	pytest tests/ -v

coverage:
	pytest tests/ --cov=swarm --cov-report=term-missing --cov-report=html

ci: lint typecheck coverage

docs:
	mkdocs build --strict

docs-serve:
	mkdocs serve

clean:
	rm -rf .mypy_cache .pytest_cache .ruff_cache htmlcov .coverage site/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +
