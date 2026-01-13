#!/bin/bash

echo "Downloading WireMock stub definitions..."

# Define the URL for the stub definitions and the temporary file path
STUBS_URL="https://library.wiremock.org/catalog/api/p/personio.de/personio-de-personnel/personio.de-personnel-stubs.json"
TMP_STUBS_FILE="/tmp/personio-stubs.json"

# Define the WireMock server URL
WIREMOCK_URL="http://localhost:8080"

# Download the stub definitions
curl -s -o "$TMP_STUBS_FILE" "$STUBS_URL"

echo "Download complete. Stubs saved to $TMP_STUBS_FILE"
echo "Importing stubs into WireMock..."

# Send a POST request to WireMock's import endpoint with the downloaded file
curl -v -X POST -H "Content-Type: application/json" --data-binary "@$TMP_STUBS_FILE" "$WIREMOCK_URL/__admin/mappings/import"

echo ""
echo "WireMock stub import request sent."
