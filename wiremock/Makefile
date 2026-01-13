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

entrypoints: venv   # Generate plugin entrypoints for Python package
	$(VENV_RUN); python -m plux entrypoints

format:		    ## Run ruff to format the whole codebase
	$(VENV_RUN); python -m ruff format .; python -m ruff check --output-format=full --fix .

test:		    ## Run integration tests (requires LocalStack running with the Extension installed)
	$(VENV_RUN); pytest tests $(PYTEST_ARGS)

sample:		    ## Deploy sample app
	echo "Creating stubs in WireMock ..."
	bin/create-stubs.sh
	echo "Deploying sample app into LocalStack via Terraform ..."
	(cd sample-app; tflocal init; tflocal apply -auto-approve)
	apiId=$$(awslocal apigateway get-rest-apis | jq -r '.items[0].id'); \
	    endpoint=https://$$apiId.execute-api.us-east-1.localhost.localstack.cloud/dev/time-off; \
	    echo "Invoking local API Gateway endpoint: $$endpoint"; \
	    curl -k -v $$endpoint | grep time_off_date

clean-dist: clean
	rm -rf dist/

.PHONY: clean clean-dist dist install publish usage venv format test
