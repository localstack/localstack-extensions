VENV_BIN = python3 -m venv
VENV_DIR ?= .venv
VENV_ACTIVATE = $(VENV_DIR)/bin/activate
VENV_RUN = . $(VENV_ACTIVATE)
TEST_PATH ?= tests
PIP_CMD ?= pip
FRONTEND_FOLDER = aws_proxy/frontend
COREPACK_EXISTS := $(shell command -v corepack)
YARN_EXISTS := $(shell command -v yarn)

usage:          ## Show this help
	@grep -Fh "##" $(MAKEFILE_LIST) | grep -Fv fgrep | sed -e 's/:.*##\s*/##/g' | awk -F'##' '{ printf "%-25s %s\n", $$1, $$2 }'

clean:          ## Clean up
	rm -rf .venv/
	rm -rf build/
	rm -rf .eggs/
	rm -rf *.egg-info/

format:				## Run ruff to format the whole codebase
	($(VENV_RUN); python -m ruff format .; python -m ruff check --output-format=full --fix .)

lint:				## Run code linter to check code style
	($(VENV_RUN); python -m ruff check --output-format=full . && python -m ruff format --check .)

test:               ## Run tests
	$(VENV_RUN); python -m pytest $(PYTEST_ARGS) $(TEST_PATH)

entrypoints: install build-frontend ## Generate plugin entrypoints for Python package
	$(VENV_RUN); pip install --upgrade plux; python -m plux entrypoints --exclude '**/node_modules/**'

install-build-deps: venv ## Install build dependencies
	$(VENV_RUN); pip install --upgrade build setuptools wheel plux setuptools_scm

build: install-build-deps build-frontend entrypoints ## Build the extension
	$(VENV_RUN); python -m build --no-isolation . --outdir dist
	@# make sure that the entrypoints are contained in the dist folder and are non-empty
	@test -s localstack_extension_aws_proxy.egg-info/entry_points.txt || (echo "Entrypoints were not correctly created! Aborting!" && exit 1)

enable: $(wildcard ./dist/localstack_extension_aws_proxy-*.tar.gz)  ## Enable the extension in LocalStack
	$(VENV_RUN); \
		pip uninstall --yes localstack-extension-aws-proxy; \
		localstack extensions -v install file://$?

publish: clean-dist venv build
	$(VENV_RUN); pip install --upgrade twine; twine upload dist/*

check-frontend-deps:
	@if [ -z "$(YARN_EXISTS)" ]; then \
		npm install --global yarn; \
	fi
	@if [ -z "$(COREPACK_EXISTS)" ]; then \
		npm install -g corepack; \
	fi

install-frontend: check-frontend-deps  ## Install dependencies of the frontend
	cd $(FRONTEND_FOLDER) && yarn install

build-frontend: # Build the React app
	@if [ ! -d "$(FRONTEND_FOLDER)/node_modules" ]; then \
		$(MAKE) install-frontend; \
	fi
	cd $(FRONTEND_FOLDER); rm -rf build && NODE_ENV=prod npm run build

start-frontend: ## Start the frontend in dev mode (hot reload)
	cd $(FRONTEND_FOLDER); yarn start

venv:
	test -d .venv || $(VENV_BIN) .venv

install: install-frontend venv     ## Install dependencies
	$(VENV_RUN); pip install -e .
	$(VENV_RUN); pip install -e .[test]
	touch $(VENV_DIR)/bin/activate

clean-dist: clean
	rm -rf dist/

.PHONY: build clean clean-dist dist install publish test
