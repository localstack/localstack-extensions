VENV_BIN = python3 -m venv
VENV_DIR ?= .venv
VENV_ACTIVATE = $(VENV_DIR)/bin/activate
VENV_RUN = . $(VENV_ACTIVATE)

usage:          ## Show usage for this Makefile
	@cat Makefile | grep -E '^[a-zA-Z_-]+:.*?## .*$$' | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

venv: $(VENV_ACTIVATE)

$(VENV_ACTIVATE): pyproject.toml
	test -d .venv || $(VENV_BIN) .venv
	$(VENV_RUN); pip install --upgrade pip setuptools wheel build
	$(VENV_RUN); pip install -e .[dev,test]
	touch $(VENV_DIR)/bin/activate

clean:          ## Clean up build artifacts and virtual environment
	rm -rf .venv/
	rm -rf build/
	rm -rf .eggs/
	rm -rf *.egg-info/

install: venv   ## Install the package in development mode

dist: venv      ## Create distribution package
	$(VENV_RUN); python -m build

publish: clean-dist venv dist   ## Publish package to PyPI
	$(VENV_RUN); pip install --upgrade twine; twine upload dist/*

format: venv    ## Run ruff to format and fix the code
	$(VENV_RUN); python -m ruff format .; python -m ruff check --fix .

lint: venv      ## Run ruff to lint the code
	$(VENV_RUN); python -m ruff check --output-format=full .

test: venv      ## Run all tests
	$(VENV_RUN); python -m pytest tests/ -v

test-unit: venv ## Run unit tests only (no Docker required)
	$(VENV_RUN); python -m pytest tests/unit/ -v

test-integration: venv ## Run integration tests (Docker required)
	$(VENV_RUN); python -m pytest tests/integration/ -v

clean-dist: clean
	rm -rf dist/

.PHONY: clean clean-dist dist install publish usage venv format lint test test-unit test-integration
