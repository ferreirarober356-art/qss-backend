#!/usr/bin/env bash
set -euo pipefail

HOST_ID="${1:?usage: edr_isolate_host.sh <host_identifier>}"

: "${EDR_API_URL:?missing EDR_API_URL}"
: "${EDR_API_TOKEN:?missing EDR_API_TOKEN}"

case "$HOST_ID" in
  dc-*|jump-*|backup-*|hypervisor-*|prod-core-*)
    jq -n --arg host "$HOST_ID" '{ok:false,mode:"live",message:"refused protected host",host:$host}'
    exit 0
    ;;
esac

curl -sS -X POST "$EDR_API_URL" \
  -H "Authorization: Bearer $EDR_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d "$(jq -n --arg host "$HOST_ID" '{action:"isolate_host", host:$host}')" |
jq -c '.'
