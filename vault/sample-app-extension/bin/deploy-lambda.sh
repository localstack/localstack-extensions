#!/bin/bash
# Deploy the sample Lambda function with Vault Lambda Extension layer
#
# NOTE: This approach currently has issues with LocalStack - the extension
# cannot read environment variables. See README.md for details.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SAMPLE_APP_DIR="$(dirname "$SCRIPT_DIR")"
LAMBDA_DIR="$SAMPLE_APP_DIR/lambda"

FUNCTION_NAME="vault-test-function"
VAULT_ADDR="${VAULT_ADDR:-http://vault.localhost.localstack.cloud:4566}"
AWS_REGION="${AWS_DEFAULT_REGION:-us-east-1}"

# Public Vault Lambda Extension layer ARN from HashiCorp
# See: https://developer.hashicorp.com/vault/docs/deploy/aws/lambda-extension
# Detect architecture and use appropriate layer
ARCH=$(uname -m)
if [ "$ARCH" = "arm64" ] || [ "$ARCH" = "aarch64" ]; then
    VAULT_LAYER_VERSION="${VAULT_LAYER_VERSION:-12}"
    VAULT_LAYER_ARN="arn:aws:lambda:${AWS_REGION}:634166935893:layer:vault-lambda-extension-arm64:${VAULT_LAYER_VERSION}"
    LAMBDA_ARCH="arm64"
else
    VAULT_LAYER_VERSION="${VAULT_LAYER_VERSION:-24}"
    VAULT_LAYER_ARN="arn:aws:lambda:${AWS_REGION}:634166935893:layer:vault-lambda-extension:${VAULT_LAYER_VERSION}"
    LAMBDA_ARCH="x86_64"
fi

echo "=== Deploying Lambda function with Vault Lambda Extension ==="
echo "Detected architecture: $ARCH -> Lambda: $LAMBDA_ARCH"
echo "Using public layer: $VAULT_LAYER_ARN"
echo ""

# Create deployment package
echo "Creating deployment package..."
cd "$LAMBDA_DIR"
zip -q -r /tmp/vault-lambda.zip handler.py

# Create IAM role for Lambda
echo "Creating IAM role..."
awslocal iam create-role \
    --role-name vault-lambda-role \
    --assume-role-policy-document '{
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"Service": "lambda.amazonaws.com"},
            "Action": "sts:AssumeRole"
        }]
    }' 2>/dev/null || echo "Role already exists"

# Attach basic execution policy
awslocal iam attach-role-policy \
    --role-name vault-lambda-role \
    --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole 2>/dev/null || true

# Delete existing function if present
awslocal lambda delete-function --function-name "$FUNCTION_NAME" 2>/dev/null || true

echo "Creating Lambda function: $FUNCTION_NAME"

# Environment variables for the Vault Lambda Extension
# Required: VAULT_ADDR, VAULT_AUTH_PROVIDER, VAULT_AUTH_ROLE
# Optional: VAULT_SECRET_PATH_*, VAULT_SECRET_FILE_*
ENV_VARS=$(cat <<EOF
{
  "Variables": {
    "VAULT_ADDR": "${VAULT_ADDR}",
    "VAULT_AUTH_PROVIDER": "aws",
    "VAULT_AUTH_ROLE": "default-lambda-role",
    "VAULT_SECRET_PATH_MYAPP": "secret/data/myapp/config",
    "VAULT_SECRET_FILE_MYAPP": "/tmp/secrets/myapp"
  }
}
EOF
)

awslocal lambda create-function \
    --function-name "$FUNCTION_NAME" \
    --runtime python3.11 \
    --role arn:aws:iam::000000000000:role/vault-lambda-role \
    --handler handler.handler \
    --zip-file fileb:///tmp/vault-lambda.zip \
    --timeout 30 \
    --architectures "$LAMBDA_ARCH" \
    --layers "$VAULT_LAYER_ARN" \
    --environment "$ENV_VARS"

# Verify environment variables were set correctly
echo ""
echo "Verifying environment variables..."
awslocal lambda get-function-configuration --function-name "$FUNCTION_NAME" | jq '.Environment.Variables'

# Verify layer was attached
echo ""
echo "Verifying layer..."
awslocal lambda get-function-configuration --function-name "$FUNCTION_NAME" | jq '.Layers'

# Wait for function to be active
echo ""
echo "Waiting for function to be active..."
awslocal lambda wait function-active --function-name "$FUNCTION_NAME"

echo ""
echo "=== Lambda deployment complete ==="
echo ""
echo "Function: $FUNCTION_NAME"
echo "Architecture: $LAMBDA_ARCH"
echo "Layer: $VAULT_LAYER_ARN"
echo "Vault Address: $VAULT_ADDR"
echo ""
echo "To test: make test"
