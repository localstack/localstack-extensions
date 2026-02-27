VENV_BIN = python3 -m venv
VENV_DIR ?= .venv
VENV_ACTIVATE = $(VENV_DIR)/bin/activate
VENV_RUN = . $(VENV_ACTIVATE)
TEST_PATH ?= tests

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
	$(VENV_RUN); pytest $(PYTEST_ARGS) $(TEST_PATH)

deploy:		    ## Deploy the sample app CDK stack
	cd sample-app/cdk && pip install -r requirements.txt && cdklocal bootstrap && cdklocal deploy --all --require-approval never

test-sample:    ## Run sample app API tests (requires LocalStack running with deployed stack)
	@echo "Getting token from Keycloak..."
	@TOKEN=$$(curl -s -X POST \
		"http://keycloak.localhost.localstack.cloud:4566/realms/localstack/protocol/openid-connect/token" \
		-d "grant_type=client_credentials" \
		-d "client_id=localstack-client" \
		-d "client_secret=localstack-client-secret" | jq -r '.access_token') && \
	API_ID=$$(awslocal apigateway get-rest-apis --query 'items[0].id' --output text) && \
	API_URL="http://localhost:4566/_aws/execute-api/$${API_ID}/prod" && \
	echo "API URL: $${API_URL}" && \
	echo "\n=== List users ===" && \
	curl -s -H "Authorization: Bearer $${TOKEN}" "$${API_URL}/users" | jq . && \
	echo "\n=== Create user ===" && \
	curl -s -X POST "$${API_URL}/users" \
		-H "Authorization: Bearer $${TOKEN}" \
		-H "Content-Type: application/json" \
		-d '{"username": "testuser", "email": "test@example.com", "name": "Test User"}' | jq . && \
	echo "\n=== Get user ===" && \
	curl -s -H "Authorization: Bearer $${TOKEN}" "$${API_URL}/users/testuser" | jq . && \
	echo "\n=== Delete user ===" && \
	curl -s -X DELETE -H "Authorization: Bearer $${TOKEN}" "$${API_URL}/users/testuser" | jq . && \
	echo "\n=== Sample app tests completed ==="

clean-dist: clean
	rm -rf dist/

.PHONY: clean clean-dist dist install publish usage venv format test lint entrypoints deploy test-sample
