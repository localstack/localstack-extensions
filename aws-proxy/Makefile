VENV_BIN = python3 -m venv
VENV_DIR ?= .venv
VENV_ACTIVATE = $(VENV_DIR)/bin/activate
VENV_RUN = . $(VENV_ACTIVATE)
TEST_PATH ?= tests
PIP_CMD ?= pip

usage:          ## Show this help
	@grep -Fh "##" $(MAKEFILE_LIST) | grep -Fv fgrep | sed -e 's/:.*##\s*/##/g' | awk -F'##' '{ printf "%-25s %s\n", $$1, $$2 }'

install:        ## Install dependencies
	test -d .venv || $(VENV_BIN) .venv
	$(VENV_RUN); pip install -e .[test]
	touch $(VENV_DIR)/bin/activate

clean:          ## Clean up
	rm -rf .venv/
	rm -rf build/
	rm -rf .eggs/
	rm -rf *.egg-info/

format:				## Run ruff to format the whole codebase
	($(VENV_RUN); python -m ruff format .; python -m ruff check --output-format=full --fix .)

lint:				## Run code linter to check code style
	($(VENV_RUN); python -m ruff check --output-format=full . && python -m ruff format --check .)

test: venv          ## Run tests
	$(VENV_RUN); python -m pytest $(PYTEST_ARGS) $(TEST_PATH)

dist: venv          ## Create distribution package
	$(VENV_RUN); python setup.py sdist bdist_wheel

build:              ## Build the extension
	mkdir -p build
	cp -r setup.py setup.cfg README.md aws_proxy build/
	(cd build && python setup.py sdist)

enable: $(wildcard ./build/dist/localstack_extension_aws_proxy-*.tar.gz)  ## Enable the extension in LocalStack
	$(VENV_RUN); \
		pip uninstall --yes localstack-extension-aws-proxy; \
		localstack extensions -v install file://$?

publish: clean-dist venv dist
	$(VENV_RUN); pip install --upgrade twine; twine upload dist/*

clean-dist: clean
	rm -rf dist/

.PHONY: build clean clean-dist dist install publish test
