import re
from typing import Tuple, List

MONEY_RE = re.compile(
    r"\$([\d,]+(?:\.\d+)?)\s*(million|billion|m|bn)?",
    re.IGNORECASE
)

KEYWORD_TAGS = {
    "kickback": ["kickback", "bribe", "bribery"],
    "overbilling": ["overbill", "inflated invoice", "overcharge", "billing scheme"],
    "bid_rigging": ["bid rig", "bid-rig", "collusion", "price fixing"],
    "false_claims": ["false claims act", "fca"],
    "procurement": ["procurement", "contract", "purchase order", "invoice"],
    "grant_fraud": ["grant", "award", "subrecipient"],
    "healthcare": ["medicare", "medicaid"],
    "disaster_fraud": ["fema", "disaster", "emergency"],
    "cyber": ["cyber", "hacking", "ransomware"],
}

AGENCY_HINTS = [
    ("DoD", ["department of defense", "dod", "army", "navy", "air force", "defense"]),
    ("DOE", ["department of energy", "doe"]),
    ("VA", ["department of veterans affairs", "va"]),
    ("HHS", ["hhs", "health and human services", "medicare", "medicaid"]),
    ("DHS", ["department of homeland security", "dhs", "fema"]),
    ("GSA", ["general services administration", "gsa"]),
    ("DOJ", ["department of justice", "doj"]),
]

def extract_amount_usd(text: str) -> float | None:
    if not text:
        return None
    matches = MONEY_RE.findall(text)
    if not matches:
        return None
    # take the largest mentioned number
    best = 0.0
    for num_s, scale in matches:
        num = float(num_s.replace(",", ""))
        s = (scale or "").lower()
        if s in ("million", "m"):
            num *= 1_000_000
        elif s in ("billion", "bn"):
            num *= 1_000_000_000
        best = max(best, num)
    return best if best > 0 else None

def guess_tags(title: str, body: str) -> List[str]:
    t = f"{title}\n{body}".lower()
    tags = []
    for tag, kws in KEYWORD_TAGS.items():
        if any(k in t for k in kws):
            tags.append(tag)
    return tags

def guess_agency(title: str, body: str) -> str:
    t = f"{title}\n{body}".lower()
    for agency, kws in AGENCY_HINTS:
        if any(k in t for k in kws):
            return agency
    return ""

