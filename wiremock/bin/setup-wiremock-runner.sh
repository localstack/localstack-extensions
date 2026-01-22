#!/bin/bash

# Setup WireMock Runner for LocalStack

set -e

MOCK_API_NAME="${MOCK_API_NAME:-wiremock}"
MOCK_API_PORT="${MOCK_API_PORT:-8080}"
WIREMOCK_DIR="${WIREMOCK_DIR:-.wiremock}"
STUBS_URL="${STUBS_URL:-https://library.wiremock.org/catalog/api/p/personio.de/personio-de-personnel/personio.de-personnel-stubs.json}"

echo "=== WireMock Runner Setup ==="

# Check prerequisites
if ! command -v wiremock &> /dev/null; then
    echo "Error: WireMock CLI not installed. Run: npm install -g wiremock"
    exit 1
fi

if ! wiremock mock-apis list &> /dev/null; then
    echo "Error: Not logged in. Run: wiremock login"
    exit 1
fi

echo "✓ CLI authenticated"

# Create Mock API
echo "Creating Mock API '${MOCK_API_NAME}'..."
wiremock mock-apis create "${MOCK_API_NAME}" 2>&1 || echo "Note: May already exist"

wiremock mock-apis list
echo ""
echo "Enter Mock API ID:"
read -r MOCK_API_ID

[ -z "$MOCK_API_ID" ] && { echo "Error: Mock API ID required"; exit 1; }

# Create config
mkdir -p "${WIREMOCK_DIR}/stubs/${MOCK_API_NAME}/mappings"

cat > "${WIREMOCK_DIR}/wiremock.yaml" << EOF
services:
  ${MOCK_API_NAME}:
    type: 'REST'
    name: '${MOCK_API_NAME}'
    port: ${MOCK_API_PORT}
    path: '/'
    cloud_id: '${MOCK_API_ID}'
EOF

echo "✓ Created ${WIREMOCK_DIR}/wiremock.yaml"

# Download stubs
TMP_STUBS_FILE="/tmp/wiremock-stubs.json"
curl -s -o "$TMP_STUBS_FILE" "$STUBS_URL"

if [ -f "$TMP_STUBS_FILE" ] && command -v jq &> /dev/null; then
    MAPPING_COUNT=$(jq '.mappings | length' "$TMP_STUBS_FILE" 2>/dev/null || jq 'length' "$TMP_STUBS_FILE" 2>/dev/null || echo "0")
    if [ "$MAPPING_COUNT" != "0" ] && [ "$MAPPING_COUNT" != "null" ]; then
        for i in $(seq 0 $((MAPPING_COUNT - 1))); do
            jq ".mappings[$i] // .[$i]" "$TMP_STUBS_FILE" > "${WIREMOCK_DIR}/stubs/${MOCK_API_NAME}/mappings/mapping-$i.json" 2>/dev/null
        done
        echo "✓ Extracted ${MAPPING_COUNT} stubs"
    fi
fi

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Start LocalStack with:"
echo "  LOCALSTACK_WIREMOCK_API_TOKEN=\"your-token\" \\"
echo "  LOCALSTACK_WIREMOCK_CONFIG_DIR=\"$(pwd)\" \\"
echo "  localstack start"
echo ""
echo "WireMock available at: http://wiremock.localhost.localstack.cloud:4566"
