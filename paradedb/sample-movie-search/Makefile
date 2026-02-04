.PHONY: install deploy init seed destroy clean help web-ui test-search get-api-url

help:
	@echo "ParadeDB Movie Search Sample App"
	@echo ""
	@echo "Usage:"
	@echo "  make install    - Install all dependencies"
	@echo "  make deploy     - Deploy CDK stack to LocalStack"
	@echo "  make init       - Initialize database schema and BM25 index"
	@echo "  make seed       - Load movie data from S3 into ParadeDB"
	@echo "  make web-ui     - Run the Web UI on localhost port 3000"
	@echo "  make destroy    - Tear down the stack"
	@echo "  make clean      - Remove build artifacts"
	@echo ""
	@echo "Quick start:"
	@echo "  make install && make deploy && make init && make seed && make web-ui"

install:
	@echo "Installing CDK dependencies..."
	npm install
	@echo "Installing Lambda dependencies..."
	cd lambda && npm install
	@echo "Done!"

deploy:
	@echo "Deploying MovieSearchStack to LocalStack..."
	cdklocal bootstrap
	cdklocal deploy --require-approval never
	@echo ""
	@echo "Deployment complete!"

init:
	@echo "Initializing database schema and BM25 index..."
	@API_URL=$$(awslocal cloudformation describe-stacks \
		--stack-name MovieSearchStack \
		--query 'Stacks[0].Outputs[?OutputKey==`ApiEndpoint`].OutputValue' \
		--output text 2>/dev/null); \
	if [ -z "$$API_URL" ]; then \
		echo "Error: Stack not deployed. Run 'make deploy' first."; \
		exit 1; \
	fi; \
	curl -s -X POST "$${API_URL}admin/init" | jq .
	@echo "Database initialized!"

seed:
	@echo "Seeding movie data from S3..."
	@API_URL=$$(awslocal cloudformation describe-stacks \
		--stack-name MovieSearchStack \
		--query 'Stacks[0].Outputs[?OutputKey==`ApiEndpoint`].OutputValue' \
		--output text 2>/dev/null); \
	if [ -z "$$API_URL" ]; then \
		echo "Error: Stack not deployed. Run 'make deploy' first."; \
		exit 1; \
	fi; \
	curl -s -X POST "$${API_URL}admin/seed" | jq .
	@echo "Data seeded!"

test-search:
	@echo "Testing search endpoint..."
	@API_URL=$$(awslocal cloudformation describe-stacks \
		--stack-name MovieSearchStack \
		--query 'Stacks[0].Outputs[?OutputKey==`ApiEndpoint`].OutputValue' \
		--output text 2>/dev/null); \
	if [ -z "$$API_URL" ]; then \
		echo "Error: Stack not deployed. Run 'make deploy' first."; \
		exit 1; \
	fi; \
	echo "Searching for 'redemption'..."; \
	curl -s "$${API_URL}search?q=redemption" | jq .

destroy:
	@echo "Destroying MovieSearchStack..."
	cdklocal destroy --force
	@echo "Stack destroyed!"

clean:
	rm -rf node_modules lambda/node_modules cdk.out dist
	@echo "Cleaned!"

get-api-url:
	@awslocal cloudformation describe-stacks \
		--stack-name MovieSearchStack \
		--query 'Stacks[0].Outputs[?OutputKey==`ApiEndpoint`].OutputValue' \
		--output text

web-ui:
	@echo "Starting Movie Search Web UI..."
	@echo "API endpoint: http://movie-search-api.execute-api.localhost.localstack.cloud:4566/dev"
	@echo ""
	@which serve > /dev/null 2>&1 || (echo "Installing serve..." && npm i -g serve)
	serve -s ./web -l 3000
