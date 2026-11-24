.PHONY: run setup-vault deploy test clean help

help:           ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

run: setup-vault deploy test   ## Run the full sample (setup, deploy, test)

setup-vault:    ## Create test secrets in Vault
	@echo "=== Setting up Vault secrets ==="
	./bin/setup-vault.sh

deploy:         ## Deploy Lambda with Vault extension layer
	@echo "=== Deploying Lambda with Vault Lambda Extension ==="
	./bin/deploy-lambda.sh

test:           ## Test the Lambda function
	@echo "=== Testing Lambda invocation ==="
	./bin/test-lambda.sh

clean:          ## Delete the Lambda function
	@echo "=== Cleaning up ==="
	awslocal lambda delete-function --function-name vault-test-function 2>/dev/null || true
	@echo "Done"
