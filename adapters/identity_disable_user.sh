#!/usr/bin/env bash
set -euo pipefail

USER_ID="${1:?usage: identity_disable_user.sh <user_identifier>}"

: "${IDENTITY_API_URL:?missing IDENTITY_API_URL}"
: "${IDENTITY_API_TOKEN:?missing IDENTITY_API_TOKEN}"

case "$USER_ID" in
  admin*|root|svc-*|service-*|breakglass*|emergency*)
    jq -n --arg user "$USER_ID" '{ok:false,mode:"live",message:"refused protected account",user:$user}'
    exit 0
    ;;
esac

curl -sS -X POST "$IDENTITY_API_URL" \
  -H "Authorization: Bearer $IDENTITY_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d "$(jq -n --arg user "$USER_ID" '{action:"disable_user", user:$user}')" |
jq -c '.'
