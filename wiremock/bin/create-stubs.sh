#!/bin/bash

# Import stubs into OSS WireMock (for WireMock Runner, use setup-wiremock-runner.sh)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCAL_STUBS_FILE="${SCRIPT_DIR}/../sample-app-oss/stubs.json"
STUBS_URL="${STUBS_URL:-https://library.wiremock.org/catalog/api/p/personio.de/personio-de-personnel/personio.de-personnel-stubs.json}"
TMP_STUBS_FILE="/tmp/personio-stubs.json"
WIREMOCK_URL="${WIREMOCK_URL:-http://wiremock.localhost.localstack.cloud:4566}"

# Use bundled stubs file if available, otherwise try to download from remote
if [ -f "$LOCAL_STUBS_FILE" ]; then
  echo "Using bundled stubs file: ${LOCAL_STUBS_FILE}"
  TMP_STUBS_FILE="$LOCAL_STUBS_FILE"
else
  echo "Downloading stubs from ${STUBS_URL}..."
  curl -sf -o "$TMP_STUBS_FILE" "$STUBS_URL" || { echo "ERROR: Failed to download stubs from ${STUBS_URL}"; exit 1; }
fi

echo "Importing stubs into WireMock at ${WIREMOCK_URL}..."
curl -v -X POST -H "Content-Type: application/json" --data-binary "@$TMP_STUBS_FILE" "${WIREMOCK_URL}/__admin/mappings/import"

echo ""
echo "Verify stubs at: ${WIREMOCK_URL}/__admin/mappings"
