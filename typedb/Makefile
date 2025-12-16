VENV_BIN = python3 -m venv
VENV_DIR ?= .venv
VENV_ACTIVATE = $(VENV_DIR)/bin/activate
VENV_RUN = . $(VENV_ACTIVATE)

usage:          ## Shows usage for this Makefile
	@cat Makefile | grep -E '^[a-zA-Z_-]+:.*?## .*$$' | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

venv: $(VENV_ACTIVATE)

$(VENV_ACTIVATE): pyproject.toml
	test -d .venv || $(VENV_BIN) .venv
	$(VENV_RUN); pip install --upgrade pip setuptools plux
	$(VENV_RUN); pip install -e .[dev]
	touch $(VENV_DIR)/bin/activate

clean:
	rm -rf .venv/
	rm -rf build/
	rm -rf .eggs/
	rm -rf *.egg-info/

install: venv   ## Install dependencies
	$(VENV_RUN); python -m plux entrypoints

dist: venv      ## Create distribution
	$(VENV_RUN); python -m build

publish: clean-dist venv dist   ## Publish extension to pypi
	$(VENV_RUN); pip install --upgrade twine; twine upload dist/*

entrypoints: venv   ## Generate plugin entrypoints for Python package
	$(VENV_RUN); python -m plux entrypoints

format:		    ## Run ruff to format the codebase
	$(VENV_RUN); python -m ruff format .; make lint

lint:		    ## Run ruff to lint the codebase
	$(VENV_RUN); python -m ruff check --output-format=full .

test:		    ## Run integration tests (requires LocalStack running with the Extension installed)
	$(VENV_RUN); pytest tests $(PYTEST_ARGS)

clean-dist: clean
	rm -rf dist/

.PHONY: clean clean-dist dist install publish usage venv format test
