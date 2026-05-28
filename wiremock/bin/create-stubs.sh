#!/bin/bash

# Import stubs into OSS WireMock (for WireMock Runner, use setup-wiremock-runner.sh)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STUBS_FILE="${SCRIPT_DIR}/../sample-app-oss/stubs.json"
WIREMOCK_URL="${WIREMOCK_URL:-http://wiremock.localhost.localstack.cloud:4566}"

# Note: stubs are bundled locally because library.wiremock.org now redirects to HTML
# rather than serving the JSON file directly, making the remote URL unreliable.
echo "Importing stubs into WireMock at ${WIREMOCK_URL}..."
curl -v -X POST -H "Content-Type: application/json" --data-binary "@$STUBS_FILE" "${WIREMOCK_URL}/__admin/mappings/import"

echo ""
echo "Verify stubs at: ${WIREMOCK_URL}/__admin/mappings"
