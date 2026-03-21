from __future__ import annotations
from dataclasses import dataclass

@dataclass
class TypologyMatch:
    typology: str
    confidence: float
    evidence: str

RULES = [
    ("kickbacks", 0.90, ["kickback", "bribe", "bribery", "illegal gratuities"]),
    ("overbilling", 0.85, ["overbill", "overcharged", "inflated invoice", "billing scheme", "false billing"]),
    ("bid_rigging", 0.90, ["bid rig", "bid-rig", "collusion", "price fixing", "bid rotation"]),
    ("false_claims_act", 0.95, ["false claims act", "fca"]),
    ("procurement_fraud", 0.80, ["procurement", "contract", "purchase order", "invoice", "contracting"]),
    ("grant_fraud", 0.80, ["grant", "subrecipient", "award funds", "grant program"]),
    ("ppp_fraud", 0.90, ["ppp", "paycheck protection program"]),
    ("healthcare_fraud", 0.80, ["medicare", "medicaid", "medical testing", "hospital", "physician"]),
    ("small_business_setaside", 0.85, ["small business", "set-aside", "sdvosb", "8(a)", "hubzone"]),
    ("foreign_sourcing", 0.75, ["foreign-flagged", "foreign", "made in", "country of origin"]),
    ("money_laundering", 0.75, ["money laundering", "laundered", "shell company"]),
]

def classify(title: str, text: str) -> list[TypologyMatch]:
    t = f"{title}\n{text}".lower()
    matches: list[TypologyMatch] = []
    for typ, conf, kws in RULES:
        hit = None
        for k in kws:
            if k in t:
                hit = k
                break
        if hit:
            matches.append(TypologyMatch(typology=typ, confidence=conf, evidence=f"matched: {hit}"))
    return matches

