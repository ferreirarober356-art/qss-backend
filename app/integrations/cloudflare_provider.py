import json
import os
import urllib.request
import urllib.error
from typing import Any, Dict


class CloudflareEnforcementError(Exception):
    pass


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _scope() -> tuple[str, str]:
    account_id = _env("CLOUDFLARE_ACCOUNT_ID")
    zone_id = _env("CLOUDFLARE_ZONE_ID")
    if account_id:
        return ("accounts", account_id)
    if zone_id:
        return ("zones", zone_id)
    raise CloudflareEnforcementError("Missing CLOUDFLARE_ACCOUNT_ID or CLOUDFLARE_ZONE_ID")


def _target(value: str) -> str:
    if ":" in value and "/" not in value:
        return "ip6"
    if "/" in value:
        return "ip_range"
    return "ip"


def execute_cloudflare_action(action_type: str, params: Dict[str, Any], dry_run: bool, note: str = "") -> Dict[str, Any]:
    if action_type != "block_ip":
        raise CloudflareEnforcementError(f"Unsupported Cloudflare action: {action_type}")

    target = (
        params.get("ip")
        or params.get("ip_address")
        or params.get("value")
        or params.get("cidr")
    )
    if not target:
        raise CloudflareEnforcementError("block_ip requires params.ip or params.ip_address or params.value")

    if dry_run:
        return {
            "provider": "cloudflare",
            "dry_run": True,
            "action_type": action_type,
            "target": target,
            "message": "Dry run only. No Cloudflare rule created."
        }

    token = _env("CLOUDFLARE_API_TOKEN")
    if not token:
        raise CloudflareEnforcementError("Missing CLOUDFLARE_API_TOKEN")

    scope_kind, scope_id = _scope()
    payload = {
        "configuration": {
            "target": _target(target),
            "value": target
        },
        "mode": "block",
        "notes": (note or "QSS autonomous approved block_ip execution")[:500]
    }

    url="https://api.cloudflare.com/client/v4/{}/{}/firewall/access_rules/rules".format(scope_kind, scope_id)
    req = urllib.request.Request(
        url=url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise CloudflareEnforcementError(f"Cloudflare HTTP {e.code}: {body}")
    except Exception as e:
        raise CloudflareEnforcementError(f"Cloudflare request failed: {e}")

    if not data.get("success"):
        raise CloudflareEnforcementError(f"Cloudflare API error: {json.dumps(data)}")

    result = data.get("result", {}) or {}
    return {
        "provider": "cloudflare",
        "dry_run": False,
        "action_type": action_type,
        "target": target,
        "rule_id": result.get("id"),
        "created_on": result.get("created_on"),
        "scope": result.get("scope"),
        "configuration": result.get("configuration"),
        "notes": result.get("notes"),
        "raw": result
    }
