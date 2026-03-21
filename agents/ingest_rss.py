import feedparser
import requests
from bs4 import BeautifulSoup
from dateutil import parser as dtparser

from agents.db import upsert_source, upsert_case, replace_tags
from agents.parsing import extract_amount_usd, guess_tags, guess_agency

UA = {"User-Agent": "SentinelAIP/1.0 (Quantum Sentinel Solutions) public-ingest"}

def fetch_full_text(url: str) -> str:
    try:
        r = requests.get(url, headers=UA, timeout=30)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        # crude: grab main text blocks
        main = soup.find("main") or soup.body
        text = main.get_text("\n", strip=True) if main else ""
        return text[:20000]  # cap
    except Exception:
        return ""

def ingest_rss(source_name: str, feed_url: str, max_items: int = 50) -> dict:
    sid = upsert_source(source_name, feed_url, "rss")
    feed = feedparser.parse(feed_url)

    inserted = 0
    updated = 0

    for entry in feed.entries[:max_items]:
        url = getattr(entry, "link", "").strip()
        title = getattr(entry, "title", "").strip()
        summary = getattr(entry, "summary", "").strip()

        if not url or not title:
            continue

        published_date = None
        if getattr(entry, "published", None):
            try:
                published_date = dtparser.parse(entry.published).date()
            except Exception:
                published_date = None

        body_text = fetch_full_text(url)
        agency = guess_agency(title, body_text or summary)
        amount = extract_amount_usd(body_text or summary or title)
        tags = guess_tags(title, body_text or summary)

        is_new = upsert_case({
            "source_id": sid,
            "title": title,
            "published_date": published_date,
            "url": url,
            "summary": summary[:4000],
            "body_text": body_text[:20000],
            "agency": agency,
            "case_type": "public",
            "amount_usd": amount,
        })

        replace_tags(url, tags)

        if is_new:
            inserted += 1
        else:
            updated += 1

    return {"source": source_name, "inserted": inserted, "updated": updated}
