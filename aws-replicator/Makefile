VENV_BIN = python3 -m venv
VENV_DIR ?= .venv
VENV_ACTIVATE = $(VENV_DIR)/bin/activate
VENV_RUN = . $(VENV_ACTIVATE)
TEST_PATH ?= tests
PIP_CMD ?= pip

usage:                    ## Show this help
	@grep -Fh "##" $(MAKEFILE_LIST) | grep -Fv fgrep | sed -e 's/:.*##\s*/##/g' | awk -F'##' '{ printf "%-25s %s\n", $$1, $$2 }'

venv: $(VENV_ACTIVATE)

$(VENV_ACTIVATE): setup.py setup.cfg
	test -d .venv || $(VENV_BIN) .venv
	$(VENV_RUN); pip install --upgrade pip setuptools plux wheel
	$(VENV_RUN); pip install --upgrade black isort pyproject-flake8 flake8-black flake8-isort
	$(VENV_RUN); pip install -e .
	touch $(VENV_DIR)/bin/activate

clean:
	rm -rf .venv/
	rm -rf build/
	rm -rf .eggs/
	rm -rf *.egg-info/

lint:
	$(VENV_RUN); python -m pflake8 --show-source

format:
	$(VENV_RUN); python -m isort .; python -m black .

install: venv
	$(VENV_RUN); $(PIP_CMD) install -e ".[test]"

test: venv
	$(VENV_RUN); python -m pytest $(TEST_PATH)

dist: venv
	$(VENV_RUN); python setup.py sdist bdist_wheel

build:   ## Build the extension
	mkdir -p build
	cp -r setup.py setup.cfg README.md aws_replicator build/
	(cd build && python setup.py sdist)

enable: $(wildcard ./build/dist/localstack_extension_aws_replicator-*.tar.gz)  ## Enable the extension in LocalStack
	$(VENV_RUN); \
		pip uninstall --yes localstack-extension-aws-replicator; \
		localstack extensions -v install file://$?

publish: clean-dist venv dist
	$(VENV_RUN); pip install --upgrade twine; twine upload dist/*

clean-dist: clean
	rm -rf dist/

.PHONY: build clean clean-dist dist install publish test
