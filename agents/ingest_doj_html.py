import requests
from bs4 import BeautifulSoup
from dateutil import parser as dtparser
from agents.db import upsert_source, upsert_case, replace_tags
from agents.parsing import extract_amount_usd, guess_tags, guess_agency

LIST_URL = "https://www.justice.gov/civil/fraud-section-press-releases"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
}

def ingest_doj(max_pages: int = 1):
    sid = upsert_source(
        "DOJ Civil Fraud Section Press Releases",
        LIST_URL,
        "html"
    )

    inserted = 0
    updated = 0

    try:
        r = requests.get(LIST_URL, headers=HEADERS, timeout=30)
        r.raise_for_status()
    except Exception as e:
        return {"source": "DOJ", "error": str(e)}

    soup = BeautifulSoup(r.text, "html.parser")

    for a in soup.select("h2 a"):
        title = a.get_text(strip=True)
        url = a.get("href", "").strip()

        if url.startswith("/"):
            url = "https://www.justice.gov" + url

        if not title or not url:
            continue

        try:
            article = requests.get(url, headers=HEADERS, timeout=30)
            article.raise_for_status()
            article_soup = BeautifulSoup(article.text, "html.parser")
            main = article_soup.find("main") or article_soup.body
            body = main.get_text("\n", strip=True) if main else ""
        except Exception:
            continue

        amount = extract_amount_usd(body or title)
        agency = guess_agency(title, body)
        tags = guess_tags(title, body)

        is_new = upsert_case({
            "source_id": sid,
            "title": title,
            "published_date": None,
            "url": url,
            "summary": body[:500],
            "body_text": body[:20000],
            "agency": agency,
            "case_type": "FCA/DOJ",
            "amount_usd": amount,
        })

        replace_tags(url, tags)

        if is_new:
            inserted += 1
        else:
            updated += 1

    return {
        "source": "DOJ Civil Fraud",
        "inserted": inserted,
        "updated": updated
    }
