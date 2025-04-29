VENV_BIN = python3 -m venv
VENV_DIR ?= .venv
VENV_ACTIVATE = $(VENV_DIR)/bin/activate
VENV_RUN = . $(VENV_ACTIVATE)

venv: $(VENV_ACTIVATE)

$(VENV_ACTIVATE): setup.py setup.cfg
	test -d .venv || $(VENV_BIN) .venv
	$(VENV_RUN); pip install --upgrade pip setuptools plux
	$(VENV_RUN); pip install --upgrade black isort pyproject-flake8 flake8-black flake8-isort
	$(VENV_RUN); pip install -e .
	touch $(VENV_DIR)/bin/activate

clean:
	rm -rf .venv/
	rm -rf build/
	rm -rf .eggs/
	rm -rf *.egg-info/

install: venv
	$(VENV_RUN); python setup.py develop

lint:              		  ## Run code linter to check code style
	($(VENV_RUN); python -m pflake8 --show-source)

format:            		  ## Run black and isort code formatter
	$(VENV_RUN); python -m isort .; python -m black .

dist: venv
	$(VENV_RUN); python setup.py sdist bdist_wheel

publish: clean-dist venv dist
	$(VENV_RUN); pip install --upgrade twine; twine upload dist/*

clean-dist: clean
	rm -rf dist/

.PHONY: clean clean-dist dist install publish
