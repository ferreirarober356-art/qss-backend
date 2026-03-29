#!/usr/bin/env bash
set -euo pipefail

IP="${1:?usage: firewall_block_ip.sh <ip>}"

: "${FIREWALL_API_URL:?missing FIREWALL_API_URL}"
: "${FIREWALL_API_TOKEN:?missing FIREWALL_API_TOKEN}"

case "$IP" in
  10.*|127.*|172.16.*|172.17.*|172.18.*|172.19.*|172.2*|172.30.*|172.31.*|192.168.*)
    jq -n --arg ip "$IP" '{ok:false,mode:"live",message:"refused private/internal IP",ip:$ip}'
    exit 0
    ;;
esac

curl -sS -X POST "$FIREWALL_API_URL" \
  -H "Authorization: Bearer $FIREWALL_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d "$(jq -n --arg ip "$IP" '{action:"block_ip", ip:$ip}')" |
jq -c '.'
