#!/bin/bash
# Setup Vault with test secrets for the sample Lambda function

set -euo pipefail

VAULT_ADDR="${VAULT_ADDR:-http://vault.localhost.localstack.cloud:4566}"
VAULT_TOKEN="${VAULT_TOKEN:-root}"

echo "=== Setting up Vault secrets ==="
echo "VAULT_ADDR: $VAULT_ADDR"

# Wait for Vault to be ready
echo "Waiting for Vault to be ready..."
for i in {1..30}; do
    if curl -sf "$VAULT_ADDR/v1/sys/health" > /dev/null 2>&1; then
        echo "Vault is ready!"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "ERROR: Vault not ready after 30 seconds"
        exit 1
    fi
    sleep 1
done

# Create test secrets using the Vault HTTP API
echo "Creating test secrets at secret/data/myapp/config..."

curl -sf -X POST \
    -H "X-Vault-Token: $VAULT_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{
        "data": {
            "api_key": "sk-test-12345",
            "db_host": "localhost",
            "db_password": "supersecret",
            "feature_flags": "enable_new_ui,beta_features"
        }
    }' \
    "$VAULT_ADDR/v1/secret/data/myapp/config"

echo ""
echo "=== Verifying secret was created ==="

curl -sf \
    -H "X-Vault-Token: $VAULT_TOKEN" \
    "$VAULT_ADDR/v1/secret/data/myapp/config" | jq '.data.data | keys'

echo ""
echo "=== Creating Vault IAM auth role for Lambda ==="

# Create the IAM auth role that accepts Lambda functions from LocalStack
# This is needed because the extension's auto-creation may not work with older code
curl -sf -X POST \
    -H "X-Vault-Token: $VAULT_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{
        "auth_type": "iam",
        "bound_iam_principal_arn": ["arn:aws:iam::000000000000:role/vault-lambda-role"],
        "resolve_aws_unique_ids": false,
        "policies": ["default-lambda-policy"],
        "token_ttl": "24h",
        "token_max_ttl": "24h"
    }' \
    "$VAULT_ADDR/v1/auth/aws/role/default-lambda-role" || echo "(role may already exist)"

echo "IAM auth role 'default-lambda-role' configured"

echo ""
echo "=== Vault setup complete ==="
echo ""
echo "Secret path: secret/data/myapp/config"
echo "Keys: api_key, db_host, db_password, feature_flags"
echo "IAM auth role: default-lambda-role"
