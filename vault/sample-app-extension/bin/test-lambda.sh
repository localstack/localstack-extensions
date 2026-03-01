#!/bin/bash
# Test the Lambda function's Vault integration via the Lambda Extension

set -euo pipefail

FUNCTION_NAME="vault-test-function"
OUTPUT_FILE="/tmp/vault-lambda-output.json"

echo "=== Testing Vault Lambda Extension ==="
echo ""

awslocal lambda invoke \
    --function-name "$FUNCTION_NAME" \
    "$OUTPUT_FILE" \
    --cli-read-timeout 60

echo ""
cat "$OUTPUT_FILE" | jq '.'

SUCCESS=$(cat "$OUTPUT_FILE" | jq -r '.success' 2>/dev/null)

echo ""
if [ "$SUCCESS" = "true" ]; then
    echo "✅ SUCCESS"
else
    echo "❌ FAILED"
    exit 1
fi

rm -f "$OUTPUT_FILE"
