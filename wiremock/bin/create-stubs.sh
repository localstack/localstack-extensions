#!/bin/bash

# Import stubs into OSS WireMock (for WireMock Runner, use setup-wiremock-runner.sh)

STUBS_URL="${STUBS_URL:-https://library.wiremock.org/catalog/api/p/personio.de/personio-de-personnel/personio.de-personnel-stubs.json}"
TMP_STUBS_FILE="/tmp/personio-stubs.json"
WIREMOCK_URL="${WIREMOCK_URL:-http://wiremock.localhost.localstack.cloud:4566}"

echo "Downloading stubs from ${STUBS_URL}..."
curl -s -o "$TMP_STUBS_FILE" "$STUBS_URL"

echo "Importing stubs into WireMock at ${WIREMOCK_URL}..."
curl -v -X POST -H "Content-Type: application/json" --data-binary "@$TMP_STUBS_FILE" "${WIREMOCK_URL}/__admin/mappings/import"

echo ""
echo "Verify stubs at: ${WIREMOCK_URL}/__admin/mappings"
