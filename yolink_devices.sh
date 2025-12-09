#!/bin/bash
# Get device list from YoLink local hub
#
# Environment Variables:
#   YOLINK_URL: Base URL of the YoLink local hub (includes port)
#   YOLINK_TOKEN: Bearer token from yolink_token.sh

set -o pipefail

# Validate environment variables
if [[ -z "$YOLINK_URL" || -z "$YOLINK_TOKEN" ]]; then
    echo "Error: Missing required environment variables:" >&2
    [[ -z "$YOLINK_URL" ]] && echo "  - YOLINK_URL" >&2
    [[ -z "$YOLINK_TOKEN" ]] && echo "  - YOLINK_TOKEN" >&2
    exit 1
fi

API_URL="${YOLINK_URL}/open/yolink/v2/api"

echo "Fetching device list from ${API_URL}..." >&2

curl -s -X POST \
    --header 'Content-Type: application/json' \
    --header "Authorization: Bearer ${YOLINK_TOKEN}" \
    --data-raw '{"method":"Home.getDeviceList"}' \
    --insecure \
    "${API_URL}"

exit $?
