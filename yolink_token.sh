#!/bin/bash
# Fetch authentication token from YoLink local hub
#
# Environment Variables:
#   YOLINK_URL: Base URL of the YoLink local hub (includes port)
#   YOLINK_CLIENT_ID: OAuth client ID
#   YOLINK_CLIENT_SECRET: OAuth client secret

set -o pipefail

# Validate environment variables
if [[ -z "$YOLINK_URL" || -z "$YOLINK_CLIENT_ID" || -z "$YOLINK_CLIENT_SECRET" ]]; then
    echo "Error: Missing required environment variables:" >&2
    [[ -z "$YOLINK_URL" ]] && echo "  - YOLINK_URL" >&2
    [[ -z "$YOLINK_CLIENT_ID" ]] && echo "  - YOLINK_CLIENT_ID" >&2
    [[ -z "$YOLINK_CLIENT_SECRET" ]] && echo "  - YOLINK_CLIENT_SECRET" >&2
    exit 1
fi

TOKEN_URL="${YOLINK_URL}/open/yolink/token"

echo "Requesting token from ${TOKEN_URL}..." >&2

RESPONSE=$(curl -s -X POST \
    -d "grant_type=client_credentials&client_id=${YOLINK_CLIENT_ID}&client_secret=${YOLINK_CLIENT_SECRET}" \
    --insecure \
    "${TOKEN_URL}")

# Extract the token from the response
# Try jq first, fall back to grep/sed if jq is not available
if command -v jq &> /dev/null; then
    TOKEN=$(echo "$RESPONSE" | jq -r '.access_token' 2>/dev/null)
else
    # Fallback: use grep and sed
    TOKEN=$(echo "$RESPONSE" | grep -o '"access_token"[^,]*' | cut -d'"' -f4)
fi

if [[ -z "$TOKEN" ]]; then
    echo "Error: Failed to obtain token" >&2
    echo "Response: $RESPONSE" >&2
    exit 1
fi

echo ""
echo "Please add :"
echo "export YOLINK_TOKEN=${TOKEN}"
echo "to your shell"
echo ""

exit 0
