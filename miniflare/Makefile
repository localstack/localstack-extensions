VENV_BIN = python3 -m venv
VENV_DIR ?= .venv
VENV_ACTIVATE = $(VENV_DIR)/bin/activate
VENV_RUN = . $(VENV_ACTIVATE)

venv: $(VENV_ACTIVATE)

$(VENV_ACTIVATE): setup.py setup.cfg
	test -d .venv || $(VENV_BIN) .venv
	$(VENV_RUN); pip install --upgrade pip setuptools plux wheel
	$(VENV_RUN); pip install --upgrade black isort pyproject-flake8 flake8-black flake8-isort
	touch $(VENV_DIR)/bin/activate

clean:
	rm -rf .venv/
	rm -rf build/
	rm -rf .eggs/
	rm -rf *.egg-info/

lint:              		  ## Run code linter to check code style
	$(VENV_RUN); python -m pflake8 --show-source --ignore=E501 --exclude .venv,build

format:            		  ## Run black and isort code formatter
	$(VENV_RUN); python -m isort .; python -m black miniflare

install: venv
	$(VENV_RUN); python -m pip install -e .[dev]

dist: venv
	$(VENV_RUN); python setup.py sdist bdist_wheel

publish: clean-dist venv dist
	$(VENV_RUN); pip install --upgrade twine; twine upload dist/*

clean-dist: clean
	rm -rf dist/

.PHONY: clean clean-dist dist install publish
